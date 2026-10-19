"""Bounded compositions of existing planner operators, not source evolution.

Reuses the E1 proposer/journal and E2 adapter. No generated Python, environment
factory, additional memory framework, or scientific dispatcher exists here.
"""
from dataclasses import dataclass
import math
import random

import numpy as np

from nexus.evolution1.catalogue import Variant, digest, plan_bound
from nexus.evolution1.fixtures import Journal
from nexus.evolution1.toy_loop import AdaptiveProposer, TrainingFeedback, VARIANTS, features
from nexus.evolution2.planner_adapter import decide
from nexus.evolution2.planner_quality_diagnostic import fit_ridge, predict_ridge
from nexus.core.strategy_memory import describe_support


@dataclass(frozen=True)
class Strategy:
    kind: str
    left: Variant
    right: Variant | None = None
    threshold: float = 0.

    def __post_init__(self):
        if self.kind not in ("leaf", "switch", "rank_blend") or type(self.left) is not Variant:
            raise ValueError("invalid_strategy")
        if self.kind == "leaf":
            if self.right is not None or self.threshold != 0.: raise ValueError("noncanonical_leaf")
        elif type(self.right) is not Variant or self.left == self.right:
            raise ValueError("distinct_vetted_children_required")
        if self.kind == "switch" and (type(self.threshold) is not float or self.threshold not in (.25, 1.)):
            raise ValueError("unvetted_gate")
        if self.kind == "rank_blend":
            if self.threshold != 0. or self.left.fingerprint > self.right.fingerprint:
                raise ValueError("noncanonical_commutative_composition")

    def payload(self):
        return {"version": "bounded_strategy_v1", "kind": self.kind, "left": self.left.payload(),
                "right": None if self.right is None else self.right.payload(), "threshold": self.threshold}

    @property
    def fingerprint(self): return digest(self.payload())

    def active(self, obs):
        x = np.asarray(obs, float)
        if x.ndim != 1 or not len(x) or not np.isfinite(x).all(): raise ValueError("finite_observation_required")
        return self.right if self.kind == "switch" and abs(x[0]) > self.threshold else self.left

    def components(self, obs, cap=1536):
        if type(cap) is not int or not 48 <= cap <= 1536: raise ValueError("invalid_strategy_cap")
        return ((self.left, cap // 2), (self.right, cap // 2)) if self.kind == "rank_blend" else ((self.active(obs), cap),)

    def bound(self, obs, n_actions, cap=1536):
        return sum(plan_bound(v, n_actions, c).imagined_per_decision for v, c in self.components(obs, cap))


def leaf(v): return Strategy("leaf", v)


def compose(kind, a, b, threshold=.25):
    if a == b: return leaf(a)
    if kind == "rank_blend":
        a, b = sorted((a, b), key=lambda v: v.fingerprint)
        return Strategy(kind, a, b)
    if kind != "switch": raise ValueError("unknown_composition")
    return Strategy(kind, a, b, threshold)


def universe():
    out = [leaf(v) for v in VARIANTS]
    for a in VARIANTS:
        for b in VARIANTS:
            if a == b: continue
            out.extend(compose("switch", a, b, t) for t in (.25, 1.))
            if a.fingerprint < b.fingerprint: out.append(compose("rank_blend", a, b))
    return tuple(out)


def action_scores(decision, variant, n_actions):
    if variant.rule.value == "successor": return np.asarray(decision.scores)
    return np.asarray([max((s for s, seq in zip(decision.scores, decision.sequences) if seq[0] == a), default=-math.inf)
                       for a in range(n_actions)])


def execute(strategy, family, obs, model, *, seed, n_actions=3, cap=1536, resolve=None):
    if type(strategy) is not Strategy: raise TypeError("typed_strategy_required")
    resolve = resolve or (lambda v, c: decide(family, v, obs, model, seed=seed, imagined_cap=c))
    parts = strategy.components(obs, cap)
    decisions = [resolve(v, c) for v, c in parts]
    if strategy.kind != "rank_blend": return decisions[0].action
    ranks = []
    for (v, _), d in zip(parts, decisions):
        q = action_scores(d, v, n_actions)
        # Midranks preserve equal-score ties and do not mix unlike score scales.
        ranks.append(np.asarray([sum(x > y for y in q) + .5 * sum(x == y for y in q) for x in q]))
    return int(np.argmax(sum(ranks)))


def descriptor(strategy, obs, context):
    active = strategy.active(obs)
    return np.r_[features(active, context), np.zeros(6) if strategy.right is None else features(strategy.right, context),
                 float(strategy.kind == "switch"), float(strategy.kind == "rank_blend"), strategy.threshold,
                 strategy.bound(obs, context.n_actions) / 1536.]


def advantage_features(strategy, obs, support, context, normalizer, anchors):
    """Only public observations, transitions, descriptors and revealed anchors."""
    z = normalizer.embed(obs)
    support_stats = describe_support(support, context)
    task = np.r_[1., np.pad(np.tanh(z), (0, 6-len(z))), support_stats[:3], anchors]
    arm = descriptor(strategy, obs, context)
    return np.outer(task, arm).ravel()


class AdvantagePredictor:
    """Optional ranker reusing E2.25's fixed ridge=1 and train-only RMS fit."""
    def __init__(self):
        self.x, self.y, self.model, self.events = [], [], None, set()
        self.fit_calls = 0

    @property
    def parameter_count(self):
        return 0 if not self.x else len(self.x[0])

    def observe(self, x, advantage, *, event, provenance, baseline=0.):
        if provenance != "revealed_source" or event in self.events:
            raise ValueError("unique_revealed_source_receipt_required")
        x = np.asarray(x, float)
        if (x.ndim != 1 or not np.isfinite(x).all() or type(advantage) not in (int, float) or not math.isfinite(advantage)
            or type(baseline) not in (int,float) or not math.isfinite(baseline)):
            raise ValueError("finite_observation_required")
        if self.x and x.shape != self.x[0].shape: raise ValueError("feature_schema_mismatch")
        target=advantage-baseline
        if not math.isfinite(target):raise ValueError('finite_residual_target_required')
        self.x.append(x.copy()); self.y.append(target); self.events.add(event)
        self.model = None

    def predict(self, x, *, baseline=0.):
        """A permitted training-only mean can anchor the learned correction.

        Zero baseline preserves the original direct predictor. The caller owns
        provenance and must not supply query-conditioned or predicted rewards.
        """
        if type(baseline) not in (int,float) or not math.isfinite(baseline):raise ValueError('finite_baseline_required')
        if not self.x: return baseline
        if self.model is None:
            self.model = fit_ridge(self.x, self.y)
            self.fit_calls += 1
        prediction=baseline+predict_ridge(self.model, x)
        if not math.isfinite(prediction):raise ValueError('finite_prediction_required')
        return prediction


class StrategyGenerator:
    """Mutation preferences are existing AdaptiveProposer's six SGD weights.

    Credit is assigned to the active leaf of a switch, and equally to both
    leaves for a rank composition. This is a deliberately coarse credit rule.
    """
    def __init__(self, seed, adaptive=True, *, mutation_credit=False):
        self.inner = AdaptiveProposer(seed)
        self.rng = random.Random(seed)
        self.adaptive = adaptive
        self.journal = Journal()
        self.parent = None
        self.parent_strategy = None
        self.best = -1.
        self.seen = set()
        self.proposal_attempts = self.duplicate_rejections = self.fallbacks = 0
        self.mutation_credit=mutation_credit
        self.mutation_stats={k:[0.,0] for k in ('switch','rank_blend')}
        self.mutation_events=set()

    def mutation_probabilities(self):
        keys=tuple(self.mutation_stats)
        values=np.array([self.mutation_stats[k][0]/max(1,self.mutation_stats[k][1]) for k in keys])
        weights=np.exp(values-values.max());return dict(zip(keys,(weights/weights.sum()).tolist()))

    def observe_mutation(self,parent,child,parent_result,child_result,*,return_scale=100.):
        """Trusted host records matched full-policy outcomes, never forecasts.

        Does not credit child leaves. Existing coarse update remains unchanged
        for historical callers; callers choose exactly one credit path.
        """
        if not self.mutation_credit or type(parent) is not Strategy or type(child) is not Strategy or child.kind not in self.mutation_stats:
            raise ValueError('mutation_credit_contract')
        if parent.kind!='leaf' or parent.left not in (child.left,child.right):raise ValueError('single_structural_mutation_required')
        required={'kind','phase','strategy','pair_id','context_hash','reset_seed','planner_seed','horizon','planning_cap','return','cpu_s','event'}
        for strategy,row in ((parent,parent_result),(child,child_result)):
            if set(row)!=required or row['kind']!='observed_full_policy_return' or row['phase']!='training' or row['strategy']!=strategy.fingerprint:
                raise ValueError('observed_training_return_required')
            if type(row['return']) not in (int,float) or not math.isfinite(row['return']) or type(row['cpu_s']) not in (int,float) or not math.isfinite(row['cpu_s']) or row['cpu_s']<=0:raise ValueError('finite_measured_cost_and_return')
            for key in ('reset_seed','planner_seed','horizon','planning_cap'):
                if type(row[key]) is not int or row[key]<0:raise ValueError('matched_integer_protocol')
        if any(parent_result[k]!=child_result[k] for k in ('pair_id','context_hash','reset_seed','planner_seed','horizon','planning_cap')):raise ValueError('unmatched_parent_child')
        event=digest([parent_result,child_result])
        if event in self.mutation_events or parent_result['event'] in self.mutation_events or child_result['event'] in self.mutation_events:raise ValueError('duplicate_mutation_feedback')
        if type(return_scale) not in (int,float) or not math.isfinite(return_scale) or return_scale<=0:raise ValueError('registered_return_scale')
        gain=child_result['return']-parent_result['return'];cost=parent_result['cpu_s']+child_result['cpu_s']
        if not math.isfinite(gain) or not math.isfinite(cost):raise ValueError('finite_paired_difference')
        credit=float(np.tanh(gain/return_scale)/(1.+cost))
        if self.adaptive:
            self.mutation_stats[child.kind][0]+=credit;self.mutation_stats[child.kind][1]+=1
        self.mutation_events.update((event,parent_result['event'],child_result['event']))
        self.journal.append('paired_mutation_feedback',dict(event=event,parent=parent.payload(),child=child.payload(),
            mutation=child.kind,context_hash=parent_result['context_hash'],observed_gain=gain,cpu_s=cost,
            parent_result=parent_result,child_result=child_result,credit=credit,probabilities=self.mutation_probabilities()))
        return credit

    def propose(self, context, excluded=()):
        for _ in range(32):
            self.proposal_attempts += 1
            a = self.inner.choose(VARIANTS, context) if self.adaptive else self.rng.choice(VARIANTS)
            inherited = () if self.parent_strategy is None else tuple(v for v in (self.parent_strategy.left, self.parent_strategy.right) if v is not None and v != a)
            b = self.rng.choice(inherited if inherited and self.rng.random() < .5
                                else tuple(v for v in VARIANTS if v != a))
            kind = (self.rng.choices(tuple(self.mutation_stats),weights=tuple(self.mutation_probabilities().values()))[0]
                    if self.mutation_credit and self.adaptive else self.rng.choice(("switch", "rank_blend")))
            child = compose(kind, a, b, self.rng.choice((.25, 1.)))
            if child.fingerprint in excluded:
                self.duplicate_rejections += 1
                continue
            self.journal.append("generated", {"child": child.fingerprint, "parent": self.parent,
                "strategy": child.payload(), "policy": self.inner.learned_state()})
            return child
        self.fallbacks += 1
        remaining = [s for s in universe() if s.kind != "leaf" and s.fingerprint not in excluded]
        if not remaining: raise ValueError("generation_budget_exhausted")
        child = self.rng.choice(remaining)
        self.journal.append("generated", {"child": child.fingerprint, "parent": None,
            "strategy": child.payload(), "fallback": True, "policy": self.inner.learned_state()})
        return child

    def update(self, strategy, score, obs, context, *, event, withheld=False, provenance="revealed_source"):
        if provenance != "revealed_source": raise ValueError("permitted_feedback_only")
        if event in self.seen: raise ValueError("duplicate_strategy_feedback")
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("observed_unit_feedback_required")
        before = self.inner.learned_state()
        if not withheld and self.adaptive:
            credited = (strategy.left, strategy.right) if strategy.kind == "rank_blend" else (strategy.active(obs),)
            for v in credited:
                self.inner.update(TrainingFeedback(v.fingerprint, score, False, digest([event, v.fingerprint])), context)
        if not withheld and self.adaptive and score > self.best:
            self.best, self.parent, self.parent_strategy = score, strategy.fingerprint, strategy
        self.seen.add(event)
        self.journal.append("feedback", {"strategy": strategy.fingerprint, "event": event,
            "withheld": withheld, "before": before, "after": self.inner.learned_state()})
