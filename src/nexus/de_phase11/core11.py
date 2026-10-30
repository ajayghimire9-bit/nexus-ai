"""Phase 11 relational core (NOT LOCKED): typed AST, published primitive inventory, type checker, reference interpreter.

PHYSICAL TYPES (hard checks):  int (64-bit; |v| < 2^63, else ERR), num (IEEE double), str, bool; every value may be NULL (None).
Relations are BAGS of rows with an ordered schema [(name, type)]. Inferred ROLES (identity, arrival order, quantity, category) are
NOT types: they live in synth11 as soft ranking features and never forbid a type-correct operation.

THREE OUTCOMES: a value, NULL, or ERR (a runtime error). ERR propagates through every operator except an unchosen branch arm (branch
is lazy); a relation whose evaluation produces ERR in any evaluated expression is ERR as a whole (like a SQL runtime error aborting the
query). Programs outside the supported fragment raise Unsupported at type-check / compile time.

SCALAR OPERATOR FAMILIES (AST node = tuple; every sub-operation listed; no hidden normaliser or repair routine)
  const    ("const", v, T)                  literal of type T (v may be None = typed NULL)
  ref      ("col", name)                    column of the current row (row variable is implicit; scope = the relation being mapped)
  is_null  ("isnull", e)                    TRUE iff e is NULL (never NULL itself)
  compare  ("cmp", op, a, b)  op in eq ne lt le gt ge   SQL three-valued: NULL if either side is NULL; int/num compare numerically,
                                            str/str by code point, bool only eq/ne; other type pairs are type errors
           ("and", a, b) ("or", a, b) ("not", a)        Kleene three-valued logic
  arith    ("arith", op, a, b)  op in add sub mul div mod   NULL in -> NULL out; int op int -> int for add/sub/mul/mod (|result| >= 2^63 ->
                                            ERR); div ALWAYS returns num (true division); division or modulo by zero -> NULL; mod is int-only;
                                            num results are IEEE doubles (no rounding rule beyond IEEE)
  branch   ("branch", c, a, b)              CASE WHEN c THEN a ELSE b: c NULL or FALSE -> b; lazy; a / b of one type (int/num -> num)
  json_get ("json", e, path)                e: str holding JSON; path: tuple of object keys. NULL input, invalid JSON, a missing key or a
                                            JSON null -> NULL; a JSON string -> its text; a number -> its numeric text (ints as integers,
                                            other numbers as Python float repr, e.g. 1.50 -> '1.5', 1e3 -> '1000.0'); true/false -> 'true' /
                                            'false'; an object / array -> its minified JSON text. Always returns str (no implicit cast).
  convert  ("cast", e, T)                   EXPLICIT conversions only: str->int ('[+-]?[0-9]+' else NULL; out of int64 -> ERR),
                                            str->num ('[+-]?([0-9]+(.[0-9]*)?|.[0-9]+)' else NULL), int->num, int->str. Others Unsupported.
  call     ("call", f, args)                a library function (inlined: call-by-name substitution of its typed parameters)
  param    ("param", i)                     parameter i inside a function body (scalar expression, column name, literal or relation)
RELATIONAL OPERATOR FAMILIES
  rel          ("rel", name)                                 an input relation
  project_map  ("map", R, ((name, e), ...))                  one output row per input row; output schema = exactly the listed columns
  filter_rows  ("filter", R, p)                              keeps rows where p is TRUE (FALSE and NULL drop the row)
  fold_group   ("fold", R, keys, ((name, agg, e), ...))      GROUP BY keys (NULL keys form ONE group); agg in sum count count_star min max:
                                                             sum / min / max ignore NULLs and give NULL on an empty or all-NULL group; count
                                                             counts non-NULL e, count_star counts rows (both 0 when empty); sum int -> int.
                                                             keys = () -> exactly ONE output row, even for empty input (SQL). The fold
                                                             fragment is these monoid combiners over arbitrary row expressions; an arbitrary
                                                             accumulator program is Unsupported (not compilable to a native aggregate).
  rank_window  ("rank", R, keys, ((e, desc), ...), k)        ROW_NUMBER() OVER (PARTITION BY keys ORDER BY e1 [DESC] ..., then EVERY column of
                                                             R ascending) <= k; NULLs sort LAST in both directions; NULL keys form one
                                                             partition. The all-column tie-break makes the result deterministic.
  join_rel     ("join", kind, L, R, lkeys, rkeys)            kind in inner left semi anti; key pairs must have IDENTICAL physical types (no
                                                             implicit coercion: cast explicitly); NULL keys never match; duplicate keys
                                                             multiply (bag); left: unmatched left rows once with NULL right columns; output =
                                                             L columns + R columns (a clashing R name gets suffix '_r'); semi / anti = L columns
  union_rel    ("union", A, B)                               UNION ALL (bag); B is aligned to A BY NAME; names and types must match
Not provided (explicitly): transactional MERGE (a pure next-state upsert is EXPRESSIBLE, e.g. union(anti-join(old, new), new), but is
not equated with MERGE's duplicate-source, delete-clause or transactional behaviour), set (DISTINCT) union, ORDER BY / LIMIT output order
(outputs compare as bags), recursion, arbitrary fold accumulators.
SIZE  expanded size = AST nodes after inlining every call: each operator node 1, each column reference / literal 1, each key or output
name 1. A library call never makes a program legal that its expansion would not be."""
from __future__ import annotations

