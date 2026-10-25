"""Wave 24 general-capability suite: learned, transferable search over unwrapped tools.

Cost model (uniform, charged on one WorkMeter, never hidden):
  * one tool application on one value      = 1 unit (macros charge every primitive step)
  * one unlabeled probe execution           = 1 unit (setup)
  * one forward-model prediction            = 1 unit
  * one policy / model training row         = 1 unit
  * one value projection (type+mass)        = 1 unit per 256 atoms (bounded by the cap)
Wall-clock and CPU seconds are reported next to work units.

Certificates are relative to an explicitly declared space: the fixed baseline
certifies over the exhaustive quotiented chain space up to depth D (minimal-
depth convention); the learned solver certifies over its declared pruned
space. Every certificate's witness is re-executed on public IO and the query.
Grading against teacher answers happens only after the answer is locked.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import math
import random
import re
import time

from nexus.wave24_auto_laws import AtomicForceClassifier, AtomicFieldProjector
from nexus.wave24_domains import Tool, vkey
from nexus.wave24_quotient_core import WorkMeter, WorkExhausted

SCALARS = ("int", "float", "bool", "NoneType")


# --------------------------------------------------------------------------- abstraction
def amass(value, cap=10_000):
    """Mass in atoms: len for sequences/maps, bit width for ints, 1 for other scalars."""
    if isinstance(value, bool):
        return 1
    if isinstance(value, int):
        return max(1, abs(value).bit_length())
    if isinstance(value, (str, bytes, list, tuple, dict, set, frozenset)):
        return min(len(value), cap)
    return 1


def abstract(value):
    return (type(value).__name__, amass(value))


def phase(value):
    """Input phase for fault boundaries: type + corruption flags (NaN / None / mixed element types)."""
    items = list(value.values()) if isinstance(value, dict) else list(value) if isinstance(value, (list, tuple)) else [value]
    nan = any(isinstance(v, float) and not math.isfinite(v) for v in items)
    none = any(v is None for v in items)
    mixed = len({type(v).__name__ for v in items}) > 1
    keys = tuple(sorted(map(repr, value))) if isinstance(value, dict) and len(value) <= 6 else ()
    return (type(value).__name__, nan, none, mixed, keys)


def projection_cost(value):
    return 1 + amass(value) // 256


class BoundedProjector:
    """Signature projection with bounded cost on large inputs (gap 5 scaling).

    Mass and type are exact in O(1). Hash fields use a deterministic stride
    sample of at most `k` atoms, so the cost is O(min(N, k)). Sampled
    signatures are guidance only; they never certify a prune.
    """

    def __init__(self, k=256):
        self.k = k
        self.exact = AtomicFieldProjector()

    def project(self, value):
        if isinstance(value, (list, tuple, str, bytes)) and len(value) > self.k:
            stride = len(value) / self.k
            sample = type(value)(value[int(i * stride)] for i in range(self.k)) if not isinstance(value, (str, bytes)) \
                else value[::max(1, int(stride))][:self.k]
            sig = self.exact.project(sample)
            return dict(type=type(value).__name__, mass=len(value), sampled=True, sig=sig)
        return dict(type=type(value).__name__, mass=amass(value), sampled=False, sig=self.exact.project(value))


# --------------------------------------------------------------------------- world model
@dataclass
class ToolModel:
    out_types: Counter = field(default_factory=Counter)   # (in_type, out_type) -> n
    faults: Counter = field(default_factory=Counter)      # in_type -> n raised
    seen: Counter = field(default_factory=Counter)        # in_type -> n
    ratio_lo: dict = field(default_factory=dict)          # in_type -> min mass ratio
    ratio_hi: dict = field(default_factory=dict)          # in_type -> max mass ratio


class ForwardWorldModel:
    """Predicts a tool's effect on the abstract (type, mass) state BEFORE executing it.

    Learned from unlabeled probe executions and from every transition the
    solver executes anyway (no extra execution). Used to prune candidate
    steps and plan multi-step trajectories in signature space.
    """

    def __init__(self, slack=0.0):
        self.models = defaultdict(ToolModel)
        self.slack = slack  # approximate-law tolerance (gap 5 graceful degradation)
        self.predictions = 0

    def observe(self, tool, x, y=None, raised=False):
        m = self.models[tool.name]
        tin = type(x).__name__
        m.seen[tin] += 1
        if raised:
            m.faults[tin] += 1
            return
        m.out_types[(tin, type(y).__name__)] += 1
        r = (amass(y) + 1) / (amass(x) + 1)
        m.ratio_lo[tin] = min(m.ratio_lo.get(tin, r), r)
        m.ratio_hi[tin] = max(m.ratio_hi.get(tin, r), r)

    def fit_probes(self, tools, probes, meter):
        for tool in tools:
            for x in probes:
                meter.charge("world_model_probe_work_units")
                try:
                    y = tool(x)
                except Exception:
                    self.observe(tool, x, raised=True)
                    continue
                self.observe(tool, x, y)
                meter.charge("world_model_training_work_units")

    def predict(self, tool, state_abs, meter):
        """Predicted set of (out_type, mass_lo, mass_hi) per input, or None if unknown."""
        meter.charge("world_model_prediction_work_units")
        self.predictions += 1
        m = self.models.get(tool.name)
        if m is None:
            return None
        out = []
        for tin, mass in state_abs:
            if m.seen[tin] == 0:
                return None
            if m.faults[tin] == m.seen[tin]:
                out.append(None)  # always faulted on this type
                continue
            types = {o for (i, o), n in m.out_types.items() if i == tin}
            lo, hi = m.ratio_lo.get(tin, 0.0), m.ratio_hi.get(tin, 1e9)
            out.append((types, (mass + 1) * lo * (1 - self.slack) - 1, (mass + 1) * hi * (1 + self.slack) - 1))
        return out

    def can_match(self, tool, state_abs, target_abs, meter):
        """Last-step check: could this tool map every state to its exact target abstract?"""
        pred = self.predict(tool, state_abs, meter)
        if pred is None:
            return True
        for p, (ttype, tmass) in zip(pred, target_abs):
            if p is None:
                return False
            types, lo, hi = p
            if ttype not in types or not (lo - 1e-9 <= tmass <= hi + 1e-9):
                return False
        return True

    def reachability_table(self, tools):
        """Learned type-transition graph (signature-space planning substrate)."""
        edges = defaultdict(set)
        for tool in tools:
            m = self.models.get(tool.name)
            if m is None:
                return None
            for (i, o), n in m.out_types.items():
                edges[i].add(o)
        return edges

    def can_reach(self, tool, state_abs, target_abs, steps_after, edges, meter):
        """Predict this step's output types, then plan: can targets be reached in `steps_after` more?"""
        pred = self.predict(tool, state_abs, meter)
        if pred is None or edges is None:
            return True
        for p, (ttype, _) in zip(pred, target_abs):
            if p is None:
                return False
            types = p[0]
            frontier, seen = set(types), set(types)
            for _ in range(steps_after):
                frontier = {o for f in frontier for o in edges[f]} - seen
                seen |= frontier
            if ttype not in seen:
                return False
        return True

    def type_reachable(self, tools, state_types, target_types, steps):
        """Signature-space planning: can every input type reach its target type in <= steps?"""
        edges = defaultdict(set)
        for tool in tools:
            m = self.models.get(tool.name)
            if m is None:
                return True
            for (i, o), n in m.out_types.items():
                edges[i].add(o)
        for s, t in zip(state_types, target_types):
            frontier, seen = {s}, {s}
            for _ in range(steps):
                frontier = {o for f in frontier for o in edges[f]} - seen
                seen |= frontier
            if t not in seen:
                return False
        return True


