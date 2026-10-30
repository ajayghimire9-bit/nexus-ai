"""Phase 10F atomic-dedup architectural baseline (NOT LOCKED; audit finding 4).

The Phase 10E replay macro recombines a dedup that Phase 10E split into two primitives (add_partition -> set_dedup). B_atomic
asks whether the macro beats simply HAVING the original one-step dedup with the same column-role features:

  SUBSTRATE  dag10e with the Phase 10D ATOMIC set_dedup restored on relations WITHOUT a dedup (every int key x int order x
             direction in one edit, dag10d.candidates) and add_partition removed. Everything else is dag10e unchanged: the
             Phase 10E discriminative roles (ckey = schema.yml unique test, arrival = increases with landing order inside every
             duplicate group), the acceptance rules (deterministic_dedup, latest_state_witness), the other operators, search10e.
             `atomic()` swaps dag10e's operator table for the duration of a with-block (search10e, bind and replay look the
             operators up at call time); nothing on disk changes.
  GUIDANCE   B_atomic_fixed: the fixed operator order. B_atomic_learned: G_atomic, the ranker trained (same trainer, seed and
             held-project split as the learner's last ranker cycle) on the SAME step records as G_L0, rewritten into the atomic
             substrate: each consecutive add_partition -> set_dedup pair on the stg node becomes ONE atomic set_dedup record (the
             partition step's context and relation roles + the ordering step's key / order / direction roles); an unpaired
             add_partition record and every add_partition negative are dropped (that operator does not exist here)."""
from __future__ import annotations

import contextlib

from nexus.de_phase10 import guide10 as G
from nexus.de_phase10c import search10c as S10
from nexus.de_phase10c.rng10c import rng, seed_of
from nexus.de_phase10d import dag10d as D10
from nexus.de_phase10e import dag10e as D

OPS_ATOMIC = D10.OPS
_SPLIT = dict(OPS=D.OPS, candidates=D.candidates)


def candidates_atomic(op, spec_k, dom):
    if op == "add_partition":
        return []
    if op == "set_dedup":
        return D10.candidates(op, spec_k, dom) if D.OP_NODE[op] == dom.k else []
    return _SPLIT["candidates"](op, spec_k, dom)


@contextlib.contextmanager
def atomic():
    D.OPS, D.candidates = OPS_ATOMIC, candidates_atomic
    try:
        yield
    finally:
        D.OPS, D.candidates = _SPLIT["OPS"], _SPLIT["candidates"]


def _roles(abs_edit):
    out = []
    for x in abs_edit[1:]:
        out += [f"{x[0]}:{r}" for r in x[1]] if isinstance(x[1], (tuple, list)) else [f"{x[0]}={x[1]}"]
    return out


def rewrite_atomic(steps):
    """Step records over the split substrate -> ranker pairs over the atomic substrate (see the module docstring)."""
    pairs, merged = [], 0
    for pid, recs in steps:
        i = 0
        while i < len(recs):
            r = recs[i]
            negs = [n for n in r["negs"] if n[0] != "op:add_partition"]
            if r["abs"][0] == "add_partition":
                nx = recs[i + 1] if i + 1 < len(recs) else None
                if nx is not None and nx["stage"] == r["stage"] and nx["abs"][0] == "set_dedup":
                    a = ["set_dedup", r["abs"][1]] + list(nx["abs"][2:])
                    pos = S10.tokens("op:set_dedup", r["ctx"], _roles(a))
                    pairs += [(pid, pos, ng) for ng in negs + [n for n in nx["negs"] if n[0] != "op:add_partition"]]
                    merged += 1
                    i += 2
                    continue
                i += 1
                continue
            pairs += [(pid, r["pos"], ng) for ng in negs]
            i += 1
    return pairs, merged


def atomic_guide(mem, rep, cycles):
    """G_atomic on the learner's final step records (the held-project split and trainer seed of its last ranker cycle)."""
    steps = [(pid, recs) for pid, recs in mem["steps"]]
    pairs, merged = rewrite_atomic(steps)
    projects = sorted({pid.split("#")[0] for pid, _ in steps})
    held = set(rng(rep, cycles, 3).sample(projects, max(1, len(projects) // 5))) if projects else set()
    tr = [(a, b) for pid, a, b in pairs if pid.split("#")[0] not in held]
    te = [(a, b) for pid, a, b in pairs if pid.split("#")[0] in held]
    w = G.train(tr, seed=seed_of(rep, cycles, 4))
    return w, dict(pairs=len(pairs), merged_dedup_pairs=merged, train=len(tr), heldout=len(te), heldout_pair_accuracy=G.pair_accuracy(w, te), weights=len(w))
