"""Phase 10E general external loader + multi-table input binder (NOT LOCKED; task-agnostic, no per-task rule).

Takes practitioner text AS WRITTEN (SQL in a named dialect, dbt Jinja, PySpark, Polars, Scala Spark) plus the provided input
tables, and produces the stage IR of de_phase6.ir6 (frozen) - or a typed failure saying which funnel stage stopped it.

  load(text, lang, tables) -> Loaded(ok, stage, error, stages=[spec, ...], inputs, input_rows, header, notes)
    stage  'parse'      the text does not parse in its language
           'bind'       a relation it reads is not a provided table
           'express'    it parses and binds, but some construct has no IR form (MERGE, JSON paths, CASE, MIN, COUNT(col) ...)
           'ok'         lifted; `stages` is a 1- or 2-stage pipeline over `input_rows`

GENERAL RULES (each applies to any text of its kind; the notes list which fired):
  SQL   R1 dbt rendering: ref(x) -> x, source(s, x) -> x, config(..) -> '', var(x, d) -> d, is_incremental() -> false
        R2 the LAST statement is the model; a bare SELECT / WITH is its output (dbt convention); CREATE TABLE AS uses its query
        R3 CTEs referenced once are inlined (sqlglot), so a WITH chain over one input reaches the stage form
        R4 input binding: every base relation must be a provided table. ONE base table -> it is the stage input `raw` (any
           name, any alias; column qualifiers are dropped). SEVERAL -> the MULTI-TABLE BINDER: the FROM / JOIN clause is
           materialised as the stage input by DuckDB over the provided tables (columns `alias__col`, references rewritten),
           and the SELECT list / WHERE / GROUP BY is lifted over it
        R5 unaliased output columns are aliased by their column name; COUNT(*) -> SUM(1) (exact)
        R6 QUALIFY ROW_NUMBER() OVER (PARTITION BY k ORDER BY o [ASC|DESC]) = 1, a ROW_NUMBER derived table with any alias /
           filter column name, and DISTINCT ON (k) .. ORDER BY k, o -> the IR dedup (latest per key). The IR orders DESC only:
           an ASC order on a column whose visible values are all integers is read as DESC on (0 - CAST(o AS INT)) (exact for
           integers; disclosed)
        R7 a WHERE evaluated before a dedup (filter-then-dedup) becomes a 2-stage pipeline (filter stage, then dedup stage)
  PySpark  top-level statements are wrapped into run(spark, raw, state); the free DataFrame name is bound to the input;
        dropDuplicates([k]) -> first row per key by landing order; select('a', ...) -> aliased columns; the last assigned
        DataFrame is `clean`
  Polars   a chain on the free DataFrame name: filter(expr), unique(subset=[k], keep='first'|'last'|'any'), select(..)
           (pl.col / pl.lit / != == > >= < <= & |); filter-then-unique -> 2 stages
  Scala    the free DataFrame name of the first chain is bound to the input (ir6.lift_scala requires it to be `raw`)"""
from __future__ import annotations

import ast
import copy
import json
import re
from dataclasses import dataclass, field

import duckdb
import jinja2
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.eliminate_ctes import eliminate_ctes  # noqa: F401
from sqlglot.optimizer.merge_subqueries import merge_subqueries  # noqa: F401

from nexus.de_phase4 import adapter as AD
from nexus.de_phase6 import ir6

DIALECT = {"sql": "sqlite", "postgres": "postgres", "snowflake": "snowflake", "hive": "hive", "j2": "postgres", "duckdb": "duckdb"}


@dataclass
class Loaded:
    ok: bool
    stage: str
    error: str | None = None
    stages: list = field(default_factory=list)
    input_rows: list = field(default_factory=list)
    header: list = field(default_factory=list)
    inputs: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def _fail(stage, err, notes, inputs=()):
    return Loaded(False, stage, err, notes=list(notes), inputs=list(inputs))


