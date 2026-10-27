"""Wave 40 proposal search (SOLVER SIDE; NOT LOCKED): the Wave 39 lazy best-first search with the state-dominance repair.

Defect (Wave 39, traced in Wave 40 Step 1): observational dedup kept ONE global `seen` set of value states, marked at whatever
depth a state was first popped. Under a non-uniform prior a state can first be popped on a cheaper but DEEPER route (e.g. a
no-op encoder followed by the true first step); the same state later arriving on a shallower route, which still had the depth
needed to finish, was discarded. Uniform priors pop states in depth order, so Fresh was unaffected.

Repair (full continuation dominance): a popped state is pruned only if an already-EXPANDED route to the same state dominates
it in every resource that constrains future extensions. In this language those resources are exactly
  * the value vector on the public inputs + query (it determines every future value), and
  * the remaining depth (it determines how many extensions are legal and whether the final-step type rule applies).
The tool set is identical at every node, there are no bound variables, and the execution budget counts executions, not prior
cost; the prior cost and the last tool only change the ORDER of exploration, never legality. So the dominance tuple is
(values, remaining depth) and a route dominates iff it reached the same values with >= remaining depth, i.e. we keep
`min_depth_seen[values]` and re-expand whenever a strictly shorter route arrives (new_depth < min_depth_seen).

Consequence (tested exhaustively in tests/test_search_order_invariance.py): run to completion, every ordering expands every
reachable state at its minimal depth, so the set of reachable fitting value vectors is identical for every prior."""
from __future__ import annotations

import heapq

from nexus import w39_lang as L
from nexus import w39_search as Q39

LIST_OUT = Q39.LIST_OUT
design_probe = Q39.design_probe


def _walk(public, query, tools, depth, prior, budget, meter, on_fit, lang=L, last_rule=True):
    xs = [x for x, _ in public] + [query]
    n = len(public)
    targets = [lang.key(y) for _, y in public]
    nonlist = all(not isinstance(y, list) for _, y in public)
    last_ok = [t for t in range(len(tools)) if not (last_rule and nonlist and tools[t]["op"] in LIST_OUT)]
    cost = prior["cost"]
    T = len(tools)
    min_depth = {tuple(lang.key(x) for x in xs): 0}
    heap, tick, execs = [], 0, 0
    for t in (last_ok if depth == 1 else range(T)):
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
            continue                                  # dominated: expanded before with >= as many remaining steps
        min_depth[kk] = d
        if d < depth:
            row = cost[chain[-1] + 1]
            for t in (last_ok if d == depth - 1 else range(T)):
                heapq.heappush(heap, (c + row[t], tick, chain + (t,), outs)); tick += 1
    if meter is not None:
        meter["execs"] = meter.get("execs", 0) + execs
    return stopped, execs


def search(public, query, tools, depth, prior, budget=10**6, meter=None, lang=L, last_rule=True):
    """First fitting chain (list of tool specs) in prior order, or None. Same interface as w39_search.search."""
    ch, _ = _walk(public, query, tools, depth, prior, budget, meter, lambda c, k, o: True, lang, last_rule)
    return [tools[i] for i in ch] if ch is not None else None


def reachable_fitting(public, query, tools, depth, prior, budget=10**9, lang=L, last_rule=True):
    """Run to completion: the set of fitting value vectors (outputs on public inputs + query) reachable within `depth`."""
    found = set()
    _walk(public, query, tools, depth, prior, budget, None, lambda c, k, o: found.add(k) or False, lang, last_rule)
    return found


def disagreeing_witness(public, query, tools, depth, prior, claimed, budget=10**9, meter=None, lang=L, last_rule=True):
    """Sound ambiguity short-circuit (Wave 40 Step 5): continue in prior order until a fitting chain whose QUERY answer differs
    from `claimed` is found; returns that chain (two in-scope fitting programs with different query answers => the scope verdict
    is AMBIGUOUS whatever else exists) or None after exhausting the scope / budget (then the checker must sweep)."""
    ck = lang.key(claimed)
    n = len(public)
    ch, _ = _walk(public, query, tools, depth, prior, budget, meter, lambda c, k, o: k[n] != ck, lang, last_rule)
    return [tools[i] for i in ch] if ch is not None else None