# --------------------------------------------------------------------------- force-level policy
def direction(state_abs, target_abs):
    rel = set()
    for (st, sm), (tt, tm) in zip(state_abs, target_abs):
        if st != tt:
            rel.add("TYPE_CHANGE")
        else:
            rel.add("DEC" if tm < sm else "INC" if tm > sm else "EQ")
    return "|".join(sorted(rel))


class StoneUsefulnessPolicy:
    """Domain-agnostic stepping-stone policy over (deficit direction, atomic force).

    Learned from solved tasks: a stone (state, tool) is useful when it lies on
    the certified solution path. Prunes expansions whose force has a low
    measured usefulness rate under the current deficit direction. The pruning
    threshold is itself meta-learned (see `retune`), not hand-set.
    """

    def __init__(self, tau=0.0, min_count=8):
        self.useful = Counter()
        self.expanded = Counter()
        self.tau = tau
        self.min_count = min_count
        self.log = []          # (key, on_path) replay buffer for threshold retuning
        self.history = []

    def rate(self, key):
        n = self.expanded[key]
        return None if n < self.min_count else self.useful[key] / n

    def allow(self, key):
        r = self.rate(key)
        return r is None or r >= self.tau

    def learn(self, expansions, path_keys, meter):
        path = Counter(path_keys)
        for key in expansions:
            meter.charge("policy_training_work_units")
            self.expanded[key] += 1
        for key, n in path.items():
            self.useful[key] += n
        self.log.extend((k, path[k] > 0) for k in set(expansions))

    def retune(self, meter, *, recall_floor=0.97):
        """Meta-learning: the most aggressive tau that keeps on-path recall (O(K log K), charged)."""
        rated = sorted((self.rate(k), self.useful[k]) for k in self.expanded if self.rate(k) is not None)
        meter.charge("meta_learning_work_units", 1 + len(rated) * max(1, int(math.log2(len(rated) + 1))))
        total = sum(self.useful.values())
        best, dropped = 0.0, 0
        for rate, useful in rated:
            if total and (total - dropped - useful) / total < recall_floor:
                break
            dropped += useful
            best = rate
        self.tau = best
        self.history.append(best)
        return best

    def state(self):
        return dict(tau=self.tau, keys=len(self.expanded),
                    rates={"/".join(k): self.rate(k) for k in sorted(self.expanded) if self.rate(k) is not None})


# --------------------------------------------------------------------------- algebraic laws
LAW_FAMILIES = ("idempotent", "involution", "commute")


