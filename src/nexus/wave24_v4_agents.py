"""Wave 24 v4 agents: six cumulative arms over ONE exact program space and one work meter.

Shared space and certificate (every arm, `wave24_v4_core.solve_exact`): minimal-size programs over
plain chains of target tools (depth <= 3) and guard(c, P, r) (P a chain of depth <= 2, c a size-1
predicate of the generic phi grammar, r a public-output constant / identity / tool), size-s level =
chains of length s + guards of size s. UNIQUE iff one query output at the first nonempty level (with a
concrete verified witness); AMBIGUOUS iff two concrete programs disagree. Every arm is exact over this
space, so learning can change WORK (and, under the per-task budget and probe budget, SOLVES) but never
the certified verdict of a completed level. Arms differ only in how they search and probe:

  1 literal_fixed_baseline         fixed op order, no Popper, fixed generate-and-test guard schedule
                                   (every (P, c, r) executed), no early ambiguity stop, no probes.
  2 abstractions_fixed_refinement  + Popper (sound FD nogoods + constraint-based guard generation),
                                   source role schemas (anti-unified role n-grams, homomorphic role binding
                                   incl. Procedure C algebraic roles) ordering ops, sound early ambiguity
                                   stop, fixed designed probes (full preserving scan, propose_refinement).
  3 learned_refinement_ttt_trm     + TTT fast memory M_t (online logistic memory, reset per family) ranking
                                   partials / predicate families / recoveries / probe families, online role
                                   bigrams, TRM-style iterative probe revision (each probe outcome updates the
                                   shared M_t that designs the next probe).
  4 full_nexus_reusable_procedures + Library 2 procedures mined from source trajectories (prior for M_t,
                                   persistent across families), meta-policy (designed vs cheap random probe
                                   per symptom) and DiscoRL-style meta-learned M_t step size, admitted by the
                                   Tycho gate on source validation tasks, transfer-aware source curriculum.
  5 amnesiac_no_source_control     arm-4 code, zero source training.
  6 independent_proposal_ablation  arm 4 with TRM/designed probes replaced by independent random probes and
                                   M_t-free (seeded random) guard enumeration order; same probe budget.
Hidden answers are never read by a learner; learning signals are public fits, probe observations and
certificate status only.
"""
from __future__ import annotations

import copy
import math
import random
from collections import Counter, defaultdict

from nexus.wave24_auto_laws import AtomicForceClassifier
from nexus.wave24_domains import vkey
from nexus.wave24_quotient_core import WorkExhausted
from nexus.wave24_v4_core import (AMBIGUOUS, BOOL_FEATURES, EXHAUSTED, UNIQUE, SearchResult, algebraic_signature,
                                  meter, predicates_for, program_size, propose_refinement, solve_exact, verify)
from nexus.wave24_v4_world import PROBE_COST, oracle_for, source_domains, target_domains, task_stream

TASK_BUDGET = 60000
DOWNSTREAM_HORIZON = 100   # Tycho: declared downstream tasks over which a per-task saving is projected
ETA_GRID = (0.1, 0.3, 1.0)
DEFAULT_ETA = 0.3
FAMILIES = tuple(BOOL_FEATURES) + ("type", "key", "len", "bound")

ARMS = ("literal_fixed_baseline", "abstractions_fixed_refinement", "learned_refinement_ttt_trm",
        "full_nexus_reusable_procedures", "amnesiac_no_source_control", "independent_proposal_ablation")
EXTRA_ARMS = ("full_nexus_frozen_zero_shot",)

_BASE = dict(popper=True, schemas=True, naive=False, early=True, probes="designed", ttt=True, trm=True,
             procedures=True, meta=True, source=True, persist=True, random_order=False)
