"""Phase 13 trainable task-conditioned Delta-State selector and counterfactual regret auditing (NOT LOCKED; engineering machinery).

WHAT IS MACHINERY AND WHAT IS LEARNED
  The code below (scoring rule, update rules, clipping, cost mapping) is general machinery written by the engineering team. What
  NEXUS learns autonomously is only the STATE it produces during source training: Selector.weights, Selector.tag_prior,
  DeltaStateGuide counts and the update ledger. The runner records that state (and its fingerprint) separately from the code.

  1  SELECTOR            linear score w . features over proposals13.FEATURE_NAMES (proposal kind, Delta-State deltas, partition
                         statistics, task flags read from the live candidates' ASTs and kind x task crosses). Uniform weights =
                         the Untrained control; the Trained arm starts from the same uniform weights and is updated only from
                         source-training experience.
  2  TRAINING            listwise softmax policy gradient toward COUNTERFACTUAL utilities: during source training every scored
                         proposal's reference answer is known (budgeted reference oracle), so the utility of every alternative
                         query - not only the one taken - is computed from the members' already-executed outputs.
  3  REGRET AUDIT        regret = max utility - utility of the chosen proposal. With regret > 0 every weight moves by
                         regret_lr * regret * (f_best - f_chosen): the features that steered the choice to the worse query are
                         demoted, the ones of the counterfactual best are promoted. Logged per update.
  4  SHORTCUT DEMOTION   accepted leaders whose acceptance is later falsified demote their shortcut tags (passthrough, count_star,
                         join kinds, comparison strictness; proposals13.shortcut_tags); surviving alternatives' tags are promoted;
                         confirmed leaders get a small promotion. The prior is bounded and only ORDERS the VersionSpace leader
                         (leader_prior). It never removes, skips or locks a member: no permanent passthrough / COUNT(*) lock.
  5  DELTA-STATE GUIDE   production-cost table for synth12.Costs learned from productions of verified programs (and penalised by
                         productions of accepted-then-falsified ones). rel / col / const stay at cost 1 (band structure).
  6  ISOLATION           freeze() makes every learning entry point raise FrozenSelectorError; fingerprint() is a sha256 of the
                         learned state, so evaluation can prove that nothing changed while evaluating."""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter

from nexus.de_phase12 import synth12 as S
from nexus.de_phase13 import proposals13 as P

W_CLIP, PRIOR_CLIP, LEADER_BONUS, CONFIRM_SCALE = 8.0, 3.0, 0.5, 0.25
ARMS = ("fixed", "random", "untrained", "trained")
PINNED = ("rel", "col", "const")


class FrozenSelectorError(RuntimeError):
    """A learning update was attempted on a frozen (evaluation) selector or guide."""


def _softmax(xs, temperature=1.0):
    if not xs:
        return []
    t = max(1e-6, float(temperature))
    m = max(xs)
    e = [math.exp((x - m) / t) for x in xs]
    z = sum(e)
    return [v / z for v in e]


def _clip(v, lim):
    return max(-lim, min(lim, v))


def _index_of(scored, chosen):
    if chosen is None:
        return None
    if isinstance(chosen, int):
        return chosen if 0 <= chosen < len(scored) else None
    for i, s in enumerate(scored):
        if s is chosen:
            return i
    cid = chosen.get("id") if isinstance(chosen, dict) else None
    for i, s in enumerate(scored):
        if cid is not None and s.get("id") == cid and s.get("kind") == chosen.get("kind") and s.get("base") == chosen.get("base"):
            return i
    return None


# ------------------------------------------------------------------ counterfactual utilities
def counterfactual_utilities(scored, ref_fps, leader_id=None, leader_bonus=LEADER_BONUS):
    """Utility of every scored proposal given the reference answer fingerprint on its input (aligned list, or dict keyed by list
    index). Utility = fraction of evaluated members whose output differs from the reference (they would be falsified) + leader_bonus
    if the leader would be falsified. A proposal without a reference answer gets utility 0. Used ONLY in source training."""
    out = []
    for i, s in enumerate(scored):
        ref = ref_fps.get(i) if isinstance(ref_fps, dict) else (ref_fps[i] if i < len(ref_fps) else None)
        outs = s.get("outputs") or {}
        if ref is None or not outs:
            out.append(0.0)
            continue
        bad = [mid for mid, fp in outs.items() if fp != ref]
        u = len(bad) / len(outs)
        if leader_id is not None and leader_id in outs and outs[leader_id] != ref:
            u += leader_bonus
        out.append(u)
    return out


