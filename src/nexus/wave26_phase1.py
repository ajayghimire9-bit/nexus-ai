"""Wave 26 Phase 1: where does learning pay? Oracle-cost x world-complexity crossover map.

Reuses the wave25 stack unchanged: exact certifier (v4 Searcher), S1-Auto contracts + dual-ledger vault,
answer-directed S3 objective, revisable anticipatory controller, S2 mined diagnostic rules.

Worlds: records with F fields (1 bool, 1 score, F-3 distractors correlated with the score, 1 tag; names
randomised per seed), binding grammar size G (thresholds / k values), teacher depth d. Episodes are
multi-query (q1 selected AMBIGUOUS on the public pairs, q2 from the sampler). The oracle costs c_oracle units
per probe. Depth 4-5 cells are not run: the exact certifier enumerates to depth 3 and depth-4 enumeration is
outside the session budget (reported as infeasible, not silently dropped).

Arms (all exact-certified; differ in contracts and probe policy):
  exact_eig_enum        no contracts, flat exact EIG over standard perturbations
  s2_transferred_rule   no contracts, mined S2 F/S rule probe when it applies, else flat exact EIG
  myopic_s3             no contracts, answer-directed S3
  revisable_controller  no contracts, revisable anticipatory controller (cost-aware lookahead)
  full_nexus_vault      vault contracts + revisable controller + persistent V_t + S2 rule when its measured
                        design cost is below c_oracle
Fully loaded = episode work (probes at c_oracle) + amortised one-time costs (contract learning for the vault
arm; S2 mining + rule learning + scope check for the two rule arms) x episodes / HORIZON.
"""
from __future__ import annotations

import random
from collections import Counter

from nexus.wave24_domains import vkey
from nexus.wave24_quotient_core import WorkExhausted
from nexus.wave24_v4_core import AMBIGUOUS, UNIQUE, Searcher, meter
from nexus.wave25_anticipate import AnticipatoryProcedure
from nexus.wave25_contracts import learn_contracts
from nexus.wave25_factored import (FIELD_POOL, PROBE_BUDGET, TASK_BUDGET, _edit_space, _pairs_by_swap,
                                   _value_pool, binding_grammar, collect_pair_data, ints_world, mine_rules,
                                   phi_holds, run, scope_check)
from nexus.wave25_s3 import _H, _reps, choose_probe, cond_info, enumerate_H, outputs
from nexus.wave25_vault import ContractVault, Episode, ReasoningProcedure, certify_full, certify_static, task_context

HORIZON = 100
ORACLE_COSTS = (20, 200, 2_000, 20_000)
GRAMMARS = {"small": dict(n_thresholds=2, ks=(1, 2)), "medium": dict(n_thresholds=3, ks=(1, 2, 3)),
            "large": dict(n_thresholds=5, ks=(1, 2, 3, 4))}
CELLS = (("d2", 2, 3, "small"), ("d2", 2, 5, "medium"), ("d2", 2, 8, "large"), ("d3", 3, 5, "medium"))
INFEASIBLE = (("d4", 4), ("d5", 5))
MAX_D = 3
ARMS = ("exact_eig_enum", "s2_transferred_rule", "myopic_s3", "revisable_controller", "full_nexus_vault")
COST_AWARE = ("revisable_controller", "full_nexus_vault")


def records_world_f(seed, n_fields):
    rng = random.Random(f"w26-names:{seed}:{n_fields}")
    names = rng.sample(FIELD_POOL + tuple(f"x{i}" for i in range(12)), n_fields)
    fb, fs, ft, dist = names[0], names[1], names[2], names[3:]

    def sample(r, n=None):
        out = []
        for _ in range(n or r.randint(3, 5)):
            s = r.randint(0, 9)
            rec = {fb: r.random() < 0.6, fs: s, ft: r.choice(("a", "b", "c"))}
            for j, d in enumerate(dist):
                rec[d] = max(0, min(9, s + r.choice((-1, 0, 0, 1)) * (j + 1)))
            out.append(rec)
        return out
    return dict(name=f"RECORDS_F{n_fields}", sample=sample, maps=False, fields=tuple(names))


def grammar(inputs, G):
    return [t for t in binding_grammar(inputs, maps=False, **GRAMMARS[G]) if t.fn.role != "Agg"]


