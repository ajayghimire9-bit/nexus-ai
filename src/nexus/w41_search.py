"""Wave 41 shared search (SOLVER SIDE; NOT LOCKED): the Wave 40 dominance-repaired best-first walk (w40_search) plus the base
static lemmas (w41_lemmas), used identically by every arm. Arms differ only in the cost matrix (prior / routing) and in what
the child tries before searching (compiled skills).
  * last layer: a child tool is pushed only if its intro covers every public example's needed characters (it is never
    executed otherwise; such a child cannot fit, by the lemma);
  * earlier layers: a state is not expanded if some needed character is outside the union of the scope's intros (it is not
    marked in the dominance table, so a later arrival is unaffected).
The lemmas never touch fitting checks or certificates: a state is still a solution iff it equals the public targets, and
every verdict is still Checker v5's. With lemmas=False this is exactly w40_search."""
from __future__ import annotations

import heapq

from nexus import w39_lang as L
from nexus import w39_search as Q39
from nexus import w41_lemmas as M

LIST_OUT = Q39.LIST_OUT
design_probe = Q39.design_probe


def _walk(public, query, tools, depth, prior, budget, meter, on_fit, lem=None, lang=L, last_rule=True):
    xs = [x for x, _ in public] + [query]
    n = len(public)
    targets = [lang.key(y) for _, y in public]
    nonlist = all(not isinstance(y, list) for _, y in public)
    last_ok = [t for t in range(len(tools)) if not (last_rule and nonlist and tools[t]["op"] in LIST_OUT)]
    cost = prior["cost"]
    T = len(tools)
    min_depth = {tuple(lang.key(x) for x in xs): 0}
    heap, tick, execs, skips = [], 0, 0, 0

    def children(vals, d):
        nonlocal skips
        if d == depth - 1:
            cand = last_ok
            if lem is not None:
                need = lem.need(vals[:n])
                if any(need):
                    keep = [t for t in cand if lem.tool_ok(t, need)]
                    skips += len(cand) - len(keep)
                    cand = keep
            return cand
        if lem is not None and not lem.reachable(lem.need(vals[:n]), depth - d):
            skips += T
            return []
        return range(T)

    for t in children(xs, 0):
        heapq.heappush(heap, (cost[0][t], tick, (t,), xs)); tick += 1
    stopped = None
    while heap:
        c, _, chain, vals = heapq.heappop(heap)
        execs += 1
        if execs > budget:
            break
        spec = tools[chain[-1]]
        outs = []
        for v in vals:
            o = lang.run([spec], v)
            if o == lang.ERROR:
                break
            outs.append(o)
        if len(outs) < len(vals):
            continue
        kk = tuple(lang.key(o) for o in outs)
        d = len(chain)
        if list(kk[:n]) == targets and on_fit(chain, kk, outs):
            stopped = chain
            break
        if min_depth.get(kk, depth + 1) <= d:
            continue
        if d < depth:
            ch = children(outs, d)
            if not ch:
                continue
            min_depth[kk] = d
            row = cost[chain[-1] + 1]
            for t in ch:
                heapq.heappush(heap, (c + row[t], tick, chain + (t,), outs)); tick += 1
        else:
            min_depth[kk] = d
    if meter is not None:
        meter["execs"] = meter.get("execs", 0) + execs
        meter["lemma_skips"] = meter.get("lemma_skips", 0) + skips
    return stopped, execs


def search(public, query, tools, depth, prior, budget=10**6, meter=None, lem=None, lang=L, last_rule=True):
    ch, _ = _walk(public, query, tools, depth, prior, budget, meter, lambda c, k, o: True, lem, lang, last_rule)
    return [tools[i] for i in ch] if ch is not None else None


def reachable_fitting(public, query, tools, depth, prior, budget=10**9, lem=None, lang=L, last_rule=True, meter=None):
    found = set()
    _walk(public, query, tools, depth, prior, budget, meter, lambda c, k, o: found.add(k) or False, lem, lang, last_rule)
    return found


def disagreeing_witness(public, query, tools, depth, prior, claimed, budget=10**9, meter=None, lem=None, lang=L,
                        last_rule=True):
    ck = lang.key(claimed)
    n = len(public)
    ch, _ = _walk(public, query, tools, depth, prior, budget, meter, lambda c, k, o: k[n] != ck, lem, lang, last_rule)
    return [tools[i] for i in ch] if ch is not None else None


def disagreeing_on(public, query, tools, depth, prior, cand, x, budget=10**9, meter=None, lem=None, lang=L, last_rule=True):
    """A fitting in-scope chain whose output on future input x differs from cand's (for distinguishing-query design)."""
    want = lang.key(lang.run(cand, x))

    def on_fit(chain, k, o):
        return lang.key(lang.run([tools[i] for i in chain], x)) != want
    ch, _ = _walk(public, query, tools, depth, prior, budget, meter, on_fit, lem, lang, last_rule)
    return [tools[i] for i in ch] if ch is not None else None