# ------------------------------------------------------------------ selector
class Selector:
    """Task-conditioned Delta-State proposal selector with counterfactual regret demotion and a soft shortcut-tag prior."""

    def __init__(self, weights=None, tag_prior=None, lr=0.25, regret_lr=0.5, prior_lr=0.5, l2=1e-3, temperature=1.0, name="trained"):
        self.weights = dict(P.uniform_weights())
        self.weights.update({k: float(v) for k, v in (weights or {}).items() if k in self.weights})
        self.tag_prior = {k: float(v) for k, v in (tag_prior or {}).items()}
        self.lr, self.regret_lr, self.prior_lr, self.l2, self.temperature = lr, regret_lr, prior_lr, l2, temperature
        self.name, self.frozen = name, False
        self.stats = Counter()
        self.ledger = []

    # ---- isolation
    def freeze(self):
        self.frozen = True
        return self

    def _guard(self, what):
        if self.frozen:
            self.stats["frozen_update_refused"] += 1
            raise FrozenSelectorError(f"{self.name}: {what} attempted on a frozen selector (evaluation isolation)")

    def copy(self, name=None, frozen=None):
        new = Selector.from_dict(self.to_dict())
        new.name = name or self.name
        new.frozen = self.frozen if frozen is None else frozen
        return new

    # ---- scoring
    def score(self, features):
        return sum(self.weights.get(k, 0.0) * float(v) for k, v in features.items())

    def probs(self, scored):
        return _softmax([self.score(s["features"]) for s in scored], self.temperature)

    def choose(self, scored):
        """argmax w . features (ties by menu order) - identical rule to proposals13.choose('weighted')."""
        return P.choose(scored, "weighted", self.weights)

    def leader_prior(self, member):
        """Soft prior used ONLY to order VersionSpace.leader; bounded, never excludes a member."""
        return sum(self.tag_prior.get(t, 0.0) for t in member.get("tags", ()))

    # ---- learning (source training only)
    def train_step(self, scored, utilities, context=None):
        """Listwise softmax policy gradient: w += lr * sum_i (q_i - p_i) f_i, q = softmax(utilities); L2 decay; clipped."""
        self._guard("train_step")
        if not scored or len(scored) != len(utilities) or max(utilities) - min(utilities) <= 1e-12:
            self.stats["train_skipped_flat"] += 1
            return dict(kind="train", skipped=True)
        p, q = self.probs(scored), _softmax(list(utilities), 0.25)
        grad = Counter()
        for pi, qi, s in zip(p, q, scored):
            for k, v in s["features"].items():
                if v:
                    grad[k] += (qi - pi) * float(v)
        delta = {}
        for k in self.weights:
            nw = _clip(self.weights[k] * (1.0 - self.l2) + self.lr * grad.get(k, 0.0), W_CLIP)
            if abs(nw - self.weights[k]) > 1e-12:
                delta[k] = nw - self.weights[k]
            self.weights[k] = nw
        self.stats["train_steps"] += 1
        rec = dict(kind="train", n=len(scored), u_max=max(utilities), top=_top(delta), context=context)
        self.ledger.append(rec)
        return rec

    def audit_choice(self, scored, chosen, utilities, context=None):
        """Counterfactual regret of a choice; with regret > 0 move w by regret_lr * regret * (f_best - f_chosen)."""
        self._guard("audit_choice")
        ci = _index_of(scored, chosen)
        if ci is None or not utilities:
            return dict(kind="regret", regret=0.0, skipped=True)
        bi = max(range(len(utilities)), key=lambda i: (utilities[i], -i))
        regret = float(utilities[bi] - utilities[ci])
        rec = dict(kind="regret", regret=regret, chosen=ci, best=bi, chosen_kind=scored[ci].get("kind"),
                   best_kind=scored[bi].get("kind"), context=context)
        self.stats["audits"] += 1
        if regret > 1e-12:
            fc, fb = scored[ci]["features"], scored[bi]["features"]
            delta = {}
            for k in set(fc) | set(fb):
                if k not in self.weights:
                    continue
                d = self.regret_lr * regret * (float(fb.get(k, 0.0)) - float(fc.get(k, 0.0)))
                if d:
                    nw = _clip(self.weights[k] + d, W_CLIP)
                    delta[k] = nw - self.weights[k]
                    self.weights[k] = nw
            rec["demoted"] = sorted(k for k, v in delta.items() if v < 0)
            rec["top"] = _top(delta)
            self.stats["regret_updates"] += 1
            self.stats["regret_total"] += regret
        self.ledger.append(rec)
        return rec

    def audit_submission(self, leader_tags, falsified, alternative_tags=(), context=None):
        """Regret on an ACCEPTED leader: falsified -> demote its shortcut tags (and promote tags of surviving alternatives that the
        leader lacked); confirmed -> small promotion. Bounded; affects only leader ordering, never admissibility."""
        self._guard("audit_submission")
        lt, at = set(leader_tags or ()), set(alternative_tags or ())
        delta = {}

        def bump(t, d):
            old = self.tag_prior.get(t, 0.0)
            self.tag_prior[t] = _clip(old + d, PRIOR_CLIP)
            delta[t] = self.tag_prior[t] - old
        if falsified:
            for t in sorted(lt):
                bump(t, -self.prior_lr)
            for t in sorted(at - lt):
                bump(t, self.prior_lr * 0.5)
            self.stats["shortcut_demotions"] += 1
        else:
            for t in sorted(lt):
                bump(t, self.prior_lr * CONFIRM_SCALE)
            self.stats["shortcut_confirmations"] += 1
        rec = dict(kind="shortcut", falsified=bool(falsified), delta=delta, context=context)
        self.ledger.append(rec)
        return rec

    def demoted_shortcuts(self):
        return sorted(t for t, v in self.tag_prior.items() if v < 0)

    # ---- persistence
    def learned_state(self):
        return dict(weights={k: round(v, 12) for k, v in sorted(self.weights.items())},
                    tag_prior={k: round(v, 12) for k, v in sorted(self.tag_prior.items())})

    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.learned_state(), sort_keys=True).encode()).hexdigest()

    def to_dict(self):
        return dict(name=self.name, frozen=self.frozen, lr=self.lr, regret_lr=self.regret_lr, prior_lr=self.prior_lr, l2=self.l2,
                    temperature=self.temperature, stats=dict(self.stats), ledger_len=len(self.ledger), **self.learned_state())

    @classmethod
    def from_dict(cls, d):
        s = cls(weights=d.get("weights"), tag_prior=d.get("tag_prior"), lr=d.get("lr", 0.25), regret_lr=d.get("regret_lr", 0.5),
                prior_lr=d.get("prior_lr", 0.5), l2=d.get("l2", 1e-3), temperature=d.get("temperature", 1.0), name=d.get("name", "trained"))
        s.frozen = bool(d.get("frozen", False))
        s.stats.update(d.get("stats", {}))
        return s

    def save(self, path):
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, sort_keys=True, indent=1)

    @classmethod
    def load(cls, path):
        with open(path) as fh:
            return cls.from_dict(json.load(fh))


