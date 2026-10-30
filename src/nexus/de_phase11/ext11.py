"""Phase 11 Suite 2: the existing 16 Phase 10C / 10E external DEVELOPMENT tasks (scripts/agi10c_external.py; NOT LOCKED).
These are development diagnostics, not a held-out benchmark (the Phase 10E loader was developed on these same texts). Prior labels are
preserved: Phase 10C native ingestion 0 / 16 (one genuine repair, T09, behind a human adapter); Phase 10E: T05 vacuous (its data cannot
show the ordering bug), T11 invalid (issue text vs reference), T16 a wrong repair.
  io_task(t)   the 10 tasks WITH a reference repair become Phase 11 I/O synthesis tasks over the input table `raw` (all columns str, as
               written): vis_a = rows 1-7, vis_b = rows 8-14, evidence = rows 15-17, hidden = ALL rows; expected outputs are the
               reference SQL's DuckDB results on each slice (types read from the values). Tasks without a reference (T02 T04 T06 T07
               T13 T14) cannot be posed as I/O tasks: reported, never dropped from the denominator.
  ingest(t)    coverage of the LEGACY text: parse (sqlglot, the task's dialect) -> bind (every table exists) -> represent (a declared
               SQL subset translated into the core: single-table SELECT with column / literal / arithmetic / CAST / TRY_CAST / CASE /
               COALESCE / comparison / AND OR NOT / IS NULL expressions, WHERE, GROUP BY with SUM COUNT MIN MAX, QUALIFY ROW_NUMBER() = 1)
               -> native (DuckDB codegen + execution) -> conformance (reference interpreter == DuckDB). Non-SQL languages (PySpark,
               Polars, Scala), dbt Jinja (no renderer in Phase 11), MERGE, JSON operators and multi-table queries stop at the stage
               where they fail."""
from __future__ import annotations

import sys
from pathlib import Path

import sqlglot
from sqlglot import exp

from nexus.de_phase11 import core11 as C, sql11 as Q

ROOT = Path(__file__).resolve().parents[3]
LABELS = {"T05": "vacuous (Phase 10E: data cannot show the ordering bug)", "T11": "invalid (Phase 10C / 10E)", "T09": "genuine repair (Phase 10C behind a human adapter)",
          "T16": "Phase 10E wrong repair (visible-sample gap)"}
DIALECT = dict(snowflake="snowflake", postgres="postgres", hive="hive", sql="duckdb", j2="duckdb")


def tasks():
    sys.path.insert(0, str(ROOT / "scripts"))
    import agi10c_external as EXT
    return EXT


def _typed(cols, rows):
    types = []
    for j in range(len(cols)):
        vals = [r[j] for r in rows if r[j] is not None]
        t = C.STR
        if vals and all(isinstance(v, bool) for v in vals):
            t = C.BOOL
        elif vals and all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
            t = C.INT
        elif vals and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            t = C.NUM
        types.append(t)
    conv = [tuple((float(v) if t == C.NUM and v is not None else v) for v, t in zip(r, types)) for r in rows]
    return C.Rel(cols, types, conv)


def _raw(rows):
    cols = list(rows[0].keys())
    return C.Rel(cols, [C.STR] * len(cols), [tuple(None if r[c] == "" else r[c] for c in cols) for r in rows])


def io_task(t):
    EXT = tasks()
    if not t["ref"] or len(t["tables"]) != 1:
        return None
    rows = next(iter(t["tables"].values()))
    sl = dict(vis_a=rows[:7], vis_b=rows[7:14], evidence=rows[14:17] or rows[:3], hid=rows)
    envs, exps = {}, {}
    for k, rs in sl.items():
        cols, out = EXT.reference(t, rs)
        envs[k] = {"raw": _raw(rs)}
        exps[k] = _typed(cols, [tuple(r) for r in out])
    types = {}
    for k in exps:
        for c, ty in zip(exps[k].cols, exps[k].types):
            if exps[k].rows:
                types.setdefault(c, ty)
    for k in exps:
        exps[k] = C.Rel(exps[k].cols, [types.get(c, ty) for c, ty in zip(exps[k].cols, exps[k].types)], exps[k].rows)
    learner = dict(id=f"X{t['id']}", inputs={k: envs[k] for k in ("vis_a", "vis_b")}, expected={k: exps[k] for k in ("vis_a", "vis_b")},
                   out_schema=tuple(zip(exps["vis_a"].cols, exps["vis_a"].types)))
    admin = dict(evidence=(envs["evidence"], exps["evidence"]))
    hidden = dict(kind=t["id"], hid=[(envs["hid"], exps["hid"])], width=len(rows[0]))
    return learner, admin, hidden


# ------------------------------------------------------------------ legacy-text ingestion coverage
class NotRepresentable(Exception):
    pass


def _lit(e):
    if e.is_string:
        return ("const", e.this, C.STR)
    v = e.this
    return ("const", int(v), C.INT) if v.lstrip("-").isdigit() else ("const", float(v), C.NUM)


CMPS = {exp.EQ: "eq", exp.NEQ: "ne", exp.GT: "gt", exp.GTE: "ge", exp.LT: "lt", exp.LTE: "le"}
ARS = {exp.Add: "add", exp.Sub: "sub", exp.Mul: "mul", exp.Div: "div", exp.Mod: "mod"}


