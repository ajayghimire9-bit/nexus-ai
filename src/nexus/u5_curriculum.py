"""Pillar 4 - practice between projects (NOT LOCKED): failure-boundary curriculum vs random / fixed / none.

Learner state = (construction config: operator costs + affinity weights, library). A WAKE pass solves tasks with the
current learner and keeps its own experience: solved programs, affinity samples from its solved searches, the weakness
record (failed tasks, slow solves, and the highest-affinity partial programs of every failed search). UPDATE refits costs
and affinity weights on all experience and re-admits library functions (utility admission, Pillar 3) - identical for every
arm. ACCEPTANCE (PowerPlay zero forgetting, identical for every arm): the updated learner must still solve every src task
the old learner solved, else the update is rejected.

Practice generators (equal CPU budget per arm; every generated task is CHECKABLE: its oracle is the generated program, and
a task is kept only if that program evaluates without exceptions to a non-constant output on every input):
  boundary   (PowerPlay / wake-sleep dreaming) inputs taken from tasks NEXUS failed or solved slowly; programs built from
             that failed search's own near-miss partial programs plus primitive operators, sized just beyond the largest
             program NEXUS currently solves; kept only if the current learner FAILS it on a quick check (it is at the
             boundary), then practised with the full per-task budget
  random     inputs from random src tasks, sizes uniform 3..21, uniform operators, no boundary filter
  fixed      inputs from src tasks in a fixed order, sizes on a preset schedule 5, 7, ..., 17, uniform operators
  none       no practice (the src wake only)"""
from __future__ import annotations

import math
import random
import time

from nexus import u5_construct as K
from nexus import u5_library as LB
from nexus.oop_synthesizer import ERR, ev, size

NUM_OPS = ("+", "-", "*", "/")


class Experience:
    def __init__(self):
        self.solutions, self.samples, self.solved_ids = [], [], set()
        self.weak, self.near = [], {}
        self.max_size = 0

    def add(self, tid, node, search, cpu, budget, envs):
        if node is not None:
            self.solutions.append(node)
            self.samples += K.affinity_samples(search, node, max_neg=800)
            self.solved_ids.add(tid)
            self.max_size = max(self.max_size, size(node))
            if cpu > 0.5 * budget:
                self.weak.append((tid, envs))
        else:
            self.weak.append((tid, envs))
            self.near[tid] = _near_misses(search)


def _near_misses(s, k=8):
    sc = []
    for e in s.sig.values():
        if any(isinstance(v, (dict, list, set)) for v in e[1]) or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in e[1]):
            continue
        f = s.tg.features(e[1])
        sc.append((f[2] + f[3] + f[5] + f[6], e[0]))
    sc.sort(key=lambda x: -x[0])
    return [n for _, n in sc[:k]]


def wake(tasks, cfg, lib, budget_s, exp=None):
    exp = exp or Experience()
    cpu = 0.0
    for t in tasks:
        node, st, s = K.solve(t.train, t.y_train, cfg, lib, budget_s)
        exp.add(t.tid, node, s, st["cpu_s"], budget_s, t.train)
        cpu += st["cpu_s"]
    return exp, cpu


def update(cfg, exp):
    new = dict(cfg)
    new["op_cost"] = K.count_costs(exp.solutions)
    w, b = K.fit_affinity_xy(exp.samples)
    new["weights"], new["bias"] = w, b
    return new


# ------------------------------------------------------------------------------------------------ generators
def _leaves(envs):
    e = envs[0]
    out = []
    r, t = e.get("r", {}), e.get("t", {})
    for k, v in r.items():
        if all(isinstance(x["r"].get(k), (int, float)) and not isinstance(x["r"].get(k), bool) for x in envs):
            out.append(("u", "float", ("b", "get", ("var", "r"), ("const", k))))
    for k, v in t.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(("b", "get", ("var", "t"), ("const", k)))
        if isinstance(v, dict):
            for rk in r:
                if all(x["r"].get(rk) in v for x in envs):
                    out.append(("b", "get", ("b", "get", ("var", "t"), ("const", k)), ("b", "get", ("var", "r"), ("const", rk))))
    return out