CONFIG = {
    "literal_fixed_baseline": dict(_BASE, popper=False, schemas=False, naive=True, early=False, probes=None,
                                   ttt=False, trm=False, procedures=False, meta=False, source=False,
                                   persist=False),
    "abstractions_fixed_refinement": dict(_BASE, ttt=False, trm=False, procedures=False, meta=False,
                                          persist=False),
    "learned_refinement_ttt_trm": dict(_BASE, procedures=False, meta=False, persist=False),
    "full_nexus_reusable_procedures": dict(_BASE),
    "amnesiac_no_source_control": dict(_BASE, source=False, persist=False),
    "independent_proposal_ablation": dict(_BASE, probes="random", trm=False, random_order=True),
    "full_nexus_frozen_zero_shot": dict(_BASE, frozen=True),
}


def _sig(z):
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


# --------------------------------------------------------------------------- TTT fast memory
class FastMemory:
    """M_t: logistic success memory over (context, choice); M_{t+1} = M_t - eta * grad of the log loss.

    Exact outcome records are kept alongside; the memory only ranks proposals, never certifies.
    """

    def __init__(self, eta=DEFAULT_ETA, prior=None):
        self.eta = eta
        self.w = defaultdict(float, prior or {})
        self.records = []
        self.updates = 0

    def p(self, ctx, choice):
        return _sig(self.w[(ctx, choice)] + 0.5 * self.w[("*", choice)])

    def ranker(self):
        return lambda kind, choice: -self.p(kind, choice)

    def update(self, ctx, choice, success, m):
        g = self.p(ctx, choice) - float(success)
        self.w[(ctx, choice)] -= self.eta * g
        self.w[("*", choice)] -= self.eta * 0.5 * g
        m.charge("ttt_update_work_units", 2)
        self.updates += 1
        self.records.append((ctx, choice, bool(success)))


# --------------------------------------------------------------------------- Library 2: procedures
class ProcedureLibrary:
    """Mined (symptom -> choice -> outcome) trajectories, compiled into a prior for M_t.

    Procedure A = ("predicate"/"recovery"/"partial" choices under symptom subset-failure),
    Procedure B/C = ("probe" family choices under disagreement: permutation probes vs 2-step probes).
    """

    def __init__(self):
        self.stats = defaultdict(lambda: [0, 0])
        self.admitted = {}

    def record(self, kind, choice, success):
        s = self.stats[(kind, choice)]
        s[0] += int(success)
        s[1] += 1

    def prior(self, kinds=None):
        out = {}
        for (kind, choice), (s, n) in self.stats.items():
            if kinds is not None and kind not in kinds:
                continue
            out[(kind, choice)] = math.log((s + 1) / (n - s + 1))
        return out

    def summary(self):
        return {f"{k}:{c}": list(v) for (k, c), v in sorted(self.stats.items())}


# --------------------------------------------------------------------------- Library 1: role schemas
def fine_roles(tools, probes, classifier, m):
    roles = {}
    for t in tools:
        force = classifier.classify(t.fn, probes, meter=m).force
        inv, idem, order_dep = algebraic_signature(t, probes[:6], m)
        roles[t.name] = (force, "inv" if inv else "idem" if idem else "ord" if order_dep else "-")
    return roles


def mine_schemas(witness_roles, *, min_support=3):
    """Anti-unified role n-grams (n = 2, 3) recurring on certified witnesses of >= min_support tasks."""
    support = Counter()
    for roles in witness_roles:
        grams = set()
        for n in (2, 3):
            for i in range(len(roles) - n + 1):
                grams.add(tuple(roles[i:i + n]))
        support.update(grams)
    return {g: c for g, c in support.items() if c >= min_support}


def schema_order(roles, schemas, online):
    """Op order after `prev`: ops whose role continues a schema (or an online bigram) first."""
    nxt = Counter()
    for g, c in schemas.items():
        for a, b in zip(g, g[1:]):
            nxt[(a, b)] += c
    for (a, b), c in online.items():
        nxt[(a, b)] += c

    def order(prev, ops):
        pr = roles.get(prev.name) if prev is not None else "START"
        return sorted(ops, key=lambda o: -nxt.get((pr, roles.get(o.name)), 0))
    return order