# ------------------------------------------------------------------ SQL
def render_dbt(text):
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    return env.from_string(text).render(ref=lambda *a: a[-1], source=lambda s, t: t, config=lambda *a, **k: "", var=lambda n, d=None: d,
                                        is_incremental=lambda: False, this="this")


def _base_tables(tree):
    ctes = {c.alias for c in tree.find_all(exp.CTE)}
    return sorted({t.name for t in tree.find_all(exp.Table) if t.name not in ctes})


def _inline_ctes(sel):
    """R3: inline every CTE as a derived table (sqlglot), then merge simple subqueries."""
    w = sel.args.get("with")
    if not w:
        return sel
    defs = {c.alias: c.this for c in w.expressions}
    sel = sel.copy()
    sel.set("with", None)
    for t in list(sel.find_all(exp.Table)):
        if t.name in defs:
            t.replace(exp.Subquery(this=defs[t.name].copy(), alias=exp.TableAlias(this=exp.to_identifier(t.alias_or_name))))
    try:
        sel = merge_subqueries(sel)
    except Exception:                                             # noqa: BLE001
        pass
    return sel


def _alias_outputs(sel, notes):
    out = []
    for e in sel.expressions:
        if isinstance(e, exp.Alias) or isinstance(e, exp.Star):
            out.append(e)
        elif isinstance(e, exp.Column):
            out.append(exp.alias_(e, e.name, quoted=False))
            notes.add("R5 alias")
        else:
            out.append(e)
    sel.set("expressions", out)


def _count_star(sel, notes):
    for c in list(sel.find_all(exp.Count)):
        if isinstance(c.this, exp.Star):
            c.replace(exp.Sum(this=exp.Literal.number(1)))
            notes.add("R5 count(*)")


def _int_col(rows, col):
    vals = [r.get(col) for r in rows if r.get(col) not in (None, "")]
    return bool(vals) and all(re.fullmatch(r"-?[0-9]+", str(v)) for v in vals)


def _order_desc(o, rows, notes):
    """IR dedup order: DESC expression (R6)."""
    x = o.this
    if o.args.get("desc"):
        return x
    col = x.name if isinstance(x, exp.Column) else None
    if col and _int_col(rows, col):
        notes.add("R6 asc->desc(0-int)")
        return exp.Sub(this=exp.Literal.number(0), expression=exp.Cast(this=x.copy(), to=exp.DataType.build("int")))
    raise AD.Unsupported("ascending dedup order on a non-integer column")


def _window_dedup(win):
    if not (isinstance(win, exp.Window) and isinstance(win.this, exp.RowNumber) and win.args.get("partition_by") and win.args.get("order")):
        return None
    return win.args["partition_by"][0], win.args["order"].expressions[0]


def _strip_qualifiers(node):
    for c in node.find_all(exp.Column):
        if c.table:
            c.set("table", None)
    return node


