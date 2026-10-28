"""Part 4 - self-evolution over the audited state-learning surface, guided (or not) by NEXUS's research ledger (NOT LOCKED).

Audit result (oc track): u5's evolvable_learner exposed only construction costs and an affinity AST - not the computations
that do STATE learning. The editable surface here is exactly those computations, as used by oc_experiments.episode:
  weights      continuation-class weights for counterexample search            (a) constructing distinguishing continuations
  revision     'all_suffixes' | 'short_suffixes' after a label counterexample   (b) revising state partitions
  order        'occam' | 'freq' update-proposal order (freq = persistent update  (c) proposing register-update expressions
               statistics from earlier episodes; never task memory)
  budget, rounds  queries per counterexample search, search rounds              (d) allocating query budget
Outside the surface (not editable): the oracle, the episode generator, the evaluator (held-out exactness), the query meter.
Fitness = LEARNING CURVE: mean over episodes of the fraction of budgets B = (25, 50, 100, 200, 400) queries at which the
hypothesis was already exact on the held-out stream (task memory wiped per episode)."""
from __future__ import annotations

import copy
import random
import re
import time
from collections import Counter
from pathlib import Path

from nexus import oc_experiments as X
from nexus import oc_learner as OL

BUDGETS = (25, 50, 100, 200, 400)
SURFACE0 = dict(weights={c: 1.0 for c in X.CLASSES}, revision="all_suffixes", order="occam", budget=30, rounds=8)
OPERATORS = ("class_weight", "revision_rule", "update_order", "query_budget")
CATEGORY = {"class_weight": "experiment_design", "revision_rule": "state_representation", "update_order": "search_order",
            "query_budget": "verification"}


def curve_score(r):
    q = r["q_to_correct"]
    return sum(q is not None and q <= b for b in BUDGETS) / len(BUDGETS)


class FreqOrder:
    """Persistent (cross-episode) update statistics for the 'freq' proposal order - part of the procedure, not task memory."""
    counts = Counter()


def run_surface(ep, S, seed=0):
    orig_domain = OL.Learner3._domain
    if S["order"] == "freq" and FreqOrder.counts:
        def _domain(self, t, _o=orig_domain):
            return sorted(_o(self, t), key=lambda n: -FreqOrder.counts.get(repr(n), 0))
        OL.Learner3._domain = _domain
    try:
        r = X.episode(ep, "meta", S["weights"], rounds=S["rounds"], budget=S["budget"], seed=seed,
                      short_suffixes=S["revision"] == "short_suffixes")
    finally:
        OL.Learner3._domain = orig_domain
    FreqOrder.counts.update(r.get("updates", []))                # persistent procedure statistics (no task memory)
    return r


def fitness(S, eps):
    rows = [run_surface(ep, S, seed=ep.seed) for ep in eps]
    return sum(curve_score(r) for r in rows) / len(rows), rows


def mutate(S, op, rnd):
    S = copy.deepcopy(S)
    if op == "class_weight":
        c = rnd.choice(X.CLASSES)
        S["weights"][c] = round(max(0.05, S["weights"][c] * rnd.choice([0.25, 0.5, 2.0, 4.0])), 4)
    elif op == "revision_rule":
        S["revision"] = "short_suffixes" if S["revision"] == "all_suffixes" else "all_suffixes"
    elif op == "update_order":
        S["order"] = "freq" if S["order"] == "occam" else "occam"
    elif op == "query_budget":
        if rnd.random() < 0.5:
            S["budget"] = max(5, min(80, S["budget"] + rnd.choice([-10, 10])))
        else:
            S["rounds"] = max(3, min(14, S["rounds"] + rnd.choice([-2, 2])))
    return S


# ------------------------------------------------------------------------------------------------ the research ledger
CAT_PATTERNS = {
    "verification": r"coverage|verif|reconcil|certif|monitor|conformance|spot.check|checker",
    "experiment_design": r"probe|experiment|counterexample|continuation|active (?:learning|query)|membership quer",
    "state_representation": r"state|register|representation|mode split|splitting|automat",
    "search_order": r"search order|enumerat|heuristic|ranker|proposal policy|cost model|prior",
    "library": r"library|abstraction|macro|admission",
    "curriculum": r"curriculum|practice|dream",
    "meta_evolution": r"meta-?learn|self-?evol|meta-?improv|evolv|genome|learning-to-learn",
    "neural": r"neural|network|mlp|gradient|ppo|transformer|rssm",
    "transport_alignment": r"alignment|transport|gromov|knockoff|wasserstein|mapping",
}
POS = re.compile(r"\b(PASSED|PASS|POSITIVE|PROMOTED|KEPT|CONFIRMED|PROMOTION CANDIDATE)\b")
NEG = re.compile(r"\b(NEGATIVE|REJECTED|FAILED|FAIL|NOT MET|NOT PROMOTED|INCONCLUSIVE)\b")
VERDICT_LINE = re.compile(r"verdict|outcome|gate|criterion|decision|result", re.I)


def ledger_records(docs_dir, exclude=()):
    recs = []
    for p in sorted(Path(docs_dir).glob("*.md")):
        if any(x in p.name for x in exclude):
            continue
        txt = p.read_text(errors="ignore")
        lines = [l for l in txt.splitlines() if VERDICT_LINE.search(l)]
        pos = sum(bool(POS.search(l)) for l in lines)
        neg = sum(bool(NEG.search(l)) for l in lines)
        if pos == neg:
            continue
        low = txt.lower()
        cats = [c for c, pat in CAT_PATTERNS.items() if len(re.findall(pat, low)) >= 3]
        recs.append(dict(doc=p.name, gain=pos > neg, cats=cats))
    return recs


def ledger_predictor(recs):
    n, g = Counter(), Counter()
    for r in recs:
        for c in r["cats"]:
            n[c] += 1
            g[c] += r["gain"]
    return {c: round((g[c] + 1) / (n[c] + 2), 4) for c in CAT_PATTERNS}, dict(n)


# ------------------------------------------------------------------------------------------------ proposal arms
def evolve(arm, eps, n_props, seed, P=None):
    """(1 + 1) evolution of the surface with operator choice by arm; returns (best surface, history, cpu)."""
    rnd = random.Random(seed)
    t0 = time.process_time()
    best = copy.deepcopy(SURFACE0)
    fbest, rows = fitness(best, eps)
    hist = [dict(step=0, op=None, fitness=round(fbest, 4))]
    for i in range(1, n_props + 1):
        if arm == "ledger":
            op = rnd.choices(OPERATORS, weights=[P[CATEGORY[o]] for o in OPERATORS])[0]
        elif arm == "trace":
            unsolved = sum(r["q_to_correct"] is None for r in rows) / len(rows)
            late = sum((r["q_to_correct"] or 0) > 100 for r in rows) / len(rows)
            op = "query_budget" if unsolved > 0.3 else ("class_weight" if late > 0.2 else rnd.choice(OPERATORS))
        else:
            op = rnd.choice(OPERATORS)
        cand = mutate(best, op, rnd)
        f, r2 = fitness(cand, eps)
        hist.append(dict(step=i, op=op, fitness=round(f, 4), accepted=f > fbest))
        if f > fbest:
            best, fbest, rows = cand, f, r2
    return best, hist, time.process_time() - t0
