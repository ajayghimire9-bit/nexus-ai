"""Wave 24 v3 procedural experiments: validated portable schemas (Piece C) and a strategy-allocation
meta-policy (Piece D) over the procedural families.

Forbidden crutches are absent by construction: no skeleton library (skeleton_mode="none"), no
idiom streams (uniform seeded random teachers from wave24_domains.task_bank), and no surface-type
relevance suppression - every arm always keeps every original domain tool; transfer can only ADD
candidates, never hide a tool.

Piece C - domain adapters + portable schemas:
  * adapter discovery: entering a family, every raw operator is fingerprinted from unlabeled
    probes into one of the five atomic force roles (select / translate / transmute / condense /
    branch) by AtomicForceClassifier, and try/except recovery partners are synthesised on faults;
  * portable schemas: role bigrams (force_a -> force_b) that recur on certified source witnesses
    across >= `min_support` distinct source tasks;
  * validated binding: in a target family a schema binds to a concrete tool pair only after that
    pair is observed on a certified witness of a warm-up/stream task in THIS family (first
    occurrence), whereas without a schema prior the learner needs two occurrences. A bound macro
    that is never reused is retired by the learner's own hindsight accounting.
  * arms: experienced (source-trained: law-family evidence, LODO-validated force policy,
    strategy statistics, schemas), amnesiac (same learner, same in-family learning, no source
    experience), fixed (exhaustive quotiented search).
Piece D - strategy allocation by problem signature:
  * strategies = space-preserving solver configurations {full, no_predict};
  * signature = (input kind, output kind, mass relation, any tool faults on a public input) -
    domain-agnostic and computed from public data (fault probe charged);
  * policy: highest posterior solve rate, ties within 0.05 broken by lower expected work (a
    non-full choice is charged its failure probability x the full strategy's work); the first
    `explore_k` occurrence of each coarse signature (output kind, faults) also runs the alternative
    strategy as a charged shadow;
    a non-full choice that fails falls back to `full` (charged), so no solve is traded for work;
  * meta (persistent, source-trained) vs reset (fresh learner per family, always `full`).
Every unit (probes, predictions, shadows, fallbacks, training) is charged on the meters.
"""
from __future__ import annotations

import copy
import random
from collections import Counter, defaultdict

from nexus.wave24_agi_suite import NexusLearner, UNIQUE, amass, grade, solve
from nexus.wave24_domains import source_domains, target_domains, task_bank
from nexus.wave24_quotient_core import WorkMeter

BUDGET = 6000
# Only strategies that keep the declared program space are allocated: on dev seed 2, dropping
# recovery synthesis ("no_recovery"/"lean") produced UNIQUE certificates in a smaller space whose
# query answers were wrong, i.e. it traded correct solves for work. Forward-model prediction only
# prunes branches predicted unable to reach the target, so toggling it keeps the space.
CONFIGS = {
    "full": dict(predict=True, recovery=True),
    "no_predict": dict(predict=False, recovery=True),
}


