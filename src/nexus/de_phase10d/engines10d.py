"""Phase 10D engine lowerings and runners (NOT LOCKED): one DAG spec (ir10d) -> executable code on four engines.

  duckdb    SQL script (DuckDB 1.1.3): QUALIFY ROW_NUMBER() latest-per-key, json_extract_string, TRY_CAST; MERGE as an atomic
            upsert inside one transaction (DuckDB 1.1 has no MERGE INTO: delete / update / insert set operations)
  sqlite    SQL script (SQLite 3.50): ROW_NUMBER() subquery (no QUALIFY), CAST(json_extract(..) AS TEXT), GLOB-guarded casts,
            the same transactional upsert
  polars    Python source (Polars 2.1 LazyFrame): select / filter / with_columns, latest-per-key via rank('ordinal').over(key) (window), unique() delete keys,
            pl.col().cast(pl.Int64, strict=False), str.json_path_match, join (left / inner, expression keys), group_by().agg(),
            join_asof (by, backward / forward), the upsert as anti / semi joins + concat
  spark     Python source (PySpark 4.0.1 DataFrame API): get_json_object, try_cast, row_number().over(Window), joins, asof via
            range join + row_number, groupBy().agg(), the upsert as left_anti / left_semi joins + unionByName
gen_sql(spec, dialect) also writes the legacy dialects (snowflake / postgres / hive, with MERGE INTO) used by legacy10d."""
from __future__ import annotations

import sqlite3

import duckdb

from nexus.de_phase10d import ir10d as IR

QUALIFY = {"duckdb", "snowflake", "dbt"}
LEGACY_SQL = ("snowflake", "postgres", "hive", "dbt")       # dbt = DuckDB expressions in Jinja models + a real MERGE statement


# ------------------------------------------------------------------ SQL
def lit(v):
    return f"'{v}'" if isinstance(v, str) else ("NULL" if v is None else str(v))


def X(e, d, q=None):
    d = "duckdb" if d == "dbt" else d
    op = e[0]
    if op == "col":
        return f"{q}.{e[1]}" if q else e[1]
    if op == "lit":
        return lit(e[1])
    if op == "try_int":
        x = X(e[1], d, q)
        return {"duckdb": f"TRY_CAST(TRIM(CAST({x} AS VARCHAR)) AS INTEGER)",
                "sqlite": f"(CASE WHEN TRIM(CAST({x} AS TEXT)) <> '' AND TRIM(CAST({x} AS TEXT)) NOT GLOB '*[^0-9]*' THEN CAST(TRIM(CAST({x} AS TEXT)) AS INTEGER) END)",
                "snowflake": f"TRY_CAST({x} AS INT)", "postgres": f"CASE WHEN {x} ~ '^[0-9]+$' THEN CAST({x} AS INT) END", "hive": f"CAST({x} AS INT)"}[d]
    if op == "json":
        p, path = (f"{q}.{e[1]}" if q else e[1]), e[2]
        return {"duckdb": f"json_extract_string({p}, '$.{path}')", "sqlite": f"CAST(json_extract({p}, '$.{path}') AS TEXT)",
                "snowflake": f"JSON_EXTRACT_PATH_TEXT({p}, '{path}')", "postgres": f"JSON_EXTRACT_PATH_TEXT(CAST({p} AS JSON), {', '.join(lit(k) for k in path.split('.'))})",
                "hive": f"get_json_object({p}, '$.{path}')"}[d]
    if op == "coalesce":
        return f"COALESCE({X(e[1], d, q)}, {X(e[2], d, q)})"
    if op in ("ne", "eq"):
        return f"({X(e[1], d, q)} {'<>' if op == 'ne' else '='} {X(e[2], d, q)})"
    if op == "notnull":
        return f"({X(e[1], d, q)} IS NOT NULL)"
    raise ValueError(op)


def AGG(a, e, d, q=None):
    return f"{a.upper()}({X(e, d, q)})"