class LawLibrary:
    """Probe-discovered algebraic laws over anonymous tools, grouped into force-pair families.

    A law is a hypothesis from unlabeled probes; families carry a measured
    reliability (precision on held-out inputs) learned on SOURCE domains. On a
    target, only families with transferred reliability are probed and used,
    which is the cross-domain transfer being measured.
    """

    def __init__(self):
        self.idempotent, self.involution, self.commute = set(), set(), set()

    @staticmethod
    def family(kind, fa, fb=None):
        return (kind, fa, fb or fa)

    def discover(self, tools, probes, forces, meter, *, allowed=None):
        def ok(fn, x):
            try:
                return True, fn(x)
            except Exception:
                return False, None
        for a in tools:
            fam_i = self.family("idempotent", forces[a.name])
            fam_v = self.family("involution", forces[a.name])
            if allowed is not None and fam_i not in allowed and fam_v not in allowed:
                continue
            idem = invol = True
            for x in probes:
                meter.charge("law_probe_work_units", 2)
                d1, y = ok(a, x)
                if not d1:
                    continue
                d2, z = ok(a, y)
                idem &= d2 and vkey(z) == vkey(y)
                invol &= d2 and vkey(z) == vkey(x)
            if idem and (allowed is None or fam_i in allowed):
                self.idempotent.add(a.name)
            if invol and (allowed is None or fam_v in allowed):
                self.involution.add(a.name)
        for i, a in enumerate(tools):
            for b in tools[i + 1:]:
                fam = self.family("commute", *sorted((forces[a.name], forces[b.name])))
                if allowed is not None and fam not in allowed:
                    continue
                holds, defined = True, 0
                for x in probes:
                    meter.charge("law_probe_work_units", 4)
                    d1, ab = ok(lambda v: a(b(v)), x)
                    d2, ba = ok(lambda v: b(a(v)), x)
                    if d1 != d2 or (d1 and vkey(ab) != vkey(ba)):
                        holds = False
                        break
                    defined += d1
                if holds and defined >= 2:
                    self.commute.add((a.name, b.name))
        return self

    def prune(self, prev, tool):
        """Skip `tool` right after `prev` when a law makes the step redundant or non-canonical."""
        if prev is None:
            return False
        if prev == tool and (tool in self.idempotent or tool in self.involution):
            return True
        return (tool, prev) in self.commute  # canonical order: only a-then-b with a < b survives

    def laws(self, forces):
        out = [("idempotent", t) for t in sorted(self.idempotent)] + [("involution", t) for t in sorted(self.involution)]
        out += [("commute", a, b) for a, b in sorted(self.commute)]
        return out


def measure_law_reliability(domain, forces, meter, *, probes=6, holdout=40, seed=0, only=None):
    """Source-side: discover laws on few probes, validate on held-out unlabeled inputs, per family."""
    rng = random.Random(f"laws:{domain.name}:{seed}")
    lib = LawLibrary().discover(list(domain.tools), domain.inputs(rng, probes), forces, meter, allowed=only)
    held = domain.inputs(rng, holdout)
    stats = {}
    tools = {t.name: t for t in domain.tools}
    def holds(fn1, fn2, x):
        try:
            a = fn1(x)
        except Exception:
            a = "<raise>"
        try:
            b = fn2(x)
        except Exception:
            b = "<raise>"
        return (a == "<raise>") == (b == "<raise>") and (a == "<raise>" or vkey(a) == vkey(b))
    for name in lib.idempotent:
        t = tools[name]
        fam = LawLibrary.family("idempotent", forces[name])
        meter.charge("law_validation_work_units", 3 * holdout)
        good = all(holds(lambda v: t(t(v)), t, x) for x in held)
        stats.setdefault(fam, []).append(good)
    for name in lib.involution:
        t = tools[name]
        fam = LawLibrary.family("involution", forces[name])
        meter.charge("law_validation_work_units", 2 * holdout)
        good = all(holds(lambda v: t(t(v)), lambda v: v, x) for x in held)
        stats.setdefault(fam, []).append(good)
    for a, b in lib.commute:
        ta, tb = tools[a], tools[b]
        fam = LawLibrary.family("commute", *sorted((forces[a], forces[b])))
        meter.charge("law_validation_work_units", 4 * holdout)
        good = all(holds(lambda v: ta(tb(v)), lambda v: tb(ta(v)), x) for x in held)
        stats.setdefault(fam, []).append(good)
    return stats


# --------------------------------------------------------------------------- solver
@dataclass
class SolveResult:
    status: str
    answer: object = None
    witness: tuple = ()
    depth: int = 0
    work: int = 0
    expansions: list = field(default_factory=list)
    path_keys: list = field(default_factory=list)
    pruned_model: int = 0
    pruned_policy: int = 0
    certificate_valid: object = None


UNIQUE = "UNIQUE_MINIMAL_DEPTH_IN_DECLARED_SPACE"


def recovery_tool(a, b):
    def run(x, a=a, b=b):
        run.last_cost = 0
        try:
            out = a(x)
            run.last_cost += _cost_of(a)
            return out
        except Exception:
            run.last_cost += _cost_of(a)
            try:
                return b(x)
            finally:
                run.last_cost += _cost_of(b)
    run.last_cost = 0
    return Tool(f"try[{a.name}|{b.name}]", run, f"{a.doc} otherwise {b.doc}", a.cost + b.cost,
                layer=max(a.layer, b.layer) + 1, parts=(a.name, b.name), children=(a, b), kind="recovery")


def _cost_of(tool):
    return max(1, tool.fn.last_cost) if hasattr(tool.fn, "last_cost") else tool.cost


def macro_tool(tools_by_name, chain):
    parts = [tools_by_name[n] for n in chain]
    def run(x, parts=parts):
        run.last_cost = 0
        for p in parts:
            try:
                x = p(x)
            finally:
                run.last_cost += _cost_of(p)   # exact primitive work of every part, loops included
        return x
    run.last_cost = 0
    return Tool("macro[" + ">".join(chain) + "]", run, " then ".join(p.doc for p in parts),
                sum(p.cost for p in parts), layer=max(p.layer for p in parts) + 1, parts=tuple(chain),
                children=tuple(parts), kind="macro")


