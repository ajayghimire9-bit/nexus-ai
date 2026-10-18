"""Pre-call reservation state machine; no executor, clock reader or authorization.

A trusted future host must supply operation metadata and monotonic elapsed
clock readings. Tests supply synthetic values. This is not a process meter.
"""
from dataclasses import dataclass

from .catalogue import ContractError
from .fixtures import Journal


def _count(value: int, maximum: int = 10**15) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ContractError('invalid_resource_count')
    return value


@dataclass(frozen=True)
class Work:
    real_steps: int = 0
    imagined_transitions: int = 0
    model_calls: int = 0
    network_forwards: int = 0

    def __post_init__(self):
        for value in self.values():
            _count(value)

    def values(self):
        return (self.real_steps, self.imagined_transitions,
                self.model_calls, self.network_forwards)

    def plus(self, other):
        if type(other) is not Work:
            raise ContractError('invalid_work')
        return Work(*(a + b for a, b in zip(self.values(), other.values())))

    def fits(self, cap):
        if type(cap) is not Work:
            raise ContractError('invalid_work_cap')
        return all(a <= b for a, b in zip(self.values(), cap.values()))

    def payload(self):
        return dict(zip(('real_steps', 'imagined_transitions', 'model_calls',
                         'network_forwards'), self.values()))


def model_work(observation_shape: tuple, action_rows: int,
               network_forwards: int = 1) -> Work:
    """Charge observation rows, including explicit single-action broadcast.

    Shape metadata only. No observation values, actions or models are accessed.
    A future adapter must check real arrays and attest actual network calls.
    """
    if type(observation_shape) is not tuple or len(observation_shape) not in (1, 2):
        raise ContractError('invalid_observation_shape')
    for dim in observation_shape:
        if _count(dim) == 0:
            raise ContractError('empty_observation_shape')
    rows = 1 if len(observation_shape) == 1 else observation_shape[0]
    if _count(action_rows) not in (1, rows):
        raise ContractError('action_batch_mismatch')
    if _count(network_forwards) == 0:
        raise ContractError('missing_network_count')
    return Work(imagined_transitions=rows, model_calls=1,
                network_forwards=network_forwards)


@dataclass(frozen=True)
class Operation:
    key: str
    kind: str
    cost: Work
    cache_record_hash: str | None = None

    def __post_init__(self):
        if (type(self.key) is not str or not 1 <= len(self.key) <= 64
                or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in self.key)):
            raise ContractError('invalid_operation_id')
        if type(self.kind) is not str or self.kind not in ('environment', 'model', 'cached'):
            raise ContractError('invalid_operation_kind')
        if type(self.cost) is not Work or not any(self.cost.values()):
            raise ContractError('missing_operation_cost')
        if self.kind == 'environment' and self.cost != Work(real_steps=1):
            raise ContractError('environment_operation_must_be_one_step')
        if self.kind == 'model' and (self.cost.real_steps != 0
                or self.cost.imagined_transitions < 1 or self.cost.model_calls != 1
                or self.cost.network_forwards < 1):
            raise ContractError('invalid_model_cost')
        if self.kind == 'cached':
            h = self.cache_record_hash
            if type(h) is not str or len(h) != 64 or any(c not in '0123456789abcdef' for c in h):
                raise ContractError('cached_record_reference_required')
        elif self.cache_record_hash is not None:
            raise ContractError('unexpected_cache_reference')

    @property
    def physical_cost(self):
        return Work() if self.kind == 'cached' else self.cost


@dataclass(frozen=True)
class Clock:
    """Trusted host's elapsed readings since one common origin, in nanoseconds."""
    cpu_ns: int
    wall_ns: int

    def __post_init__(self):
        _count(self.cpu_ns)
        _count(self.wall_ns)


@dataclass(frozen=True)
class Limits:
    physical: Work
    logical: Work
    cpu_ns: int
    wall_ns: int

    def __post_init__(self):
        if type(self.physical) is not Work or type(self.logical) is not Work:
            raise ContractError('invalid_work_cap')
        if _count(self.cpu_ns) == 0 or _count(self.wall_ns) == 0:
            raise ContractError('invalid_time_cap')


@dataclass(frozen=True)
class Ticket:
    operation: Operation


@dataclass(frozen=True)
class ExecutionReport:
    status: str
    reason: str | None
    physical_reserved: Work
    physical_completed_reported: Work
    physical_unknown_upper_bound: Work
    logical_charged: Work
    elapsed: Clock
    completed_keys: tuple
    unresolved_keys: tuple
    pending_key: str | None
    events: tuple


