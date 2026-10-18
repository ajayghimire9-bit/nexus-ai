"""Metered stub host. Reuses Evolution-1 ReservationLedger. Not a sandbox."""
from __future__ import annotations
from dataclasses import dataclass
import json
import os
import subprocess
import sys
import time

from nexus.evolution1.catalogue import ContractError, digest
from nexus.evolution1.resources import Clock, Limits, Operation, ReservationLedger, Work
from nexus.evolution2.bindings import BoundEvaluation, MODE, SCIENTIFIC

try:
    import resource
except ImportError:  # pragma: no cover - fail closed on platforms without it
    resource = None


REQUEST_SCHEMA = 'nexus.evolution2.evaluator_request.v1'
RESPONSE_SCHEMA = 'nexus.evolution2.evaluator_response.v1'
REQUEST_KEYS = frozenset({
    'schema', 'request_id', 'family', 'variant_id', 'binding_fingerprint',
    'checkpoint_id', 'world_model_id', 'context', 'mode',
})
RESPONSE_KEYS = frozenset({
    'schema', 'request_id', 'variant_id', 'score', 'failed', 'event_id',
})
MAX_MESSAGE = 4096
ISOLATION_LIMITATIONS = (
    'same_filesystem_readable',
    'no_seccomp_or_landlock',
    'shared_uid_and_environment',
    'stderr_not_a_secret_channel_guarantee',
    'subprocess_is_not_a_security_sandbox',
)
STUB_BEHAVIORS = ('ok', 'crash', 'hang', 'invalid', 'empty', 'nonfinite', 'extra', 'oversized')


def _hex64(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ContractError('invalid_identity_hash')
    return value


def _cpu_ns(usage):
    return int((usage.ru_utime + usage.ru_stime) * 1_000_000_000)


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ContractError('duplicate_field')
        out[key] = value
    return out


def _nonfinite(_):
    raise ContractError('nonfinite_json')


@dataclass(frozen=True)
class MeasuredTime:
    parent_cpu_ns: int
    child_cpu_ns: int
    wall_ns: int

    def __post_init__(self):
        for value in (self.parent_cpu_ns, self.child_cpu_ns, self.wall_ns):
            if type(value) is not int or value < 0:
                raise ContractError('invalid_resource_count')


class ProcessClock:
    """Trusted host readings. Parent and child CPU are distinct from wall."""

    def __init__(self):
        if resource is None or not hasattr(resource, 'RUSAGE_SELF') \
                or not hasattr(resource, 'RUSAGE_CHILDREN'):
            raise ContractError('cpu_measurement_unavailable')
        try:
            self._wall0 = time.monotonic_ns()
            self._parent0 = _cpu_ns(resource.getrusage(resource.RUSAGE_SELF))
            self._child0 = _cpu_ns(resource.getrusage(resource.RUSAGE_CHILDREN))
        except (OSError, AttributeError) as exc:
            raise ContractError('cpu_measurement_unavailable') from exc

    def read(self):
        try:
            parent = _cpu_ns(resource.getrusage(resource.RUSAGE_SELF)) - self._parent0
            child = _cpu_ns(resource.getrusage(resource.RUSAGE_CHILDREN)) - self._child0
            wall = time.monotonic_ns() - self._wall0
        except (OSError, AttributeError) as exc:
            raise ContractError('cpu_measurement_unavailable') from exc
        if parent < 0 or child < 0 or wall < 0:
            raise ContractError('nonmonotonic_or_invalid_clock')
        return MeasuredTime(parent, child, wall)

    def ledger_clock(self):
        measured = self.read()
        return Clock(measured.parent_cpu_ns + measured.child_cpu_ns, measured.wall_ns)


def public_request(bound, *, request_id=None):
    if type(bound) is not BoundEvaluation:
        raise ContractError('bound_evaluation_required')
    payload = {
        'schema': REQUEST_SCHEMA,
        'request_id': request_id or digest({
            'family': bound.binding.family, 'variant': bound.variant.fingerprint,
            'binding': bound.binding.fingerprint, 'mode': MODE,
        }),
        'family': bound.binding.family,
        'variant_id': bound.variant.fingerprint,
        'binding_fingerprint': bound.binding.fingerprint,
        'checkpoint_id': bound.binding.checkpoint_id,
        'world_model_id': bound.binding.world_model_id,
        'context': bound.context.payload(),
        'mode': MODE,
    }
    if set(payload) != REQUEST_KEYS:
        raise ContractError('invalid_request_schema')
    _hex64(payload['request_id'])
    return payload


def encode_request(payload):
    if type(payload) is not dict or set(payload) != REQUEST_KEYS:
        raise ContractError('unexpected_request_fields')
    blob = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(blob) > MAX_MESSAGE:
        raise ContractError('invalid_or_oversized_request')
    return blob


def parse_response(raw, request):
    if type(raw) is not bytes or not raw or len(raw) > MAX_MESSAGE:
        raise ContractError('invalid_or_oversized_response')
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique, parse_constant=_nonfinite)
    except (ValueError, TypeError, RecursionError, UnicodeDecodeError) as exc:
        raise ContractError('invalid_json') from exc
    if type(data) is not dict or set(data) != RESPONSE_KEYS:
        raise ContractError('unexpected_response_fields')
    if data['schema'] != RESPONSE_SCHEMA:
        raise ContractError('invalid_response_schema')
    if data['request_id'] != request['request_id'] or data['variant_id'] != request['variant_id']:
        raise ContractError('unbound_or_replayed_receipt')
    if type(data['failed']) is not bool:
        raise ContractError('invalid_result')
    if data['failed']:
        if data['score'] is not None:
            raise ContractError('failed_feedback_has_score')
    elif type(data['score']) not in (int, float) or not 0 <= data['score'] <= 1:
        raise ContractError('invalid_result')
    _hex64(data['event_id'])
    return data


