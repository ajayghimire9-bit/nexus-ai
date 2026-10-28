"""Step 2 - an acceptance check with EXPLICIT LIMITS (NOT LOCKED). Replaces open-ended random probing (oc revision 1's 150
random long words) with two deterministic tiers built from the hypothesis itself; every query is a counted membership query.

Tier 1  EXHAUSTIVE within a declared finite scope: every kind word of length exactly h from a fresh key (outputs are
        per event, so this also covers every shorter word), h = the largest horizon with |alphabet|^h <= cap_exhaustive,
        one generic value draw per word. Within the learner's hypothesis class (per-key machines whose register updates are
        affine in (acc, x) with +-1 / 0 / 1 coefficients) a generic real draw separates two different output functions of
        the same kind word with probability 1, so tier 1 is an exact comparison of behaviour on all words of length <= h.
Tier 2  TARGETED STRUCTURAL tests for what lies beyond h, aimed at the Step 1 failure modes:
        delayed effects      for every hypothesis mode q, reach q by LOADED prefixes (shortest word reaching q with every
                             register - and, separately, each single register - holding a value-dependent, non-zero value;
                             BFS over (mode, loaded-register set)), apply every kind a, then follow the SHORTEST EMITTING
                             CONTINUATION for each register r from the mode reached (BFS to a transition that emits r), so a
                             register silently corrupted (or not reset) by a is forced into an output
        register interaction single-register loaders + generic distinct values keep r0 != r1, so swapped / merged / split
                             registers cannot hide behind equal values
        boundary values      each delayed-effect test is run twice: a generic draw and a boundary draw rotating through
                             x = 0 at the tested event, x = 1, a sign change (x = -v), and an all-equal record (conflict:
                             every event of the word carries the same value, zero at the tested event = two edges at once)
        middle depth 1       the delayed-effect tests are repeated with one extra event b before the flush (W-method style:
                             covers targets with up to one more mode along every tested path), within cap_structural
Label: a machine that passes is TESTED_WITHIN_STATED_LIMITS with the exact scope record (alphabet, hypothesis modes and
registers, exhaustive horizon and word count, structural tests run, value draws, caps reached, stated assumptions) - never a
universal certificate. Kinds never seen at build time are outside the scope by construction."""
from __future__ import annotations

import itertools
import random
from collections import deque

from nexus import u5_statesplit as SP

GEN = {"acc": 3.7182818, "x": 5.1415926}
BOUNDARY = ("zero", "unit", "sign", "all_equal")


def _ev(g, acc, x):
    return SP.S.ev(g, {"acc": acc, "x": x})


def _emitters(m):
    emit = {}
    for ((q, a), ri, vj), src in m["sources"].items():
        if src and src[0] == "reg":
            emit.setdefault((q, a), set()).add(src[1])
    return emit


def _step_mask(m, q, a, mask):
    """Hypothesis step on (mode, loaded-register mask): loaded = holds a generic non-zero value."""
    if (q, a) not in m["delta"]:
        return q, mask
    new = mask
    for i, rg in enumerate(m["regs"]):
        g = rg["upd"].get((q, a))
        if g is None:
            continue
        v = _ev(g, GEN["acc"] if mask >> i & 1 else 0.0, GEN["x"])
        new = new | (1 << i) if abs(v) > 1e-9 else new & ~(1 << i)
    return m["delta"][(q, a)], new


def loaded_prefixes(m, alpha, max_depth=10):
    """Shortest word reaching each (mode, loaded mask) in the hypothesis."""
    start = (m["init"], 0)
    best = {start: ()}
    dq = deque([start])
    while dq:
        q, mask = dq.popleft()
        w = best[(q, mask)]
        if len(w) >= max_depth:
            continue
        for a in alpha:
            nxt = _step_mask(m, q, a, mask)
            if nxt not in best:
                best[nxt] = w + (a,)
                dq.append(nxt)
    return best


def flush_paths(m, alpha, R, emit, max_depth=8):
    """flush[(q, r)] = shortest continuation from mode q whose LAST event emits register r (hypothesis)."""
    out = {}
    for q0 in range(m["n"]):
        seen, dq = {q0: ()}, deque([q0])
        need = set(range(R))
        while dq and need:
            q = dq.popleft()
            w = seen[q]
            for a in alpha:
                for r in [r for r in need if r in emit.get((q, a), ())]:
                    out[(q0, r)] = w + (a,)
                    need.discard(r)
                if len(w) < max_depth and (q, a) in m["delta"]:
                    q2 = m["delta"][(q, a)]
                    if q2 not in seen:
                        seen[q2] = w + (a,)
                        dq.append(q2)
    return out


