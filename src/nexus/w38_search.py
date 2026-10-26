"""Wave 38 proposal search (SOLVER SIDE; NOT LOCKED): lazy best-first over a declared tool set with a transition prior,
exact observational dedup, executed with the PROVER's interpreter (w38_lang). Generic: no domain knowledge."""
from __future__ import annotations

import heapq
import math

from nexus import w38_lang as L


def uniform(T):
    return {"cost": [[1.0] * T for _ in range(T + 1)]}


def search(public, query, tools, depth, prior, budget=10**6, meter=None):
    """Returns the first fitting chain (list of tool specs) or None. `budget` = max node executions (counted)."""
    xs = [x for x, _ in public] + [query]
    n = len(public)
    targets = [L.key(y) for _, y in public]
    cost = prior["cost"]
    T = len(tools)
    seen = {tuple(L.key(x) for x in xs)}
    heap, tick, execs = [], 0, 0
    for t in range(T):
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
            for t in range(T):
                heapq.heappush(heap, (c + row[t], tick, chain + (t,), outs)); tick += 1
    if meter is not None:
        meter["execs"] = meter.get("execs", 0) + execs
    return None