def make_episodes(world, seed, n, depth, G):
    rng = random.Random(f"w26-p1:{world['name']}:{seed}:{depth}:{G}")
    out, tries = [], 0
    while len(out) < n and tries < n * 400:
        tries += 1
        xs = [world["sample"](rng) for _ in range(4)]
        tools = grammar(xs, G)
        mechs = [t.fn for t in tools]
        chain = tuple(rng.choice(mechs) for _ in range(depth))
        try:
            ys = [run(chain, x) for x in xs]
        except Exception:
            continue
        if len({vkey(y) for y in ys[:3]}) < 2 or any(vkey(x) == vkey(y) for x, y in zip(xs, ys)):
            continue
        public = tuple(zip(xs[:3], ys[:3]))
        res = Searcher(public, xs[3], tools, popper=True, m=meter(TASK_BUDGET), partial_depth=0,
                       max_depth=depth).run_to(depth)
        if res.size != depth or res.status != AMBIGUOUS or vkey(ys[3]) not in {vkey(h[1]) for h in res.hypotheses}:
            continue
        for _ in range(20):
            q2 = world["sample"](rng)
            if vkey(q2) in {vkey(x) for x in xs}:
                continue
            try:
                a2 = run(chain, q2)
            except Exception:
                continue
            out.append((Episode(world["name"], public, (xs[3], q2), (ys[3], a2), chain), xs[:3] + [xs[3]]))
            break
    return out


# --------------------------------------------------------------------------- S2 rule probe (no fallback inside)
def rule_probe(res, public, query, world, rules, m):
    seen = {vkey(x) for x, _ in public} | {vkey(query)}
    progs = [p for rest, (p, v) in res.searcher.graph.classes.get(tuple(res.searcher.targets), {}).items()
             if len(p) == res.size]
    for ms, mt in _pairs_by_swap(res, public, m):
        rule = rules.get((ms.role, mt.role)) or rules.get((mt.role, ms.role))
        if rule is None:
            continue
        first, second = (ms, mt) if rules.get((ms.role, mt.role)) else (mt, ms)
        for x in _edit_space([x for x, _ in public] + [query], list(world["fields"]), _value_pool(public, query)):
            m.charge("probe_design_work_units", 2 * len(x))
            if vkey(x) in seen or not phi_holds(rule, first, second, x):
                continue
            outs = set()
            for p in progs:
                m.charge("probe_design_work_units", len(p))
                try:
                    outs.add(vkey(run([t.fn for t in p], x)))
                except Exception:
                    outs.add("__raise__")
            if len(outs) > 1:
                return x
    return None


class NoContractProcedure(AnticipatoryProcedure):
    def select_active_contracts(self, ctx, roles):
        self.activation_log.append(dict(ctx=list(ctx), sound=[], active=[]))
        return []


class FullProcedure(AnticipatoryProcedure):
    """Vault + revisable controller; the S2 rule probe is tried first while its measured design cost per probe
    is below c_oracle (utility-gated, not a hand threshold)."""

    def __init__(self, *a, rules=None, **kw):
        super().__init__(*a, **kw)
        self.rules = rules or {}
        self.rule_cost, self.rule_n = 0.0, 0

    def schedule_probe_full(self, res, H, yq, public, query, world, rng, m):
        mean = self.rule_cost / self.rule_n if self.rule_n else 0.0
        if self.rules and mean < self.oracle_cost:
            w0 = m.total
            x = rule_probe(res, public, query, world, self.rules, m)
            self.rule_cost += m.total - w0
            self.rule_n += 1
            if x is not None and cond_info(yq, outputs(H, x, m)) > 0:
                self.lookahead_log["rule_probes"] += 1
                return x, "rule"
        return self.schedule_probe(H, yq, public, query, world, rng, m)