def AND(cs, d, q=None):
    return " AND ".join(X(c, d, q) for c in cs)


def sql_stg(name, t, d):
    proj = ", ".join(f"{X(x, d)} AS {n}" for n, x in t["cols"])
    inner = f"SELECT * FROM (SELECT {proj} FROM {t['src']}) AS s0 WHERE {AND(t['pre'], d)}" if t.get("pre") else f"SELECT {proj} FROM {t['src']}"
    names = ", ".join(n for n, _ in t["cols"])
    if t.get("dedup"):
        k, o = X(t["dedup"]["key"], d), X(t["dedup"]["order"], d)
        dr = "DESC" if t["dedup"].get("desc", True) else "ASC"
        if d in QUALIFY:
            ded = f"SELECT * FROM ({inner}) AS p QUALIFY ROW_NUMBER() OVER (PARTITION BY {k} ORDER BY {o} {dr}) = 1"
        else:
            ded = f"SELECT {names} FROM (SELECT p.*, ROW_NUMBER() OVER (PARTITION BY {k} ORDER BY {o} {dr}) AS rn__ FROM ({inner}) AS p) AS q WHERE rn__ = 1"
    else:
        ded = inner
    post = f" WHERE {AND(t['post'], d)}" if t.get("post") else ""
    if t.get("latest_as"):
        return [f"CREATE TABLE {t['latest_as']} AS {ded}", f"CREATE TABLE {name} AS SELECT * FROM {t['latest_as']}{post}"]
    return [f"CREATE TABLE {name} AS SELECT * FROM ({ded}) AS d{post}" if post else f"CREATE TABLE {name} AS {ded}"]


def sql_int(s, d):
    sel = [f"b.{c} AS {c}" for c in s["base_cols"]]
    frm = f"{s['base']} AS b"
    for k, j in enumerate(s["joins"]):
        a = f"j{k}"
        if j["how"] == "asof":
            cmp = "<=" if j.get("strategy", "backward") == "backward" else ">="
            order = "DESC" if cmp == "<=" else "ASC"
            for o, c in j["take"]:
                sel.append(f"(SELECT r.{c} FROM {j['rel']} AS r WHERE r.{j['by'][1]} = b.{j['by'][0]} AND {X(j['rkey'], d, 'r')} {cmp} {X(j['lkey'], d, 'b')} "
                           f"ORDER BY {X(j['rkey'], d, 'r')} {order} LIMIT 1) AS {o}")
            continue
        if j.get("agg"):
            g = j["agg"]
            rel = f"(SELECT {g['by']}, " + ", ".join(f"{AGG(ag, x, d)} AS {m}" for m, ag, x in g["measures"]) + f" FROM {j['rel']} GROUP BY {g['by']})"
        else:
            rel = j["rel"]
        frm += f" {'LEFT JOIN' if j['how'] == 'left' else 'INNER JOIN'} {rel} AS {a} ON {X(j['lkey'], d, 'b')} = {X(j['rkey'], d, a)}"
        sel += [f"{a}.{c} AS {o}" for o, c in j["take"]]
    out = ", ".join(f"{X(x, d)} AS {n}" for n, x in s["out"])
    return [f"CREATE TABLE int_orders AS SELECT {out} FROM (SELECT {', '.join(sel)} FROM {frm}) AS x"]


def fct_names(f):
    return [n for n, _ in f["group"]] + [n for n, _, _ in f["measures"]]


