"""Persistent learner state (R, L, pi, M) with provenance (NOT LOCKED).

R  learned executable representations: unary programs T -> T' built from primitives (body uses hole $0 for the raw
   input); in a task each is instantiated on every input of type T and becomes a leaf (a derived observation feature).
L  learned reusable abstractions: macros with typed positional holes (no input names, no free lambda arguments).
pi effort-allocation / search policy: production costs (the grammar prior over primitives, constants, L and R items),
   the competitor-collection margin, unlabelled probe count, lambda-body cost cap, how many R features to instantiate,
   and the experiment-selection rule.
M  the bounded meta-improver program (improver.py): which proposals are generated, how pi is updated, how proposals are
   admitted and pruned, how the curriculum is chosen. M can never touch the evaluator, verifiers, meter, splits or the
   substrate semantics (it only parameterises improver.py).
Every R / L item carries provenance: birth task, birth round, expanded source, description length, admission record,
and every later task in which it appeared in a submitted solution."""
from __future__ import annotations

import copy
import hashlib
import json

from nexus.campaign import substrate as S


def pi0():
    costs = {p: 2 for p in S.PRIMS}
    costs.update({"x": 1, "a": 1})
    for v in S.BASE_CONSTS:
        costs[f"c:{v}"] = 1 if v <= 2 else 2
    return dict(costs=costs, margin=1, n_probes=8, lam_max=6, feat_k=8, qsel="entropy", confirm_q=4, fit_alpha=0.1,
                item_cost=2)


def empty_state(M):
    return dict(R={}, L={}, pi=pi0(), M=copy.deepcopy(M), next_id=0, history=[])


def tup(o):
    if isinstance(o, list):
        return tuple(tup(x) for x in o)
    return o


def to_json(st):
    return json.loads(json.dumps(st, default=list))


def from_json(d):
    st = copy.deepcopy(d)
    for r in st["R"].values():
        r["body"] = tup(r["body"])
    for m in st["L"].values():
        m["body"] = tup(m["body"])
        m["holes"] = tuple(m["holes"])
    return st


def digest(st):
    core = dict(R={k: v["body"] for k, v in st["R"].items()}, L={k: v["body"] for k, v in st["L"].items()}, pi=st["pi"], M=st["M"])
    return hashlib.sha256(json.dumps(to_json(core), sort_keys=True).encode()).hexdigest()[:16]


def macros_of(st):
    return {lid: (m["body"], tuple(m["holes"]), m["out"]) for lid, m in st["L"].items()}


def feats_of(st, k=None):
    items = sorted(st["R"].items(), key=lambda kv: (-kv[1].get("util", 0), kv[0]))
    if k is not None:
        items = items[:k]
    return {rid: (r["body"], r["tin"], r["tout"]) for rid, r in items}


def costs_of(st):
    c = dict(st["pi"]["costs"])
    for lid, m in st["L"].items():
        c.setdefault(f"L:{lid}", st["pi"].get("item_cost", 2))
    for rid in st["R"]:
        c.setdefault(f"R:{rid}", st["pi"].get("item_cost", 2))
    return c


def expand(ast, st):
    """Inline every L / R reference (for reporting expanded source and description length)."""
    t = ast[0]
    if t == "m":
        body = expand(st["L"][ast[1]]["body"], st)
        args = [expand(a, st) for a in ast[2:]]
        return _subst(body, args)
    if t == "r":
        return _subst(expand(st["R"][ast[1]]["body"], st), [("x", ast[2])])
    if t == "lam":
        return ("lam", ast[1], expand(ast[2], st))
    if t == "p":
        return ast[:2] + tuple(expand(a, st) for a in ast[2:])
    return ast


def _subst(n, args):
    if n[0] == "h":
        return args[n[1]]
    if n[0] == "lam":
        return ("lam", n[1], _subst(n[2], args))
    if n[0] in ("p", "m"):
        return n[:2] + tuple(_subst(a, args) for a in n[2:])
    return n
