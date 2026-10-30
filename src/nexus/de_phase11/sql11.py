"""Phase 11 native compilation (NOT LOCKED): expanded core AST -> SQL for DuckDB (primary) and SQLite (coverage extension).

Coverage stages per engine: generate native code -> execute -> semantic conformance (scripts/agi11_conformance.py compares every
result with the reference interpreter on development fixtures: NULLs, empty input, duplicate keys, aggregation, ordering / ties).
  DuckDB 1.1.3  every core operator. Division / modulo by zero are GUARDED explicitly (DuckDB itself returns inf for x / 0.0);
                str->int / str->num casts are regexp-guarded TRY casts; json_get = CASE WHEN json_valid(e) THEN
                json_extract_string(e, path) END.
  SQLite 3.50   every operator; booleans are stored as 0 / 1 and converted back by schema type; str->int / str->num via GLOB
                guards; json_get = CAST(json_extract(...) AS TEXT) guarded by json_valid; json object / boolean results differ from the
                reference text (declared: conformance reports it).
  Polars, PySpark: NOT IMPLEMENTED in Phase 11 (coverage gaps, never counted as native execution).
No fold pattern is recognised specially: the core fold is already a GROUP BY over monoid aggregates. rank_window compiles to
ROW_NUMBER() OVER (... ORDER BY keys, then every column ASC NULLS LAST) <= k in a subquery. A pure next-state upsert is just its
union / anti-join expression (no MERGE statement is ever emitted)."""
from __future__ import annotations

import sqlite3

import duckdb

from nexus.de_phase11 import core11 as C

SQLTYPE = {"duckdb": {C.INT: "BIGINT", C.NUM: "DOUBLE", C.STR: "VARCHAR", C.BOOL: "BOOLEAN"},
           "sqlite": {C.INT: "INTEGER", C.NUM: "REAL", C.STR: "TEXT", C.BOOL: "INTEGER"}}
ENGINES = ("duckdb", "sqlite")
NOT_IMPLEMENTED = ("polars", "pyspark")


def q(name):
    return '"' + name.replace('"', '""') + '"'


def lit(v, t, d):
    if v is None:
        return f"CAST(NULL AS {SQLTYPE[d][t]})"
    if t == C.BOOL:
        return ("TRUE" if v else "FALSE") if d == "duckdb" else ("1" if v else "0")
    if t == C.INT:
        return f"CAST({int(v)} AS {SQLTYPE[d][t]})"
    if t == C.NUM:
        return f"CAST({float(v)!r} AS {SQLTYPE[d][t]})"
    return "'" + str(v).replace("'", "''") + "'"


OPS = dict(eq="=", ne="<>", lt="<", le="<=", gt=">", ge=">=", add="+", sub="-", mul="*")


