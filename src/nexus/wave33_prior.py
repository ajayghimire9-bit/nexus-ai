"""Milestone A (NOT LOCKED): domain-general fragment priors for proposal search. Solver side, runs in the sandboxed child.

Diagnosis (Wave 31 v3, val_v3, held-out cores): the checker's work is identical across arms. The solver's proposal is
about 31% of a task's work, and Experienced loses on held-out cores (+37% solver work) because its whole-program
macro search fails before the full primitive search. A learned library never touched the primitive search itself.

Mechanism:
  * Lazy best-first proposal over the matched scope's tools (complete for depth <= D): a node is executed only when
    popped. Priority = accumulated transition cost. Observational dedup on exact value vectors (public + query).
  * Transition prior learned from certified source programs:
        p(t | prev) = lam * p_op(t | prev) + (1 - lam) * p_sig(sig(t) | sig(prev)) / |sig(t)|
    where sig(t) is t's TYPE SIGNATURE, inferred by running t on observed sample values (the set of input type ->
    output type pairs where t succeeds). Ops never seen in source still inherit mass from ops with the same
    signature. Laplace smoothing alpha at both levels.
  * Fresh uses the same engine with a uniform prior (length order), so the generic engine gain is separated from the
    learning gain. Placebo uses the learned prior with tool identities permuted (same distribution shape).
Correctness never depends on the prior: the checker certifies over the full declared scope.
"""
from __future__ import annotations

import heapq
import math
import random

from nexus import checker_kernel_v2 as V          # interpreter only (disclosed, as in wave31_solver)

START = -1


def vtype(v):
    if isinstance(v, str):
        return "str"
    if isinstance(v, bool) or isinstance(v, int):
        return "scalar"
    if isinstance(v, dict):
        return "dict:" + ",".join(sorted(v))[:20]
    if isinstance(v, list):
        if V._grid(v):
            return "grid"
        if not v:
            return "list:empty"
        k = {vtype(e) if not isinstance(e, dict) else "dict" for e in v}
        return "list:" + (k.pop() if len(k) == 1 else "mixed")
    return "other"


def compat(a, b):
    return a == b or (a.startswith("list:") and b.startswith("list:") and "list:empty" in (a, b))


def signatures(tools, samples):
    """sig(t) = sorted (input type -> output type) pairs on the sample values where t succeeds."""
    sig = []
    for t in tools:
        pairs = set()
        for v in samples:
            o, _ = V.run([t], v)
            if o != V.ERROR:
                pairs.add((vtype(v), vtype(o)))
        sig.append(repr(sorted(pairs)))
    return sig


def sample_values(views, tools, depth=3, per_type=2):
    """Type-stratified observed values: source inputs and their images under tool chains of length <= depth, keeping
    at most `per_type` values of each observed type (so intermediate types are covered at bounded cost)."""
    by_type, seen = {}, set()

    def add(x):
        k = V.key(x)
        ty = vtype(x)
        if k in seen or len(by_type.get(ty, [])) >= per_type:
            return False
        seen.add(k)
        by_type.setdefault(ty, []).append(x)
        return True
    frontier = []
    for v in views:
        for x in [p[0] for p in v["public"]] + [v["query"]]:
            if add(x):
                frontier.append(x)
    for _ in range(depth):
        nxt = []
        for x in frontier:
            for t in tools:
                o, _ = V.run([t], x)
                if o != V.ERROR and add(o):
                    nxt.append(o)
        frontier = nxt
    return [x for xs in by_type.values() for x in xs]


def type_table(tools, samples):
    """Learned tool knowledge: tmap[t][in_type] = sorted output types observed (absent = predicted error)."""
    tmap = []
    for t in tools:
        m = {}
        for v in samples:
            o, _ = V.run([t], v)
            if o != V.ERROR:
                m.setdefault(vtype(v), set()).add(vtype(o))
        tmap.append({k: sorted(x) for k, x in m.items()})
    return tmap


