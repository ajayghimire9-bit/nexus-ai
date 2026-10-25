"""Wave 25 refocus: answer-equivalence version spaces, dual-ledger contract vault, self-evolving reasoning
procedure. Reuses wave25_contracts (learner, proved-contract pruner), wave25_s3 (exact hypothesis
enumeration, answer objective, candidate generators) and the v4 ObsEGraph certifier.

Version space. V_t is never stored as a pruned set: it is the exact set of minimal-size programs consistent
with ALL observations made so far on the latent task (public pairs + every probe observation). A query is
certified UNIQUE when every program in V_t agrees on it; nothing is deleted when that happens, so a later
query on the same task is re-partitioned over the same V_t and probes only for its own new split.

Dual ledger. Each contract carries an immutable ValidityRecord (PROVED_SOUND / UNPROVED_HEURISTIC / REFUTED)
and a context-dependent UtilityRecord. Only PROVED_SOUND contracts may prune (enforced at pruner
construction); UNPROVED_HEURISTIC patterns may only reorder the certifier's search. Utility is credited
online with a deterministic lower bound: a prune at depth d is credited one full expansion of that node
(n_ops x values) only if level d + 1 was completed without the early-ambiguity stop; the credited saving
minus the property's check cost updates an EMA per context. A contract with negative utility in a context
is deactivated there (kept in the vault, re-explored every EXPLORE_EVERY tasks of that context).

ReasoningProcedure. Inspectable state that improves across tasks: contextual contract activation, two-tier
probe-generator scheduling (cheap standard perturbations first; factored disagreement edits only if no
cheap candidate reaches the maximal answer information H(Y_q | V_t); generators ordered by per-domain hit
rate), and a soft search-order prior from operator success frequencies (UNPROVED_HEURISTIC, ordering only).
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from nexus.wave24_domains import vkey
from nexus.wave24_quotient_core import WorkExhausted
from nexus.wave24_v4_core import AMBIGUOUS, UNIQUE, Searcher, candidate_probes, meter
from nexus.wave25_contracts import (NUMERIC, default_props, item_map, learn_contracts, make_contract_pruner,
                                    tycho_admit_contracts, usable_props)
from nexus.wave25_factored import (MAX_DEPTH, ORACLE_COST, PROBE_BUDGET, TASK_BUDGET, ints_world, make_tasks,
                                   records_world, run)
from nexus.wave25_s3 import _H, _reps, choose_probe, cond_info, enumerate_H, factored_candidates, outputs

PROVED_SOUND, UNPROVED_HEURISTIC, REFUTED = "PROVED_SOUND", "UNPROVED_HEURISTIC", "REFUTED"
EMA_RATE = 0.3
EXPLORE_EVERY = 5
MIN_OBS = 2
PRUNE_PROPS = ("kind",) + tuple(NUMERIC) + ("provenance",)


# --------------------------------------------------------------------------- dual-ledger vault
@dataclass(frozen=True)
class ValidityRecord:
    prop: str
    applicable_operators: tuple
    relation: str
    assumptions: str
    verification_scope: str
    status: str


@dataclass
class UtilityRecord:
    discovery_cost: float = 0.0
    check_cost_total: int = 0
    observed_work_saved: float = 0.0
    net_utility_ema: dict = field(default_factory=dict)      # context -> EMA of (credited saving - checks)
    n_obs: Counter = field(default_factory=Counter)
    active_by_context: dict = field(default_factory=dict)


class ContractVault:
    """Validity is fixed once decided; utility evolves. Pruning permission is checked here, nowhere else."""

    def __init__(self, lib):
        self.lib = lib
        self.validity = []
        for c in lib.contracts:
            status = PROVED_SOUND if c.status == "proved" else REFUTED if c.status == "refuted" else UNPROVED_HEURISTIC
            self.validity.append(ValidityRecord(c.prop, (c.role,), c.relation,
                                                assumptions=f"role {c.role} has verified class {lib.role_classes.get(c.role)}",
                                                verification_scope="derived from verified IR class + property lifting "
                                                                   "table; cross-checked on declared universes",
                                                status=status))
        self.heuristics = {}          # pattern name -> ValidityRecord(UNPROVED_HEURISTIC), ordering only
        learning = sum(lib.work.values())
        self.utility = {p: UtilityRecord(discovery_cost=learning / len(PRUNE_PROPS)) for p in PRUNE_PROPS}

    def sound_props(self, roles):
        """Properties that are PROVED_SOUND for every list role present (the only ones that may prune)."""
        return usable_props(self.lib, roles)

    def pruner_props(self, roles, active):
        u = self.sound_props(roles)
        sound = set(u["numeric"]) | ({"provenance"} if u["provenance"] else set()) | \
            ({"kind"} if u["scalar_terminal"] else set())
        bad = set(active) - sound
        if bad:
            raise PermissionError(f"only PROVED_SOUND contracts may prune; refused {sorted(bad)}")
        return dict(numeric=[p for p in NUMERIC if p in active and p in u["numeric"]],
                    provenance="provenance" in active and u["provenance"],
                    provenance_image=u.get("provenance_image", False),
                    scalar_terminal="kind" in active and u["scalar_terminal"])

    def status_counts(self):
        return dict(Counter(v.status for v in self.validity))


# --------------------------------------------------------------------------- reasoning procedure
def task_context(world, public, tools):
    n = sum(len(x) for x, _ in public if isinstance(x, list)) / max(1, len(public))
    fan = len(tools)
    return (world["name"], "fan<40" if fan < 40 else "fan<80" if fan < 80 else "fan80+", "len<=3" if n <= 3 else "len>3")


class ReasoningProcedure:
    def __init__(self, vault, *, seed=0):
        self.vault = vault
        self.ctx_tasks = Counter()
        self.gen_hits = defaultdict(Counter)
        self.gen_tries = defaultdict(Counter)
        self.op_success = defaultdict(Counter)       # world -> (role, slot-kind) -> certified uses
        self.activation_log = []
        self.rng = random.Random(f"w25-rp:{seed}")

    # 1. contextual contract activation
    def select_active_contracts(self, ctx, roles):
        u = self.vault.sound_props(roles)
        sound = [p for p in PRUNE_PROPS if (p == "kind" and u["scalar_terminal"]) or p in u["numeric"]
                 or (p == "provenance" and u["provenance"])]
        k = self.ctx_tasks[ctx]
        explore = k % EXPLORE_EVERY == 0
        active = []
        for p in sound:
            rec = self.vault.utility[p]
            ema = rec.net_utility_ema.get(ctx)
            on = ema is None or rec.n_obs[ctx] < MIN_OBS or ema >= 0 or explore
            rec.active_by_context[ctx] = on
            if on:
                active.append(p)
        self.activation_log.append(dict(ctx=list(ctx), sound=sound, active=active))
        return active

    def update_utility(self, ctx, attribution, res, n_ops, n_vals):
        s = res.searcher
        reached = res.size or MAX_DEPTH
        early = s.early_stopped_depth
        unit = n_ops * n_vals
        for p in PRUNE_PROPS:
            checks = attribution.get(("checks", p), 0)
            saved = 0.0
            for r in range(1, MAX_DEPTH + 1):
                c = attribution.get(("by", p, r), 0)
                d = MAX_DEPTH - r
                if c and d + 1 <= reached and early != d + 1:
                    saved += c * unit             # lower bound: one expansion of each pruned node
            if checks == 0 and saved == 0:
                continue
            rec = self.vault.utility[p]
            rec.check_cost_total += checks
            rec.observed_work_saved += saved
            v = saved - checks
            old = rec.net_utility_ema.get(ctx)
            rec.net_utility_ema[ctx] = v if old is None else (1 - EMA_RATE) * old + EMA_RATE * v
            rec.n_obs[ctx] += 1
        self.ctx_tasks[ctx] += 1

    # 3. soft search-order prior (UNPROVED_HEURISTIC, ordering only)
    @staticmethod
    def _op_kind(mech):
        return (mech.role, tuple(type(s).__name__ for s in mech.slots))

    def rank_candidates(self, world):
        freq = self.op_success[world["name"]]
        if not freq:
            return None

        def order(prev, ops):
            return sorted(ops, key=lambda t: -freq.get(self._op_kind(t.fn), 0))
        return order

    def record_witnesses(self, world, H):
        for h in H:
            for mech in h:
                self.op_success[world["name"]][self._op_kind(mech)] += 1
        self.vault.heuristics[f"op_success:{world['name']}"] = ValidityRecord(
            "op_success", tuple(sorted({k[0] for k in self.op_success[world["name"]]})), "frequency",
            assumptions="empirical frequency in certified version spaces", verification_scope="none",
            status=UNPROVED_HEURISTIC)

    # 2. two-tier probe-generator scheduling
    def schedule_probe(self, H, yq, public, query, world, rng, m):
        seen = {vkey(x) for x, _ in public} | {vkey(query)}
        dom = world["name"]
        cap = _H(Counter(yq))
        bases = [x for x, _ in public] + [query]
        best, best_key, best_gen = None, (0.0, 0.0), None

        def scan(cands):
            nonlocal best, best_key, best_gen
            for gen, x in cands:
                k = vkey(x)
                if k in seen:
                    continue
                seen.add(k)
                self.gen_tries[dom][gen] += 1
                ys = outputs(H, x, m)
                key = (cond_info(yq, ys), _H(Counter(ys)))
                if key > best_key:
                    best, best_key, best_gen = x, key, gen
                    if key[0] >= cap - 1e-12:
                        return True
            return False

        def by_rate(cands):
            rate = {g: (self.gen_hits[dom][g] + 1) / (self.gen_tries[dom][g] + 2) for g, _ in cands}
            return sorted(cands, key=lambda gx: -rate[gx[0]])

        reps = [h for h in H[:50]]
        tier1 = [(fam, x) for fam, x, _ in candidate_probes(bases, [(None, None, tuple(_T(mm) for mm in h))
                                                                    for h in reps], query)]
        done = scan(by_rate(tier1)[:300])
        tier = 1
        if not done:
            tier = 2
            scan(by_rate(factored_candidates(H, yq, public, query, rng, m, labels=True))[:300])
        if best is not None:
            self.gen_hits[dom][best_gen] += 1
        return best, f"tier{tier}:{best_gen}"


class _T:
    """Minimal Tool-like wrapper so v4's candidate_probes can read a mechanism as a program step."""

    def __init__(self, fn):
        self.fn, self.name = fn, fn.name()

    def __call__(self, x):
        return self.fn(x)


