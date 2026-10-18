"""Feedback-driven toy prototype, not a scientific controller or secure sandbox."""
from dataclasses import asdict, dataclass
import math
import random

from .catalogue import ContractError, Generator, Rule, canonical, catalogue, digest
from .fixtures import (FixtureBroker, FixtureCost, FixtureTable, Journal,
                       PublicFixtureContext, TrainingFixture, TrainingReceipt, verify_journal)
from .promotion import FixtureAuditor, FixturePromotionHarness, FixtureSnapshot
from .resources import Clock, Limits, Operation, ReservationLedger, Work


VARIANTS = catalogue()
BY_ID = {v.fingerprint: v for v in VARIANTS}
ANCHORS = (VARIANTS[2], VARIANTS[8])  # flat/ successor IID H16
CONTEXT = PublicFixtureContext(3, 3, 1, 1536)
TEST_KEY = b'evolution1-synthetic-auditor-only'


def _hash(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ContractError('invalid_feedback_reference')


def _score(value):
    if type(value) not in (int,float) or not 0 <= value <= 1 or not math.isfinite(value):
        raise ContractError('invalid_feedback_score')


@dataclass(frozen=True)
class TrainingFeedback:
    variant_id: str
    score: float | None
    failed: bool
    event_id: str

    def __post_init__(self):
        if type(self.variant_id) is not str or self.variant_id not in BY_ID or type(self.failed) is not bool:
            raise ContractError('invalid_training_feedback')
        _hash(self.event_id)
        if self.failed:
            if self.score is not None: raise ContractError('failed_feedback_has_score')
        else: _score(self.score)


def permitted_feedback(receipt):
    if type(receipt) is not TrainingReceipt:
        raise ContractError('training_receipt_required')
    return TrainingFeedback(receipt.variant_id,receipt.score,receipt.failed,receipt.event_id)


def features(variant, context):
    if type(context) is not PublicFixtureContext:
        raise ContractError('public_training_context_required')
    s = float(variant.rule is Rule.SUCCESSOR)
    h = variant.horizon / 16.0
    return (1.0,s,float(variant.generator is Generator.BALANCED),h,
            s*context.obs_dim/16.0,h*context.n_actions/16.0)


class FixedProposer:
    name = 'fixed'

    def __init__(self, seed=7):
        if type(seed) is not int or not 0 <= seed <= 10**9:
            raise ContractError('invalid_toy_seed')
        self._rng = random.Random(seed)
        self._feedback_seen = set()

    def learned_state(self): return {'weights': (), 'updates': 0}

    def rng_state(self): return self._rng.getstate()

    def memory_state(self):
        return {'learned':self.learned_state(),'feedback_seen':tuple(sorted(self._feedback_seen))}

    def choose(self, available, context):
        return max(available,key=lambda v:(v.horizon,v.rule is Rule.FLAT,v.generator is Generator.IID))

    def update(self, feedback, context):
        if type(feedback) is not TrainingFeedback or type(context) is not PublicFixtureContext:
            raise ContractError('permitted_training_feedback_only')
        if feedback.event_id in self._feedback_seen:
            raise ContractError('replayed_training_feedback')
        self._learn(feedback,context)
        self._feedback_seen.add(feedback.event_id)

    def _learn(self, feedback, context): pass


class RandomProposer(FixedProposer):
    name = 'random'

    def choose(self, available, context): return self._rng.choice(available)


class AdaptiveProposer(FixedProposer):
    """Fixed normalized linear SGD rule sharing features across catalogue arms."""
    name = 'adaptive'

    def __init__(self, seed=7):
        super().__init__(seed)
        self._weights = (0.0,)*6
        self._updates = 0
        order = list(VARIANTS); self._rng.shuffle(order)
        self._tie_rank = {v.fingerprint:i for i,v in enumerate(order)}

    def learned_state(self): return {'weights':self._weights,'updates':self._updates}

    def memory_state(self):
        return {**super().memory_state(),
                'tie_order':tuple(sorted(self._tie_rank,key=self._tie_rank.get))}

    def choose(self, available, context):
        return max(available,key=lambda v:(sum(w*x for w,x in zip(self._weights,features(v,context))),
                                          -self._tie_rank[v.fingerprint]))

    def _learn(self, feedback, context):
        x = features(BY_ID[feedback.variant_id],context)
        y = 0.0 if feedback.failed else float(feedback.score)
        error = y-sum(w*f for w,f in zip(self._weights,x))
        scale = 0.5*error/sum(f*f for f in x)
        self._weights = tuple(w+scale*f for w,f in zip(self._weights,x))
        self._updates += 1


@dataclass(frozen=True)
class Attempt:
    variant_id: str
    score: float | None
    failed: bool
    policy_before: str
    policy_after: str
    receipt: TrainingReceipt


@dataclass(frozen=True)
class TrainingRun:
    policy: str
    planned_proposals: int
    status: str
    policy_before: str
    policy_after: str
    initial: FixtureSnapshot
    candidate: FixtureSnapshot | None
    attempts: tuple
    history: tuple
    broker_events: tuple
    broker_charged: FixtureCost
    resources: object


def _snapshot(variant_id, policy, context):
    return FixtureSnapshot(variant_id,digest(policy.rng_state()),digest(context.payload()),
                           digest(policy.memory_state()))


def run_training(policy, rows, *, proposals=4, withhold_feedback=False, work_cap=None):
    """No development gate, development scores or hidden task object is accepted."""
    if type(policy) not in (FixedProposer,RandomProposer,AdaptiveProposer):
        raise ContractError('unreviewed_proposer')
    if type(proposals) is not int or not 2 <= proposals <= 6 or type(withhold_feedback) is not bool:
        raise ContractError('bounded_nonexhaustive_proposal_count_required')
    rows = tuple(rows)
    table = FixtureTable(CONTEXT,rows)
    if any(row.cpu_units != 1 for row in rows):
        raise ContractError('toy_requires_uniform_declared_feedback_cost')
    broker = FixtureBroker(table,FixtureCost(proposals,1536*proposals,proposals))
    # Conservative equal logical credits, not measured or executed transitions.
    unit = Work(real_steps=1,imagined_transitions=1536)
    cap = Work(real_steps=proposals,imagined_transitions=1536*proposals) if work_cap is None else work_cap
    fixture_hash = digest([asdict(r) for r in rows])
    ledger = ReservationLedger(tuple(Operation(f'attempt_{i}','cached',unit,fixture_hash)
                                    for i in range(proposals)),
                               Limits(Work(),cap,4*proposals+4,4*proposals+4))
    initial_state = canonical(policy.learned_state())
    initial = _snapshot(ANCHORS[0].fingerprint,policy,CONTEXT)
    history = Journal(); attempts = []; available = list(VARIANTS)
    for i in range(proposals):
        variant = ANCHORS[i] if i < 2 else policy.choose(tuple(available),CONTEXT)
        if variant not in available:
            history.append('rejected_duplicate_or_invalid',{'slot':i})
            break
        try: ticket = ledger.reserve(f'attempt_{i}',Clock(2*i,2*i))
        except ContractError:
            history.append('resource_stop',{'slot':i})
            break
        before = canonical(policy.learned_state())
        try: receipt = broker.submit(variant.wire())
        except ContractError:
            ledger.settle(ticket,'failed',Clock(2*i+1,2*i+1))
            history.append('broker_failure',{'slot':i})
            break
        # A failed candidate is valid evaluated feedback, not a broken lookup.
        ledger.settle(ticket,'success',Clock(2*i+1,2*i+1))
        if not withhold_feedback: policy.update(permitted_feedback(receipt),CONTEXT)
        attempt = Attempt(variant.fingerprint,receipt.score,receipt.failed,before,
                          canonical(policy.learned_state()),receipt)
        attempts.append(attempt); available.remove(variant)
        history.append('training_attempt',asdict(attempt))
    report = ledger.close(Clock(2*len(attempts)+1,2*len(attempts)+1))
    verify_journal(broker.journal())
    status = report.status
    successful = [a for a in attempts if not a.failed]
    winner = max(successful,key=lambda a:a.score).variant_id if successful else initial.variant_id
    candidate = _snapshot(winner,policy,CONTEXT) if status == 'complete_execution' else None
    return TrainingRun(policy.name,proposals,status,initial_state,canonical(policy.learned_state()),initial,candidate,
                       tuple(attempts),history.snapshot(),broker.journal(),broker.charged,report)


@dataclass(frozen=True)
class DevelopmentScore:
    variant_id: str
    score: float

    def __post_init__(self):
        if type(self.variant_id) is not str or self.variant_id not in BY_ID:
            raise ContractError('invalid_development_variant')
        _score(self.score)


@dataclass(frozen=True)
class GateResult:
    gain: float
    passed: bool
    query_count: int
    audit: object


class DevelopmentGate:
    """One candidate-vs-incumbent comparison; never calls a proposal policy."""
    def __init__(self, rows, key=TEST_KEY):
        rows = tuple(rows)
        if any(type(r) is not DevelopmentScore for r in rows):
            raise ContractError('development_rows_required')
        if len(rows) != 12 or {r.variant_id for r in rows} != set(BY_ID):
            raise ContractError('incomplete_development_grid')
        self._rows = {r.variant_id:r.score for r in rows}
        self._auditor = FixtureAuditor(key)
        self._used = False

    def assess(self, training):
        if type(training) is not TrainingRun or training.status != 'complete_execution' or training.candidate is None:
            raise ContractError('complete_frozen_training_required')
        if self._used: raise ContractError('development_gate_consumed')
        if (training.resources.status != 'complete_execution'
                or type(training.planned_proposals) is not int or not 2 <= training.planned_proposals <= 6
                or len(training.attempts) != training.planned_proposals
                or training.resources.completed_keys != tuple(f'attempt_{i}' for i in range(training.planned_proposals))
                or training.resources.unresolved_keys or training.resources.pending_key is not None):
            raise ContractError('incomplete_training_grid')
        if len({a.variant_id for a in training.attempts}) != len(training.attempts):
            raise ContractError('duplicate_training_variant')
        verify_journal(training.history)
        verify_journal(training.broker_events)
        settled = [e for e in training.broker_events if e.kind == 'settled']
        if len(training.broker_events) != 2*training.planned_proposals or len(settled) != training.planned_proposals:
            raise ContractError('incomplete_broker_history')
        if len(training.history) != len(training.attempts):
            raise ContractError('incomplete_training_history')
        for event,attempt,settlement in zip(training.history,training.attempts,settled):
            if event.kind != 'training_attempt' or event.payload_json != canonical(asdict(attempt)):
                raise ContractError('training_history_mismatch')
            if settlement.fingerprint != attempt.receipt.event_id:
                raise ContractError('unbound_training_receipt')
        eligible = [a for a in training.attempts if not a.failed]
        winner = max(eligible,key=lambda a:a.score).variant_id if eligible else training.initial.variant_id
        if training.candidate.variant_id != winner:
            raise ContractError('candidate_not_frozen_training_winner')
        self._used = True
        gain = self._rows[training.candidate.variant_id]-self._rows[training.initial.variant_id]
        passed = gain >= 0.05
        head = training.history[-1].fingerprint
        audit = self._auditor.attest(training.candidate,head,'pass' if passed else 'reject')
        return GateResult(gain,passed,2,audit)


def retain_or_rollback(harness, observed_snapshot):
    """Toy state-reference verification only, not a real checkpoint audit."""
    if type(observed_snapshot) is not FixtureSnapshot:
        raise ContractError('verified_fixture_snapshot_required')
    if observed_snapshot.fingerprint != harness.incumbent.fingerprint:
        return harness.rollback_for_test(),True
    return harness.incumbent,False


def run_cycle(policy, training_rows, development_rows, *, observed_snapshot=None, **training_options):
    training = run_training(policy,training_rows,**training_options)
    if training.status != 'complete_execution':
        return {'mode':'synthetic_only','training':asdict(training),'gate':None,
                'decision':'incomplete_no_promotion','incumbent':asdict(training.initial)}
    gate = DevelopmentGate(development_rows).assess(training)
    harness = FixturePromotionHarness(training.initial,TEST_KEY)
    decision = 'development_rejected_preserved'
    if gate.passed:
        harness.promote_for_test(training.candidate,training.history[-1].fingerprint,gate.audit)
        observed = (FixtureSnapshot(**asdict(training.candidate)) if observed_snapshot is None
                    else observed_snapshot)
        _,rolled_back = retain_or_rollback(harness,observed)
        decision = 'integrity_mismatch_rolled_back' if rolled_back else 'fixture_promoted'
    return {'mode':'synthetic_only','training':asdict(training),'gate':asdict(gate),
            'decision':decision,'incumbent':asdict(harness.incumbent),
            'promotion_events':harness.events,'archive':[asdict(s) for s in harness.archived_snapshots]}


def synthetic_case(name):
    """Crafted examples, not sampled physics or independent scientific tasks."""
    if name not in ('aligned_signal','heuristic_counterexample','development_reversal'):
        raise ContractError('unknown_toy_case')
    train = []; dev = []
    for i,v in enumerate(VARIANTS):
        successor = v.rule is Rule.SUCCESSOR
        balanced = v.generator is Generator.BALANCED
        score = (0.65 if successor else 0.15)+0.04*(v.horizon/16)+0.15*balanced
        dscore = (0.70 if successor else 0.20)+0.03*(v.horizon/16)+0.10*balanced
        if name == 'heuristic_counterexample':
            score = 0.99 if i == 5 else (0.6 if successor else 0.1)
            dscore = 0.95 if i == 5 else (0.4 if successor else 0.1)
        if name == 'development_reversal': dscore = 0.05 if successor else 0.4
        train.append(TrainingFixture(v.fingerprint,score,False,1))
        dev.append(DevelopmentScore(v.fingerprint,dscore))
    return tuple(train),tuple(dev)
