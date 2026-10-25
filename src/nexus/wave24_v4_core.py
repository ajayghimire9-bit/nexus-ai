"""Wave 24 v4 core: ObsEGraph witness conservation, Popper constraints, propose_refinement.

Reused: `wave24_domains.Tool/vkey`, `wave24_quotient_core.WorkMeter/WorkExhausted` (one meter, every
unit charged). New here, because the v3 chain solver has no per-input fault records, no guard space
and no explicit witness sets:

* phi(x) - total (never-raising) relational features of any value (emptiness, zeros, keys, order,
  token well-formedness, bounds, type); `predicates_for` invents executable predicates (atoms and
  2-conjunctions over phi) that separate a pass set from a fail set.
* ObsEGraph - observational-equivalence classes keyed by the public signature; inside a class every
  distinct query (+ probe) output keeps its own concrete representative program, so the witness set
  never drops an output: Y_q is a subset of Y^_q under parent composition. UNIQUE iff |Y^_q| == 1 with a
  verified witness; AMBIGUOUS iff two concrete verified programs disagree on the query.
* Popper constraints (sound): a prefix whose public outputs violate the functional dependency
  state_i == state_j => y_i == y_j cannot be completed by any deterministic suffix, so the whole
  family {s o p} is pruned; the violating public signature is stored as a nogood (O(1) lookups).
* guard(c, P, r) programs: `if c(x): P(x) else r(x)` with an explicit predicate - an exception in P on
  a routed input propagates (no exception swallowing anywhere).
* propose_refinement(...) -> RefinementPlan(candidate_predicate, distinguishing_test, candidate_repair).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from itertools import combinations

from nexus.wave24_domains import Tool, vkey
from nexus.wave24_quotient_core import WorkExhausted, WorkMeter

RAISED = ("__raised__",)
UNIQUE = "UNIQUE_IN_BOUNDED_SPACE"
AMBIGUOUS = "AMBIGUOUS_WITNESS_FOUND"
NONE_FOUND = "NO_PROGRAM_IN_DECLARED_SPACE"
EXHAUSTED = "UNKNOWN_BUDGET_EXHAUSTED"


def meter(limit):
    return WorkMeter(limit=int(limit), wall_limit=900.0)


# --------------------------------------------------------------------------- relational features
def _atoms(v, depth=0):
    if isinstance(v, dict):
        for x in v.values():
            yield from _atoms(x, depth + 1)
    elif isinstance(v, (list, tuple)) and depth < 3:
        for x in v:
            yield from _atoms(x, depth + 1)
    else:
        yield v


def _num(a):
    return isinstance(a, (int, float)) and not isinstance(a, bool)


def phi(v):
    """Total relational feature map; every feature is computed without raising."""
    f = {"type": type(v).__name__}
    if isinstance(v, (list, tuple, str, bytes, dict)):
        f["len"] = len(v)
        f["empty"] = len(v) == 0
    atoms = list(_atoms(v)) if not isinstance(v, (str, bytes)) else []
    nums = [a for a in atoms if _num(a)]
    f["has_zero"] = any(a == 0 for a in nums)
    f["nonfinite"] = any(isinstance(a, float) and not math.isfinite(a) for a in nums)
    f["has_none"] = any(a is None for a in atoms)
    if nums and all(math.isfinite(a) for a in nums):
        f["sum_zero"] = sum(nums) == 0
        f["max_num"] = max(nums)
        f["min_num"] = min(nums)
    if isinstance(v, dict):
        f["keys"] = frozenset(map(str, v))
    if isinstance(v, list) and v and all(isinstance(r, dict) for r in v):
        f["common_keys"] = frozenset.intersection(*(frozenset(map(str, r)) for r in v))
        for k in sorted(f["common_keys"]):
            col = [r[k] if k in r else r.get(int(k)) if k.isdigit() else None for r in v]
            if len(v) >= 2 and all(_num(c) for c in col):
                f[f"sorted_by:{k}"] = col == sorted(col)      # order relation over a shared numeric field
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        try:
            f["sorted"] = list(v) == sorted(v)
        except TypeError:
            f["sorted"] = None
    if isinstance(v, str):
        toks = [p.strip() for p in v.split(",")]
        f["numeric_tokens"] = bool(toks) and all(re.fullmatch(r"-?\d+", p) for p in toks)
        f["is_int_text"] = re.fullmatch(r"\s*-?\d+\s*", v) is not None
    if isinstance(v, bytes):
        f["len_mod4"] = len(v) % 4 == 0
    return f


BOOL_FEATURES = ("empty", "has_zero", "nonfinite", "has_none", "sum_zero", "sorted", "numeric_tokens",
                 "is_int_text", "len_mod4")


@dataclass(frozen=True)
class Predicate:
    name: str
    family: str
    test: tuple = field(compare=False, repr=False)      # ((feature, op, value), ...) conjunction
    size: int = 1

    def __call__(self, x):
        f = phi(x)
        return all(_atom(f, a) for a in self.test)


def _atom(f, a):
    feat, op, val = a
    if op == "is":
        return f.get(feat) is val
    if op == "type":
        return f.get("type") == val
    if op == "haskey":
        return val in f.get("keys", ()) or val in f.get("common_keys", ())
    if op == "nokey":
        return not (val in f.get("keys", ()) or val in f.get("common_keys", ()))
    x = f.get(feat)
    if not _num(x):
        return False
    return x <= val if op == "le" else x >= val


def atom_candidates(xs):
    """Atomic predicates instantiated from the observed inputs (generic grammar, no domain hints)."""
    fs = [phi(x) for x in xs]
    out = []
    for feat in BOOL_FEATURES:
        if any(feat in f for f in fs):
            for val in (True, False):
                out.append(Predicate(f"{feat}={val}", feat, ((feat, "is", val),)))
    for feat in sorted({k for f in fs for k in f if k.startswith("sorted_by:")}):
        for val in (True, False):
            out.append(Predicate(f"{feat}={val}", "sorted", ((feat, "is", val),)))
    for ty in sorted({f["type"] for f in fs}):
        out.append(Predicate(f"type={ty}", "type", (("type", "type", ty),)))
    keys = set()
    for f in fs:
        keys |= set(f.get("keys", ())) | set(f.get("common_keys", ()))
    for k in sorted(keys):
        out.append(Predicate(f"has:{k}", "key", (("keys", "haskey", k),)))
        out.append(Predicate(f"lacks:{k}", "key", (("keys", "nokey", k),)))
    for feat, fam in (("len", "len"), ("max_num", "bound"), ("min_num", "bound")):
        vals = sorted({f[feat] for f in fs if _num(f.get(feat))})
        for v in vals:
            out.append(Predicate(f"{feat}<={v}", fam, ((feat, "le", v),)))
            out.append(Predicate(f"{feat}>={v}", fam, ((feat, "ge", v),)))
    return out


def predicates_for(pass_xs, fail_xs, *, families=None, max_size=2, meter_=None, limit=None, grammar_xs=None):
    """Executable predicates c with c(x) True on every pass input and False on every fail input.

    Size-1 atoms first; 2-conjunctions only of atoms that hold on every pass input. Each atom
    evaluation on one input is charged one unit. `families` (ordered) restricts the grammar.
    """
    xs = list(pass_xs) + list(fail_xs)
    atoms = atom_candidates(list(grammar_xs) if grammar_xs is not None else xs)
    if families is not None:
        rank = {f: i for i, f in enumerate(families)}
        atoms = sorted((a for a in atoms if a.family in rank), key=lambda a: rank[a.family])
    found, keep = [], []
    for a in atoms:
        if meter_ is not None:
            meter_.charge("predicate_work_units", len(xs))
        on_pass = all(a(x) for x in pass_xs)
        if not on_pass:
            continue
        keep.append(a)
        if not any(a(x) for x in fail_xs):
            found.append(a)
            if limit and len(found) >= limit:
                return found
    if max_size >= 2 and not found:
        for a, b in combinations(keep, 2):
            if meter_ is not None:
                meter_.charge("predicate_work_units", len(fail_xs))
            if not any(a(x) and b(x) for x in fail_xs):
                found.append(Predicate(f"{a.name}&{b.name}", f"{a.family}&{b.family}", a.test + b.test, 2))
                if limit and len(found) >= limit:
                    break
    return found


# --------------------------------------------------------------------------- programs
def run_chain(chain, x):
    for t in chain:
        x = t(x)
    return x


def guard_tool(pred, chain, recovery):
    """guard(c, P, r): explicit predicate routing; exceptions inside P or r propagate."""
    kind, r = recovery
    if kind == "const":
        rfun, rname, rsize = (lambda x, c=r: c), repr(r), 0
    elif kind == "tool":
        rfun, rname, rsize = r, r.name, 1
    else:
        rfun, rname, rsize = (lambda x: x), "id", 0

    def fn(x, pred=pred, chain=tuple(chain), rfun=rfun):
        return run_chain(chain, x) if pred(x) else rfun(x)
    body = ">".join(t.name for t in chain)
    return Tool(f"guard[{pred.name}?{body}:{rname}]", fn, f"if {pred.name} then {body} else {rname}",
                cost=1 + len(chain) + rsize, layer=1, parts=tuple(t.name for t in chain), kind="guard")


def program_size(chain):
    s = 0
    for t in chain:
        s += (len(t.parts) + 1) if t.kind == "guard" else max(1, len(t.parts)) if t.kind == "macro" else 1
    return s


# --------------------------------------------------------------------------- ObsEGraph
class ObsEGraph:
    """Observational-equivalence classes with conserved witness sets.

    Key = public signature; inside a class, each distinct rest-signature (query + probe outputs) keeps
    its first (cheapest under breadth-first order) concrete representative program.
    """

    def __init__(self, n_public):
        self.n = n_public
        self.classes = {}

    def add(self, program, values):
        keys = tuple(vkey(v) for v in values)
        pub, rest = keys[:self.n], keys[self.n:]
        cls = self.classes.setdefault(pub, {})
        if rest in cls:
            return False
        cls[rest] = (tuple(program), tuple(values))
        return True

    def witnesses(self, target_keys):
        """{query-output key: (program, query value)} for the class matching the targets."""
        cls = self.classes.get(tuple(target_keys), {})
        out = {}
        for rest, (prog, vals) in cls.items():
            if vals[-1] is not RAISED:
                out.setdefault(rest[-1], (prog, vals[-1]))
        return out


def compose_witness_set(child_outputs, parent):
    """Sound parent composition of a conserved witness set: Y^_q(parent) = {parent(y) : y in Y^_q}."""
    out = set()
    for y in child_outputs:
        try:
            out.add(vkey(parent(y)))
        except Exception:
            out.add(RAISED)
    return out


def lossy_representative_set(child_outputs, keep=2):
    """The v1 bug, kept only for the regression test: a bounded summary (min and max) of a class."""
    ys = sorted(child_outputs)
    return {ys[0], ys[-1]} if len(ys) > keep else set(ys)


# --------------------------------------------------------------------------- search
@dataclass
class SearchResult:
    status: str
    answer: object = None
    witness: tuple = ()
    size: int = 0
    work: int = 0
    evaluations: int = 0
    pruned_popper: int = 0
    hypotheses: list = field(default_factory=list)    # [(program names, query value, program)]
    partials: list = field(default_factory=list)      # [(chain, vector, outputs)] for refinement


def _apply(tool, values, m):
    out = []
    for v in values:
        if v is RAISED:
            out.append(RAISED)
            continue
        m.charge("search_work_units", tool.cost)
        try:
            out.append(tool(v))
        except Exception:
            out.append(RAISED)
    return out


def fd_violation(state_keys, target_keys):
    """Functional-dependency check: equal states that need different outputs (sound prune)."""
    seen = {}
    for s, y in zip(state_keys, target_keys):
        if s in seen and seen[s] != y:
            return True
        seen[s] = y
    return False


class Searcher:
    """Resumable iterative-deepening chain search with ObsEGraph dedup and Popper nogoods.

    public: ((x, y), ...) including observed probe pairs. `extra`: unlabeled inputs whose outputs are
    tracked (and so conserved) but not constrained. `order(prev_op, ops)` may reorder the ops expanded
    after `prev_op` (search order only - every op is still expanded, so a UNIQUE certificate is over
    the full declared level). `early_ambiguity`: stop a level as soon as two concrete witnesses
    disagree on the query (sound: AMBIGUOUS needs only two verified disagreeing programs).
    """

    def __init__(self, public, query, ops, *, popper=True, extra=(), order=None, early_ambiguity=False,
                 partial_depth=2, m=None, budget=20000, max_depth=3, abstract=None):
        self.m = m or meter(budget)
        self.xs = [x for x, _ in public]
        self.targets = [vkey(y) for _, y in public]
        self._target_values = [y for _, y in public]
        self.n = len(self.xs)
        self.inputs = self.xs + list(extra) + [query]
        self.graph = ObsEGraph(self.n)
        self.graph.add((), self.inputs)
        self.nogood = set()
        self.ops = list(ops)
        self.order = order
        self.popper, self.early = popper, early_ambiguity
        self.partial_depth = partial_depth
        # abstract(values_public, targets, remaining_depth, meter) -> True iff provably no plain completion
        # reaches the targets (sound pruner; its own evaluation work is charged by the callee)
        self.abstract, self.max_depth = abstract, max_depth
        self.pruned_abstract = 0
        self.level_sizes = []
        self.early_stopped_depth = None
        self._partial_keys = set()
        self._side, self._side_keys = [], set()
        self.frontier = [((), self.inputs)]
        self.depth = 0
        self.res = SearchResult(NONE_FOUND)
        self._start = self.m.total

    def level(self):
        """Expand exactly one more depth. Returns {query key: (program, query value)} of plain goals found
        there (with early_ambiguity, expansion stops once two goals disagree on the query).

        Popper nogoods are sound for PLAIN completions only: a guard's then-branch needs to match only a
        subset of the public pairs. So a pruned (or partly raising) state below `partial_depth` is still
        expanded once more, solely to record guard partials; it never becomes a plain goal or reaches a
        deeper plain level.
        """
        n, targets = self.n, self.targets
        depth = self.depth + 1
        nxt, side, found = [], [], {}
        res = self.res
        sources = [(c, v, False) for c, v in self.frontier] + [(c, v, True) for c, v in self._side]
        for chain, values, partial_only in sources:
            ops = self.order(chain[-1] if chain else None, self.ops) if self.order else self.ops
            for op in ops:
                out = _apply(op, values, self.m)
                res.evaluations += 1
                prog = chain + (op,)
                pub = out[:n]
                raised = [v is RAISED for v in pub]
                keys = tuple(vkey(v) for v in pub)
                full = None
                if depth <= self.partial_depth and not all(k == t for k, t in zip(keys, targets)):
                    vec = tuple("raise" if r else ("match" if k == t else "miss")
                                for r, k, t in zip(raised, keys, targets))
                    full = tuple(vkey(v) for v in out)
                    if "match" in vec and full not in self._partial_keys:
                        self._partial_keys.add(full)
                        res.partials.append((prog, vec, out))
                if partial_only:
                    continue
                keep_side = depth < self.partial_depth
                if any(raised):
                    if keep_side and not all(raised):
                        self._side_add(side, prog, out, full)
                    continue
                if self.popper and (keys in self.nogood or fd_violation(keys, targets)):
                    self.nogood.add(keys)
                    res.pruned_popper += 1
                    if keep_side:
                        self._side_add(side, prog, out, full)
                    continue
                if not self.graph.add(prog, out):
                    continue
                if self.abstract is not None and list(keys) != targets and \
                        self.abstract(pub, self._target_values, self.max_depth - depth, self.m):
                    self.pruned_abstract += 1
                    continue
                if list(keys) == targets:
                    if out[-1] is not RAISED:
                        found.setdefault(vkey(out[-1]), (prog, out[-1]))
                        if self.early and len(found) >= 2:
                            self.depth = depth
                            self.early_stopped_depth = depth
                            return found
                    continue
                nxt.append((prog, out))
        self.depth = depth
        self.frontier = nxt
        self._side = side
        self.level_sizes.append(len(nxt))
        return found

    def _side_add(self, side, prog, out, full):
        k = full or tuple(vkey(v) for v in out)
        if k not in self._side_keys:
            self._side_keys.add(k)
            side.append((prog, out))

    def run_to(self, max_depth):
        """Plain-chain certificate: first depth with a goal (UNIQUE / AMBIGUOUS), else NONE / EXHAUSTED."""
        res = self.res
        try:
            while self.depth < max_depth and res.status == NONE_FOUND:
                found = self.level()
                if found:
                    res.hypotheses = [(tuple(t.name for t in p), q, p) for p, q in found.values()]
                    res.size = self.depth
                    res.witness, res.answer = res.hypotheses[0][0], res.hypotheses[0][1]
                    res.status = UNIQUE if len(found) == 1 else AMBIGUOUS
        except WorkExhausted:
            res.status = EXHAUSTED
        res.work = self.m.total - self._start
        return res


def search(public, query, ops, *, max_depth=3, budget=20000, popper=True, m=None, **kw):
    return Searcher(public, query, ops, popper=popper, m=m, budget=budget, **kw).run_to(max_depth)


def verify(program, public, query, answer):
    """Independent re-execution of a certified program on every public pair and the query."""
    try:
        for x, y in public:
            if vkey(run_chain(program, x)) != vkey(y):
                return False
        return vkey(run_chain(program, query)) == vkey(answer)
    except Exception:
        return False


# --------------------------------------------------------------------------- guard levels
GUARD_SHAPES = {2: ((1, 0),), 3: ((2, 0), (1, 1))}   # size -> (len(P), recovery size); predicate size 1


def recovery_candidates(public, tools, m):
    """Every recovery that matches at least one public pair: constants (public outputs), identity, tools."""
    xs = [x for x, _ in public]
    ys = [vkey(y) for _, y in public]
    out = []
    for y in {vkey(y): y for _, y in public}.values():
        out.append((("const", y), frozenset(i for i, k in enumerate(ys) if k == vkey(y))))
    ident = frozenset(i for i, (x, k) in enumerate(zip(xs, ys)) if vkey(x) == k)
    if ident:
        out.append((("id", None), ident))
    for t in tools:
        S = set()
        for i, x in enumerate(xs):
            m.charge("repair_work_units", t.cost)
            try:
                if vkey(t(x)) == ys[i]:
                    S.add(i)
            except Exception:
                pass
        if S:
            out.append((("tool", t), frozenset(S)))
    return out


def _rsize(r):
    return 1 if r[0] == "tool" else 0


def _route_answer(chain, r, c, q, m):
    m.charge("verification_work_units", 1)
    try:
        if c(q):
            return run_chain(chain, q)
        return q if r[0] == "id" else r[1] if r[0] == "const" else r[1](q)
    except Exception:
        return RAISED


def guard_level(public, query, partials, size, tools, m, *, recs=None, early=False, known=None,
                order_partials=None, order_recoveries=None, families=None):
    """Exact constrained enumeration of every guard(c, P, r) of `size` that fits all public pairs.

    For P with match set S_P and r with match set S_r, a fitting predicate must be true on all - S_r and
    false on all - S_P (and S_P | S_r must cover every pair). Fits hold by construction; nothing is
    test-executed. Returns {query key: (guard tool, query value)}.
    """
    n = len(public)
    allset = frozenset(range(n))
    xs = [x for x, _ in public]
    recs = recs if recs is not None else recovery_candidates(public, tools, m)
    found = dict(known or {})
    shapes = GUARD_SHAPES.get(size, ())
    parts = [p for p in partials if len(p[0]) in {lp for lp, _ in shapes}]
    if order_partials:
        parts = sorted(parts, key=order_partials)
    rr = sorted(recs, key=order_recoveries) if order_recoveries else recs
    for chain, vec, _ in parts:
        SP = frozenset(i for i, v in enumerate(vec) if v == "match")
        for lp, rs in shapes:
            if len(chain) != lp:
                continue
            for r, Sr in rr:
                if _rsize(r) != rs or (SP | Sr) != allset:
                    continue
                must_true = sorted(allset - Sr)
                must_false = sorted(allset - SP)
                seps = predicates_for([xs[i] for i in must_true], [xs[i] for i in must_false],
                                      families=families, max_size=1, meter_=m, grammar_xs=xs)
                for c in seps:
                    q = _route_answer(chain, r, c, query, m)
                    if q is RAISED:
                        continue
                    k = vkey(q)
                    if k not in found:
                        found[k] = (guard_tool(c, chain, r), q)
                        if early and len(found) >= 2:
                            return found
    return found


def guard_level_naive(public, query, partials, size, tools, m, *, recs=None, known=None):
    """Arm-1 fixed generate-and-test: build every (P, c, r) of `size` and execute it on every public pair."""
    xs = [x for x, _ in public]
    recs = recs if recs is not None else recovery_candidates(public, tools, m)
    atoms = atom_candidates(xs)
    found = dict(known or {})
    for chain, vec, _ in partials:
        for lp, rs in GUARD_SHAPES.get(size, ()):
            if len(chain) != lp:
                continue
            for r, _ in recs:
                if _rsize(r) != rs:
                    continue
                for c in atoms:
                    g = guard_tool(c, chain, r)
                    ok = True
                    for x, y in public:
                        m.charge("repair_work_units", g.cost)
                        try:
                            if vkey(g(x)) != vkey(y):
                                ok = False
                                break
                        except Exception:
                            ok = False
                            break
                    if not ok:
                        continue
                    m.charge("verification_work_units", 1)
                    try:
                        q = g(query)
                    except Exception:
                        continue
                    found.setdefault(vkey(q), (g, q))
    return found


def solve_exact(public, query, tools, m, *, popper=True, order=None, early=False, naive=False,
                order_partials=None, order_recoveries=None, families=None, max_size=3):
    """Minimal-size certificate over plain chains (depth <= 3) and guards (size 2..3) - the shared space.

    Size s level = plain chains of length s plus guards of size s. UNIQUE iff exactly one query output at
    the first nonempty level (concrete witness kept); AMBIGUOUS iff two concrete programs disagree.
    """
    s = Searcher(public, query, tools, popper=popper, order=order, early_ambiguity=early, m=m)
    res = s.res
    recs = None
    try:
        for size in range(1, max_size + 1):
            found = {k: (p, q) for k, (p, q) in s.level().items()}
            if size >= 2 and res.partials and not (early and len(found) >= 2):
                if recs is None:
                    recs = recovery_candidates(public, tools, m)
                if naive:
                    gl = guard_level_naive(public, query, res.partials, size, tools, m, recs=recs)
                else:
                    gl = guard_level(public, query, res.partials, size, tools, m, recs=recs, early=early,
                                     known={k: None for k in found}, order_partials=order_partials,
                                     order_recoveries=order_recoveries, families=families)
                for k, v in gl.items():
                    if v is not None and k not in found:
                        found[k] = ((v[0],), v[1])
            if found:
                res.hypotheses = [(tuple(t.name for t in p), q, tuple(p)) for p, q in found.values()]
                res.size = size
                res.witness, res.answer = res.hypotheses[0][0], res.hypotheses[0][1]
                res.status = UNIQUE if len(found) == 1 else AMBIGUOUS
                break
    except WorkExhausted:
        res.status = EXHAUSTED
    res.work = m.total
    return res


# --------------------------------------------------------------------------- distinguishing tests
def _swap01(v):
    return type(v)([v[1], v[0]] + list(v[2:])) if len(v) >= 2 else v


TRANSFORMS = {
    # name: (applies-to, fn) -- generic structure-preserving perturbations
    "reverse": (lambda v: isinstance(v, (list, tuple)) and len(v) >= 2, lambda v: type(v)(reversed(v))),
    "rotate": (lambda v: isinstance(v, (list, tuple)) and len(v) >= 2, lambda v: type(v)(list(v[1:]) + [v[0]])),
    "swap01": (lambda v: isinstance(v, (list, tuple)) and len(v) >= 2, _swap01),
    "drop_last": (lambda v: isinstance(v, (list, tuple, str, bytes)) and len(v) >= 1, lambda v: v[:-1]),
    "dup_first": (lambda v: isinstance(v, (list, tuple)) and len(v) >= 1, lambda v: type(v)([v[0]] + list(v))),
    "str_reverse": (lambda v: isinstance(v, (str, bytes)) and len(v) >= 2, lambda v: v[::-1]),
}
PRESERVED = ("type", "len", "keys", "common_keys", "has_zero", "has_none")


def _multiset(v):
    try:
        return tuple(sorted(vkey(a) for a in v)) if isinstance(v, (list, tuple)) else None
    except Exception:
        return None


def candidate_probes(bases, hypotheses, query, *, families=None, two_step=True):
    """Probe inputs: generic transforms of public/query inputs plus 2-step a(x) probes."""
    qk = vkey(query)
    out = []
    fams = families or list(TRANSFORMS) + (["two_step"] if two_step else [])
    for fam in fams:
        if fam == "two_step":
            firsts = {p[0].name: p[0] for _, _, p in hypotheses if p}
            for b in bases:
                for a in firsts.values():
                    try:
                        x = a(b)
                    except Exception:
                        continue
                    out.append(("two_step", x, b))
            continue
        ok, fn = TRANSFORMS[fam]
        for b in bases:
            if ok(b):
                try:
                    out.append((fam, fn(b), b))
                except Exception:
                    pass
    seen, uniq = {qk}, []
    for fam, x, b in out:
        k = vkey(x)
        if k not in seen:
            seen.add(k)
            uniq.append((fam, x, b))
    return uniq


def preserved_score(x, base):
    fa, fb = phi(x), phi(base)
    s = sum(fa.get(k) == fb.get(k) for k in PRESERVED)
    return s + (1 if _multiset(x) is not None and _multiset(x) == _multiset(base) else 0)


def outputs_on(program, x):
    try:
        return vkey(run_chain(program, x))
    except Exception:
        return RAISED


# --------------------------------------------------------------------------- propose_refinement
@dataclass
class RefinementPlan:
    candidate_predicate: object = None    # Predicate (invented concept / guard condition)
    distinguishing_test: object = None    # (family, probe input) or None
    candidate_repair: object = None       # ("guard", Tool) | ("rebind", hypotheses) | None
    family: str = ""
    cost: int = 0
    alternatives: list = field(default_factory=list)


def invent_concept(public_xs, query, order=None):
    """A predicate shared by every public input but false on the query (the distinction they hide)."""
    best = []
    for p in atom_candidates(list(public_xs) + [query]):
        if all(p(x) for x in public_xs) and not p(query):
            best.append(p)
    if order:
        best.sort(key=order)
    return best


def propose_refinement(competing_hypotheses, observed_evidence, current_representation, goal, remaining_budget,
                       *, rank=None, m=None):
    """Executable refinement operator.

    goal == "disambiguate": hypotheses [(names, qval, program)] that agree on public data. Returns the
      invented splitting concept, the most preserving probe on which >= 2 hypotheses disagree (probe
      families ordered by `rank`), and a rebind repair to apply once the probe is observed.
    goal == "repair": evidence = partial-fit records; returns guard repairs ordered by `rank`.
    Every hypothesis execution and predicate evaluation is charged to `m`.
    """
    m = m or meter(max(1, remaining_budget))
    plan = RefinementPlan()
    public = observed_evidence["public"]
    query = observed_evidence["query"]
    xs = [x for x, _ in public]
    start = m.total
    if goal == "disambiguate":
        concepts = invent_concept(xs, query, order=(lambda p: rank("concept", p.family)) if rank else None)
        plan.candidate_predicate = concepts[0] if concepts else None
        fams = current_representation.get("probe_families")
        if rank and fams:
            fams = sorted(fams, key=lambda f: rank("probe", f))
        probes = candidate_probes(xs + [query], competing_hypotheses, query, families=fams)
        scored = []
        for i, (fam, x, base) in enumerate(probes):
            outs = set()
            for _, _, prog in competing_hypotheses:
                m.charge("probe_design_work_units", len(prog))
                outs.add(outputs_on(prog, x))
            if len(outs) >= 2:
                flips = int(bool(concepts) and concepts[0](base) != concepts[0](x))
                key = (rank("probe", fam) if rank else 0, -flips, -preserved_score(x, base), i)
                scored.append((key, fam, x))
                if rank:
                    break       # learned ordering: take the first disagreeing probe of the best family
        if scored:
            scored.sort(key=lambda r: r[0])
            plan.distinguishing_test = (scored[0][1], scored[0][2])
            plan.family = scored[0][1]
            plan.alternatives = [(f, x) for _, f, x in scored[1:4]]
        plan.candidate_repair = ("rebind", competing_hypotheses)
    elif goal == "repair":
        repairs = guard_repairs(observed_evidence, current_representation, rank=rank, m=m,
                                limit=current_representation.get("limit"))
        if repairs:
            plan.candidate_repair = ("guard", repairs[0][0])
            plan.candidate_predicate = repairs[0][1]
            plan.family = repairs[0][1].family
            plan.alternatives = repairs[1:]
    plan.cost = m.total - start
    return plan


def recoveries_for(fail_xs, fail_ys, tools, m):
    out = []
    ys = {vkey(y) for y in fail_ys}
    if len(ys) == 1:
        out.append(("const", fail_ys[0]))
    if all(vkey(x) == vkey(y) for x, y in zip(fail_xs, fail_ys)):
        out.append(("id", None))
    for t in tools:
        m.charge("repair_work_units", len(fail_xs))
        try:
            if all(vkey(t(x)) == vkey(y) for x, y in zip(fail_xs, fail_ys)):
                out.append(("tool", t))
        except Exception:
            pass
    return out


def guard_repairs(evidence, rep, *, rank=None, m, limit=None):
    """Procedure A candidates: guard(c, P, r) built from partial fits; every guard fits all public pairs."""
    public, partials, tools = evidence["public"], evidence["partials"], rep["tools"]
    xs = [x for x, _ in public]
    ys = [y for _, y in public]
    fams = rep.get("predicate_families")
    if rank and fams:
        fams = sorted(fams, key=lambda f: rank("predicate", f))
    out = []
    parts = list(partials)
    if rank:
        parts.sort(key=lambda p: rank("partial", "raise" if "raise" in p[1] else "miss"))
    for chain, vec, _ in parts:
        S = [i for i, v in enumerate(vec) if v == "match"]
        F = [i for i, v in enumerate(vec) if v != "match"]
        if len(S) < 1 or not F:
            continue
        recs = recoveries_for([xs[i] for i in F], [ys[i] for i in F], tools, m)
        if not recs:
            continue
        preds = predicates_for([xs[i] for i in S], [xs[i] for i in F], families=fams, meter_=m,
                               limit=None)
        for p in preds:
            for r in recs:
                g = guard_tool(p, chain, r)
                m.charge("repair_work_units", len(xs))
                try:
                    if all(vkey(g(x)) == vkey(y) for x, y in public):
                        out.append((g, p, chain, r))
                except Exception:
                    continue
        if limit and len(out) >= limit:
            break
    out.sort(key=lambda r: program_size((r[0],)))
    return out


# --------------------------------------------------------------------------- algebraic roles (Procedure C)
def algebraic_signature(tool, probes, m):
    """Refined role: involution / idempotent / order-dependent, from 2-step and permutation probes."""
    inv = idem = None
    order_dep = False
    for x in probes:
        m.charge("binding_probe_work_units", 2)
        try:
            y = tool(x)
            yy = tool(y)
        except Exception:
            continue
        inv = (inv is not False) and vkey(yy) == vkey(x)
        idem = (idem is not False) and vkey(yy) == vkey(y)
        if isinstance(x, (list, tuple)) and len(x) >= 2:
            m.charge("binding_probe_work_units", 1)
            try:
                if vkey(tool(type(x)(reversed(x)))) != vkey(y):
                    order_dep = True
            except Exception:
                pass
    return (bool(inv), bool(idem), order_dep)