def apply_tool(tool, values, meter, category="search_work_units", *, where=None):
    """Apply to every value (each application charged). `where`, if a list, receives the faulting index."""
    out = []
    variable = hasattr(tool.fn, "last_cost")   # loops report their exact step count
    for i, v in enumerate(values):
        if not variable:
            meter.charge(category, tool.cost)
        try:
            out.append(tool(v))
        except Exception:
            if variable:
                meter.charge(category, max(1, tool.fn.last_cost))
            if where is not None:
                where.append(i)
            return None, True
        if variable:
            meter.charge(category, max(1, tool.fn.last_cost))
    return out, False


def solve(task, tools, *, max_depth=4, budget=6000, learned=False, model=None, policy=None,
          forces=None, recovery=True, record=True, recovery_map=None, laws=None, predict=True, fault_memory=None):
    """Iterative-deepening quotiented chain search; minimal-depth uniqueness certificate.

    learned=False: exhaustive baseline (only exact observational-equivalence dedup).
    learned=True:  forward-model last-step + type-reachability pruning and
                   force-policy stone pruning (declared, heuristic) before execution.
    `recovery` adds try(a|b) composites when a tool faults on part of a state.
    """
    meter = WorkMeter(limit=budget, wall_limit=10.0)
    inputs = [x for x, _ in task.public] + [task.query]
    targets = [y for _, y in task.public]
    target_keys = [vkey(y) for y in targets]
    target_abs = [abstract(y) for y in targets]
    n = len(targets)
    by_name = {t.name: t for t in tools}
    frontier = [(tuple(inputs), ())]
    seen = {tuple(vkey(v) for v in inputs)}
    res = SolveResult("NO_PROGRAM_IN_BOUNDED_GRAMMAR")
    edges = model.reachability_table(tools) if (learned and model is not None) else None
    try:
        for depth in range(1, max_depth + 1):
            goals, nxt = [], []
            last = depth == max_depth
            for values, chain in frontier:
                state_abs = [abstract(v) for v in values[:n]]
                if learned:
                    meter.charge("projection_work_units", sum(projection_cost(v) for v in values[:n]))
                    dkey = direction(state_abs, target_abs)
                    if model is not None and predict and not model.type_reachable(tools, [a[0] for a in state_abs],
                                                                      [a[0] for a in target_abs], max_depth - depth + 1):
                        res.pruned_model += 1
                        continue
                candidates = list(tools)
                prev_name = chain[-1].name if chain else None
                for tool in candidates:
                    key = None
                    if laws is not None and laws.prune(prev_name, tool.name):
                        res.pruned_model += 1
                        continue
                    if learned:
                        prev = forces.get(chain[-1].name, "F_COMPOSITE") if (forces is not None and chain) else "START"
                        key = (dkey, prev, forces.get(tool.name, "F_COMPOSITE")) if forces is not None else None
                        if policy is not None and key is not None and not policy.allow(key):
                            res.pruned_policy += 1
                            continue
                        if model is not None and predict and last and not model.can_match(tool, state_abs, target_abs, meter):
                            res.pruned_model += 1
                            continue
                        if model is not None and predict and not last and not model.can_reach(
                                tool, state_abs, target_abs, max_depth - depth, edges, meter):
                            res.pruned_model += 1
                            continue
                    where = []
                    out, faulted = apply_tool(tool, values, meter, where=where)
                    if faulted and recovery and tool.layer == 0:
                        # phase of the value that faulted, from the execution already charged
                        fault_phases = [phase(values[where[0]])] if (learned and fault_memory is not None and where) else None
                        for alt in tools:
                            if alt.name == tool.name or alt.layer:
                                continue
                            if fault_phases and all(fault_memory.get((tool.name, alt.name, ph)) is False for ph in fault_phases):
                                res.pruned_policy += 1   # learned: alt also faults on this phase -> dead branch
                                continue
                            rt = recovery_tool(tool, alt)
                            o2, f2 = apply_tool(rt, values, meter, "recovery_work_units")
                            if learned and fault_memory is not None and fault_phases:
                                for ph in fault_phases:
                                    fault_memory[(tool.name, alt.name, ph)] = not f2
                            if not f2:
                                _push(o2, chain + (rt,), goals, nxt, seen, target_keys, n, res, key, record, model, rt, values)
                        continue
                    if model is not None and record:
                        for v, o in zip(values, out or ()):
                            model.observe(tool, v, o)
                    if out is None:
                        continue
                    _push(out, chain + (tool,), goals, nxt, seen, target_keys, n, res, key, record, model, tool, values)
            if goals:
                answers = {vkey(v[-1]) for v, _ in goals}
                values, chain = goals[0]
                res.depth, res.witness, res.answer = depth, tuple(t.name for t in chain), values[-1]
                res.status = UNIQUE if len(answers) == 1 else "AMBIGUOUS_WITNESS_FOUND"
                res._chain = chain
                break
            frontier = nxt
    except WorkExhausted:
        res.status = "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED"
    res.work = meter.total
    res.meter = meter
    if res.status == UNIQUE:
        res.certificate_valid = verify_witness(task, res._chain, res.answer)
        if forces is not None:
            res.path_keys = _path_keys(task, res._chain, forces, target_abs)
    return res


def _push(out, chain, goals, nxt, seen, target_keys, n, res, key, record, model, tool, values):
    k = tuple(vkey(v) for v in out)
    if record and key is not None:
        res.expansions.append(key)
    if k in seen:
        return
    seen.add(k)
    if list(k[:n]) == target_keys:
        goals.append((out, chain))
    nxt.append((out, chain))


