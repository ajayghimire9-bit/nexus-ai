"""Metered stub host. Reuses Evolution-1 ReservationLedger. Not a sandbox."""
from __future__ import annotations
from dataclasses import dataclass
import json
import os
import subprocess
import sys
import threading
import time

from nexus.evolution1.catalogue import ContractError, digest
from nexus.evolution1.resources import Clock, Limits, Operation, ReservationLedger, Work
from nexus.evolution2.bindings import (
    BoundEvaluation, MAX_MESSAGE, MODE, REQUEST_KEYS, REQUEST_SCHEMA, RESPONSE_KEYS,
    RESPONSE_SCHEMA, SCIENTIFIC, derived_request_id, expected_event_id,
    validate_public_payload,
)

try:
    import resource
except ImportError:  # pragma: no cover - fail closed on platforms without it
    resource = None


ISOLATION_LIMITATIONS = (
    'same_filesystem_readable',
    'no_seccomp_or_landlock',
    'shared_uid_and_environment',
    'stderr_not_a_secret_channel_guarantee',
    'subprocess_is_not_a_security_sandbox',
    'rusage_children_includes_unrelated_subprocesses',
    'worker_cpu_measured_not_enforced',
)
STUB_BEHAVIORS = (
    'ok', 'crash', 'hang', 'invalid', 'empty', 'nonfinite', 'extra', 'oversized', 'flood',
)
CPU_ACCOUNTING = 'measured_not_enforced'


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
    worker_child_cpu_ns: int = 0

    def __post_init__(self):
        for value in (self.parent_cpu_ns, self.child_cpu_ns, self.wall_ns, self.worker_child_cpu_ns):
            if type(value) is not int or value < 0:
                raise ContractError('invalid_resource_count')


class ProcessClock:
    """Trusted host readings. Measurement only; not a per-worker CPU cap."""

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

    def children_elapsed_ns(self):
        try:
            child = _cpu_ns(resource.getrusage(resource.RUSAGE_CHILDREN)) - self._child0
        except (OSError, AttributeError) as exc:
            raise ContractError('cpu_measurement_unavailable') from exc
        if child < 0:
            raise ContractError('nonmonotonic_or_invalid_clock')
        return child

    def read(self, worker_child_cpu_ns=0):
        try:
            parent = _cpu_ns(resource.getrusage(resource.RUSAGE_SELF)) - self._parent0
            child = _cpu_ns(resource.getrusage(resource.RUSAGE_CHILDREN)) - self._child0
            wall = time.monotonic_ns() - self._wall0
        except (OSError, AttributeError) as exc:
            raise ContractError('cpu_measurement_unavailable') from exc
        if parent < 0 or child < 0 or wall < 0:
            raise ContractError('nonmonotonic_or_invalid_clock')
        return MeasuredTime(parent, child, wall, worker_child_cpu_ns)

    def ledger_clock(self):
        measured = self.read()
        return Clock(measured.parent_cpu_ns + measured.child_cpu_ns, measured.wall_ns)


def public_request(bound, *, request_id=None):
    if type(bound) is not BoundEvaluation:
        raise ContractError('bound_evaluation_required')
    context = bound.context.payload()
    derived = derived_request_id(
        bound.binding.family, bound.variant.fingerprint, bound.binding.fingerprint,
        bound.binding.checkpoint_id, bound.binding.world_model_id, context)
    if request_id is not None and request_id != derived:
        raise ContractError('request_identity_mismatch')
    payload = {
        'schema': REQUEST_SCHEMA,
        'request_id': derived,
        'family': bound.binding.family,
        'variant_id': bound.variant.fingerprint,
        'binding_fingerprint': bound.binding.fingerprint,
        'checkpoint_id': bound.binding.checkpoint_id,
        'world_model_id': bound.binding.world_model_id,
        'context': context,
        'mode': MODE,
    }
    validate_public_payload(payload)
    return payload


