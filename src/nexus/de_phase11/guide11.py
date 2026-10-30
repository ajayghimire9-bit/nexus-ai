"""Phase 11 learned search guidance (NOT LOCKED): production costs fitted on solved programs.
fit(programs, vocabulary): counts the search productions used by each program (relational: rel, filter, rank, fold:<agg>, join:<kind>,
union, call:<f>; scalar: col, const, isnull, not, and, or, branch, json, cmp:<op>, arith:<op>, cast:<type>, call:<f>), add-one
smoothing over the declared vocabulary, cost(prod) = clamp(1 + round(log2(p_max / p)), 1, synth11.MAX_COST). The final project_map and
the final aggregation's measure functions are deductive steps (not search productions) and are not counted.
G_A0 is fitted on primitive-EXPANDED records; G_M on the SAME records rewritten with the frozen library (abstr11.rewrite); the same
records, splits and fitting rule; the only difference is the representation."""
from __future__ import annotations

import math
from collections import Counter

from nexus.de_phase11 import core11 as C, synth11 as S

BASE_VOCAB = (["rel", "filter", "rank", "union"] + [f"fold:{a}" for a in C.AGGS] + [f"join:{k}" for k in C.JOIN_KINDS] +
              ["col", "const", "isnull", "not", "and", "or", "branch", "json"] + [f"cmp:{o}" for o in C.CMP_OPS] + [f"arith:{o}" for o in C.ARITH_OPS] +
              [f"cast:{t}" for t in (C.INT, C.NUM, C.STR)])


def productions(x, top=True, out=None):
    out = Counter() if out is None else out
    if not isinstance(x, tuple) or not x or not isinstance(x[0], str):
        return out
    op = x[0]
    if op == "call":
        out[f"call:{x[1]}"] += 1
        for a in x[2]:
            productions(a, False, out)
        return out
    if op == "map":
        productions(x[1], False, out)
        for _, e in x[2]:
            if not top:
                productions(e, False, out)
            else:
                _scalar(e, out)
        return out
    if op == "rel":
        out["rel"] += 1
    elif op == "filter":
        out["filter"] += 1
        productions(x[1], False, out)
        _scalar(x[2], out)
    elif op == "fold":
        for _, agg, e in x[3]:
            out[f"fold:{agg}"] += 1
            if e is not None:
                _scalar(e, out)
        productions(x[1], False, out)
    elif op == "rank":
        out["rank"] += 1
        productions(x[1], False, out)
    elif op == "join":
        out[f"join:{x[1]}"] += 1
        productions(x[2], False, out)
        productions(x[3], False, out)
    elif op == "union":
        out["union"] += 1
        productions(x[1], False, out)
        productions(x[2], False, out)
    return out


def _scalar(e, out):
    if not isinstance(e, tuple) or not e:
        return
    op = e[0]
    if op == "call":
        out[f"call:{e[1]}"] += 1
        for a in e[2]:
            _scalar(a, out)
        return
    if op in ("cmp", "arith"):
        out[f"{op}:{e[1]}"] += 1
        _scalar(e[2], out)
        _scalar(e[3], out)
    elif op == "cast":
        out[f"cast:{e[2]}"] += 1
        _scalar(e[1], out)
    elif op in ("col", "const"):
        out[op] += 1
    else:
        out[op] += 1
        for y in e[1:]:
            if isinstance(y, tuple) and y and isinstance(y[0], str):
                _scalar(y, out)


def fit(programs, library_names=()):
    vocab = list(BASE_VOCAB) + [f"call:{f}" for f in library_names]
    cnt = Counter()
    for p in programs:
        cnt.update(productions(p))
    total = sum(cnt[v] for v in vocab) + len(vocab)
    probs = {v: (cnt[v] + 1) / total for v in vocab}
    pmax = max(probs.values())
    table = {v: max(1, min(S.MAX_COST, 1 + round(math.log2(pmax / p)))) for v, p in probs.items()}
    table["__default__"] = S.MAX_COST
    return table, dict(records=len(programs), productions=sum(cnt.values()), vocab=len(vocab), counts=dict(cnt))