# --------------------------------------------------------------------------- meta-policy
class MetaPolicy:
    """When is invoking propose_refinement (a designed probe) cheaper than a cheap independent probe?

    Q[symptom][action] = [progress, n, work]; choose the action with the best progress rate (+-0.05), then
    the lower mean work (probe + re-certification). Ties prefer the designed probe.
    """

    ACTIONS = ("designed", "random")

    def __init__(self):
        self.q = defaultdict(lambda: {a: [0, 0, 0] for a in self.ACTIONS})
        self.decisions = Counter()

    def record(self, sym, action, ok, work):
        r = self.q[sym][action]
        r[0] += int(ok)
        r[1] += 1
        r[2] += work

    def known(self, sym):
        return all(self.q[sym][a][1] > 0 for a in self.ACTIONS)

    def choose(self, sym):
        rows = self.q[sym]
        est = {a: ((r[0] + 1) / (r[1] + 2), r[2] / max(1, r[1])) for a, r in rows.items()}
        best = max(e[0] for e in est.values())
        ok = [a for a, e in est.items() if e[0] >= best - 0.05]
        a = min(ok, key=lambda a: (est[a][1], a != "designed"))
        self.decisions[a] += 1
        return a

    def state(self):
        return {"|".join(map(str, s)): {a: list(v) for a, v in d.items()} for s, d in self.q.items()}