def _path_keys(task, chain, forces, target_abs):
    values = [x for x, _ in task.public]
    keys, prev = [], "START"
    for tool in chain:
        force = forces.get(tool.name, "F_COMPOSITE")
        keys.append((direction([abstract(v) for v in values], target_abs), prev, force))
        prev = force
        values = [tool(v) for v in values]
    return keys


def verify_witness(task, chain, answer):
    """Independent re-execution of the certified program on public IO and the query."""
    try:
        for x, y in task.public:
            v = x
            for t in chain:
                v = t(v)
            if vkey(v) != vkey(y):
                return False
        v = task.query
        for t in chain:
            v = t(v)
        return vkey(v) == vkey(answer)
    except Exception:
        return False


def grade(task, res):
    return res.status == UNIQUE and res.certificate_valid is True and vkey(res.answer) == vkey(task.answer)


# --------------------------------------------------------------------------- the learner
class NexusLearner:
    """One persistent learner across domains: forces, world model, policy, macros, explorer."""

    def __init__(self, *, seed=0, meta=True, transfer=True, frozen=False, skeleton_mode="none", invent=True):
        self.meta, self.transfer, self.frozen = meta, transfer, frozen
        self.skeleton_mode = skeleton_mode   # none | all | transfer
        self.skeleton_prior = Counter()      # domain-agnostic (type, slot) schemas seen in certified solutions
        self.relevance = Counter()           # (abstract I/O feature, skeleton type) -> certified uses
        self.feature_seen = Counter()        # abstract I/O feature -> certified solutions
        self.invent = invent
        self.policy = StoneUsefulnessPolicy()
        self.rng = random.Random(seed)
        self.classifier = AtomicForceClassifier()
        self.setup_work = 0
        self.training_work = 0
        self.macro_stats = Counter()       # chain length -> (promoted, reused) learned for invent-vs-reuse
        self.macro_outcomes = []           # (length, reused?) hindsight log
        self.failure_log = []
        self.law_evidence = defaultdict(list)   # family -> [held-out validity] from source domains
        self.policy_prune = False                # enabled only if leave-one-domain-out recall holds
        self.domain_path_logs = {}               # domain -> (expansions, path_keys)
        self.policy_active = True                # meta decision: keep paying for the force policy?
        self.explore_history = []                # (cost, estimated gain) per explored domain
        self.meta_decisions = []

    # ---- entering a domain (zero target labels: only unlabeled probes of its tools)
    def enter(self, domain, meter):
        if not self.transfer:
            self.policy = StoneUsefulnessPolicy()
        probes = domain.inputs(random.Random(f"probe:{domain.name}"), 12)
        if domain.messy_sampler:
            probes += domain.inputs(random.Random(f"probe-messy:{domain.name}"), 6, messy=True)
        self.forces = {}
        for t in domain.tools:
            self.forces[t.name] = self.classifier.classify(t.fn, probes, meter=meter).force
        self.model = ForwardWorldModel()
        self.model.fit_probes(domain.tools, probes, meter)
        law_probes = probes[:6]
        if not self.frozen and (domain.family == "source" or self.meta) and self.transfer is True:
            # Learning-to-learn: validate only families whose evidence is still thin.
            thin = None if domain.family == "source" else {f for f in self._all_families() if len(self.law_evidence[f]) < 4}
            if thin is None or thin:
                for fam, ok in measure_law_reliability(domain, self.forces, meter, holdout=20, only=thin).items():
                    self.law_evidence[fam].extend(ok)
            else:
                self.meta_decisions.append(dict(domain=domain.name, decision="skip_law_validation_evidence_sufficient"))
        if self.transfer == "all_laws":
            self.laws = LawLibrary().discover(list(domain.tools), law_probes, self.forces, meter, allowed=None)
        elif self.transfer:
            allowed = self.reliable_families()
            self.laws = LawLibrary().discover(list(domain.tools), law_probes, self.forces, meter, allowed=allowed)
        else:
            self.laws = None
        self.tools = list(domain.tools)
        self.macros = {}
        self.macro_uses = Counter()
        self.recovery_map = {}   # tool -> alternatives seen on certified solution paths (fault boundaries)
        self.predict_on = True
        self.fault_memory = {}           # (tool, alt, input phase) -> alt survives where tool faults
        self.predict_stats = [0, 0, 0]   # predictions charged, model prunes, tasks observed
        self.gram_counts = Counter()     # recurrence of sub-chains in certified solutions
        self.domain = domain
        return probes

    def _all_families(self):
        fams = set()
        for a in self.forces.values():
            fams |= {LawLibrary.family("idempotent", a), LawLibrary.family("involution", a)}
            for b in self.forces.values():
                fams.add(LawLibrary.family("commute", *sorted((a, b))))
        return fams

    def should_explore(self):
        """Meta decision from measured history: explore while estimated stream gain exceeds its cost."""
        if not self.meta:
            return False
        recent = self.explore_history[-2:]
        if len(recent) == 2 and all(gain <= cost for cost, gain in recent):
            self.meta_decisions.append(dict(domain=self.domain.name, decision="skip_exploration_not_paying"))
            return False
        return True

    def reliable_families(self, min_evidence=2, precision=0.95):
        return {f for f, ok in self.law_evidence.items() if len(ok) >= min_evidence and sum(ok) / len(ok) >= precision}

    def validate_policy_transfer(self, meter, floor=0.95):
        """Learning-to-learn: does the force policy learned on other domains keep recall on a held-out one?

        Leave-one-domain-out from per-domain counters (total minus held-out), O(keys x domains), charged.
        """
        per = {}
        for name, (exp, path) in self.domain_path_logs.items():
            per[name] = (Counter(exp), Counter(path))
        tot_e = sum((e for e, _ in per.values()), Counter())
        tot_u = sum((u for _, u in per.values()), Counter())
        recalls = []
        for held, (e_h, u_h) in per.items():
            meter.charge("meta_learning_work_units", len(tot_e) + 1)
            pol = StoneUsefulnessPolicy()
            pol.expanded, pol.useful = tot_e - e_h, tot_u - u_h
            pol.retune(meter)
            if u_h:
                recalls.append(sum(n for k, n in u_h.items() if pol.allow(k)) / sum(u_h.values()))
        self.policy_prune = bool(recalls) and min(recalls) >= floor
        self.policy_validation = dict(recalls=recalls, enabled=self.policy_prune)
        return self.policy_validation

    def toolset(self):
        return self.tools + [m for m in self.macros.values()]

    @staticmethod
    def io_feature(task):
        """Domain-agnostic task signature: (input kind, output kind, mass relation)."""
        def kind(v):
            return "map" if isinstance(v, dict) else "str" if isinstance(v, (str, bytes)) else \
                "seq" if isinstance(v, (list, tuple)) else "scalar"
        x, y = task.public[0]
        rel = {(amass(b) > amass(a)) - (amass(b) < amass(a)) for a, b in task.public}
        return (kind(x), kind(y), tuple(sorted(rel)))

    def relevant_types(self, task, *, min_seen=3, floor=0.1):
        """Learned skeleton-type relevance for this I/O signature, or None (no evidence -> all types)."""
        f = self.io_feature(task)
        n = self.feature_seen[f]
        if n < min_seen:
            return None
        from nexus.wave24_skeletons import SKELETON_TYPES
        return {t for t in SKELETON_TYPES if self.relevance[(f, t)] / n >= floor}

    def task_skeletons(self, task, restrict=True):
        """Skeleton instantiations for this task (parameters fitted on its public inputs only)."""
        if self.skeleton_mode == "none":
            return []
        from nexus.wave24_skeletons import skeleton_library, spec_key, SKELETON_TYPES
        types = self.relevant_types(task) if (restrict and self.meta) else None
        lib = skeleton_library([x for x, _ in task.public], self.tools, types=SKELETON_TYPES if types is None else types)
        if self.skeleton_mode == "transfer":
            allowed = {k for k, n in self.skeleton_prior.items() if n >= 1}
            lib = [t for t in lib if spec_key(t) in allowed]
        return lib

    # ---- solving one task with the full learned system
    def solve(self, task, *, budget, max_depth=4):
        restricted = self.meta and self.skeleton_mode != "none" and self.relevant_types(task) is not None
        task_tools = self.toolset() + self.task_skeletons(task)
        for t in task_tools:
            # skeleton types are domain-agnostic force classes the policy can transfer across families
            self.forces.setdefault(t.name, "SK_" + t.name.split("(")[0] if t.kind == "skeleton" else "F_COMPOSITE")
        res = solve(task, task_tools, max_depth=max_depth, budget=budget, learned=True,
                    model=self.model, policy=self.policy if self.policy_prune else None, forces=self.forces_all(),
                    recovery_map=self.recovery_map, laws=self.laws, predict=self.predict_on,
                    fault_memory=self.fault_memory)
        if not getattr(self, "_exploring", False):
            self._gate_prediction(task, res)
        if restricted and res.status != UNIQUE and res.work < budget:
            # Declared fallback: learned skeleton relevance mispredicted -> full skeleton library.
            full = self.toolset() + self.task_skeletons(task, restrict=False)
            for t in full:
                self.forces.setdefault(t.name, "SK_" + t.name.split("(")[0] if t.kind == "skeleton" else "F_COMPOSITE")
            spent = res.work
            res = solve(task, full, max_depth=max_depth, budget=max(1, budget - spent), learned=True, model=self.model,
                        policy=self.policy if self.policy_prune else None, forces=self.forces_all(),
                        laws=self.laws, predict=self.predict_on, fault_memory=self.fault_memory)
            res.work += spent
            res.relevance_fallback = True
            task_tools = full
        if res.status == "UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED" or (res.status == "NO_PROGRAM_IN_BOUNDED_GRAMMAR"
                                                                   and (res.pruned_policy or res.pruned_model)):
            # Declared fallback: the pruned space was empty/insufficient -> exhaustive search,
            # paying the remaining budget. Work of BOTH passes is counted.
            spent = res.work
            res2 = solve(task, task_tools, max_depth=max_depth, budget=max(1, budget - spent), learned=False,
                         model=self.model, forces=self.forces_all(), laws=self.laws)
            res2.work += spent
            res2.fallback = True
            res = res2
        if res.status == UNIQUE and res.certificate_valid and not self.frozen:
            self._learn_from(task, res)
        else:
            self.failure_log.append(dict(task=task, status=res.status))
        return res

    def _gate_prediction(self, task, res, window=3):
        """Learning-to-learn: keep forward-model pruning only while its measured payoff exceeds its cost."""
        if not self.predict_on or not self.meta:
            return
        st = self.predict_stats
        st[0] += res.meter.counts.get("world_model_prediction_work_units", 0)
        st[1] += res.pruned_model
        st[2] += 1
        execution_cost = len(task.public) + 1
        if st[2] >= window and st[1] * execution_cost < st[0]:
            self.predict_on = False
            self.meta_decisions.append(dict(domain=self.domain.name, decision="disable_forward_model_pruning",
                                            predictions=st[0], prunes=st[1]))

    def forces_all(self):
        f = dict(self.forces)
        for name in self.macros:
            f[name] = "F_COMPOSITE"
        return f

    def _learn_from(self, task, res):
        meter = WorkMeter(limit=10**9)
        if self.policy_active:
            self.policy.learn(res.expansions, res.path_keys, meter)
            log = self.domain_path_logs.setdefault(self.domain.name, ([], []))
            log[0].extend(res.expansions)
            log[1].extend(res.path_keys)
        self.training_work += meter.total
        for name in res.witness:
            if name in self.macros:
                self.macro_uses[name] += 1
        for tool in getattr(res, "_chain", ()):
            if tool.kind == "recovery":
                self.recovery_map.setdefault(tool.children[0].name, set()).add(tool.children[1].name)
        from nexus.wave24_skeletons import skeletons_in
        keys = skeletons_in(getattr(res, "_chain", ()))
        for key in keys:
            self.skeleton_prior[key] += 1
        f = self.io_feature(task)
        self.feature_seen[f] += 1
        for t in {k[0] for k in keys}:
            self.relevance[(f, t)] += 1
        if getattr(self, "_exploring", False) or not self.invent:
            return  # self-play contributes knowledge (faults, transitions), never stream recurrence counts
        # invent-vs-reuse: a sub-chain (primitives, recovery composites or existing macros) is
        # invented only once it RECURS in certified solutions; composites of composites raise the layer.
        chain = list(getattr(res, "_chain", ()))
        for i in range(len(chain) - 1):
            pair = tuple(chain[i:i + 2])
            g = tuple(t.name for t in pair)
            self.gram_counts[g] += 1
            if self.gram_counts[g] == 2 and self.should_invent(2):
                m = macro_tool({t.name: t for t in pair}, g)
                self.macros.setdefault(m.name, m)

    def should_invent(self, length):
        if not self.meta:
            return True
        outcomes = [r for L, r in self.macro_outcomes if L == length]
        if len(outcomes) < 3:
            return True
        return sum(outcomes) / len(outcomes) >= 0.25

    def close_domain(self, meter):
        """End of a domain: hindsight invent-vs-reuse labels, eviction, meta-retune."""
        decisions = []
        for name, m in self.macros.items():
            reused = self.macro_uses[name] > 0
            self.macro_outcomes.append((len(m.parts), reused))
            decisions.append(reused)
        if self.meta and self.policy_active:
            self.policy.retune(meter)
            if len(self.domain_path_logs) >= 2:
                self.validate_policy_transfer(meter)
                if not self.policy_prune and len(self.domain_path_logs) >= 3:
                    self.policy_active = False   # stop investing in a heuristic that does not transfer
                    self.meta_decisions.append(dict(domain=self.domain.name, decision="retire_force_policy",
                                                    recalls=self.policy_validation["recalls"]))
        return dict(promoted=len(decisions), reused=sum(decisions))

    # ---- gap 4: idle autopoietic exploration with counterfactual promotion
    def explore(self, domain, *, tasks=6, budget=2000, meter, task_filter=None, pool=None):
        """Idle self-play on unlabeled (incl. messy) inputs.

        Discoveries: (1) policy / world-model experience from self-solved tasks,
        (2) fault boundaries -> recovery partners on certified paths,
        (3) helper chains promoted only on measured counterfactual ΔW > 0 on >= 2 self tasks.
        Every self-play and counterfactual unit is charged to `meter`.
        """
        from nexus.wave24_domains import generate_task
        rng = random.Random(f"explore:{domain.name}:{self.rng.random()}")
        own = []
        for i in range(tasks * (40 if task_filter else 4)):
            t = generate_task(domain, rng, rng.choice((2, 3)), messy=bool(domain.messy_sampler) and i % 2 == 0,
                              recovery=bool(domain.messy_sampler) and i % 4 == 0)
            meter.charge("self_task_proposal_work_units")
            if t is not None and (task_filter is None or task_filter(t)):
                own.append(t)
            if len(own) == tasks:
                break
        grams, solved = Counter(), []
        self._exploring = True
        for t in own:
            r = self.solve(t, budget=budget)
            meter.charge("exploration_work_units", r.work)
            if r.status == UNIQUE and r.certificate_valid:
                solved.append((t, r))
                for g in {tuple(r.witness[i:i + 2]) for i in range(len(r.witness) - 1)}:
                    grams[g] += 1
        self._exploring = False
        promoted, rejected = [], []
        by_name = {x.name: x for x in self.tools}
        for chain, count in grams.most_common(3):
            if count < 2 or not all(c in by_name for c in chain):
                continue
            m = macro_tool(by_name, chain)
            gains = []
            for t, r in solved:
                if not any(tuple(r.witness[i:i + 2]) == chain for i in range(len(r.witness) - 1)):
                    continue
                with_m = solve(t, self.toolset() + [m], budget=budget, learned=True, model=self.model,
                               policy=self.policy, forces={**self.forces_all(), m.name: "F_COMPOSITE"},
                               record=False, recovery_map=self.recovery_map)
                meter.charge("counterfactual_work_units", with_m.work)
                if grade(t, with_m):
                    gains.append(r.work - with_m.work)
            if len(gains) >= 3 and sum(gains) > 0 and all(g > 0 for g in gains):
                self.macros[m.name] = m
                promoted.append(dict(macro=m.name, gains=gains))
            else:
                rejected.append(dict(macro=m.name, gains=gains))
        return dict(self_tasks=len(own), self_solved=len(solved), promoted=promoted, rejected=rejected,
                    fault_boundaries={k: sorted(v) for k, v in self.recovery_map.items()})

    def evict_net_negative(self, window_results):
        """Retire helpers that were expanded but never on a solution path in the recent window."""
        used = Counter(n for r in window_results for n in r.witness)
        evicted = [name for name in list(self.macros) if used[name] == 0]
        for name in evicted:
            self.macros.pop(name)
        return evicted