def sql_fct(f, d):
    g = ", ".join(f"{X(x, d)} AS {n}" for n, x in f["group"])
    ms = ", ".join(f"{AGG(a, x, d)} AS {n}" for n, a, x in f["measures"])
    st = [f"CREATE TABLE fct_src AS SELECT {g}, {ms} FROM {f['src']} GROUP BY {', '.join(X(x, d) for _, x in f['group'])}"]
    m = f.get("merge")
    if not m:
        return st + ["CREATE TABLE fct_out AS SELECT * FROM fct_src"]
    names = fct_names(f)
    k = m["key"]
    dl = m.get("deletes")
    dsel = (f"SELECT {X(dl['key'], d)} AS k FROM {dl['rel']} WHERE {X(dl['key'], d)} NOT IN (SELECT {X(dl['key'], d)} FROM {dl['minus']} "
            f"WHERE {X(dl['key'], d)} IS NOT NULL)") if dl else "SELECT NULL AS k WHERE 1 = 0"
    if d in LEGACY_SQL:                                            # legacy text: a real MERGE INTO statement
        cols = ", ".join(names)
        st.append(f"CREATE TABLE merge_src AS SELECT {cols}, 'u' AS op FROM fct_src WHERE {k} NOT IN (SELECT k FROM ({dsel}) AS dk WHERE k IS NOT NULL) "
                  f"UNION ALL SELECT k AS {k}, " + ", ".join("NULL" for _ in names[1:]) + f", 'd' AS op FROM ({dsel}) AS dk WHERE k IS NOT NULL")
        whens = []
        if m["delete"]:
            whens.append("WHEN MATCHED AND s.op = 'd' THEN DELETE")
        if m["update"]:
            whens.append("WHEN MATCHED THEN UPDATE SET " + ", ".join(f"{n} = s.{n}" for n in names if n != k))
        whens.append(f"WHEN NOT MATCHED AND s.op <> 'd' THEN INSERT ({cols}) VALUES ({', '.join('s.' + n for n in names)})")
        return st + [f"MERGE INTO fct_target AS t USING merge_src AS s ON t.{k} = s.{k} " + " ".join(whens)]
    D = f"(SELECT k FROM ({dsel}) AS dk WHERE k IS NOT NULL)"
    S = f"(SELECT * FROM fct_src WHERE {k} IS NOT NULL AND {k} NOT IN {D})"
    cols = ", ".join(names)
    parts = [f"SELECT {cols} FROM fct_target WHERE {k} NOT IN (SELECT {k} FROM {S} AS s0) AND {k} NOT IN {D}"]
    parts.append(f"SELECT {cols} FROM {S} AS s1 WHERE {k} IN (SELECT {k} FROM fct_target)" if m["update"] else
                 f"SELECT {cols} FROM fct_target WHERE {k} IN (SELECT {k} FROM {S} AS s1)")
    parts.append(f"SELECT {cols} FROM {S} AS s2 WHERE {k} NOT IN (SELECT {k} FROM fct_target)")
    if not m["delete"]:
        parts.append(f"SELECT {k}, " + ", ".join("NULL" for _ in names[1:]) + f" FROM fct_target WHERE {k} IN {D}" if m["update"] else
                     f"SELECT {cols} FROM fct_target WHERE {k} IN {D}")
    return st + ["BEGIN TRANSACTION", f"CREATE TABLE fct_out AS " + " UNION ALL ".join(parts), "COMMIT"]


def gen_sql(spec, d):
    out = []
    for name in sorted(spec["stg"]):
        out += sql_stg(name, spec["stg"][name], d)
    return out + sql_int(spec["int"], d) + sql_fct(spec["fct"], d)


def node_sql(spec, d):
    """Statements grouped by DAG node (legacy files / dbt models are written per node)."""
    return dict(stg=[s for name in sorted(spec["stg"]) for s in sql_stg(name, spec["stg"][name], d)], int=sql_int(spec["int"], d), fct=sql_fct(spec["fct"], d))


def _load_sql(con, tables, state, f, kind):
    for name, rows in tables.items():
        cols = list(rows[0].keys())
        con.execute(f"CREATE TABLE {name} ({', '.join(c + (' VARCHAR' if kind == 'duckdb' else ' TEXT') for c in cols)})")
        con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' for _ in cols)})", [[r.get(c) for c in cols] for r in rows])
    names = fct_names(f)
    con.execute(f"CREATE TABLE fct_target ({', '.join(n + (' BIGINT' if kind == 'duckdb' else ' INTEGER') for n in names)})")
    tg = state.get("fct_target", [])
    if tg:
        con.executemany(f"INSERT INTO fct_target VALUES ({', '.join('?' for _ in names)})", [[r.get(n) for n in names] for r in tg])