def stream_bank(domain, seed, per_depth):
    bank = task_bank(domain, seed, (2, 3, 4), per_depth)
    if domain.messy_sampler:
        bank += task_bank(domain, seed + 7, (2, 3), max(2, per_depth // 2), messy=True, recovery=True)
    random.Random(f"shuffle:{domain.name}:{seed}").shuffle(bank)
    return bank


def signature(task, tools, meter):
    """Domain-agnostic problem signature from public data only (fault probe charged)."""
    def kind(v):
        return "map" if isinstance(v, dict) else "str" if isinstance(v, (str, bytes)) else \
            "seq" if isinstance(v, (list, tuple)) else "scalar"
    x, y = task.public[0]
    rel = tuple(sorted({(amass(b) > amass(a)) - (amass(b) < amass(a)) for a, b in task.public}))
    faults = False
    for t in tools:
        if t.layer:
            continue
        for xi, _ in task.public:
            meter.charge("signature_probe_work_units")
            try:
                t(xi)
            except Exception:
                faults = True
                break
        if faults:
            break
    return (kind(x), kind(y), rel, faults)


class StrategyMetaPolicy:
    SHADOWS = ("no_predict",)

    def __init__(self, *, explore_k=1, tol=0.05):
        self.stats = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))   # sig -> cfg -> [solved, n, work]
        self.seen = Counter()
        self.explore_k, self.tol = explore_k, tol
        self.decisions = Counter()

    def record(self, sig, cfg, solved, work):
        s = self.stats[sig][cfg]
        s[0] += int(solved)
        s[1] += 1
        s[2] += work

    def _estimates(self, sig):
        rows = self.stats.get(sig)
        if not rows or sum(v[1] for v in rows.values()) < 2:
            pooled = defaultdict(lambda: [0, 0, 0])
            for k, d in self.stats.items():
                if k[3] == sig[3]:
                    for c, v in d.items():
                        for i in range(3):
                            pooled[c][i] += v[i]
            rows = pooled
        return {c: ((v[0] + 1) / (v[1] + 2), v[2] / max(1, v[1])) for c, v in rows.items() if v[1]}

    def choose(self, sig):
        """Minimum expected cost, counting the charged fall-back to `full` when a choice fails."""
        est = self._estimates(sig)
        if "full" not in est:
            return "full"
        best_rate = max(r for r, _ in est.values())
        ok = [c for c, (r, _) in est.items() if r >= best_rate - self.tol]
        full_work = est["full"][1]
        def expected(c):
            rate, work = est[c]
            return work if c == "full" else work + (1 - rate) * full_work
        choice = min(ok, key=lambda c: (expected(c), c != "full", c))
        self.decisions[choice] += 1
        return choice

    @staticmethod
    def coarse(sig):
        return (sig[1], sig[3])          # output kind, faults-on-public-input

    def should_explore(self, sig):
        return self.seen[self.coarse(sig)] < self.explore_k

    def state(self):
        return {repr(k): {c: list(v) for c, v in d.items()} for k, d in self.stats.items()}


def portable_schemas(witness_roles, *, min_support=3):
    """Role bigrams recurring on certified witnesses of >= min_support distinct tasks."""
    support = Counter()
    for roles in witness_roles:
        support.update({(a, b) for a, b in zip(roles, roles[1:]) if "F_COMPOSITE" not in (a, b)})
    return {k: n for k, n in support.items() if n >= min_support}


