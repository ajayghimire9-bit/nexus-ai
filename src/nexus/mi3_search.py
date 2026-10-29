"""MI-3 shared evaluation engine for Stages 2-4 (NOT LOCKED; new versioned module).

Every evaluation = mi3_accept.full_space3 (the x7 learner with the arm's register-hypothesis procedure and the frozen MI-3
acceptance check) on a fresh Episode3 per episode (task memory reset), per-episode CPU cap CAP_S, scored by the unchanged
evaluator (mi_learner.score: exact on the held-out stream; silent = accepted but not exact). No fast path in MI-3 (it is identical
for every arm; dropping it removes shared cost and makes known-task retention depend on the arm's own procedure - disclosed).

Staged evaluation (Stage 2 calibrates, Stage 3 uses the frozen schedule):
  screen   the first 2 episodes of each family of the pool (6 episodes)
  survive  screen exact >= 1  or  screen mean partial (fraction of register searches solved; learner-side) >= TAU
  full     a survivor is evaluated on the remaining pool episodes; its fitness is the full-pool fitness
  rejection audit  10 % of cumulative screening CPU is reserved: whenever audit_spent + 3 x (the candidate's screening CPU) <=
           0.10 x screen_spent, one uniformly drawn, not yet audited rejected candidate is fully evaluated (seeded RNG); an audited
           candidate is ranked by its full fitness like a survivor. Zero screening solves is therefore never a permanent rejection.
Fitness (frozen, MI-2): [exact, mean partial, -CPU s]; a fully evaluated candidate always ranks above a screened-out one."""
from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path

from nexus import mi_learner as ML
from nexus import mi_lpl as LP
from nexus import mi2_learner as M2
from nexus import mi3_accept as A
from nexus import t7_repair as TR

ROOT = Path(__file__).resolve().parents[2]
CAP_S = 1.0                     # artifacts/mi3_dev/capcal.json (frozen rule, MI-2 development solve times)
AUDIT_FRAC = 0.10
FAMS_U = ("MUL", "ADDC", "SUBH")
PROBE_CTX = [{}, {"obs": [2.0, 4.0, 8.0, 3.0, 6.0], "n_trans": 3}, {"obs": [1.5, 4.5, 7.25, 10.0, 12.5, 3.0], "n_trans": 5}]


def fixed_domain(exprs):
    out = [LP.ACC] + [g for g in exprs if g != LP.ACC]

    def f(ctx):
        return list(out), dict(size=len(out))
    return f


def domain_of(spec):
    """spec kinds: baseline | a5 | a6 | lpl(prog) | params(size_bound, max_lit, max_s) | file(path of a frozen winner) | fixed."""
    k = spec["kind"]
    if k == "baseline":
        return ML.baseline_domain, 60.0
    if k == "a5":
        return ML.lpl_domain(M2.A5_PROG), 60.0
    if k == "a6":
        return M2.a6_domain(), 60.0
    if k == "lpl":
        return ML.lpl_domain(spec["prog"]), 60.0
    if k == "params":
        return M2.params_domain(spec["size_bound"], spec["max_lit"]), spec.get("max_s", 60.0)
    if k == "fixed":
        return fixed_domain([tuple_expr(x) for x in spec["exprs"]]), 60.0
    if k == "file":
        w = json.loads((ROOT / spec["file"]).read_text())["winner"]
        return domain_of(dict(w, kind="params") if w["kind"] == "params" else dict(kind="lpl", prog=w["prog"]))
    raise ValueError(k)


def tuple_expr(x):
    return tuple(tuple_expr(y) if isinstance(y, list) else y for y in x) if isinstance(x, (list, tuple)) else x


def space_signature(spec):
    """Behavioural identity of a procedure: its ordered hypothesis space (expression signatures) on fixed probe contexts."""
    dom, _ = domain_of(spec)
    parts = []
    for ctx in PROBE_CTX:
        try:
            lst, _ = dom(dict(ctx))
            parts.append([LP._sig(g) for g in lst])
        except Exception as e:                                       # noqa: BLE001
            parts.append(["invalid", repr(e)[:80]])
    h = hashlib.sha1(json.dumps(parts, default=str).encode()).hexdigest()[:16]
    return h, [len(p) for p in parts]


def eval_one(dom, max_s, seed, family, cap_s=CAP_S):
    c0 = time.process_time()
    ep = A.Episode3(seed, family)
    out, s = A.full_space3(ep, dom, ep.seed, max_s=max_s, cap_s=cap_s)
    sc = ML.score(ep, out)
    return dict(seed=seed, family=family, exact=sc["exact"], silent=sc["silent"], accepted=sc["accepted"], outcome=s["outcome"],
                learner_cpu_s=s["cpu_s"], cpu_s=round(time.process_time() - c0, 4), queries=s["queries"],
                explained=round(s["explained"], 3), updates=ML.updates_src(out))


def fitness(rows):
    if not rows:
        return [0, 0.0, 0.0]
    return [sum(r["exact"] for r in rows), round(sum(r["explained"] for r in rows) / len(rows), 4),
            -round(sum(r["cpu_s"] for r in rows), 3)]


def screen_split(pool):
    """pool = list of (seed, family) in pool order; screen = first 2 of each family."""
    scr, rest, cnt = [], [], {}
    for sf in pool:
        cnt[sf[1]] = cnt.get(sf[1], 0) + 1
        (scr if cnt[sf[1]] <= 2 else rest).append(sf)
    return scr, rest


def survives(screen_rows, tau):
    f = fitness(screen_rows)
    return f[0] >= 1 or f[1] >= tau


def rank_key(c):
    """Higher is better: fully evaluated (survivor or audited) above screened-out; then fitness."""
    return (1 if c.get("full_fitness") is not None else 0, c.get("full_fitness") or c.get("screen_fitness"))


def pool_of(split, fams, per):
    from nexus import mi3_seeds  # noqa: F401
    from nexus import seed_registry as R
    seeds = list(R.REGISTRY[("mi3", split)])
    out = []
    for f in fams:
        out += [(seeds[i], f) for i in range(per)]
    # interleave so that the screen (first 2 per family) is well defined independent of order
    return out


GRAMMAR = list(TR.GRAMMAR5)
