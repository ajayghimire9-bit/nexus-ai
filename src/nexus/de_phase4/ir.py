"""Phase 4 stage IR (NOT LOCKED): the pipeline form the learner edits, its pure-Python reference semantics, and its
LOWERING to the two real artifact languages a project ships:
  * SQLite 3 script  (pipeline.sql: one TEMP VIEW per stage, CREATE TABLE clean / rejects; state files as state_* tables)
  * PySpark 4 script (pipeline.py: def run(spark, raw, state) with DataFrame stages; executed under ANSI mode)
The engines only ever execute the lowered TEXT; adapter.py lifts real files back into this IR with sqlglot / Python ast.

Spec (extends the Phase 3 campaign3.de_world spec):
  stage 1  dedup       {key, order: expr}  latest row per key (ROW_NUMBER ... DESC)  |  {key}  first row per key by landing order
  stage 2  filter      expr (rows kept)          quarantine  expr (rows rejected to `rejects`)
  stage 3  group       [name, key expr] | None   outputs  [[name, expr]]  (SUM(expr) per group when group is set)
Expressions are nested lists, e.g. ["try_int", ["col", "qty"]]; ["file", "watermark.json", "watermark"] reads a state file
at run time (never a literal copied from the visible batch)."""
from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP

STAGE_OF = {"dedup": 1, "filter": 2, "quarantine": 2, "group": 3, "outputs": 3}


# ------------------------------------------------------------------ helpers
def exprs(spec):
    """(slot, index, expr) for every expression of the spec (outputs, group key, filter, quarantine, dedup order)."""
    out = [("outputs", i, x) for i, (_, x) in enumerate(spec["outputs"])]
    if spec.get("group"):
        out.append(("group", 0, spec["group"][1]))
    for k in ("filter", "quarantine"):
        if spec.get(k):
            out.append((k, 0, spec[k]))
    return out


def walk(e):
    if isinstance(e, list):
        yield e
        for x in e[1:]:
            yield from walk(x)


def cols_in(e):
    return [n[1] for n in walk(e) if n and n[0] == "col"]


def canon(spec):
    return json.dumps(spec, sort_keys=True)


# ------------------------------------------------------------------ reference semantics (pure Python; never an engine)
class RefError(Exception):
    pass


def _is_int(s):
    return isinstance(s, str) and s.strip() != "" and s.strip().isascii() and s.strip().isdigit()


