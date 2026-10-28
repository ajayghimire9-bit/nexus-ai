"""Pillar 5 - the editable META-LEVEL improver M that proposes and selects edits to the base learner L (NOT LOCKED).

M is a small program held as data (so a meta-improver can edit it, OOPS / HyperAgents style):
  edit_w     probability weights over L's variation operators (evolvable_learner.EDITS)
  k          proposals per round;  n_eval  tasks per paired evaluation;  sigma  constant step size
  accept     'greedy' | 'threshold' (needs > tau) | 'anneal' (Metropolis with temperature T0 -> 0) | 'random' (coin flip)
  select     'random' | 'failed_first' (tasks the incumbent failed last time are re-sampled first)
  credit     online operator credit: an accepted edit kind's weight is multiplied by (1 + credit)
  paired     re-evaluate the incumbent on the same task sample as the proposals (else reuse its last score)
improve(M, L0, pool, B) runs M for B CPU seconds (every evaluation counted) and returns the final incumbent L.
Arms (the Pillar 5 comparison): M0 (hand-written), Scalar_Tuning (M0 restricted to scalar edits), Random_Modification
(M0's proposals accepted by coin flip), M_evolved (M0 edited by meta_evolve on meta-training families only).
The evaluator (score callable), checker kernels and budget meter are outside both L and M."""
from __future__ import annotations

import copy
import math
import random
import time

from nexus import evolvable_learner as EL

M0 = dict(edit_w={e: 1.0 for e in EL.EDITS}, k=1, n_eval=6, sigma=0.3, accept="greedy", tau=0.0, T0=0.5,
          select="random", credit=0.0, paired=True)


def scalar_tuning():
    m = copy.deepcopy(M0)
    m["edit_w"] = {e: (1.0 if e in EL.SCALAR_EDITS else 0.0) for e in EL.EDITS}
    return m


def random_modification():
    m = copy.deepcopy(M0)
    m["accept"] = "random"
    return m


def _pick_edit(w, rnd):
    tot = sum(w.values())
    x = rnd.uniform(0, tot)
    for e, v in w.items():
        x -= v
        if x <= 0 and v > 0:
            return e
    return max(w, key=w.get)


def improve(M, L0, pool, budget_s, seed, score_fn=EL.score):
    """Run improver M on base learner L0 with training-task pool `pool` for budget_s CPU seconds."""
    rnd = random.Random(seed)
    w = dict(M["edit_w"])
    L, t0 = copy.deepcopy(L0), time.process_time()
    failed = []
    last = None
    log = []
    while time.process_time() - t0 < budget_s:
        n = min(M["n_eval"], len(pool))
        if M["select"] == "failed_first" and failed:
            tasks = failed[:n] + rnd.sample([t for t in pool if t not in failed], max(0, n - len(failed[:n])))
        else:
            tasks = rnd.sample(pool, n)
        if M["paired"] or last is None:
            base, _, _ = score_fn(L, tasks)
        else:
            base = last
        props = []
        for _ in range(M["k"]):
            kind = _pick_edit(w, rnd)
            cand, desc = EL.mutate(L, kind, rnd, M["sigma"])
            if cand is None:
                continue
            s, _, _ = score_fn(cand, tasks)
            props.append((s, kind, desc, cand))
            if time.process_time() - t0 >= budget_s:
                break
        if not props:
            continue
        s, kind, desc, cand = max(props, key=lambda p: p[0])
        frac = min(1.0, (time.process_time() - t0) / budget_s)
        if M["accept"] == "greedy":
            take = s > base
        elif M["accept"] == "threshold":
            take = s > base + M["tau"]
        elif M["accept"] == "anneal":
            T = max(1e-3, M["T0"] * (1 - frac))
            take = s > base or rnd.random() < math.exp((s - base) / T)
        else:
            take = rnd.random() < 0.5
        if take:
            L, last = cand, s
            w[kind] *= 1 + M["credit"]
        else:
            last = base
        if M["select"] == "failed_first":
            failed = [t for t in tasks if not _solved_quick(L, t)] if take else failed
        log.append(dict(edit=desc, kind=kind, base=round(base, 3), cand=round(s, 3), accepted=take,
                        cpu=round(time.process_time() - t0, 2)))
    return L, log, time.process_time() - t0