# --------------------------------------------------------------------------- gap 8: grounding & planning
_WORD = re.compile(r"[a-z]+")


def _bag(text):
    return Counter(w for w in _WORD.findall(text.lower()) if len(w) > 2)


class DocstringRetriever:
    """Symbolic-linguistic grounding: TF-IDF retrieval of tools from task text.

    Used because no local LLM runtime is available in this environment; the
    tools' own docstrings are the knowledge source (no hand-written bridges).
    """

    def __init__(self, tools):
        self.tools = list(tools)
        self.docs = {t.name: _bag(t.doc + " " + t.name.replace("_", " ")) for t in self.tools}
        df = Counter(w for bag in self.docs.values() for w in bag)
        self.idf = {w: math.log((1 + len(self.docs)) / (1 + c)) + 1 for w, c in df.items()}

    def rank(self, text, k=3):
        q = _bag(text)
        def score(name):
            d = self.docs[name]
            return sum(q[w] * d[w] * self.idf.get(w, 0) ** 2 for w in q) / (1 + math.sqrt(sum(v * v for v in d.values())))
        return sorted(self.docs, key=lambda n: (-score(n), n))[:k]


def degrade_description(text, rng, dropout=0.35):
    """Paraphrase noise: drop words and add distractors so retrieval is not string matching."""
    stages = []
    for stage in text.split(" then "):
        words = [w for w in stage.split() if rng.random() > dropout] or stage.split()[:1]
        words += rng.sample(["please", "carefully", "the", "data", "result", "value", "now"], 2)
        rng.shuffle(words)
        stages.append(" ".join(words))
    return " then ".join(stages)