def _top(delta, n=8):
    return [(k, round(v, 6)) for k, v in sorted(delta.items(), key=lambda kv: (-abs(kv[1]), kv[0]))[:n]]


# ------------------------------------------------------------------ arms
def pick(arm, scored, selector=None, rng=None):
    """Arm choice rule over already-scored proposals (identical budget / caps are the runner's responsibility).
    fixed: first in menu order; random: seeded uniform draw; untrained: uniform weights; trained: the learned selector."""
    if arm == "fixed":
        return P.choose(scored, "fixed")
    if arm == "random":
        return P.choose(scored, "random", rng=rng or random.Random(0))
    if arm == "untrained":
        return P.choose(scored, "weighted", P.uniform_weights())
    if arm == "trained":
        if selector is None:
            raise ValueError("trained arm needs a selector")
        return selector.choose(scored)
    raise ValueError(f"unknown arm {arm!r}")


# ------------------------------------------------------------------ Delta-State search guide
_SC_UNARY = {"isnull", "not", "json"}


def productions(ast, provenance=None):
    """synth12 production names used by an expanded program (cost-table keys), plus call:<id> for library provenance."""
    out = Counter()

    def walk(x):
        if not isinstance(x, tuple) or not x or not isinstance(x[0], str):
            if isinstance(x, tuple):
                for y in x:
                    walk(y)
            return
        h = x[0]
        if h == "rel" and len(x) == 2:
            out["rel"] += 1
            return
        if h == "col" and len(x) == 2:
            out["col"] += 1
            return
        if h == "const" and len(x) == 3:
            out["const"] += 1
            return
        if h == "join" and len(x) == 6:
            out[f"join:{x[1]}"] += 1
        elif h == "fold" and len(x) == 4:
            for m in x[3]:
                if isinstance(m, tuple) and len(m) >= 2:
                    out[f"fold:{m[1]}"] += 1
        elif h in ("cmp", "arith") and len(x) == 4:
            out[f"{h}:{x[1]}"] += 1
        elif h == "cast" and len(x) == 3:
            out[f"cast:{x[2]}"] += 1
        elif h in ("filter", "rank", "union", "branch", "and", "or") or h in _SC_UNARY:
            out[h] += 1
        for y in x[1:]:
            if isinstance(y, tuple):
                walk(y)
    walk(ast)
    for kind in ("relational", "scalar"):
        for f in (provenance or {}).get(kind, ()):
            out[f"call:{f}"] += 1
    return out