def run_sql(spec, tables, state, kind, rels):
    con = duckdb.connect() if kind == "duckdb" else sqlite3.connect(":memory:", isolation_level=None)
    try:
        _load_sql(con, tables, state, spec["fct"], kind)
        for s in gen_sql(spec, kind):
            con.execute(s)
        out = {}
        for r in rels:
            cur = con.execute(f"SELECT * FROM {r}")
            cols = [c[0] for c in cur.description]
            out[r] = [dict(zip(cols, row)) for row in cur.fetchall()]
        return out
    finally:
        con.close()


# ------------------------------------------------------------------ Polars
def PX(e):
    op = e[0]
    if op == "col":
        return f"pl.col({e[1]!r})"
    if op == "lit":
        return f"pl.lit({e[1]!r})"
    if op == "try_int":
        return f"({PX(e[1])}).cast(pl.Utf8).str.strip_chars().cast(pl.Int64, strict=False)"
    if op == "json":
        return f"pl.col({e[1]!r}).str.json_path_match('$.{e[2]}')"
    if op == "coalesce":
        return f"pl.coalesce([{PX(e[1])}, {PX(e[2])}])"
    if op in ("ne", "eq"):
        return f"(({PX(e[1])}) {'!=' if op == 'ne' else '=='} ({PX(e[2])}))"
    if op == "notnull":
        return f"({PX(e[1])}).is_not_null()"
    raise ValueError(op)


def PAGG(a, e):
    x = PX(e)
    if a == "sum":
        return f"pl.when(({x}).count() > 0).then(({x}).sum()).otherwise(None)"
    return f"({x}).count()" if a == "count" else f"({x}).max()"