def encode_request(payload):
    validate_public_payload(payload)
    blob = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(blob) > MAX_MESSAGE:
        raise ContractError('invalid_or_oversized_request')
    return blob


def request_binding_digest(request):
    return digest(encode_request(request).decode())


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
    if data['event_id'] != expected_event_id(request):
        raise ContractError('unbound_or_replayed_receipt')
    return data


def _bounded_collect(proc, timeout_s, limit):
    stdout_parts = []
    stderr_parts = []
    overflow = threading.Event()

    def pump(pipe, parts):
        try:
            while not overflow.is_set():
                chunk = pipe.read(256)
                if not chunk:
                    return
                parts.append(chunk)
                if sum(len(part) for part in parts) > limit:
                    overflow.set()
                    return
        except (ValueError, OSError):
            return

    threads = [
        threading.Thread(target=pump, args=(proc.stdout, stdout_parts), daemon=True),
        threading.Thread(target=pump, args=(proc.stderr, stderr_parts), daemon=True),
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout_s
    timed_out = False
    while time.monotonic() < deadline:
        if overflow.is_set():
            break
        if proc.poll() is not None and not any(thread.is_alive() for thread in threads):
            break
        time.sleep(0.01)
    else:
        timed_out = True
    if overflow.is_set() or timed_out:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass
        proc.wait()
    for thread in threads:
        thread.join(timeout=0.5)
    stdout = b''.join(stdout_parts)[:limit]
    stderr = b''.join(stderr_parts)[:limit]
    if overflow.is_set():
        return 'invalid_result', stdout, stderr
    if timed_out or proc.returncode is None:
        return 'interrupted', stdout, stderr
    if proc.returncode != 0:
        return 'failed', stdout, stderr
    return 'success', stdout, stderr


class ProcessSupervisor:
    """Hard wall timeout and bounded pipes. Not OS isolation or CPU enforcement."""

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
            proc = subprocess.Popen(
                [sys.executable, '-B', '-m', 'nexus.evolution2.evaluator_worker'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            )
        except OSError:
            return {'outcome': 'failed', 'stdout': b'', 'returncode': None}
        try:
            proc.stdin.write(blob)
            proc.stdin.close()
        except (OSError, ValueError, BrokenPipeError):
            try:
                proc.kill()
            except OSError:
                pass
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            return {'outcome': 'failed', 'stdout': b'', 'returncode': proc.returncode}
        outcome, stdout, _stderr = _bounded_collect(proc, float(timeout_s), MAX_MESSAGE)
        return {'outcome': outcome, 'stdout': stdout, 'returncode': proc.returncode}


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
    cpu_enforced: bool = False
    cpu_accounting: str = CPU_ACCOUNTING


def runtime_gate_status():
    return {
        'trusted_adapters': 'PASS',
        'metered_execution_host': 'PASS',
        'process_separated_evaluator_stub': 'PASS',
        'request_binding': 'PASS',
        'bounded_ipc': 'PASS',
        'worker_cpu_enforcement': 'BLOCKED',
        'hardened_os_filesystem_sandbox': 'BLOCKED',
        'real_planner_simulator_checkpoint_execution': 'BLOCKED',
        'development_twelve_arm_binding': 'PASS',
        'scientific_experiment_authorization': 'BLOCKED',
        'scientific': False,
        'authorized': False,
        'cpu_accounting': CPU_ACCOUNTING,
        'isolation_limitations': list(ISOLATION_LIMITATIONS),
    }


class MeteredHost:
    """Owns the ledger. Candidate policies never receive it."""

    def __init__(self, operations, limits, *, clock=None, supervisor=None, timeout_s=2.0):
        if type(timeout_s) not in (int, float) or not 0 < timeout_s <= 30:
            raise ContractError('invalid_supervisor_timeout')
        if type(operations) is not tuple:
            raise ContractError('invalid_operation_plan')
        self._clock = clock or ProcessClock()
        self._limits = limits
        self._operations = {op.key: op for op in operations}
        self._ledger = ReservationLedger(operations, limits)
        self._supervisor = supervisor or ProcessSupervisor()
        self._timeout_s = float(timeout_s)
        self._seen = set()
        self._closed = None
        self._worker_child_cpu_ns = 0

    def ledger(self):
        raise ContractError('ledger_not_exported_to_policies')

    def _remaining_wall_s(self):
        remaining_ns = self._limits.wall_ns - self._clock.read().wall_ns
        if remaining_ns <= 0:
            return 0.0
        return min(self._timeout_s, remaining_ns / 1_000_000_000)

    def _assert_committed_request(self, key, request):
        if key not in self._operations:
            raise ContractError('unknown_or_duplicate_operation')
        if request_binding_digest(request) != self._operations[key].cache_record_hash:
            raise ContractError('request_binding_mismatch')

    def _settle_pending(self, ticket, outcome):
        if ticket is None:
            return
        try:
            pending = self._ledger._pending
        except AttributeError:
            pending = None
        if pending is ticket:
            try:
                self._ledger.settle(ticket, outcome, self._clock.ledger_clock())
            except ContractError:
                try:
                    self._ledger.settle(ticket, 'failed', self._clock.ledger_clock())
                except ContractError:
                    pass

    def dispatch(self, key, request, *, stub_behavior='ok'):
        if self._closed is not None:
            raise ContractError('ledger_finalized')
        self._assert_committed_request(key, request)
        request_id = _hex64(request['request_id'])
        if request_id in self._seen:
            raise ContractError('unbound_or_replayed_receipt')
        timeout_s = self._remaining_wall_s()
        ticket = None
        try:
            ticket = self._ledger.reserve(key, self._clock.ledger_clock())
            self._seen.add(request_id)
            if timeout_s <= 0:
                self._settle_pending(ticket, 'interrupted')
                return None, 'interrupted'
            before = self._clock.children_elapsed_ns()
            try:
                raw = self._supervisor.run(request, timeout_s, behavior=stub_behavior)
            except Exception:
                self._settle_pending(ticket, 'failed')
                return None, 'failed'
            after = self._clock.children_elapsed_ns()
            self._worker_child_cpu_ns += max(0, after - before)
            outcome = raw['outcome']
            receipt = None
            if outcome == 'success':
                try:
                    parsed = parse_response(raw['stdout'], request)
                    receipt = StubReceipt(parsed['variant_id'], parsed['score'], parsed['failed'],
                                          parsed['event_id'], parsed['request_id'])
                except ContractError:
                    outcome = 'invalid_result'
            self._settle_pending(ticket, outcome)
            return receipt, outcome
        except ContractError:
            self._settle_pending(ticket, 'invalid_result')
            raise

    def close(self):
        report = self._ledger.close(self._clock.ledger_clock())
        measured = self._clock.read(self._worker_child_cpu_ns)
        self._closed = report
        return report, measured


def planned_operation(bound, request):
    if type(bound) is not BoundEvaluation:
        raise ContractError('bound_evaluation_required')
    validate_public_payload(request)
    if request['variant_id'] != bound.variant.fingerprint:
        raise ContractError('request_binding_mismatch')
    if request['binding_fingerprint'] != bound.binding.fingerprint:
        raise ContractError('request_binding_mismatch')
    return Operation('eval_0', 'cached', bound.declared_work, request_binding_digest(request))


def run_stub_evaluation(bound, limits, *, stub_behavior='ok', timeout_s=2.0, request_id=None,
                        enforce_worker_cpu=False):
    if type(bound) is not BoundEvaluation or bound.scientific is not False:
        raise ContractError('scientific_dispatch_blocked')
    if enforce_worker_cpu:
        raise ContractError('cpu_enforcement_unavailable')
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
        measured, 1, ISOLATION_LIMITATIONS, False, False, False, CPU_ACCOUNTING,
    )
