"""Measured experiments for the eight Wave 24 capability gaps.

Every function returns raw per-task records; aggregates and gates are
recomputed independently by scripts/verify_wave24_agi_gap_suite.py.
"""
from __future__ import annotations

import copy
import random
import time

from nexus.wave24_agi_suite import (
    BoundedProjector, ForwardWorldModel, IntrinsicGoalSetter, NexusLearner,
    StoneUsefulnessPolicy, UNIQUE, abstract, degrade_description, grade, grounded_plan_solve, solve,
)
from nexus.wave24_auto_laws import AtomicFieldProjector
from nexus.wave24_domains import source_domains, target_domains, task_bank
from nexus.wave24_quotient_core import WorkMeter

BUDGET = 6000
EVAL_DEPTHS = (2, 3, 4)


def record(task, res, method):
    chain = getattr(res, "_chain", ())
    return dict(domain=task.domain, depth=len(task.teacher), messy=task.messy, method=method,
                status=res.status, solved=grade(task, res), work=res.work,
                certificate_valid=res.certificate_valid,
                wrong_unique=res.status == UNIQUE and res.certificate_valid is True and not grade(task, res),
                witness=list(res.witness), found_depth=res.depth,
                layer_max=max((t.layer for t in chain), default=0),
                recovery_fired=recovery_fired(task, chain), fallback=getattr(res, "fallback", False),
                pruned_model=res.pruned_model, pruned_policy=res.pruned_policy,
                on_path=len(res.path_keys), expansions=len(res.expansions))


def recovery_fired(task, chain):
    """True iff a recovery tool inside the certified witness actually caught an exception on public data."""
    def run(tool, v):
        if tool.kind == "recovery":
            head, alt = tool.children
            try:
                return run(head, v), False
            except Exception:
                return alt(v), True
        if tool.kind == "macro":
            fired = False
            for child in tool.children:
                v, f = run(child, v)
                fired |= f
            return v, fired
        return tool(v), False
    for x, _ in task.public:
        v = x
        try:
            for tool in chain:
                v, fired = run(tool, v)
                if fired:
                    return True
        except Exception:
            continue
    return False


def eval_bank(domain, seed):
    bank = task_bank(domain, seed, EVAL_DEPTHS, 4)
    if domain.messy_sampler:
        bank += task_bank(domain, seed + 7, (2, 3), 3, messy=True, recovery=True)
    return bank


def run_stream(learner, domain, bank, meter, *, probe_tasks=3):
    """Enter a domain, decide (meta) whether to explore, solve the stream. Every unit is charged.

    Exploration gain is estimated with a charged counterfactual: a pre-exploration
    snapshot also solves the first `probe_tasks` stream tasks.
    """
    learner.enter(domain, meter)
    explored, explore_cost, gain = False, 0, None
    snapshot = None
    if learner.should_explore():
        snapshot = copy.deepcopy(learner)
        em = WorkMeter(limit=10**12)
        learner.explore(domain, meter=em)
        explore_cost, explored = em.total, True
        meter.charge("exploration_work_units", em.total)
    results = []
    for i, t in enumerate(bank):
        r = learner.solve(t, budget=BUDGET)
        results.append(r)
        if snapshot is not None and i < probe_tasks:
            c = snapshot.solve(t, budget=BUDGET)
            meter.charge("exploration_counterfactual_work_units", c.work)
            gain = (gain or 0) + (c.work - r.work)
    if explored:
        est = (gain or 0) * len(bank) / max(1, min(probe_tasks, len(bank)))
        learner.explore_history.append((explore_cost, est))
    meter.charge("policy_training_work_units", learner.training_work - getattr(learner, "_charged_training", 0))
    learner._charged_training = learner.training_work
    close = learner.close_domain(meter)
    return results, dict(explored=explored, explore_cost=explore_cost, estimated_gain=gain, close=close)


