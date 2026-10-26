"""E1 (NOT LOCKED): variance-stabilised Bayesian payoff controller over learning / refit actions. Solver side (child).

The controller is written by hand (category (d)); it wraps the existing online learner interpreter (wave34_learner).
  * Two actions per task: plain primitive search ("b") or prior-guided search ("p", only once a prior exists).
  * Normal-Inverse-Gamma posterior on log(search cost units) per action (conjugate; prior mean m0 = 0 offset from the first
    plain observations, kappa0 = 1, alpha0 = 2, beta0 = 1): shrinkage toward the pooled mean when data are scarce.
  * Thompson sampling chooses the action; the refit cost is charged in full to the "p" action's observation on the task
    after the refit.
  * Refit (every >= 4 certified tasks) only while P(mean_p < mean_b) estimated from the posterior means exceeds 1/2, or
    while "p" has < 3 observations (probation). First fit after 3 certified tasks.
All decisions use the deterministic op-unit counter (wave34_learner.UNITS), so runs replay exactly."""
from __future__ import annotations

import copy
import math
import random

from nexus import wave34_learner as L

ST = {}


def reset():
    L.reset()
    ST.clear()
    ST.update(obs={"b": [], "p": []}, pending_refit=0.0, n=0)


def _post(xs, m0):
    k0, a0, b0 = 1.0, 2.0, 1.0
    n = len(xs)
    if n == 0:
        return m0, k0, a0, b0
    mean = sum(xs) / n
    ss = sum((x - mean) ** 2 for x in xs)
    kn = k0 + n
    mn = (k0 * m0 + n * mean) / kn
    an = a0 + n / 2
    bn = b0 + 0.5 * ss + k0 * n * (mean - m0) ** 2 / (2 * kn)
    return mn, kn, an, bn


def _sample(xs, m0, rng):
    mn, kn, an, bn = _post(xs, m0)
    var = bn / max(1e-9, rng.gammavariate(an, 1.0))           # sigma^2 ~ InvGamma(an, bn)
    return rng.gauss(mn, math.sqrt(var / kn))


def _m0():
    allx = ST["obs"]["b"] + ST["obs"]["p"]
    return sum(allx) / len(allx) if allx else 0.0


def program(use_p, refit):
    p = copy.deepcopy(L.SEED_PRIOR)
    p["use"]["p"] = ["true"] if use_p else ["false"]
    p["extract"]["p"] = ["true"] if refit else ["false"]
    return p


def choose(seed):
    rng = random.Random(f"w36-e1:{seed}:{ST['n']}")
    if L.ST["prior"] is None:
        return "b"
    if len(ST["obs"]["p"]) < 3:
        return "p"
    m0 = _m0()
    return "p" if _sample(ST["obs"]["p"], m0, rng) < _sample(ST["obs"]["b"], m0, rng) else "b"


def solve(chan, view, seed):
    a = choose(seed)
    ST["last"] = a
    return L.solve(chan, view, program(a == "p", False), seed)


def update(candidate, view, certified, rec):
    a = ST.get("last", "b")
    ST["n"] += 1
    spent = sum(ph[1] for ph in (rec or {}).get("phases", [])) if rec else 0
    if a == "p":
        spent += ST["pending_refit"]
        ST["pending_refit"] = 0.0
    if rec:
        ST["obs"][a].append(math.log(1.0 + spent))
    mb = _post(ST["obs"]["b"], _m0())[0] if ST["obs"]["b"] else float("inf")
    mp = _post(ST["obs"]["p"], _m0())[0] if ST["obs"]["p"] else -float("inf")
    want = (L.ST["prior"] is None and L.ST["n_cert"] + int(certified) >= 3) or len(ST["obs"]["p"]) < 3 or mp < mb
    u0 = L.UNITS[0]
    out = L.update(program(False, want), candidate, view, certified, rec)
    ST["pending_refit"] += L.UNITS[0] - u0 if out.get("refit") else 0.0
    out.update(action=a, n_b=len(ST["obs"]["b"]), n_p=len(ST["obs"]["p"]))
    return out
