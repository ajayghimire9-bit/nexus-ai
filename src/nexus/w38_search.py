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


def mutate(x, rng, depth=0):
    """Generic input mutation for active probing (no domain knowledge): edits one atom of the value."""
    if isinstance(x, str):
        if not x:
            return "a"
        i = rng.randrange(len(x))
        pool = sorted(set(x)) + list("0123456789")
        return x[:i] + rng.choice(pool) + x[i + 1:]
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, int):
        return x + rng.choice((-2, -1, 1, 2))
    if isinstance(x, list):
        if not x:
            return x
        if all(isinstance(r, list) for r in x) and x and all(isinstance(c, int) for r in x for c in r):
            g = [list(r) for r in x]
            i, j = rng.randrange(len(g)), rng.randrange(len(g[0]))
            g[i][j] = rng.choice(sorted({c for r in g for c in r} | {0}))
            return g
        y = list(x)
        k = rng.randrange(len(y))
        if rng.random() < 0.2 and len(y) > 1:
            y.pop(k)
        else:
            y[k] = mutate(y[k], rng, depth + 1)
        return y
    if isinstance(x, dict):
        if set(x) == {"nodes", "edges"}:
            e = [list(p) for p in x["edges"]]
            ns = x["nodes"]
            if e and rng.random() < 0.5:
                e.pop(rng.randrange(len(e)))
            elif len(ns) > 1:
                a, b = sorted(rng.sample(ns, 2))
                if [a, b] not in e:
                    e.append([a, b])
            return {"nodes": list(ns), "edges": sorted(e)}
        y = dict(x)
        if y:
            k = rng.choice(sorted(y))
            y[k] = mutate(y[k], rng, depth + 1)
        return y
    return x


def design_probe(public, query, tools, verdict, rng, tries=200):
    w = verdict.get("witnesses") or []
    if len(w) < 2:
        return None
    p1, p2 = [tools[i] for i in w[0]["chain"]], [tools[i] for i in w[1]["chain"]]
    pool = [p[0] for p in public] + [query]
    seen = {L.key(p[0]) for p in public} | {L.key(query)}
    for _ in range(tries):
        x = mutate(rng.choice(pool), rng)
        if L.key(x) in seen:
            continue
        a, b = L.run(p1, x), L.run(p2, x)
        if L.key(a) != L.key(b):
            return x
    return None