def gen_polars(spec):
    L = ["import polars as pl", "", "", "def run(T, S):", "    R = {}"]
    for name in sorted(spec["stg"]):
        t = spec["stg"][name]
        L.append(f"    df = T[{t['src']!r}].lazy().select([{', '.join(f'({PX(x)}).alias({n!r})' for n, x in t['cols'])}])")
        for c in t.get("pre", []):
            L.append(f"    df = df.filter({PX(c)})")
        if t.get("dedup"):
            L.append(f"    df = df.with_columns(({PX(t['dedup']['key'])}).alias('__k'), ({PX(t['dedup']['order'])}).alias('__o'))"
                     f".filter(pl.col('__o').rank('ordinal', descending={t['dedup'].get('desc', True)!r}).over('__k') == 1).drop(['__k', '__o'])")
        if t.get("latest_as"):
            L.append(f"    R[{t['latest_as']!r}] = df.collect()")
        for c in t.get("post", []):
            L.append(f"    df = df.filter({PX(c)})")
        L.append(f"    R[{name!r}] = df.collect()")
    s = spec["int"]
    L.append(f"    b = R[{s['base']!r}].lazy().select({s['base_cols']!r})")
    for k, j in enumerate(s["joins"]):
        L.append(f"    r = R[{j['rel']!r}].lazy()")
        if j.get("agg"):
            L.append(f"    r = r.group_by({j['agg']['by']!r}).agg([{', '.join(f'({PAGG(a, x)}).alias({m!r})' for m, a, x in j['agg']['measures'])}])")
        ren = ", ".join(f"pl.col({c!r}).alias({o!r})" for o, c in j["take"])
        if j["how"] == "asof":
            L.append(f"    r = r.select([({PX(j['rkey'])}).alias('__rk'), pl.col({j['by'][1]!r}).alias('__by'), {ren}]).filter(pl.col('__rk').is_not_null()).sort('__rk')")
            L.append(f"    b = b.with_columns(({PX(j['lkey'])}).alias('__lk')).sort('__lk').join_asof(r, left_on='__lk', right_on='__rk', by_left={j['by'][0]!r}, "
                     f"by_right='__by', strategy={j.get('strategy', 'backward')!r}).drop(['__lk', '__rk'], strict=False)")
        else:
            L.append(f"    r = r.select([({PX(j['rkey'])}).alias('__rk'), {ren}])")
            L.append(f"    b = b.with_columns(({PX(j['lkey'])}).alias('__lk')).join(r, left_on='__lk', right_on='__rk', how={j['how']!r}).drop(['__lk', '__rk'], strict=False)")
    L.append(f"    R['int_orders'] = b.select([{', '.join(f'({PX(x)}).alias({n!r})' for n, x in s['out'])}]).collect()")
    f = spec["fct"]
    L.append(f"    g = R[{f['src']!r}].lazy().with_columns([{', '.join(f'({PX(x)}).alias({n!r})' for n, x in f['group'])}])")
    L.append(f"    src = g.group_by({[n for n, _ in f['group']]!r}).agg([{', '.join(f'({PAGG(a, x)}).alias({n!r})' for n, a, x in f['measures'])}]).collect()")
    L.append("    R['fct_src'] = src")
    m = f.get("merge")
    if not m:
        L.append("    R['fct_out'] = src")
    else:
        names, k = fct_names(f), m["key"]
        L.append(f"    T0 = pl.DataFrame({{n: [r.get(n) for r in S.get('fct_target', [])] for n in {names!r}}}, schema={{n: pl.Int64 for n in {names!r}}})")
        if m.get("deletes"):
            dl = m["deletes"]
            L.append(f"    act = R[{dl['minus']!r}].select(({PX(dl['key'])}).alias('k')).drop_nulls()['k'].to_list()")
            L.append(f"    D = R[{dl['rel']!r}].select(({PX(dl['key'])}).alias('k')).drop_nulls().unique().filter(~pl.col('k').is_in(act))['k'].to_list()")
        else:
            L.append("    D = []")
        L.append(f"    Sx = src.filter(pl.col({k!r}).is_not_null() & ~pl.col({k!r}).is_in(D)).select({names!r})")
        L.append(f"    tk, sk = T0[{k!r}].to_list(), Sx[{k!r}].to_list()")
        L.append(f"    parts = [T0.filter(~pl.col({k!r}).is_in(sk) & ~pl.col({k!r}).is_in(D))]")
        L.append(f"    parts.append(Sx.filter(pl.col({k!r}).is_in(tk)) if {m['update']!r} else T0.filter(pl.col({k!r}).is_in(sk)))")
        L.append(f"    parts.append(Sx.filter(~pl.col({k!r}).is_in(tk)))")
        if not m["delete"]:
            nul = ", ".join(f"pl.lit(None, dtype=pl.Int64).alias({n!r})" for n in names[1:])
            L.append(f"    parts.append(T0.filter(pl.col({k!r}).is_in(D)).select([pl.col({k!r}), {nul}]) if {m['update']!r} else T0.filter(pl.col({k!r}).is_in(D)))")
        L.append("    R['fct_out'] = pl.concat([p.select(%r).cast({n: pl.Int64 for n in %r}, strict=False) for p in parts], how='vertical_relaxed')" % (names, names))
    L.append("    return R")
    return "\n".join(L) + "\n"


def run_polars(spec, tables, state, rels, code=None):
    import warnings
    import polars as pl
    warnings.filterwarnings("ignore", message="Sortedness of columns cannot be checked")
    ns = {}
    exec(code or gen_polars(spec), ns)                     # noqa: S102  (our own generated code)
    T = {n: pl.DataFrame({c: [r.get(c) for r in rows] for c in rows[0]}, schema={c: pl.Utf8 for c in rows[0]}) for n, rows in tables.items()}
    R = ns["run"](T, state)
    return {r: R[r].to_dicts() for r in rels}