def _solved_quick(L, t):
    from nexus import u5_construct as K
    cfg, lib = EL.to_config(L)
    node, _, _ = K.solve(t.train, t.y_train, cfg, lib, min(0.5, L["per_task_s"]))
    return node is not None


# ------------------------------------------------------------------------------------------------ editing M itself
def mutate_M(M, rnd):
    M = copy.deepcopy(M)
    kind = rnd.choice(["edit_w", "edit_w", "k", "n_eval", "accept", "tau", "T0", "select", "sigma", "credit", "paired"])
    if kind == "edit_w":
        e = rnd.choice(EL.EDITS)
        M["edit_w"][e] = round(min(8.0, max(0.0, (M["edit_w"][e] or 0.25) * rnd.choice([0.0, 0.5, 2.0]))), 4)
        if sum(M["edit_w"].values()) == 0:
            M["edit_w"][e] = 1.0
    elif kind == "k":
        M["k"] = max(1, min(4, M["k"] + rnd.choice([-1, 1])))
    elif kind == "n_eval":
        M["n_eval"] = max(3, min(12, M["n_eval"] + rnd.choice([-2, 2])))
    elif kind == "accept":
        M["accept"] = rnd.choice(["greedy", "threshold", "anneal"])
    elif kind == "tau":
        M["tau"] = round(max(0.0, M["tau"] + rnd.choice([-0.25, 0.25])), 3)
    elif kind == "T0":
        M["T0"] = round(max(0.05, M["T0"] * rnd.choice([0.5, 2.0])), 3)
    elif kind == "select":
        M["select"] = "failed_first" if M["select"] == "random" else "random"
    elif kind == "sigma":
        M["sigma"] = round(max(0.05, min(1.5, M["sigma"] * rnd.choice([0.67, 1.5]))), 3)
    elif kind == "credit":
        M["credit"] = round(max(0.0, min(1.0, M["credit"] + rnd.choice([-0.25, 0.25]))), 3)
    elif kind == "paired":
        M["paired"] = not M["paired"]
    return M, kind


def meta_evolve(L0, meta_pool, meta_val, b_meta, gens, lam, seed, score_fn=EL.score, log_fn=None):
    """(1 + lambda) evolution of M on META-TRAINING families only. fitness(M) = score(M(L0) on meta_val) - score(L0 on
    meta_val). Returns (M_best, history, cpu_s)."""
    rnd = random.Random(seed)
    t0 = time.process_time()
    base_val, _, _ = score_fn(L0, meta_val)

    def fitness(M, s):
        L, _, _ = improve(M, L0, meta_pool, b_meta, s, score_fn)
        v, solved, cpu = score_fn(L, meta_val)
        return v - base_val, solved

    best = copy.deepcopy(M0)
    best_fit, best_solved = fitness(best, rnd.randrange(10 ** 6))
    hist = [dict(gen=0, M="M0", fitness=round(best_fit, 3), solved=best_solved)]
    for g in range(1, gens + 1):
        kids = []
        for _ in range(lam):
            child, kind = mutate_M(best, rnd)
            for _ in range(rnd.randint(0, 2)):
                child, k2 = mutate_M(child, rnd)
                kind += "+" + k2
            f, sv = fitness(child, rnd.randrange(10 ** 6))
            kids.append((f, sv, kind, child))
            hist.append(dict(gen=g, M=kind, fitness=round(f, 3), solved=sv))
            if log_fn:
                log_fn(hist[-1])
        f, sv, kind, child = max(kids, key=lambda x: x[0])
        if f > best_fit:
            best, best_fit, best_solved = child, f, sv
    return best, hist, time.process_time() - t0
