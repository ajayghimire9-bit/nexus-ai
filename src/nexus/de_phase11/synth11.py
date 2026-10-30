"""Phase 11 typed synthesizer (NOT LOCKED): bounded program search over core11 with recoverable observational fingerprints.

INPUT (the learner's view of a task): input relations and expected outputs on the VISIBLE batches, the output schema, and a budgeted
evidence interface (one extra example batch with its expected output, released on request). Never: reference programs, generator
paths, family labels or hidden batches.

SEARCH (identical machinery in every arm; the arms differ only in production COSTS and in whether library calls are offered)
  relational  best-first enumeration in cost order from the input relations. Unary steps: filter_rows(B, p) with p from a predicate
              pool (is_null / not is_null of a column; = / <> against each value of a low-cardinality column; < <= > >= against mined
              numeric constants); rank_window(B, (k,), ((col o, desc),), 1) (k must have a duplicate in some visible batch: otherwise
              the step is an exact no-op and is skipped - sound); fold_group(B, (k,), ((m, agg, col c),)) with one measure. Binary
              steps with every relation already popped: join_rel(kind, B, A, (kb,), (ka,)) (identical key types; key pairs sharing no
              visible value are skipped - declared heuristic) and union_rel(B, A) (same schema). Library relational functions: the
              popped relation fills the first relation parameter; other parameters range over popped relations, column names and mined
              literals (type-checked before execution; capped). Every child runs on the visible batches; a child whose visible result
              (column names + the bag of every batch) equals an earlier one joins that earlier CLASS as a retained alternative.
  final step  on every popped relation B: PROJECTION (|B| = |output| per batch; output columns whose bags equal a B column's are
              passthroughs and align the rows; every other output column needs a scalar expression over B equal on the aligned rows -
              multiset-equal inside each alignment group) and AGGREGATION (output columns whose values are exactly the distinct values of
              a B column are group keys (1 or 2); every other output column needs agg(e) per group, agg in count_star sum count min max).
  scalar pool bottom-up in bands of cumulative production cost; scalar expanded size <= SC_SIZE in EVERY arm (bands only order the
              search). OE CLASSES are keyed by type + the full encoded values (NULL / ERR / type distinguished; multiplicity and row
              order kept) on a MICRO-SLICE = the first SLICE rows of the context. A class keeps every structurally distinct member
              (operator over CHILD CLASS ids, cap ALT_CAP), so alternatives are REGENERABLE: matching tests the representative on the
              FULL rows and, when it fails, the other realisations of the class (REFINEMENT; every full check charged). Overflowing a
              cap is logged as completeness loss.
  submission  a final program must reproduce the expected bag exactly on both visible batches; then the shared evidence policy requests
              the evidence batch ONCE (every arm, B_ev = 1) and the program must reproduce it too. On an evidence counterexample the
              solver first tries the other visible-passing realisations of the matched classes and the retained alternatives of B's
              relational class (refinement), then continues the search; every later candidate is checked on the evidence batch as well.
              Hidden batches never reach the search.
LIMITS (published, identical in every arm): expanded program size <= SIZE_LIMIT, scalar size <= SC_SIZE, relational children <= REL_CAP,
scalar micro-evaluations <= SC_CAP, wall <= WALL_S (a safety cap; a search ended by it is logged wall_bound)."""
from __future__ import annotations

import heapq
import itertools
import json
import time
from collections import Counter

from nexus.de_phase11 import core11 as C

SIZE_LIMIT, SC_SIZE, SLICE, ALT_CAP, REAL_CAP, PASS_ALTS = 40, 8, 10, 48, 400, 6
POOL_CAP, REFINE_CAP, DEDUCE_ARM_SIZE, DEDUCE_FREE, JOIN_OVERLAP = 25000, 300, 3, 3, 0.2
TIER_CAPS, ESC_STEP = (1500, 6000, 15000, POOL_CAP), 2                    # scalar-pool micro caps per escalation tier; tier cost step
REL_CAP, SC_CAP, WALL_S = 4000, 400000, 3.0
VIS = ("vis_a", "vis_b")
MAX_COST = 4


class Budget:
    def __init__(self, rel_cap=REL_CAP, sc_cap=SC_CAP, wall=WALL_S):
        self.rel_cap, self.sc_cap, self.wall = rel_cap, sc_cap, wall
        self.t0 = time.time()
        self.c = Counter()
        self._n, self._timed_out = 0, False

    def out(self):
        if self.c["rel_evals"] >= self.rel_cap or self.c["micro_evals"] >= self.sc_cap or self._timed_out:
            return True
        self._n += 1
        if self._n & 511 == 0 and time.time() - self.t0 > self.wall:      # the clock is read every 512 checks
            self._timed_out = True
        return self._timed_out

    def wall_bound(self):
        return time.time() - self.t0 > self.wall


class Costs:
    """Production costs. Fixed search: every production costs 1. Learned guide: guide11 table (1..MAX_COST)."""

    def __init__(self, table=None):
        self.t = dict(table or {})

    def __call__(self, prod):
        return self.t.get(prod, self.t.get("__default__", 1)) if self.t else 1


# ------------------------------------------------------------------ scalar pool with recoverable classes
def _subs(name):
    if name == "cmp":
        return [f"cmp:{o}" for o in C.CMP_OPS]
    if name == "arith":
        return [f"arith:{o}" for o in C.ARITH_OPS]
    if name == "cast":
        return [f"cast:{t}" for t in (C.INT, C.NUM, C.STR)]
    return [name]


def _splits(total, k):
    if k == 1:
        return [(total,)] if total >= 1 else []
    return [(a,) + r for a in range(1, total - k + 2) for r in _splits(total - a, k - 1)]


def _diag(total, lens):
    """Index tuples with the given sum, each index < its length."""
    if len(lens) == 1:
        if total < lens[0]:
            yield (total,)
        return
    for a in range(min(total, lens[0] - 1) + 1):
        for rest in _diag(total - a, lens[1:]):
            yield (a,) + rest


def _fill(tmpl, kids):
    it = iter(kids)
    return tuple(next(it) if x is None else x for x in tmpl)


