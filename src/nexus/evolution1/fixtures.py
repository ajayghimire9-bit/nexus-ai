"""Training-only synthetic feedback transport; never evaluates a controller.

All costs/rewards are fixture declarations, not experimental measurements.
Private Python attributes are not an isolation or authorization boundary.
"""
from dataclasses import dataclass
import hashlib
import math

from .catalogue import (CATALOGUE_DIGEST,ContractError,canonical,catalogue,
                        parse_proposal,plan_bound,positive_int)


@dataclass(frozen=True)
class FixtureCost:
    steps: int
    imagined_states: int
    cpu_units: int

    def __post_init__(self):
        if any(type(v) is not int or not 0<=v<=10**12 for v in (self.steps,self.imagined_states,self.cpu_units)):
            raise ContractError('invalid_fixture_cost')

    def payload(self):return dict(steps=self.steps,imagined_states=self.imagined_states,cpu_units=self.cpu_units)

    def plus(self,other):
        if type(other) is not FixtureCost:raise ContractError('invalid_fixture_cost')
        return FixtureCost(self.steps+other.steps,self.imagined_states+other.imagined_states,self.cpu_units+other.cpu_units)

    def fits(self,cap):return all(self.payload()[k]<=cap.payload()[k] for k in self.payload())


@dataclass(frozen=True)
class PublicFixtureContext:
    n_actions: int
    obs_dim: int
    episode_steps: int
    imagined_cap: int

    def __post_init__(self):
        positive_int(self.n_actions,16);positive_int(self.obs_dim,4096)
        positive_int(self.episode_steps,200);positive_int(self.imagined_cap,1536)

    def payload(self):
        return dict(n_actions=self.n_actions,obs_dim=self.obs_dim,
                    episode_steps=self.episode_steps,imagined_cap=self.imagined_cap)


@dataclass(frozen=True)
class TrainingFixture:
    variant_id: str
    score: float | None
    failed: bool
    cpu_units: int
    purpose: str='training'

    def __post_init__(self):
        if self.purpose!='training' or type(self.failed) is not bool:raise ContractError('training_only')
        positive_int(self.cpu_units)
        if type(self.variant_id) is not str or self.variant_id not in {v.fingerprint for v in catalogue()}:
            raise ContractError('unknown_variant')
        if self.failed:
            if self.score is not None:raise ContractError('failed_fixture_has_score')
        elif type(self.score) not in (int,float) or not 0<=self.score<=1 or not math.isfinite(self.score):
            raise ContractError('invalid_fixture_score')


class FixtureTable:
    def __init__(self,context,rows):
        if type(context) is not PublicFixtureContext:raise ContractError('invalid_context')
        rows=tuple(rows)
        if any(type(r) is not TrainingFixture for r in rows):raise ContractError('training_fixture_required')
        ids=[r.variant_id for r in rows]
        if len(ids)!=len(set(ids)) or set(ids)!={v.fingerprint for v in catalogue()}:
            raise ContractError('incomplete_fixture_catalogue')
        for v in catalogue():plan_bound(v,context.n_actions,context.imagined_cap)
        self._context=context;self._rows={r.variant_id:r for r in rows};self._seen=set()

    @property
    def context(self):return self._context

    @property
    def fixture_materializations(self):return len(self._seen)

    def _read(self,variant):
        self._seen.add(variant.fingerprint)
        return self._rows[variant.fingerprint]

    def _peek_cost(self,variant):
        row=self._rows[variant.fingerprint]
        bound=plan_bound(variant,self._context.n_actions,self._context.imagined_cap)
        return FixtureCost(self._context.episode_steps,self._context.episode_steps*bound.imagined_per_decision,row.cpu_units)


@dataclass(frozen=True)
class Event:
    sequence: int
    kind: str
    payload_json: str
    previous: str
    fingerprint: str