# ------------------------------------------------------------------ PySpark
def SX(e):
    op = e[0]
    if op == "col":
        return f"F.col({e[1]!r})"
    if op == "lit":
        return f"F.lit({e[1]!r})"
    if op == "try_int":
        return f"F.trim(({SX(e[1])}).cast('string')).try_cast('int')"
    if op == "json":
        return f"F.get_json_object(F.col({e[1]!r}), '$.{e[2]}')"
    if op == "coalesce":
        return f"F.coalesce({SX(e[1])}, {SX(e[2])})"
    if op in ("ne", "eq"):
        return f"(({SX(e[1])}) {'!=' if op == 'ne' else '=='} ({SX(e[2])}))"
    if op == "notnull":
        return f"({SX(e[1])}).isNotNull()"
    raise ValueError(op)


def SAGG(a, e):
    return f"F.{a}({SX(e)})"


def gen_spark(spec):
    L = ["from pyspark.sql import functions as F", "from pyspark.sql.window import Window", "", "", "def run(spark, T, S):", "    R = {}"]
    for name in sorted(spec["stg"]):
        t = spec["stg"][name]
        L.append(f"    df = T[{t['src']!r}].select({', '.join(f'({SX(x)}).alias({n!r})' for n, x in t['cols'])})")
        for c in t.get("pre", []):
            L.append(f"    df = df.filter({SX(c)})")
        if t.get("dedup"):
            L.append(f"    w = Window.partitionBy({SX(t['dedup']['key'])}).orderBy(({SX(t['dedup']['order'])}).{'desc' if t['dedup'].get('desc', True) else 'asc'}_nulls_last())")
            L.append("    df = df.withColumn('__rn', F.row_number().over(w)).filter(F.col('__rn') == 1).drop('__rn')")
        if t.get("latest_as"):
            L.append(f"    R[{t['latest_as']!r}] = df")
        for c in t.get("post", []):
            L.append(f"    df = df.filter({SX(c)})")
        L.append(f"    R[{name!r}] = df")
    s = spec["int"]
    L.append(f"    b = R[{s['base']!r}].select({', '.join(repr(c) for c in s['base_cols'])}).withColumn('__id', F.monotonically_increasing_id())")
    for k, j in enumerate(s["joins"]):
        L.append(f"    r = R[{j['rel']!r}]")
        if j.get("agg"):
            L.append(f"    r = r.groupBy({j['agg']['by']!r}).agg({', '.join(f'({SAGG(a, x)}).alias({m!r})' for m, a, x in j['agg']['measures'])})")
        ren = ", ".join(f"F.col({c!r}).alias({o!r})" for o, c in j["take"])
        if j["how"] == "asof":
            cmp = "<=" if j.get("strategy", "backward") == "backward" else ">="
            L.append(f"    r = r.select(({SX(j['rkey'])}).alias('__rk'), F.col({j['by'][1]!r}).alias('__by'), {ren})")
            L.append(f"    b = b.withColumn('__lk', {SX(j['lkey'])}).withColumn('__id', F.monotonically_increasing_id())")
            L.append(f"    m = b.join(r, (b[{j['by'][0]!r}] == r['__by']) & (r['__rk'] {cmp} b['__lk']), 'left')")
            L.append(f"    w = Window.partitionBy('__id').orderBy(F.col('__rk').{'desc' if cmp == '<=' else 'asc'}_nulls_last())")
            L.append("    b = m.withColumn('__rn', F.row_number().over(w)).filter(F.col('__rn') == 1).drop('__rn', '__lk', '__rk', '__by')")
        else:
            L.append(f"    r = r.select(({SX(j['rkey'])}).alias('__rk'), {ren})")
            L.append(f"    b = b.withColumn('__lk', {SX(j['lkey'])})")
            L.append(f"    b = b.join(r, b['__lk'] == r['__rk'], {j['how']!r}).drop('__lk', '__rk')")
    L.append(f"    R['int_orders'] = b.select({', '.join(f'({SX(x)}).alias({n!r})' for n, x in s['out'])})")
    f = spec["fct"]
    gn = [n for n, _ in f["group"]]
    L.append(f"    g = R[{f['src']!r}]" + "".join(f".withColumn({n!r}, {SX(x)})" for n, x in f["group"]))
    L.append(f"    src = g.groupBy({', '.join(repr(n) for n in gn)}).agg({', '.join(f'({SAGG(a, x)}).alias({n!r})' for n, a, x in f['measures'])})")
    L.append("    R['fct_src'] = src")
    m = f.get("merge")
    if not m:
        L.append("    R['fct_out'] = src")
    else:
        names, k = fct_names(f), m["key"]
        L.append(f"    T0 = spark.createDataFrame([tuple(r.get(n) for n in {names!r}) for r in S.get('fct_target', [])], "
                 f"{', '.join(n + ' long' for n in names)!r})")
        if m.get("deletes"):
            dl = m["deletes"]
            L.append(f"    act = R[{dl['minus']!r}].select(({SX(dl['key'])}).cast('long').alias({k!r})).na.drop()")
            L.append(f"    D = R[{dl['rel']!r}].select(({SX(dl['key'])}).cast('long').alias({k!r})).na.drop().distinct().join(act, {k!r}, 'left_anti')")
        else:
            L.append(f"    D = spark.createDataFrame([], '{k} long')")
        L.append(f"    Sx = src.select(*[F.col(n).cast('long').alias(n) for n in {names!r}]).filter(F.col({k!r}).isNotNull()).join(D, {k!r}, 'left_anti')")
        L.append(f"    parts = [T0.join(Sx.select({k!r}), {k!r}, 'left_anti').join(D, {k!r}, 'left_anti')]")
        L.append(f"    parts.append(Sx.join(T0.select({k!r}), {k!r}, 'left_semi') if {m['update']!r} else T0.join(Sx.select({k!r}), {k!r}, 'left_semi'))")
        L.append(f"    parts.append(Sx.join(T0.select({k!r}), {k!r}, 'left_anti'))")
        if not m["delete"]:
            nul = ", ".join(f"F.lit(None).cast('long').alias({n!r})" for n in names[1:])
            L.append(f"    parts.append(T0.join(D, {k!r}, 'left_semi').select(F.col({k!r}), {nul}) if {m['update']!r} else T0.join(D, {k!r}, 'left_semi'))")
        L.append(f"    out = parts[0].select(*{names!r})")
        L.append(f"    for p in parts[1:]:\n        out = out.unionByName(p.select(*{names!r}))")
        L.append("    R['fct_out'] = out")
    L.append("    return R")
    return "\n".join(L) + "\n"


