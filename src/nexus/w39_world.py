"""Wave 39 cheap adaptation for the noisy / changing world (NOT LOCKED): N1-lite, a reduced-cost BOCPD over the SwitchGrid goal
model (same likelihood, hazard and greedy planner as wave36_world.BOCPD; N1 itself is unchanged).

Exact reductions (no approximation):
  * uninformative steps: when the likelihood is identical for every goal (no reward and the believed landing cell is no goal),
    a BOCPD step leaves every run's goal posterior unchanged and only ages run lengths by the hazard; s such steps are applied
    lazily at the next informative step in closed form (surviving runs x (1-H)^s; new runs born in the stretch all carry the
    uniform prior, so they are ONE run of mass 1 - (1-H)^s). The predictive used for acting is
    (1-H)^s * predictive_at_last_flush + (1 - (1-H)^s) * uniform.
  * merging: runs with identical goal posteriors are one run (constant hazard: run length does not affect the future).
Approximations (tunable, reported as a frontier):
  * prune: drop runs with mass < eps, keep at most rmax runs (renormalised);
  * surprise gate theta: on an informative step whose reward prediction error |rew - p| < theta, skip change-point branching
    (Bayes-update each run's posterior; no new run). theta = 0 -> every informative step is a full BOCPD step.
Pure Python (4-element beliefs); compute is the agent's own OS retired instructions, as for every other agent."""
from __future__ import annotations

import random

from nexus import wave36_world as Wd

U = (0.25, 0.25, 0.25, 0.25)


class N1Lite:
    H = 1 / 100

    def __init__(self, rng, eps=1e-4, rmax=16, theta=0.0):
        self.rng, self.eps, self.rmax, self.theta = rng, eps, rmax, theta
        self.runs = [[1.0, list(U)]]
        self.s = 0
        self.pred0 = list(U)
        self.p = 0.04
        self.full_steps = self.gated_steps = self.lazy_steps = 0

    def _belief(self):
        a = (1 - self.H) ** self.s
        return [a * b + (1 - a) * 0.25 for b in self.pred0]

    def act(self, o):
        b = self._belief()
        g = max(range(4), key=lambda k: (b[k], -k))
        goal = Wd.GOALS[g]
        a = Wd.toward(o, goal) if o != goal else self.rng.randrange(4)
        land = Wd.nxt(o, a)
        self.p = sum(b[k] * (0.85 if land == Wd.GOALS[k] else 0.02) for k in range(4))
        return a, self.p

    def _flush(self):
        if self.s:
            a = (1 - self.H) ** self.s
            for r in self.runs:
                r[0] *= a
            self.runs.append([1 - a, list(U)])
            self.s = 0

    def _compact(self):
        merged = {}
        for w, g in self.runs:
            k = tuple(round(x, 12) for x in g)
            if k in merged:
                merged[k][0] += w
            else:
                merged[k] = [w, g]
        runs = sorted(merged.values(), key=lambda r: -r[0])
        runs = [r for r in runs if r[0] >= self.eps][: self.rmax] or runs[:1]
        z = sum(r[0] for r in runs)
        self.runs = [[w / z, g] for w, g in runs]
        pred = [0.0] * 4
        for w, g in self.runs:
            for k in range(4):
                pred[k] += w * g[k]
        zz = sum(pred)
        self.pred0 = [x / zz for x in pred]

    def learn(self, o, a, rew, o2):
        land = Wd.nxt(o, a)
        lik = [Wd._lik(rew, land, g) for g in range(4)]
        if lik[0] == lik[1] == lik[2] == lik[3]:
            self.s += 1; self.lazy_steps += 1
            return
        self._flush()
        if self.theta > 0 and abs(rew - self.p) < self.theta:
            self.gated_steps += 1
            new = []
            for w, g in self.runs:
                post = [g[k] * lik[k] for k in range(4)]
                pr = sum(post)
                new.append([w * pr, [x / pr for x in post]])
            self.runs = new
        else:
            self.full_steps += 1
            grown, cp = [], 0.0
            for w, g in self.runs:
                post = [g[k] * lik[k] for k in range(4)]
                pr = sum(post)
                grown.append([w * pr * (1 - self.H), [x / pr for x in post]])
                cp += w * pr * self.H
            pl = sum(0.25 * l for l in lik)
            self.runs = [[cp, [0.25 * l / pl for l in lik]]] + grown
        self._compact()


VARIANTS = {"N1-merge-exact": dict(eps=0.0, rmax=300, theta=0.0), "N1-lite-prune": dict(eps=1e-4, rmax=16, theta=0.0),
            "N1-lite-prune8": dict(eps=1e-3, rmax=8, theta=0.0), "N1-lite-gate0.3": dict(eps=1e-4, rmax=16, theta=0.3),
            "N1-lite-gate0.6": dict(eps=1e-4, rmax=16, theta=0.6)}


def make(name, seed):
    if name in VARIANTS:
        return N1Lite(random.Random(f"w36-agent:{name}:{seed}"), **VARIANTS[name])
    return Wd.make(name, seed)
