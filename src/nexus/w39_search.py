"""Wave 39 proposal search (SOLVER SIDE; NOT LOCKED): the Wave 38 lazy best-first search, executed with the Wave 39
interpreter, plus generic type-reachability pruning given to EVERY arm: when no public output is a list, the final step skips
tools whose result is always a list (they cannot fit; the same sound rule Checker v5 uses). No learned component."""
from __future__ import annotations

import heapq

from nexus import w38_search as Q38
from nexus import w39_lang as L

LIST_OUT = {"map", "filter", "sortby", "groupby", "countby", "scan", "take", "drop", "rev", "uniq", "flat", "enum", "pairs",
            "split", "chars", "words", "toks", "proj", "tjoin", "fill", "objs", "recolor_if", "reach", "topo", "indeg",
            "outdeg", "paint"}


def search(public, query, tools, depth, prior, budget=10**6, meter=None, deadline_execs=None):
    xs = [x for x, _ in public] + [query]
    n = len(public)
    targets = [L.key(y) for _, y in public]
    nonlist = all(not isinstance(y, list) for _, y in public)
    last_ok = [t for t in range(len(tools)) if not (nonlist and tools[t]["op"] in LIST_OUT)]
    cost = prior["cost"]
    T = len(tools)
    seen = {tuple(L.key(x) for x in xs)}
    heap, tick, execs = [], 0, 0
    for t in (last_ok if depth == 1 else range(T)):
        heapq.heappush(heap, (cost[0][t], tick, (t,), xs)); tick += 1
    while heap:
        c, _, chain, vals = heapq.heappop(heap)
        execs += 1
        if execs > budget:
            break
        spec = tools[chain[-1]]
        outs = []
        for v in vals:
            o = L.run([spec], v)
            if o == L.ERROR:
                break
            outs.append(o)
        if len(outs) < len(vals):
            continue
        kk = tuple(L.key(o) for o in outs)
        if list(kk[:n]) == targets:
            if meter is not None:
                meter["execs"] = meter.get("execs", 0) + execs
            return [tools[i] for i in chain]
        if kk in seen:
            continue
        seen.add(kk)
        if len(chain) < depth:
            row = cost[chain[-1] + 1]
            for t in (last_ok if len(chain) == depth - 1 else range(T)):
                heapq.heappush(heap, (c + row[t], tick, chain + (t,), outs)); tick += 1
    if meter is not None:
        meter["execs"] = meter.get("execs", 0) + execs
    return None


def design_probe(public, query, tools, verdict, rng, tries=200):
    w = verdict.get("witnesses") or []
    if len(w) < 2:
        return None
    p1, p2 = [tools[i] for i in w[0]["chain"]], [tools[i] for i in w[1]["chain"]]
    pool = [p[0] for p in public] + [query]
    seen = {L.key(p[0]) for p in public} | {L.key(query)}
    for _ in range(tries):
        x = Q38.mutate(rng.choice(pool), rng)
        if L.key(x) in seen:
            continue
        a, b = L.run(p1, x), L.run(p2, x)
        if L.key(a) != L.key(b):
            return x
    return None