# --------------------------------------------------------------------------- certification
def certify_full(public, query, tools, world, rp, ctx, m):
    roles = {t.fn.role for t in tools}
    active = rp.select_active_contracts(ctx, roles)
    props = rp.vault.pruner_props(roles, active)
    maps = [item_map(t.fn) for t in tools if item_map(t.fn) is not None]
    attr = Counter()
    pr = make_contract_pruner(props, attribution=attr, maps=maps) if active else None
    s = Searcher(tuple(public), query, tools, popper=True, m=meter(TASK_BUDGET), partial_depth=0,
                 max_depth=MAX_DEPTH, abstract=pr, early_ambiguity=True, order=rp.rank_candidates(world))
    res = s.run_to(MAX_DEPTH)
    res.searcher = s
    m.charge("certify_work_units", res.work)
    rp.update_utility(ctx, attr, res, len(tools), len(public) + 1)
    return res, active


def certify_static(public, query, tools, world, props, m):
    pr = None
    if props is not None:
        maps = [item_map(t.fn) for t in tools if item_map(t.fn) is not None]
        pr = make_contract_pruner(props, maps=maps)
    s = Searcher(tuple(public), query, tools, popper=True, m=meter(TASK_BUDGET), partial_depth=0,
                 max_depth=MAX_DEPTH, abstract=pr)
    res = s.run_to(MAX_DEPTH)
    res.searcher = s
    m.charge("certify_work_units", res.work)
    return res