class ProcessSupervisor:
    """Hard wall timeout around the worker. Not OS isolation."""

    def run(self, payload, timeout_s, *, behavior='ok'):
        if type(timeout_s) not in (int, float) or not 0 < timeout_s <= 30:
            raise ContractError('invalid_supervisor_timeout')
        if behavior not in STUB_BEHAVIORS:
            raise ContractError('unknown_stub_behavior')
        blob = encode_request(payload)
        env = os.environ.copy()
        env['NEXUS_E2_STUB_BEHAVIOR'] = behavior
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        src = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env['PYTHONPATH'] = src + os.pathsep + env.get('PYTHONPATH', '')
        try:
            completed = subprocess.run(
                [sys.executable, '-B', '-m', 'nexus.evolution2.evaluator_worker'],
                input=blob, capture_output=True, timeout=float(timeout_s), env=env,
            )
        except subprocess.TimeoutExpired:
            return {'outcome': 'interrupted', 'stdout': b'', 'returncode': None}
        if completed.returncode != 0:
            return {'outcome': 'failed', 'stdout': completed.stdout or b'',
                    'returncode': completed.returncode}
        return {'outcome': 'success', 'stdout': completed.stdout or b'',
                'returncode': completed.returncode}


@dataclass(frozen=True)
class StubReceipt:
    variant_id: str
    score: float | None
    failed: bool
    event_id: str
    request_id: str
    scientific: bool = SCIENTIFIC


@dataclass(frozen=True)
class HostReport:
    status: str
    reason: str | None
    receipt: StubReceipt | None
    declared_logical: Work
    physical_reserved: Work
    physical_completed_reported: Work
    physical_unknown_upper_bound: Work
    measured: MeasuredTime
    lookups: int
    isolation_limitations: tuple
    scientific: bool
    authorized: bool