def _lift_stage(sel, rows, notes):
    """One SELECT over `raw` (after R5-R7) -> list of IR stage specs."""
    filt, ded = sel.args.get("where"), None
    src = sel.args["from"].this
    if isinstance(src, exp.Subquery) and isinstance(src.this, exp.Select):       # R6 derived-table ROW_NUMBER form
        inner = src.this
        rn = next((a for a in inner.expressions if isinstance(a, exp.Alias) and _window_dedup(a.this)), None)
        if rn is not None and filt is not None:
            k, o = _window_dedup(rn.this)
            ded = (k, o)
            notes.add("R6 row_number derived table")
            filt = inner.args.get("where")
            src = inner.args["from"].this
    q = sel.args.get("qualify")
    if q is not None:
        cond = q.this
        win = cond.this if isinstance(cond, exp.EQ) else None
        if win is None or _window_dedup(win) is None:
            raise AD.Unsupported("QUALIFY other than ROW_NUMBER() = 1")
        ded = _window_dedup(win)
        notes.add("R6 qualify")
    don = sel.args.get("distinct")
    if don is not None and don.args.get("on") is not None:
        k = don.args["on"].expressions[0]
        orders = [o for o in sel.args["order"].expressions if not (isinstance(o.this, exp.Column) and o.this.name == getattr(k, "name", None))]
        ded = (k, orders[0])
        notes.add("R6 distinct on")
    if not (isinstance(src, exp.Table) and src.name == "raw"):
        raise AD.Unsupported(f"FROM {type(src).__name__}")
    outs = sel.copy()
    for a in ("where", "qualify", "distinct", "order"):
        outs.set(a, None)
    outs.set("from", exp.From(this=exp.to_table("src__")))
    _alias_outputs(outs, notes)
    _count_star(outs, notes)
    for agg in outs.find_all(exp.AggFunc):
        if not isinstance(agg, exp.Sum):
            raise AD.Unsupported(f"aggregate {agg.key.upper()} (the IR aggregates SUM only)")
    pre = f" WHERE {filt.this.sql(dialect='sqlite')}" if filt is not None else ""
    stages = []
    if ded is not None:
        k, o = ded
        dd = f"SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY {k.sql(dialect='sqlite')} ORDER BY {_order_desc(o, rows, notes).sql(dialect='sqlite')} DESC) AS __rn FROM {{src}}) WHERE __rn = 1"
        if pre:
            notes.add("R7 filter-then-dedup -> 2 stages")
            stages.append(f"CREATE TABLE clean AS SELECT * FROM raw{pre};")
            pre = ""
        body = re.sub(r"\bsrc__\b", "dd", outs.sql(dialect="sqlite"))
        stages.append(f"CREATE VIEW dd AS {dd.format(src='raw')};\nCREATE TABLE clean AS {body};")
    else:
        body = re.sub(r"\bsrc__\b", "raw", outs.sql(dialect="sqlite"))
        stages.append(f"CREATE TABLE clean AS {body}{pre};")
    specs = []
    for s in stages:
        if s.startswith("CREATE TABLE clean AS SELECT * FROM raw"):
            specs.append(dict(outputs=[[c, ["col", c]] for c in (rows[0] if rows else {})], filter=AD.lift_sql(s.replace("SELECT *", "SELECT " + ", ".join(f"{c} AS {c}" for c in rows[0])))["filter"]))
        else:
            specs.append(ir6.norm_spec(AD.lift_sql(s)))
    return specs


def _bind_multi(sel, tables, notes):
    """R4 multi-table binder: materialise the FROM / JOIN clause over the provided tables -> (rows, rewritten select)."""
    aliases = {}
    for t in sel.find_all(exp.Table):
        aliases[t.alias_or_name] = t.name
    con = duckdb.connect()
    for name, rs in tables.items():
        cols = list(rs[0].keys())
        con.execute(f'create table "{name}" ({", ".join(chr(34) + c + chr(34) + " varchar" for c in cols)})')
        con.executemany(f'insert into "{name}" values ({", ".join("?" for _ in cols)})', [[r[c] for c in cols] for r in rs])
    owners = {}
    for a, n in aliases.items():
        for c in tables[n][0]:
            owners.setdefault(c, []).append(a)
    proj = ", ".join(f'"{a}"."{c}" AS "{a}__{c}"' for a, n in aliases.items() for c in tables[n][0])
    frm = sel.args["from"].sql(dialect="duckdb") + " " + " ".join(j.sql(dialect="duckdb") for j in sel.args.get("joins") or [])
    cur = con.execute(f"SELECT {proj} {frm}")
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, ["" if v is None else str(v) for v in r])) for r in cur.fetchall()]
    out = sel.copy()
    out.set("joins", None)
    out.set("from", exp.From(this=exp.to_table("raw")))
    for c in list(out.find_all(exp.Column)):
        a = c.table or (owners.get(c.name, [None])[0] if len(owners.get(c.name, [])) == 1 else None)
        if a is None:
            raise AD.Unsupported(f"ambiguous column {c.name}")
        c.replace(exp.column(f"{a}__{c.name}"))
    notes.add("R4 multi-table binder")
    return rows, out


