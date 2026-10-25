"""Wave 25 spike (S1 + S2): factored mechanisms x bindings, tier-1 abstract pruning, learned
non-commutativity diagnostic rules. Dev seeds only; design: docs/NEXUS_WAVE25_FACTORED_DISCOVERY_DESIGN.md.

Reused: `wave24_v4_core.Searcher` (ObsEGraph certificate, Popper FD nogoods, new `abstract` hook),
`propose_refinement` / `candidate_probes` (the v4 designed-probe baseline), `wave24_domains.Tool/vkey`.

Mechanisms are NEXUS's own white-box operators with slots; a bound instance is a Tool:
  F[p]      keep items with p(item)                         (order kept)
  S[k, o]   the first k items under order o, output in o-order (stable by position)
  Sort[o]   all items in o-order
  Map[g]    g applied to every item                          (source world only)
  Agg[r]    count / sum(path) / max(path) -> scalar
Slots are bound from a domain-free grammar instantiated from the task's own unlabeled inputs: item paths
are discovered (the item itself for ints, record keys for records - names randomised per seed), never
named by hand.
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations, product

from nexus.wave24_domains import Tool, vkey
from nexus.wave24_quotient_core import WorkExhausted
from nexus.wave24_v4_core import AMBIGUOUS, UNIQUE, Searcher, candidate_probes, meter, propose_refinement

ORACLE_COST = 20
PROBE_BUDGET = 3
MAX_DEPTH = 3
TASK_BUDGET = 400_000


# --------------------------------------------------------------------------- items, paths, bindings
def paths_of(items):
    """Observable item paths: '.' for scalar items, sorted common keys for records."""
    recs = [i for i in items if isinstance(i, dict)]
    if not recs:
        return ["."]
    keys = set(recs[0])
    for r in recs[1:]:
        keys &= set(r)
    return sorted(keys)


def get(item, path):
    return item if path == "." else item[path]


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


@dataclass(frozen=True)
class Pred:
    path: str
    op: str            # ge | le | eq
    val: object

    def __call__(self, item):
        v = get(item, self.path)
        if self.op == "eq":
            return v == self.val
        if not _num(v):
            return False
        return v >= self.val if self.op == "ge" else v <= self.val

    def name(self):
        return f"{self.path}{'>=' if self.op == 'ge' else '<=' if self.op == 'le' else '=='}{self.val!r}"


@dataclass(frozen=True)
class Order:
    path: str          # "#" = position
    desc: bool = False

    def key(self, indexed):
        i, item = indexed
        if self.path == "#":
            return (i,)
        v = get(item, self.path)
        return ((-v if self.desc else v), i)

    def name(self):
        return "pos" if self.path == "#" else f"{'-' if self.desc else '+'}{self.path}"


def _ordered(xs, o):
    return [it for _, it in sorted(enumerate(xs), key=o.key)]


@dataclass(frozen=True)
class Mech:
    role: str          # F | S | Sort | Map | Agg
    slots: tuple       # bound slot values

    def __call__(self, xs):
        if not isinstance(xs, list):
            raise TypeError("list mechanism on a scalar")
        if self.role == "F":
            return [x for x in xs if self.slots[0](x)]
        if self.role == "S":
            k, o = self.slots
            return _ordered(xs, o)[:k]
        if self.role == "Sort":
            return _ordered(xs, self.slots[0])
        if self.role == "Map":
            return [MAPS[self.slots[0]](x) for x in xs]
        r, path = self.slots
        if r == "count":
            return len(xs)
        vals = [get(x, path) for x in xs]
        if not all(_num(v) for v in vals):
            raise TypeError("non-numeric aggregate")
        return sum(vals) if r == "sum" else max(vals)

    def name(self):
        if self.role == "F":
            return f"F[{self.slots[0].name()}]"
        if self.role == "S":
            return f"S[{self.slots[0]},{self.slots[1].name()}]"
        if self.role == "Sort":
            return f"Sort[{self.slots[0].name()}]"
        if self.role == "Map":
            return f"Map[{self.slots[0]}]"
        return f"Agg[{self.slots[0]}:{self.slots[1]}]"


MAPS = {"inc": lambda x: x + 1, "dbl": lambda x: 2 * x, "neg": lambda x: -x}


def tool_of(mech):
    return Tool(mech.name(), mech, mech.name(), kind="primitive", parts=(mech.role,))


def binding_grammar(inputs, *, maps=False, ks=(1, 2, 3), n_thresholds=3):
    """Bound mechanism instances from the unlabeled inputs (grammar 𝔅), deterministic order."""
    items = [it for x in inputs if isinstance(x, list) for it in x]
    paths = paths_of(items)
    preds, orders = [], [Order("#")]
    for p in paths:
        vals = [get(i, p) for i in items]
        if all(isinstance(v, bool) for v in vals):
            preds += [Pred(p, "eq", True), Pred(p, "eq", False)]
        elif all(_num(v) for v in vals):
            u = sorted(set(vals))
            qs = sorted({u[round(j * (len(u) - 1) / max(1, n_thresholds - 1))] for j in range(n_thresholds)}) if u else []
            preds += [Pred(p, op, q) for q in qs for op in ("ge", "le")]
            orders += [Order(p, False), Order(p, True)]
        else:
            preds += [Pred(p, "eq", c) for c in sorted({v for v in vals if isinstance(v, (str, int))}, key=repr)[:4]]
    mechs = [Mech("F", (p,)) for p in preds]
    mechs += [Mech("S", (k, o)) for k in ks for o in orders]
    mechs += [Mech("Sort", (o,)) for o in orders if o.path != "#"]
    if maps:
        mechs += [Mech("Map", (g,)) for g in MAPS]
    mechs += [Mech("Agg", ("count", "."))] + [Mech("Agg", (r, p)) for p in paths for r in ("sum", "max")
                                              if all(_num(get(i, p)) for i in items)]
    return [tool_of(mc) for mc in mechs]


# --------------------------------------------------------------------------- worlds
FIELD_POOL = ("qa", "zu", "mek", "tov", "ril", "sna", "bo", "kel", "vix", "dar", "lum", "pei")


def records_world(seed):
    """Records with randomised field names: one bool, two correlated ints, one str (roles unknown)."""
    rng = random.Random(f"w25-names:{seed}")
    fb, fs, fd, ft = rng.sample(FIELD_POOL, 4)

    def sample(r, n=None):
        n = n or r.randint(3, 5)
        out = []
        for _ in range(n):
            s = r.randint(0, 9)
            out.append({fb: r.random() < 0.6, fs: s, fd: max(0, min(9, s + r.choice((-1, 0, 0, 1)))),
                        ft: r.choice(("a", "b", "c"))})
        return out
    return dict(name="RECORDS", sample=sample, maps=False, fields=(fb, fs, fd, ft))


def ints_world(seed):
    def sample(r, n=None):
        return [r.randint(-3, 9) for _ in range(n or r.randint(3, 5))]
    return dict(name="INT_LIST", sample=sample, maps=True, fields=(".",))


@dataclass(frozen=True)
class Task:
    world: str
    public: tuple
    query: object
    answer: object = field(compare=False)
    teacher: tuple = field(compare=False, default=())       # Mech chain (oracle / grading only)
    kind: str = "passive"


def run(chain, x):
    for m in chain:
        x = m(x)
    return x


def make_tasks(world, seed, n, *, active=False, max_depth=2):
    """Teacher = random bound chain over the grammar of its own sampled inputs; for active=True keep only
    tasks whose exact certificate on the public pairs is AMBIGUOUS (selected, never authored)."""
    rng = random.Random(f"w25-tasks:{world['name']}:{seed}:{active}")
    out, tries = [], 0
    while len(out) < n and tries < n * 400:
        tries += 1
        xs = [world["sample"](rng) for _ in range(4)]
        tools = binding_grammar(xs, maps=world["maps"])
        mechs = [t.fn for t in tools if t.fn.role != "Agg"]
        depth = rng.choice(range(1, max_depth + 1)) if not active else 2
        chain = tuple(rng.choice(mechs) for _ in range(depth))
        if active and {c.role for c in chain} != {"F", "S"}:
            if rng.random() < 0.7:        # most active tasks are F/S pairs, the rest are other pairs
                continue
        try:
            ys = [run(chain, x) for x in xs]
        except Exception:
            continue
        if len({vkey(y) for y in ys[:3]}) < 2 or any(vkey(x) == vkey(y) for x, y in zip(xs, ys)):
            continue
        public = tuple(zip(xs[:3], ys[:3]))
        res = Searcher(public, xs[3], tools, popper=True, m=meter(TASK_BUDGET), partial_depth=0,
                       max_depth=depth).run_to(depth)
        if res.size != depth or vkey(ys[3]) not in {vkey(h[1]) for h in res.hypotheses}:
            continue
        if active != (res.status == AMBIGUOUS):
            continue
        out.append(Task(world["name"], public, xs[3], ys[3], chain, "active" if active else "passive"))
    return out


# --------------------------------------------------------------------------- S1: tier-1 abstract rules
def _closure(values, maps, r):
    """Every value reachable from `values` by <= r applications of the bound item maps (exact set)."""
    seen, frontier = set(values), set(values)
    for _ in range(r):
        nxt = set()
        for v in frontier:
            for g in maps:
                nxt.add(g(v))
        frontier = nxt - seen
        seen |= nxt
    return seen


RULES = ("length", "distinct", "provenance")


def make_abstract(rules, *, maps=()):
    """Tier-1 abstract reachability over the mechanism IR (proved, see docstring of each rule):

    length:     every list mechanism maps a list to a list no longer (F, S, Sort, Map) or to a scalar
                (Agg); no mechanism maps a scalar to anything. So a list target needs a list state with
                len(state) >= len(target); a scalar state must already equal a scalar target.
    distinct:   F, S, Sort return sub-multisets and Map applies a function item-wise, so the number of
                distinct items never increases.
    provenance: without Map, output items are a sub-multiset of the state's items; with Map, every target
                item lies in the closure of the state's items under <= r applications of the bound maps.
    Unit (same as a mechanism application in Searcher): one operation on one value. Each rule test on one
    public pair costs 1; the Map closure costs 1 more (charged).
    """
    rules = set(rules)

    def prune(pub, targets, r, m):
        for v, y in zip(pub, targets):
            if isinstance(y, list):
                if not isinstance(v, list):
                    return True
                m.charge("abstract_work_units", 1)
                if "length" in rules and len(v) < len(y):
                    return True
                if r == 0:
                    continue
                if "distinct" in rules:
                    m.charge("abstract_work_units", 1)
                    if len({vkey(i) for i in v}) < len({vkey(i) for i in y}):
                        return True
                if "provenance" in rules:
                    m.charge("abstract_work_units", 1)
                    if not maps:
                        have = Counter(vkey(i) for i in v)
                        need = Counter(vkey(i) for i in y)
                        if any(have[k] < c for k, c in need.items()):
                            return True
                    elif all(isinstance(i, int) for i in v) and all(isinstance(i, int) for i in y):
                        clo = _closure(set(v), list(maps), r)
                        m.charge("abstract_work_units", 1)
                        if any(i not in clo for i in y):
                            return True
            else:
                m.charge("abstract_work_units", 1)
                if not isinstance(v, list) and vkey(v) != vkey(y):
                    return True
                if isinstance(v, list) and r == 0:
                    return True
        return False
    return prune


def task_grammar(task, world):
    """The declared space of a task: the grammar instantiated once from its public inputs + query (kept
    fixed while probes are added, so observations never move the space)."""
    return binding_grammar([x for x, _ in task.public] + [task.query], maps=world["maps"])


def certify(task, world, *, popper=True, rules=(), early=False, extra=(), public=None, tools=None):
    public = tuple(public if public is not None else task.public)
    tools = tools if tools is not None else task_grammar(task, world)
    ab = make_abstract(rules, maps=list(MAPS.values()) if world["maps"] else ()) if rules else None
    s = Searcher(public, task.query, tools, popper=popper, m=meter(TASK_BUDGET), partial_depth=0,
                 early_ambiguity=early, extra=extra, max_depth=MAX_DEPTH, abstract=ab)
    res = s.run_to(MAX_DEPTH)
    res.searcher = s
    return res


# --------------------------------------------------------------------------- S2: slot-relative features
def kept(mech, xs):
    """The item positions a selection-like mechanism keeps (F: accepted; S: inside the boundary;
    Sort: all). None for mechanisms that create items (Map) or scalars (Agg)."""
    if mech.role == "F":
        return frozenset(i for i, x in enumerate(xs) if mech.slots[0](x))
    if mech.role == "S":
        k, o = mech.slots
        order = [i for i, _ in sorted(enumerate(xs), key=o.key)]
        return frozenset(order[:k])
    if mech.role == "Sort":
        return frozenset(range(len(xs)))
    return None


KAPPA = ("n", "Ks", "Kt", "Ks&Kt", "Ks-Kt", "Kt-Ks")


def kappa(ms, mt, xs):
    a, b = kept(ms, xs), kept(mt, xs)
    if a is None or b is None:
        return None
    return dict(n=len(xs), Ks=len(a), Kt=len(b), **{"Ks&Kt": len(a & b), "Ks-Kt": len(a - b), "Kt-Ks": len(b - a)})


def k_of(m):
    return m.slots[0] if m.role == "S" else None


def atoms_for(ms, mt):
    """Generic atoms over the kappa features: f >= 1, f == 0, f >= k (k of either selection slot)."""
    ks = sorted({k for k in (k_of(ms), k_of(mt)) if k is not None})
    out = []
    for f in KAPPA:
        out += [(f, ">=", 1), (f, "==", 0)] + [(f, ">=k", k) for k in ks] + [(f, ">k", k) for k in ks]
    return out


def holds(atom, kp):
    f, op, c = atom
    v = kp[f]
    return v >= 1 if op == ">=" else v == 0 if op == "==" else v >= c if op == ">=k" else v > c


@dataclass
class DiagnosticRule:
    """Learned relational diagnostic rule for an adjacent pair (role_s, role_t): Phi over kappa atoms with
    Phi(x) <=> exec(s.t, x) != exec(t.s, x) on all mined source evidence and on the scope check."""
    pattern: tuple
    phi: tuple                         # conjunction of atoms, with k given by position (s, t)
    support: int
    precision: float
    recall: float
    scope_checked: int = 0
    scope_violations: int = 0
    tier: str = "empirical"
    discovery_work: int = 0


def _abstract_atom(atom, ms, mt):
    f, op, c = atom
    if op in (">=k", ">k"):
        return (f, op, "s" if k_of(ms) == c else "t")
    return atom


def _concrete_atom(atom, ms, mt):
    f, op, c = atom
    if op in (">=k", ">k"):
        return (f, op, k_of(ms) if c == "s" else k_of(mt))
    return atom


def mine_rules(pair_data, *, min_pos=10, max_size=2):
    """pair_data: {(role_s, role_t): [(ms, mt, xs, disagree)]}; minimal exact conjunction per pattern."""
    rules, work = {}, 0
    for pattern, rows in pair_data.items():
        pos = sum(d for *_, d in rows)
        if pos < min_pos:
            rules[pattern] = None
            continue
        feats = []
        for ms, mt, xs, d in rows:
            kp = kappa(ms, mt, xs)
            work += 6
            if kp is not None:
                feats.append((ms, mt, kp, d))
        if sum(d for *_, d in feats) < min_pos:
            rules[pattern] = None
            continue
        best = None
        cands = {}
        for ms, mt, kp, d in feats:
            for a in atoms_for(ms, mt):
                cands.setdefault(_abstract_atom(a, ms, mt), None)
        cand_list = sorted(cands, key=repr)
        for size in range(1, max_size + 1):
            for conj in combinations(cand_list, size):
                tp = fp = fn = 0
                for ms, mt, kp, d in feats:
                    work += size
                    ok = all(holds(_concrete_atom(a, ms, mt), kp) for a in conj)
                    tp += ok and d
                    fp += ok and not d
                    fn += (not ok) and d
                if fp == 0 and fn == 0:
                    best = DiagnosticRule(pattern, conj, pos, 1.0, 1.0)
                    break
            if best:
                break
        rules[pattern] = best
    return rules, work


def phi_holds(rule, ms, mt, xs):
    kp = kappa(ms, mt, xs)
    return kp is not None and all(holds(_concrete_atom(a, ms, mt), kp) for a in rule.phi)


def scope_check(rule, *, n_max=4, values=(-1, 0, 2, 5)):
    """Exhaustive check of Phi <=> disagreement over every int list of length <= n_max over `values` and
    every F/S binding instantiated on that universe (source scope; tier 'scope-verified')."""
    universe = [list(t) for n in range(0, n_max + 1) for t in product(values, repeat=n)]
    tools = [t.fn for t in binding_grammar([values * 2], maps=False)]
    rs, rt = rule.pattern
    ms_list = [m for m in tools if m.role == rs]
    mt_list = [m for m in tools if m.role == rt]
    checked = viol = 0
    for ms, mt in product(ms_list, mt_list):
        for xs in universe:
            d = vkey(mt(ms(xs))) != vkey(ms(mt(xs)))
            checked += 1
            viol += phi_holds(rule, ms, mt, xs) != d
    rule.scope_checked, rule.scope_violations = checked, viol
    rule.tier = "scope-verified" if viol == 0 else "refuted"
    return checked, viol


# --------------------------------------------------------------------------- probe arms
def _class_hypotheses(res):
    s = res.searcher
    cls = s.graph.classes.get(tuple(s.targets), {})
    return [prog for rest, (prog, vals) in cls.items() if len(prog) == res.size]


def _pairs_by_swap(res, public, m):
    """(h, swap(h)) for every 2-step representative whose swapped order also fits every public pair."""
    out = []
    for prog in _class_hypotheses(res):
        if len(prog) != 2:
            continue
        a, b = prog
        m.charge("probe_design_work_units", len(public))
        try:
            if all(vkey(a.fn(b.fn(x))) == vkey(y) for x, y in public):
                out.append((a.fn, b.fn))          # (first, second) of the representative
        except Exception:
            continue
    return out


def _edit_space(bases, world_fields, pool, *, max_edits=2, cap=3000):
    """Field-value edits of observed inputs: <= max_edits item edits, values from the observed pool.
    Breadth-first over edit count (every 1-edit of every base before any 2-edit), so the cap never hides a
    cheaper edit of a later base."""
    out = []
    for e in range(1, max_edits + 1):
        for b in bases:
            if not isinstance(b, list) or not b:
                continue
            slots = [(i, f) for i in range(len(b)) for f in (world_fields if isinstance(b[0], dict) else (".",))]
            for chosen in combinations(slots, e):
                if len({i for i, _ in chosen}) < e:
                    continue
                for vals in product(*[pool.get(f, ()) for _, f in chosen]):
                    x = [dict(it) if isinstance(it, dict) else it for it in b]
                    for (i, f), v in zip(chosen, vals):
                        if f == ".":
                            x[i] = v
                        else:
                            x[i][f] = v
                    out.append(x)
                    if len(out) >= cap:
                        return out
    return out


def _value_pool(public, query):
    pool = {}
    for x in [x for x, _ in public] + [query]:
        for it in x:
            if isinstance(it, dict):
                for f, v in it.items():
                    pool.setdefault(f, set()).add(v)
            else:
                pool.setdefault(".", set()).add(it)
    return {f: sorted(v, key=repr) for f, v in pool.items()}


def _partition_entropy(progs, x, m):
    outs = Counter()
    for p in progs:
        m.charge("probe_design_work_units", len(p))
        try:
            outs[vkey(run([t.fn for t in p], x))] += 1
        except Exception:
            outs["__raise__"] += 1
    n = sum(outs.values())
    return -sum(c / n * math.log2(c / n) for c in outs.values())


def design_probe(arm, res, public, query, world, rules, rng, m):
    """Returns (probe input, design label) or (None, reason)."""
    qk = vkey(query)
    seen = {vkey(x) for x, _ in public} | {qk}
    fields = [f for f in world["fields"]]
    if arm == "random":
        for _ in range(10):
            x = world["sample"](rng)
            if vkey(x) not in seen:
                return x, "random"
        return None, "none"
    progs = _class_hypotheses(res)
    bases = [x for x, _ in public] + [query]
    if arm == "rule":
        for ms, mt in _pairs_by_swap(res, public, m):
            # representative program is (ms then mt) -> exec = mt(ms(x)); rule pattern is (first, second)
            rule = rules.get((ms.role, mt.role)) or rules.get((mt.role, ms.role))
            if rule is None:
                continue
            first, second = (ms, mt) if rules.get((ms.role, mt.role)) else (mt, ms)
            pool = _value_pool(public, query)
            for x in _edit_space(bases, fields, pool):
                m.charge("probe_design_work_units", 2 * len(x))
                if vkey(x) in seen:
                    continue
                if phi_holds(rule, first, second, x) and _partition_entropy(progs, x, m) > 0:
                    # Phi separates this (possibly mis-bound) pair; spend the oracle call only if the probe
                    # also splits the whole current hypothesis set (exact, charged)
                    return x, f"rule:{rule.pattern}"
        arm = "eig_edit"                     # declared fallback when no rule applies
    if arm == "v4":
        hyps = [(tuple(t.name for t in p), None, p) for p in progs]
        plan = propose_refinement(hyps, dict(public=public, query=query), dict(tools=[]), "disambiguate",
                                  TASK_BUDGET, m=m)
        return (plan.distinguishing_test[1], "v4") if plan.distinguishing_test else (None, "none")
    if arm in ("eig_perturb", "eig_edit"):
        if arm == "eig_perturb":
            cands = [x for _, x, _ in candidate_probes(bases, [(None, None, p) for p in progs], query)]
        else:
            cands = _edit_space(bases, fields, _value_pool(public, query))
        best, best_h = None, 0.0
        hmax = math.log2(max(1, len(progs)))
        for x in cands:
            if vkey(x) in seen:
                continue
            h = _partition_entropy(progs, x, m)
            if h > best_h + 1e-12:
                best, best_h = x, h
                if h >= hmax - 1e-9:
                    break
        return (best, arm) if best is not None else (None, "none")
    raise ValueError(arm)


def solve_active(task, world, arm, rules, *, seed=0):
    """Certify, probe (charged oracle = teacher, never on the query), re-certify; up to PROBE_BUDGET."""
    m = meter(10**9)
    public = list(task.public)
    rng = random.Random(f"w25-probe:{seed}:{arm}:{vkey(task.query)}")
    probes, labels = 0, []
    tools = task_grammar(task, world)
    try:
        res = certify(task, world, public=public, tools=tools)
        m.charge("certify_work_units", res.work)
        while res.status == AMBIGUOUS and probes < PROBE_BUDGET:
            x, label = design_probe(arm, res, public, task.query, world, rules, rng, m)
            labels.append(label)
            if x is None:
                break
            probes += 1
            m.charge("oracle_work_units", ORACLE_COST)
            try:
                y = run(task.teacher, x)
            except Exception:
                continue
            public.append((x, y))
            res = certify(task, world, public=public, tools=tools)
            m.charge("certify_work_units", res.work)
    except WorkExhausted:
        return dict(arm=arm, solved=False, status="EXHAUSTED", probes=probes, work=m.total, labels=labels)
    solved = res.status == UNIQUE and vkey(res.answer) == vkey(task.answer)
    false = res.status == UNIQUE and vkey(res.answer) != vkey(task.answer)
    return dict(arm=arm, solved=solved, false_certificate=false, status=res.status, probes=probes, work=m.total,
                work_by=dict(m.counts), labels=labels)


# --------------------------------------------------------------------------- source mining
def collect_pair_data(world, seed, n_tasks, rng_inputs=40):
    """From source synthesis episodes: every surviving swapped pair (and every adjacent mechanism pair in
    the grammar of the episode) is labelled on sampled + perturbed inputs by exact execution - no oracle
    is needed for this label (both programs are executed)."""
    data, work = {}, 0
    rng = random.Random(f"w25-mine:{seed}")
    for task in make_tasks(world, seed, n_tasks, active=True):
        res = certify(task, world)
        work += res.work
        m = meter(10**9)
        pairs = _pairs_by_swap(res, task.public, m)
        work += m.total
        inputs = [world["sample"](rng) for _ in range(rng_inputs)] + [x for x, _ in task.public]
        for a, b in pairs:
            for xs in inputs:
                try:
                    d = vkey(b(a(xs))) != vkey(a(b(xs)))
                except Exception:
                    continue
                work += 2 * len(xs)
                data.setdefault((a.role, b.role), []).append((a, b, xs, d))
    return data, work


# --------------------------------------------------------------------------- spike drivers
def s1_compare(tasks, world, rules):
    """Identical exact certifier with FD only vs FD + abstract rules: verdicts, evaluations, total work."""
    rows = []
    for t in tasks:
        a = certify(t, world, popper=True)
        b = certify(t, world, popper=True, rules=rules)
        same = a.status == b.status and {vkey(h[1]) for h in a.hypotheses} == {vkey(h[1]) for h in b.hypotheses}
        rows.append(dict(world=world["name"], depth=len(t.teacher), status=a.status, same=same,
                         evals_fd=a.evaluations, evals_ab=b.evaluations, work_fd=a.work, work_ab=b.work,
                         pruned_abstract=b.searcher.pruned_abstract,
                         abstract_work=b.searcher.m.counts.get("abstract_work_units", 0)))
    return rows


def tycho_rules(tasks, world, *, horizon=100):
    """Admit each abstract rule iff its marginal saving (with the other admitted rules) on source validation
    tasks, projected over the horizon, exceeds the validation work; greedy in a fixed order."""
    admitted, log, spent = [], [], 0
    for r in RULES:
        base = s1_compare(tasks, world, tuple(admitted)) if admitted else None
        trial = s1_compare(tasks, world, tuple(admitted + [r]))
        w_base = sum(x["work_ab"] for x in base) if base else sum(x["work_fd"] for x in trial)
        w_trial = sum(x["work_ab"] for x in trial)
        spent += w_trial + (sum(x["work_ab"] for x in base) if base else sum(x["work_fd"] for x in trial))
        per_task = (w_base - w_trial) / max(1, len(tasks))
        net = per_task * horizon - spent
        ok = net > 0 and all(x["same"] for x in trial)
        log.append(dict(rule=r, saving_per_task=per_task, net_benefit=net, validation_work=spent, admitted=ok))
        if ok:
            admitted.append(r)
    return admitted, log, spent


def fs_composition_ambiguous(task):
    """Ground-truth stratum label (scoring only): the teacher is an F/S pair whose swapped order also fits
    every public pair but answers the query differently."""
    if len(task.teacher) != 2 or {m.role for m in task.teacher} != {"F", "S"}:
        return False
    a, b = task.teacher
    try:
        fits = all(vkey(a(b(x))) == vkey(y) for x, y in task.public)
        return fits and vkey(a(b(task.query))) != vkey(task.answer)
    except Exception:
        return False


S2_ARMS = ("rule", "eig_edit", "eig_perturb", "v4", "random")


def run_spike_seed(seed, *, n_mine=30, n_val=20, n_s1=30, n_s2=40):
    """One dev seed: mine (source ints), Tycho-admit abstract rules (source validation), S1 on both worlds,
    S2 on active record tasks with every probe arm. Returns raw rows and the discovery ledger."""
    src, tgt = ints_world(seed), records_world(seed)
    ledger = Counter()
    # Library: diagnostic rules mined on source episodes, scope-checked on the source universe
    data, w = collect_pair_data(src, seed, n_mine)
    ledger["mining_work"] += w
    rules, w = mine_rules(data)
    ledger["rule_learning_work"] += w
    kept_rules = {}
    for k, r in rules.items():
        if r is not None:
            checked, viol = scope_check(r)
            ledger["scope_check_work"] += checked
            if viol == 0:
                kept_rules[k] = r
    # S1: Tycho admission of tier-1 abstract rules on SOURCE validation tasks, then measurement
    val = make_tasks(src, seed + 100, n_val, active=False, max_depth=3)
    admitted, tlog, spent = tycho_rules(val, src)
    ledger["tycho_abstract_validation_work"] += spent
    s1 = []
    for world, tseed in ((src, seed + 200), (tgt, seed + 200)):
        tasks = make_tasks(world, tseed, n_s1, active=False, max_depth=3)
        for label, rs in (("all_proved", RULES), ("tycho_admitted", tuple(admitted))):
            s1 += [dict(r, ruleset=label) for r in s1_compare(tasks, world, rs)]
    # S2: active record tasks, every arm on the same tasks
    tasks = make_tasks(tgt, seed + 300, n_s2, active=True)
    s2 = []
    for i, t in enumerate(tasks):
        stratum = "fs_ambiguous" if fs_composition_ambiguous(t) else "other"
        for arm in S2_ARMS:
            r = solve_active(t, tgt, arm, kept_rules, seed=seed)
            r.update(task=i, stratum=stratum, seed=seed)
            s2.append(r)
    return dict(seed=seed, ledger=dict(ledger), rules={f"{k[0]}>{k[1]}": dict(phi=[list(a) for a in r.phi],
                support=r.support, scope_checked=r.scope_checked, scope_violations=r.scope_violations,
                tier=r.tier) for k, r in kept_rules.items()},
                rejected_patterns=sorted(f"{k[0]}>{k[1]}" for k, r in rules.items() if r is None),
                abstract_admitted=admitted, tycho_log=tlog, s1=s1, s2=s2,
                fields=list(tgt["fields"]))