class Journal:
    def __init__(self):self._events=()

    def append(self,kind,payload):
        sequence=len(self._events);previous=self._events[-1].fingerprint if sequence else '0'*64
        raw=canonical(dict(mode='synthetic_fixture',sequence=sequence,kind=kind,payload=payload,previous=previous))
        event=Event(sequence,kind,canonical(payload),previous,hashlib.sha256(raw.encode()).hexdigest())
        self._events+= (event,)
        return event

    def snapshot(self):return self._events


def verify_journal(events,expected_head=None,expected_count=None):
    """Check a chain; external head/count anchors are needed to detect truncation.

    This does not authenticate an audit authority or prove cost measurements.
    """
    import json
    expected=Journal()
    for event in events:
        if type(event) is not Event:raise ContractError('invalid_event')
        if type(event.sequence) is not int or type(event.kind) is not str:
            raise ContractError('invalid_event')
        try:again=expected.append(event.kind,json.loads(event.payload_json))
        except (ValueError,TypeError) as exc:raise ContractError('invalid_event') from exc
        if again!=event:raise ContractError('journal_tampered')
    rebuilt=expected.snapshot()
    head=rebuilt[-1].fingerprint if rebuilt else '0'*64
    if expected_head is not None and (type(expected_head) is not str or head!=expected_head):
        raise ContractError('journal_head_mismatch')
    if expected_count is not None and (type(expected_count) is not int or len(rebuilt)!=expected_count):
        raise ContractError('journal_count_mismatch')
    return True


@dataclass(frozen=True)
class TrainingReceipt:
    variant_id: str
    score: float | None
    failed: bool
    charged: FixtureCost
    cumulative: FixtureCost
    event_id: str

    def wire(self):
        return canonical(dict(mode='synthetic_fixture',catalogue=CATALOGUE_DIGEST,
            variant_id=self.variant_id,score=self.score,failed=self.failed,
            charged=self.charged.payload(),cumulative=self.cumulative.payload(),event_id=self.event_id))


class FixtureBroker:
    """No environment/evaluator callback, file path, hidden split or run API."""
    def __init__(self,table,cap,max_attempts=32):
        if type(table) is not FixtureTable or type(cap) is not FixtureCost:raise ContractError('invalid_fixture_broker')
        positive_int(max_attempts,64)
        self._table,self._cap,self._max_attempts=table,cap,max_attempts
        self._charged=FixtureCost(0,0,0);self._attempts=0;self._seen=set();self._journal=Journal()

    def public_context(self):return canonical(dict(mode='synthetic_fixture',catalogue=CATALOGUE_DIGEST,**self._table.context.payload()))

    @property
    def charged(self):return self._charged

    def journal(self):return self._journal.snapshot()

    def submit(self,wire):
        if self._attempts>=self._max_attempts:raise ContractError('attempt_limit')
        self._attempts+=1
        try:
            variant=parse_proposal(wire)
            if variant.fingerprint in self._seen:raise ContractError('duplicate_proposal')
            cost=self._table._peek_cost(variant)
            total=self._charged.plus(cost)
            if not total.fits(self._cap):raise ContractError('fixture_budget_exhausted')
        except ContractError:
            self._journal.append('rejected',dict(attempt=self._attempts))
            raise
        # Reserve before exposing feedback; cache hits still consume full cost.
        self._charged=total;self._seen.add(variant.fingerprint)
        self._journal.append('reserved',dict(variant_id=variant.fingerprint,cost=cost.payload(),total=total.payload()))
        try:row=self._table._read(variant)
        except Exception:
            # Reservation survives an internal fixture fault. No refund or retry.
            self._journal.append('internal_failure',dict(variant_id=variant.fingerprint))
            raise ContractError('fixture_materialization_failed') from None
        event=self._journal.append('settled',dict(variant_id=variant.fingerprint,score=row.score,failed=row.failed))
        return TrainingReceipt(variant.fingerprint,row.score,row.failed,cost,total,event.fingerprint)
