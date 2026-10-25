"""Wave 24 v2 experiments: wake-sleep self-evolution, deep hierarchy, schema transfer,
meta-learning with in-domain evolution, semantic specs, goal-directed sleep, wild arena.

Raw per-task rows only; gates are recomputed by scripts/verify_wave24_agi_gap_suite.py.
"""
from __future__ import annotations

import copy
import random
import time

from nexus.wave24_agi_suite import NexusLearner, UNIQUE, grade, amass
from nexus.wave24_domains import Task, source_domains, target_domains, vkey
from nexus.wave24_quotient_core import WorkMeter
from nexus.wave24_wake_sleep import WakeSleep, generic_tool, idiom_library, idiom_stream, _step_tools, _defined

BUDGET = 12_000
STREAM = 30


def row(task, res, method, **extra):
    chain = getattr(res, "_chain", ())
    return dict(domain=task.domain, method=method, depth=len(task.teacher), solved=grade(task, res),
                certificate_valid=res.certificate_valid, status=res.status, work=res.work,
                wrong_unique=res.status == UNIQUE and res.certificate_valid is True and not grade(task, res),
                layer_max=max((t.layer for t in chain), default=0), witness=list(res.witness),
                on_path=len(res.path_keys), expansions=len(res.expansions), **extra)


def _ws_stream(learner, d, stream, *, evolve=True, layer_cap=None):
    m = WorkMeter(limit=10**13)
    learner.enter(d, m)
    ws = WakeSleep(learner, layer_cap=layer_cap, sleep_every=6 if evolve else 10**9, budget=BUDGET)
    res = [ws.wake(t) for t in stream]
    return res, ws, m.total


# --------------------------------------------------------------------------- gaps 4 + 6
def gap4_6_wake_sleep(seed):
    rows, domains = [], []
    for d in (*source_domains(), *target_domains()):
        stream = idiom_stream(d, seed + 100, STREAM, idiom_library(d, seed))
        for method, evolve, cap in (("no_evolution", False, None), ("evolved", True, None), ("evolved_layer1_cap", True, 1)):
            L = NexusLearner(seed=seed, skeleton_mode="all", invent=False)
            res, ws, setup = _ws_stream(L, d, stream, evolve=evolve, layer_cap=cap)
            for t, r in zip(stream, res):
                rows.append(row(t, r, method))
            domains.append(dict(domain=d.name, method=method, sleep_work=ws.sleep_work, setup_work=setup,
                                promotions=ws.promotions, rejections=len(ws.rejections), resolved=len(ws.resolved),
                                bridges=ws.bridges, macros=sorted(L.macros)))
    return dict(seed=seed, rows=rows, domains=domains)


# --------------------------------------------------------------------------- gap 2
def gap2_schema_transfer(seed, n=20):
    src = NexusLearner(seed=seed, skeleton_mode="all", invent=False)
    sm, source_work, generic = WorkMeter(limit=10**13), 0, {}
    for d in source_domains():
        src.enter(d, sm)
        ws = WakeSleep(src, budget=BUDGET)
        for t in idiom_stream(d, seed + 500, 24, idiom_library(d, seed)):
            source_work += ws.wake(t).work
        source_work += ws.sleep_work
        generic.update({k: m for k, m in src.macros.items() if generic_tool(m)})
        src.close_domain(sm)
    rows = []
    for d in target_domains():
        bank = idiom_stream(d, seed + 2000, n, idiom_library(d, seed))
        for method in ("skeleton_policy_transfer", "law_only", "skeletons_no_source"):
            L = NexusLearner(seed=seed, frozen=True, skeleton_mode="none" if method == "law_only" else "all", invent=False)
            if method != "skeletons_no_source":
                L.law_evidence = copy.deepcopy(src.law_evidence)
            m = WorkMeter(limit=10**13)
            L.enter(d, m)
            if method == "skeleton_policy_transfer":
                L.macros.update(generic)
                L.policy, L.policy_prune = copy.deepcopy(src.policy), src.policy_prune
                L.relevance, L.feature_seen = copy.deepcopy(src.relevance), copy.deepcopy(src.feature_seen)
                L.meta = True   # use the transferred relevance model
            for i, t in enumerate(bank):
                r = L.solve(t, budget=BUDGET)
                rows.append(row(t, r, method, setup_work=m.total if i == 0 else 0))
    return dict(seed=seed, rows=rows, source_work=source_work + sm.total, generic_macros=sorted(generic),
                policy_validated=src.policy_prune)


# --------------------------------------------------------------------------- gap 3
def gap3_meta_ws(seed, orders=3, k=12):
    rng = random.Random(f"orders-v2:{seed}")
    runs = []
    for o in range(orders):
        order = list(target_domains())
        rng.shuffle(order)
        for method in ("meta", "reset"):
            L = NexusLearner(seed=seed, meta=method == "meta", transfer=method == "meta", skeleton_mode="all", invent=False)
            generic = {}
            for pos, d in enumerate(order):
                if method == "reset":
                    L = NexusLearner(seed=seed, meta=False, transfer=False, skeleton_mode="all", invent=False)
                m = WorkMeter(limit=10**13)
                L.enter(d, m)
                if method == "meta":
                    L.macros.update(generic)
                ws = WakeSleep(L, budget=BUDGET)
                bank = idiom_stream(d, seed + 3000 + pos, k, idiom_library(d, seed))
                res = [ws.wake(t) for t in bank]
                if method == "meta":
                    generic.update({kk: v for kk, v in L.macros.items() if generic_tool(v)})
                L.close_domain(m)
                runs.append(dict(order=o, method=method, position=pos, domain=d.name,
                                 acquisition_work=sum(r.work for r in res) + ws.sleep_work + m.total,
                                 solved=sum(grade(t, r) for t, r in zip(bank, res)),
                                 on_path=sum(len(r.path_keys) for r in res), expansions=sum(len(r.expansions) for r in res)))
    return dict(seed=seed, runs=runs)


