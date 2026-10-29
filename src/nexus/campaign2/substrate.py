"""Multi-world campaign: shared typed deterministic substrate (NOT LOCKED).

One language for all six worlds. Values are Python ints, bools and tuples; four value types:
  'i' int, 'b' bool, 'l' tuple of ints (lists, records, rows, signals, node sets, plans),
  'L' tuple of tuples of ints (tables, grids, adjacency lists, event streams).
Lambda contexts: 'i' (x), 'ii' (acc, x), 'l' (row). A lambda body sees its own arguments, the task inputs and constants; an
inner lambda never sees an outer lambda's arguments (closure over the task inputs only). Every primitive is total
(out-of-range reads give 0, division by 0 gives 0); results exceeding LIM_INT / LIM_LEN are invalid (None).

AST nodes (tuples):
  ('x', k)  task input k      ('c', v) constant     ('a', k) lambda argument k     ('h', k) macro / feature hole k
  ('r', rid, k)  learned representation rid applied to input k (a leaf; R)
  ('m', lid, *args)  learned library macro lid (L)
  ('p', name, *args) primitive; a functional argument is ('lam', ctx, body)
No primitive is specific to a family, world or benchmark task; the list is a small functional/relational standard library.

The enumerator is cost-ordered bottom-up synthesis with static typing, observational-equivalence deduplication over every
context (labelled examples plus the learner's own unlabelled probe inputs, so hypotheses that agree on the labels but differ
elsewhere are kept apart), subexpression sharing and a CPU deadline. Production costs come from the caller (the policy pi)."""
from __future__ import annotations

import itertools
import time

LIM_INT, LIM_LEN, ITER_MAX = 10 ** 6, 40, 8
LAM_LAG = 2


class Deadline(Exception):
    pass


def _i(v):
    return v if -LIM_INT <= v <= LIM_INT else None


def _l(t):
    return t if len(t) <= LIM_LEN else None


def _nth(l, i):
    return l[i] if 0 <= i < len(l) else 0


def _transpose(L):
    if not L:
        return ()
    w = max(len(r) for r in L)
    return tuple(tuple(r[j] if j < len(r) else 0 for r in L) for j in range(w))


def _groupsum(fk, fv, L):
    acc = {}
    for r in L:
        k = fk(r)
        v = fv(r)
        if k is None or v is None:
            return None
        acc[k] = acc.get(k, 0) + v
    return _l(tuple((k, acc[k]) for k in sorted(acc)))


def _scan(f, a, l):
    out = []
    for x in l:
        a = f(a, x)
        if a is None:
            return None
        out.append(a)
    return tuple(out)


def _fold(f, a, l):
    for x in l:
        a = f(a, x)
        if a is None:
            return None
    return a


def _iterate(f, s, n):
    for _ in range(max(0, min(n, ITER_MAX))):
        s = f(s)
        if s is None or len(s) > LIM_LEN:
            return None
    return s


def _seq(f, l):
    out = tuple(f(x) for x in l)
    return None if None in out else out


def _gather(L, l):
    out = []
    for i in l:
        if 0 <= i < len(L):
            out.extend(L[i])
    return _l(tuple(out))


def _prod(A, B):
    if len(A) * len(B) > LIM_LEN:
        return None
    return tuple(a + b for a in A for b in B)


