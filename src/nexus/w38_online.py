"""Wave 38 online learning procedure (SOLVER SIDE; NOT LOCKED) for experiments 4, 5, 6: an empty-library online learner
over Wave 38 program streams, parameterised by a small genome (meta-learned / evolved; the checker, meter and scope fixed).

genome: alpha, lam (prior smoothing / mixture), refit (certified tasks between refits), sharpen (weight on certified
traces), use_after (warm-up before the prior is used), decay (recency weight per certified task), gate ('none' | 'surprise':
N1-style BOCPD over the surprise of each certified solution under the current prior; a declared change down-weights
pre-change traces by 0.1).
BASELINE_80F9CC2 = the Wave 36 frozen learner's settings mapped to this language (alpha 1, lam 0.8, refit 8, sharpen 100).
Every decision uses deterministic quantities (no wall-clock)."""
from __future__ import annotations

import math

from nexus import w38_learn as K

GENES = {"alpha": (0.25, 0.5, 1.0, 2.0), "lam": (0.2, 0.5, 0.8, 1.0), "refit": (1, 2, 4, 8), "sharpen": (1, 10, 100),
         "use_after": (1, 3, 6), "decay": (1.0, 0.9, 0.7), "gate": ("none", "surprise", "regime")}
BASELINE_80F9CC2 = {"alpha": 1.0, "lam": 0.8, "refit": 8, "sharpen": 100, "use_after": 1, "decay": 1.0, "gate": "none"}
H, RMAX = 1 / 30, 120


def validate(g):
    if set(g) != set(GENES) or any(g[k] not in GENES[k] for k in GENES):
        raise ValueError("genome outside the editable scope")
    return g


def signature(view):
    """Observable task signature: the INPUT type shape of the first public pair (no domain label). (Dev iteration: an
    input+output signature split every mechanism into its own tiny, never-refit context.)"""
    from nexus import wave33_prior as P0
    x, y = view["public"][0]
    def ty(v):
        if isinstance(v, dict):
            return "dict:" + ",".join(sorted(v))[:24]
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return "list:dict:" + ",".join(sorted(v[0]))[:24]
        return P0.vtype(v)
    return ty(x)


class RegimeLearner:
    """gate='regime' (Stage 2 dev iteration after the inert surprise gate): N1-style BOCPD over the observable input-type
    signature; a declared change opens a NEW context instead of overwriting; each task uses the prior of the stored context
    whose signature counts best match (so returning regimes reuse their own knowledge and new regimes start clean)."""

    def __init__(self, g):
        self.g = validate(dict(g))
        self.ctx = []                     # list of dict(sig={sig: n}, learner=Learner)
        self.cur = None
        self.runs = [(1.0, {})]
        self.declared = 0
        self.vocab = set()

    def _match(self, sig):
        best, bs = None, 0.0
        for i, c in enumerate(self.ctx):
            n = sum(c["sig"].values())
            sc = c["sig"].get(sig, 0) / n if n else 0.0
            if sc > bs:
                best, bs = i, sc
        return best if bs >= 0.3 else None

    def current_prior(self, view=None):
        if view is None or not self.ctx:
            return None
        i = self._match(signature(view))
        return self.ctx[i]["learner"].current_prior() if i is not None else None

    def _bocpd(self, sig):
        self.vocab.add(sig)
        K = len(self.vocab) + 1
        grown, cp = [], 0.0
        for w, cnt in self.runs:
            n = sum(cnt.values())
            pred = (cnt.get(sig, 0) + 0.5) / (n + 0.5 * K)
            c2 = dict(cnt); c2[sig] = c2.get(sig, 0) + 1
            grown.append((w * pred * (1 - H), c2)); cp += w * pred * H
        new = [(cp, {sig: 1})] + grown
        z = sum(w for w, _ in new)
        self.runs = [(w / z, c) for w, c in new[:RMAX]]
        return sum(w for w, _ in self.runs[:3])

    def update(self, prog, view):
        sig = signature(view)
        p_short = self._bocpd(sig)
        i = self._match(sig)
        if i is None or (p_short > 0.5 and (self.cur is None or i != self.cur)):
            if i is None:
                self.ctx.append(dict(sig={}, learner=Learner(dict(self.g, gate="none"))))
                i = len(self.ctx) - 1
            self.declared += 1
        self.cur = i
        c = self.ctx[i]
        c["sig"][sig] = c["sig"].get(sig, 0) + 1
        return c["learner"].update(prog)


class Learner:
    def __init__(self, g):
        self.g = validate(dict(g))
        self.progs, self.w = [], []
        self.prior, self.since = None, 0
        self.runs = [(1.0, [0, 0, 0])]
        self.declared = 0

    def current_prior(self):
        return self.prior if (self.prior is not None and len(self.progs) >= self.g["use_after"]) else None

    def _surprise(self, prog, tools_prior):
        if tools_prior is None:
            return 1
        c = K.cost_matrix(tools_prior, prog)["cost"]
        s = sum(c[i][i] for i in range(len(prog))) / max(1, len(prog))    # cost of each step given its predecessor
        return 0 if s < 2.0 else (1 if s < 4.0 else 2)

    def _bocpd(self, b):
        grown, cp = [], 0.0
        for w, cnt in self.runs:
            pred = (cnt[b] + 0.5) / (sum(cnt) + 1.5)
            c2 = list(cnt); c2[b] += 1
            grown.append((w * pred * (1 - H), c2)); cp += w * pred * H
        new = [(cp, [1 if i == b else 0 for i in range(3)])] + grown
        z = sum(w for w, _ in new)
        self.runs = [(w / z, c) for w, c in new[:RMAX]]
        return sum(w for w, _ in self.runs[:3])

    def update(self, prog):
        """Called with each certified solution; returns True if the prior was refit."""
        if self.g["gate"] == "surprise":
            if self._bocpd(self._surprise(prog, self.prior)) > 0.5 and len(self.progs) > 3:
                self.w = [x * 0.1 for x in self.w]
                self.declared += 1
        self.w = [x * self.g["decay"] for x in self.w]
        self.progs.append(prog); self.w.append(1.0)
        self.since += 1
        if self.since >= self.g["refit"]:
            self.prior = K.fit(self.progs, self.g["alpha"], self.g["lam"], [x * self.g["sharpen"] for x in self.w])
            self.since = 0
            return True
        return False
