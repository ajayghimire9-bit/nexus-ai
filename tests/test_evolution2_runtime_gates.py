"""Source-only Evolution-2 runtime-gate tests. No scientific execution."""
from __future__ import annotations
import ast
import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from nexus.evolution1.catalogue import ContractError, Generator, Rule, Variant
from nexus.evolution1.resources import Limits, Work
from nexus.evolution2.bindings import (
    FAMILIES, bind_evaluation, fixture_checkpoint, fixture_world_model, reviewed_binding,
)
from nexus.evolution2.host import (
    ISOLATION_LIMITATIONS, MeteredHost, ProcessClock, encode_request, planned_operation,
    public_request, run_stub_evaluation, runtime_gate_status,
)
from nexus.evolution2.screen import run_screen


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'artifacts' / 'research_session_h16_same_state_library_usage.json'
SUCCESSOR = Variant(Rule.SUCCESSOR, Generator.IID, 16)
FLAT = Variant(Rule.FLAT, Generator.IID, 16)
BALANCED = Variant(Rule.SUCCESSOR, Generator.BALANCED, 16)


def bound(family='pendulum', variant=SUCCESSOR, **kwargs):
    binding = reviewed_binding(family)
    return bind_evaluation(
        family, variant,
        checkpoint_id=kwargs.get('checkpoint_id', binding.checkpoint_id),
        world_model_id=kwargs.get('world_model_id', binding.world_model_id),
        model_obs_dim=kwargs.get('obs', binding.obs_dim),
        model_n_actions=kwargs.get('actions', binding.n_actions),
        binding=kwargs.get('binding'),
        imagined_cap=kwargs.get('cap', 1536),
    )


def limits(logical=None, cpu=10**12, wall=10**12):
    return Limits(Work(), logical or Work(imagined_transitions=1536), cpu, wall)


def test_explicit_family_binding_rejects_unknown_and_inferred_identities():
    pendulum = reviewed_binding('pendulum')
    acrobot = reviewed_binding('acrobot')
    assert pendulum.n_actions == acrobot.n_actions == 3
    assert pendulum.obs_dim == 3 and acrobot.obs_dim == 6
    assert pendulum.family != acrobot.family
    for family in ('navigation', 'cartpole', 'successor_scale', '', None, True):
        with pytest.raises(ContractError, match='unknown_family'):
            reviewed_binding(family)
    with pytest.raises(ContractError, match='model_interface_mismatch'):
        bound('acrobot', obs=3, actions=3)
    with pytest.raises(ContractError, match='model_interface_mismatch'):
        bound('pendulum', obs=6, actions=3)


@pytest.mark.parametrize('field,value', [
    ('reward_symbol', 'acrobot_step_reward'),
    ('reward_timing', 'next'),
    ('action_kind', 'native_discrete_index'),
    ('action_values', (-1.0, 0.0, 1.0)),
    ('observation_layout', ('theta', 'velocity', 'other')),
    ('root_survival', 'multiply_root_survival'),
    ('wrapper_chain', ()),
])
def test_semantic_mismatch_is_rejected_before_dispatch(field, value):
    with pytest.raises(ContractError, match='family_semantics_mismatch|unsupported_action_decoding'):
        adapter = replace(reviewed_binding('pendulum'), **{field: value})
        bound(binding=adapter)


def test_action_decoding_and_termination_metadata_are_validated():
    pendulum = reviewed_binding('pendulum')
    assert pendulum.action_kind == 'continuous_scalar'
    assert pendulum.action_values == (-2.0, 0.0, 2.0)
    assert pendulum.reward_timing == 'current'
    assert pendulum.goal_termination == 'disabled'
    assert pendulum.truncation == 'time_limit'
    for values in ((2.0, 0.0, -2.0), (-2, 0, 2), (-2.0, True, 2.0), (-2.0, float('nan'), 2.0)):
        with pytest.raises(ContractError, match='family_semantics_mismatch|unsupported_action_decoding'):
            bound(binding=replace(pendulum, action_values=values))
    with pytest.raises(ContractError, match='unsupported_termination_semantics'):
        replace(pendulum, goal_termination='native')
    acrobot = reviewed_binding('acrobot')
    with pytest.raises(ContractError, match='unsupported_action_decoding'):
        replace(acrobot, action_values=(2, 1, 0))


def test_unsupported_operator_and_incompatible_checkpoint_fail_closed():
    with pytest.raises(ContractError, match='unsupported_balanced_generator'):
        bound(variant=BALANCED)
    with pytest.raises(ContractError, match='incompatible_checkpoint'):
        bound(checkpoint_id=fixture_checkpoint('acrobot'))
    with pytest.raises(ContractError, match='incompatible_checkpoint'):
        bound(world_model_id=fixture_world_model('acrobot'))
    item = bound()
    with pytest.raises(ContractError, match='scientific_dispatch_blocked'):
        item.require_scientific()
    assert item.scientific is False


def test_reservation_happens_before_any_worker_dispatch():
    calls = []

    class Forbidden:
        def run(self, payload, timeout_s, *, behavior='ok'):
            calls.append(payload)
            raise AssertionError('dispatch_without_reservation')

    item = bound()
    request = public_request(item)
    operation = planned_operation(item, request)
    host = MeteredHost((operation,), limits(logical=Work(imagined_transitions=1)),
                       supervisor=Forbidden())
    with pytest.raises(ContractError, match='pre_call_quota_exhausted'):
        host.dispatch(operation.key, request)
    assert calls == []
    with pytest.raises(ContractError, match='ledger_not_exported_to_policies'):
        host.ledger()