def load_sql(text, lang, tables):
    notes = set()
    if lang == "j2":
        try:
            text = render_dbt(text)
            notes.add("R1 dbt")
        except Exception as e:                                    # noqa: BLE001
            return _fail("parse", f"jinja: {e}", notes)
    try:
        stmts = [s for s in sqlglot.parse(text, read=DIALECT[lang]) if s is not None]
    except Exception as e:                                        # noqa: BLE001
        return _fail("parse", str(e)[:120], notes)
    if not stmts:
        return _fail("parse", "empty", notes)
    s = stmts[-1]
    if isinstance(s, exp.Create) and isinstance(s.expression, (exp.Select, exp.With)):
        s = s.expression
    base = _base_tables(s)
    missing = [b for b in base if b not in tables]
    if isinstance(s, exp.Merge):
        src = s.args.get("using")
        bound = [t.name for t in (src.find_all(exp.Table) if src is not None else [])]
        if any(b not in tables for b in bound):
            return _fail("bind", f"MERGE source not provided: {bound}", notes, bound)
        return _fail("express", "MERGE (no IR construct for an upsert into a target state)", notes | {"R2 merge source bound"}, bound)
    if not isinstance(s, exp.Select):
        return _fail("express", f"statement {type(s).__name__}", notes, base)
    if missing:
        return _fail("bind", f"relations not provided: {missing}", notes, base)
    notes.add("R2 model statement")
    try:
        sel = _inline_ctes(s)
        if sel is not s:
            notes.add("R3 cte")
        base = _base_tables(sel)
        if len(base) == 1 and not list(sel.find_all(exp.Subquery)) or (len(base) == 1 and _single_chain(sel)):
            for t in sel.find_all(exp.Table):
                if t.name == base[0]:
                    t.replace(exp.to_table("raw"))
            _strip_qualifiers(sel)
            rows = tables[base[0]]
            notes.add("R4 single input")
        else:
            if any(isinstance(x, exp.Subquery) for x in sel.find_all(exp.Subquery)) and len(base) > 1:
                rows, sel = _bind_multi_ctes(sel, tables, notes)
            else:
                rows, sel = _bind_multi(sel, tables, notes)
        stages = _lift_stage(sel, rows, notes)
    except AD.Unsupported as e:
        return _fail("express", str(e)[:140], notes, base)
    except Exception as e:                                        # noqa: BLE001
        return _fail("express", f"{type(e).__name__}: {str(e)[:120]}", notes, base)
    return Loaded(True, "ok", None, stages, rows, list(rows[0].keys()) if rows else [], base, sorted(notes))


def _single_chain(sel):
    """One base table reached through nested derived tables only (no join)."""
    return not sel.args.get("joins") and all(not s.args.get("joins") for s in sel.find_all(exp.Select))


def _bind_multi_ctes(sel, tables, notes):
    """Several inputs combined through derived tables (e.g. aggregated CTEs joined together): the derived tables would have to be
    materialised as separate stages, which a linear stage pipeline cannot hold."""
    raise AD.Unsupported("joins over derived (aggregated) inputs: a linear stage pipeline holds one input per stage")


# ------------------------------------------------------------------ PySpark
def _free_names(mod, defined=("F", "Window", "spark", "state", "pl", "col", "lit", "when")):
    assigned, free = set(), []
    for s in mod.body:
        if isinstance(s, ast.Assign):
            for n in ast.walk(s.value):
                if isinstance(n, ast.Name) and n.id not in assigned and n.id not in defined and n.id not in free:
                    base = n
                    free.append(base.id)
            for t in s.targets:
                if isinstance(t, ast.Name):
                    assigned.add(t.id)
    return free, assigned


