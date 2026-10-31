"""Phase 14 multi-engine compiler, reverse lifters and semantic conformance verifier (NOT LOCKED; engineering machinery).

WHAT THIS MODULE DOES
  1  AST -> SQL (3 dialects)   core11 relational ASTs -> SQLite / DuckDB / Spark SQL: quoting, type names, typed NULL literals, double
                               literals, division / modulo by zero (NULLIF outside SQLite), semi / anti joins as [NOT] EXISTS (Spark:
                               LEFT SEMI / ANTI JOIN), and window ranking compiled to core11's EMPIRICALLY PROBED semantics.
  2  RANK SEMANTICS            core11_rank_semantics runs core11's rank on tie / NULL / bound probes and keeps the UNIQUE candidate rule
                               consistent with every probe: 'rank' (SQL RANK, ties kept), 'row_input' (one row per position, ties broken
                               by input order) or 'row_cols' (ties broken by every column in column order with a probed direction and
                               NULL placement). The compiler emits RANK() only for 'rank'; otherwise ROW_NUMBER() with the probed
                               tie-break (row_cols: every base column; row_input: rowid / monotonically_increasing_id() over a base table,
                               anything else unsupported). Order-key NULL placement comes from core11_null_order. An uncalibrated or
                               ambiguous probe makes every rank EngineUnsupported: a rank is never compiled on a guess.
  3  SQL -> AST (reverse)      from_sql extends the Phase 13 subset parser to everything the compiler emits; a window is accepted only
                               when its function, tie-break tail and NULL placement equal core11's probed semantics (else SqlUnsupported).
                               round_trip compares AST -> SQL -> AST by execution and never rewrites the input AST.
  4  DATAFRAME -> AST          from_dataframe parses Polars / PySpark method-chain SOURCE TEXT (Python ast, never executed) into core11
                               ASTs with engine semantics explicit (Polars SUM of all-NULL = 0, Polars rank drops NULL order values,
                               Polars inner / left joins drop right keys). dataframe_fidelity runs the ORIGINAL code natively (only when
                               the engine is installed) and compares with core11 on the lifted AST, fail-closed.
  5  POLARS / PYSPARK          eager Polars backend with SQL NULL semantics written out (same probed rank rule as SQL), and Spark SQL on a
                               local[1] session (ANSI off). A failed session start marks pyspark 'unavailable' for the process.
  6  CONFORMANCE (fail-closed) conformant only when every REQUIRED engine agreed and none disagreed, errored or went unchecked; each
                               comparison charges one full check BEFORE it runs. Unavailable / unsupported engines never agree.
  7  SUITE                     NULL 3VL, window ranking (tie and NULL-order cases kept), group folds and anti-join upserts across engines
                               (core11 = reference); a SQLite 'unsupported' case counts as failing (no silent pass).
  8  READINESS                 engine_ready(engine) is a cached LIVE probe: an installed engine must also execute a trivial query and agree
                               with core11 (fail-closed conformance) before it can serve as a REQUIRED engine. find_spec alone is not
                               evidence (e.g. pyspark without a JVM); a missing engine is reported, never simulated.

RANK REPRESENTATION  core11 executes only the FIVE-element rank AST ('rank', base, keys, orders, n); every rank this module constructs
goes through rank_ast (bound explicit, default 1). The compiler still accepts both forms (missing bound = 1).

Optional engines are detected with importlib.util.find_spec and imported only when used; missing engines are never simulated.
ATTRIBUTION  general machinery written by the engineering team (human / Claude / Codex / Gemini edits are external engineering)."""
from __future__ import annotations

import ast as _pyast
import importlib
import json
import math
import re
import sqlite3
import textwrap
import time
from collections import Counter
from decimal import Decimal
from functools import cmp_to_key

from nexus.de_phase11 import core11 as C
from nexus.de_phase13 import pipeline_lifter13 as L
from nexus.de_phase14 import engine_availability, engine_available

EXEC_ENGINES = ("sqlite", "duckdb", "polars", "pyspark")
SQL_DIALECTS = ("sqlite", "duckdb", "spark")
DF_APIS = ("polars", "pyspark")
ENGINE_DIALECT = {"sqlite": "sqlite", "duckdb": "duckdb", "pyspark": "spark"}
FEATURES = ("null_3vl", "window_rank", "group_fold", "anti_join_upsert")
STATUSES = ("agree", "disagree", "error", "unsupported", "unavailable", "unchecked")
DEFAULT_NULLS = {"sqlite": (True, False), "spark": (True, False), "duckdb": (False, False)}   # (ASC nulls first, DESC nulls first)
RID = "nx_rid"
RANK_MODES = (("rank", None, None), ("row_input", None, None)) + tuple(("row_cols", d, nf) for d in (False, True) for nf in (True, False))
_TYPES = {"sqlite": {C.INT: "INTEGER", C.NUM: "REAL", C.STR: "TEXT", C.BOOL: "INTEGER"},
          "duckdb": {C.INT: "BIGINT", C.NUM: "DOUBLE", C.STR: "VARCHAR", C.BOOL: "BOOLEAN"},
          "spark": {C.INT: "BIGINT", C.NUM: "DOUBLE", C.STR: "STRING", C.BOOL: "BOOLEAN"}}
_JOIN = {"inner": "INNER JOIN", "left": "LEFT JOIN", "right": "RIGHT JOIN", "full": "FULL OUTER JOIN", "outer": "FULL OUTER JOIN"}
_EXEC_ERRORS = L._EXEC_ERRORS


class EngineUnsupported(L.SqlUnsupported):
    """A construct the target engine backend / front end does not handle (reported 'unsupported', never approximated)."""


class EngineUnavailable(RuntimeError):
    """The engine cannot run in this environment (not installed, or its session failed to start)."""


# ------------------------------------------------------------------ values and bags
def _coerce(v, t):
    if v is None:
        return None
    return {C.INT: int, C.NUM: float, C.STR: str, C.BOOL: bool}.get(t, lambda x: x)(v)


def _sqlite_val(v):
    return int(v) if isinstance(v, bool) else L._py(v)