def train_on_sources(learner, seed, meter):
    work = 0
    for d in source_domains():
        learner.enter(d, meter)
        for t in task_bank(d, seed, (1, 2, 3), 6):
            work += learner.solve(t, budget=BUDGET).work
        learner.close_domain(meter)
    return work


# --------------------------------------------------------------------------- gap 1
def gap1_full_cost(seed, per_depth=8):
    """Full learned system (multi-hop ON, depth 4) vs fixed exhaustive search, EVERY cost charged.

    Learned total = source law validation + all probing/model/policy training +
    meta-learning + exploration + exploration counterfactuals + all solving.
    """
    t0 = time.process_time()
    meter = WorkMeter(limit=10**13)
    learner = NexusLearner(seed=seed)
    rows, streams = [], []
    domains = (*source_domains(), *target_domains())
    banks = {d.name: lifelong_bank(d, seed + 1000, per_depth) for d in domains}
    for d in domains:
        before = meter.total
        res, info = run_stream(learner, d, banks[d.name], meter)
        for t, r in zip(banks[d.name], res):
            rows.append(record(t, r, "learned"))
        streams.append(dict(domain=d.name, overhead=meter.total - before, **info))
    learned_cpu = time.process_time() - t0
    t1 = time.process_time()
    for d in domains:
        for t in banks[d.name]:
            rows.append(record(t, solve(t, d.tools, budget=BUDGET), "fixed"))
    fixed_cpu = time.process_time() - t1
    return dict(seed=seed, rows=rows, overhead_work=meter.total, overhead_by_category=dict(meter.counts),
                streams=streams, cpu_s=dict(learned=learned_cpu, fixed=fixed_cpu),
                meta_decisions=learner.meta_decisions)


