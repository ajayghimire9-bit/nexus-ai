"""Wave 40 learned knowledge (SOLVER SIDE; NOT LOCKED). Extends w39_learn without changing it.
  fixed_repr : Fixed-v5 as the base prior mean, updated with the learned representation counts. Repr-v5's cost is a Dirichlet
               posterior with a UNIFORM base measure of strength alpha*T: (n(k) + alpha) / (N + alpha*T). Fixed+Repr replaces the
               uniform base by the Fixed-v5 row distribution p_fix(k | prev) = softmax(-fixed cost) at the SAME strength:
                 row 0 (first step) : -log((first(k) + alpha*T * p_fix(k | START)) / (N_first + alpha*T))
                 rows r > 0         : 0.5 * (-log p_fix(k | prev)) + 0.5 * -log((last(k) + alpha*T * p_fix(k | prev)) / (N_last + alpha*T))
               (Repr's rows r > 0 are 0.5 * (log T + last cost), i.e. the same 50/50 mix with the uniform base; only the base changes).
               No new hyperparameter. With no programs it reduces exactly to Fixed-v5's ordering.
Everything else delegates to w39_learn.cost_matrix."""
from __future__ import annotations

import math

from nexus import w38_learn as K
from nexus import w39_learn as W


def _norm(costs):
    m = min(costs)
    w = [math.exp(-(c - m)) for c in costs]
    z = sum(w)
    return [x / z for x in w]


def cost_matrix(prior, tools):
    if not prior or prior.get("kind") != "fixed_repr":
        return W.cost_matrix(prior, tools)
    fx = W.cost_matrix({"kind": "fixed5"}, tools)["cost"]
    rp = prior["repr"]
    T = len(tools)
    ks = [K.akey(t) for t in tools]
    s = rp["alpha"] * T
    nf, nl = sum(rp["first"].values()), sum(rp["last"].values())

    def row(r):
        pf = _norm(fx[r])
        if r == 0:
            return [-math.log((rp["first"].get(k, 0) + s * p) / (nf + s)) for k, p in zip(ks, pf)]
        return [0.5 * -math.log(p) + 0.5 * -math.log((rp["last"].get(k, 0) + s * p) / (nl + s)) for k, p in zip(ks, pf)]
    return {"cost": K.Lazy(T + 1, row)}


def _learned(prior, tools):
    """Exact O(T)-per-row re-implementation of w38_learn.cost_matrix's 'learned' mixture (also used by Placebo and the online
    learners): w38 recounts `members` (tools sharing an op) inside the per-tool loop, O(T^2) per row; here the counts are
    precomputed. Every cost is the same float expression evaluated in the same order (tested for exact equality)."""
    T = len(tools)
    ks = [K.akey(t) for t in tools]
    ops = [t["op"] for t in tools]
    a, lam = prior["alpha"], prior["lam"]
    n_ops = max(1, len({o for o in ops}))
    mem = {}
    for o in ops:
        mem[o] = mem.get(o, 0) + 1

    def row(prev_k, prev_o):
        kr = prior["kb"].get(prev_k, {})
        orow = prior["ob"].get(prev_o, {})
        nk, no = sum(kr.values()), sum(orow.values())
        out = []
        for k, o in zip(ks, ops):
            pk = (kr.get(k, 0.0) + a) / (nk + a * T)
            members = max(1, mem[o])
            po = (orow.get(o, 0.0) + a) / (no + a * n_ops) / members
            out.append(-math.log(lam * pk + (1 - lam) * po))
        return out
    return {"cost": K.Lazy(T + 1, lambda r: row(K.START, K.START) if r == 0 else row(ks[r - 1], ops[r - 1]))}


def cost_matrix_fast(prior, tools):
    """Wave 40 cost matrices: fixed_repr (above), the learned mixture via the exact O(T) rows, and the hierarchical prior with
    its global component via the exact O(T) rows. Every number equals w39_learn.cost_matrix's (or fixed_repr's definition)."""
    if prior and prior.get("kind") == "learned" and "kb" in prior:
        return _learned(prior, tools)
    if prior and prior.get("kind") == "hier" and prior.get("local") is not None:
        g = _learned(prior["global"], tools)["cost"]
        loc, s = prior["local"], prior["shrink"]
        ks = [K.akey(t) for t in tools]

        def row(r):
            prev = K.START if r == 0 else ks[r - 1]
            cnt = loc["kb"].get(prev, {})
            n = sum(cnt.values())
            return [-math.log((cnt.get(k, 0.0) + s * math.exp(-gc)) / (n + s)) for k, gc in zip(ks, g[r])]
        return {"cost": K.Lazy(len(tools) + 1, row)}
    if prior and prior.get("kind") == "hier":
        return _learned(prior["global"], tools)
    return cost_matrix(prior, tools)