def runtime_gate_status():
    return {
        'trusted_adapters': 'PASS',
        'metered_execution_host': 'PASS',
        'process_separated_evaluator_stub': 'PASS',
        'hardened_os_filesystem_sandbox': 'BLOCKED',
        'real_planner_simulator_checkpoint_execution': 'BLOCKED',
        'scientific_experiment_authorization': 'BLOCKED',
        'scientific': False,
        'authorized': False,
        'isolation_limitations': list(ISOLATION_LIMITATIONS),
    }


class MeteredHost:
    """Owns the ledger. Candidate policies never receive it."""

    def __init__(self, operations, limits, *, clock=None, supervisor=None, timeout_s=2.0):
        if type(timeout_s) not in (int, float) or not 0 < timeout_s <= 30:
            raise ContractError('invalid_supervisor_timeout')
        self._clock = clock or ProcessClock()
        self._limits = limits
        self._ledger = ReservationLedger(operations, limits)
        self._supervisor = supervisor or ProcessSupervisor()
        self._timeout_s = float(timeout_s)
        self._seen = set()
        self._closed = None

    def ledger(self):
        raise ContractError('ledger_not_exported_to_policies')

    def _remaining_wall_s(self):
        remaining_ns = self._limits.wall_ns - self._clock.read().wall_ns
        if remaining_ns <= 0:
            return 0.0
        return min(self._timeout_s, remaining_ns / 1_000_000_000)

    def dispatch(self, key, request, *, stub_behavior='ok'):
        if self._closed is not None:
            raise ContractError('ledger_finalized')
        if type(request) is not dict or set(request) != REQUEST_KEYS:
            raise ContractError('unexpected_request_fields')
        request_id = _hex64(request['request_id'])
        if request_id in self._seen:
            raise ContractError('unbound_or_replayed_receipt')
        timeout_s = self._remaining_wall_s()
        ticket = self._ledger.reserve(key, self._clock.ledger_clock())
        self._seen.add(request_id)
        if timeout_s <= 0:
            self._ledger.settle(ticket, 'interrupted', self._clock.ledger_clock())
            return None, 'interrupted'
        raw = self._supervisor.run(request, timeout_s, behavior=stub_behavior)
        outcome = raw['outcome']
        receipt = None
        if outcome == 'success':
            try:
                parsed = parse_response(raw['stdout'], request)
                receipt = StubReceipt(parsed['variant_id'], parsed['score'], parsed['failed'],
                                      parsed['event_id'], parsed['request_id'])
            except ContractError:
                outcome = 'invalid_result'
        self._ledger.settle(ticket, outcome, self._clock.ledger_clock())
        return receipt, outcome

    def close(self):
        report = self._ledger.close(self._clock.ledger_clock())
        measured = self._clock.read()
        self._closed = report
        return report, measured


def planned_operation(bound, request):
    if type(bound) is not BoundEvaluation:
        raise ContractError('bound_evaluation_required')
    blob = encode_request(request)
    return Operation('eval_0', 'cached', bound.declared_work, digest(blob.decode()))


def run_stub_evaluation(bound, limits, *, stub_behavior='ok', timeout_s=2.0, request_id=None):
    if type(bound) is not BoundEvaluation or bound.scientific is not False:
        raise ContractError('scientific_dispatch_blocked')
    request = public_request(bound, request_id=request_id)
    operation = planned_operation(bound, request)
    host = MeteredHost((operation,), limits, timeout_s=timeout_s)
    receipt, outcome = host.dispatch(operation.key, request, stub_behavior=stub_behavior)
    ledger_report, measured = host.close()
    status = ledger_report.status
    if outcome != 'success' and status == 'complete_execution':
        status = 'incomplete_execution'
    return HostReport(
        status, ledger_report.reason if outcome == 'success' else outcome, receipt,
        ledger_report.logical_charged, ledger_report.physical_reserved,
        ledger_report.physical_completed_reported, ledger_report.physical_unknown_upper_bound,
        measured, 1, ISOLATION_LIMITATIONS, False, False,
    )