class V3Learner(NexusLearner):
    """NexusLearner without skeletons, plus strategy allocation and schema-primed binding."""

    def __init__(self, *, seed=0, meta=True, transfer=True, strategy=True, schemas=None):
        super().__init__(seed=seed, meta=meta, transfer=transfer, skeleton_mode="none", invent=True)
        self.strategy = StrategyMetaPolicy() if strategy else None
        self.schemas = dict(schemas or {})
        self.witness_roles = []
        self.bindings = []
        self.shadow_work = 0

    def solve_cfg(self, task, cfg, *, budget):
        c = CONFIGS[cfg]
        saved = self.predict_on
        self.predict_on = saved and c["predict"]
        try:
            tools = self.toolset()
            res = solve(task, tools, max_depth=4, budget=budget, learned=True, model=self.model,
                        policy=self.policy if self.policy_prune else None, forces=self.forces_all(),
                        recovery_map=self.recovery_map, laws=self.laws, predict=self.predict_on,
                        fault_memory=self.fault_memory, recovery=c["recovery"])
            if res.status == "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED" or (
                    res.status == "NO_PROGRAM_IN_BOUNDED_GRAMMAR" and (res.pruned_policy or res.pruned_model)):
                spent = res.work
                res2 = solve(task, tools, max_depth=4, budget=max(1, budget - spent), learned=False,
                             model=self.model, forces=self.forces_all(), laws=self.laws, recovery=c["recovery"])
                res2.work += spent
                res2.fallback = True
                res = res2
            if res.status == "AMBIGUOUS_WITNESS_FOUND" and len(tools) > len(self.tools):
                # Declared fallback: learned macros can make a longer program "minimal" and admit
                # several answers; re-certify in the primitive space (charged).
                spent = res.work
                res2 = solve(task, list(self.tools), max_depth=4, budget=max(1, budget - spent), learned=True,
                             model=self.model, policy=self.policy if self.policy_prune else None,
                             forces=self.forces_all(), recovery_map=self.recovery_map, laws=self.laws,
                             predict=self.predict_on, fault_memory=self.fault_memory, recovery=c["recovery"])
                res2.work += spent
                res2.macro_ambiguity_fallback = True
                res = res2
        finally:
            self.predict_on = saved
        return res

    def solve_task(self, task, *, budget=BUDGET):
        """Strategy-allocated solve with charged shadows / fallback; learns from certified results."""
        meter = WorkMeter(limit=10**12)
        if self.strategy is None:
            res = self.solve_cfg(task, "full", budget=budget)
            cfg, sig = "full", None
        else:
            sig = signature(task, self.tools, meter)
            explore = self.strategy.should_explore(sig)
            self.strategy.seen[self.strategy.coarse(sig)] += 1
            cfg = "full" if explore else self.strategy.choose(sig)
            res = self.solve_cfg(task, cfg, budget=budget)
            self.strategy.record(sig, cfg, res.status == UNIQUE and res.certificate_valid is True, res.work)
            if explore:
                for other in self.strategy.SHADOWS:
                    sh = self.solve_cfg(task, other, budget=budget)
                    meter.charge("strategy_shadow_work_units", sh.work)
                    self.shadow_work += sh.work
                    self.strategy.record(sig, other, sh.status == UNIQUE and sh.certificate_valid is True, sh.work)
            elif cfg != "full" and not (res.status == UNIQUE and res.certificate_valid is True):
                spent = res.work
                res = self.solve_cfg(task, "full", budget=budget)
                res.work += spent
                res.strategy_fallback = True
        res.work += meter.total
        res.strategy = cfg
        res.signature = sig
        if res.status == UNIQUE and res.certificate_valid is True:
            if not self.frozen:
                self._learn_from(task, res)
                self._bind(res)
            chain = getattr(res, "_chain", ())
            self.witness_roles.append([self.forces_all().get(t.name, "F_COMPOSITE") if t.kind == "primitive"
                                       else "F_COMPOSITE" for t in chain])
        else:
            self.failure_log.append(dict(task=task, status=res.status))
        return res

    def _bind(self, res):
        """Validated binding: a schema-matching adjacent primitive pair on THIS certified witness."""
        if not self.schemas:
            return
        from nexus.wave24_agi_suite import macro_tool
        chain = list(getattr(res, "_chain", ()))
        for a, b in zip(chain, chain[1:]):
            if a.kind != "primitive" or b.kind != "primitive":
                continue
            roles = (self.forces.get(a.name), self.forces.get(b.name))
            if roles in self.schemas:
                m = macro_tool({a.name: a, b.name: b}, (a.name, b.name))
                if m.name not in self.macros:
                    self.macros[m.name] = m
                    self.bindings.append(dict(domain=self.domain.name, macro=m.name, roles=list(roles),
                                              support=self.schemas[roles]))


# --------------------------------------------------------------------------- source training
def train_sources(seed, *, per_depth=4):
    L = V3Learner(seed=seed, meta=True, transfer=True, strategy=True)
    m = WorkMeter(limit=10**13)
    work = 0
    for d in source_domains():
        L.enter(d, m)
        for t in task_bank(d, seed, (1, 2, 3), per_depth):
            work += L.solve_task(t).work
        m.charge("policy_training_work_units", L.training_work - getattr(L, "_charged", 0))
        L._charged = L.training_work
        L.close_domain(m)
    L.schemas = portable_schemas(L.witness_roles)
    return L, work + m.total