# --------------------------------------------------------------------------- multi-query episodes
@dataclass
class Episode:
    world: str
    public: tuple
    queries: tuple             # (q1, q2)
    answers: tuple             # grading only
    teacher: tuple             # oracle only


def make_episodes(world, seed, n):
    rng = random.Random(f"w25-mq:{world['name']}:{seed}")
    out = []
    for t in make_tasks(world, seed, n, active=True):
        for _ in range(20):
            q2 = world["sample"](rng)
            try:
                a2 = run(t.teacher, q2)
            except Exception:
                continue
            if vkey(q2) not in {vkey(x) for x, _ in t.public} | {vkey(t.query)}:
                out.append(Episode(world["name"], t.public, (t.query, q2), (t.answer, a2), t.teacher))
                break
    return out


def run_episode(ep, world, arm, *, rp=None, static_props=None, reuse=True, seed=0):
    """Answer q1 then q2 on the same latent task. With reuse, q2 starts from every observation made so far
    (the persistent version space); without reuse it starts from the public pairs only."""
    m = meter(10**12)
    tools = episode_grammar(ep, world)
    mechs = [t.fn for t in tools]
    obs = list(ep.public)
    rng = random.Random(f"w25-ep:{seed}:{arm}:{vkey(ep.queries[0])}")
    per_q = []
    for qi, (q, ans) in enumerate(zip(ep.queries, ep.answers)):
        if qi == 1 and not reuse:
            obs = list(ep.public)
        probes, labels, actives = 0, [], []
        q_start = m.total
        try:
            ctx = task_context(world, obs, tools)
            res, act = certify_full(obs, q, tools, world, rp, ctx, m) if arm == "full" else \
                (certify_static(obs, q, tools, world, static_props, m), None)
            actives.append(act)
            initial_status = res.status
            while res.status == AMBIGUOUS and probes < PROBE_BUDGET:
                H = enumerate_H(obs, mechs, res.size, m) if res.size in (1, 2) else \
                    [tuple(t.fn for t in p) for p in _reps(res)]
                yq = outputs(H, q, m)
                if arm == "full":
                    x, label = rp.schedule_probe(H, yq, obs, q, world, rng, m)
                else:
                    x, label = choose_probe({"s3_batch": "s3", "flat_eig": "flat_eig", "b_first": "b_first",
                                             "v4": "v4"}[arm], H, obs, q, world, rng, m, _reps(res))
                labels.append(label)
                if x is None:
                    break
                probes += 1
                m.charge("oracle_work_units", ORACLE_COST)
                try:
                    y = run(ep.teacher, x)
                except Exception:
                    continue
                obs.append((x, y))
                ctx = task_context(world, obs, tools)
                res, act = certify_full(obs, q, tools, world, rp, ctx, m) if arm == "full" else \
                    (certify_static(obs, q, tools, world, static_props, m), None)
                actives.append(act)
        except WorkExhausted:
            per_q.append(dict(q=qi, status="EXHAUSTED", solved=False, false_certificate=False, probes=probes,
                              work=m.total - q_start, labels=labels))
            continue
        if arm == "full" and res.status == UNIQUE and res.size in (1, 2):
            rp.record_witnesses(world, enumerate_H(obs, mechs, res.size, meter(10**12)))
        per_q.append(dict(q=qi, initial_status=initial_status, status=res.status,
                          solved=res.status == UNIQUE and vkey(res.answer) == vkey(ans),
                          false_certificate=res.status == UNIQUE and vkey(res.answer) != vkey(ans),
                          probes=probes, work=m.total - q_start, labels=labels, active=actives))
    return dict(arm=arm, world=ep.world, reuse=reuse, queries=per_q, work=m.total,
                probes=sum(q["probes"] for q in per_q), solved=sum(q["solved"] for q in per_q),
                false_certificates=sum(q["false_certificate"] for q in per_q))


