"""Phase 10 two-tier epistemic memory and the MDL promotion test (NOT LOCKED).

P* (provisional memory) keeps what is NOT yet verified, with explicit counts:
  hypotheses  abstract edit patterns (role form) from partial stage repairs of unsolved tasks and from failed attempts;
              support = later verified repairs (or further partials) containing the pattern, refute = regressions of
              the same operator on the same evidence; a Beta(1 + s, 1 + r) mean and 90 % interval
  witnesses   boundary witness rows x_diff of decision points (with the stakeholder answer, when one was given)
  claims      unresolved document claims (provenance, effect, why unresolved)
Promotion P* -> L* (trusted library) only through the sleep admission: Delta MDL > threshold across >= 2 tasks AND
leave-one-paradigm-out validation without regression (lineage10). The 'discard uncertain' ablation (C2) keeps P* empty
and abstracts only from verified repairs.

DESCRIPTION LENGTH (a declared bit model): a primitive step costs log2(|OPS|) + log2(B) bits (B = 10 typical parameter
choices), a library call log2(|OPS| + |L|) + log2(2); a method of k steps costs k primitive steps to define. A candidate
supported by t tasks saves t * (k * step - call) - k * step bits. Single-operator specialisations need t >= 4; two-step
compositions t >= 2."""
from __future__ import annotations

import json
import math

from nexus.de_phase6 import engines6 as E

STEP_BITS = math.log2(len(E.OPS)) + math.log2(10)


def call_bits(n_lib):
    return math.log2(len(E.OPS) + max(1, n_lib)) + 1.0


def delta_mdl(k, t, n_lib):
    return round(t * (k * STEP_BITS - call_bits(n_lib)) - k * STEP_BITS, 3)


def empty_p():
    return dict(hypotheses={}, witnesses=[], claims=[])


def _key(edits):
    return json.dumps(edits, sort_keys=True, default=list)


def add_hypothesis(P, edits, project, kind):
    h = P["hypotheses"].setdefault(_key(edits), dict(edits=edits, support=0, refute=0, sources=[], kinds=[]))
    if project not in h["sources"]:
        h["sources"].append(project)
        h["support"] += 1
    if kind not in h["kinds"]:
        h["kinds"].append(kind)
    return h


def confirm(P, edits, project):
    """A verified repair contains the pattern: +support."""
    k = _key(edits)
    if k in P["hypotheses"] and project not in P["hypotheses"][k]["sources"]:
        P["hypotheses"][k]["support"] += 1
        P["hypotheses"][k]["sources"].append(project)


def refute(P, op, feats):
    for h in P["hypotheses"].values():
        if any(e[0] == op for e in h["edits"]):
            h["refute"] += 1


def interval(h):
    a, b = 1 + h["support"], 1 + h["refute"]
    m = a / (a + b)
    sd = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
    return round(m, 3), round(max(0.0, m - 1.645 * sd), 3), round(min(1.0, m + 1.645 * sd), 3)


def strong(P, n=3, min_support=2):
    hs = [h for h in P["hypotheses"].values() if h["support"] >= min_support and h["refute"] == 0]
    return sorted(hs, key=lambda h: (-h["support"], -len(h["edits"])))[:n]