def learned_redundancy(tools, samples, min_obs=6):
    """(a, b) bigrams observed to equal [a] (b is a no-op after a) on every sample where both are defined."""
    red = []
    for i, a in enumerate(tools):
        imgs = []
        for v in samples:
            o, _ = V.run([a], v)
            if o != V.ERROR:
                imgs.append(o)
        for j, b in enumerate(tools):
            n, ok = 0, True
            for o in imgs:
                o2, _ = V.run([b], o)
                if o2 == V.ERROR:
                    continue
                n += 1
                if V.key(o2) != V.key(o):
                    ok = False
                    break
            if ok and n >= min_obs:
                red.append([i, j])
    return red


def _knowledge(tools, samples, min_obs=6):
    """One pass: images[t][s] for every tool and sample, giving signatures, the type table and redundant bigrams (the
    redundancy test reuses the images and only runs b on a's outputs)."""
    imgs = [[V.run([t], v)[0] for v in samples] for t in tools]
    sig, tmap = [], []
    for ti in range(len(tools)):
        pairs, m = set(), {}
        for v, o in zip(samples, imgs[ti]):
            if o != V.ERROR:
                pairs.add((vtype(v), vtype(o)))
                m.setdefault(vtype(v), set()).add(vtype(o))
        sig.append(repr(sorted(pairs)))
        tmap.append({k: sorted(x) for k, x in m.items()})
    red = []
    for i in range(len(tools)):
        outs = [o for o in imgs[i] if o != V.ERROR]
        for j, b in enumerate(tools):
            n, ok = 0, True
            for o in outs:
                if vtype(o) not in tmap[j]:
                    continue
                o2, _ = V.run([b], o)
                if o2 == V.ERROR:
                    continue
                n += 1
                if V.key(o2) != V.key(o):
                    ok = False
                    break
                if n >= min_obs:
                    break
            if ok and n >= min_obs:
                red.append([i, j])
    return sig, tmap, red


def fit_prior(programs, tools, views, alpha=0.5, lam=0.5, knowledge=True, weights=None):
    """Returns cost[prev+1][t] = -log p(t | prev) for prev in START..T-1, plus learned tool knowledge (type table,
    redundant bigrams) when `knowledge`."""
    T = len(tools)
    keys = [V.key(t) for t in tools]
    idx = {k: i for i, k in enumerate(keys)}
    samples = sample_values(views, tools)
    sig, tmap, red = _knowledge(tools, samples)
    sig_ids = sorted(set(sig))
    sid = [sig_ids.index(s) for s in sig]
    members = {s: sum(1 for x in sid if x == s) for s in set(sid)}
    op = [[0.0] * T for _ in range(T + 1)]
    sg = [[0.0] * len(sig_ids) for _ in range(len(sig_ids) + 1)]
    for pi, p in enumerate(programs):
        w = 1.0 if weights is None else float(weights[pi])     # weights=None reproduces Milestone A exactly
        prev = START
        for spec in p:
            i = idx.get(V.key(spec))
            if i is None:
                prev = START
                continue
            op[prev + 1][i] += w
            sg[(sid[prev] + 1) if prev != START else 0][sid[i]] += w
            prev = i
    cost = []
    for r in range(T + 1):
        prev = r - 1
        n_op = sum(op[r])
        srow = sg[(sid[prev] + 1) if prev != START else 0]
        n_sg = sum(srow)
        row = []
        for t in range(T):
            p_op = (op[r][t] + alpha) / (n_op + alpha * T)
            p_sg = (srow[sid[t]] + alpha) / (n_sg + alpha * len(sig_ids)) / members[sid[t]]
            row.append(-math.log(lam * p_op + (1 - lam) * p_sg))
        cost.append(row)
    out = {"cost": cost, "signatures": sig, "n_programs": len(programs)}
    if knowledge:
        out["types"] = tmap
        out["observed_types"] = sorted({vtype(x) for x in samples})
        out["redundant"] = red
    return out


def uniform_prior(T):
    return {"cost": [[1.0] * T for _ in range(T + 1)], "signatures": [], "n_programs": 0}