def episode_grammar(ep, world):
    """The episode's declared space, fixed once from the public inputs + q1 (exactly the space the task was
    generated and selected in); later queries and probes never move it."""
    from nexus.wave25_factored import binding_grammar
    return binding_grammar([x for x, _ in ep.public] + [ep.queries[0]], maps=world["maps"])


ARMS = ("full", "s3_batch", "flat_eig", "b_first", "v4")


def run_seed(seed, *, n_per_world=30, n_val=15):
    """Five arms on the same multi-query episodes of both worlds, interleaved in a seeded order."""
    lib = learn_contracts()
    worlds = {"INT_LIST": ints_world(seed), "RECORDS": records_world(seed)}
    eps = [(n, e) for n, w in worlds.items() for e in make_episodes(w, seed + 900, n_per_world)]
    random.Random(f"w25-order:{seed}").shuffle(eps)
    # static batch-twin admission (prior wave25 design) for the baseline arms
    blib = learn_contracts()
    val = make_tasks(worlds["INT_LIST"], seed + 700, n_val, active=False, max_depth=3) + \
        make_tasks(worlds["RECORDS"], seed + 700, n_val, active=False, max_depth=3)
    tycho = tycho_admit_contracts(blib, val, worlds)
    static = {n: default_props(blib, {"F", "S", "Sort", "Agg"} | ({"Map"} if w["maps"] else set()))
              for n, w in worlds.items()}
    vault = ContractVault(lib)
    rp = ReasoningProcedure(vault, seed=seed)
    rows, cf = [], []
    for i, (n, ep) in enumerate(eps):
        w = worlds[n]
        r = run_episode(ep, w, "full", rp=rp, seed=seed)
        r.update(seed=seed, episode=i)
        rows.append(r)
        for arm in ARMS[1:]:
            r = run_episode(ep, w, arm, static_props=static[n], seed=seed)
            r.update(seed=seed, episode=i)
            rows.append(r)
        # counterfactual (reporting only): the full arm without version-space reuse, on a frozen copy of rp
        import copy
        r = run_episode(ep, w, "full", rp=copy.deepcopy(rp), reuse=False, seed=seed)
        r.update(seed=seed, episode=i, arm="full_no_reuse")
        cf.append(r)
    act = [a for a in rp.activation_log]
    return dict(seed=seed, rows=rows, counterfactual=cf, tycho_batch=tycho,
                overhead=dict(full=sum(lib.work.values()), batch=tycho["validation_overhead"]),
                vault=dict(status=vault.status_counts(),
                           proved_sound=sorted({v.prop for v in vault.validity if v.status == PROVED_SOUND}),
                           heuristics=sorted(vault.heuristics),
                           utility={p: dict(check_cost_total=u.check_cost_total, observed_work_saved=u.observed_work_saved,
                                            ema={"|".join(k): round(v, 1) for k, v in u.net_utility_ema.items()},
                                            active={"|".join(k): v for k, v in u.active_by_context.items()})
                                    for p, u in vault.utility.items()}),
                activation=dict(certifications=len(act),
                                rate={p: sum(p in a["active"] for a in act if p in a["sound"]) /
                                      max(1, sum(p in a["sound"] for a in act)) for p in PRUNE_PROPS}),
                generators={d: dict(hits=dict(rp.gen_hits[d]), tries=dict(rp.gen_tries[d])) for d in rp.gen_hits},
                static_props=static)