def _row(task, res, method, **extra):
    chain = getattr(res, "_chain", ())
    return dict(domain=task.domain, depth=len(task.teacher), messy=task.messy, method=method,
                solved=grade(task, res), work=res.work, status=res.status,
                certificate_valid=res.certificate_valid,
                wrong_unique=res.status == UNIQUE and res.certificate_valid is True and not grade(task, res),
                witness=list(res.witness), on_path=len(res.path_keys), expansions=len(res.expansions),
                layer_max=max((t.layer for t in chain), default=0), strategy=getattr(res, "strategy", "fixed"),
                **extra)


# --------------------------------------------------------------------------- Piece C
def transfer_v3(seed, *, per_depth=5, trained=None):
    trained, source_work = trained or train_sources(seed)
    rows, bindings = [], []
    for d in target_domains():
        bank = stream_bank(d, seed + 2000, per_depth)
        for method in ("experienced", "amnesiac"):
            if method == "experienced":
                L = copy.deepcopy(trained)
                L.bindings = []
            else:
                L = V3Learner(seed=seed, meta=True, transfer=True, strategy=True)
            setup = WorkMeter(limit=10**13)
            L.enter(d, setup)
            for i, t in enumerate(bank):
                r = L.solve_task(t)
                rows.append(_row(t, r, method, setup_work=setup.total if i == 0 else 0, target=d.name))
            setup2 = WorkMeter(limit=10**13)
            setup2.charge("policy_training_work_units", L.training_work - getattr(L, "_charged", 0))
            L._charged = L.training_work
            L.close_domain(setup2)
            if rows:
                rows[-1]["setup_work"] = rows[-1].get("setup_work", 0) + setup2.total
            if method == "experienced":
                bindings += L.bindings
        for t in bank:
            rows.append(_row(t, solve(t, d.tools, budget=BUDGET), "fixed", setup_work=0, target=d.name))
    return dict(seed=seed, rows=rows, source_work=source_work, schemas={f"{a}>{b}": n for (a, b), n in
                                                                         sorted(trained.schemas.items())},
                bindings=bindings, policy_validated=trained.policy_prune)


# --------------------------------------------------------------------------- Piece D
def meta_v3(seed, *, orders=3, per_depth=3, trained=None):
    rng = random.Random(f"orders-v3:{seed}")
    runs = []
    trained, source_work = trained or train_sources(seed)
    for o in range(orders):
        order = list(target_domains())
        rng.shuffle(order)
        for method in ("meta", "reset"):
            L = copy.deepcopy(trained) if method == "meta" else None
            for pos, d in enumerate(order):
                if method == "reset":
                    L = V3Learner(seed=seed, meta=False, transfer=False, strategy=False)
                m = WorkMeter(limit=10**13)
                L.enter(d, m)
                bank = stream_bank(d, seed + 3000 + pos, per_depth)
                shadow0 = L.shadow_work
                res = [L.solve_task(t) for t in bank]
                m.charge("policy_training_work_units", L.training_work - getattr(L, "_charged", 0))
                L._charged = L.training_work
                L.close_domain(m)
                solved = sum(grade(t, r) for t, r in zip(bank, res))
                work = sum(r.work for r in res) + m.total
                runs.append(dict(order=o, method=method, position=pos, domain=d.name, tasks=len(bank),
                                 solved=solved, acquisition_work=work, work_per_solve=work / max(1, solved),
                                 on_path=sum(len(r.path_keys) for r in res),
                                 expansions=sum(len(r.expansions) for r in res),
                                 strategies=dict(Counter(getattr(r, "strategy", "full") for r in res)),
                                 fallbacks=sum(bool(getattr(r, "strategy_fallback", False)) for r in res),
                                 shadow_work=L.shadow_work - shadow0,
                                 false_certificates=sum(r.status == UNIQUE and r.certificate_valid is False
                                                        for r in res)))
    return dict(seed=seed, runs=runs, source_work=source_work, strategy_state=trained.strategy.state())


def run_seed(seed, *, transfer_per_depth=5, meta_orders=3, meta_per_depth=3):
    trained = train_sources(seed)
    return dict(seed=seed, transfer=transfer_v3(seed, per_depth=transfer_per_depth, trained=trained),
                meta=meta_v3(seed, orders=meta_orders, per_depth=meta_per_depth, trained=trained))