def run_episode(ep, world, tools, arm, c_oracle, *, rp=None, rules=None, seed=0):
    m = meter(10**12)
    mechs = [t.fn for t in tools]
    obs = list(ep.public)
    rng = random.Random(f"w26-p1-run:{seed}:{arm}:{vkey(ep.queries[0])}")
    per_q = []
    nexus = arm in COST_AWARE
    if nexus:
        rp.oracle_cost = c_oracle
    for qi, (q, ans) in enumerate(zip(ep.queries, ep.answers)):
        probes, labels, q0 = 0, [], m.total
        try:
            def cert():
                if nexus:
                    return certify_full(obs, q, tools, world, rp, task_context(world, obs, tools), m)[0]
                return certify_static(obs, q, tools, world, None, m)
            res = cert()
            initial = res.status
            if qi > 0 and nexus:
                rp.qm.observe_followup(res.status == AMBIGUOUS, rp.last_pool_ambiguity)
            while res.status == AMBIGUOUS and probes < PROBE_BUDGET:
                H = enumerate_H(obs, mechs, res.size, m) if res.size in (1, 2) else \
                    [tuple(t.fn for t in p) for p in _reps(res)]
                yq = outputs(H, q, m)
                x, label = None, "none"
                if arm == "s2_transferred_rule":
                    x = rule_probe(res, obs, q, world, rules, m)
                    label = "rule" if x is not None else "none"
                    if x is None:
                        x, label = choose_probe("flat_eig", H, obs, q, world, rng, m, _reps(res))
                elif arm == "exact_eig_enum":
                    x, label = choose_probe("flat_eig", H, obs, q, world, rng, m, _reps(res))
                elif arm == "myopic_s3":
                    x, label = choose_probe("s3", H, obs, q, world, rng, m, _reps(res))
                elif arm == "full_nexus_vault":
                    x, label = rp.schedule_probe_full(res, H, yq, obs, q, world, rng, m)
                else:
                    x, label = rp.schedule_probe(H, yq, obs, q, world, rng, m)
                labels.append(label)
                if x is None:
                    break
                probes += 1
                m.charge("oracle_work_units", c_oracle)
                try:
                    y = run(ep.teacher, x)
                except Exception:
                    continue
                obs.append((x, y))
                w0 = m.total
                res = cert()
                if nexus:
                    rp.cert_work += m.total - w0
                    rp.cert_n += 1
        except WorkExhausted:
            per_q.append(dict(q=qi, status="EXHAUSTED", solved=False, false_certificate=False, probes=probes,
                              work=m.total - q0, labels=labels))
            continue
        per_q.append(dict(q=qi, initial_status=initial, status=res.status,
                          solved=res.status == UNIQUE and vkey(res.answer) == vkey(ans),
                          false_certificate=res.status == UNIQUE and vkey(res.answer) != vkey(ans),
                          probes=probes, work=m.total - q0, labels=labels))
    if nexus:
        rp.qm.end_episode(len(ep.queries) - 1)
    return dict(arm=arm, c_oracle=c_oracle, queries=per_q, work=m.total, work_by=dict(m.counts),
                probes=sum(q["probes"] for q in per_q), solved=sum(q["solved"] for q in per_q),
                false_certificates=sum(q["false_certificate"] for q in per_q))


def one_time_costs(seed):
    """S2 rule mining on the int-list source world (charged), and S1-Auto contract learning (charged)."""
    data, w_mine = collect_pair_data(ints_world(seed), seed, 30)
    rules, w_learn = mine_rules(data)
    kept, w_scope = {}, 0
    for k, r in rules.items():
        if r is not None:
            checked, viol = scope_check(r)
            w_scope += checked
            if viol == 0:
                kept[k] = r
    lib = learn_contracts()
    return kept, dict(s2_mining=w_mine + w_learn + w_scope, contract_learning=sum(lib.work.values()))


def run_cell(seed, cell, *, n_eps, costs=ORACLE_COSTS, rules=None, once=None):
    label, depth, n_fields, G = cell
    world = records_world_f(seed, n_fields)
    eps = make_episodes(world, seed + 31 * depth + n_fields, n_eps, depth, G)
    rows = []
    for arm in ARMS:
        cs = costs if arm in COST_AWARE else (0,)
        for c in cs:
            if arm == "revisable_controller":
                rp = NoContractProcedure(ContractVault(learn_contracts()), seed=seed)
            elif arm == "full_nexus_vault":
                rp = FullProcedure(ContractVault(learn_contracts()), seed=seed, rules=rules)
            else:
                rp = None
            for i, (ep, inputs) in enumerate(eps):
                tools = grammar(inputs, G)
                r = run_episode(ep, world, tools, arm, c, rp=rp, rules=rules, seed=seed)
                r.update(seed=seed, cell=f"{label}/F{n_fields}/{G}", episode=i)
                rows.append(r)
    return rows, len(eps)


def price(rows, n_eps, once, c):
    """Fully-loaded cost per arm at oracle cost c (cost-independent arms re-priced from their probe counts)."""
    out = {}
    for arm in ARMS:
        rs = [r for r in rows if r["arm"] == arm and (r["c_oracle"] == c if arm in COST_AWARE else True)]
        work = sum(r["work"] + (r["probes"] * c if arm not in COST_AWARE else 0) for r in rs)
        amort = 0.0
        if arm in ("s2_transferred_rule", "full_nexus_vault"):
            amort += once["s2_mining"] * n_eps / HORIZON
        if arm == "full_nexus_vault":
            amort += once["contract_learning"] * n_eps / HORIZON
        out[arm] = dict(episodes=len(rs), solved=sum(r["solved"] for r in rs), probes=sum(r["probes"] for r in rs),
                        false=sum(r["false_certificates"] for r in rs), work=work, amortised=amort,
                        fully_loaded=work + amort)
    return out