class Gen:
    def __init__(self, d, env_schema):
        self.d, self.env, self.ctes, self.n = d, env_schema, [], 0

    def scalar(self, e, schema):
        d, op = self.d, e[0]
        if op == "const":
            return lit(e[1], e[2], d)
        if op == "col":
            return q(e[1])
        if op == "isnull":
            return f"({self.scalar(e[1], schema)} IS NULL)"
        if op == "cmp":
            return f"({self.scalar(e[2], schema)} {OPS[e[1]]} {self.scalar(e[3], schema)})"
        if op in ("and", "or"):
            return f"({self.scalar(e[1], schema)} {op.upper()} {self.scalar(e[2], schema)})"
        if op == "not":
            return f"(NOT {self.scalar(e[1], schema)})"
        if op == "arith":
            a, b = self.scalar(e[2], schema), self.scalar(e[3], schema)
            if e[1] == "div":
                return f"(CASE WHEN {b} = 0 THEN NULL ELSE CAST({a} AS {SQLTYPE[d][C.NUM]}) / {b} END)"
            if e[1] == "mod":
                return f"(CASE WHEN {b} = 0 THEN NULL ELSE {a} % {b} END)"
            return f"({a} {OPS[e[1]]} {b})"
        if op == "branch":
            return f"(CASE WHEN {self.scalar(e[1], schema)} THEN {self.scalar(e[2], schema)} ELSE {self.scalar(e[3], schema)} END)"
        if op == "json":
            a = self.scalar(e[1], schema)
            path = "$" + "".join("." + k for k in e[2])
            if d == "duckdb":
                return f"(CASE WHEN json_valid({a}) THEN json_extract_string({a}, '{path}') END)"
            return f"(CASE WHEN json_valid({a}) THEN CAST(json_extract({a}, '{path}') AS TEXT) END)"
        if op == "cast":
            a, t = self.scalar(e[1], schema), e[2]
            src = C.scalar_type(e[1], schema)
            if src == t:
                return a
            if src == C.STR and t == C.INT:
                if d == "duckdb":
                    return f"(CASE WHEN regexp_full_match({a}, '[+-]?[0-9]+') THEN CAST({a} AS BIGINT) END)"
                ok = f"(({a} GLOB '[0-9]*' AND {a} NOT GLOB '*[^0-9]*') OR (length({a}) > 1 AND {a} GLOB '[+-]*' AND substr({a}, 2) NOT GLOB '*[^0-9]*'))"
                return f"(CASE WHEN {ok} THEN CAST({a} AS INTEGER) END)"
            if src == C.STR and t == C.NUM:
                if d == "duckdb":
                    return f"(CASE WHEN regexp_full_match({a}, '[+-]?([0-9]+(\\.[0-9]*)?|\\.[0-9]+)') THEN CAST({a} AS DOUBLE) END)"
                raise C.Unsupported("sqlite str->num cast")
            return f"CAST({a} AS {SQLTYPE[d][t]})"
        raise C.Unsupported(f"compile scalar {op}")

    def cte(self, sql):
        self.n += 1
        name = f"t{self.n}"
        self.ctes.append(f"{name} AS ({sql})")
        return name

    def rel(self, x):
        """-> (cte name, schema)."""
        op = x[0]
        if op == "rel":
            s = C.rel_schema(x, self.env)
            return self.cte(f"SELECT {', '.join(q(n) for n, _ in s)} FROM {q(x[1])}"), s
        if op == "map":
            t, s = self.rel(x[1])
            sd = dict(s)
            return self.cte(f"SELECT {', '.join(f'{self.scalar(e, sd)} AS {q(n)}' for n, e in x[2])} FROM {t}"), C.rel_schema(x, self.env)
        if op == "filter":
            t, s = self.rel(x[1])
            return self.cte(f"SELECT * FROM {t} WHERE {self.scalar(x[2], dict(s))}"), s
        if op == "fold":
            t, s = self.rel(x[1])
            sd = dict(s)
            parts = [q(k) for k in x[2]]
            for n, agg, e in x[3]:
                if agg == "count_star":
                    parts.append(f"COUNT(*) AS {q(n)}")
                else:
                    parts.append(f"{agg.upper()}({self.scalar(e, sd)}) AS {q(n)}")
            gb = f" GROUP BY {', '.join(q(k) for k in x[2])}" if x[2] else ""
            return self.cte(f"SELECT {', '.join(parts)} FROM {t}{gb}"), C.rel_schema(x, self.env)
        if op == "rank":
            t, s = self.rel(x[1])
            sd = dict(s)
            order = [f"{self.scalar(e, sd)} {'DESC' if desc else 'ASC'} NULLS LAST" for e, desc in x[3]] + [f"{q(n)} ASC NULLS LAST" for n, _ in s]
            part = f"PARTITION BY {', '.join(q(k) for k in x[2])} " if x[2] else ""
            inner = f"SELECT *, ROW_NUMBER() OVER ({part}ORDER BY {', '.join(order)}) AS __rn FROM {t}"
            return self.cte(f"SELECT {', '.join(q(n) for n, _ in s)} FROM ({inner}) WHERE __rn <= {int(x[4])}"), s
        if op == "join":
            kind, L, R, lk, rk = x[1:]
            tl, sl = self.rel(L)
            tr, sr = self.rel(R)
            on = " AND ".join(f"l.{q(a)} = r.{q(b)}" for a, b in zip(lk, rk))
            if kind in ("semi", "anti"):
                neg = "NOT " if kind == "anti" else ""
                return self.cte(f"SELECT l.* FROM {tl} l WHERE {neg}EXISTS (SELECT 1 FROM {tr} r WHERE {on})"), sl
            rn = C.join_right_names(sl, sr)
            cols = [f"l.{q(n)} AS {q(n)}" for n, _ in sl] + [f"r.{q(n)} AS {q(m)}" for (n, _), (m, _) in zip(sr, rn)]
            j = "JOIN" if kind == "inner" else "LEFT JOIN"
            return self.cte(f"SELECT {', '.join(cols)} FROM {tl} l {j} {tr} r ON {on}"), C.rel_schema(x, self.env)
        if op == "union":
            ta, sa = self.rel(x[1])
            tb, sb = self.rel(x[2])
            cols = ", ".join(q(n) for n, _ in sa)
            return self.cte(f"SELECT {cols} FROM {ta} UNION ALL SELECT {cols} FROM {tb}"), sa
        raise C.Unsupported(f"compile relational {op}")


def compile_sql(prog, env_schema, d="duckdb", lib=None):
    x = C.expand(prog, lib or {})
    C.rel_schema(x, env_schema)
    g = Gen(d, env_schema)
    t, s = g.rel(x)
    return f"WITH {', '.join(g.ctes)} SELECT * FROM {t}", s


def _to_py(v, t, d):
    if v is None:
        return None
    if t == C.BOOL:
        return bool(v)
    if t == C.INT:
        return int(v)
    if t == C.NUM:
        return float(v)
    return v if isinstance(v, str) else str(v)


def execute(prog, env, d="duckdb", lib=None):
    """Run natively. -> Rel, or C.ERR on an engine runtime error. Raises Unsupported when the program cannot be compiled."""
    if d in NOT_IMPLEMENTED:
        raise C.Unsupported(f"{d}: native adapter not implemented in Phase 11")
    es = {k: v.schema() for k, v in env.items()}
    sql, s = compile_sql(prog, es, d, lib)
    try:
        if d == "duckdb":
            con = duckdb.connect()
            for name, R in env.items():
                con.execute(f"CREATE TABLE {q(name)} ({', '.join(f'{q(c)} {SQLTYPE[d][t]}' for c, t in R.schema())})")
                if R.rows:
                    con.executemany(f"INSERT INTO {q(name)} VALUES ({', '.join('?' for _ in R.cols)})", [list(r) for r in R.rows])
            rows = con.execute(sql).fetchall()
            con.close()
        else:
            con = sqlite3.connect(":memory:")
            for name, R in env.items():
                con.execute(f"CREATE TABLE {q(name)} ({', '.join(f'{q(c)} {SQLTYPE[d][t]}' for c, t in R.schema())})")
                if R.rows:
                    con.executemany(f"INSERT INTO {q(name)} VALUES ({', '.join('?' for _ in R.cols)})",
                                    [[(int(v) if isinstance(v, bool) else v) for v in r] for r in R.rows])
            rows = con.execute(sql).fetchall()
            con.close()
    except (duckdb.Error, sqlite3.Error, OverflowError):
        return C.ERR
    return C.Rel([n for n, _ in s], [t for _, t in s], [tuple(_to_py(v, t, d) for v, (_, t) in zip(r, s)) for r in rows])