def _grow(target, leaves, blocks, rnd, ops):
    if target <= 5 or rnd.random() < 0.15:
        pool = [b for b in blocks if size(b) <= target] or leaves
        return rnd.choice(pool)
    op = rnd.choice(ops)
    left = rnd.randint(4, max(4, target - 5))
    return ("b", op, _grow(left, leaves, blocks, rnd, ops), _grow(target - 1 - left, leaves, blocks, rnd, ops))


def _checkable(node, envs):
    ys = []
    for e in envs:
        v = ev(node, e)
        if v is ERR or not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or abs(v) > 1e12:
            return None
        ys.append(round(v, 9))
    if len(set(ys)) < 3:
        return None
    return ys


class GenTask:
    def __init__(self, tid, envs, node, ys, test_envs=None):
        self.tid, self.train, self.y_train, self.reference = tid, envs, ys, node
        self.test = test_envs or envs


def generate(kind, exp, src_tasks, rnd, i):
    for _ in range(50):
        if kind == "boundary" and exp.weak:
            tid, envs = rnd.choice(exp.weak)
            blocks = exp.near.get(tid, [])
            lo = max(5, exp.max_size + 1)
            target = rnd.randint(lo, lo + 5)
        elif kind == "fixed":
            t = src_tasks[i % len(src_tasks)]
            envs, blocks, target = t.train, [], (5, 7, 9, 11, 13, 15, 17)[i % 7]
        else:
            t = rnd.choice(src_tasks)
            envs, blocks, target = t.train, [], rnd.randint(3, 21)
        leaves = _leaves(envs)
        if not leaves:
            continue
        node = _grow(target, leaves, blocks, rnd, NUM_OPS)
        ys = _checkable(node, envs)
        if ys is not None:
            return GenTask(f"{kind}-{i}", envs, node, ys)
    return None


def practise(kind, cfg, lib, src_tasks, exp, budget_s, per_task_s, seed, quick_s=0.3):
    """Generate and solve practice tasks for budget_s CPU seconds; returns (experience, log)."""
    rnd = random.Random(f"{kind}-{seed}")
    t0 = time.process_time()
    log = dict(generated=0, rejected_easy=0, practised=0, solved=0)
    i = 0
    while time.process_time() - t0 < budget_s and kind != "none":
        i += 1
        g = generate(kind, exp, src_tasks, rnd, i)
        if g is None:
            continue
        log["generated"] += 1
        if kind == "boundary":
            node, st, _ = K.solve(g.train, g.y_train, cfg, lib, quick_s)
            if node is not None:
                log["rejected_easy"] += 1
                continue
        left = budget_s - (time.process_time() - t0)
        if left <= 0:
            break
        node, st, s = K.solve(g.train, g.y_train, cfg, lib, min(per_task_s, left))
        log["practised"] += 1
        log["solved"] += node is not None
        if node is not None:
            exp.solutions.append(node)
            exp.samples += K.affinity_samples(s, node, max_neg=800)
            exp.max_size = max(exp.max_size, size(node))
    log["cpu_s"] = round(time.process_time() - t0, 2)
    return exp, log


def accept_no_forgetting(old_cfg, old_lib, new_cfg, new_lib, src_tasks, solved_ids, budget_s):
    """PowerPlay acceptance: every src task the old learner solved must still be solved by the new one."""
    lost = []
    for t in src_tasks:
        if t.tid not in solved_ids:
            continue
        node, _, _ = K.solve(t.train, t.y_train, new_cfg, new_lib, budget_s)
        if node is None:
            lost.append(t.tid)
    return (new_cfg, new_lib, lost) if not lost else (old_cfg, old_lib, lost)


def library_from(exp, adm_tasks, cfg, budget_s, max_s=400.0):
    cands = LB.candidates(exp.solutions)
    lib, log, cpu = LB.admit_utility(cands, adm_tasks, cfg, budget_s, max_s=max_s)
    return lib, log, cpu