def load_py(text, tables):
    notes = set()
    try:
        mod = ast.parse(text)
    except SyntaxError as e:
        return _fail("parse", str(e)[:120], notes)
    if any(isinstance(s, ast.FunctionDef) and s.name == "run" for s in mod.body):
        src = text
    else:
        free, assigned = _free_names(mod)
        dfs = [f for f in free if f in tables]
        if len(dfs) != 1 or any(f not in tables for f in free):
            return _fail("bind", f"free names {free} vs provided {sorted(tables)}", notes, free)
        notes.add("PY bind free DataFrame")
        lines = ["from pyspark.sql import functions as F", "from pyspark.sql.window import Window", "", "def run(spark, raw, state):"]
        last = None
        for s in mod.body:
            if not isinstance(s, ast.Assign):
                continue
            v = _py_rewrite(s.value, dfs[0], notes, lines)
            name = s.targets[0].id
            last = name
            lines.append(f"    {name} = {ast.unparse(v)}")
        if last != "clean":
            lines.append(f"    clean = {last}")
        lines.append('    return {"clean": clean, "rejects": None}')
        src = "\n".join(lines) + "\n"
    try:
        spec = ir6.norm_spec(AD.lift_py(src))
    except AD.Unsupported as e:
        return _fail("express", str(e)[:140], notes, list(tables))
    rows = next(iter(tables.values()))
    return Loaded(True, "ok", None, [spec], rows, list(rows[0].keys()), list(tables), sorted(notes))


def _py_rewrite(v, df, notes, lines):
    """dropDuplicates([k]) -> row_number over Window.partitionBy(k).orderBy(__rowid); select('a') -> select(F.col('a').alias('a'))."""
    v = copy.deepcopy(v)

    class T(ast.NodeTransformer):
        def visit_Name(self, n):
            return ast.copy_location(ast.Name(id="raw", ctx=n.ctx), n) if n.id == df else n

        def visit_Call(self, n):
            self.generic_visit(n)
            if isinstance(n.func, ast.Attribute) and n.func.attr == "select" and n.args and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in n.args):
                n.args = [ast.parse(f"F.col({a.value!r}).alias({a.value!r})").body[0].value for a in n.args]
                notes.add("PY select(str) -> aliased")
            return n

    v = T().visit(v)
    chain, node = [], v
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        chain.append(node)
        node = node.func.value
    for c in chain:
        if c.func.attr == "dropDuplicates":
            ks = c.args[0].elts if c.args and isinstance(c.args[0], ast.List) else c.args
            k = ks[0].value
            lines.append(f"    __w = Window.partitionBy({k!r}).orderBy(F.col('__rowid'))")
            lines.append(f"    __dd = {ast.unparse(c.func.value)}.withColumn('__rn', F.row_number().over(__w)).filter(F.col('__rn') == 1).drop('__rn')")
            c.func.value.__class__ = ast.Name
            repl = ast.Name(id="__dd", ctx=ast.Load())
            if c is v:
                return repl
            parent = next(p for p in chain if p.func.value is c)
            parent.func.value = repl
            notes.add("PY dropDuplicates -> first per key")
    return v


# ------------------------------------------------------------------ Polars
_PL_OPS = {ast.NotEq: "ne", ast.Eq: "eq", ast.Gt: "gt", ast.GtE: "ge", ast.Lt: "lt"}


def _pl_expr(n):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "col" and isinstance(n.func.value, ast.Name) and n.func.value.id == "pl":
        return ["col", n.args[0].value]
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "lit":
        return ["lit", n.args[0].value]
    if isinstance(n, ast.Constant):
        return ["lit", n.value]
    if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in _PL_OPS:
        return [_PL_OPS[type(n.ops[0])], _pl_expr(n.left), _pl_expr(n.comparators[0])]
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitAnd):
        return ["and", _pl_expr(n.left), _pl_expr(n.right)]
    raise AD.Unsupported(f"Polars expression {ast.dump(n)[:60]}")


