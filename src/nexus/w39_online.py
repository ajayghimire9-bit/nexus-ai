"""Wave 39 hierarchical stream memory (SOLVER SIDE; NOT LOCKED) for the continual program stream (Step 5) and the external
online arm (Step 6). Regime identification is Wave 38's (N1-style BOCPD over the observable input-type signature; contexts are
matched by signature counts; w38_online.RegimeLearner). The prior differs: instead of a separate learner per context (which
starts every new regime from scratch and so blocks positive transfer), HierLearner keeps ONE global cross-domain prior over all
certified programs plus a regime-specific residual (w39_learn 'hier': Dirichlet shrinkage of the matched context's own counts
toward the global prior, strength `shrink` pseudo-programs). Refit schedule and smoothing follow the genome (BASELINE_80F9CC2)."""
from __future__ import annotations

from nexus import w38_learn as K
from nexus import w38_online as O


class HierLearner(O.RegimeLearner):
    def __init__(self, g, shrink=4.0):
        super().__init__(dict(g, gate="regime"))
        self.shrink = shrink
        self.progs, self.cid, self.since = [], [], 0
        self.glob, self.loc = None, {}

    def current_prior(self, view=None):
        if self.glob is None or len(self.progs) < self.g["use_after"]:
            return None
        i = self._match(O.signature(view)) if view is not None and self.ctx else None
        return {"kind": "hier", "global": self.glob, "local": self.loc.get(i), "shrink": self.shrink}

    def update(self, prog, view):
        sig = O.signature(view)
        p_short = self._bocpd(sig)
        i = self._match(sig)
        if i is None or (p_short > 0.5 and (self.cur is None or i != self.cur)):
            if i is None:
                self.ctx.append(dict(sig={}))
                i = len(self.ctx) - 1
            self.declared += 1
        self.cur = i
        self.ctx[i]["sig"][sig] = self.ctx[i]["sig"].get(sig, 0) + 1
        self.progs.append(prog); self.cid.append(i)
        self.since += 1
        if self.since >= self.g["refit"]:
            a, lam, sh = self.g["alpha"], self.g["lam"], self.g["sharpen"]
            self.glob = K.fit(self.progs, a, lam, [sh] * len(self.progs))
            self.loc = {c: K.fit([p for p, q in zip(self.progs, self.cid) if q == c], a, lam)
                        for c in set(self.cid)}
            self.since = 0
            return True
        return False