import functools
import json
import re
from collections import Counter

INT, NUM, STR, BOOL = "int", "num", "str", "bool"
TYPES = (INT, NUM, STR, BOOL)
I64 = 2 ** 63
SCALAR_OPS = ("const", "col", "isnull", "cmp", "and", "or", "not", "arith", "branch", "json", "cast", "call", "param")
REL_OPS = ("rel", "map", "filter", "fold", "rank", "join", "union", "call")
CMP_OPS = ("eq", "ne", "lt", "le", "gt", "ge")
ARITH_OPS = ("add", "sub", "mul", "div", "mod")
AGGS = ("sum", "count", "count_star", "min", "max")
JOIN_KINDS = ("inner", "left", "semi", "anti")
CASTS = {(STR, INT), (STR, NUM), (INT, NUM), (INT, STR)}
INVENTORY = dict(scalar=dict(const="typed literal", col="column reference", isnull="IS NULL", cmp=list(CMP_OPS), logic=["and", "or", "not"],
                             arith=list(ARITH_OPS), branch="lazy CASE WHEN", json="json_get(str, key path) -> str", cast=sorted(f"{a}->{b}" for a, b in CASTS),
                             call="library function (inlined)", param="function parameter"),
                 relational=dict(rel="input relation", map="project_map", filter="filter_rows", fold=list(AGGS), rank="rank_window (row_number <= k)",
                                 join=list(JOIN_KINDS), union="union all by name"))


class Unsupported(Exception):
    pass


class TypeErr(Exception):
    pass


class _Err:
    __slots__ = ()

    def __repr__(self):
        return "ERR"


ERR = _Err()


class Rel:
    __slots__ = ("cols", "types", "rows")

    def __init__(self, cols, types, rows):
        self.cols, self.types, self.rows = tuple(cols), tuple(types), list(rows)

    def schema(self):
        return tuple(zip(self.cols, self.types))

    def bag(self):
        return Counter(tuple(enc(v) for v in r) for r in self.rows)

    def __repr__(self):
        return f"Rel({list(self.cols)}, {len(self.rows)} rows)"


class RelErr(Exception):
    """A relation evaluation that hit ERR (the whole query fails)."""


def enc(v):
    """Full value encoding used for comparison / fingerprints (NULL, ERR and type distinguished; floats rounded to 12 significant
    digits so that summation order does not split equal values)."""
    if v is None:
        return ("N",)
    if v is ERR:
        return ("E",)
    if isinstance(v, bool):
        return ("b", v)
    if isinstance(v, int):
        return ("i", v)
    if isinstance(v, float):
        if v != v:
            return ("f", "nan")
        return ("f", float(f"{v:.12g}"))
    return ("s", v)


# ------------------------------------------------------------------ library expansion
def subst(x, args):
    if isinstance(x, tuple):
        if len(x) == 2 and x[0] == "param" and isinstance(x[1], int):
            return args[x[1]]
        return tuple(subst(y, args) for y in x)
    return x


def expand(x, lib):
    """Inline every library call (recursively: functions may call earlier functions)."""
    if isinstance(x, tuple):
        if x and x[0] == "call" and len(x) == 3 and isinstance(x[1], str):
            f = lib[x[1]]
            return expand(subst(f["body"], tuple(expand(a, lib) for a in x[2])), lib)
        return tuple(expand(y, lib) for y in x)
    return x