F = ("fn",)
# name: (arg types, out type, fn); a functional slot is ("fn", ctx, out)
PRIMS = {
    "add": (("i", "i"), "i", lambda a, b: _i(a + b)),
    "sub": (("i", "i"), "i", lambda a, b: _i(a - b)),
    "mul": (("i", "i"), "i", lambda a, b: _i(a * b)),
    "div": (("i", "i"), "i", lambda a, b: a // b if b else 0),
    "mod": (("i", "i"), "i", lambda a, b: a % b if b else 0),
    "min2": (("i", "i"), "i", min),
    "max2": (("i", "i"), "i", max),
    "coalesce": (("i", "i"), "i", lambda a, b: a if a >= 0 else b),
    "lt": (("i", "i"), "b", lambda a, b: a < b),
    "eq": (("i", "i"), "b", lambda a, b: a == b),
    "and": (("b", "b"), "b", lambda a, b: a and b),
    "or": (("b", "b"), "b", lambda a, b: a or b),
    "not": (("b",), "b", lambda a: not a),
    "ite_i": (("b", "i", "i"), "i", lambda c, a, b: a if c else b),
    "ite_l": (("b", "l", "l"), "l", lambda c, a, b: a if c else b),
    "ite_L": (("b", "L", "L"), "L", lambda c, a, b: a if c else b),
    "len": (("l",), "i", len),
    "sum": (("l",), "i", lambda l: _i(sum(l))),
    "maxl": (("l",), "i", lambda l: max(l) if l else 0),
    "minl": (("l",), "i", lambda l: min(l) if l else 0),
    "head": (("l",), "i", lambda l: l[0] if l else 0),
    "last": (("l",), "i", lambda l: l[-1] if l else 0),
    "nth": (("l", "i"), "i", _nth),
    "rev": (("l",), "l", lambda l: l[::-1]),
    "sort": (("l",), "l", lambda l: tuple(sorted(l))),
    "uniq": (("l",), "l", lambda l: tuple(sorted(set(l)))),
    "take": (("l", "i"), "l", lambda l, n: l[:max(n, 0)]),
    "drop": (("l", "i"), "l", lambda l, n: l[max(n, 0):]),
    "cons": (("i", "l"), "l", lambda x, l: _l((x,) + l)),
    "cat": (("l", "l"), "l", lambda a, b: _l(a + b)),
    "list1": (("i",), "l", lambda x: (x,)),
    "list2": (("i", "i"), "l", lambda x, y: (x, y)),
    "range": (("i",), "l", lambda n: tuple(range(n)) if n <= LIM_LEN else None),
    "mem": (("i", "l"), "b", lambda x, l: x in l),
    "subset": (("l", "l"), "b", lambda a, b: set(a) <= set(b)),
    "repeat": (("l", "i"), "l", lambda l, n: _l(tuple(x for x in l for _ in range(max(n, 0)))) if n <= LIM_LEN else None),
    "map": ((("fn", "i", "i"), "l"), "l", _seq),
    "filter": ((("fn", "i", "b"), "l"), "l", lambda f, l: tuple(x for x in l if f(x))),
    "count": ((("fn", "i", "b"), "l"), "i", lambda f, l: sum(1 for x in l if f(x))),
    "zipw": ((("fn", "ii", "i"), "l", "l"), "l", lambda f, a, b: _seq(lambda p: f(*p), tuple(zip(a, b)))),
    "scan": ((("fn", "ii", "i"), "i", "l"), "l", _scan),
    "fold": ((("fn", "ii", "i"), "i", "l"), "i", _fold),
    "lenL": (("L",), "i", len),
    "row": (("L", "i"), "l", lambda L, i: L[i] if 0 <= i < len(L) else ()),
    "col": (("L", "i"), "l", lambda L, i: tuple(_nth(r, i) for r in L)),
    "revL": (("L",), "L", lambda L: L[::-1]),
    "transpose": (("L",), "L", _transpose),
    "repeatL": (("L", "i"), "L", lambda L, n: _l(tuple(r for r in L for _ in range(max(n, 0)))) if n <= LIM_LEN else None),
    "prod": (("L", "L"), "L", _prod),
    "gather": (("L", "l"), "l", _gather),
    "flat": (("L",), "l", lambda L: _l(tuple(x for r in L for x in r))),
    "mapr": ((("fn", "l", "l"), "L"), "L", _seq),
    "mapri": ((("fn", "l", "i"), "L"), "l", _seq),
    "filterr": ((("fn", "l", "b"), "L"), "L", lambda f, L: tuple(r for r in L if f(r))),
    "sortby": ((("fn", "l", "i"), "L"), "L", lambda f, L: tuple(sorted(L, key=lambda r: (f(r), r)))),
    "groupsum": ((("fn", "l", "i"), ("fn", "l", "i"), "L"), "L", _groupsum),
    "iterate": ((("fn", "l", "l"), "l", "i"), "l", _iterate),
}
LAM_ARGS = {"i": ("i",), "ii": ("i", "i"), "l": ("l",)}
CTXS = ("i", "ii", "l", "top")
BASE_CONSTS = (0, 1, 2, 3, 4, 5)


def is_fn(t):
    return isinstance(t, tuple)


# ---------------------------------------------------------------- compile / evaluate
def compile_ast(n, macros=None, feats=None):
    """AST -> closure g(X, A, H) (task inputs, lambda args, holes). macros: lid -> (body, hole types, out);
    feats: rid -> (body, in type, out)."""
    t = n[0]
    if t == "x":
        k = n[1]
        return lambda X, A, H: X[k]
    if t == "c":
        v = n[1]
        return lambda X, A, H: v
    if t == "a":
        k = n[1]
        return lambda X, A, H: A[k]
    if t == "h":
        k = n[1]
        return lambda X, A, H: H[k]
    if t == "r":
        body = compile_ast(feats[n[1]][0], macros, feats)
        k = n[2]
        return lambda X, A, H: body(X, (), (X[k],))
    if t == "lam":
        body = compile_ast(n[2], macros, feats)
        return lambda X, A, H: (lambda *args: body(X, args, H))
    if t == "m":
        body = compile_ast(macros[n[1]][0], macros, feats)
        args = [compile_ast(c, macros, feats) for c in n[2:]]

        def g(X, A, H):
            hv = tuple(a(X, A, H) for a in args)
            return None if None in hv else body(X, (), hv)
        return g
    fn = PRIMS[n[1]][2]
    args = [compile_ast(c, macros, feats) for c in n[2:]]
    if len(args) == 1:
        a0 = args[0]

        def g1(X, A, H):
            v = a0(X, A, H)
            return None if v is None else fn(v)
        return g1
    if len(args) == 2:
        a0, a1 = args

        def g2(X, A, H):
            u = a0(X, A, H)
            if u is None:
                return None
            v = a1(X, A, H)
            return None if v is None else fn(u, v)
        return g2

    def gn(X, A, H):
        vs = []
        for a in args:
            v = a(X, A, H)
            if v is None:
                return None
            vs.append(v)
        return fn(*vs)
    return gn


def run(ast, X, macros=None, feats=None):
    try:
        return compile_ast(ast, macros, feats)(tuple(X), (), ())
    except (RecursionError, TypeError, ValueError, OverflowError, IndexError, KeyError):
        return None


def size(n):
    """Description length in nodes (lambda wrappers are free; a macro or representation call is one node)."""
    if n[0] in ("x", "c", "a", "h", "r"):
        return 1
    if n[0] == "lam":
        return size(n[2])
    return 1 + sum(size(c) for c in n[2:])


def to_src(n):
    t = n[0]
    if t == "x":
        return f"x{n[1]}"
    if t == "c":
        return str(n[1])
    if t == "a":
        return ("x", "y")[n[1]] if n[1] < 2 else f"a{n[1]}"
    if t == "h":
        return f"${n[1]}"
    if t == "r":
        return f"R{n[1]}(x{n[2]})"
    if t == "lam":
        names = {"i": "x", "ii": "x y", "l": "x"}[n[1]]
        return f"(\\{names}. {to_src(n[2])})"
    head = f"L{n[1]}" if t == "m" else n[1]
    return f"{head}({', '.join(to_src(c) for c in n[2:])})"


def nodes(n):
    """Yield every node (pre-order), descending into lambda bodies."""
    yield n
    if n[0] == "lam":
        yield from nodes(n[2])
    elif n[0] in ("p", "m"):
        for c in n[2:]:
            yield from nodes(c)


def prod_names(n):
    """Production names used by an AST (for the policy's usage statistics)."""
    out = []
    for m in nodes(n):
        if m[0] == "p":
            out.append(m[1])
        elif m[0] == "m":
            out.append(f"L:{m[1]}")
        elif m[0] == "r":
            out.append(f"R:{m[1]}")
        elif m[0] == "c":
            out.append(f"c:{m[1]}")
    return out


# ---------------------------------------------------------------- enumerator
def _compositions(total, k):
    if k == 1:
        yield (total,)
        return
    for first in range(1, total - k + 2):
        for rest in _compositions(total - first, k - 1):
            yield (first,) + rest


def lam_probes(X):
    """Probe arguments for lambda contexts, from one example's inputs (no labels)."""
    ints, lists = [], []

    def walk(v, depth):
        if isinstance(v, bool):
            return
        if isinstance(v, int):
            if v not in ints:
                ints.append(v)
        elif isinstance(v, tuple):
            if depth == 0 and all(isinstance(z, int) and not isinstance(z, bool) for z in v):
                lists.append(v)
            for z in v[:8]:
                if isinstance(z, tuple) and z not in lists and len(lists) < 6:
                    lists.append(z)
                walk(z, depth + 1)
    for v in X:
        walk(v, 0)
    ints = (ints + [0, 1])[:7]
    if not lists:
        lists = [()]
    pairs = [(ints[i], ints[(i * 3 + 1) % len(ints)]) for i in range(len(ints))]
    return {"i": [(v,) for v in ints], "ii": pairs, "l": [(r,) for r in lists[:4]]}


class Search:
    """Cost-ordered bottom-up enumeration over all contexts of one task.

    xs: inputs of every top context (labelled examples first, then unlabelled probes); sig: input types; out: output type.
    costs: production -> integer cost (prims by name, 'c:<v>' constants, 'x' inputs, 'a' lambda args, 'L:<id>', 'R:<id>').
    macros: lid -> (body, hole types, out type); feats: rid -> (body, in type, out type) (instantiated on every input of the
    in type); extra: draft subtrees [(ast, ctx)] added as cost-1 leaves; consistent(vals) -> bool decides hypotheses.
    Phase 2: partial(vals) -> [0, 1] scores every inconsistent top-level candidate of the output type on the labelled
    examples; the best partial_k with score >= partial_min are kept (`partials`) as incomplete-experience material."""

    def __init__(self, xs, sig, out, costs, consistent, macros=None, feats=None, extra=(), consts=BASE_CONSTS,
                 deadline=None, pool_cap=6000, lam_max=99, prims=None, partial=None,
                 partial_min=0.3, partial_k=3):
        self.xs, self.sig, self.out, self.costs = [tuple(x) for x in xs], tuple(sig), out, costs
        self.consistent, self.macros, self.feats = consistent, macros or {}, feats or {}
        self.deadline, self.pool_cap, self.lam_max = deadline, pool_cap, lam_max
        self.prims = [p for p in (prims or PRIMS) if p in PRIMS]
        self.ctx = {"top": [(e, ()) for e in range(len(self.xs))]}
        pr = [lam_probes(x) for x in self.xs]
        for c in ("i", "ii", "l"):
            self.ctx[c] = [(e, a) for e in range(len(self.xs)) for a in pr[e][c]]
        self.pool = {c: {} for c in CTXS}           # ctx -> type -> cost -> [(ast, vals)]
        self.seen = {c: set() for c in CTXS}
        self.n_cands = 0
        self.lamcache = {}
        self.cmac = {lid: compile_ast(m[0], self.macros, self.feats) for lid, m in self.macros.items()}
        self.consts = consts
        self.extra = list(extra)
        self.fvals = {}
        for rid, (body, tin, tout) in self.feats.items():
            g = compile_ast(body, self.macros, self.feats)
            for k, t in enumerate(self.sig):
                if t == tin:
                    vs = []
                    for x in self.xs:
                        try:
                            vs.append(g(x, (), (x[k],)))
                        except Exception:                                # noqa: BLE001
                            vs.append(None)
                    if None not in vs:
                        self.fvals[(rid, k)] = (tout, vs)
        self.hyps = []
        self.partial, self.partial_min, self.partial_k, self.partials = partial, partial_min, partial_k, []
        self.pool_n = {}
        self.ex_of = {c: [e for e, _ in v] for c, v in self.ctx.items()}
        self.prods = [(p, PRIMS[p][0], PRIMS[p][1], PRIMS[p][2], self.costs.get(p, 2), False,
                       tuple(is_fn(sl) for sl in PRIMS[p][0])) for p in self.prims]
        self.prods += [(lid, m[1], m[2], self.cmac[lid], self.costs.get(f"L:{lid}", 2), True, tuple(False for _ in m[1]))
                       for lid, m in self.macros.items()]

    def _tick(self):
        self.n_cands += 1
        if self.deadline is not None and not (self.n_cands & 63) and time.process_time() > self.deadline:
            raise Deadline()

    def _add(self, ctx, t, cost, ast, vals):
        self._tick()
        if vals is None or (t, vals) in self.seen[ctx]:
            return
        self._store(ctx, t, cost, ast, vals)

    def _leaves(self, ctx, c):
        cs = self.ctx[ctx]
        if self.costs.get("x", 1) == c:
            for k, t in enumerate(self.sig):
                self._add(ctx, t, c, ("x", k), tuple(self.xs[e][k] for e, _ in cs))
        if ctx != "top" and self.costs.get("a", 1) == c:
            for k, t in enumerate(LAM_ARGS[ctx]):
                self._add(ctx, t, c, ("a", k), tuple(a[k] for _, a in cs))
        for v in self.consts:
            if self.costs.get(f"c:{v}", 1 if v <= 2 else 2) == c:
                self._add(ctx, "i", c, ("c", v), tuple(v for _ in cs))
        for (rid, k), (t, vs) in self.fvals.items():
            if self.costs.get(f"R:{rid}", 1) == c:
                self._add(ctx, t, c, ("r", rid, k), tuple(vs[e] for e, _ in cs))
        if c == 1:
            for ast, ectx in self.extra:
                if ectx == ctx:
                    self._add(ctx, _type_of(ast, self.sig, ctx, self.macros, self.feats), 1, ast, self._eval_vec(ctx, ast))

    def _eval_vec(self, ctx, ast):
        try:
            g = compile_ast(ast, self.macros, self.feats)
            vs = tuple(g(self.xs[e], a, ()) for e, a in self.ctx[ctx])
            return None if None in vs else vs
        except Exception:                                                # noqa: BLE001
            return None

    def _lams(self, body, lctx):
        """Per-context closures of a lambda body (closed over each example's inputs only)."""
        key = id(body)
        hit = self.lamcache.get(key)
        if hit is None:
            g = compile_ast(body, self.macros, self.feats)
            if lctx == "ii":
                per_e = [(lambda X: (lambda a, b: g(X, (a, b), ())))(X) for X in self.xs]
            else:
                per_e = [(lambda X: (lambda *a: g(X, a, ())))(X) for X in self.xs]
            hit = self.lamcache[key] = (per_e, body, {})
        return hit

    def _lam_col(self, body, lctx, ctx):
        per_e, _, cols = self._lams(body, lctx)
        col = cols.get(ctx)
        if col is None:
            col = cols[ctx] = [per_e[e] for e in self.ex_of[ctx]]
        return col

    def _slot_items(self, ctx, slot, cost):
        if is_fn(slot):
            _, lctx, lout = slot
            if cost > self.lam_max:
                return []
            return self.pool[lctx].get(lout, {}).get(cost, [])
        return self.pool[ctx].get(slot, {}).get(cost, [])

    def _apps(self, ctx, c):
        seen = self.seen[ctx]
        for name, slots, out, fn, base, is_mac, mask in self.prods:
            rem = c - base
            k = len(slots)
            if rem < k:
                continue
            anyfn = any(mask)
            for split in _compositions(rem, k):
                lists = [self._slot_items(ctx, s, sc) for s, sc in zip(slots, split)]
                if not all(lists):
                    continue
                for combo in itertools.product(*lists):
                    try:
                        if is_mac:
                            vals = [fn(None, (), hv) for hv in zip(*[it[1] for it in combo])]
                        elif not anyfn:
                            vals = list(map(fn, *[it[1] for it in combo]))
                        else:
                            vals = list(map(fn, *[self._lam_col(it[0], s[1], ctx) if f else it[1]
                                                  for s, it, f in zip(slots, combo, mask)]))
                    except (TypeError, ValueError, OverflowError, RecursionError, IndexError):
                        vals = None
                    self.n_cands += 1
                    if self.deadline is not None and not (self.n_cands & 255) and time.process_time() > self.deadline:
                        raise Deadline()
                    if vals is None or None in vals:
                        continue
                    vals = tuple(vals)
                    if (out, vals) in seen:
                        continue
                    if is_mac:
                        ast = ("m", name) + tuple(it[0] for it in combo)
                    else:
                        ast = ("p", name) + tuple(("lam", s[1], it[0]) if f else it[0] for s, it, f in zip(slots, combo, mask))
                    self._store(ctx, out, c, ast, vals)

    def _store(self, ctx, t, cost, ast, vals):
        self.seen[ctx].add((t, vals))
        if ctx == "top" and t == self.out:
            if self.consistent(vals):
                self.hyps.append((cost, ast, vals))
            elif self.partial is not None:
                sc = self.partial(vals)
                if sc >= self.partial_min:
                    self.partials.append((sc, -cost, ast, vals))
                    if len(self.partials) > 4 * self.partial_k:
                        self.partials.sort(key=lambda z: (z[0], z[1]), reverse=True)
                        del self.partials[self.partial_k:]
        byc = self.pool[ctx].setdefault(t, {})
        lst = byc.setdefault(cost, [])
        if self.pool_n.get((ctx, t), 0) < self.pool_cap:
            lst.append((ast, vals))
            self.pool_n[(ctx, t)] = self.pool_n.get((ctx, t), 0) + 1

    def levels(self, max_cost):
        """Generator: completes cost level c in every context, then yields c. Raises Deadline."""
        # Phase 2 bound repair: lambda-body pools are built LAZILY, lagging the top-level cost by LAM_LAG (a body of cost k
        # can only occur in a program of cost >= k + LAM_LAG, since its higher-order primitive and at least one other
        # argument each cost >= 1), so there is no fixed body-cost cap (lam_max is only an optional ceiling) and no time is spent on
        # bodies that no program of the current cost can use. Inner lambdas inside bodies lag again by the same rule.
        built = 0
        for c in range(1, max_cost + 1):
            while built < min(c - LAM_LAG, self.lam_max):
                built += 1
                for ctx in ("i", "ii", "l"):
                    self._leaves(ctx, built)
                    self._apps(ctx, built)
            self._leaves("top", c)
            self._apps("top", c)
            yield c


def _type_of(n, sig, ctx, macros, feats):
    t = n[0]
    if t == "x":
        return sig[n[1]]
    if t == "c":
        return "i"
    if t == "a":
        return LAM_ARGS[ctx][n[1]]
    if t == "r":
        return feats[n[1]][2]
    if t == "m":
        return macros[n[1]][2]
    if t == "p":
        return PRIMS[n[1]][1]
    raise ValueError(n)


def type_of(n, sig, ctx="top", macros=None, feats=None, holes=()):
    """Static type of an AST node (holes typed by `holes`)."""
    if n[0] == "h":
        return holes[n[1]]
    return _type_of(n, sig, ctx, macros or {}, feats or {})


def check_types(n, sig, ctx="top", macros=None, feats=None, holes=()):
    """Full static type check; returns the type or raises TypeError."""
    macros, feats = macros or {}, feats or {}
    t = n[0]
    if t in ("x", "c", "a", "r", "h"):
        if t == "a" and (ctx == "top" or n[1] >= len(LAM_ARGS[ctx])):
            raise TypeError("lambda arg outside lambda")
        if t == "x" and n[1] >= len(sig):
            raise TypeError("input index")
        return type_of(n, sig, ctx, macros, feats, holes)
    if t == "m":
        body, hts, out = macros[n[1]]
        if len(n) - 2 != len(hts):
            raise TypeError("macro arity")
        for c, ht in zip(n[2:], hts):
            if check_types(c, sig, ctx, macros, feats, holes) != ht:
                raise TypeError("macro arg type")
        return out
    slots, out, _ = PRIMS[n[1]]
    if len(n) - 2 != len(slots):
        raise TypeError("arity")
    for c, s in zip(n[2:], slots):
        if is_fn(s):
            if c[0] != "lam" or c[1] != s[1] or check_types(c[2], sig, s[1], macros, feats, holes) != s[2]:
                raise TypeError("lambda slot")
        elif check_types(c, sig, ctx, macros, feats, holes) != s:
            raise TypeError(f"slot {n[1]}")
    return out