def lifelong_bank(domain, seed, per_depth):
    bank = task_bank(domain, seed, EVAL_DEPTHS, per_depth)
    if domain.messy_sampler:
        bank += task_bank(domain, seed + 7, (2, 3), max(2, per_depth // 2), messy=True, recovery=True)
    return bank


# --------------------------------------------------------------------------- gap 2
def gap2_zero_shot(seed):
    """Frozen source-trained abstractions on 5 unseen targets; no target learning of any kind."""
    trained = NexusLearner(seed=seed)
    trained_meter = WorkMeter(limit=10**12)
    train_on_sources(trained, seed, trained_meter)
    rows = []
    for d in target_domains():
        bank = lifelong_bank(d, seed + 2000, 8)
        for method in ("transfer", "no_transfer", "all_laws_no_evidence"):
            L = NexusLearner(seed=seed, frozen=True,
                             transfer={"transfer": True, "no_transfer": True, "all_laws_no_evidence": "all_laws"}[method])
            if method == "transfer":
                # the ONLY things carried over: force-level policy, its validated switch, law-family evidence
                L.policy = copy.deepcopy(trained.policy)
                L.policy_prune = trained.policy_prune
                L.law_evidence = copy.deepcopy(trained.law_evidence)
            setup = WorkMeter(limit=10**12)
            L.enter(d, setup)
            for i, t in enumerate(bank):
                r = L.solve(t, budget=BUDGET)
                row = record(t, r, method)
                row["setup_work"] = setup.total if i == 0 else 0   # target probing charged once per domain
                rows.append(row)
        for t in bank:
            rows.append(record(t, solve(t, d.tools, budget=BUDGET), "fixed"))
    return dict(seed=seed, rows=rows, source_training_work=trained_meter.total, transferred_policy=trained.policy.state(),
                reliable_law_families=sorted(map(list, trained.reliable_families())),
                policy_validation=getattr(trained, "policy_validation", None))


# --------------------------------------------------------------------------- gap 3
def gap3_meta(seed, orders=4, k=8):
    """Sequence of unfamiliar domains; meta learner vs per-domain reset control."""
    rng = random.Random(f"orders:{seed}")
    targets = list(target_domains())
    runs = []
    for o in range(orders):
        order = targets[:]
        rng.shuffle(order)
        for method in ("meta", "reset"):
            L = NexusLearner(seed=seed, meta=method == "meta", transfer=method == "meta")
            m = WorkMeter(limit=10**12)
            if method == "meta":
                train_on_sources(L, seed, m)
            for pos, d in enumerate(order):
                before = m.total
                bank = task_bank(d, seed + 3000 + pos, EVAL_DEPTHS, 3)[:k]
                res, info = run_stream(L, d, bank, m)
                close = info["close"]
                runs.append(dict(order=o, method=method, position=pos, domain=d.name,
                                 acquisition_work=sum(r.work for r in res) + (m.total - before),
                                 explored=info["explored"],
                                 solved=sum(grade(t, r) for t, r in zip(bank, res)),
                                 on_path=sum(len(r.path_keys) for r in res),
                                 expansions=sum(len(r.expansions) for r in res),
                                 wasted_branches=sum(len(r.expansions) - len(r.path_keys) for r in res),
                                 macros_promoted=close["promoted"], macros_reused=close["reused"],
                                 tau=L.policy.tau))
    return dict(seed=seed, runs=runs)


# --------------------------------------------------------------------------- gap 4
def gap4_closed_loop(seed):
    """Idle exploration -> promoted helpers -> measured effect on the evaluated stream."""
    base = NexusLearner(seed=seed)
    train_on_sources(base, seed, WorkMeter(limit=10**12))
    rows, promotions, evictions = [], [], []
    for d in target_domains():
        bank = eval_bank(d, seed + 4000)
        for method in ("explore", "no_explore"):
            L = copy.deepcopy(base)
            L.enter(d, WorkMeter(limit=10**12))
            explore_work = 0
            if method == "explore":
                em = WorkMeter(limit=10**12)
                rep = L.explore(d, meter=em)
                explore_work = em.total
                promotions.append(dict(domain=d.name, **rep))
            res = [L.solve(t, budget=BUDGET) for t in bank]
            for t, r in zip(bank, res):
                rows.append(dict(record(t, r, method), explore_work=explore_work))
            if method == "explore":
                # distribution shift: a different-seed, deeper stream; retire helpers never used
                shifted = task_bank(d, seed + 4500, (4,), 4)
                shifted_res = [L.solve(t, budget=BUDGET) for t in shifted]
                evictions.append(dict(domain=d.name, evicted=L.evict_net_negative(shifted_res),
                                      remaining=sorted(L.macros)))
    return dict(seed=seed, rows=rows, promotions=promotions, evictions=evictions)


# --------------------------------------------------------------------------- gap 5
def gap5_robustness(seed):
    proj, exact = BoundedProjector(), AtomicFieldProjector()
    scaling = []
    for n in (100, 1000, 10000):
        value = list(range(n))
        t0 = time.perf_counter()
        for _ in range(20):
            proj.project(value)
        t1 = time.perf_counter()
        for _ in range(20):
            exact.project(value)
        t2 = time.perf_counter()
        scaling.append(dict(n=n, bounded_ms=(t1 - t0) / 20 * 1000, exact_ms=(t2 - t1) / 20 * 1000))
    # approximate laws: probes on short inputs, evaluation on longer ones (mass distribution shift)
    from nexus.wave24_domains import series_domain
    d = series_domain()
    short = [[float(i % 5) for i in range(n)] for n in (3, 4)]
    retention = {}
    for slack in (0.0, 0.5):
        model = ForwardWorldModel(slack=slack)
        model.fit_probes(d.tools, short, WorkMeter(limit=10**9))
        bank = task_bank(d, seed + 5000, (2, 3), 4)
        kept = sum(grade(t, solve(t, d.tools, budget=BUDGET, learned=True, model=model, forces={})) for t in bank)
        retention[str(slack)] = dict(solved=kept, tasks=len(bank),
                                     fixed=sum(grade(t, solve(t, d.tools, budget=BUDGET)) for t in bank))
    from nexus.wave24_domains import stdlib_domain
    sd = stdlib_domain()
    return dict(seed=seed, scaling=scaling, approximate_law_retention=retention,
                stdlib_ingested=[t.name for t in sd.tools])


# --------------------------------------------------------------------------- gap 7
def gap7_world_model(seed):
    rows, accuracy = [], dict(predicted=0, contained=0)
    for d in (*source_domains(), *target_domains()):
        L = NexusLearner(seed=seed, frozen=True)
        L.enter(d, WorkMeter(limit=10**12))
        bank = eval_bank(d, seed + 7000)
        for t in bank:
            x = t.public[0][0]
            for tool in d.tools:
                pred = L.model.predict(tool, [abstract(x)], WorkMeter(limit=10**9))
                try:
                    y = tool(x)
                except Exception:
                    continue
                if pred is not None and pred[0] is not None:
                    accuracy["predicted"] += 1
                    accuracy["contained"] += type(y).__name__ in pred[0][0]
            r = solve(t, d.tools, budget=BUDGET, learned=True, model=L.model, forces=L.forces)
            rows.append(record(t, r, "world_model"))
            rows.append(record(t, solve(t, d.tools, budget=BUDGET), "fixed"))
    return dict(seed=seed, rows=rows, prediction_accuracy=accuracy)


# --------------------------------------------------------------------------- gap 8
def gap8_grounding_planning(seed):
    rng = random.Random(f"text:{seed}")
    rows = []
    for d in (*source_domains(), *target_domains()):
        bank = task_bank(d, seed + 8000, (4, 5, 6), 2)
        for t in bank:
            text = degrade_description(t.description, rng)
            g = grounded_plan_solve(t, d.tools, text, budget=BUDGET)
            rows.append(dict(domain=d.name, depth=len(t.teacher), method="grounded_planner", solved=bool(g.get("correct")),
                             work=g["work"], status=g["status"], certificate_valid=None if "witness" not in g else True))
            r = solve(t, d.tools, max_depth=6, budget=BUDGET)
            rows.append(record(t, r, "blind_fixed"))
    return dict(seed=seed, rows=rows)


def gap8_intrinsic_goals(seed):
    """Failure log -> self-set goals -> directed exploration -> unseen tasks (vs undirected, same task count)."""
    setter = IntrinsicGoalSetter()
    base = NexusLearner(seed=seed)
    train_on_sources(base, seed, WorkMeter(limit=10**12))
    out, goals_log = [], []
    for d in target_domains():
        L = copy.deepcopy(base)
        L.enter(d, WorkMeter(limit=10**12))
        L.failure_log = []                    # goals come only from THIS domain's own failures
        for t in task_bank(d, seed + 8100, (3, 4), 4):
            L.solve(t, budget=BUDGET // 3)   # under-budgeted first pass -> failure log
        goals = setter.goals(L.failure_log)
        if not goals:
            continue
        match = lambda t, goals=goals: any(setter.matches(g, t) for g in goals)
        unseen = [t for t in task_bank(d, seed + 8200, (3, 4), 20) if match(t)][:10]
        goals_log.append(dict(domain=d.name, goals=goals, unseen=len(unseen)))
        if not unseen:
            continue
        for method in ("directed", "undirected"):
            M = copy.deepcopy(L)
            em = WorkMeter(limit=10**12)
            M.explore(d, meter=em, tasks=8, budget=BUDGET // 2, task_filter=match if method == "directed" else None)
            res = [M.solve(t, budget=BUDGET // 3) for t in unseen]
            for t, r in zip(unseen, res):
                out.append(dict(record(t, r, method), exploration_work=em.total))
    return dict(seed=seed, rows=out, goals=goals_log)