# children of a compound production may have expanded SIZE <= CHILD_SIZE[op] (published enumeration shape, identical in every arm;
# bands = cumulative production cost only ORDER the enumeration)
CHILD_SIZE = dict(isnull=3, **{"not": 4}, cast=3, json=2, cmp=2, arith=2, branch=3, call=3, **{"and": 3, "or": 3})
BRANCH_ARM_SIZE = 1          # pool branches take LEAF arms (columns, 0 / 1, output-mined constants; not threshold quantiles); larger
                             # arms are reached by deductive branch unification at match time (projection targets)


class Pool:
    """Typed bottom-up scalar enumeration over one relation context (columns + rows). Slice values are computed compositionally from
    the child classes' value vectors with core11's value-level operators (identical semantics to the interpreter)."""

    def __init__(self, cols, types, rows, consts, paths, lib, costs, budget, log):
        self.cols, self.types, self.rows, self.slice = tuple(cols), tuple(types), rows, rows[:SLICE]
        self.consts, self.paths, self.lib, self.costs, self.budget, self.log = consts, paths, lib, costs, budget, log
        self.classes, self.index, self.by_band, self.band = [], {}, {}, 0
        self.sch = dict(zip(self.cols, self.types))
        self.typed = {}                                    # (type, band) -> [ids]
        self.micro, self.cap, self.capped = 0, TIER_CAPS[0], False
        self._rcache = {}
        self.qconsts = {(t, v) for t, vs in getattr(consts, "quantile", {}).items() for v in vs}

    def realize(self, cid, cap=REAL_CAP, depth=0):
        """Concrete ASTs of class cid, representative first. Members are interleaved round-robin; inside a compound member the child
        realisation indices are enumerated DIAGONALLY (increasing index sum), so every child's alternatives are reconsidered evenly
        within the cap (lexicographic enumeration would only ever vary the last child)."""
        key = (cid, cap, depth)
        if key in self._rcache:
            return self._rcache[key]
        members = self.classes[cid]["members"]
        gens = [self._member(node, cap, depth) for node in members]
        out, seen = [], set()
        while gens and len(out) < cap:
            nxt = []
            for g in gens:
                e = next(g, None)
                if e is None:
                    continue
                nxt.append(g)
                if e not in seen:
                    seen.add(e)
                    out.append(e)
                    if len(out) >= cap:
                        break
            gens = nxt
        self._rcache[key] = out
        return out

    def _member(self, node, cap, depth):
        if node[0] == "leaf":
            yield node[1]
            return
        tmpl, kids = node
        if depth >= 2:                                              # beyond depth 2 only representatives (bounded cost)
            yield _fill(tmpl, [self.rep(k) for k in kids])
            return
        lists = [self.realize(k, max(1, cap // 2), depth + 1) for k in kids]
        top = sum(len(x) - 1 for x in lists)
        for total in range(top + 1):
            for idx in _diag(total, [len(x) for x in lists]):
                yield _fill(tmpl, [lst[i] for lst, i in zip(lists, idx)])

    def rep(self, cid):
        return self.classes[cid]["rep"]

    def _new(self, ast, t, vec, node, band, size):
        if size > SC_SIZE:
            return
        self.budget.c["micro_evals"] += 1
        self.micro += 1
        self._rcache = {}
        key = (t, tuple(C.enc(v) for v in vec))
        cid = self.index.get(key)
        if cid is None:
            self.index[key] = len(self.classes)
            self.classes.append(dict(type=t, vec=vec, ek=key[1], members=[node], rep=ast, band=band, size=size))
            self.by_band.setdefault(band, []).append(len(self.classes) - 1)
            self.typed.setdefault((t, band), []).append(len(self.classes) - 1)
        elif len(self.classes[cid]["members"]) < ALT_CAP:
            self.classes[cid]["members"].append(node)
            self.log["suppressed_alternatives"] += 1
        else:
            self.log["completeness_loss_alt_cap"] += 1

    def _q(self, c):
        r = self.classes[c]["rep"]
        return r[0] == "const" and (r[2], r[1]) in self.qconsts and len(self.classes[c]["members"]) == 1

    def ids_upto(self, t=None):
        return [i for b in range(1, self.band + 1) for i in self.by_band.get(b, []) if t is None or self.classes[i]["type"] == t]

    def _ids(self, band, t=None):
        if t is None:
            return self.by_band.get(band, [])
        return self.typed.get((t, band), [])

    def grow(self):
        """Enumerate the next band. False when no expression within SC_SIZE can remain, or the budget is out."""
        if self.band >= SC_SIZE * MAX_COST or self.budget.out() or self.micro >= self.cap:
            if self.micro >= self.cap:
                self.capped = True
                if self.cap >= POOL_CAP:
                    self.log["completeness_loss_pool_cap"] += 1
            return False
        self.band += 1
        b, K, cl = self.band, self.costs, self.classes
        if K("col") == b:
            for c, t in zip(self.cols, self.types):
                self._new(("col", c), t, tuple(r[self.cols.index(c)] for r in self.slice), ("leaf", ("col", c)), b, 1)
        if K("const") == b:
            for t, vs in self.consts.items():
                for v in vs:
                    self._new(("const", v, t), t, (v,) * len(self.slice), ("leaf", ("const", v, t)), b, 1)
        sz = lambda c, op: cl[c]["size"] <= CHILD_SIZE[op]                         # noqa: E731
        # unary
        for sub, op in [("isnull", "isnull"), ("not", "not"), ("json", "json")] + [(f"cast:{t}", "cast") for t in (C.INT, C.NUM, C.STR)]:
            cb = b - K(sub)
            if cb < 1:
                continue
            for c in self._ids(cb):
                if self.budget.out():
                    return False
                x = cl[c]
                if x["rep"][0] == "const" or not sz(c, op):
                    continue
                if op == "isnull":
                    self._new(("isnull", x["rep"]), C.BOOL, tuple(C.v_isnull(v) for v in x["vec"]), (("isnull", None), [c]), b, 1 + x["size"])
                elif op == "not" and x["type"] == C.BOOL:
                    self._new(("not", x["rep"]), C.BOOL, tuple(C.v_not(v) for v in x["vec"]), (("not", None), [c]), b, 1 + x["size"])
                elif op == "json" and x["type"] == C.STR:
                    for pth in self.paths:
                        self._new(("json", x["rep"], pth), C.STR, tuple(C.v_json(v, pth) for v in x["vec"]), (("json", None, pth), [c]), b, 1 + x["size"] + len(pth))
                elif op == "cast":
                    tg = sub.split(":")[1]
                    if (x["type"], tg) in C.CASTS:
                        self._new(("cast", x["rep"], tg), tg, tuple(C.v_cast(v, tg) for v in x["vec"]), (("cast", None, tg), [c]), b, 1 + x["size"])
        # binary
        for o in C.CMP_OPS + tuple(f"a{o}" for o in C.ARITH_OPS) + ("and", "or"):
            if o.startswith("a") and o[1:] in C.ARITH_OPS:
                sub, op, ao = f"arith:{o[1:]}", "arith", o[1:]
            elif o in ("and", "or"):
                sub, op, ao = o, o, None
            else:
                sub, op, ao = f"cmp:{o}", "cmp", o
            rest = b - K(sub)
            for b1, b2 in _splits(rest, 2) if rest >= 2 else []:
                for c1 in self._ids(b1):
                    x1 = cl[c1]
                    if not sz(c1, op):
                        continue
                    if op in ("and", "or") and x1["type"] != C.BOOL:
                        continue
                    if op == "arith" and not C.num_like(x1["type"]):
                        continue
                    for c2 in self._ids(b2):
                        if self.budget.out():
                            return False
                        x2 = cl[c2]
                        if not sz(c2, op):
                            continue
                        t1, t2 = x1["type"], x2["type"]
                        if x1["rep"][0] == "const" and x2["rep"][0] == "const":
                            continue
                        if op == "cmp":
                            if not (t1 == t2 or (C.num_like(t1) and C.num_like(t2))) or (t1 == C.BOOL and ao not in ("eq", "ne")):
                                continue
                            vec = tuple(C.v_cmp(ao, u, v) for u, v in zip(x1["vec"], x2["vec"]))
                            self._new(("cmp", ao, x1["rep"], x2["rep"]), C.BOOL, vec, (("cmp", ao, None, None), [c1, c2]), b, 1 + x1["size"] + x2["size"])
                        elif op == "arith":
                            if not C.num_like(t2) or (ao == "mod" and (t1 != C.INT or t2 != C.INT)):
                                continue
                            rt = C.NUM if ao == "div" else (C.INT if t1 == t2 == C.INT else C.NUM)
                            vec = tuple(C.v_arith(ao, u, v) for u, v in zip(x1["vec"], x2["vec"]))
                            self._new(("arith", ao, x1["rep"], x2["rep"]), rt, vec, (("arith", ao, None, None), [c1, c2]), b, 1 + x1["size"] + x2["size"])
                        else:
                            if t2 != C.BOOL or c1 >= c2:
                                continue
                            f = C.v_and if op == "and" else C.v_or
                            vec = tuple(f(u, v) for u, v in zip(x1["vec"], x2["vec"]))
                            self._new((op, x1["rep"], x2["rep"]), C.BOOL, vec, ((op, None, None), [c1, c2]), b, 1 + x1["size"] + x2["size"])
        # branch: condition of size <= CHILD_SIZE["branch"], arms of one type of size <= BRANCH_ARM_SIZE
        rest = b - K("branch")
        for b0, b1, b2 in _splits(rest, 3) if rest >= 3 else []:
            conds = [c for c in self._ids(b0, C.BOOL) if cl[c]["rep"][0] != "const" and sz(c, "branch")]
            for t in C.TYPES:
                A1 = [c for c in self._ids(b1, t) if cl[c]["size"] <= BRANCH_ARM_SIZE and not self._q(c)]
                A2 = [c for c in self._ids(b2, t) if cl[c]["size"] <= BRANCH_ARM_SIZE and not self._q(c)]
                if not A1 or not A2:
                    continue
                for c0 in conds:
                    x0 = cl[c0]
                    for c1 in A1:
                        for c2 in A2:
                            if self.budget.out():
                                return False
                            if c1 == c2:
                                continue
                            x1, x2 = cl[c1], cl[c2]
                            vec = tuple(C.v_branch(u, v, w) for u, v, w in zip(x0["vec"], x1["vec"], x2["vec"]))
                            self._new(("branch", x0["rep"], x1["rep"], x2["rep"]), t, vec, (("branch", None, None, None), [c0, c1, c2]), b,
                                      1 + x0["size"] + x1["size"] + x2["size"])
        # library scalar functions: arguments of size <= CHILD_SIZE["call"]
        for fname, f in sorted(self.lib.items()):
            if f["kind"] != "scalar":
                continue
            rest, ar = b - K(f"call:{fname}"), len(f["params"])
            for split in _splits(rest, ar) if rest >= ar else []:
                slots = []
                for (pk, pm), s_ in zip(f["params"], split):
                    if pk == "lit" and pm == "path":
                        slots.append([("path", p) for p in self.paths] if s_ == 1 else [])
                    else:
                        slots.append([("cls", c) for c in self._ids(s_) if sz(c, "call")])
                for combo in itertools.product(*slots):
                    if self.budget.out():
                        return False
                    args = []
                    for (pk, pm), (tag, val) in zip(f["params"], combo):
                        if tag == "path":
                            args.append(val)
                            continue
                        r = self.rep(val)
                        if pk == "name":
                            if r[0] != "col":
                                break
                            args.append(r[1])
                        elif pk == "lit":
                            if r[0] != "const" or r[2] != pm:
                                break
                            args.append(r[1])
                        else:
                            args.append(r)
                    else:
                        try:
                            ast = C.expand(("call", fname, tuple(args)), self.lib)
                            t = C.scalar_type(ast, self.sch)
                            fn = C.compile_scalar(ast, self.cols)
                            vec = tuple(fn(r) for r in self.slice)
                        except (KeyError, IndexError, TypeError, C.TypeErr, C.Unsupported):
                            continue
                        self._new(ast, t, vec, ("leaf", ast), b, C.size(ast))
        return True


# ------------------------------------------------------------------ constants from permitted observations
def quantiles(vals):
    v = sorted(set(x for x in vals if x is not None))
    if not v:
        return []
    return sorted({v[round(q * (len(v) - 1))] for q in (0, 0.25, 0.5, 0.75, 1)})


def mine(vis_envs, expected):
    """Constants from PERMITTED observations: 0 and 1; every value of a low-cardinality (<= 6 distinct) string column; the QUANTILE
    constants (min, quartiles, max) of every numeric input column over both visible batches (also kept per column for filter
    predicates); small value sets (<= 4 distinct) of output columns; object keys of JSON text in string columns (paths)."""
    consts = {C.INT: {0, 1}, C.NUM: set(), C.STR: set(), C.BOOL: set()}
    paths, colq, colvals = set(), {}, {}
    for env in vis_envs.values():
        for rn, R in env.items():
            for j, (c, t) in enumerate(zip(R.cols, R.types)):
                colvals.setdefault((rn, c, t), []).extend(r[j] for r in R.rows)
    for (rn, c, t), vals in colvals.items():
        nn = [v for v in vals if v is not None]
        cnt = Counter(nn)
        if t == C.STR and len(cnt) <= 6:
            consts[C.STR] |= set(cnt)
        if t == C.STR:
            for v in nn[:20]:
                try:
                    o = json.loads(v)
                except (ValueError, TypeError):
                    continue
                if isinstance(o, dict):
                    paths |= {(k,) for k in o}
        if C.num_like(t):
            colq[c] = quantiles(nn)
    base_c = {t: set(v) for t, v in consts.items()}
    for R in expected.values():
        for j, t in enumerate(R.types):
            vals = {r[j] for r in R.rows if r[j] is not None}
            if t in (C.STR, C.INT) and len(vals) <= 4:
                consts[t] |= vals
                base_c.setdefault(t, set()).update(vals)
    for c, q in colq.items():
        for v in q:
            consts[C.INT if isinstance(v, int) else C.NUM].add(v)
    out = _Consts({t: sorted(v, key=repr) for t, v in consts.items() if v})
    out.quantile = {t: sorted({v for q in colq.values() for v in q if isinstance(v, int) == (t == C.INT)} - (base_c.get(t, set()))) for t in (C.INT, C.NUM)}
    return out, sorted(paths)[:6], colq


class _Consts(dict):
    """The mined constants (dict type -> values) + .quantile: the constants that come ONLY from numeric quantiles (thresholds)."""
    quantile = {}


AGG_FN = {"sum": lambda v: (lambda nn: None if not nn else (sum(nn) if all(isinstance(z, int) for z in nn) else float(sum(float(z) for z in nn))))([z for z in v if z is not None]),
          "count": lambda v: sum(1 for z in v if z is not None),
          "min": lambda v: (lambda nn: min(nn) if nn else None)([z for z in v if z is not None]),
          "max": lambda v: (lambda nn: max(nn) if nn else None)([z for z in v if z is not None])}


class Search:
    def __init__(self, task, lib, costs, budget, evidence=None):
        self.task, self.lib, self.costs, self.b = task, dict(lib or {}), costs, budget
        self.log = Counter()
        self.envs = {k: task["inputs"][k] for k in VIS}
        self.exp = {k: task["expected"][k] for k in VIS}
        self.out_schema = tuple(task["out_schema"])
        self.outn = [n for n, _ in self.out_schema]
        self.outt = [t for _, t in self.out_schema]
        self.evidence, self.ev = evidence, None
        self.consts, self.paths, self.colq = mine(self.envs, self.exp)
        self.pools = {}

    def _exec(self, x):
        try:
            return [C.run(x, self.envs[k]) for k in VIS]
        except C.RelErr:
            return None
        except (TypeError, C.TypeErr, C.Unsupported):              # defensive: an ill-typed candidate is invalid, never a crash
            self.log["runtime_type_error"] += 1
            return None

    @staticmethod
    def _fp(vals):
        return (vals[0].cols,) + tuple(frozenset(R.bag().items()) for R in vals)

    # ---------------------------------------------------------- relational enumeration
    def run(self):
        """ONE best-first cost order over three kinds of heap item (identical in every arm):
          relational child  pushed UNEVALUATED with its cost and expanded size; executed when popped (one relational evaluation); a
                            result equal to an earlier class (column names + visible bags) joins it as a retained alternative
          pair token        the binary children (join / union) of two popped relations, costed by a lower bound and generated lazily
          escalation        re-runs a popped relation's final step with the next pool cap TIER_CAPS[t] (pools keep their state);
                            cost = the relation's cost + ESC_STEP * t, so scalar deepening competes with relational expansion"""
        self.es = {k: v.schema() for k, v in self.envs[VIS[0]].items()}
        heap, tick, classes, self.popped, seen = [], itertools.count(), {}, [], set()
        self.parked = []
        for name in sorted(self.es):
            heapq.heappush(heap, (self.costs("rel"), next(tick), ("rel", name), ("rel", name), 1))
            seen.add(("rel", name))
        while heap and not self.b.out():
            cost, _, prog, x, sz = heapq.heappop(heap)
            if prog == "__pair__":                                    # lazy binary children of (popped[x[0]], popped[x[1]])
                bi, j = x
                if j < len(self.popped):
                    if j != bi:
                        for child, cx, cc, csz in self.binary(self.popped[bi], self.popped[j]):
                            if csz <= SIZE_LIMIT and cx not in seen:
                                seen.add(cx)
                                heapq.heappush(heap, (cc, next(tick), child, cx, csz))
                    self._push_pair(heap, tick, bi, j + 1)
                continue
            if prog == "__esc__":                                     # scalar deepening of a popped relation's final step
                ni, t = x
                node = self.popped[ni]
                self.log[f"escalated_tier{t}"] += 1
                sol = self._final_node(node, t)
                if sol is not None:
                    return sol
                if node["capped"] and t + 1 < len(TIER_CAPS):
                    heapq.heappush(heap, (node["cost"] + ESC_STEP * (t + 1), next(tick), "__esc__", (ni, t + 1), 0))
                continue
            try:
                C.rel_schema(x, self.es)
            except (C.TypeErr, C.Unsupported, KeyError, ValueError, IndexError):
                continue
            self.b.c["rel_evals"] += 1
            vals = self._exec(x)
            if vals is None:
                continue
            fp = self._fp(vals)
            if fp in classes:
                if len(classes[fp]) < ALT_CAP:
                    classes[fp].append(prog)
                    self.log["rel_suppressed_alternatives"] += 1
                else:
                    self.log["completeness_loss_rel_alt_cap"] += 1
                continue
            classes[fp] = [prog]
            node = dict(prog=prog, x=x, vals=vals, cost=cost, size=sz, alts=classes[fp], capped=False,
                        sets=[[{v for v in (row[i] for row in R.rows) if v is not None} for i in range(len(R.cols))] for R in vals],
                        dup=[any(len({C.enc(row[i]) for row in R.rows}) < len(R.rows) for R in vals) for i in range(len(vals[0].cols))])
            self.popped.append(node)
            for bi, j in [t for t in self.parked if t[1] == len(self.popped) - 1]:
                self.parked.remove((bi, j))
                self._push_pair(heap, tick, bi, j)
            self._push_pair(heap, tick, len(self.popped) - 1, 0)
            sol = self._final_node(node, 0)
            if sol is not None:
                return sol
            if node["capped"]:
                heapq.heappush(heap, (cost + ESC_STEP, next(tick), "__esc__", (len(self.popped) - 1, 1), 0))
            for child, cx, cc, csz in self.children(node):
                if csz > SIZE_LIMIT or cx in seen:
                    continue
                seen.add(cx)
                heapq.heappush(heap, (cc, next(tick), child, cx, csz))
        return None

    def _push_pair(self, heap, tick, bi, j):
        """Token for the binary children of popped[bi] with popped[j], costed by a lower bound; parked until popped[j] exists."""
        if j >= len(self.popped):
            self.parked.append((bi, j))
            return
        lb = self.popped[bi]["cost"] + self.popped[j]["cost"] + min(self.costs("union"), min(self.costs(f"join:{k}") for k in C.JOIN_KINDS) + 2)
        heapq.heappush(heap, (lb, next(tick), "__pair__", (bi, j), 0))

    def binary(self, node, n2):
        """join_rel (both orders; inner once) on key pairs of identical type sharing >= JOIN_OVERLAP of the smaller distinct-value set
        on some visible batch (declared heuristic), and union_rel on identical schemas."""
        K, out = self.costs, []
        prog, x, vals, cost, sz = node["prog"], node["x"], node["vals"], node["cost"], node["size"]
        p2, x2, v2, c2 = n2["prog"], n2["x"], n2["vals"], n2["cost"]
        R0, Rb = vals[0], v2[0]
        for i, a in enumerate(R0.cols):
            for j, bcol in enumerate(Rb.cols):
                if R0.types[i] != Rb.types[j] or R0.types[i] == C.BOOL:
                    continue
                if not any(len(node["sets"][q][i] & n2["sets"][q][j]) >= JOIN_OVERLAP * max(1, min(len(node["sets"][q][i]), len(n2["sets"][q][j])))
                           for q in range(len(vals))):
                    continue
                for kind in C.JOIN_KINDS:
                    jc, js = cost + c2 + K(f"join:{kind}") + 2, sz + n2["size"] + 3
                    out.append((("join", kind, prog, p2, (a,), (bcol,)), ("join", kind, x, x2, (a,), (bcol,)), jc, js))
                    if kind != "inner":
                        out.append((("join", kind, p2, prog, (bcol,), (a,)), ("join", kind, x2, x, (bcol,), (a,)), jc, js))
        if dict(R0.schema()) == dict(Rb.schema()) and len(R0.cols) == len(Rb.cols):
            out.append((("union", prog, p2), ("union", x, x2), cost + c2 + K("union"), sz + n2["size"] + 1))
        return out

    def _final_node(self, node, tier):
        self.cap = TIER_CAPS[tier]
        for k, p in self.pools.items():
            if k[1] == node["x"]:
                p.cap = TIER_CAPS[tier]
        sol = self.final(node["prog"], node["x"], node["vals"], node["alts"])
        node["capped"] = sol is None and any(p.capped for k, p in self.pools.items() if k[1] == node["x"])
        for p in self.pools.values():
            p.capped = False
        return sol

    def children(self, node):
        K, out = self.costs, []
        prog, x, vals, cost, sz = node["prog"], node["x"], node["vals"], node["cost"], node["size"]
        R0 = vals[0]
        cols, types = R0.cols, R0.types
        allrows = [r for R in vals for r in R.rows]
        for p, pc in self.preds(cols, types, allrows):
            out.append((("filter", prog, p), ("filter", x, p), cost + K("filter") + pc, sz + 1 + C.size(p)))
        for i, k in enumerate(cols):
            if not node["dup"][i]:
                continue                                              # rank on a duplicate-free key is an exact no-op (sound)
            for j, o in enumerate(cols):
                if j == i or types[j] == C.BOOL:
                    continue
                for desc in (True, False):
                    oe = ((("col", o), desc),)
                    out.append((("rank", prog, (k,), oe, 1), ("rank", x, (k,), oe, 1), cost + K("rank") + 2, sz + 3))
        for i, k in enumerate(cols):
            if not node["dup"][i] or k == "m":
                continue                                              # declared heuristic: no fold on a duplicate-free key
            meas = [("count_star", None)] + [(a, c) for c, t in zip(cols, types) if c != k for a in (("sum", "min", "max") if C.num_like(t) else ("min", "max"))]
            for agg, c in meas:
                m = (("m", agg, ("col", c) if c else None),)
                out.append((("fold", prog, (k,), m), ("fold", x, (k,), m), cost + K(f"fold:{agg}") + (2 if c else 1), sz + 3 + (1 if c else 0)))
        for fname, f in sorted(self.lib.items()):
            if f["kind"] != "rel":
                continue
            for args in self.rel_args(f, prog, x, vals, [(n["prog"], n["x"], n["vals"], n["cost"]) for n in self.popped]):
                try:
                    cx = C.expand(("call", fname, tuple(a[1] for a in args)), self.lib)
                except (KeyError, IndexError):
                    continue
                out.append((("call", fname, tuple(a[0] for a in args)), cx, cost + K(f"call:{fname}") + sum(a[2] for a in args), C.size(cx)))
        out.sort(key=lambda z: z[2])
        return out

    def rel_args(self, f, prog, x, vals, popped):
        rel_ps = [i for i, (k, _) in enumerate(f["params"]) if k == "rel"]
        if not rel_ps:
            return []
        names = sorted({c for _, _, v, _ in popped for c in v[0].cols} | set(vals[0].cols))
        choices = []
        for i, (k, t) in enumerate(f["params"]):
            if k == "rel":
                choices.append([(prog, x, 0)] if i == rel_ps[0] else [(p, xx, c) for p, xx, _, c in popped])
            elif k == "name":
                choices.append([(n, n, 1) for n in names])
            elif k == "lit":                                       # literals of the parameter's declared type (paths for a json path)
                choices.append([(p, p, 1) for p in self.paths] if t == "path" else [(v, v, 1) for v in self.consts.get(t, [])])
            else:
                choices.append([(("col", n), ("col", n), 1) for n in names])
        out = []
        for combo in itertools.product(*choices):
            out.append(combo)
            if len(out) >= 400:
                self.log["rel_call_args_capped"] += 1
                break
        return out

    def preds(self, cols, types, rows):
        out = []
        for i, (c, t) in enumerate(zip(cols, types)):
            vals = [r[i] for r in rows if r[i] is not None]
            if len(vals) < len(rows):
                out.append((("isnull", ("col", c)), 2))
                out.append((("not", ("isnull", ("col", c))), 3))
            cnt = Counter(vals)
            if t in (C.STR, C.BOOL) and len(cnt) <= 6:
                for v in sorted(cnt, key=repr):
                    out.append((("cmp", "eq", ("col", c), ("const", v, t)), 3))
                    out.append((("cmp", "ne", ("col", c), ("const", v, t)), 3))
            if C.num_like(t):
                for v in sorted(set(self.colq.get(c, [])) | {0}, key=repr):
                    for o in ("lt", "le", "gt", "ge"):
                        out.append((("cmp", o, ("col", c), ("const", v, C.INT if isinstance(v, int) else C.NUM)), 3))
        return out

    # ---------------------------------------------------------- final step
    def final(self, prog, x, vals, alts):
        for gen in (self.solve_projection, self.solve_aggregation):
            for finals in gen(prog, x, vals):
                for fp in finals:
                    st = self._accept(fp)
                    if st == "ok":
                        return fp
                    if st == "evidence_fail":                    # refinement over the relational class
                        for alt in alts[1:]:
                            st2 = self._accept(_swap_base(fp, prog, alt))
                            if st2 == "ok":
                                self.log["refinement_recovered_rel"] += 1
                                return _swap_base(fp, prog, alt)
                if self.b.out():
                    return None
        return None

    def _check(self, xf, env, exp):
        try:
            got = C.run(xf, env)
        except C.RelErr:
            return False
        if set(got.cols) != set(self.outn) or len(got.cols) != len(self.outn):
            return False
        return C.same_bag(C.project_like(got, self.outn), exp)

    def _accept(self, prog_final):
        try:
            xf = C.expand(prog_final, self.lib)
            C.rel_schema(xf, self.es)
        except (C.TypeErr, C.Unsupported, KeyError, IndexError, ValueError):
            return "invalid"
        if C.size(xf) > SIZE_LIMIT:
            return "too_large"
        self.b.c["full_checks"] += 1
        if not all(self._check(xf, self.envs[k], self.exp[k]) for k in VIS):
            return "visible_fail"
        if self.evidence is not None:
            if self.ev is None:
                self.ev = self.evidence()
                self.b.c["evidence_requests"] += 1
            if not self._check(xf, *self.ev):
                self.log["evidence_counterexample"] += 1
                return "evidence_fail"
        return "ok"

    def _pool(self, key, cols, types, rows):
        if key not in self.pools:
            self.pools[key] = Pool(cols, types, rows, self.consts, self.paths, self.lib, self.costs, self.b, self.log)
            self.pools[key].cap = getattr(self, "cap", TIER_CAPS[0])
        return self.pools[key]

    @staticmethod
    def _slice_groups(groups, target):
        """Groups lying entirely inside the micro-slice: (lo, hi, target). A class can be rejected EXACTLY on them from its slice
        vector, before any full check (sound prefilter)."""
        out, pos = [], 0
        for g, tg in zip(groups, target):
            if pos + len(g) > SLICE:
                break
            out.append((pos, pos + len(g), tg))
            pos += len(g)
        return out

    def _prefilter(self, pool, cid, sg, agg):
        vec = pool.classes[cid]["vec"]
        return all(agg(list(vec[lo:hi])) == tg for lo, hi, tg in sg)

    def _passing(self, pool, cid, groups, target, agg, refine=True, real=None):
        """Realisations of class cid that match on the FULL rows (group-wise). The representative is tried first; with refine=True the
        other realisations of the class are tried when it fails (REFINEMENT, every check charged). Up to PASS_ALTS passing ASTs."""
        out = []
        reals = real if real is not None else (pool.realize(cid) if refine else [pool.rep(cid)])
        for n, e in enumerate(reals):
            self.b.c["full_checks"] += 1
            f = C.compile_scalar(e, pool.cols)
            if all(agg([f(r) for r in g]) == tg for g, tg in zip(groups, target)):
                out.append(e)
                if n > 0 and len(out) == 1:
                    self.log["refinement_recovered"] += 1
                if len(out) >= PASS_ALTS:
                    break
            elif n == 0 and len(reals) > 1:
                self.log["refinement_split"] += 1
        return out

    def _refine_pass(self, pool, t, groups, target, agg, keep=None):
        """Second pass for SCANNED targets: non-representative realisations of multi-member classes (bounded by REFINE_CAP)."""
        n = 0
        for cid in pool.ids_upto(t):
            if len(pool.classes[cid]["members"]) < 2 or (keep is not None and not keep(pool.classes[cid]["type"])):
                continue
            reals = pool.realize(cid)[1:]
            n += len(reals)
            p = self._passing(pool, cid, groups, target, agg, real=reals)
            if p:
                self.log["refinement_recovered"] += 1
                return p
            if n >= REFINE_CAP:
                self.log["completeness_loss_refine_cap"] += 1
                break
        return []

    def _deduce_branch(self, pool, t, groups, target):
        """Deductive branch unification for a singleton-aligned projection target: each arm class (size <= DEDUCE_ARM_SIZE) gets a
        bitmask of the slice rows it explains; for every pair of masks covering all rows, the condition must be TRUE where only the
        first arm explains the target and FALSE / NULL where only the second does (rows both explain are free, at most DEDUCE_FREE);
        the condition class is looked up among the pool's boolean classes and each candidate branch(c, a, b) is checked on the full
        rows with refinement (every realisation of the condition class)."""
        want = tuple(tg[0] for tg in target)[:SLICE]
        n = len(want)
        full = (1 << n) - 1
        masks = {}
        for c in pool.ids_upto(t):
            cl = pool.classes[c]
            if cl["size"] > DEDUCE_ARM_SIZE:
                continue
            m = sum(1 << i for i, (v, w) in enumerate(zip(cl["ek"], want)) if v == w)
            if m:
                masks.setdefault(m, []).append(c)
        bools = {}
        for c in pool.ids_upto(C.BOOL):
            if pool.classes[c]["size"] <= CHILD_SIZE["branch"] and pool.rep(c)[0] != "const":
                bools.setdefault(pool.classes[c]["ek"], c)
        T, F, N = C.enc(True), C.enc(False), C.enc(None)
        ms = sorted(masks)
        for ma in ms:
            for mb in ms:
                if ma | mb != full or ma == mb or self.b.out():
                    continue
                opts = [[T] if (ma >> i) & 1 and not (mb >> i) & 1 else [F, N] if (mb >> i) & 1 and not (ma >> i) & 1 else [T, F, N] for i in range(n)]
                if sum(len(o) == 3 for o in opts) > DEDUCE_FREE:
                    continue
                for vec in itertools.product(*opts):
                    c = bools.get(vec)
                    if c is None:
                        continue
                    for a in masks[ma][:4]:
                        for b in masks[mb][:4]:
                            if 1 + pool.classes[c]["size"] + pool.classes[a]["size"] + pool.classes[b]["size"] > SC_SIZE:
                                continue
                            self.b.c["deduction_candidates"] += 1
                            cand = [("branch", ec, pool.rep(a), pool.rep(b)) for ec in pool.realize(c, ALT_CAP)]
                            p = self._passing(pool, None, groups, target, lambda v: sorted(C.enc(z) for z in v), real=cand)
                            if p:
                                self.log["deduced_branch"] += 1
                                return p
        return []

    def solve_projection(self, prog, x, vals):
        exp = [self.exp[k] for k in VIS]
        if any(len(R.rows) != len(E.rows) for R, E in zip(vals, exp)):
            return
        cols, types = vals[0].cols, vals[0].types
        pt = {}
        for j, (o, t) in enumerate(self.out_schema):
            pt[o] = [c for i, (c, ct) in enumerate(zip(cols, types)) if ct == t and all(
                Counter(C.enc(r[i]) for r in R.rows) == Counter(C.enc(r[j]) for r in E.rows) for R, E in zip(vals, exp))]
        fixed = [o for o in self.outn if pt[o]]
        rest = [o for o in self.outn if not pt[o]]
        for combo in itertools.islice(itertools.product(*[pt[o] for o in fixed]), 6) if fixed else [()]:
            assign = dict(zip(fixed, combo))
            ci, oi = [cols.index(assign[o]) for o in fixed], [self.outn.index(o) for o in fixed]
            groups, targets, ok = [], {o: [] for o in rest}, True
            for R, E in zip(vals, exp):
                gb, ge = {}, {}
                for r in R.rows:
                    gb.setdefault(tuple(C.enc(r[i]) for i in ci), []).append(r)
                for r in E.rows:
                    ge.setdefault(tuple(C.enc(r[i]) for i in oi), []).append(r)
                if {k: len(v) for k, v in gb.items()} != {k: len(v) for k, v in ge.items()}:
                    ok = False
                    break
                for k in sorted(gb):
                    groups.append(gb[k])
                    for o in rest:
                        targets[o].append(sorted(C.enc(r[self.outn.index(o)]) for r in ge[k]))
            if not ok:
                continue
            found = {o: [("col", assign[o])] for o in fixed}
            if rest:
                flat = [r for g in groups for r in g]
                pool = self._pool(("proj", x, combo), cols, types, flat)
                single = all(len(g) == 1 for g in groups)
                m = self._match(pool, rest, groups, targets, single, lambda v: sorted(C.enc(z) for z in v))
                if m is None:
                    continue
                found.update(m)
            yield [("map", prog, tuple((o, e[o]) for o in self.outn)) for e in _combos(found, self.outn)]

    def _match(self, pool, rest, groups, targets, single, agg):
        found, scanned, deduced = {}, {o: 0 for o in rest}, set()
        while True:
            for o in rest:
                if o in found:
                    continue
                t = self.outt[self.outn.index(o)]
                if single:
                    cid = pool.index.get((t, tuple(tg[0] for tg in targets[o])[:SLICE]))
                    p = self._passing(pool, cid, groups, targets[o], agg) if cid is not None else []
                    if not p and pool.band >= 3 and o not in deduced:
                        deduced.add(o)
                        p = self._deduce_branch(pool, t, groups, targets[o])
                else:
                    ids = pool.ids_upto(t)
                    sg = self._slice_groups(groups, targets[o])
                    p = []
                    for cid in ids[scanned[o]:]:
                        if sg and not self._prefilter(pool, cid, sg, agg):
                            continue
                        p = self._passing(pool, cid, groups, targets[o], agg, refine=False)
                        if p:
                            break
                    scanned[o] = len(ids)
                if p:
                    found[o] = p
            if all(o in found for o in rest):
                return found
            if not pool.grow():
                for o in rest:
                    if o not in found and not single:
                        p = self._refine_pass(pool, self.outt[self.outn.index(o)], groups, targets[o], agg)
                        if p:
                            found[o] = p
                return found if all(o in found for o in rest) else None

    def solve_aggregation(self, prog, x, vals):
        exp = [self.exp[k] for k in VIS]
        cols, types = vals[0].cols, vals[0].types
        keyc = {}
        for j, (o, t) in enumerate(self.out_schema):
            keyc[o] = [c for i, (c, ct) in enumerate(zip(cols, types)) if ct == t and all(
                Counter(C.enc(r[j]) for r in E.rows) == Counter({C.enc(v): 1 for v in {r[i] for r in R.rows}}) for R, E in zip(vals, exp))]
        kos = [o for o in self.outn if keyc[o]]
        for nk in (1, 2):
            for ko in itertools.combinations(kos, nk):
                for kc in itertools.islice(itertools.product(*[keyc[o] for o in ko]), 4):
                    if len(set(kc)) != len(kc) or any(o not in ko and o in kc for o in self.outn):
                        continue
                    r = self._agg_with_keys(prog, x, vals, exp, ko, kc, cols, types)
                    if r:
                        yield r
                    if self.b.out():
                        return

    def _agg_with_keys(self, prog, x, vals, exp, ko, kc, cols, types):
        ci, oi = [cols.index(c) for c in kc], [self.outn.index(o) for o in ko]
        meas_o = [o for o in self.outn if o not in ko]
        groups, targets, multi = [], {o: [] for o in meas_o}, False
        for R, E in zip(vals, exp):
            gb = {}
            for r in R.rows:
                gb.setdefault(tuple(r[i] for i in ci), []).append(r)
            ge = {tuple(r[i] for i in oi): r for r in E.rows}
            if set(gb) != set(ge) or len(ge) != len(E.rows):
                return None
            multi = multi or any(len(g) > 1 for g in gb.values())
            for k in sorted(gb, key=repr):
                groups.append(gb[k])
                for o in meas_o:
                    targets[o].append(C.enc(ge[k][self.outn.index(o)]))
        if not multi:
            return None                                          # all groups are singletons: the projection solve covers it (sound)
        found = {}
        for o in meas_o:
            if [C.enc(len(g)) for g in groups] == targets[o]:
                found[o] = [("count_star", None)]
        pool = self._pool(("agg", x, kc), cols, types, [r for g in groups for r in g]) if any(o not in found for o in meas_o) else None
        scanned = {o: 0 for o in meas_o}
        while pool is not None and not all(o in found for o in meas_o):
            for o in meas_o:
                if o in found:
                    continue
                t = self.outt[self.outn.index(o)]
                ids = pool.ids_upto()
                sg = self._slice_groups(groups, targets[o])
                for cid in ids[scanned[o]:]:
                    if self.b.out():
                        return None
                    ct = pool.classes[cid]["type"]
                    for an, af in AGG_FN.items():
                        rt = C.INT if an == "count" else ct
                        if (an == "sum" and not C.num_like(ct)) or rt != t:
                            continue
                        ag = lambda v, af=af: C.enc(af(v))                        # noqa: E731
                        if sg and not self._prefilter(pool, cid, sg, ag):
                            continue
                        p = self._passing(pool, cid, groups, targets[o], ag, refine=False)
                        if p:
                            found[o] = [(an, e) for e in p]
                            break
                    if o in found:
                        break
                scanned[o] = len(ids)
            if not all(o in found for o in meas_o) and not pool.grow():
                for o in meas_o:
                    if o in found:
                        continue
                    t = self.outt[self.outn.index(o)]
                    for an, af in AGG_FN.items():
                        keep = (lambda ct: True) if an == "count" else (lambda ct, an=an: ct == t and (an != "sum" or C.num_like(ct)))
                        if an == "count" and t != C.INT:
                            continue
                        p = self._refine_pass(pool, None, groups, targets[o], lambda v, af=af: C.enc(af(v)), keep=keep)
                        if p:
                            found[o] = [(an, e) for e in p]
                            break
                if not all(o in found for o in meas_o):
                    return None
        rename = dict(zip(kc, ko))
        out = []
        for pick in _combos(found, meas_o):
            meas = tuple((o, pick[o][0], pick[o][1]) for o in meas_o)
            fold = ("fold", prog, tuple(kc), meas)
            names = list(kc) + meas_o
            out.append(("map", fold, tuple((o, ("col", next(c for c in names if rename.get(c, c) == o))) for o in self.outn)))
        return out


def _combos(found, order, cap=12):
    keys = [o for o in order if o in found]
    return [dict(zip(keys, c)) for c in itertools.islice(itertools.product(*[found[o] for o in keys]), cap)]


def _swap_base(final, base, alt):
    """The final program with its base relation `base` replaced by the alternative `alt` (same visible class)."""
    if final[1] == base:
        return (final[0], alt) + final[2:]
    inner = final[1]
    return (final[0], (inner[0], alt) + inner[2:]) + final[2:]


def solve(task, lib=None, costs=None, budget=None, evidence=None):
    """-> dict(program (with library calls), expanded, outcome, counters, log, wall)."""
    b = budget or Budget()
    s = Search(task, lib or {}, costs or Costs(), b, evidence)
    t0 = time.time()
    prog = s.run()
    out = dict(outcome="submitted" if prog is not None else "none", program=prog, expanded=C.expand(prog, s.lib) if prog is not None else None,
               counters=dict(b.c), log=dict(s.log), wall=round(time.time() - t0, 3), wall_bound=prog is None and b.wall_bound(), evidence_used=s.ev is not None)
    if prog is not None:
        out["size"] = C.size(out["expanded"])
    return out
