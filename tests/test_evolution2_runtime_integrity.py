"""Adversarial integrity tests for Evolution-2 runtime gates. Not science."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from nexus.evolution1.catalogue import ContractError, Generator, Rule, Variant, catalogue
from nexus.evolution1.resources import Limits, Operation, Work
from nexus.evolution2.bindings import bind_evaluation, reviewed_binding, validate_public_payload
from nexus.evolution2.evaluator_worker import parse_request
from nexus.evolution2.host import (
    MAX_MESSAGE, MeteredHost, ProcessSupervisor, encode_request, planned_operation,
    public_request, request_binding_digest, run_stub_evaluation, runtime_gate_status,
)


SUCCESSOR = Variant(Rule.SUCCESSOR, Generator.IID, 16)
FLAT = Variant(Rule.FLAT, Generator.IID, 16)
BALANCED = next(
    v for v in catalogue()
    if v.generator is Generator.BALANCED and v.rule is Rule.SUCCESSOR and v.horizon == 16
)


def bound(variant=SUCCESSOR):
    binding = reviewed_binding('pendulum')
    return bind_evaluation(
        'pendulum', variant, checkpoint_id=binding.checkpoint_id,
        world_model_id=binding.world_model_id, model_obs_dim=binding.obs_dim,
        model_n_actions=binding.n_actions,
    )


def limits():
    return Limits(Work(), Work(imagined_transitions=1536), 10**12, 10**12)


def test_hr1_reserved_request_cannot_be_substituted():
    first = bound(SUCCESSOR)
    second = bound(FLAT)
    req_a = public_request(first)
    req_b = public_request(second)
    assert req_a['variant_id'] != req_b['variant_id']
    operation = planned_operation(first, req_a)
    seen = []

    class Probe:
        def run(self, payload, timeout_s, *, behavior='ok'):
            seen.append(payload['variant_id'])
            if payload['variant_id'] != req_a['variant_id']:
                raise AssertionError('substituted_request_dispatched')
            return ProcessSupervisor().run(payload, timeout_s, behavior=behavior)

    host = MeteredHost((operation,), limits(), supervisor=Probe(), timeout_s=5.0)
    with pytest.raises(ContractError, match='request_binding_mismatch'):
        host.dispatch(operation.key, req_b)
    assert seen == []
    receipt, outcome = host.dispatch(operation.key, req_a)
    assert outcome == 'success' and receipt is not None
    assert receipt.variant_id == req_a['variant_id']


def test_hr2_host_and_worker_reject_substituted_balanced_identity():
    item = bound()
    valid = public_request(item)
    crafted = dict(valid)
    crafted['variant_id'] = BALANCED.fingerprint
    with pytest.raises(ContractError, match='request_identity_mismatch'):
        encode_request(crafted)
    with pytest.raises(ContractError, match='request_identity_mismatch'):
        parse_request(json.dumps(crafted, sort_keys=True, separators=(',', ':')).encode())
    with pytest.raises(ContractError, match='request_identity_mismatch'):
        validate_public_payload(dict(valid, variant_id=BALANCED.fingerprint, request_id=valid['request_id']))
    operation = planned_operation(item, valid)
    host = MeteredHost((operation,), limits(), timeout_s=5.0)
    with pytest.raises(ContractError, match='request_binding_mismatch|request_identity_mismatch'):
        host.dispatch(operation.key, crafted)
    forged = Operation('eval_0', 'cached', item.declared_work, 'ab' * 32)
    with pytest.raises(ContractError, match='request_binding_mismatch|request_identity_mismatch'):
        MeteredHost((forged,), limits()).dispatch('eval_0', crafted)
    own = bound(BALANCED)
    assert own.variant.generator is Generator.BALANCED
    assert own.scientific is False


def test_hr3_cpu_is_measured_and_not_enforced():
    status = runtime_gate_status()
    assert status['worker_cpu_enforcement'] == 'BLOCKED'
    assert status['cpu_accounting'] == 'measured_not_enforced'
    assert 'worker_cpu_measured_not_enforced' in status['isolation_limitations']
    item = bound()
    with pytest.raises(ContractError, match='cpu_enforcement_unavailable'):
        run_stub_evaluation(item, limits(), enforce_worker_cpu=True, timeout_s=5.0)
    report = run_stub_evaluation(item, limits(), timeout_s=5.0)
    assert report.cpu_enforced is False
    assert report.cpu_accounting == 'measured_not_enforced'
    assert report.measured.child_cpu_ns >= 0
    assert report.measured.worker_child_cpu_ns >= 0
    assert report.authorized is False


def test_hr4_supervisor_bounds_output_while_reading():
    item = bound()
    request = public_request(item)
    raw = ProcessSupervisor().run(request, 5.0, behavior='flood')
    assert raw['outcome'] == 'invalid_result'
    assert len(raw['stdout']) <= MAX_MESSAGE
    report = run_stub_evaluation(item, limits(), stub_behavior='flood', timeout_s=5.0)
    assert report.receipt is None
    assert report.reason == 'invalid_result'
    assert report.status == 'invalid_integrity'


def test_hr5_supervisor_failures_settle_without_a_receipt():
    item = bound()
    request = public_request(item)
    operation = planned_operation(item, request)

    class Boom:
        def run(self, payload, timeout_s, *, behavior='ok'):
            raise OSError('exec format error')

    host = MeteredHost((operation,), limits(), supervisor=Boom(), timeout_s=5.0)
    receipt, outcome = host.dispatch(operation.key, request)
    assert receipt is None and outcome == 'failed'
    report, _measured = host.close()
    assert report.pending_key is None
    assert report.status == 'incomplete_execution'
    assert operation.key not in report.completed_keys


def test_hr5_invalid_request_does_not_leave_a_pending_reservation():
    item = bound()
    request = public_request(item)
    operation = planned_operation(item, request)
    host = MeteredHost((operation,), limits(), timeout_s=5.0)
    bad = dict(request)
    bad['context'] = dict(request['context'], imagined_cap=True)
    with pytest.raises(ContractError):
        host.dispatch(operation.key, bad)
    report, _measured = host.close()
    assert report.pending_key is None
    assert report.status == 'incomplete_execution'


def test_forged_event_identity_is_not_accepted():
    item = bound()
    request = public_request(item)
    operation = planned_operation(item, request)

    class Forged:
        def run(self, payload, timeout_s, *, behavior='ok'):
            body = {
                'schema': 'nexus.evolution2.evaluator_response.v1',
                'request_id': payload['request_id'],
                'variant_id': payload['variant_id'],
                'score': 1.0,
                'failed': False,
                'event_id': '0' * 64,
            }
            return {'outcome': 'success', 'stdout': json.dumps(body).encode(), 'returncode': 0}

    host = MeteredHost((operation,), limits(), supervisor=Forged(), timeout_s=5.0)
    receipt, outcome = host.dispatch(operation.key, request)
    assert receipt is None and outcome == 'invalid_result'


def test_candidate_cannot_rebind_request_identity_or_export_the_ledger():
    item = bound()
    with pytest.raises(ContractError, match='request_identity_mismatch'):
        public_request(item, request_id='ab' * 32)
    request = public_request(item)
    operation = planned_operation(item, request)
    host = MeteredHost((operation,), limits(), timeout_s=5.0)
    with pytest.raises(ContractError, match='ledger_not_exported_to_policies'):
        host.ledger()
    assert request_binding_digest(request) == operation.cache_record_hash
    assert runtime_gate_status()['scientific_experiment_authorization'] == 'BLOCKED'
    assert runtime_gate_status()['authorized'] is False


def test_research_ledger_file_is_untouched():
    payload = json.loads(
        (Path(__file__).resolve().parents[1] / 'artifacts' /
         'research_session_h16_same_state_library_usage.json').read_text())
    assert payload['ledger']['consumed_total_s'] == 305.842
    assert payload['remaining_session_allowance_s'] == 3294.158