def _scalar(e):
    if isinstance(e, exp.Paren):
        return _scalar(e.this)
    if isinstance(e, exp.Column):
        return ("col", e.name)
    if isinstance(e, exp.Literal):
        return _lit(e)
    if isinstance(e, exp.Null):
        return ("const", None, C.STR)
    if isinstance(e, (exp.Cast, exp.TryCast)):
        t = e.to.this.name.lower() if hasattr(e.to.this, "name") else str(e.to.this).lower()
        tt = C.INT if "int" in t else C.NUM if any(k in t for k in ("double", "float", "decimal", "numeric", "real")) else C.STR if any(k in t for k in ("char", "text", "string")) else None
        if tt is None:
            raise NotRepresentable(f"cast type {t}")
        return ("cast", _scalar(e.this), tt)
    for k, o in CMPS.items():
        if isinstance(e, k):
            return ("cmp", o, _scalar(e.this), _scalar(e.expression))
    for k, o in ARS.items():
        if isinstance(e, k):
            return ("arith", o, _scalar(e.this), _scalar(e.expression))
    if isinstance(e, exp.And):
        return ("and", _scalar(e.this), _scalar(e.expression))
    if isinstance(e, exp.Or):
        return ("or", _scalar(e.this), _scalar(e.expression))
    if isinstance(e, exp.Not):
        return ("not", _scalar(e.this))
    if isinstance(e, exp.Is) and isinstance(e.expression, exp.Null):
        return ("isnull", _scalar(e.this))
    if isinstance(e, exp.Case):
        out = _scalar(e.args["default"]) if e.args.get("default") else ("const", None, C.STR)
        for w in reversed(e.args.get("ifs") or []):
            out = ("branch", _scalar(w.this), _scalar(w.args["true"]), out)
        return out
    if isinstance(e, exp.Coalesce):
        args = [e.this] + list(e.expressions)
        out = _scalar(args[-1])
        for a in reversed(args[:-1]):
            s = _scalar(a)
            out = ("branch", ("isnull", s), out, s)
        return out
    raise NotRepresentable(f"expression {type(e).__name__}")


def represent(tree, tables):
    if not isinstance(tree, exp.Select):
        raise NotRepresentable(f"statement {type(tree).__name__}")
    if tree.args.get("joins"):
        raise NotRepresentable("multi-table query")
    frm = tree.args.get("from")
    if frm is None or not isinstance(frm.this, exp.Table):
        raise NotRepresentable("FROM is not a single base table")
    tname = frm.this.name
    if tname not in tables:
        raise NotRepresentable(f"unbound table {tname}")
    if tree.args.get("distinct"):
        raise NotRepresentable("DISTINCT / DISTINCT ON")
    base = ("rel", tname)
    if tree.args.get("where"):
        base = ("filter", base, _scalar(tree.args["where"].this))
    q = tree.args.get("qualify")
    if q is not None:
        cond = q.this
        if not (isinstance(cond, exp.EQ) and isinstance(cond.this, exp.Window) and isinstance(cond.this.this, exp.RowNumber) and str(cond.expression) == "1"):
            raise NotRepresentable("QUALIFY other than ROW_NUMBER() = 1")
        w = cond.this
        keys = tuple(p.name for p in (w.args.get("partition_by") or []))
        order = tuple((_scalar(o.this), bool(o.args.get("desc"))) for o in (w.args["order"].expressions if w.args.get("order") else []))
        base = ("rank", base, keys, order, 1)
    outs = []
    aggs = []
    for e in tree.expressions:
        name = e.alias_or_name
        inner = e.this if isinstance(e, exp.Alias) else e
        if isinstance(inner, (exp.Sum, exp.Count, exp.Min, exp.Max)):
            agg = {exp.Sum: "sum", exp.Count: "count", exp.Min: "min", exp.Max: "max"}[type(inner)]
            if agg == "count" and isinstance(inner.this, exp.Star):
                aggs.append((name, "count_star", None))
            else:
                aggs.append((name, agg, _scalar(inner.this)))
            outs.append((name, ("col", name)))
        else:
            outs.append((name, _scalar(inner)))
    if tree.args.get("group"):
        keys = []
        for g in tree.args["group"].expressions:
            if not isinstance(g, exp.Column):
                raise NotRepresentable("GROUP BY over an expression / ordinal")
            keys.append(g.name)
        base = ("fold", base, tuple(keys), tuple(aggs))
        outs = [(n, ("col", n if n in [a[0] for a in aggs] else n)) for n, _ in outs]
    elif aggs:
        base = ("fold", base, (), tuple(aggs))
    return ("map", base, tuple(outs))


def ingest(t):
    """-> dict(stage reached, ok flags per stage, error)."""
    st = dict(id=t["id"], lang=t["lang"], parse=False, bind=False, represent=False, native=False, conformance=False, error=None)
    if t["lang"] in ("py", "polars", "scala"):
        st["error"] = f"{t['lang']}: no Phase 11 front end (SQL subset only)"
        return st
    try:
        tree = sqlglot.parse_one(t["legacy"], read=DIALECT[t["lang"]])
        st["parse"] = True
    except Exception as e:                                          # noqa: BLE001
        st["error"] = f"parse: {type(e).__name__}"
        return st
    tables = {n: _raw(rs) for n, rs in t["tables"].items()}
    names = {x.name for x in tree.find_all(exp.Table)}
    if not names or not names <= set(tables):
        st["error"] = f"bind: tables {sorted(names)} not all provided"
        return st
    st["bind"] = True
    try:
        prog = represent(tree, tables)
        C.rel_schema(prog, {k: v.schema() for k, v in tables.items()})
        st["represent"] = True
    except (NotRepresentable, C.TypeErr, C.Unsupported, KeyError) as e:
        st["error"] = f"represent: {e}"
        return st
    try:
        nat = Q.execute(prog, tables, "duckdb")
        st["native"] = nat is not C.ERR
        ref = C.evaluate(prog, tables)
        st["conformance"] = st["native"] and ref is not C.ERR and C.same_bag(nat, ref)
    except C.Unsupported as e:
        st["error"] = f"native: {e}"
    return st