def size(x):
    """Expanded-size count of an AST (structural, per operator; see the module docstring). A surviving call counts 1 + its args."""
    op = x[0]
    if op in ("const", "col", "rel", "param"):
        return 1
    if op in ("isnull", "not", "cast"):
        return 1 + size(x[1])
    if op in ("cmp", "arith"):
        return 1 + size(x[2]) + size(x[3])
    if op in ("and", "or", "union"):
        return 1 + size(x[1]) + size(x[2])
    if op == "branch":
        return 1 + size(x[1]) + size(x[2]) + size(x[3])
    if op == "json":
        return 1 + size(x[1]) + len(x[2])
    if op == "call":
        return 1 + sum(size(a) if isinstance(a, tuple) and a and isinstance(a[0], str) and a[0] in SCALAR_OPS + REL_OPS else 1 for a in x[2])
    if op == "map":
        return 1 + size(x[1]) + sum(1 + size(e) for _, e in x[2])
    if op == "filter":
        return 1 + size(x[1]) + size(x[2])
    if op == "fold":
        return 1 + size(x[1]) + len(x[2]) + sum(1 + (size(e) if e is not None else 0) for _, _, e in x[3])
    if op == "rank":
        return 1 + size(x[1]) + len(x[2]) + sum(size(e) for e, _ in x[3])
    if op == "join":
        return 1 + size(x[2]) + size(x[3]) + len(x[4]) + len(x[5])
    raise Unsupported(f"size of {op}")


# ------------------------------------------------------------------ type checking
def num_like(t):
    return t in (INT, NUM)


def scalar_type(e, schema):
    """schema: dict name -> type. Returns the physical type of e (None for an untyped NULL literal never occurs: consts carry T)."""
    op = e[0]
    if op == "const":
        if e[2] not in TYPES:
            raise TypeErr(f"bad const type {e[2]}")
        return e[2]
    if op == "col":
        if e[1] not in schema:
            raise TypeErr(f"unknown column {e[1]}")
        return schema[e[1]]
    if op == "isnull":
        scalar_type(e[1], schema)
        return BOOL
    if op == "cmp":
        a, b = scalar_type(e[2], schema), scalar_type(e[3], schema)
        if e[1] not in CMP_OPS:
            raise TypeErr("cmp op")
        if not (a == b or (num_like(a) and num_like(b))):
            raise TypeErr(f"cmp {a} {b}")
        if a == BOOL and e[1] not in ("eq", "ne"):
            raise TypeErr("bool order")
        return BOOL
    if op in ("and", "or"):
        if scalar_type(e[1], schema) != BOOL or scalar_type(e[2], schema) != BOOL:
            raise TypeErr("logic")
        return BOOL
    if op == "not":
        if scalar_type(e[1], schema) != BOOL:
            raise TypeErr("not")
        return BOOL
    if op == "arith":
        a, b = scalar_type(e[2], schema), scalar_type(e[3], schema)
        if not (num_like(a) and num_like(b)):
            raise TypeErr("arith")
        if e[1] == "div":
            return NUM
        if e[1] == "mod":
            if a != INT or b != INT:
                raise TypeErr("mod int")
            return INT
        return INT if a == b == INT else NUM
    if op == "branch":
        if scalar_type(e[1], schema) != BOOL:
            raise TypeErr("branch cond")
        a, b = scalar_type(e[2], schema), scalar_type(e[3], schema)
        if a == b:
            return a
        if num_like(a) and num_like(b):
            return NUM
        raise TypeErr("branch arms")
    if op == "json":
        if scalar_type(e[1], schema) != STR or not isinstance(e[2], tuple) or not e[2]:
            raise TypeErr("json")
        return STR
    if op == "cast":
        a = scalar_type(e[1], schema)
        if a == e[2]:
            return a
        if (a, e[2]) not in CASTS:
            raise Unsupported(f"cast {a}->{e[2]}")
        return e[2]
    raise Unsupported(f"scalar op {op}")