# --------------------------------------------------------------------------- the agent
class V4Agent:
    def __init__(self, arm, *, seed=0, eta=DEFAULT_ETA):
        self.arm = arm
        self.cfg = dict(CONFIG[arm])
        self.seed = seed
        self.classifier = AtomicForceClassifier()
        self.procedures = ProcedureLibrary()
        self.schemas = {}
        self.meta = MetaPolicy()
        self.eta = eta
        self.memory = FastMemory(eta)
        self.witness_roles = []
        self.online_bigrams = Counter()
        self.frozen = bool(self.cfg.get("frozen"))
        self._mining = False

    # ---- entering a family: zero target labels, only unlabeled probes of its tools (charged)
    def enter(self, domain, m):
        self.domain = domain
        self.tools = list(domain.tools)
        self.online_bigrams = Counter()
        probes = domain.inputs(random.Random(f"v4-probe:{domain.name}"), 10)
        if domain.messy_sampler:
            probes += domain.inputs(random.Random(f"v4-probe-messy:{domain.name}"), 4, messy=True)
        self.roles = fine_roles(self.tools, probes, self.classifier, m) if self.cfg["schemas"] else {}
        if self.cfg["ttt"]:
            prior = self.procedures.prior(kinds=set(self.procedures.admitted)) if self.cfg["procedures"] else {}
            if self.cfg["persist"]:
                if not hasattr(self, "_persist_memory"):
                    self._persist_memory = FastMemory(self.eta, prior)
                self.memory = self._persist_memory
            else:
                self.memory = FastMemory(self.eta, prior)
        self.rng = random.Random(f"v4-agent:{self.arm}:{self.seed}:{domain.name}")
        return probes

    # ---- orderings (search order only; certificates are exact)
    def _orders(self):
        if self.cfg["random_order"]:
            rng = self.rng
            return dict(order=None, order_partials=lambda p: rng.random(), order_recoveries=lambda r: rng.random(),
                        families=None)
        out = dict(order=None, order_partials=None, order_recoveries=None, families=None)
        if self.cfg["schemas"]:
            out["order"] = schema_order(self.roles, self.schemas, self.online_bigrams)
        if self.cfg["ttt"]:
            rank = self.memory.ranker()
            out["order_partials"] = lambda p: rank("partial", "raise" if "raise" in p[1] else "miss")
            out["order_recoveries"] = lambda r: rank("recovery", r[0][0])
            out["families"] = sorted(FAMILIES, key=lambda f: rank("predicate", f))
        return out

    def _exact(self, public, query, m):
        return solve_exact(public, query, self.tools, m, popper=self.cfg["popper"], early=self.cfg["early"],
                           naive=self.cfg["naive"], **self._orders())

    # ---- one task
    def solve(self, task, *, learn=True):
        m = meter(TASK_BUDGET)
        public = list(task.public)
        oracle = oracle_for(task) if (task.kind == "active" and self.cfg["probes"]) else None
        probes_used, info = 0, Counter()
        learn = learn and not self.frozen
        try:
            res = self._exact(public, task.query, m)
            while res.status == AMBIGUOUS and oracle is not None and probes_used < task.probe_budget:
                bucket = self._bucket(res, task)          # symptom before the probe
                mode = self._probe_mode(res, task, info, learn)
                x, fam = self._probe(res, public, task.query, m, info, mode)
                if x is None:
                    break
                m.charge("probe_work_units", PROBE_COST)
                probes_used += 1
                before = {vkey(h[1]) for h in res.hypotheses}
                try:
                    y = oracle(x)
                except Exception:
                    info["probe_teacher_raised"] += 1
                    self._learn("probe", fam, False, m, learn)
                    continue
                public.append((x, y))
                w0 = m.total
                res = self._exact(public, task.query, m)
                progress = res.status == UNIQUE or bool(before - {vkey(h[1]) for h in res.hypotheses})
                self._learn("probe", fam, progress, m, learn)           # TRM step: revise M_t, then redesign
                if self.cfg["meta"] and learn:
                    self.meta.record(bucket, mode, progress, m.total - w0 + PROBE_COST)
        except WorkExhausted:
            res = SearchResult(EXHAUSTED)
        verified = None
        if res.status == UNIQUE:
            prog = res.hypotheses[0][2]
            m.counts["verification_work_units"] += (len(public) + 1) * max(1, program_size(prog))
            verified = verify(prog, public, task.query, res.answer)
        if res.status in (UNIQUE, AMBIGUOUS) and learn:
            self._learn_outcome(res, m)
        return self._row(task, res, m, verified, probes_used, info)

    # ---- probes (Procedures B / C via propose_refinement)
    @staticmethod
    def _bucket(res, task):
        return ("many" if len(res.hypotheses) > 2 else "two", type(task.query).__name__)

    def _probe_mode(self, res, task, info, learn):
        mode = self.cfg["probes"]
        if mode == "designed" and self.cfg["meta"]:
            b = self._bucket(res, task)
            if self.meta.known(b) or not learn:
                mode = self.meta.choose(b)
            elif self.meta.q[b]["random"][1] == 0:
                mode = "random"          # explore the cheap alternative once per symptom bucket
        info["probe_mode_" + mode] += 1
        return mode

    def _probe(self, res, public, query, m, info, mode):
        if mode == "random":
            for _ in range(8):
                x = self.domain.inputs(self.rng, 1)[0]
                if vkey(x) != vkey(query) and all(vkey(x) != vkey(px) for px, _ in public):
                    return x, "random"
            return None, None
        rank = self.memory.ranker() if (self.cfg["ttt"] and self.cfg["trm"]) else None
        plan = propose_refinement(res.hypotheses, dict(public=public, query=query), dict(tools=self.tools),
                                  "disambiguate", TASK_BUDGET - m.total, rank=rank, m=m)
        if plan.candidate_predicate is not None:
            info["concept_" + plan.candidate_predicate.family] += 1
        if plan.distinguishing_test is None:
            return None, None
        return plan.distinguishing_test[1], plan.distinguishing_test[0]

    # ---- learning (public / observed signals only)
    def _learn(self, kind, choice, success, m, learn):
        if choice is None or not learn:
            return
        if self._mining:
            self.procedures.record(kind, choice, success)
        if self.cfg["ttt"]:
            self.memory.update(kind, choice, success, m)

    def _learn_outcome(self, res, m):
        for _, _, prog in res.hypotheses:
            for t in prog:
                if t.kind == "guard":
                    fam = _guard_family(t)
                    self._learn("predicate", fam, True, m, True)
                    rk = "tool" if t.cost > 1 + len(t.parts) else ("id" if t.name.endswith(":id]") else "const")
                    self._learn("recovery", rk, True, m, True)
        if res.status == UNIQUE and self.cfg["schemas"] and self.cfg["ttt"]:
            prog = res.hypotheses[0][2]
            rs = [self.roles.get(t.name, ("guard", "-")) for t in prog]
            self.witness_roles.append(rs)
            for a, b in zip(["START"] + rs, rs):
                self.online_bigrams[(a, b)] += 1
        elif res.status == UNIQUE and self._mining:
            prog = res.hypotheses[0][2]
            self.witness_roles.append([self.roles.get(t.name, ("guard", "-")) for t in prog])

    def _row(self, task, res, m, verified, probes_used, info):
        answers = {vkey(h[1]) for h in res.hypotheses}
        truth = vkey(task.answer)
        if task.gold == "AMBIGUOUS":
            # Correct abstention. With the sound early stop only two disagreeing witnesses are kept, so
            # truth-in-set is checked (G1 witness conservation) only for arms that complete each level.
            solved = res.status == AMBIGUOUS
        else:
            solved = res.status == UNIQUE and verified is True and vkey(res.answer) == truth
        false_cert = res.status == UNIQUE and verified is True and vkey(res.answer) != truth
        return dict(arm=self.arm, domain=task.domain, kind=task.kind, gold=task.gold, teacher=task.teacher,
                    status=res.status, solved=bool(solved), false_certificate=bool(false_cert),
                    truth_in_witness_set=truth in answers, complete_levels=not self.cfg["early"],
                    n_hypotheses=len(answers), work=m.total,
                    work_by=dict(m.counts), evaluations=res.evaluations, pruned_popper=res.pruned_popper,
                    probes=probes_used, witness=list(res.witness), size=res.size, info=dict(info))