def norm(v):
    """Engine-neutral cell value. Integers stay EXACT (no float collapse); integral floats below 2**53 become ints; other floats
    are rounded to 9 digits; bools are 0 / 1; anything else is its string."""
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, Decimal):
        v = int(v) if v.is_finite() and v == v.to_integral_value() else float(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if not math.isfinite(v):
            return repr(v)
        return int(v) if v.is_integer() and abs(v) < 2 ** 53 else round(v, 9)
    return str(v)


def bag_equal(names, rows, E):
    """Bag equality of an engine result (column names + rows) with a core11 relation, column order independent."""
    ec, names = list(E.cols), list(names)
    if len(names) != len(ec) or sorted(names) != sorted(ec):
        return False
    idx = [names.index(c) for c in ec]
    return Counter(tuple(norm(r[j]) for j in idx) for r in rows) == Counter(tuple(norm(v) for v in r) for r in E.rows)


def _sample(names, rows, k=5):
    return dict(cols=list(names or []), rows=sorted((tuple(norm(v) for v in r) for r in (rows or [])), key=repr)[:k], n=len(rows or []))


def make_rel(cols, types, rows):
    """A core11 relation built through whatever constructor core11 exposes (validated: columns, types and rows round-trip)."""
    cols, types, rows = tuple(cols), tuple(types), [tuple(r) for r in rows]
    want = [tuple(C.enc(v) for v in r) for r in rows]

    def ok(R):
        try:
            return tuple(R.cols) == cols and tuple(R.types) == types and [tuple(C.enc(v) for v in r) for r in R.rows] == want
        except (AttributeError, TypeError):
            return False
    makers = []
    for fn in ("make_rel", "mk_rel"):
        f = getattr(C, fn, None)
        if callable(f):
            makers += [lambda f=f: f(cols, types, rows), lambda f=f: f(list(cols), list(types), list(rows)),
                       lambda f=f: f(tuple(zip(cols, types)), rows)]
    Rel = getattr(C, "Rel", None)
    if Rel is not None:
        makers += [lambda: Rel(cols, types, rows), lambda: Rel(cols=cols, types=types, rows=rows), lambda: Rel(list(cols), list(types), list(rows))]
    for mk in makers:
        try:
            R = mk()
        except Exception:                                          # noqa: BLE001 - unknown constructor signature, try the next
            continue
        if ok(R):
            return R
    raise EngineUnsupported("cannot construct a core11 relation (no compatible constructor)")


def _head(x):
    return x[0] if isinstance(x, tuple) and x and isinstance(x[0], str) else None


def _has(x, h):
    return isinstance(x, tuple) and bool(x) and (x[0] == h or any(_has(y, h) for y in x if isinstance(y, tuple)))


def rank_ast(base, keys, orders, n=1):
    """Executable core11 rank AST: ALWAYS the five-element form with the bound explicit (the four-element form does not execute)."""
    return ("rank", base, tuple(keys), tuple(orders), int(n))


# ------------------------------------------------------------------ core11 NULL-ordering and tie calibration
_NULL_ORDER = {}
_RANK_SEM = {}


def core11_null_order(refresh=False):
    """Where core11's rank places NULL order values (probed empirically, cached). Fallback: SQLite convention (NULL smallest)."""
    if _NULL_ORDER and not refresh:
        return dict(_NULL_ORDER)
    out = dict(calibrated=False, asc_nulls_first=True, desc_nulls_first=False, detail=None)
    try:
        t = make_rel(("k", "o", "v"), (C.INT, C.INT, C.INT), [(1, None, 1), (1, 5, 2)])
        got = {}
        for desc in (False, True):
            R = C.run(rank_ast(("rel", "t"), ("k",), ((("col", "o"), desc),)), {"t": t})
            vi = list(R.cols).index("v")
            kept = sorted(r[vi] for r in R.rows)
            if kept in ([1], [2]):
                got[desc] = kept == [1]
        if len(got) == 2:
            out.update(calibrated=True, asc_nulls_first=got[False], desc_nulls_first=got[True])
        else:
            out["detail"] = "probe inconclusive (ties or empty result)"
    except (EngineUnsupported,) + _EXEC_ERRORS as e:
        out["detail"] = f"{type(e).__name__}: {str(e)[:120]}"
    _NULL_ORDER.clear()
    _NULL_ORDER.update(out)
    return dict(out)


# (descending order on o, bound n, rows (k, o, a, b)); the probes jointly separate every candidate in RANK_MODES
_RANK_PROBES = (
    (True, 1, [(1, 5, 9, 1), (1, 5, 2, 8), (1, 3, 4, 4), (2, 7, 1, 1)]),
    (True, 1, [(1, 5, 2, 8), (1, 5, 9, 1), (1, 3, 4, 4)]),
    (True, 2, [(1, 5, None, 3), (1, 5, 4, None), (1, 5, 1, 2), (1, 1, 0, 0)]),
    (False, 1, [(1, 5, 4, None), (1, 5, None, 3), (1, 6, 1, 2)]),
    (False, 1, [(1, 5, 3, 9), (1, 5, 3, 2), (None, 2, 1, 1), (None, 2, 0, 5)]),
    (True, 2, [(1, 5, 1, 1), (1, 4, 2, 2), (1, 4, 3, 3)]),
)


def _cmp_val(a, b, desc, nulls_first):
    if a is None or b is None:
        if a is None and b is None:
            return 0
        return (-1 if nulls_first else 1) * (1 if a is None else -1)
    if a == b:
        return 0
    r = -1 if a < b else 1
    return -r if desc else r


def _simulate_rank(rows, mode, desc, n, nulls):
    """Reference simulation of one candidate rule on a probe (partition = column 0, order = column 1)."""
    kind, tdesc, tnf = mode
    onf = nulls["desc_nulls_first" if desc else "asc_nulls_first"]
    groups = {}
    for i, r in enumerate(rows):
        groups.setdefault(r[0], []).append((i, r))

    def ocmp(x, y):
        return _cmp_val(x[1][1], y[1][1], desc, onf)

    def full(x, y):
        c = ocmp(x, y)
        if c or kind == "rank":
            return c
        if kind == "row_cols":
            for a, b in zip(x[1], y[1]):
                c = _cmp_val(a, b, tdesc, tnf)
                if c:
                    return c
        return (x[0] > y[0]) - (x[0] < y[0])
    out = Counter()
    for g in groups.values():
        if kind == "rank":
            out.update(x[1] for x in g if 1 + sum(ocmp(y, x) < 0 for y in g) <= n)
        else:
            out.update(x[1] for x in sorted(g, key=cmp_to_key(full))[:n])
    return out


def core11_rank_semantics(refresh=False):
    """core11's rank tie rule, probed empirically (cached). calibrated only when the NULL order is calibrated, at least one probe ran
    and EXACTLY ONE candidate of RANK_MODES reproduces every probe; otherwise every rank compilation is refused."""
    if _RANK_SEM and not refresh:
        return dict(_RANK_SEM)
    nulls = core11_null_order(refresh)
    alive, used, errors = list(RANK_MODES), 0, []
    for i, (desc, n, rows) in enumerate(_RANK_PROBES):
        try:
            t = make_rel(("k", "o", "a", "b"), (C.INT,) * 4, rows)
            R = C.run(rank_ast(("rel", "t"), ("k",), ((("col", "o"), desc),), n), {"t": t})
            idx = [list(R.cols).index(c) for c in ("k", "o", "a", "b")]
            got = Counter(tuple(r[j] for j in idx) for r in R.rows)
        except (EngineUnsupported, ValueError) + _EXEC_ERRORS as e:
            errors.append(f"probe{i}: {type(e).__name__}: {str(e)[:80]}")
            continue
        used += 1
        alive = [m for m in alive if _simulate_rank(rows, m, desc, n, nulls) == got]
    mode = alive[0] if len(alive) == 1 else (None, None, None)
    out = dict(calibrated=bool(nulls.get("calibrated")) and used > 0 and len(alive) == 1, mode=mode[0], tie_desc=mode[1],
               tie_nulls_first=mode[2], candidates=[list(m) for m in alive], probes=used, errors=errors)
    _RANK_SEM.clear()
    _RANK_SEM.update(out)
    return dict(out)


# ------------------------------------------------------------------ core11 AST -> SQL (dialect aware)
def _quoter(dialect):
    if dialect == "spark":
        return lambda n: "`" + str(n).replace("`", "``") + "`"
    return lambda n: '"' + str(n).replace('"', '""') + '"'


class _Gen:
    def __init__(self, dialect, cols_of=None, nulls=None, rank_sem=None):
        if dialect not in SQL_DIALECTS:
            raise EngineUnsupported(f"unknown SQL dialect {dialect!r}")
        self.d, self.cols_of, self.n, self.q = dialect, cols_of, 0, _quoter(dialect)
        self.nulls = nulls if nulls is not None else core11_null_order()
        self.rank_sem = rank_sem if rank_sem is not None else core11_rank_semantics()
        self.nulls_clause = dialect != "sqlite" or sqlite3.sqlite_version_info >= (3, 30, 0)

    def alias(self):
        self.n += 1
        return f"nx_t{self.n}"

    def cols(self, x):
        c = self.cols_of(x) if self.cols_of else None
        if not c:
            raise EngineUnsupported("column list needed (rank / join / union) but unavailable")
        return list(c)

    def ty(self, t):
        s = _TYPES[self.d].get(t)
        if s is None:
            raise EngineUnsupported(f"type {t!r} has no {self.d} counterpart")
        return s

    def lit(self, v, t):
        if v is None:
            return f"CAST(NULL AS {self.ty(t)})" if t in _TYPES[self.d] else "NULL"
        if isinstance(v, bool):
            return ("1" if v else "0") if self.d == "sqlite" else ("TRUE" if v else "FALSE")
        if isinstance(v, (int, float)):
            if not math.isfinite(float(v)):
                raise EngineUnsupported("non-finite literal")
            if t == C.NUM or isinstance(v, float):
                f = repr(float(v))
                return f if self.d == "sqlite" else (f"CAST({f} AS DOUBLE)" if self.d == "duckdb" else f"{f}D")
            return repr(int(v))
        if isinstance(v, str):
            if self.d == "spark":
                return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
            return "'" + v.replace("'", "''") + "'"
        raise EngineUnsupported(f"literal {v!r}")

    def nulls_for(self, nulls_first, desc):
        if self.nulls_clause:
            return " NULLS FIRST" if nulls_first else " NULLS LAST"
        if nulls_first == DEFAULT_NULLS["sqlite"][1 if desc else 0]:
            return ""
        raise EngineUnsupported("this SQLite build has no NULLS FIRST / LAST and its default NULL placement differs from core11")

    def nulls_sql(self, desc):
        return self.nulls_for(self.nulls["desc_nulls_first" if desc else "asc_nulls_first"], desc)

    def rank(self, x):
        q, sem = self.q, self.rank_sem
        if not sem.get("calibrated"):
            raise EngineUnsupported("core11 rank tie semantics are not calibrated; a rank is never compiled on a guess")
        base_cols, n, mode = self.cols(x[1]), int(x[4]) if len(x) > 4 else 1, sem["mode"]
        cl = ", ".join(q(c) for c in base_cols)
        if mode == "rank" and not x[3]:                            # SQL RANK without ORDER BY: every row has rank 1
            return f"SELECT {cl} FROM ({self.rel(x[1])}) AS {self.alias()}" + ("" if n >= 1 else " WHERE 1 = 0")
        part = f"PARTITION BY {', '.join(q(k) for k in x[2])} " if x[2] else ""
        items = [f"{self.sc(e)} {'DESC' if d else 'ASC'}{self.nulls_sql(d)}" for e, d in x[3]]
        inner = None
        if mode == "row_cols":
            td = bool(sem["tie_desc"])
            items += [f"{q(c)} {'DESC' if td else 'ASC'}{self.nulls_for(sem['tie_nulls_first'], td)}" for c in base_cols]
        elif mode == "row_input":
            if _head(x[1]) != "rel" or len(x[1]) != 2 or any(str(c).lower() in ("rowid", RID) for c in base_cols):
                raise EngineUnsupported("input-order rank ties are compiled only over a base relation")
            rid = "monotonically_increasing_id()" if self.d == "spark" else "rowid"
            inner = f"SELECT *, {rid} AS {q(RID)} FROM {q(x[1][1])}"
            items.append(f"{q(RID)} ASC")
        elif mode != "rank":
            raise EngineUnsupported(f"unknown rank mode {mode!r}")
        func = "RANK" if mode == "rank" else "ROW_NUMBER"
        inner = inner if inner is not None else self.rel(x[1])
        rk, t1, t2 = q("nx_rk"), self.alias(), self.alias()
        return (f"SELECT {cl} FROM (SELECT *, {func}() OVER ({part}ORDER BY {', '.join(items)}) AS {rk} FROM ({inner}) AS {t1}) AS {t2} "
                f"WHERE {rk} <= {n}")

    def rel(self, x):
        if not isinstance(x, tuple) or not x:
            raise EngineUnsupported(f"not a relational AST: {x!r}")
        h, q = x[0], self.q
        if h == "rel" and len(x) == 2:
            return f"SELECT * FROM {q(x[1])}"
        if h == "filter" and len(x) == 3:
            return f"SELECT * FROM ({self.rel(x[1])}) AS {self.alias()} WHERE {self.sc(x[2])}"
        if h == "map" and len(x) == 3:
            return f"SELECT {', '.join(f'{self.sc(e)} AS {q(o)}' for o, e in x[2])} FROM ({self.rel(x[1])}) AS {self.alias()}"
        if h == "fold" and len(x) == 4:
            keys = [q(k) for k in x[2]]
            grp = f" GROUP BY {', '.join(keys)}" if keys else ""
            return f"SELECT {', '.join(keys + [self.agg(m) for m in x[3]])} FROM ({self.rel(x[1])}) AS {self.alias()}{grp}"
        if h == "rank" and len(x) >= 4:
            return self.rank(x)
        if h == "join" and len(x) == 6:
            kind, l, r, lk, rk = x[1:6]
            Ls, Rs, ta, tb = self.rel(l), self.rel(r), self.alias(), self.alias()
            on = " AND ".join(f"{ta}.{q(a)} = {tb}.{q(b)}" for a, b in zip(lk, rk))
            if kind in ("semi", "anti"):
                if self.d == "spark":
                    return f"SELECT * FROM ({Ls}) AS {ta} LEFT {kind.upper()} JOIN ({Rs}) AS {tb} ON {on}"
                return f"SELECT {ta}.* FROM ({Ls}) AS {ta} WHERE {'NOT ' if kind == 'anti' else ''}EXISTS (SELECT 1 FROM ({Rs}) AS {tb} WHERE {on})"
            jk = _JOIN.get(kind)
            if jk is None:
                raise EngineUnsupported(f"join kind {kind!r}")
            lc, rc, sel = self.cols(l), self.cols(r), []
            for c in self.cols(x):
                if c not in lc and c not in rc:
                    raise EngineUnsupported(f"join output column {c!r} renamed by core11")
                sel.append(f"{ta if c in lc else tb}.{q(c)} AS {q(c)}")
            return f"SELECT {', '.join(sel)} FROM ({Ls}) AS {ta} {jk} ({Rs}) AS {tb} ON {on}"
        if h == "union" and len(x) == 3:
            cl = ", ".join(q(c) for c in self.cols(x[1]))
            return f"SELECT {cl} FROM ({self.rel(x[1])}) AS {self.alias()} UNION ALL SELECT {cl} FROM ({self.rel(x[2])}) AS {self.alias()}"
        raise EngineUnsupported(f"relational head {h!r}")

    def agg(self, m):
        name, kind, e = m[0], m[1], (m[2] if len(m) > 2 else None)
        if kind == "count_star":
            return f"COUNT(*) AS {self.q(name)}"
        if kind in ("count", "sum", "min", "max", "avg") and e is not None:
            return f"{kind.upper()}({self.sc(e)}) AS {self.q(name)}"
        raise EngineUnsupported(f"aggregate {kind!r}")

    def sc(self, e):
        if not isinstance(e, tuple) or not e:
            raise EngineUnsupported(f"not a scalar AST: {e!r}")
        h = e[0]
        if h == "col":
            return self.q(e[1])
        if h == "const":
            return self.lit(e[1], e[2] if len(e) > 2 else None)
        if h == "isnull":
            return f"({self.sc(e[1])} IS NULL)"
        if h == "not":
            return f"(NOT {self.sc(e[1])})"
        if h == "cmp":
            op = L._CMP_SQL.get(e[1])
            if op is None:
                raise EngineUnsupported(f"comparison {e[1]!r}")
            return f"({self.sc(e[2])} {op} {self.sc(e[3])})"
        if h == "arith":
            sym, a, b = L._arith_sym(e[1]), self.sc(e[2]), self.sc(e[3])
            if sym == "/":
                return f"(CAST({a} AS REAL) / {b})" if self.d == "sqlite" else f"(CAST({a} AS DOUBLE) / NULLIF({b}, 0))"
            if sym == "%":
                return f"({a} % {b})" if self.d == "sqlite" else f"({a} % NULLIF({b}, 0))"
            return f"({a} {sym} {b})"
        if h in ("and", "or"):
            return f"({self.sc(e[1])} {h.upper()} {self.sc(e[2])})"
        if h == "branch":
            return f"(CASE WHEN {self.sc(e[1])} THEN {self.sc(e[2])} ELSE {self.sc(e[3])} END)"
        if h == "cast":
            return f"CAST({self.sc(e[1])} AS {self.ty(e[2])})"
        if h == "json" and self.d == "sqlite":
            return f"json_extract({self.sc(e[1])}, {self.lit('$' + ''.join('.' + str(k) for k in e[2]), C.STR)})"
        raise EngineUnsupported(f"scalar head {h!r} not compiled for {self.d}")


def to_engine_sql(ast, dialect="sqlite", cols_of=None, lib=None, nulls=None, rank_sem=None):
    """Compile a core11 relational AST to SQL for `dialect` ('sqlite' / 'duckdb' / 'spark')."""
    if lib:
        try:
            ast = C.expand(ast, lib)
        except (KeyError, IndexError) as e:
            raise EngineUnsupported(f"cannot expand library call: {e}") from e
    return _Gen(dialect, cols_of, nulls, rank_sem).rel(ast)


def compile_all(ast, env, lib=None):
    """{dialect: {sql, error}} for every SQL dialect (column lists resolved on env)."""
    cols_of, out = L._cols_fn(env), {}
    for d in SQL_DIALECTS:
        try:
            out[d] = dict(sql=to_engine_sql(ast, d, cols_of, lib), error=None)
        except L.SqlUnsupported as e:
            out[d] = dict(sql=None, error=str(e)[:200])
    return out


# ------------------------------------------------------------------ SQL -> core11 AST (reverse direction)
_DLIT = re.compile(r"(?<![\w.])(\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?)[dD](?!\w)")


def _spark_to_standard(sql):
    """Spark SQL text -> standard quoting: backtick identifiers -> "..", backslash-escaped strings -> '' escapes, 1.5D -> 1.5."""
    out, i, n = [], 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in "'`":
            j, buf = i + 1, []
            while j < n:
                c = sql[j]
                if ch == "'" and c == "\\" and j + 1 < n:
                    buf.append(sql[j + 1])
                    j += 2
                    continue
                if c == ch:
                    if j + 1 < n and sql[j + 1] == ch:
                        buf.append(ch)
                        j += 2
                        continue
                    break
                buf.append(c)
                j += 1
            if j >= n:
                raise L.SqlParseError("unterminated quoted token")
            s = "".join(buf)
            out.append("'" + s.replace("'", "''") + "'" if ch == "'" else '"' + s.replace('"', '""') + '"')
            i = j + 1
        else:
            j = i
            while j < n and sql[j] not in "'`":
                j += 1
            out.append(_DLIT.sub(r"\1", sql[i:j]))
            i = j
    return "".join(out)


class _EParser(L._Parser):
    """Phase 13 subset parser extended with the constructs the multi-dialect compiler emits."""

    def __init__(self, sql, cols_of, dialect):
        super().__init__(sql, cols_of)
        self.dialect = dialect

    def _word(self, w, k=0):
        t = self.peek(k)
        return t[0] == "id" and str(t[1]).upper() == w

    def _rid_ahead(self):
        if self.dialect == "spark":
            return self._word("MONOTONICALLY_INCREASING_ID") and self.is_op("(", 1)
        return self._word("ROWID") and not self.is_op("(", 1)

    def row_id(self):
        fn = str(self.peek()[1]).upper()
        self.i += 1
        if fn != "ROWID":
            self.expect_op("(")
            self.expect_op(")")
        self.expect_kw("AS")
        if self.ident() != RID:
            raise L.SqlUnsupported(f"row identifier must be aliased {RID}")
        return fn

    def select(self):
        outer, self.refs = self.refs, []
        self.expect_kw("SELECT")
        if self.is_kw("DISTINCT"):
            raise L.SqlUnsupported("SELECT DISTINCT")
        win = rid = None
        if self.is_ident() and self.is_op(".", 1) and self.is_op("*", 2):
            self.i, items = self.i + 3, "*"
        elif self.accept_op("*"):
            items = "*"
            if self.accept_op(","):
                if self._rid_ahead():
                    rid = self.row_id()
                else:
                    win = self.window()
        else:
            items = self.select_list()
        self.expect_kw("FROM")
        src, scope = self.from_clause()
        pred, keys = None, None
        if self.accept_kw("WHERE"):
            pred = self.expr()
            if L._has_agg(pred):
                raise L.SqlUnsupported("aggregate in WHERE")
        if self.accept_kw("GROUP"):
            self.expect_kw("BY")
            keys = [self.keyref()]
            while self.accept_op(","):
                keys.append(self.keyref())
        for w in ("HAVING", "ORDER", "LIMIT", "OVER"):
            if self.is_kw(w):
                raise L.SqlUnsupported(w)
        self.resolve(self.refs, src, scope)
        self.refs = outer
        if rid is not None:
            if pred is not None or keys is not None or len(scope) != 1 or _head(src) != "rel":
                raise L.SqlUnsupported("a row identifier is accepted only directly over a base table")
            return ("__rid", src)
        if win is not None:
            if pred is not None or keys is not None or len(scope) != 1:
                raise L.SqlUnsupported("window SELECT with WHERE / GROUP BY / join")
            return ("__ranked",) + self.window_semantics(src, win)
        if _head(src) == "__ranked":
            return self.ranked(src, items, pred, keys)
        if _head(src) == "__rid":
            raise L.SqlUnsupported("row identifier outside a window")
        base = src if pred is None else self.exists_join(src, scope, pred)
        if keys is None and items != "*" and any(L._has_agg(e) for e, _ in items):
            keys = []                                              # keyless aggregate -> keyless fold
        return self.trim(self.build(items, base, keys))

    def trim(self, x):
        """A map that only passes every input column through, in order, is its input."""
        if _head(x) == "map" and self.cols_of and all(e == ("col", o) for o, e in x[2]):
            cols = self.cols_of(x[1])
            if cols is not None and list(cols) == [o for o, _ in x[2]]:
                return x[1]
        return x

    def window(self):
        func = next((f for f in ("RANK", "ROW_NUMBER") if self._word(f) and self.is_op("(", 1)), None)
        if func is None:
            raise L.SqlUnsupported("window function other than RANK() / ROW_NUMBER()")
        self.i += 1
        for o in ("(", ")"):
            self.expect_op(o)
        self.expect_kw("OVER")
        self.expect_op("(")
        keys, items = [], []
        if self._word("PARTITION"):
            self.i += 1
            self.expect_kw("BY")
            keys = [self.keyref()]
            while self.accept_op(","):
                keys.append(self.keyref())
        if self.accept_kw("ORDER"):
            self.expect_kw("BY")
            while True:
                e, desc, nf = self.expr(), False, None
                if self._word("DESC") or self._word("ASC"):
                    desc = self._word("DESC")
                    self.i += 1
                if self._word("NULLS"):
                    self.i += 1
                    if not (self._word("FIRST") or self._word("LAST")):
                        raise L.SqlParseError("expected FIRST or LAST after NULLS")
                    nf = self._word("FIRST")
                    self.i += 1
                items.append((e, desc, nf))
                if not self.accept_op(","):
                    break
        self.expect_op(")")
        self.accept_kw("AS")
        return func, tuple(keys), items, self.ident()

    def window_semantics(self, src, win):
        """(base, partition keys, orders, rank alias) when the window equals core11's probed rank semantics, else SqlUnsupported."""
        func, keys, items, rk = win
        sem, core = core11_rank_semantics(), core11_null_order()
        if not sem.get("calibrated"):
            raise L.SqlUnsupported("core11 rank tie semantics are not calibrated")

        def nf_of(desc, nf):
            return DEFAULT_NULLS[self.dialect][1 if desc else 0] if nf is None else nf
        mode, base = sem["mode"], src
        if func == "RANK":
            if mode != "rank":
                raise L.SqlUnsupported("RANK() keeps tied rows; core11 rank does not")
            order_items = items
        elif mode == "rank":
            raise L.SqlUnsupported("ROW_NUMBER() drops tied rows; core11 rank keeps them")
        elif mode == "row_cols":
            cols = self.cols_of(src) if (self.cols_of and _head(src) != "__rid") else None
            if not cols or len(items) < len(cols):
                raise L.SqlUnsupported("ROW_NUMBER() tie-break must list every base column (column resolution needed)")
            cut = len(items) - len(cols)
            for c, (e, d, nf) in zip(cols, items[cut:]):
                if e != ("col", c) or bool(d) != bool(sem["tie_desc"]) or nf_of(d, nf) != sem["tie_nulls_first"]:
                    raise L.SqlUnsupported("ROW_NUMBER() tie-break differs from core11 rank tie semantics")
            order_items = items[:cut]
        elif mode == "row_input":
            if _head(src) != "__rid" or not items or items[-1][0] != ("col", RID) or items[-1][1]:
                raise L.SqlUnsupported("input-order ROW_NUMBER() must end with the row identifier ascending")
            base, order_items = src[1], items[:-1]
        else:
            raise L.SqlUnsupported(f"unknown core11 rank mode {mode!r}")
        if _head(base) == "__rid":
            raise L.SqlUnsupported("row identifier in an unsupported position")
        orders = []
        for e, d, nf in order_items:
            if nf_of(d, nf) != core["desc_nulls_first" if d else "asc_nulls_first"]:
                raise L.SqlUnsupported(f"NULLS {'FIRST' if nf_of(d, nf) else 'LAST'} ({'DESC' if d else 'ASC'}) differs from core11 rank "
                                       "semantics")
            orders.append((e, bool(d)))
        return base, tuple(keys), tuple(orders), rk

    def ranked(self, src, items, pred, keys):
        _, base, pkeys, orders, rk = src
        n = None
        if keys is None and _head(pred) == "cmp" and pred[2] == ("col", rk) and _head(pred[3]) == "const" \
                and isinstance(pred[3][1], int) and not isinstance(pred[3][1], bool):
            v = pred[3][1]
            n = {"le": v, "lt": v - 1, "eq": v if v == 1 else None}.get(pred[1])
        if n is None or n < 1:
            raise L.SqlUnsupported("ranked derived table without a 'rank <= n' filter")
        if items == "*" or any(e[0] != "col" or e[1] in (rk, RID) for e, _ in items):
            raise L.SqlUnsupported("rank column projected or computed over a ranked table")
        return self.trim(("map", rank_ast(base, pkeys, orders, n), tuple((a, e) for e, a in items)))

    def exists_join(self, src, scope, p):
        neg = p[0] == "not" and _head(p[1]) == "__exists"
        ex = p[1] if neg else (p if p[0] == "__exists" else None)
        if ex is None:
            if _has(p, "__exists"):
                raise L.SqlUnsupported("EXISTS inside a larger predicate")
            return ("filter", src, p)
        kind = "anti" if neg else "semi"
        if kind not in tuple(C.JOIN_KINDS):
            raise L.SqlUnsupported(f"core11 has no {kind} join")
        _, right, ra, pairs = ex
        lal, lk, rk = {a for a, _ in scope}, [], []
        for a, b in pairs:
            if a[0] == ra and b[0] in lal:
                a, b = b, a
            if a[0] not in lal or b[0] != ra:
                raise L.SqlUnsupported("EXISTS correlation must compare outer.col = inner.col")
            lk.append(a[1])
            rk.append(b[1])
        return ("join", kind, src, right, tuple(lk), tuple(rk))

    def from_clause(self):
        left, la = self.from_item()
        scope, lal = [(la, left)], {la}
        while True:
            if self.accept_kw("INNER"):
                self.expect_kw("JOIN")
                kind = "inner"
            elif self.is_kw("LEFT") or self.is_kw("RIGHT") or self.is_kw("FULL"):
                kind = self.peek()[1].lower()
                self.i += 1
                if kind == "left" and (self._word("SEMI") or self._word("ANTI")):
                    kind = self.peek()[1].lower()
                    self.i += 1
                else:
                    self.accept_kw("OUTER")
                self.expect_kw("JOIN")
            elif self.accept_kw("JOIN"):
                kind = "inner"
            elif self.is_op(",") or self.is_kw("CROSS"):
                raise L.SqlUnsupported("comma / cross join")
            else:
                break
            if kind not in tuple(C.JOIN_KINDS):
                raise L.SqlUnsupported(f"join kind {kind!r} not in core11")
            right, ra = self.from_item()
            heads = (_head(left), _head(right))
            if ra is None or any(a is None for a, _ in scope) or "__ranked" in heads or "__rid" in heads:
                raise L.SqlUnsupported("a derived table in a join needs an alias (and cannot be a bare window)")
            if ra in lal:
                raise L.SqlParseError(f"duplicate relation alias {ra!r}")
            self.expect_kw("ON")
            lk, rk = [], []
            while True:
                a = self.colref()
                self.expect_op("=")
                b = self.colref()
                sa, sb = self._side(a, lal, ra, left, right), self._side(b, lal, ra, left, right)
                if sa == "r" or sb == "l":
                    a, b, sa, sb = b, a, sb, sa
                if sa != "l" or sb != "r":
                    raise L.SqlUnsupported("ON keys must compare one column of each join side")
                lk.append(a[1])
                rk.append(b[1])
                if not self.accept_kw("AND"):
                    break
            left = ("join", kind, left, right, tuple(lk), tuple(rk))
            lal.add(ra)
            if kind not in ("semi", "anti"):                       # semi / anti joins output only the left columns
                scope.append((ra, right))
        return left, scope

    def primary(self):
        if self._word("EXISTS") and self.is_op("(", 1):
            self.i += 1
            self.expect_op("(")
            self.expect_kw("SELECT")
            if self.peek()[0] != "num":
                raise L.SqlUnsupported("EXISTS subquery must be SELECT <constant> FROM ...")
            self.i += 1
            self.expect_kw("FROM")
            right, ra = self.from_item()
            self.expect_kw("WHERE")
            pairs = []
            while True:
                a = self.colref()
                self.expect_op("=")
                pairs.append((a, self.colref()))
                if not self.accept_kw("AND"):
                    break
            self.expect_op(")")
            return ("__exists", right, ra, tuple(pairs))
        return super().primary()

    def call(self):
        fn = str(self.peek()[1]).upper()
        if fn in ("NULLIF", "AVG"):
            self.i += 1
            self.expect_op("(")
            a = self.expr()
            b = self.expr() if fn == "NULLIF" and self.accept_op(",") else None
            self.expect_op(")")
            if fn == "AVG":
                return ("__agg", "avg", a)
            if _head(b) != "const" or b[1] != 0 or isinstance(b[1], bool):
                raise L.SqlUnsupported("NULLIF other than NULLIF(x, 0)")
            return ("__nullif0", a)
        return super().call()


def _arith_sym_or_none(name):
    try:
        return L._arith_sym(name)
    except L.SqlUnsupported:
        return None


def _canon(x):
    """Undo the compiler's dialect devices: NULLIF(b, 0) divisors, the CAST(a AS DOUBLE) numerator, CAST(literal) constants."""
    if not isinstance(x, tuple):
        return x
    h = _head(x)
    if h == "__nullif0":
        raise L.SqlUnsupported("NULLIF(x, 0) outside a division / modulo divisor")
    if h == "arith" and len(x) == 4:
        a, b, sym = x[2], x[3], _arith_sym_or_none(x[1])
        if sym in ("/", "%") and _head(b) == "__nullif0":
            b = b[1]
        if sym == "/" and _head(a) == "cast" and len(a) == 3 and a[2] == C.NUM:
            a = a[1]
        return ("arith", x[1], _canon(a), _canon(b))
    x = tuple(_canon(y) for y in x)
    if h == "cast" and len(x) == 3 and _head(x[1]) == "const":
        v = x[1][1]
        if v is None:
            return ("const", None, x[2])
        if x[2] == C.NUM and isinstance(v, (int, float)) and not isinstance(v, bool):
            return ("const", float(v), C.NUM)
    return x


def from_sql(sql, dialect="sqlite", cols_of=None):
    """SQL text of `dialect` -> core11 AST (Phase 13 subset + compiler constructs; anything else raises SqlUnsupported)."""
    if dialect not in SQL_DIALECTS:
        raise EngineUnsupported(f"unknown SQL dialect {dialect!r}")
    out = _canon(_EParser(_spark_to_standard(sql) if dialect == "spark" else sql, cols_of, dialect).parse())
    if _has(out, "__ranked") or _has(out, "__exists") or _has(out, "__rid"):
        raise L.SqlUnsupported("window, row identifier or EXISTS construct in an unsupported position")
    return out


def round_trip(ast, env, dialect="sqlite", lib=None):
    """AST -> SQL -> AST; 'agree' only when both ASTs produce the same bag on env under core11 (the input AST is never rewritten:
    a non-executable input reports core_error, never agreement)."""
    cols_of = L._cols_fn(env)
    try:
        if lib:
            ast = C.expand(ast, lib)
        sql = to_engine_sql(ast, dialect, cols_of)
        back = from_sql(sql, dialect, cols_of)
    except L.SqlUnsupported as e:
        return dict(dialect=dialect, status="unsupported", detail=str(e)[:200])
    except (KeyError, IndexError) as e:
        return dict(dialect=dialect, status="unsupported", detail=f"expand: {e}")
    R1, R2 = L._run(ast, env), L._run(back, env)
    if R1 is None or R2 is None:
        return dict(dialect=dialect, status="core_error", detail="core11 failed on the original or the parsed AST", sql=sql)
    return dict(dialect=dialect, status="agree" if L._same(R2, R1) else "disagree", detail=None, sql=sql, structural=back == ast)


# ------------------------------------------------------------------ DataFrame method chains (Polars / PySpark source) -> core11 AST
_AGG = {"count": "count", "sum": "sum", "min": "min", "max": "max", "mean": "avg", "avg": "avg"}
_HOW = {"inner": "inner", "left": "left", "left_outer": "left", "right": "right", "right_outer": "right", "full": "full",
        "outer": "full", "full_outer": "full", "semi": "semi", "left_semi": "semi", "leftsemi": "semi", "anti": "anti",
        "left_anti": "anti", "leftanti": "anti"}
_PYCMP = {_pyast.Gt: "gt", _pyast.GtE: "ge", _pyast.Lt: "lt", _pyast.LtE: "le", _pyast.Eq: "eq", _pyast.NotEq: "ne"}
_PYARITH = {_pyast.Add: "+", _pyast.Sub: "-", _pyast.Mult: "*", _pyast.Div: "/", _pyast.Mod: "%"}


def _flat(args):
    out = []
    for a in args:
        out.extend(a.elts if isinstance(a, (_pyast.List, _pyast.Tuple)) else [a])
    return out


def _strc(n):
    return n.value if isinstance(n, _pyast.Constant) and isinstance(n.value, str) else None


class _DF:
    def __init__(self, api, env):
        self.api, self.env = api, env

    def bad(self, n, why):
        raise EngineUnsupported(f"{self.api} front end: {why} (line {getattr(n, 'lineno', '?')})")

    def schema(self, x):
        R = L._run(x, self.env) if self.env else None
        if R is None:
            raise EngineUnsupported(f"{self.api} front end: column resolution needs sample inputs on which the lifted prefix runs")
        return list(R.cols), dict(zip(R.cols, R.types))

    @staticmethod
    def meth(n, *names):
        return n.func.attr if (isinstance(n, _pyast.Call) and isinstance(n.func, _pyast.Attribute)
                               and (not names or n.func.attr in names)) else None

    @staticmethod
    def kw(n, k, default=None):
        return next((x.value for x in n.keywords if x.arg == k), default)

    def colname(self, n):
        if self.meth(n, "col", "column") and len(n.args) == 1 and _strc(n.args[0]) is not None:
            return n.args[0].value
        return _strc(n.slice) if isinstance(n, _pyast.Subscript) else None

    def lit(self, n):
        v = n.value
        for t, ok in ((C.BOOL, isinstance(v, bool)), (C.INT, isinstance(v, int)), (C.NUM, isinstance(v, float)), (C.STR, isinstance(v, str))):
            if ok:
                return ("const", v, t)
        self.bad(n, "untyped or unsupported literal")

    def sc(self, n):
        c = self.colname(n)
        if c is not None:
            return ("col", c)
        if isinstance(n, _pyast.Constant):
            return self.lit(n)
        if self.meth(n, "lit") and len(n.args) == 1 and isinstance(n.args[0], _pyast.Constant):
            return self.lit(n.args[0])
        if isinstance(n, _pyast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in _PYCMP:
            return ("cmp", _PYCMP[type(n.ops[0])], self.sc(n.left), self.sc(n.comparators[0]))
        if isinstance(n, _pyast.BinOp) and isinstance(n.op, (_pyast.BitAnd, _pyast.BitOr)):
            return ("and" if isinstance(n.op, _pyast.BitAnd) else "or", self.sc(n.left), self.sc(n.right))
        if isinstance(n, _pyast.BinOp) and type(n.op) in _PYARITH:
            return ("arith", L._arith_name(_PYARITH[type(n.op)]), self.sc(n.left), self.sc(n.right))
        if isinstance(n, _pyast.UnaryOp) and isinstance(n.op, (_pyast.Invert, _pyast.Not)):
            return ("not", self.sc(n.operand))
        m = self.meth(n)
        if m in ("is_null", "isNull", "is_not_null", "isNotNull") and not n.args:
            e = ("isnull", self.sc(n.func.value))
            return e if m in ("is_null", "isNull") else ("not", e)
        if m == "fill_null" and len(n.args) == 1:
            e = self.sc(n.func.value)
            return ("branch", ("isnull", e), self.sc(n.args[0]), e)
        if m == "coalesce" and len(n.args) >= 2 and isinstance(n.func.value, _pyast.Name):
            args = [self.sc(a) for a in n.args]
            out = args[-1]
            for a in reversed(args[:-1]):
                out = ("branch", ("isnull", a), out, a)
            return out
        if m == "otherwise" and len(n.args) == 1:
            return self.when(n.func.value, self.sc(n.args[0]))
        self.bad(n, f"unsupported expression {_pyast.dump(n)[:80]}")

    def when(self, n, other):
        """pl.when(c).then(a)[.when ..].otherwise(b) / F.when(c, a)[.when ..].otherwise(b); NULL conditions take the else branch."""
        if self.meth(n, "then") and len(n.args) == 1 and self.meth(n.func.value, "when") and len(n.func.value.args) == 1:
            w = n.func.value
            br, prev = ("branch", self.sc(w.args[0]), self.sc(n.args[0]), other), w.func.value
            return self.when(prev, br) if self.meth(prev, "then") else br
        if self.meth(n, "when") and len(n.args) == 2:
            br, prev = ("branch", self.sc(n.args[0]), self.sc(n.args[1]), other), n.func.value
            return self.when(prev, br) if self.meth(prev, "when") else br
        self.bad(n, "malformed when / then / otherwise chain")

    def item(self, n):
        if _strc(n) is not None:
            return n.value, ("col", n.value)
        if self.meth(n, "alias") and len(n.args) == 1 and _strc(n.args[0]) is not None:
            return n.args[0].value, self.sc(n.func.value)
        c = self.colname(n)
        if c is None:
            self.bad(n, "output expression needs .alias(name)")
        return c, ("col", c)

    def agg(self, n):
        name = None
        if self.meth(n, "alias") and len(n.args) == 1 and _strc(n.args[0]) is not None:
            name, n = n.args[0].value, n.func.value
        m, e = self.meth(n), None
        on_module = m is not None and isinstance(n.func.value, _pyast.Name)
        if m in ("len", "count") and not n.args and on_module:
            kind = "count_star"                                    # pl.len() / pl.count()
        elif m in _AGG and not n.args and not on_module:
            kind, e = _AGG[m], self.sc(n.func.value)               # pl.col(x).sum()
        elif m in _AGG and len(n.args) == 1 and on_module:        # F.sum(x) / F.count("*") / F.count(F.lit(1))
            a = n.args[0]
            star = (isinstance(a, _pyast.Constant) and a.value in ("*", 1)) or (self.meth(a, "lit") and len(a.args) == 1
                                                                              and getattr(a.args[0], "value", None) == 1)
            if m == "count" and star:
                kind = "count_star"
            else:
                kind, e = _AGG[m], (("col", a.value) if _strc(a) is not None else self.sc(a))
        else:
            self.bad(n, "unsupported aggregate")
        if name is None:
            if self.api == "polars" and _head(e) == "col":
                name = e[1]
            else:
                self.bad(n, "aggregate needs .alias(name)")
        return (name, kind, e)

    def rank_filter(self, base, p):
        """pl.col(o).rank(method, descending=d).over(keys) <= n -> rank over the non-NULL o rows (Polars ranks NULL as NULL). The
        method must reproduce core11's probed tie rule: 'min' for 'rank', 'ordinal' for 'row_input'; 'row_cols' has no equivalent."""
        if self.api != "polars" or not (isinstance(p, _pyast.Compare) and len(p.ops) == 1 and self.meth(p.left, "over")):
            return None
        rk = p.left.func.value
        if not self.meth(rk, "rank"):
            return None
        c = p.comparators[0]
        if not (isinstance(c, _pyast.Constant) and isinstance(c.value, int) and not isinstance(c.value, bool)):
            self.bad(p, "rank filter bound must be an integer literal")
        n = {_pyast.LtE: c.value, _pyast.Lt: c.value - 1, _pyast.Eq: c.value if c.value == 1 else None}.get(type(p.ops[0]))
        method = self.kw(rk, "method", rk.args[0] if rk.args else None)
        sem = core11_rank_semantics()
        want = {"rank": "min", "row_input": "ordinal"}.get(sem["mode"]) if sem.get("calibrated") else None
        if n is None or n < 1 or want is None or _strc(method) != want:
            self.bad(p, f"only rank(method={want!r}) filtered by <= n matches core11 rank semantics ({sem.get('mode')})")
        desc = self.kw(rk, "descending")
        desc = bool(desc.value) if isinstance(desc, _pyast.Constant) else False
        keys = [_strc(k) or self.colname(k) for k in _flat(p.left.args)]
        if any(k is None for k in keys):
            self.bad(p, "over() keys must be column names")
        o = self.sc(rk.func.value)
        return rank_ast(("filter", base, ("not", ("isnull", o))), keys, ((o, desc),), n)

    def join(self, n):
        left, a = self.rel(n.func.value), n.args
        if not a:
            self.bad(n, "join without a right frame")
        right = self.rel(a[0])
        (lc, _), (rc, _) = self.schema(left), self.schema(right)
        if set(lc) & set(rc):
            self.bad(n, "overlapping column names (join output naming differs across engines)")
        how = self.kw(n, "how", a[2] if len(a) > 2 else None)
        kind = _HOW.get("inner" if how is None else (_strc(how) or "?"))
        if kind is None or kind not in tuple(C.JOIN_KINDS) or (self.api == "polars" and kind in ("right", "full")):
            self.bad(n, f"join kind {getattr(how, 'value', how)!r} unsupported")
        lo, ro, lk, rk = self.kw(n, "left_on"), self.kw(n, "right_on"), [], []
        if lo is not None and ro is not None:
            lk, rk = [_strc(x) or self.colname(x) for x in _flat([lo])], [_strc(x) or self.colname(x) for x in _flat([ro])]
        else:
            def conj(x):
                if isinstance(x, _pyast.BinOp) and isinstance(x.op, _pyast.BitAnd):
                    return conj(x.left) + conj(x.right)
                if isinstance(x, _pyast.Compare) and len(x.ops) == 1 and isinstance(x.ops[0], _pyast.Eq):
                    return [x]
                self.bad(n, "join condition must be a conjunction of col == col")
            for cm in conj(self.kw(n, "on", a[1] if len(a) > 1 else None)):
                x, y = self.colname(cm.left), self.colname(cm.comparators[0])
                if x in rc and y in lc:
                    x, y = y, x
                lk.append(x if x in lc else None)
                rk.append(y if y in rc else None)
        if not lk or len(lk) != len(rk) or any(k is None for k in lk + rk) or not set(lk) <= set(lc) or not set(rk) <= set(rc):
            self.bad(n, "join keys must name one left and one right column each")
        j = ("join", kind, left, right, tuple(lk), tuple(rk))
        if self.api == "polars" and kind in ("inner", "left"):          # Polars coalesces the keys: right key columns are dropped
            return ("map", j, tuple((c, ("col", c)) for c in self.schema(j)[0] if c not in rk))
        return j

    def rel(self, n):
        if isinstance(n, _pyast.Name):
            return ("rel", n.id)
        m = self.meth(n)
        if m is None:
            self.bad(n, "expected a frame name or a method chain")
        recv, a = n.func.value, n.args
        if m in ("lazy", "collect") and not a:
            return self.rel(recv)
        if m in ("filter", "where") and len(a) == 1:
            base = self.rel(recv)
            rk = self.rank_filter(base, a[0])
            return rk if rk is not None else ("filter", base, self.sc(a[0]))
        if m == "select" and a:
            return ("map", self.rel(recv), tuple(self.item(x) for x in _flat(a)))
        if m in ("with_columns", "withColumn"):
            base = self.rel(recv)
            order = self.schema(base)[0]
            items = {c: ("col", c) for c in order}
            new = [(a[0].value, self.sc(a[1]))] if m == "withColumn" and len(a) == 2 and _strc(a[0]) else [self.item(x) for x in _flat(a)]
            for o, e in new:
                order = order if o in items else order + [o]
                items[o] = e
            return ("map", base, tuple((o, items[o]) for o in order))
        if m == "agg" and self.meth(recv, "group_by", "groupby", "groupBy"):
            base, keys = self.rel(recv.func.value), [_strc(x) or self.colname(x) for x in _flat(recv.args)]
            if any(k is None for k in keys):
                self.bad(n, "group keys must be column names")
            meas = tuple(self.agg(x) for x in _flat(a))
            fold = ("fold", base, tuple(keys), meas)
            sums = {x[0] for x in meas if x[1] == "sum"}
            if self.api == "polars" and sums:                       # Polars: SUM over no non-NULL value is 0, not NULL
                cols, types = self.schema(fold)
                zero = lambda t: ("const", 0.0 if t == C.NUM else 0, t)   # noqa: E731
                return ("map", fold, tuple((c, ("branch", ("isnull", ("col", c)), zero(types[c]), ("col", c)) if c in sums else ("col", c))
                                           for c in cols))
            return fold
        if m == "join":
            return self.join(n)
        self.bad(n, f"method {m!r} unsupported")


def from_dataframe(code, api="polars", env=None):
    """Polars / PySpark method-chain SOURCE TEXT (one expression; frames are names of env relations) -> core11 AST. The code is
    parsed, never executed. env (sample inputs) resolves columns for with_columns, joins and Polars SUM defaults."""
    if api not in DF_APIS:
        raise EngineUnsupported(f"unknown DataFrame api {api!r}")
    try:
        tree = _pyast.parse(textwrap.dedent(code).strip(), mode="eval")
    except SyntaxError as e:
        raise L.SqlParseError(f"{api} source: {e}") from e
    return _canon(_DF(api, env).rel(tree.body))


def dataframe_fidelity(code, env, api="polars", lifted=None):
    """Lift fidelity, FAIL-CLOSED: run the ORIGINAL DataFrame code natively (restricted namespace: frames + pl / F) and compare
    with core11 on the lifted AST. 'unavailable' when the engine is not installed (never counted as agreement)."""
    out = dict(api=api, status=None, detail=None)
    try:
        lifted = lifted if lifted is not None else from_dataframe(code, api, env)
    except L.SqlUnsupported as e:
        return dict(out, status="unsupported", detail=str(e)[:200])
    E = L._run(lifted, env)
    if E is None:
        return dict(out, status="core_error", detail="core11 failed on the lifted AST")
    if not engine_available("polars" if api == "polars" else "pyspark"):
        return dict(out, status="unavailable", detail=f"{api} is not installed")
    try:
        if api == "polars":
            pr = _PolarsRun(env, L._cols_fn(env), core11_null_order())
            ns = dict(pl=pr.pl, **{k: pr.frame(k) for k in env})
        else:
            ns = dict(F=importlib.import_module("pyspark.sql.functions"), **_spark_frames(_spark(), env))
        res = eval(compile(_pyast.parse(textwrap.dedent(code).strip(), mode="eval"), "<nexus_df>", "eval"), {"__builtins__": {}}, ns)
        if api == "polars":
            res = res if hasattr(res, "rows") else res.collect()
            names, rows = list(res.columns), [tuple(r) for r in res.rows()]
        else:
            names, rows = list(res.columns), [tuple(r) for r in res.collect()]
    except EngineUnavailable as e:
        return dict(out, status="unavailable", detail=str(e)[:200])
    except Exception as e:                                         # noqa: BLE001 - any native failure is 'error', never agreement
        return dict(out, status="error", detail=f"{type(e).__name__}: {str(e)[:180]}")
    return dict(out, status="agree" if bag_equal(names, rows, E) else "disagree")


# ------------------------------------------------------------------ SQL engines
def _ddl(name, R, dialect):
    q, defs = _quoter(dialect), []
    for c, t in zip(R.cols, R.types):
        s = _TYPES[dialect].get(t)
        if s is None and dialect != "sqlite":
            raise EngineUnsupported(f"column type {t!r} has no {dialect} counterpart")
        defs.append(f"{q(c)} {s or ''}".strip())
    return f"CREATE TABLE {q(name)} ({', '.join(defs)})", f"INSERT INTO {q(name)} VALUES ({', '.join('?' for _ in R.cols)})"


def _run_dbapi(con, sql, env, dialect, conv):
    for name, R in env.items():
        create, insert = _ddl(name, R, dialect)
        con.execute(create)
        if R.rows:
            con.executemany(insert, [tuple(conv(_coerce(v, t)) for v, t in zip(r, R.types)) for r in R.rows])
    cur = con.execute(sql)
    return [d[0] for d in cur.description], [tuple(r) for r in cur.fetchall()]


def _run_sqlite(sql, env):
    con = sqlite3.connect(":memory:")
    try:
        return _run_dbapi(con, sql, env, "sqlite", _sqlite_val)
    finally:
        con.close()


def _run_duckdb(sql, env):
    con = importlib.import_module("duckdb").connect(database=":memory:")
    try:
        return _run_dbapi(con, sql, env, "duckdb", lambda v: v)
    finally:
        con.close()


_SPARK = {"session": None, "error": None}


def _spark():
    if _SPARK["session"] is not None:
        return _SPARK["session"]
    if _SPARK["error"]:
        raise EngineUnavailable(_SPARK["error"])
    try:
        b = importlib.import_module("pyspark.sql").SparkSession.builder.master("local[1]").appName("nexus_phase14")
        for k, v in (("spark.ui.enabled", "false"), ("spark.sql.shuffle.partitions", "1"), ("spark.sql.ansi.enabled", "false"),
                     ("spark.sql.session.timeZone", "UTC"), ("spark.default.parallelism", "1")):
            b = b.config(k, v)
        _SPARK["session"] = b.getOrCreate()
    except Exception as e:                                         # noqa: BLE001 - no JVM / bad install: engine unavailable
        _SPARK["error"] = f"spark session failed: {type(e).__name__}: {str(e)[:160]}"
        raise EngineUnavailable(_SPARK["error"]) from e
    return _SPARK["session"]


def _spark_frames(s, env):
    T = importlib.import_module("pyspark.sql.types")
    mp, out = {C.INT: T.LongType(), C.NUM: T.DoubleType(), C.STR: T.StringType(), C.BOOL: T.BooleanType()}, {}
    for name, R in env.items():
        if any(t not in mp for t in R.types):
            raise EngineUnsupported("column type without a Spark counterpart")
        schema = T.StructType([T.StructField(c, mp[t], True) for c, t in zip(R.cols, R.types)])
        out[name] = s.createDataFrame([tuple(_coerce(v, t) for v, t in zip(r, R.types)) for r in R.rows], schema=schema)
    return out


def _run_spark(sql, env):
    s = _spark()
    frames = _spark_frames(s, env)
    try:
        for name, df in frames.items():
            df.createOrReplaceTempView(name)
        df = s.sql(sql)
        return list(df.columns), [tuple(r) for r in df.collect()]
    finally:
        for v in frames:
            try:
                s.catalog.dropTempView(v)
            except Exception:                                      # noqa: BLE001 - best-effort cleanup
                pass


# ------------------------------------------------------------------ Polars backend (AST -> eager DataFrame plan)
class _PolarsRun:
    def __init__(self, env, cols_of, nulls, sem=None):
        self.pl = pl = importlib.import_module("polars")
        self.env, self.cols_of, self.nulls = env, cols_of, nulls
        self.sem = sem if sem is not None else core11_rank_semantics()
        self.dt = {C.INT: pl.Int64, C.NUM: pl.Float64, C.STR: pl.Utf8, C.BOOL: pl.Boolean}

    def length(self):
        f = getattr(self.pl, "len", None)
        return f() if callable(f) else self.pl.count()

    def frame(self, name):
        R, pl, series = self.env[name], self.pl, []
        for i, (c, t) in enumerate(zip(R.cols, R.types)):
            if t not in self.dt:
                raise EngineUnsupported(f"column type {t!r} has no Polars counterpart")
            series.append(pl.Series(c, [_coerce(r[i], t) for r in R.rows], dtype=self.dt[t]))
        return pl.DataFrame(series)

    def rel(self, x):
        pl, h = self.pl, x[0]
        if h == "rel" and len(x) == 2:
            return self.frame(x[1])
        if h == "filter" and len(x) == 3:
            return self.rel(x[1]).filter(self.sc(x[2]))                # a NULL predicate drops the row (SQL WHERE)
        if h == "map" and len(x) == 3:
            tmps = [f"__nx_m{i}" for i in range(len(x[2]))]
            df = self.rel(x[1]).with_columns([self.sc(e).alias(t) for (_, e), t in zip(x[2], tmps)])
            return df.select([pl.col(t).alias(o) for (o, _), t in zip(x[2], tmps)])
        if h == "fold" and len(x) == 4:
            return self.fold(self.rel(x[1]), list(x[2]), x[3])
        if h == "rank" and len(x) >= 4:
            return self.rank(x, self.rel(x[1]), list(x[2]), x[3], int(x[4]) if len(x) > 4 else 1)
        if h == "join" and len(x) == 6:
            return self.join(x)
        if h == "union" and len(x) == 3:
            a = self.rel(x[1])
            b = self.rel(x[2]).select(a.columns)
            try:
                return pl.concat([a, b], how="vertical_relaxed")
            except (TypeError, ValueError):
                return pl.concat([a, b], how="vertical")
        raise EngineUnsupported(f"relational head {h!r} not compiled for polars")

    def fold(self, df, keys, meas):
        pl, aggs = self.pl, []
        for m in meas:
            name, kind, e = m[0], m[1], (m[2] if len(m) > 2 else None)
            if kind == "count_star":
                a = self.length()
            elif e is None:
                raise EngineUnsupported(f"aggregate {kind!r} without an argument")
            else:
                x = self.sc(e)
                nn = x.is_not_null().sum()
                if kind == "count":
                    a = nn
                elif kind == "sum":
                    a = pl.when(nn == 0).then(pl.lit(None)).otherwise(x.sum())   # SQL: SUM over no non-NULL value is NULL
                elif kind in ("min", "max"):
                    a = getattr(x, kind)()
                elif kind == "avg":
                    a = x.mean()
                else:
                    raise EngineUnsupported(f"aggregate {kind!r}")
            aggs.append(a.alias(name))
        if not keys:
            return df.select(aggs)
        gb = getattr(df, "group_by", None) or df.groupby
        return gb(keys, maintain_order=True).agg(aggs)

    def rank(self, x, df, keys, orders, n):
        """Same probed core11 rule as the SQL compiler: RANK (ties kept) or one row per position with the probed tie-break."""
        pl, cols, sem = self.pl, list(df.columns), self.sem
        if not sem.get("calibrated"):
            raise EngineUnsupported("core11 rank tie semantics are not calibrated; a rank is never compiled on a guess")
        mode = sem["mode"]
        if mode == "rank" and not orders:
            return df if n >= 1 else df.filter(pl.lit(False))
        tmps = [f"__nx_o{i}" for i in range(len(orders))]
        if orders:
            df = df.with_columns([self.sc(e).alias(t) for (e, _), t in zip(orders, tmps)])
        by = list(keys) + tmps
        desc = [False] * len(keys) + [bool(d) for _, d in orders]
        nl = [False] * len(keys) + [not self.nulls["desc_nulls_first" if d else "asc_nulls_first"] for _, d in orders]
        if mode == "row_cols":
            tie = [c for c in cols if c not in keys]               # partition keys are equal inside a partition
            by += tie
            desc += [bool(sem["tie_desc"])] * len(tie)
            nl += [not sem["tie_nulls_first"]] * len(tie)
        elif mode == "row_input":
            if _head(x[1]) != "rel" or len(x[1]) != 2:
                raise EngineUnsupported("input-order rank ties are compiled only over a base relation")
            df = df.with_row_index(RID) if hasattr(df, "with_row_index") else df.with_row_count(RID)
            by.append(RID)
            desc.append(False)
            nl.append(False)
        elif mode != "rank":
            raise EngineUnsupported(f"unknown rank mode {mode!r}")
        if by:
            try:
                df = df.sort(by, descending=desc, nulls_last=nl, maintain_order=True)
            except TypeError:
                df = df.sort(by, descending=desc, nulls_last=nl)
        pos = pl.int_range(0, self.length()) + 1
        df = df.with_columns((pos.over(keys) if keys else pos).alias("__nx_pos"))
        if mode == "rank":
            df = df.with_columns(pl.col("__nx_pos").min().over(keys + tmps).alias("__nx_rk"))   # RANK = first position of the tie
            return df.filter(pl.col("__nx_rk") <= n).select(cols)
        return df.filter(pl.col("__nx_pos") <= n).select(cols)

    def join(self, x):
        pl, (kind, l, r, lk, rk) = self.pl, x[1:6]
        Ld, Rd = self.rel(l), self.rel(r)
        lc, rc = list(Ld.columns), list(Rd.columns)
        rn = {c: f"__nx_r_{c}" for c in rc}
        Rd, ro = Rd.rename(rn), [rn[k] for k in rk]
        if kind in ("semi", "anti"):
            return Ld.join(Rd, left_on=list(lk), right_on=ro, how=kind).select(lc)
        hows = {"inner": ("inner",), "left": ("left",), "right": ("right",), "full": ("full", "outer"), "outer": ("full", "outer")}
        if kind not in hows:
            raise EngineUnsupported(f"join kind {kind!r}")
        J, last = None, None
        for how in hows[kind]:
            for kw in (dict(coalesce=False), {}):
                try:
                    J = Ld.join(Rd, left_on=list(lk), right_on=ro, how=how, **kw)
                    break
                except Exception as e:                             # noqa: BLE001 - API differences across polars versions
                    last = e
            if J is not None:
                break
        if J is None:
            raise last
        out = self.cols_of(x) if self.cols_of else None
        if not out:
            raise EngineUnsupported("join output columns unavailable")
        if any(c not in lc and c not in rc for c in out):
            raise EngineUnsupported("join output column renamed by core11")
        return J.select([pl.col(c) if c in lc else pl.col(rn[c]).alias(c) for c in out])

    def sc(self, e):
        pl, h = self.pl, e[0]
        if h == "col":
            return pl.col(e[1])
        if h == "const":
            t = e[2] if len(e) > 2 else None
            return pl.lit(e[1], dtype=self.dt[t]) if t in self.dt else pl.lit(e[1])
        if h == "isnull":
            return self.sc(e[1]).is_null()
        if h == "not":
            return ~self.sc(e[1])
        if h == "cmp":
            a, b = self.sc(e[2]), self.sc(e[3])
            ops = {"eq": a == b, "ne": a != b, "lt": a < b, "le": a <= b, "gt": a > b, "ge": a >= b}
            if e[1] not in ops:
                raise EngineUnsupported(f"comparison {e[1]!r}")
            return ops[e[1]]
        if h == "arith":
            sym, a, b = L._arith_sym(e[1]), self.sc(e[2]), self.sc(e[3])
            if sym == "/":
                return pl.when(b == 0).then(pl.lit(None, dtype=pl.Float64)).otherwise(a.cast(pl.Float64) / b.cast(pl.Float64))
            if sym == "%":
                return pl.when(b == 0).then(pl.lit(None)).otherwise(a % b)
            return {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b}[sym]()
        if h in ("and", "or"):
            a, b = self.sc(e[1]), self.sc(e[2])
            return a & b if h == "and" else a | b
        if h == "branch":
            return pl.when(self.sc(e[1])).then(self.sc(e[2])).otherwise(self.sc(e[3]))
        if h == "cast" and e[2] in self.dt:
            return self.sc(e[1]).cast(self.dt[e[2]], strict=False)
        raise EngineUnsupported(f"scalar head {h!r} not compiled for polars")


def _run_polars(ast, env, nulls):
    df = _PolarsRun(env, L._cols_fn(env), nulls).rel(ast)
    return list(df.columns), [tuple(r) for r in df.rows()]


# ------------------------------------------------------------------ engine dispatch and conformance
_SQL_RUNNERS = {"sqlite": _run_sqlite, "duckdb": _run_duckdb, "pyspark": _run_spark}


def run_engine(engine, ast, env, lib=None, nulls=None):
    """Execute ast on env in one engine -> dict(status 'ok' | 'unsupported' | 'unavailable' | 'error', names, rows, artifact)."""
    t0 = time.time()
    res = dict(engine=engine, status=None, names=None, rows=None, detail=None, artifact=None)
    try:
        if lib:
            ast = C.expand(ast, lib)
        if engine == "core11":
            R = C.run(ast, env)
            res.update(names=list(R.cols), rows=[tuple(r) for r in R.rows], artifact="core11")
        elif not engine_available(engine):
            raise EngineUnavailable(f"{engine} is not installed")
        elif engine == "polars":
            res["artifact"] = "polars:eager_dataframe"
            res["names"], res["rows"] = _run_polars(ast, env, nulls or core11_null_order())
        elif engine in _SQL_RUNNERS:
            res["artifact"] = sql = to_engine_sql(ast, ENGINE_DIALECT[engine], L._cols_fn(env), nulls=nulls)
            res["names"], res["rows"] = _SQL_RUNNERS[engine](sql, env)
        else:
            raise EngineUnavailable(f"unknown engine {engine!r}")
        res["status"] = "ok"
    except L.SqlUnsupported as e:
        res.update(status="unsupported", detail=str(e)[:200])
    except EngineUnavailable as e:
        res.update(status="unavailable", detail=str(e)[:200])
    except Exception as e:                                         # noqa: BLE001 - any engine failure is 'error', never agreement
        res.update(status="error", detail=f"{type(e).__name__}: {str(e)[:180]}")
    res["seconds"] = round(time.time() - t0, 4)
    return res


def conformance(ast, env, expected=None, engines=None, require=("sqlite",), lib=None, budget=None, nulls=None):
    """Run ast on every engine and compare with `expected` (default: core11 output on env). FAIL-CLOSED: conformant only when
    every required engine agreed and no engine disagreed, errored or was left unchecked by the budget (charged before running)."""
    engines, require, core_detail = (tuple(engines) if engines is not None else EXEC_ENGINES), tuple(require or ()), None
    if lib:
        try:
            ast = C.expand(ast, lib)
        except (KeyError, IndexError):
            pass
    if expected is None:
        try:
            expected = C.run(ast, env)
        except _EXEC_ERRORS as e:
            core_detail = f"{type(e).__name__}: {str(e)[:180]}"
    out = dict(engines={}, statuses={}, required=list(require), expected_rows=None if expected is None else len(expected.rows),
               core_detail=core_detail)
    if expected is None:
        out.update(conformant=False, reason="core_error", **{s: [] for s in STATUSES})
        return out
    for e in engines:
        if e == "core11":
            continue
        if engine_available(e) and not L._charge(budget, "full_checks"):
            out["statuses"][e] = "unchecked"
            out["engines"][e] = dict(status="unchecked", detail="budget refused the comparison", artifact=None, seconds=0.0)
            continue
        r = run_engine(e, ast, env, nulls=nulls)
        status = ("agree" if bag_equal(r["names"], r["rows"], expected) else "disagree") if r["status"] == "ok" else r["status"]
        info = dict(status=status, detail=r["detail"], artifact=r["artifact"], seconds=r["seconds"])
        if status == "disagree":
            info.update(got=_sample(r["names"], r["rows"]), want=_sample(expected.cols, expected.rows))
        out["statuses"][e], out["engines"][e] = status, info
    for s in STATUSES:
        out[s] = [e for e, v in out["statuses"].items() if v == s]
    reason = next((k for k in ("disagree", "error", "unchecked") if out[k]), None)
    if reason is None:
        missing = [e for e in require if out["statuses"].get(e) != "agree"]
        reason = ("required_not_agree:" + ",".join(missing)) if missing else None
    out.update(conformant=reason is None, reason=reason)
    return out


_READY = {}


def engine_ready(engine, refresh=False):
    """Live readiness of one engine (cached): an INSTALLED engine must also execute a trivial NULL-filter query and agree with core11
    (fail-closed conformance). ready=False for 'unavailable' (not installed / session failed), 'error', 'unsupported' or 'disagree':
    such an engine cannot serve as a required engine. find_spec alone is never treated as evidence; nothing is simulated."""
    if engine in _READY and not refresh:
        return dict(_READY[engine])
    if engine == "core11":
        out = dict(engine=engine, ready=True, status="agree", detail=None)
    else:
        try:
            env = {"t": make_rel(("k", "v"), (C.INT, C.INT), [(1, 2), (2, None)])}
            r = conformance(("filter", ("rel", "t"), ("not", ("isnull", ("col", "v")))), env, engines=(engine,), require=(engine,))
            out = dict(engine=engine, ready=bool(r["conformant"]), status=r["statuses"].get(engine, "unchecked"),
                       detail=(r["engines"].get(engine) or {}).get("detail"))
        except (L.SqlUnsupported,) + _EXEC_ERRORS as e:
            out = dict(engine=engine, ready=False, status="error", detail=f"{type(e).__name__}: {str(e)[:160]}")
    _READY[engine] = out
    return dict(out)


# ------------------------------------------------------------------ anti-join upserts
def upsert_encoding():
    return "anti_join" if "anti" in tuple(getattr(C, "JOIN_KINDS", ())) else "left_join_isnull"


def upsert_ast(old, new, keys, cols):
    """UPSERT: rows of `old` whose key has no match in `new` (NULL keys never match) UNION ALL `new` (native anti join when core11
    has one, else LEFT JOIN on renamed keys + IS NULL filter)."""
    keys, cols = tuple(keys), tuple(cols)
    proj = tuple((c, ("col", c)) for c in cols)
    if upsert_encoding() == "anti_join":
        kept = ("join", "anti", old, new, keys, keys)
    else:
        tmp = tuple(f"nx_uk{i}" for i in range(len(keys)))
        rn = ("map", new, tuple((t, ("col", k)) for t, k in zip(tmp, keys)))
        kept = ("filter", ("join", "left", old, rn, keys, tmp), ("isnull", ("col", tmp[0])))
    return ("union", ("map", kept, proj), ("map", new, proj))


# ------------------------------------------------------------------ conformance suite
def suite_cases():
    """Probe cases (name, feature, ast, env) for the four semantic features; core11 is the reference semantics."""
    I, N, S_ = C.INT, C.NUM, C.STR
    col, k = (lambda c: ("col", c)), (lambda v, t: ("const", v, t))
    kinds, cases = tuple(getattr(C, "JOIN_KINDS", ("inner", "left"))), []

    def add(name, feature, ast, env):
        cases.append(dict(name=name, feature=feature, ast=ast, env=env))
    t = {"t": make_rel(("id", "x", "s"), (I, I, S_), [(1, 5, "a"), (2, None, "b"), (3, 0, None), (4, -2, "a")])}
    T, gt0 = ("rel", "t"), ("cmp", "gt", col("x"), k(0, I))
    add("filter_cmp_null", "null_3vl", ("filter", T, gt0), t)
    add("filter_not_cmp_null", "null_3vl", ("filter", T, ("not", gt0)), t)
    add("filter_or_isnull", "null_3vl", ("filter", T, ("or", gt0, ("isnull", col("x")))), t)
    add("filter_and_null_str", "null_3vl", ("filter", T, ("and", ("cmp", "eq", col("s"), k("a", S_)), gt0)), t)
    add("filter_ne_null_str", "null_3vl", ("filter", T, ("cmp", "ne", col("s"), k("a", S_))), t)
    add("map_coalesce", "null_3vl", ("map", T, (("id", col("id")), ("y", ("branch", ("isnull", col("x")), k(0, I), col("x"))))), t)
    add("map_case_null_cond", "null_3vl", ("map", T, (("id", col("id")), ("y", ("branch", gt0, k(1, I), k(0, I))))), t)
    add("map_const_only", "null_3vl", ("map", T, (("c", k(7, I)),)), t)
    try:
        add("map_div_by_zero", "null_3vl", ("map", T, (("id", col("id")), ("q", ("arith", L._arith_name("/"), k(10, I), col("x"))))), t)
        add("map_add_null", "null_3vl", ("map", T, (("id", col("id")), ("z", ("arith", L._arith_name("+"), col("x"), k(1, I))))), t)
    except L.SqlUnsupported:
        pass
    e = {"e": make_rel(("uid", "ts", "v"), (I, I, I), [(1, 10, 1), (1, 20, 2), (1, 20, 3), (2, None, 4), (2, 5, 5), (None, 7, 6), (None, 7, 7)])}
    E = ("rel", "e")
    add("rank_latest_ties", "window_rank", rank_ast(E, ("uid",), ((col("ts"), True),)), e)
    add("rank_earliest_null_order", "window_rank", rank_ast(E, ("uid",), ((col("ts"), False),)), e)
    add("rank_global_desc", "window_rank", rank_ast(E, (), ((col("v"), True),)), e)
    add("rank_mixed_directions", "window_rank", rank_ast(E, ("uid",), ((col("ts"), True), (col("v"), False))), e)
    add("rank_top2", "window_rank", rank_ast(E, ("uid",), ((col("ts"), True),), 2), e)
    g = {"g": make_rel(("g", "v", "w"), (S_, I, N), [("a", 1, 1.5), ("a", None, 2.0), ("b", None, None), (None, 3, 0.5), (None, None, 1.0)])}
    G = ("rel", "g")
    add("fold_count_star", "group_fold", ("fold", G, ("g",), (("n", "count_star", None),)), g)
    add("fold_count_col", "group_fold", ("fold", G, ("g",), (("n", "count", col("v")),)), g)
    add("fold_sum_all_null_group", "group_fold", ("fold", G, ("g",), (("s", "sum", col("v")),)), g)
    add("fold_min_max", "group_fold", ("fold", G, ("g",), (("lo", "min", col("w")), ("hi", "max", col("w")))), g)
    add("fold_no_keys", "group_fold", ("fold", G, (), (("n", "count_star", None), ("s", "sum", col("w")))), g)
    add("fold_after_null_filter", "group_fold", ("fold", ("filter", G, ("cmp", "gt", col("v"), k(0, I))), ("g",), (("n", "count", col("w")),)), g)
    up = {"old": make_rel(("k", "val"), (I, S_), [(1, "a"), (2, "b"), (None, "n"), (3, "c")]),
          "new": make_rel(("k", "val"), (I, S_), [(2, "B"), (4, "D"), (None, "N")])}
    add(f"upsert_{upsert_encoding()}", "anti_join_upsert", upsert_ast(("rel", "old"), ("rel", "new"), ("k",), ("k", "val")), up)
    if "semi" in kinds:
        add("semi_join_null_key", "anti_join_upsert", ("join", "semi", ("rel", "old"), ("rel", "new"), ("k",), ("k",)), up)
    oc = {"orders": make_rel(("oid", "cid", "amt"), (I, I, N), [(1, 10, 5.0), (2, 11, 7.5), (3, None, 1.0), (4, 99, 2.0)]),
          "custs": make_rel(("cust_id", "tier"), (I, S_), [(10, "gold"), (11, None), (12, "silver")])}
    lj = ("join", "left", ("rel", "orders"), ("rel", "custs"), ("cid",), ("cust_id",))
    for kind in ("inner", "left", "right", "full"):
        if kind in kinds:
            add(f"join_{kind}_null_unmatched", "anti_join_upsert", ("join", kind) + lj[2:], oc)
    if "left" in kinds:
        add("left_lookup_default", "anti_join_upsert",
            ("map", lj, (("oid", col("oid")), ("tier", ("branch", ("isnull", col("tier")), k("none", S_), col("tier"))))), oc)
    return cases


def conformance_suite(engines=None, budget=None, round_trips=True):
    """Every suite case on every engine (core11 = reference) plus SQL round trips in every dialect. Reports per case / feature /
    engine, core_error details, failing cases and required_ok (no build error, no core error, calibrated rank semantics, every
    feature exercised, nothing disagreeing / erroring / unchecked and nothing unsupported on SQLite). Never imputes."""
    engines = tuple(engines) if engines is not None else EXEC_ENGINES
    t0, nulls, rsem = time.time(), core11_null_order(), core11_rank_semantics()
    try:
        cases, build_error = suite_cases(), None
    except (L.SqlUnsupported,) + _EXEC_ERRORS as e:
        cases, build_error = [], f"{type(e).__name__}: {str(e)[:160]}"
    rows, tally, by_engine = [], {f: {e: Counter() for e in engines} for f in FEATURES}, {e: Counter() for e in engines}
    rt_tally = {d: Counter() for d in SQL_DIALECTS}
    for c in cases:
        res = conformance(c["ast"], c["env"], engines=engines, require=(), budget=budget, nulls=nulls)
        rts = {d: round_trip(c["ast"], c["env"], d) for d in SQL_DIALECTS} if round_trips else {}
        for d, r in rts.items():
            rt_tally[d][r["status"]] += 1
        core_err = res["reason"] == "core_error"
        statuses = {e: ("core_error" if core_err else res["statuses"].get(e, "unchecked")) for e in engines}
        for e, s in statuses.items():
            tally[c["feature"]][e][s] += 1
            by_engine[e][s] += 1
        rows.append(dict(case=c["name"], feature=c["feature"], statuses=statuses, conformant=res["conformant"], reason=res["reason"],
                         core_detail=res.get("core_detail"), round_trip={d: r["status"] for d, r in rts.items()},
                         round_trip_detail={d: r.get("detail") for d, r in rts.items() if r["status"] != "agree"},
                         details={e: {k: v for k, v in d.items() if k != "artifact"} for e, d in res["engines"].items()
                                  if d["status"] not in ("agree", "unavailable")}))
    core_errors = [dict(case=r["case"], feature=r["feature"], detail=r["core_detail"]) for r in rows if r["reason"] == "core_error"]
    failing = [dict(case=r["case"], feature=r["feature"], engine=e, status=s) for r in rows for e, s in r["statuses"].items()
               if s in ("disagree", "error", "unchecked") or (s == "unsupported" and e == "sqlite")]
    features_ok = {f: any(r["feature"] == f and r["reason"] != "core_error" for r in rows)
                   and not any(x["feature"] == f for x in failing + core_errors) for f in FEATURES}
    n_ref = len(rows) - len(core_errors)
    return dict(availability=engine_availability(), engines=list(engines), null_order=nulls, rank_semantics=rsem,
                upsert_encoding=upsert_encoding(), n_cases=len(rows), n_reference_cases=n_ref, core_errors=len(core_errors),
                core_error_cases=core_errors, build_error=build_error, failing_cases=failing, features_ok=features_ok,
                required_ok=(build_error is None and not core_errors and not failing and all(features_ok.values())
                             and bool(rsem.get("calibrated"))),
                by_engine={e: dict(v) for e, v in by_engine.items()},
                by_feature={f: {e: dict(v) for e, v in d.items()} for f, d in tally.items()},
                fully_conformant_engines=sorted(e for e in engines if n_ref and by_engine[e]["agree"] == n_ref),
                round_trip={d: dict(v) for d, v in rt_tally.items()} if round_trips else {},
                cases=rows, wall=round(time.time() - t0, 3),
                attribution="multi_engine14 compiler / lifters / verifier: engineering machinery (not NEXUS learning)")


__all__ = ["EXEC_ENGINES", "SQL_DIALECTS", "DF_APIS", "ENGINE_DIALECT", "FEATURES", "STATUSES", "DEFAULT_NULLS", "RANK_MODES",
           "EngineUnsupported", "EngineUnavailable", "make_rel", "norm", "bag_equal", "rank_ast", "core11_null_order",
           "core11_rank_semantics", "to_engine_sql", "compile_all", "from_sql", "round_trip", "from_dataframe", "dataframe_fidelity",
           "run_engine", "conformance", "engine_ready", "upsert_ast", "upsert_encoding", "suite_cases", "conformance_suite"]


if __name__ == "__main__":
    rep = conformance_suite()
    print(json.dumps({k: v for k, v in rep.items() if k != "cases"}, indent=1, sort_keys=True, default=str))