# --------------------------------------------------------------------------- gap 8a
def gap8a_semantic(seed):
    from nexus.wave24_semantic_spec import keyword_baseline, solve_spec, spec_tasks
    rows = []
    for t in spec_tasks(seed, per_spec=2, paraphrased=True):
        s = solve_spec(t)
        rows.append(dict(domain="SPEC", task=t.name, text=t.text, method="semantic_parser", solved=bool(s.get("correct")),
                         work=s["work"], status=s["status"], certificate_valid=True if s.get("witness") else None,
                         witness=s.get("witness"), edge_cases=s.get("edge_cases", 0)))
        k = keyword_baseline(t)
        rows.append(dict(domain="SPEC", task=t.name, text=t.text, method="keyword_retrieval", solved=bool(k["correct"]),
                         work=k["work"], status=k["status"], certificate_valid=None))
    return dict(seed=seed, rows=rows)


# --------------------------------------------------------------------------- gap 8b
def _self_tasks(d, rng, n, feature=None, attempts=600):
    tools = _step_tools(d, True)
    out, proposals = [], 0
    for _ in range(attempts):
        proposals += 1
        chain = [rng.choice(tools) for _ in range(rng.choice((2, 3)))]
        xs = d.inputs(rng, 4)
        try:
            ys = _defined(chain, xs)
        except Exception:
            continue
        if len({vkey(y) for y in ys[:-1]}) < 2 or all(vkey(x) == vkey(y) for x, y in zip(xs, ys)):
            continue
        t = Task(d.name, tuple(zip(xs[:-1], ys[:-1])), xs[-1], ys[-1], tuple(c.name for c in chain))
        if feature is None or NexusLearner.io_feature(t) == feature:
            out.append(t)
        if len(out) == n:
            break
    return out, proposals


def gap8b_goals(seed, n_self=8, n_unseen=10):
    """Blind-spot diagnosis -> goal-directed sleep curriculum vs undirected curriculum vs none."""
    rows, goals = [], []
    for d in target_domains():
        base = NexusLearner(seed=seed, skeleton_mode="all", invent=False)
        base.enter(d, WorkMeter(limit=10**13))
        base.meta = True
        base.failure_log = []
        first = idiom_stream(d, seed + 8100, 12, idiom_library(d, seed))
        for t in first:
            base.solve(t, budget=BUDGET // 2)   # under-budgeted wake pass -> blind spots
        from collections import Counter
        fails = Counter(NexusLearner.io_feature(f["task"]) for f in base.failure_log)
        if not fails:
            continue
        goal = fails.most_common(1)[0][0]
        pool = idiom_stream(d, seed + 8200, 60, idiom_library(d, seed))
        unseen = [t for t in pool if NexusLearner.io_feature(t) == goal][:n_unseen]
        goals.append(dict(domain=d.name, goal=list(map(str, goal)), failures=fails[goal], unseen=len(unseen)))
        if not unseen:
            continue
        for method in ("directed", "undirected", "no_self_training"):
            L = copy.deepcopy(base)
            rng = random.Random(f"curriculum:{d.name}:{seed}")
            cost = 0
            if method == "directed":
                # goal = the blind spot itself: re-attack the failed wake residuals of the goal signature
                # with a governed 2x budget, then compress their derivations (shadow-gated sleep).
                residuals = [f["task"] for f in base.failure_log if NexusLearner.io_feature(f["task"]) == goal]
                residuals += [f["task"] for f in base.failure_log if NexusLearner.io_feature(f["task"]) != goal]
                tasks = residuals[:n_self]
                ws = WakeSleep(L, budget=2 * BUDGET, sleep_every=max(2, len(tasks) // 2) or 2)
            elif method == "undirected":
                tasks, proposals = _self_tasks(d, rng, n_self)
                cost += proposals
                ws = WakeSleep(L, budget=2 * BUDGET, sleep_every=max(2, len(tasks) // 2) or 2)
            if method != "no_self_training":
                for t in tasks:
                    cost += ws.wake(t).work
                ws.sleep()
                cost += ws.sleep_work
            for t in unseen:
                r = L.solve(t, budget=BUDGET // 2)
                rows.append(row(t, r, method, self_training_work=cost))
    return dict(seed=seed, rows=rows, goals=goals)


# --------------------------------------------------------------------------- wild external arena
def wild_arena(seed):
    from nexus.wave24_code_repair import Program, repair, split_names, split_tests
    from nexus.wave24_semantic_spec import discover_law, law_tasks
    repair_rows = []
    for name in split_names("eval"):
        p = Program.load(name)
        pub, hid = split_tests(p, seed)
        if pub is None or not hid:
            continue
        for method in ("fixed", "learned"):
            r = repair(p, pub, hid, learned=method == "learned", prior={})
            repair_rows.append(dict(program=name, method=method, plausible=r.plausible, correct=r.correct, work=r.work,
                                    edit=r.edit_kind, line=r.edit_line, status=r.status))
    law_rows = []
    for t in law_tasks(seed):
        for method, sel in (("mdl_law_discovery", "mdl"), ("linear_fit", "linear")):
            r = discover_law(t, select=sel)
            law_rows.append(dict(law=t["name"], method=method, **r))
    return dict(seed=seed, repair=repair_rows, laws=law_rows)


GAPS_V2 = dict(gap4_6=gap4_6_wake_sleep, gap2_v2=gap2_schema_transfer, gap3_v2=gap3_meta_ws,
               gap8a_v2=gap8a_semantic, gap8b_v2=gap8b_goals, wild=wild_arena)