def round2(x):
    return None if x is None else float(Decimal(repr(float(x))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def ev(e, row, state):
    op = e[0]
    if op == "col":
        return row[e[1]]
    if op == "lit":
        return e[1]
    if op == "file":
        return state[e[1]][e[2]]
    a = [ev(x, row, state) for x in e[1:]] if op not in ("and",) else None
    if op == "cast_int":
        if a[0] is None:
            return None
        if not _is_int(a[0]):
            raise RefError(f"plain cast of {a[0]!r}")
        return int(a[0].strip())
    if op == "cast_real":
        return None if a[0] is None else float(a[0])
    if op == "valid_int":
        return _is_int(a[0])
    if op == "try_int":
        return int(a[0].strip()) if _is_int(a[0]) else None
    if op in ("add", "sub", "mul"):
        if a[0] is None or a[1] is None:
            return None
        return a[0] + a[1] if op == "add" else a[0] - a[1] if op == "sub" else a[0] * a[1]
    if op == "div":                       # SQLite native division (integer truncation on ints; x / 0 = NULL)
        if a[0] is None or a[1] is None or a[1] == 0:
            return None
        if isinstance(a[0], int) and isinstance(a[1], int):
            q = abs(a[0]) // abs(a[1])
            return q if (a[0] >= 0) == (a[1] >= 0) else -q
        return a[0] / a[1]
    if op == "div_real":
        if a[0] is None or a[1] is None:
            return None
        if a[1] == 0:
            raise RefError("division by zero")
        return a[0] * 1.0 / a[1]
    if op == "nullif_zero":
        return None if a[0] == 0 else a[0]
    if op == "round2":
        return round2(a[0])
    if op == "coalesce":
        return a[0] if a[0] is not None else a[1]
    if op == "nullif_empty":
        if a[0] is None:
            return None
        t = a[0].strip()
        return None if t == "" else t
    if op == "norm_text":
        return None if a[0] is None else a[0].strip().upper()
    if op in ("gt", "ge", "eq", "lt", "ne"):
        if a[0] is None or a[1] is None:
            return None
        return {"gt": a[0] > a[1], "ge": a[0] >= a[1], "eq": a[0] == a[1], "lt": a[0] < a[1], "ne": a[0] != a[1]}[op]
    if op == "and":                       # SQL three-valued AND
        l = ev(e[1], row, state)
        if l is False:
            return False
        r = ev(e[2], row, state)
        if r is False:
            return False
        return None if l is None or r is None else True
    if op == "not":
        return None if a[0] is None else not a[0]
    raise ValueError(op)


def interpret(spec, rows, state):
    """Reference execution of a spec on landed rows (dicts of text) -> {clean: [dict], rejects: [dict] | None}."""
    rs = [dict(r, __rowid=i) for i, r in enumerate(rows)]
    dd = spec.get("dedup")
    if dd:
        best = {}
        for r in rs:
            k = r[dd["key"]]
            if k not in best:
                best[k] = r
            elif dd.get("order") is not None:
                if ev(dd["order"], r, state) > ev(dd["order"], best[k], state):
                    best[k] = r
        keep = {id(v) for v in best.values()}
        rs = [r for r in rs if id(r) in keep]
    if spec.get("filter"):
        rs = [r for r in rs if ev(spec["filter"], r, state) is True]
    rejects = None
    if spec.get("quarantine"):
        q = [(r, ev(spec["quarantine"], r, state)) for r in rs]
        rejects = [{k: v for k, v in r.items() if k != "__rowid"} for r, b in q if b is True]
        rs = [r for r, b in q if b is False]
    if spec.get("group"):
        gname, gx = spec["group"]
        agg, order = {}, []
        for r in rs:
            k = ev(gx, r, state)
            if k not in agg:
                agg[k] = [None] * len(spec["outputs"])
                order.append(k)
            for j, (_, x) in enumerate(spec["outputs"]):
                v = ev(x, r, state)
                if v is not None:
                    agg[k][j] = v if agg[k][j] is None else agg[k][j] + v
        clean = [{gname: k, **{n: agg[k][j] for j, (n, _) in enumerate(spec["outputs"])}} for k in order]
    else:
        clean = [{n: ev(x, r, state) for n, x in spec["outputs"]} for r in rs]
    return dict(clean=clean, rejects=rejects)


def out_cols(spec):
    return ([spec["group"][0]] if spec.get("group") else []) + [n for n, _ in spec["outputs"]]


# ------------------------------------------------------------------ lowering: SQLite script
def sql_expr(e, kw=str.upper):
    op = e[0]
    r = lambda x: sql_expr(x, kw)                                                    # noqa: E731
    if op == "col":
        return f'"{e[1]}"'
    if op == "lit":
        v = e[1]
        return kw("null") if v is None else (f"'{v}'" if isinstance(v, str) else repr(v))
    if op == "file":
        return f'({kw("select")} "{e[2]}" {kw("from")} "state_{e[1].rsplit(".", 1)[0]}")'
    if op == "cast_int":
        return f"{kw('cast')}({r(e[1])} {kw('as')} {kw('integer')})"
    if op == "cast_real":
        return f"{kw('cast')}({r(e[1])} {kw('as')} {kw('real')})"
    if op == "valid_int":
        x = f"{kw('trim')}({r(e[1])})"
        return f"({x} <> '' {kw('and')} {x} {kw('not')} {kw('glob')} '*[^0-9]*')"
    if op == "try_int":
        x = f"{kw('trim')}({r(e[1])})"
        return (f"({kw('case')} {kw('when')} {x} <> '' {kw('and')} {x} {kw('not')} {kw('glob')} '*[^0-9]*' "
                f"{kw('then')} {kw('cast')}({x} {kw('as')} {kw('integer')}) {kw('end')})")
    if op in ("add", "sub", "mul", "div"):
        return f"({r(e[1])} {dict(add='+', sub='-', mul='*', div='/')[op]} {r(e[2])})"
    if op == "div_real":
        return f"(({r(e[1])}) * 1.0 / ({r(e[2])}))"
    if op == "nullif_zero":
        return f"{kw('nullif')}({r(e[1])}, 0)"
    if op == "round2":
        return f"{kw('round')}({r(e[1])}, 2)"
    if op == "coalesce":
        return f"{kw('coalesce')}({r(e[1])}, {r(e[2])})"
    if op == "nullif_empty":
        return f"{kw('nullif')}({kw('trim')}({r(e[1])}), '')"
    if op == "norm_text":
        return f"{kw('upper')}({kw('trim')}({r(e[1])}))"
    if op in ("gt", "ge", "eq", "lt", "ne"):
        return f"({r(e[1])} {dict(gt='>', ge='>=', eq='=', lt='<', ne='<>')[op]} {r(e[2])})"
    if op == "and":
        return f"({r(e[1])} {kw('and')} {r(e[2])})"
    if op == "not":
        return f"({kw('not')} {r(e[1])})"
    raise ValueError(op)


DEFAULT_STYLE = dict(kw="upper", views=("stage1", "stage2"), comments=True, header=None)


def lower_sql(spec, style=None):
    st = dict(DEFAULT_STYLE, **(style or {}))
    kw = str.upper if st["kw"] == "upper" else str.lower
    v1, v2 = st["views"]
    L = []
    if st.get("header"):
        L += [f"-- {h}" for h in st["header"]]
    dd = spec.get("dedup")
    if st["comments"]:
        L.append("-- stage 1: row identity")
    if dd:
        order = sql_expr(dd["order"], kw) + f" {kw('desc')}" if dd.get("order") is not None else '"__rowid"'
        L.append(f"{kw('create temp view')} {v1} {kw('as')} {kw('select')} * {kw('from')} ({kw('select')} *, "
                 f"{kw('row_number')}() {kw('over')} ({kw('partition by')} \"{dd['key']}\" {kw('order by')} {order}) "
                 f"{kw('as')} __rn {kw('from')} raw) {kw('where')} __rn = 1;")
    else:
        L.append(f"{kw('create temp view')} {v1} {kw('as')} {kw('select')} * {kw('from')} raw;")
    if st["comments"]:
        L.append("-- stage 2: row selection and quarantine")
    flt = f" {kw('where')} {sql_expr(spec['filter'], kw)}" if spec.get("filter") else ""
    L.append(f"{kw('create temp view')} {v2} {kw('as')} {kw('select')} * {kw('from')} {v1}{flt};")
    q = spec.get("quarantine")
    if q:
        L.append(f"{kw('create table')} rejects {kw('as')} {kw('select')} * {kw('from')} {v2} {kw('where')} {sql_expr(q, kw)};")
    if st["comments"]:
        L.append("-- stage 3: typed outputs")
    keep = f" {kw('where')} {kw('not')} {sql_expr(q, kw)}" if q else ""
    if spec.get("group"):
        g, gx = spec["group"]
        cols = [f'{sql_expr(gx, kw)} {kw("as")} "{g}"'] + [f'{kw("sum")}({sql_expr(x, kw)}) {kw("as")} "{n}"' for n, x in spec["outputs"]]
        L.append(f"{kw('create table')} clean {kw('as')} {kw('select')} {', '.join(cols)} {kw('from')} {v2}{keep} "
                 f"{kw('group by')} {sql_expr(gx, kw)};")
    else:
        cols = [f'{sql_expr(x, kw)} {kw("as")} "{n}"' for n, x in spec["outputs"]]
        L.append(f"{kw('create table')} clean {kw('as')} {kw('select')} {', '.join(cols)} {kw('from')} {v2}{keep};")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ lowering: PySpark script
def py_expr(e):
    op = e[0]
    r = py_expr
    if op == "col":
        return f'F.col("{e[1]}")'
    if op == "lit":
        return f"F.lit({e[1]!r})"
    if op == "file":
        return f'F.lit(state["{e[1]}"]["{e[2]}"])'
    if op == "cast_int":
        return f'{r(e[1])}.cast("int")'
    if op == "cast_real":
        return f'{r(e[1])}.cast("double")'
    if op == "valid_int":
        return f'F.trim({r(e[1])}).rlike("^[0-9]+$")'
    if op == "try_int":
        return f'F.trim({r(e[1])}).try_cast("int")'
    if op in ("add", "sub", "mul", "div"):
        return f"({r(e[1])} {dict(add='+', sub='-', mul='*', div='/')[op]} {r(e[2])})"
    if op == "div_real":
        return f"(({r(e[1])} * F.lit(1.0)) / {r(e[2])})"
    if op == "nullif_zero":
        return f"F.nullif({r(e[1])}, F.lit(0))"
    if op == "round2":
        return f"F.round({r(e[1])}, 2)"
    if op == "coalesce":
        return f"F.coalesce({r(e[1])}, {r(e[2])})"
    if op == "nullif_empty":
        return f'F.nullif(F.trim({r(e[1])}), F.lit(""))'
    if op == "norm_text":
        return f"F.upper(F.trim({r(e[1])}))"
    if op in ("gt", "ge", "eq", "lt", "ne"):
        return f"({r(e[1])} {dict(gt='>', ge='>=', eq='==', lt='<', ne='!=')[op]} {r(e[2])})"
    if op == "and":
        return f"({r(e[1])} & {r(e[2])})"
    if op == "not":
        return f"(~{r(e[1])})"
    raise ValueError(op)


PY_STYLE = dict(names=("stage1", "stage2", "kept"), comments=True, header=None, where="filter")


def lower_py(spec, style=None):
    st = dict(PY_STYLE, **(style or {}))
    n1, n2, nk = st["names"]
    flt = st["where"]
    L = ['"""' + (" ".join(st["header"]) if st.get("header") else "Pipeline.") + '"""',
         "from pyspark.sql import functions as F", "from pyspark.sql.window import Window", "", "",
         "def run(spark, raw, state):"]
    I = "    "
    dd = spec.get("dedup")
    if st["comments"]:
        L.append(I + "# stage 1: row identity")
    if dd:
        order = py_expr(dd["order"]) + ".desc()" if dd.get("order") is not None else 'F.col("__rowid")'
        L.append(I + f'w = Window.partitionBy("{dd["key"]}").orderBy({order})')
        L.append(I + f'{n1} = raw.withColumn("__rn", F.row_number().over(w)).{flt}(F.col("__rn") == 1).drop("__rn")')
    else:
        L.append(I + f"{n1} = raw")
    if st["comments"]:
        L.append(I + "# stage 2: row selection and quarantine")
    L.append(I + (f"{n2} = {n1}.{flt}({py_expr(spec['filter'])})" if spec.get("filter") else f"{n2} = {n1}"))
    q = spec.get("quarantine")
    if q:
        L.append(I + f"rejects = {n2}.{flt}({py_expr(q)})")
        L.append(I + f"{nk} = {n2}.{flt}(~{py_expr(q)})")
    else:
        L.append(I + "rejects = None")
        L.append(I + f"{nk} = {n2}")
    if st["comments"]:
        L.append(I + "# stage 3: typed outputs")
    if spec.get("group"):
        g, gx = spec["group"]
        aggs = ", ".join(f'F.sum({py_expr(x)}).alias("{n}")' for n, x in spec["outputs"])
        L.append(I + f'clean = {nk}.groupBy({py_expr(gx)}.alias("{g}")).agg({aggs})')
    else:
        sel = ", ".join(f'{py_expr(x)}.alias("{n}")' for n, x in spec["outputs"])
        L.append(I + f"clean = {nk}.select({sel})")
    L.append(I + 'return {"clean": clean, "rejects": rejects}')
    return "\n".join(L) + "\n"


def lower(spec, lang, style=None):
    return lower_sql(spec, style) if lang == "sql" else lower_py(spec, style)
