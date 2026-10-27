"""Wave 39 learned knowledge (SOLVER SIDE; NOT LOCKED). Extends w38_learn without changing it.
  fixed5 : the hand-designed category (d) prior, extended to the v5 tools (toks is an encoder; fn, first, dflt aggregate).
           Same rules as w38 'fixed'. Not learned.
  hier   : hierarchical prior = global cross-domain prior (w38 'learned' mixture over ALL certified programs) + a regime-specific
           residual: p(k | prev) = (n_regime(prev, k) + s * p_global(k | prev)) / (n_regime(prev) + s) (Dirichlet shrinkage toward
           the global prior, strength s). A new regime starts from the global prior (keeps positive cross-phase transfer); a
           returning regime's own counts dominate once it has data (retention).
Everything else delegates to w38_learn.cost_matrix (uniform / learned / repr / placebo / fixed)."""
from __future__ import annotations

import math

from nexus import w38_learn as K

ENCODERS5 = K.ENCODERS | {"toks"}
AGGREGATES5 = K.AGGREGATES | {"fn", "first", "dflt"}


def fit_hier(programs, regimes, alpha=1.0, lam=0.8, shrink=4.0):
    """programs: all certified programs so far; regimes: the regime id of each; the LAST regime id is the current regime."""
    if not programs:
        return None
    cur = regimes[-1] if regimes else None
    local = [p for p, r in zip(programs, regimes) if r == cur]
    return {"kind": "hier", "global": K.fit(programs, alpha, lam), "local": K.fit(local, alpha, lam) if local else None,
            "shrink": shrink, "n": len(programs)}


def cost_matrix(prior, tools):
    if prior is None:
        return K.cost_matrix(None, tools)
    if prior.get("kind") == "fixed5":
        ops = [t["op"] for t in tools]
        T = len(tools)

        def c1(prev_op, op):
            if prev_op == K.START:
                return 0.5 if op in ENCODERS5 else 2.0
            if op in AGGREGATES5:
                return 0.8
            return 1.0 if op not in ENCODERS5 else 1.6
        return {"cost": K.Lazy(T + 1, lambda r: [c1(K.START if r == 0 else ops[r - 1], o) for o in ops])}
    if prior.get("kind") == "hier":
        g = K.cost_matrix(prior["global"], tools)["cost"]
        loc, s = prior["local"], prior["shrink"]
        if loc is None:
            return {"cost": g}
        ks = [K.akey(t) for t in tools]

        def row(r):
            prev = K.START if r == 0 else ks[r - 1]
            cnt = loc["kb"].get(prev, {})
            n = sum(cnt.values())
            grow = g[r]
            return [-math.log((cnt.get(k, 0.0) + s * math.exp(-gc)) / (n + s)) for k, gc in zip(ks, grow)]
        return {"cost": K.Lazy(len(tools) + 1, row)}
    return K.cost_matrix(prior, tools)