def spark():
    """The shared local SparkSession of de_phase4.world.SparkCode (JAVA_HOME = Homebrew OpenJDK 17, localhost binding, ANSI mode
    on, 1 shuffle partition) - one per worker process."""
    from nexus.de_phase4 import world as W4
    return W4.SparkCode.session()


def run_spark(spec, tables, state, rels, code=None):
    ss = spark()
    ns = {}
    exec(code or gen_spark(spec), ns)                      # noqa: S102  (our own generated code)
    from pyspark.sql.types import StringType, StructField, StructType
    T = {n: ss.createDataFrame([tuple(r.get(c) for c in rows[0]) for r in rows], StructType([StructField(c, StringType()) for c in rows[0]])) for n, rows in tables.items()}
    R = ns["run"](ss, T, state)
    return {r: [x.asDict() for x in R[r].collect()] for r in rels}


def run(spec, tables, state, engine, rels):
    if engine in ("duckdb", "sqlite"):
        return run_sql(spec, tables, state, engine, rels)
    if engine == "polars":
        return run_polars(spec, tables, state, rels)
    if engine == "spark":
        return run_spark(spec, tables, state, rels)
    if engine == "ref":
        R = IR.interpret(spec, tables, state)
        return {r: R[r] for r in rels}
    raise ValueError(engine)