def load_polars(text, tables):
    notes = set()
    try:
        mod = ast.parse(text)
    except SyntaxError as e:
        return _fail("parse", str(e)[:120], notes)
    free, _ = _free_names(mod)
    if len(free) != 1 or free[0] not in tables:
        return _fail("bind", f"free names {free} vs provided {sorted(tables)}", notes, free)
    notes.add("PL bind free DataFrame")
    rows = tables[free[0]]
    cols = list(rows[0].keys())
    stages, cur = [], dict(outputs=[[c, ["col", c]] for c in cols])
    try:
        st = [s for s in mod.body if isinstance(s, ast.Assign)][-1]
        chain, node = [], st.value
        while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            chain.append(node)
            node = node.func.value
        for c in reversed(chain):
            m = c.func.attr
            if m in ("filter", "where"):
                f = _pl_expr(c.args[0])
                if cur.get("dedup") or cur.get("filter") is None and False:
                    pass
                cur["filter"] = f if not cur.get("filter") else ["and", cur["filter"], f]
            elif m == "unique":
                kw = {k.arg: k.value for k in c.keywords}
                subset = kw.get("subset") or (c.args[0] if c.args else None)
                keys = [e.value for e in subset.elts] if isinstance(subset, ast.List) else [subset.value]
                keep = kw["keep"].value if "keep" in kw else "any"
                d = dict(key=keys[0]) if keep in ("first", "any") else dict(key=keys[0], order=["col", "__rowid"])
                if cur.get("filter") or cur.get("dedup"):
                    stages.append(cur)
                    cur = dict(outputs=[[x, ["col", x]] for x in cols])
                    notes.add("R7 filter-then-dedup -> 2 stages")
                cur["dedup"] = d
                notes.add(f"PL unique keep={keep}")
            elif m == "select":
                cur["outputs"] = [[a.value, ["col", a.value]] if isinstance(a, ast.Constant) else [_pl_expr(a)[1], _pl_expr(a)] for a in c.args]
            else:
                raise AD.Unsupported(f"Polars method {m}")
        stages.append(cur)
    except AD.Unsupported as e:
        return _fail("express", str(e)[:140], notes, free)
    return Loaded(True, "ok", None, [ir6.norm_spec(s) for s in stages], rows, cols, free, sorted(notes))


# ------------------------------------------------------------------ Scala
def load_scala(text, tables):
    notes = set()
    m = re.search(r"val\s+\w+\s*=\s*([A-Za-z_]\w*)\s*\.", text)
    if not m:
        return _fail("parse", "no `val x = df.<chain>` statement", notes)
    df = m.group(1)
    if df not in tables:
        return _fail("bind", f"relation {df} not provided", notes, [df])
    notes.add("SC bind free DataFrame")
    t = re.sub(rf"\b{re.escape(df)}\s*\.", "raw.", text, count=1)
    if "Map(\"clean\"" not in t:
        t += '\nMap("clean" -> clean, "rejects" -> null)'
    try:
        spec = ir6.lift(t, "scala")
    except AD.Unsupported as e:
        return _fail("express", str(e)[:140], notes, [df])
    except Exception as e:                                        # noqa: BLE001
        return _fail("express", f"{type(e).__name__}: {str(e)[:120]}", notes, [df])
    rows = tables[df]
    return Loaded(True, "ok", None, [spec], rows, list(rows[0].keys()), [df], sorted(notes))


def load(text, lang, tables):
    if lang in DIALECT:
        return load_sql(text, lang, tables)
    if lang == "py":
        return load_py(text, tables)
    if lang == "polars":
        return load_polars(text, tables)
    if lang == "scala":
        return load_scala(text, tables)
    return _fail("parse", f"no loader for {lang}", [])


def lower_stage(spec):
    """Canonical stage text written into a built workspace (lifts back exactly with ir6.lift(.., 'sql'))."""
    return ir6.lower(spec, "sql")


def describe(L):
    return json.dumps(dict(ok=L.ok, stage=L.stage, error=L.error, n_stages=len(L.stages), inputs=L.inputs, notes=L.notes), default=str)