def permuted_prior(prior, seed):
    """Placebo: the same cost matrix and the same tool knowledge, with tool identities permuted consistently
    (same distribution shape and the same number of type entries / redundant bigrams, attached to the wrong tools)."""
    T = len(prior["cost"][0])
    perm = list(range(T))
    random.Random(f"w33-placebo-prior:{seed}").shuffle(perm)
    c = prior["cost"]
    new = [[0.0] * T for _ in range(T + 1)]
    for r in range(T + 1):
        src_r = 0 if r == 0 else perm[r - 1] + 1
        for t in range(T):
            new[r][t] = c[src_r][perm[t]]
    out = {"cost": new, "signatures": [], "n_programs": prior["n_programs"], "permutation": perm}
    if "types" in prior:
        out["types"] = [prior["types"][perm[t]] for t in range(T)]
        out["observed_types"] = prior.get("observed_types", [])
        inv = {perm[t]: t for t in range(T)}
        out["redundant"] = [[inv[a], inv[b]] for a, b in prior["redundant"]]
    return out


def _reach(types, depth):
    """reach[r][ty] = types reachable from ty in <= r steps under the learned type table."""
    alltypes = {k for m in types for k in m} | {o for m in types for os_ in m.values() for o in os_}
    reach = [{ty: {ty} for ty in alltypes}]
    for _ in range(depth):
        prev = reach[-1]
        cur = {}
        for ty in alltypes:
            s_ = set(prev.get(ty, {ty}))
            for m in types:
                for o in m.get(ty, []):
                    s_ |= prev.get(o, {o})
            cur[ty] = s_
        reach.append(cur)
    return reach


def best_first(public, query, tools, depth, meter, prior):
    """Lazy uniform-cost search by prior cost (ties by insertion order). Without tool knowledge it is complete for
    chains of length <= depth. With tool knowledge (learned type table + redundant bigrams) children predicted to error,
    to be unable to reach the target output type in the remaining depth, or to be redundant are never executed; this
    is a proposal heuristic (the caller falls back to the complete search if nothing is found).
    Returns the first fitting chain (tool indices) or None."""
    xs = [x for x, _ in public] + [query]
    n = len(public)
    targets = [V.key(y) for _, y in public]
    cost = prior["cost"]
    T = len(tools)
    types = prior.get("types")
    red = {tuple(p) for p in prior.get("redundant", [])}
    goal = {vtype(y) for _, y in public}
    reach = _reach(types, depth) if types else None

    known = {k for m in types for k in m} | set(prior.get("observed_types", [])) if types else set()

    def admissible(t, parent_type, steps_left):
        """steps_left = ops still allowed after t. Only OBSERVED input types are pruned; an input type never seen in
        source (e.g. the held-out domain's own surface) is unknown, hence admissible and able to reach anything."""
        if parent_type not in known:
            return True
        outs_ = types[t].get(parent_type)
        if outs_ is None:
            return False
        for o in outs_:
            if o not in known:
                return True
            rs = reach[steps_left].get(o, {o})
            if any(compat(r, g) for r in rs for g in goal):
                return True
        return False
    root = (tuple(V.key(x) for x in xs), list(xs))
    seen = {root[0]}
    heap, tick = [], 0
    rt = vtype(xs[0])
    for t in range(T):
        if types is not None and not admissible(t, rt, depth - 1):
            meter["pruned"] = meter.get("pruned", 0) + 1
            continue
        heapq.heappush(heap, (cost[0][t], tick, (t,), root[1])); tick += 1
    while heap:
        c, _, chain, parent_vals = heapq.heappop(heap)
        spec = tools[chain[-1]]
        outs = []
        for v in parent_vals:
            o, s = V.run([spec], v)
            meter["prover"] = meter.get("prover", 0) + s + 1
            if o == V.ERROR:
                break
            outs.append(o)
        if len(outs) < len(parent_vals):
            continue
        kk = tuple(V.key(o) for o in outs)
        if list(kk[:n]) == targets:
            return list(chain)
        if kk in seen:
            continue
        seen.add(kk)
        if len(chain) < depth:
            row = cost[chain[-1] + 1]
            pt = vtype(outs[0])
            left = depth - len(chain) - 1
            for t in range(T):
                if types is not None and ((chain[-1], t) in red or not admissible(t, pt, left)):
                    meter["pruned"] = meter.get("pruned", 0) + 1
                    continue
                heapq.heappush(heap, (c + row[t], tick, chain + (t,), outs)); tick += 1
    return None