def rel_schema(x, env_schema):
    """env_schema: dict relation name -> tuple of (name, type). Returns the output schema of relational AST x (expanded)."""
    op = x[0]
    if op == "rel":
        if x[1] not in env_schema:
            raise TypeErr(f"unknown relation {x[1]}")
        return tuple(env_schema[x[1]])
    if op == "map":
        s = dict(rel_schema(x[1], env_schema))
        names = [n for n, _ in x[2]]
        if len(set(names)) != len(names) or not names:
            raise TypeErr("map names")
        return tuple((n, scalar_type(e, s)) for n, e in x[2])
    if op == "filter":
        s = rel_schema(x[1], env_schema)
        if scalar_type(x[2], dict(s)) != BOOL:
            raise TypeErr("filter pred")
        return s
    if op == "fold":
        s = dict(rel_schema(x[1], env_schema))
        out = []
        for k in x[2]:
            if k not in s:
                raise TypeErr("fold key")
            out.append((k, s[k]))
        for n, agg, e in x[3]:
            if agg not in AGGS:
                raise Unsupported(f"aggregate {agg}")
            if agg == "count_star":
                out.append((n, INT))
                continue
            t = scalar_type(e, s)
            if agg == "count":
                out.append((n, INT))
            elif agg == "sum":
                if not num_like(t):
                    raise TypeErr("sum type")
                out.append((n, t))
            else:
                out.append((n, t))
        names = [n for n, _ in out]
        if len(set(names)) != len(names):
            raise TypeErr("fold names")
        return tuple(out)
    if op == "rank":
        s = rel_schema(x[1], env_schema)
        d = dict(s)
        for k in x[2]:
            if k not in d:
                raise TypeErr("rank key")
        for e, desc in x[3]:
            if scalar_type(e, d) == BOOL:
                pass
        if not isinstance(x[4], int) or x[4] < 1:
            raise TypeErr("rank k")
        return s
    if op == "join":
        kind, L, R, lk, rk = x[1:]
        if kind not in JOIN_KINDS:
            raise TypeErr("join kind")
        sl, sr = rel_schema(L, env_schema), rel_schema(R, env_schema)
        dl, dr = dict(sl), dict(sr)
        if len(lk) != len(rk) or not lk:
            raise TypeErr("join keys")
        for a, b in zip(lk, rk):
            if a not in dl or b not in dr or dl[a] != dr[b]:
                raise TypeErr("join key types")
        if kind in ("semi", "anti"):
            return sl
        return sl + tuple((n, t) for n, t in join_right_names(sl, sr))
    if op == "union":
        sa, sb = rel_schema(x[1], env_schema), rel_schema(x[2], env_schema)
        if dict(sa) != dict(sb) or len(sa) != len(sb):
            raise TypeErr("union schemas")
        return sa
    raise Unsupported(f"relational op {op}")


def join_right_names(sl, sr):
    taken = {n for n, _ in sl}
    out = []
    for n, t in sr:
        m = n
        while m in taken:
            m = m + "_r"
        taken.add(m)
        out.append((m, t))
    return out


# ------------------------------------------------------------------ reference interpreter
_JSON_NUM = re.compile(r"[+-]?[0-9]+$")
_INT_RE = re.compile(r"[+-]?[0-9]+")
_NUM_RE = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)")