def grounded_plan_solve(task, tools, description, *, budget, k=3):
    """Long-horizon planning: decompose text into ordered stages, ground each stage, verify on IO."""
    meter = WorkMeter(limit=budget, wall_limit=10.0)
    retriever = DocstringRetriever(tools)
    stages = [s for s in description.split(" then ") if s.strip()]
    meter.charge("grounding_work_units", len(stages) * len(tools))
    options = [retriever.rank(s, k) for s in stages]
    by_name = {t.name: t for t in tools}
    inputs = [x for x, _ in task.public] + [task.query]
    targets = [vkey(y) for _, y in task.public]
    fits = []
    try:
        frontier = [(inputs, ())]
        for stage_opts in options:
            nxt = []
            for values, chain in frontier:
                for name in stage_opts:
                    tool = by_name[name]
                    out, faulted = apply_tool(tool, values, meter)
                    if faulted:
                        for alt in stage_opts:
                            if alt != name:
                                out, f2 = apply_tool(recovery_tool(tool, by_name[alt]), values, meter, "recovery_work_units")
                                if not f2:
                                    nxt.append((out, chain + (f"try[{name}|{alt}]",)))
                        continue
                    nxt.append((out, chain + (name,)))
            frontier = nxt
        for values, chain in frontier:
            if [vkey(v) for v in values[:-1]] == targets:
                fits.append((chain, values[-1]))
    except WorkExhausted:
        return dict(status="UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED", work=meter.total, stages=len(stages))
    if not fits:
        return dict(status="NO_PROGRAM_IN_GROUNDED_PLAN_SPACE", work=meter.total, stages=len(stages))
    answers = {vkey(a) for _, a in fits}
    status = "UNIQUE_IN_GROUNDED_PLAN_SPACE" if len(answers) == 1 else "AMBIGUOUS_WITNESS_FOUND"
    return dict(status=status, work=meter.total, stages=len(stages), answer=fits[0][1], witness=fits[0][0],
                correct=status.startswith("UNIQUE") and vkey(fits[0][1]) == vkey(task.answer))