def _guard_family(t):
    pred = t.name[len("guard["):].split("?")[0]
    for f in FAMILIES:
        if pred.startswith(f + "=") or pred.startswith(f):
            return f
    if pred.startswith(("has:", "lacks:")):
        return "key"
    if pred.startswith(("max_num", "min_num")):
        return "bound"
    return "other"


# --------------------------------------------------------------------------- Tycho gate
def tycho_admit(saving_per_task, validation_work, false_certs, solved_with, solved_without,
                horizon=DOWNSTREAM_HORIZON):
    """Net benefit = projected downstream saving - every unit spent validating; admit only if positive,
    certificate-clean and not losing solves on the validation tasks."""
    net = saving_per_task * horizon - validation_work
    return net, net > 0 and false_certs == 0 and solved_with >= solved_without


# --------------------------------------------------------------------------- reference labels
def reference_verdict(task, tools):
    """Exact reference over the shared space (no Popper, no early stop, constrained guard enumeration)."""
    return solve_exact(task.public, task.query, list(tools), meter(10**9), popper=False, early=False)


def predicates_split(pass_xs, fail_xs):
    return predicates_for(pass_xs, fail_xs, max_size=1)


def labelled_stream(domain, seed):
    """Generated stream; gold = the exact reference verdict over the shared space (task dropped if the
    teacher's answer is not in the reference witness set, i.e. the task contradicts the size prior).
    Active tasks keep gold UNIQUE (the oracle can resolve them)."""
    from dataclasses import replace
    out = []
    for t in task_stream(domain, seed, predicates_split):
        r = reference_verdict(t, domain.tools)
        hyps = {vkey(h[1]) for h in r.hypotheses}
        if vkey(t.answer) not in hyps:
            continue
        gold = "UNIQUE" if (t.kind == "active" or r.status == UNIQUE) else "AMBIGUOUS"
        out.append(replace(t, gold=gold))
    return out


