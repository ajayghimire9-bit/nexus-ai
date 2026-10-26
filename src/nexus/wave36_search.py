"""R1 (NOT LOCKED): a documented ADAPTATION of Stitch-style library abstraction (Bowers et al. 2023, arXiv:2211.16605)
for this setting. Solver side; runs in the sandboxed child.

What Stitch does: top-down search for lambda abstractions that maximise corpus compression. What is adapted here:
  * NEXUS programs are linear op chains, not lambda terms, so an abstraction is a contiguous core FRAGMENT (length 2-3) and
    parameterisation reduces to the ops' own constants. (Stitch's hole-variable search over tree bodies is MISSING.)
  * Utility = compression of the certified corpus: count * (len - 1) - len (MDL-style rewrite gain minus definition cost);
    the top K with count >= 2 are kept (Stitch's exact utility and branch-and-bound are MISSING).
  * Use: fragments are extra single-step moves inside the same lazy best-first proposal (no separate macro phase, so a
    library miss adds no extra search), with prior cost = sum of the learned transition costs of the body minus
    log(1 + count); expanded length is capped at the matched depth.
Controls: FixedDSL = all ordered pairs of the 6 core ops (36 fragments, uniform weights, no learning);
Placebo = the learned fragments with op identities permuted (size- and shape-matched).
Correctness never depends on the library: the candidate is expanded to G_P ops and Checker v3 certifies over full scope.
"""
from __future__ import annotations

import heapq
import math
import random

from nexus import checker_kernel_v2 as V          # interpreter only (disclosed, as everywhere in the solver)
from nexus import wave31_grammar as G
from nexus import wave33_prior as P

CORE = [dict(v) for v in G.CORE_OPS.values()]


def _core(prog):
    return [dict(s) for s in prog if s["op"] not in G.ADAPTER_OPS]


def fragments_from(programs, k=8, min_count=2):
    counts = {}
    for p in programs:
        c = _core(p)
        seen = set()
        for n in (2, 3):
            for i in range(len(c) - n + 1):
                key = V.key(c[i:i + n])
                if key not in seen:                     # count once per program (corpus support)
                    seen.add(key)
                    counts[key] = counts.get(key, 0) + 1
    scored = []
    for key, cnt in counts.items():
        body = __import__("json").loads(key)
        util = cnt * (len(body) - 1) - len(body)
        if cnt >= min_count and util > 0:
            scored.append((-util, key, body, cnt))
    return [{"body": b, "count": c} for _, _, b, c in sorted(scored)[:k]]


def fixed_dsl_fragments():
    return [{"body": [a, b], "count": 1} for a in CORE for b in CORE]


def placebo_fragments(frags, seed):
    ops = [V.key(o) for o in CORE]
    perm = ops[:]
    random.Random(f"w36-placebo-frag:{seed}").shuffle(perm)
    m = dict(zip(ops, perm))
    out = []
    for f in frags:
        out.append({"body": [__import__("json").loads(m.get(V.key(s), V.key(s))) for s in f["body"]], "count": f["count"]})
    return out


def frag_best_first(public, query, gp, depth, meter, prior, frags):
    """Lazy best-first over G_P primitives plus fragment moves; returns an EXPANDED chain of G_P specs or None.
    Each heap entry = (cost, tick, chain_so_far, parent_values, move_ops): the move's ops are executed only when popped.
    Dedup on exact observational value vectors (public inputs + query)."""
    xs = [x for x, _ in public] + [query]
    n = len(public)
    targets = [V.key(y) for _, y in public]
    T = len(gp)
    idx = {V.key(t): i for i, t in enumerate(gp)}
    cost = prior["cost"]
    moves = [((i,), 0.0) for i in range(T)]
    for f in frags:
        body = tuple(idx.get(V.key(s_)) for s_ in f["body"])
        if None not in body:
            moves.append((body, math.log(1 + f["count"])))

    def mcost(prev, body, bonus):
        c, p_ = 0.0, prev
        for b in body:
            c += cost[p_ + 1][b]
            p_ = b
        return c - bonus
    types = prior.get("types")
    red = {tuple(p_) for p_ in prior.get("redundant", [])}
    goal = {P.vtype(y) for _, y in public}
    reach = P._reach(types, depth) if types else None
    known = ({k for m in types for k in m} | set(prior.get("observed_types", []))) if types else set()

    def admissible(t, parent_type, left):
        """The same learned type-reachability rule as wave33_prior.best_first (applied to primitive moves only)."""
        if types is None or parent_type not in known:
            return True
        outs_ = types[t].get(parent_type)
        if outs_ is None:
            return False
        return any(o not in known or any(P.compat(r, g) for r in reach[left].get(o, {o}) for g in goal) for o in outs_)

    def allowed(prev, body, parent_type, used):
        if len(body) == 1:
            if prev >= 0 and (prev, body[0]) in red:
                return False
            return admissible(body[0], parent_type, depth - used - 1)
        return True
    seen = {tuple(V.key(x) for x in xs)}
    heap, tick = [], 0
    rt = P.vtype(xs[0])
    for body, bonus in moves:
        if len(body) <= depth and allowed(-1, body, rt, 0):
            heapq.heappush(heap, (mcost(-1, body, bonus), tick, (), list(xs), body)); tick += 1
    while heap:
        c, _, chain, vals, body = heapq.heappop(heap)
        outs, ok = vals, True
        for b in body:
            nxt = []
            for v in outs:
                o, s_ = V.run([gp[b]], v)
                meter["prover"] = meter.get("prover", 0) + s_ + 1
                if o == V.ERROR:
                    ok = False
                    break
                nxt.append(o)
            if not ok:
                break
            outs = nxt
        if not ok:
            continue
        chain = chain + body
        kk = tuple(V.key(o) for o in outs)
        if list(kk[:n]) == targets:
            return [dict(gp[b]) for b in chain]
        if kk in seen:
            continue
        seen.add(kk)
        pt = P.vtype(outs[0])
        for body2, bonus in moves:
            if len(chain) + len(body2) <= depth and allowed(chain[-1], body2, pt, len(chain)):
                heapq.heappush(heap, (c + mcost(chain[-1], body2, bonus), tick, chain, outs, body2)); tick += 1
    return None