def test_successful_stub_keeps_declared_work_and_measured_clocks_separate():
    item = bound()
    report = run_stub_evaluation(item, limits(), timeout_s=5.0)
    assert report.status == 'complete_execution'
    assert report.receipt is not None and report.receipt.scientific is False
    assert report.declared_logical == item.declared_work
    assert report.physical_reserved == Work()
    assert report.physical_completed_reported == Work()
    assert report.lookups == 1
    assert report.measured.parent_cpu_ns >= 0
    assert report.measured.child_cpu_ns >= 0
    assert report.measured.wall_ns > 0
    assert report.measured.parent_cpu_ns != report.lookups
    assert report.authorized is False and report.scientific is False
    assert report.isolation_limitations == ISOLATION_LIMITATIONS
    assert 0.0 <= report.receipt.score <= 1.0


def test_worker_crash_timeout_and_invalid_output_are_charged():
    item = bound()
    crashed = run_stub_evaluation(item, limits(), stub_behavior='crash', timeout_s=5.0)
    assert crashed.status == 'incomplete_execution'
    assert crashed.reason == 'failed'
    assert crashed.receipt is None
    assert crashed.declared_logical == item.declared_work
    hung = run_stub_evaluation(item, limits(), stub_behavior='hang', timeout_s=0.3)
    assert hung.reason == 'interrupted'
    assert hung.receipt is None
    assert hung.measured.wall_ns >= 200_000_000
    invalid = run_stub_evaluation(item, limits(), stub_behavior='invalid', timeout_s=5.0)
    assert invalid.status == 'invalid_integrity'
    assert invalid.reason == 'invalid_result'
    empty = run_stub_evaluation(item, limits(), stub_behavior='empty', timeout_s=5.0)
    assert empty.reason == 'invalid_result'
    extra = run_stub_evaluation(item, limits(), stub_behavior='extra', timeout_s=5.0)
    assert extra.reason == 'invalid_result'
    huge = run_stub_evaluation(item, limits(), stub_behavior='oversized', timeout_s=5.0)
    assert huge.reason == 'invalid_result'


def test_replayed_and_unexpected_receipts_are_rejected():
    item = bound()
    request = public_request(item)
    operation = planned_operation(item, request)
    host = MeteredHost((operation,), limits(), timeout_s=5.0)
    receipt, outcome = host.dispatch(operation.key, request)
    assert outcome == 'success' and receipt is not None
    with pytest.raises(ContractError, match='unbound_or_replayed_receipt'):
        host.dispatch(operation.key, request)
    forged = dict(request)
    forged['hidden'] = 0.36
    with pytest.raises(ContractError, match='unexpected_request_fields'):
        encode_request(forged)
    ProcessClock()  # fail-closed construction must succeed on this host


def test_proposer_ipc_cannot_carry_hidden_task_family_scores():
    from nexus.evolution2 import tasks
    item = bound()
    request = public_request(item)
    dumped = json.dumps(request)
    assert 'hidden' not in dumped
    assert 'successor_scale' not in dumped
    assert '0.36' not in dumped
    assert '-0.40' not in dumped
    for weight in tasks.FAMILY_SPEC['successor_scale']['hidden']:
        assert str(weight) not in dumped
    worker = (ROOT / 'src/nexus/evolution2/evaluator_worker.py').read_text()
    assert 'FAMILY_SPEC' not in worker
    assert 'hidden_score' not in worker
    assert 'evolution2.tasks' not in worker


def test_existing_evolution_contracts_and_research_ledger_are_unchanged():
    report = run_screen(seed=7)
    assert report['scientific'] is False
    assert report['matched_lookups'] == 40
    assert report['illustration_label'] == 'synthetic_illustration_not_a_result'
    payload = json.loads(LEDGER.read_text())
    assert payload['ledger']['consumed_total_s'] == 305.842
    assert payload['remaining_session_allowance_s'] == 3294.158
    digest = hashlib.sha256(LEDGER.read_bytes()).hexdigest()
    assert digest == 'ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117'
    gates = runtime_gate_status()
    assert gates['trusted_adapters'] == 'PASS'
    assert gates['metered_execution_host'] == 'PASS'
    assert gates['process_separated_evaluator_stub'] == 'PASS'
    assert gates['request_binding'] == 'PASS'
    assert gates['bounded_ipc'] == 'PASS'
    assert gates['worker_cpu_enforcement'] == 'BLOCKED'
    assert gates['hardened_os_filesystem_sandbox'] == 'BLOCKED'
    assert gates['real_planner_simulator_checkpoint_execution'] == 'BLOCKED'
    assert gates['scientific_experiment_authorization'] == 'BLOCKED'
    assert gates['authorized'] is False


def test_runtime_modules_import_no_scientific_stack():
    forbidden = {'gymnasium', 'torch', 'optuna', 'tensorboard', 'numpy'}
    for relpath in (
        'src/nexus/evolution2/bindings.py',
        'src/nexus/evolution2/host.py',
        'src/nexus/evolution2/evaluator_worker.py',
    ):
        tree = ast.parse((ROOT / relpath).read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
        assert imported.isdisjoint(forbidden)
        assert '305.842' not in (ROOT / relpath).read_text()
    with pytest.raises(FrozenInstanceError):
        bound().declared_work.real_steps = 99