# --------------------------------------------------------------------------- source training
def run_stream(agent, domain, tasks, *, learn=True):
    m = meter(10**12)
    agent.enter(domain, m)
    rows = [agent.solve(t, learn=learn) for t in tasks]
    return rows, m.total + sum(r["work"] for r in rows)


def source_training(seed, *, n_val=8):
    """Library 1 + Library 2 mining, Tycho admission, meta-policy and DiscoRL-style step size on sources.

    Returns (trained agent, cost ledger, report). Source streams, validation streams and target streams
    use disjoint generator seeds (seed+4000 / seed+5000 / seed+6000).
    """
    ledger = Counter()
    doms = source_domains()
    streams = {d.name: labelled_stream(d, seed + 4000) for d in doms}
    vals = {d.name: labelled_stream(d, seed + 5000)[:n_val] for d in doms}

    def mine(batches):
        ag = V4Agent("learned_refinement_ttt_trm", seed=seed)
        ag._mining = True
        for d, tasks in batches:
            _, w = run_stream(ag, d, tasks)
            ledger["source_practice_work"] += w
        return ag

    def val_work(procs, d, tasks, admitted=("predicate", "recovery", "partial", "probe")):
        ag = V4Agent("full_nexus_reusable_procedures", seed=seed)
        ag.cfg.update(meta=False, persist=False)
        ag.procedures = procs
        ag.procedures.admitted = {k: 1 for k in admitted}
        rows, w = run_stream(ag, d, tasks, learn=False)
        return w, sum(r["false_certificate"] for r in rows), sum(r["solved"] for r in rows), rows

    # transfer-aware curriculum: a practice batch from family A is kept only if mining it lowers the
    # validation work on family B (cross-domain transfer benefit), charged
    base = {}
    for d in doms:
        base[d.name] = val_work(ProcedureLibrary(), d, vals[d.name])
        ledger["curriculum_validation_work"] += base[d.name][0]
    keep, curriculum = [], []
    for d in doms:
        other = next(o for o in doms if o.name != d.name)
        tasks = streams[d.name]
        for i, b in enumerate([tasks[0::2], tasks[1::2]]):
            ag = mine([(d, b)])
            w, fc, solved, _ = val_work(ag.procedures, other, vals[other.name])
            ledger["curriculum_validation_work"] += w
            benefit = base[other.name][0] - w
            curriculum.append(dict(source=d.name, batch=i, tasks=len(b), transfer_benefit=benefit, false_certs=fc))
            if benefit > 0 and fc == 0 and solved >= base[other.name][2]:
                keep.append((d, b))
    if not keep:
        keep = [(d, streams[d.name]) for d in doms]
    trained = mine(keep)
    trained.schemas = mine_schemas(trained.witness_roles)
    # Tycho gate: admit a procedure kind iff its projected net benefit on source validation is positive
    admitted, tycho = {}, {}
    for kind in ("predicate", "recovery", "partial", "probe"):
        with_k = without = fc_k = n = s_with = s_without = 0
        for d in doms:
            p = ProcedureLibrary()
            p.stats = defaultdict(lambda: [0, 0], {k: v for k, v in trained.procedures.stats.items()
                                                   if k[0] == kind})
            w1, fc1, sv1, rows = val_work(p, d, vals[d.name], admitted=(kind,))
            with_k, without, fc_k, n = with_k + w1, without + base[d.name][0], fc_k + fc1, n + len(rows)
            s_with, s_without = s_with + sv1, s_without + base[d.name][2]
        ledger["tycho_validation_work"] += with_k
        per_task = (without - with_k) / max(1, n)
        net, ok = tycho_admit(per_task, with_k, fc_k, s_with, s_without)
        tycho[kind] = dict(saving_per_task=per_task, validation_work=with_k, net_benefit=net,
                           false_certificates=fc_k, solved_with=s_with, solved_without=s_without, admitted=ok)
        if ok:
            admitted[kind] = 1
    trained.procedures.admitted = admitted
    # meta-policy + DiscoRL-style meta-learned M_t step size (grid) on the source validation streams
    best = None
    for eta in ETA_GRID:
        ag = V4Agent("full_nexus_reusable_procedures", seed=seed, eta=eta)
        ag.procedures = trained.procedures
        tot = 0
        for d in doms:
            _, w = run_stream(ag, d, vals[d.name])
            tot += w
        ledger["meta_training_work"] += tot
        if best is None or tot < best[0]:
            best = (tot, eta, ag.meta)
    trained.eta, trained.meta = best[1], best[2]
    trained._mining = False
    report = dict(curriculum=curriculum, kept_batches=[(d.name, len(b)) for d, b in keep],
                  schemas={">".join(map(str, g)): c for g, c in sorted(trained.schemas.items(),
                                                                       key=lambda kv: -kv[1])[:20]},
                  n_schemas=len(trained.schemas), procedures=trained.procedures.summary(), tycho=tycho,
                  admitted=sorted(admitted), eta=trained.eta, meta=trained.meta.state(),
                  source_tasks={k: len(v) for k, v in streams.items()},
                  validation_tasks={k: len(v) for k, v in vals.items()})
    return trained, dict(ledger), report