class IntrinsicGoalSetter:
    """Turn failure logs into concrete self-improvement goals (abstract transitions to cover)."""

    def goals(self, failures, k=2):
        counts = Counter()
        for f in failures:
            t = f["task"]
            src = [abstract(x) for x, _ in t.public]
            dst = [abstract(y) for _, y in t.public]
            counts[(src[0][0], dst[0][0], direction(src, dst))] += 1
        return [dict(in_type=a, out_type=b, direction=d, failures=n) for (a, b, d), n in counts.most_common(k)]

    def matches(self, goal, task):
        src = [abstract(x) for x, _ in task.public]
        dst = [abstract(y) for _, y in task.public]
        return (src[0][0], dst[0][0], direction(src, dst)) == (goal["in_type"], goal["out_type"], goal["direction"])


# --------------------------------------------------------------------------- statistics
def sign_test(diffs):
    """Exact two-sided binomial sign test on paired differences (zeros dropped)."""
    pos = sum(d > 0 for d in diffs)
    neg = sum(d < 0 for d in diffs)
    n = pos + neg
    if n == 0:
        return dict(n=0, positive=0, negative=0, p_value=1.0)
    k = min(pos, neg)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return dict(n=n, positive=pos, negative=neg, p_value=min(1.0, 2 * p))


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for m in range(i, j + 1):
                r[order[m]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) or 1.0
    return num / den