class ReservationLedger:
    """Sequential trusted-host contract over a fixed operation plan.

    Reservation is required before dispatch. There is deliberately no callable,
    environment/model reference, allocation or execution API in this class.
    """
    def __init__(self, operations: tuple, limits: Limits):
        if type(operations) is not tuple or not 1 <= len(operations) <= 8192:
            raise ContractError('invalid_operation_plan')
        if any(type(op) is not Operation for op in operations):
            raise ContractError('invalid_operation_plan')
        keys = [op.key for op in operations]
        if len(keys) != len(set(keys)):
            raise ContractError('duplicate_operation')
        if type(limits) is not Limits:
            raise ContractError('invalid_limits')
        self._plan = {op.key: op for op in operations}
        self._limits = limits
        self._reserved = Work()
        self._completed_work = Work()
        self._unknown = Work()
        self._logical = Work()
        self._seen = set()
        self._completed = set()
        self._pending = None
        self._clock = Clock(0, 0)
        self._reason = None
        self._report = None
        self._journal = Journal()
        self._journal.append('planned', {
            'operations': [{'key': op.key, 'kind': op.kind, 'cost': op.cost.payload(),
                            'cache_record_hash': op.cache_record_hash} for op in operations],
            'limits': {'physical': limits.physical.payload(), 'logical': limits.logical.payload(),
                       'cpu_ns': limits.cpu_ns, 'wall_ns': limits.wall_ns}})

    def _live(self):
        if self._report is not None:
            raise ContractError('ledger_finalized')

    def _observe(self, clock):
        if (type(clock) is not Clock or clock.cpu_ns < self._clock.cpu_ns
                or clock.wall_ns < self._clock.wall_ns):
            self._reason = 'invalid_clock'
            raise ContractError('nonmonotonic_or_invalid_clock')
        self._clock = clock
        if clock.cpu_ns >= self._limits.cpu_ns or clock.wall_ns >= self._limits.wall_ns:
            self._reason = self._reason or 'time_cap'

    def reserve(self, key: str, clock: Clock) -> Ticket:
        self._live()
        self._observe(clock)
        if self._reason is not None:
            raise ContractError('ledger_stopped')
        if self._pending is not None:
            raise ContractError('operation_already_pending')
        if type(key) is not str or key not in self._plan or key in self._seen:
            raise ContractError('unknown_or_duplicate_operation')
        op = self._plan[key]
        physical = self._reserved.plus(op.physical_cost)
        logical = self._logical.plus(op.cost)
        if not physical.fits(self._limits.physical) or not logical.fits(self._limits.logical):
            self._reason = 'work_cap'
            self._journal.append('quota_rejected', {'operation': key})
            raise ContractError('pre_call_quota_exhausted')
        self._reserved, self._logical = physical, logical
        self._seen.add(key)
        self._pending = Ticket(op)
        self._journal.append('reserved', {'operation': key, 'kind': op.kind,
            'cache_record_hash': op.cache_record_hash,
            'physical': op.physical_cost.payload(), 'logical': op.cost.payload(),
            'cpu_ns': clock.cpu_ns, 'wall_ns': clock.wall_ns})
        return self._pending

    def settle(self, ticket: Ticket, outcome: str, clock: Clock) -> None:
        self._live()
        if ticket is not self._pending or ticket is None:
            raise ContractError('unknown_or_replayed_ticket')
        if type(outcome) is not str or outcome not in ('success', 'failed', 'interrupted', 'invalid_result'):
            raise ContractError('invalid_settlement')
        # Record completed/unknown work even when the call passed the time cap.
        # Invalid clocks leave the pending reservation available for close().
        self._observe(clock)
        op = ticket.operation
        if outcome == 'success':
            self._completed_work = self._completed_work.plus(op.physical_cost)
            self._completed.add(op.key)
        else:
            self._unknown = self._unknown.plus(op.physical_cost)
            self._reason = ('invalid_result' if outcome == 'invalid_result'
                            else self._reason or outcome)
        self._pending = None
        self._journal.append('settled', {'operation': op.key, 'outcome': outcome,
            'cpu_ns': clock.cpu_ns, 'wall_ns': clock.wall_ns})

    def close(self, clock: Clock) -> ExecutionReport:
        self._live()
        try:
            self._observe(clock)
        except ContractError:
            pass  # Preserve the last trustworthy clock and classify invalid.
        pending = self._pending.operation if self._pending is not None else None
        unknown = self._unknown.plus(pending.physical_cost if pending else Work())
        unresolved = tuple(k for k in self._plan if k not in self._completed)
        if self._reason in ('invalid_clock', 'invalid_result'):
            status = 'invalid_integrity'
        elif self._reason is not None or unresolved:
            status = 'incomplete_execution'
        else:
            status = 'complete_execution'
        reason = self._reason or ('pending_or_missing_operations' if unresolved else None)
        self._journal.append('closed', {'status': status, 'reason': reason,
            'completed': sorted(self._completed), 'unresolved': list(unresolved)})
        self._report = ExecutionReport(status, reason, self._reserved,
            self._completed_work, unknown, self._logical, self._clock,
            tuple(k for k in self._plan if k in self._completed), unresolved,
            pending.key if pending else None, self._journal.snapshot())
        return self._report