def make_arm(arm, seed, trained):
    a = V4Agent(arm, seed=seed)
    c = CONFIG[arm]
    if c["source"]:
        if c["schemas"]:
            a.schemas = dict(trained.schemas)
        if c["procedures"]:
            a.procedures = copy.deepcopy(trained.procedures)
            a.meta = copy.deepcopy(trained.meta)
            a.eta = trained.eta
    return a


def source_cost(arm, ledger):
    """Source acquisition charged to an arm: practice work for any source product, plus curriculum, Tycho
    and meta-training work for arms that use procedures / meta-policy."""
    c = CONFIG[arm]
    if not c["source"]:
        return 0
    base = ledger.get("source_practice_work", 0)
    if c["procedures"] or c["meta"]:
        return base + sum(v for k, v in ledger.items() if k != "source_practice_work")
    return base


def run_seed(seed, *, arms=ARMS + EXTRA_ARMS, families=None):
    trained, ledger, report = source_training(seed)
    fams = [d for d in target_domains() if families is None or d.name in families]
    streams = {d.name: labelled_stream(d, seed + 6000) for d in fams}
    rows, setup = [], Counter()
    for arm in arms:
        agent = make_arm(arm, seed, trained)
        for d in fams:
            m = meter(10**12)
            agent.enter(d, m)
            setup[arm] += m.total
            rows += [dict(agent.solve(t), seed=seed) for t in streams[d.name]]
    return dict(seed=seed, rows=rows, setup_work=dict(setup), source_ledger=ledger, source_report=report,
                source_cost={a: source_cost(a, ledger) for a in arms}, popper_audit=popper_audit(streams, fams),
                stream_sizes={k: len(v) for k, v in streams.items()},
                kinds={k: dict(Counter(f"{t.kind}/{t.gold}" for t in v)) for k, v in streams.items()})


def popper_audit(streams, fams):
    """Gate 4: the identical exhaustive certifier with and without Popper (no early stop) on every target task."""
    out = []
    for d in fams:
        for t in streams[d.name]:
            rs = [solve_exact(t.public, t.query, d.tools, meter(10**9), popper=p, early=False) for p in (False, True)]
            a, b = rs
            same = a.status == b.status and {vkey(h[1]) for h in a.hypotheses} == {vkey(h[1]) for h in b.hypotheses}
            out.append(dict(domain=d.name, kind=t.kind, evals_off=a.evaluations, evals_on=b.evaluations,
                            work_off=a.work, work_on=b.work, same_verdict=same, status=a.status))
    return out