def _events(L, word, boundary=None, pos=None, fields=()):
    evs = L.make_events(word, fresh_values=True)
    if boundary is None:
        return evs
    v0 = {f: evs[0].get(f) for f in fields}
    for j, e in enumerate(evs):
        for f in fields:
            if not SP._isnum(e.get(f)):
                continue
            if boundary == "all_equal":
                e[f] = 0 if j == pos else v0[f]
            elif j == pos:
                e[f] = {"zero": 0, "unit": 1, "sign": -abs(e[f]) or -1.0}[boundary]
    return evs


def _mismatch(L, evs):
    rows = L._query(evs)
    L.n_mq += 1
    return rows, not all(SP._rows_eq(g, w) for g, w in zip(SP.run_machine(L.machine, evs), rows))


def structural_tests(m, alpha):
    R, emit = len(m["regs"]), _emitters(m)
    pre = loaded_prefixes(m, alpha)
    flush = flush_paths(m, alpha, R, emit)
    singles = {1 << i for i in range(R)} if R > 1 else set()
    tests = []
    for q in range(m["n"]):
        masks = [k for k in pre if k[0] == q]
        chosen = [max(masks, key=lambda k: (bin(k[1]).count("1"), -len(pre[k])))] if masks else []
        chosen += [k for k in masks if k[1] in singles and k not in chosen]
        for k in chosen:
            p = pre[k]
            for a in alpha:
                q2 = m["delta"].get((q, a), q)
                for r in range(R):
                    f = flush.get((q2, r))
                    if f is not None:
                        tests.append((0, p, a, (), f))
                    for b in alpha:
                        f2 = flush.get((m["delta"].get((q2, b), q2), r))
                        if f2 is not None:
                            tests.append((1, p, a, (b,), f2))
    tests = sorted(dict.fromkeys(tests), key=lambda t: t[0])     # depth-0 first; middle-depth tests within the cap
    return tests, dict(loaded_states=len(pre), flush_paths=len(flush))


def bounded_cex(L, seed=0, cap_exhaustive=400, cap_structural=700, max_cex=3):
    """Run the two tiers; returns (counterexamples, scope record). Stops early once max_cex counterexamples are found."""
    m, alpha = L.machine, list(L.alpha)
    fields = sorted({rg["field"] for rg in m["regs"] if rg.get("field")})
    cex, used = [], dict(exhaustive=0, depth0=0, depth1=0, boundary=0)
    h = 1
    while len(alpha) ** (h + 1) <= cap_exhaustive:
        h += 1
    scope = dict(label="TESTED_WITHIN_STATED_LIMITS", alphabet=alpha, hyp_modes=m["n"], hyp_regs=len(m["regs"]),
                 exhaustive=dict(horizon=h, words=len(alpha) ** h, value_draws="1 generic"),
                 assumptions=["per-key machines; behaviour depends on the kind sequence and register values",
                              "register updates affine in (acc, x) (the learner's hypothesis class)",
                              "only kinds observed at build time"])

    def done(stopped):
        scope.update(queries=sum(used.values()), runs=dict(used), stopped=stopped)
        return cex, scope

    words = list(itertools.product(alpha, repeat=h))
    random.Random(seed).shuffle(words)                          # seeded order; every word is run unless a cex stops early
    for w in words:
        evs = _events(L, w)
        rows, bad = _mismatch(L, evs)
        used["exhaustive"] += 1
        if bad:
            cex.append((evs, rows, w))
            if len(cex) >= max_cex:
                return done("counterexample")
    tests, info = structural_tests(m, alpha)
    scope["structural"] = dict(tests=len(tests), depth0_tests=sum(t[0] == 0 for t in tests), cap=cap_structural, **info)
    for idx, (d, p, a, mid, f) in enumerate(tests):
        for bd in ([None, BOUNDARY[idx % 4]] if d == 0 else [None]):
            if used["depth0"] + used["depth1"] + used["boundary"] >= cap_structural:
                scope["structural"]["cap_reached"] = True
                return done("counterexample" if cex else "passed")
            w = p + (a,) + mid + f
            evs = _events(L, w, bd, len(p), fields)
            rows, bad = _mismatch(L, evs)
            used["boundary" if bd else "depth0" if d == 0 else "depth1"] += 1
            if bad:
                cex.append((evs, rows, w))
                if len(cex) >= max_cex:
                    return done("counterexample")
    scope["structural"]["cap_reached"] = False
    return done("counterexample" if cex else "passed")