class DeltaStateGuide:
    """Production-cost table learned from experience: frequent productions in verified programs get cost 1, rare / penalised ones
    cost up to synth12.MAX_COST. Empty experience -> empty table -> uniform synth12 costs (the Untrained guide)."""

    def __init__(self, alpha=1.0, penalty=1.0, name="guide"):
        self.pos, self.neg, self.alpha, self.penalty, self.name, self.frozen, self.n = Counter(), Counter(), alpha, penalty, name, False, 0

    def freeze(self):
        self.frozen = True
        return self

    def observe(self, ast, verified, provenance=None):
        if self.frozen:
            raise FrozenSelectorError(f"{self.name}: observe attempted on a frozen guide (evaluation isolation)")
        prods = productions(ast, provenance)
        (self.pos if verified else self.neg).update(prods)
        self.n += 1
        return dict(verified=bool(verified), productions=dict(prods))

    def table(self):
        keys = (set(self.pos) | set(self.neg)) - set(PINNED)
        if not keys:
            return {}
        score = {k: max(0.0, self.pos.get(k, 0) - self.penalty * self.neg.get(k, 0)) + self.alpha for k in keys}
        top = max(score.values())
        tab = {k: int(min(S.MAX_COST, 1 + math.floor(math.log2(top / v) / 2))) for k, v in score.items()}
        tab.update({k: 1 for k in PINNED})
        return dict(sorted(tab.items()))

    def costs(self):
        return S.Costs(self.table())

    def learned_state(self):
        return dict(pos=dict(sorted(self.pos.items())), neg=dict(sorted(self.neg.items())), n=self.n)

    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.learned_state(), sort_keys=True).encode()).hexdigest()

    def to_dict(self):
        return dict(name=self.name, frozen=self.frozen, alpha=self.alpha, penalty=self.penalty, table=self.table(), **self.learned_state())

    @classmethod
    def from_dict(cls, d):
        g = cls(alpha=d.get("alpha", 1.0), penalty=d.get("penalty", 1.0), name=d.get("name", "guide"))
        g.pos.update(d.get("pos", {}))
        g.neg.update(d.get("neg", {}))
        g.n, g.frozen = int(d.get("n", 0)), bool(d.get("frozen", False))
        return g


__all__ = ["ARMS", "Selector", "DeltaStateGuide", "FrozenSelectorError", "counterfactual_utilities", "pick", "productions"]