def _json_text(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return v
    return json.dumps(v, separators=(",", ":"))


def json_get(s, path):
    if s is None:
        return None
    try:
        v = json.loads(s)
    except (ValueError, TypeError):
        return None
    for k in path:
        if not isinstance(v, dict) or k not in v:
            return None
        v = v[k]
    return _json_text(v)


def _chk(v):
    if isinstance(v, int) and not isinstance(v, bool) and not -I64 <= v < I64:
        return ERR
    return v


def _cmp(op, a, b):
    if op == "eq":
        return a == b
    if op == "ne":
        return a != b
    if op == "lt":
        return a < b
    if op == "le":
        return a <= b
    if op == "gt":
        return a > b
    return a >= b


# value-level semantics (shared by the interpreter and the synthesizer's vectorised pool: ONE definition of every operator)
def v_isnull(a):
    return ERR if a is ERR else a is None


def v_not(a):
    return a if a is None or a is ERR else not a


def v_cmp(o, a, b):
    if a is ERR or b is ERR:
        return ERR
    if a is None or b is None:
        return None
    return _cmp(o, a, b)


def v_and(a, b):
    if a is ERR or b is ERR:
        return ERR
    if a is False or b is False:
        return False
    return None if a is None or b is None else True


def v_or(a, b):
    if a is ERR or b is ERR:
        return ERR
    if a is True or b is True:
        return True
    return None if a is None or b is None else False


def v_arith(o, a, b):
    if a is ERR or b is ERR:
        return ERR
    if a is None or b is None:
        return None
    if o == "add":
        return _chk(a + b)
    if o == "sub":
        return _chk(a - b)
    if o == "mul":
        return _chk(a * b)
    if b == 0:
        return None
    if o == "div":
        return float(a) / float(b)
    return _chk(int(abs(a) % abs(b)) * (1 if a >= 0 else -1))         # SQL remainder: sign of the dividend


def v_branch(c, a, b):
    return ERR if c is ERR else a if c is True else b


def v_json(a, path):
    return ERR if a is ERR else json_get(a, path)


def v_cast(a, t):
    if a is ERR or a is None:
        return a
    if isinstance(a, str):
        if t == INT:
            return _chk(int(a)) if _INT_RE.fullmatch(a) else None
        if t == NUM:
            return float(a) if _NUM_RE.fullmatch(a) else None
        return a
    if isinstance(a, int) and not isinstance(a, bool):
        return float(a) if t == NUM else str(a) if t == STR else a
    return a


@functools.lru_cache(maxsize=200000)
def compile_scalar(e, cols):
    """e (expanded AST) over a row tuple with column names `cols` -> python function(row) -> value | None | ERR."""
    op = e[0]
    if op == "const":
        v = e[1]
        return lambda r: v
    if op == "col":
        i = cols.index(e[1])
        return lambda r: r[i]
    if op == "isnull":
        f = compile_scalar(e[1], cols)
        return lambda r: v_isnull(f(r))
    if op == "not":
        f = compile_scalar(e[1], cols)
        return lambda r: v_not(f(r))
    if op == "cmp":
        fa, fb, o = compile_scalar(e[2], cols), compile_scalar(e[3], cols), e[1]
        return lambda r: v_cmp(o, fa(r), fb(r))
    if op == "and":
        fa, fb = compile_scalar(e[1], cols), compile_scalar(e[2], cols)
        return lambda r: v_and(fa(r), fb(r))
    if op == "or":
        fa, fb = compile_scalar(e[1], cols), compile_scalar(e[2], cols)
        return lambda r: v_or(fa(r), fb(r))
    if op == "arith":
        fa, fb, o = compile_scalar(e[2], cols), compile_scalar(e[3], cols), e[1]
        return lambda r: v_arith(o, fa(r), fb(r))
    if op == "branch":
        fc, fa, fb = compile_scalar(e[1], cols), compile_scalar(e[2], cols), compile_scalar(e[3], cols)

        def g(r):                                                   # lazy: only the chosen arm is evaluated
            c = fc(r)
            if c is ERR:
                return ERR
            return fa(r) if c is True else fb(r)
        return g
    if op == "json":
        fa, path = compile_scalar(e[1], cols), e[2]
        return lambda r: v_json(fa(r), path)
    if op == "cast":
        fa, t = compile_scalar(e[1], cols), e[2]
        return lambda r: v_cast(fa(r), t)
    raise Unsupported(f"scalar op {op} (call / param must be expanded first)")


def _sort_key_cmp(order_vals_a, order_vals_b, descs):
    for x, y, d in zip(order_vals_a, order_vals_b, descs):
        if x is None and y is None:
            continue
        if x is None:
            return 1                                                # NULLS LAST in both directions
        if y is None:
            return -1
        if x == y:
            continue
        c = -1 if x < y else 1
        return -c if d else c
    return 0


def _check_err(vals):
    for v in vals:
        if v is ERR:
            raise RelErr()


def run(x, env, _memo=None):
    """Evaluate expanded relational AST x over env (name -> Rel). Raises RelErr (ERR), TypeErr, Unsupported."""
    if _memo is not None and x in _memo:
        return _memo[x]
    op = x[0]
    if op == "rel":
        out = env[x[1]]
    elif op == "map":
        R = run(x[1], env, _memo)
        fs = [compile_scalar(e, R.cols) for _, e in x[2]]
        rows = [tuple(f(r) for f in fs) for r in R.rows]
        for r in rows:
            _check_err(r)
        s = dict(R.schema())
        out = Rel([n for n, _ in x[2]], [scalar_type(e, s) for _, e in x[2]], rows)
    elif op == "filter":
        R = run(x[1], env, _memo)
        f = compile_scalar(x[2], R.cols)
        keep = []
        for r in R.rows:
            v = f(r)
            if v is ERR:
                raise RelErr()
            if v is True:
                keep.append(r)
        out = Rel(R.cols, R.types, keep)
    elif op == "fold":
        R = run(x[1], env, _memo)
        ki = [R.cols.index(k) for k in x[2]]
        ms = [(agg, compile_scalar(e, R.cols) if agg != "count_star" else None) for _, agg, e in x[3]]
        groups = {}
        for r in R.rows:
            groups.setdefault(tuple(r[i] for i in ki), []).append(r)
        if not x[2] and not groups:
            groups[()] = []
        rows = []
        for key, rs in groups.items():
            row = list(key)
            for agg, f in ms:
                if agg == "count_star":
                    row.append(len(rs))
                    continue
                vals = [f(r) for r in rs]
                _check_err(vals)
                nn = [v for v in vals if v is not None]
                if agg == "count":
                    row.append(len(nn))
                elif not nn:
                    row.append(None)
                elif agg == "sum":
                    row.append(_chk(sum(nn)) if all(isinstance(v, int) for v in nn) else float(sum(float(v) for v in nn)))
                elif agg == "min":
                    row.append(min(nn))
                else:
                    row.append(max(nn))
            rows.append(tuple(row))
        sch = rel_schema(("fold", ("rel", "__x"), x[2], x[3]), {"__x": R.schema()})
        out = Rel([n for n, _ in sch], [t for _, t in sch], rows)
    elif op == "rank":
        R = run(x[1], env, _memo)
        ki = [R.cols.index(k) for k in x[2]]
        fs = [(compile_scalar(e, R.cols), d) for e, d in x[3]]
        descs = [d for _, d in fs] + [False] * len(R.cols)
        groups = {}
        for r in R.rows:
            ov = [f(r) for f, _ in fs]
            _check_err(ov)
            groups.setdefault(tuple(r[i] for i in ki), []).append((ov + list(r), r))
        rows = []
        for g in groups.values():
            g.sort(key=functools.cmp_to_key(lambda a, b: _sort_key_cmp(a[0], b[0], descs)))
            rows += [r for _, r in g[:x[4]]]
        out = Rel(R.cols, R.types, rows)
    elif op == "join":
        kind, L, Rr, lk, rk = x[1:]
        A, B = run(L, env, _memo), run(Rr, env, _memo)
        li, ri = [A.cols.index(k) for k in lk], [B.cols.index(k) for k in rk]
        idx = {}
        for r in B.rows:
            key = tuple(r[i] for i in ri)
            if any(v is None for v in key):
                continue
            idx.setdefault(key, []).append(r)
        rows = []
        for r in A.rows:
            key = tuple(r[i] for i in li)
            m = [] if any(v is None for v in key) else idx.get(key, [])
            if kind == "semi":
                if m:
                    rows.append(r)
            elif kind == "anti":
                if not m:
                    rows.append(r)
            elif m:
                rows += [r + s for s in m]
            elif kind == "left":
                rows.append(r + (None,) * len(B.cols))
        if kind in ("semi", "anti"):
            out = Rel(A.cols, A.types, rows)
        else:
            rn = join_right_names(A.schema(), B.schema())
            out = Rel(A.cols + tuple(n for n, _ in rn), A.types + B.types, rows)
    elif op == "union":
        A, B = run(x[1], env, _memo), run(x[2], env, _memo)
        if dict(A.schema()) != dict(B.schema()) or len(A.cols) != len(B.cols):
            raise TypeErr("union schemas")
        perm = [B.cols.index(c) for c in A.cols]
        out = Rel(A.cols, A.types, A.rows + [tuple(r[i] for i in perm) for r in B.rows])
    else:
        raise Unsupported(f"relational op {op}")
    if _memo is not None:
        _memo[x] = out
    return out


def evaluate(prog, env, lib=None):
    """-> Rel or ERR (type errors / unsupported raise)."""
    x = expand(prog, lib or {})
    rel_schema(x, {k: v.schema() for k, v in env.items()})
    try:
        return run(x, env)
    except RelErr:
        return ERR


def same_bag(a, b):
    if a is ERR or b is ERR:
        return a is b
    return a.bag() == b.bag() and sorted(a.cols) == sorted(b.cols)


def project_like(R, cols):
    """R's rows re-ordered to the column order `cols` (for comparing with an expected output schema)."""
    perm = [R.cols.index(c) for c in cols]
    return Rel(cols, [R.types[i] for i in perm], [tuple(r[i] for i in perm) for r in R.rows])
