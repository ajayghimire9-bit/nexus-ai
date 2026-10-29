"""Phase 4 real-file workspace adapter (NOT LOCKED): reads a project's actual pipeline.sql (SQLite script) or pipeline.py
(PySpark 4 DataFrame script), LIFTS it into the stage IR with a real parser (sqlglot 26.16.4 for SQL, the Python `ast`
module for PySpark), and writes a repair back as a patched file plus a unified diff.

Stage-level inspection: stage 1 = dedup view / Window row_number, stage 2 = row filters and the quarantine split, stage 3 =
typed select / groupBy-agg. Clause-level inspection: CAST / TRY_CAST (try_cast), COALESCE, NULLIF, ROUND, GLOB / rlike
validity tests, ROW_NUMBER() OVER (PARTITION BY .. ORDER BY ..) windows, state-file (checkpoint / watermark) subqueries,
GROUP BY / groupBy().agg(F.sum).
Anything outside this subset raises Unsupported (the learner then abstains with ABSTAIN_UNSUPPORTED instead of guessing).
The engines never see the IR: runtimes execute the file TEXT (the lowered patch) and the evaluator executes the submission."""
from __future__ import annotations

import ast
import difflib
from pathlib import Path

import sqlglot
from sqlglot import exp

from nexus.de_phase4 import ir


class Unsupported(Exception):
    pass


# ------------------------------------------------------------------ SQL (sqlglot)
def _strip(n):
    while isinstance(n, exp.Paren):
        n = n.this
    return n


def _same(node, ir_expr):
    """Structural equality of a sqlglot node with the canonical lowering of an IR expression (idiom recognition)."""
    try:
        return _strip(node) == _strip(sqlglot.parse_one(ir.sql_expr(ir_expr), read="sqlite"))
    except Exception:                                   # noqa: BLE001
        return False


def _colname(n):
    n = _strip(n)
    if isinstance(n, exp.Column):
        return n.name
    raise Unsupported(f"expected a column, got {type(n).__name__}")


def sql_lift_expr(n):
    n = _strip(n)
    if isinstance(n, exp.Column):
        return ["col", n.name]
    if isinstance(n, exp.Null):
        return ["lit", None]
    if isinstance(n, exp.Literal):
        if n.is_string:
            return ["lit", n.this]
        return ["lit", float(n.this) if "." in n.this else int(n.this)]
    if isinstance(n, exp.Neg) and isinstance(_strip(n.this), exp.Literal):
        v = sql_lift_expr(n.this)[1]
        return ["lit", -v]
    if isinstance(n, exp.Subquery):                     # (SELECT "k" FROM state_<file>)
        sel = n.this
        if isinstance(sel, exp.Select) and len(sel.expressions) == 1:
            t = sel.args["from"].this
            if isinstance(t, exp.Table) and t.name.startswith("state_"):
                return ["file", t.name[len("state_"):] + ".json", _colname(sel.expressions[0])]
        raise Unsupported("subquery")
    if isinstance(n, exp.Cast):
        t = n.to.this
        if t in (exp.DataType.Type.INT, exp.DataType.Type.BIGINT):
            return ["cast_int", sql_lift_expr(n.this)]
        if t in (exp.DataType.Type.FLOAT, exp.DataType.Type.DOUBLE):
            return ["cast_real", sql_lift_expr(n.this)]
        raise Unsupported(f"cast to {t}")
    if isinstance(n, exp.Case):
        ifs = n.args.get("ifs") or []
        if len(ifs) == 1 and not n.args.get("default"):
            tv = _strip(ifs[0].args["true"])
            if isinstance(tv, exp.Cast) and isinstance(_strip(tv.this), exp.Trim):
                x = sql_lift_expr(_strip(tv.this).this)
                if _same(n, ["try_int", x]):
                    return ["try_int", x]
        raise Unsupported("CASE")
    if isinstance(n, exp.And):
        l = _strip(n.this)
        if isinstance(l, exp.NEQ) and isinstance(_strip(l.this), exp.Trim):
            x = sql_lift_expr(_strip(l.this).this)
            if _same(n, ["valid_int", x]):
                return ["valid_int", x]
        return ["and", sql_lift_expr(n.this), sql_lift_expr(n.expression)]
    if isinstance(n, exp.Not):
        return ["not", sql_lift_expr(n.this)]
    for cls, op in ((exp.Add, "add"), (exp.Sub, "sub"), (exp.Mul, "mul")):
        if isinstance(n, cls):
            return [op, sql_lift_expr(n.this), sql_lift_expr(n.expression)]
    if isinstance(n, exp.Div):
        num = _strip(n.this)
        if isinstance(num, exp.Mul) and isinstance(_strip(num.expression), exp.Literal) and _strip(num.expression).this in ("1.0",):
            return ["div_real", sql_lift_expr(num.this), sql_lift_expr(n.expression)]
        return ["div", sql_lift_expr(n.this), sql_lift_expr(n.expression)]
    if isinstance(n, exp.Nullif):
        a, b = _strip(n.this), _strip(n.expression)
        if isinstance(b, exp.Literal) and not b.is_string and b.this == "0":
            return ["nullif_zero", sql_lift_expr(a)]
        if isinstance(b, exp.Literal) and b.is_string and b.this == "" and isinstance(a, exp.Trim):
            return ["nullif_empty", sql_lift_expr(a.this)]
        raise Unsupported("NULLIF")
    if isinstance(n, exp.Round):
        d = _strip(n.args.get("decimals"))
        if isinstance(d, exp.Literal) and d.this == "2":
            return ["round2", sql_lift_expr(n.this)]
        raise Unsupported("ROUND")
    if isinstance(n, exp.Coalesce):
        if len(n.expressions) == 1:
            return ["coalesce", sql_lift_expr(n.this), sql_lift_expr(n.expressions[0])]
        raise Unsupported("COALESCE arity")
    if isinstance(n, exp.Upper) and isinstance(_strip(n.this), exp.Trim):
        return ["norm_text", sql_lift_expr(_strip(n.this).this)]
    for cls, op in ((exp.GT, "gt"), (exp.GTE, "ge"), (exp.EQ, "eq"), (exp.LT, "lt"), (exp.NEQ, "ne")):
        if isinstance(n, cls):
            return [op, sql_lift_expr(n.this), sql_lift_expr(n.expression)]
    raise Unsupported(f"SQL node {type(n).__name__}")


def _sql_rel(sel, rels):
    """A SELECT * FROM <relation> [WHERE] used as a stage -> relation dict."""
    src = sel.args["from"].this
    if isinstance(src, exp.Table):
        if src.name == "raw":
            base = dict(dedup=None, filters=[])
        elif src.name in rels:
            base = dict(rels[src.name], filters=list(rels[src.name]["filters"]))
        else:
            raise Unsupported(f"unknown relation {src.name}")
        w = sel.args.get("where")
        if w is not None:
            base["filters"].append(sql_lift_expr(w.this))
        return base
    if isinstance(src, exp.Subquery):                   # dedup: SELECT * FROM (SELECT *, ROW_NUMBER() OVER (..) AS __rn ..)
        inner = src.this
        win = next((_strip(x.this) for x in inner.expressions if isinstance(x, exp.Alias) and x.alias == "__rn"), None)
        w = sel.args.get("where")
        if not isinstance(win, exp.Window) or not isinstance(win.this, exp.RowNumber) or w is None:
            raise Unsupported("derived table")
        base = _sql_rel(inner, rels)
        if base["dedup"] or base["filters"]:
            raise Unsupported("dedup after filtering")
        key = _colname(win.args["partition_by"][0])
        o = win.args["order"].expressions[0]
        if isinstance(_strip(o.this), exp.Column) and _strip(o.this).name == "__rowid" and not o.args.get("desc"):
            base["dedup"] = dict(key=key)
        elif o.args.get("desc"):
            base["dedup"] = dict(key=key, order=sql_lift_expr(o.this))
        else:
            raise Unsupported("dedup order")
        return base
    raise Unsupported("FROM")


def _and_all(fs):
    out = None
    for f in fs:
        out = f if out is None else ["and", out, f]
    return out


def lift_sql(text):
    try:
        stmts = [s for s in sqlglot.parse(text, read="sqlite") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise Unsupported(f"SQL parse error: {str(e)[:80]}")
    rels, tables = {}, {}
    for s in stmts:
        if isinstance(s, exp.Drop):
            continue
        if not isinstance(s, exp.Create) or not isinstance(s.expression, exp.Select):
            raise Unsupported(f"statement {type(s).__name__}")
        name = s.this.name
        sel = s.expression
        if s.args.get("kind") == "VIEW":
            if not (len(sel.expressions) == 1 and isinstance(sel.expressions[0], exp.Star)):
                raise Unsupported("projecting view")
            rels[name] = _sql_rel(sel, rels)
        else:
            tables[name] = sel
    if "clean" not in tables:
        raise Unsupported("no clean table")
    q = None
    if "rejects" in tables:
        rsel = tables["rejects"]
        if not (len(rsel.expressions) == 1 and isinstance(rsel.expressions[0], exp.Star)):
            raise Unsupported("rejects projection")
        rrel = _sql_rel(rsel, rels)
        q = rrel["filters"].pop()
        base_r = rrel
    sel = tables["clean"]
    rel = _sql_rel(sel, rels)
    if q is not None:
        if not rel["filters"] or rel["filters"][-1] != ["not", q]:
            raise Unsupported("clean does not exclude the rejects")
        rel["filters"].pop()
        if rel["filters"] != base_r["filters"] or rel["dedup"] != base_r["dedup"]:
            raise Unsupported("rejects and clean read different stages")
    spec = dict(outputs=[])
    if rel["dedup"]:
        spec["dedup"] = rel["dedup"]
    if rel["filters"]:
        spec["filter"] = _and_all(rel["filters"])
    if q is not None:
        spec["quarantine"] = q
    grp = sel.args.get("group")
    for a in sel.expressions:
        if not isinstance(a, exp.Alias):
            raise Unsupported("unnamed output")
        x = _strip(a.this)
        if grp is not None and isinstance(x, exp.Sum):
            spec["outputs"].append([a.alias, sql_lift_expr(x.this)])
        elif grp is not None:
            if spec.get("group"):
                raise Unsupported("multiple group keys")
            spec["group"] = [a.alias, sql_lift_expr(x)]
        else:
            spec["outputs"].append([a.alias, sql_lift_expr(x)])
    if grp is not None:
        if len(grp.expressions) != 1 or not spec.get("group") or sql_lift_expr(grp.expressions[0]) != spec["group"][1]:
            raise Unsupported("GROUP BY must be the selected key expression")
    return spec


# ------------------------------------------------------------------ PySpark (Python ast)
def _const(n):
    if isinstance(n, ast.Constant):
        return n.value
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) and isinstance(n.operand, ast.Constant):
        return -n.operand.value
    raise Unsupported("expected a constant")


def _is_F(n, name):
    return isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == name and \
        isinstance(n.func.value, ast.Name) and n.func.value.id == "F"


def _method(n, name):
    return isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == name


def py_lift_expr(n):
    if _is_F(n, "col"):
        return ["col", _const(n.args[0])]
    if _is_F(n, "lit"):
        a = n.args[0]
        if isinstance(a, ast.Subscript) and isinstance(a.value, ast.Subscript) and isinstance(a.value.value, ast.Name) \
                and a.value.value.id == "state":
            return ["file", _const(a.value.slice), _const(a.slice)]
        return ["lit", _const(a)]
    if _method(n, "cast"):
        t = _const(n.args[0])
        if t in ("int", "integer", "bigint"):
            return ["cast_int", py_lift_expr(n.func.value)]
        if t in ("double", "float"):
            return ["cast_real", py_lift_expr(n.func.value)]
        raise Unsupported(f"cast {t}")
    if _method(n, "try_cast") and _is_F(n.func.value, "trim") and _const(n.args[0]) in ("int", "integer"):
        return ["try_int", py_lift_expr(n.func.value.args[0])]
    if _method(n, "rlike") and _is_F(n.func.value, "trim") and _const(n.args[0]) == "^[0-9]+$":
        return ["valid_int", py_lift_expr(n.func.value.args[0])]
    if _is_F(n, "nullif"):
        a, b = n.args
        if _is_F(b, "lit") and _const(b.args[0]) == 0:
            return ["nullif_zero", py_lift_expr(a)]
        if _is_F(b, "lit") and _const(b.args[0]) == "" and _is_F(a, "trim"):
            return ["nullif_empty", py_lift_expr(a.args[0])]
        raise Unsupported("nullif")
    if _is_F(n, "try_divide"):                         # F.try_divide(a, b) == a / NULLIF(b, 0) as a real
        return ["div_real", py_lift_expr(n.args[0]), ["nullif_zero", py_lift_expr(n.args[1])]]
    if _is_F(n, "round") and _const(n.args[1]) == 2:
        return ["round2", py_lift_expr(n.args[0])]
    if _is_F(n, "coalesce") and len(n.args) == 2:
        return ["coalesce", py_lift_expr(n.args[0]), py_lift_expr(n.args[1])]
    if _is_F(n, "upper") and _is_F(n.args[0], "trim"):
        return ["norm_text", py_lift_expr(n.args[0].args[0])]
    if isinstance(n, ast.BinOp):
        if isinstance(n.op, ast.Div):
            l = n.left
            if isinstance(l, ast.BinOp) and isinstance(l.op, ast.Mult) and _is_F(l.right, "lit") and _const(l.right.args[0]) == 1.0 \
                    and isinstance(l.right.args[0].value, float):
                return ["div_real", py_lift_expr(l.left), py_lift_expr(n.right)]
            return ["div", py_lift_expr(n.left), py_lift_expr(n.right)]
        ops = {ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.BitAnd: "and"}
        if type(n.op) in ops:
            return [ops[type(n.op)], py_lift_expr(n.left), py_lift_expr(n.right)]
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Invert):
        return ["not", py_lift_expr(n.operand)]
    if isinstance(n, ast.Compare) and len(n.ops) == 1:
        ops = {ast.Gt: "gt", ast.GtE: "ge", ast.Eq: "eq", ast.Lt: "lt", ast.NotEq: "ne"}
        if type(n.ops[0]) in ops:
            return [ops[type(n.ops[0])], py_lift_expr(n.left), py_lift_expr(n.comparators[0])]
    raise Unsupported(f"PySpark expression {ast.dump(n)[:80]}")


def _chain(n):
    """a.m1(..).m2(..) -> (base expr, [(method, call)])"""
    calls = []
    while isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
        calls.append((n.func.attr, n))
        n = n.func.value
    return n, calls[::-1]


def lift_py(text):
    try:
        mod = ast.parse(text)
    except SyntaxError as e:
        raise Unsupported(f"Python syntax error: {e}")
    fn = next((s for s in mod.body if isinstance(s, ast.FunctionDef) and s.name == "run"), None)
    if fn is None:
        raise Unsupported("no run(spark, raw, state)")
    rels, windows, rejects = {"raw": dict(dedup=None, filters=[])}, {}, {}
    clean, ret = None, None
    for s in fn.body:
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
            continue
        if isinstance(s, ast.Return):
            ret = s.value
            continue
        if not (isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)):
            raise Unsupported("statement")
        name, v = s.targets[0].id, s.value
        if isinstance(v, ast.Constant) and v.value is None:
            rejects[name] = None
            continue
        if isinstance(v, ast.Name):
            if v.id not in rels:
                raise Unsupported(f"unknown name {v.id}")
            rels[name] = dict(rels[v.id], filters=list(rels[v.id]["filters"]))
            continue
        base, calls = _chain(v)
        if isinstance(base, ast.Name) and base.id == "Window":
            d = dict(calls)
            key = _const(d["partitionBy"].args[0])
            o = d["orderBy"].args[0]
            if _method(o, "desc"):
                windows[name] = dict(key=key, order=py_lift_expr(o.func.value))
            elif py_lift_expr(o) == ["col", "__rowid"]:
                windows[name] = dict(key=key)
            else:
                raise Unsupported("window order")
            continue
        if not (isinstance(base, ast.Name) and base.id in rels):
            raise Unsupported("relation base")
        rel = dict(rels[base.id], filters=list(rels[base.id]["filters"]))
        names = [m for m, _ in calls]
        if names[:1] == ["withColumn"]:                  # dedup: withColumn("__rn", row_number().over(w)).filter(__rn == 1).drop
            wc = calls[0][1]
            if _const(wc.args[0]) != "__rn" or names[1:] not in (["filter", "drop"], ["where", "drop"]):
                raise Unsupported("withColumn")
            over = wc.args[1]
            if not (_method(over, "over") and isinstance(over.args[0], ast.Name) and over.args[0].id in windows):
                raise Unsupported("row_number window")
            if rel["dedup"] or rel["filters"]:
                raise Unsupported("dedup after filtering")
            rel["dedup"] = windows[over.args[0].id]
            rels[name] = rel
            continue
        if all(m in ("filter", "where") for m in names):
            for _, c in calls:
                f = py_lift_expr(c.args[0])
                rel["filters"].append(f)
            if name == "rejects":
                rejects[name] = rel
            else:
                rels[name] = rel
            continue
        if names == ["select"]:
            outs = []
            for a in calls[0][1].args:
                if not _method(a, "alias"):
                    raise Unsupported("unaliased select")
                outs.append([_const(a.args[0]), py_lift_expr(a.func.value)])
            clean = (rel, None, outs)
            continue
        if names == ["groupBy", "agg"]:
            g = calls[0][1].args
            if len(g) != 1 or not _method(g[0], "alias"):
                raise Unsupported("groupBy key")
            outs = []
            for a in calls[1][1].args:
                if not (_method(a, "alias") and _is_F(a.func.value, "sum")):
                    raise Unsupported("agg must be F.sum(..).alias(..)")
                outs.append([_const(a.args[0]), py_lift_expr(a.func.value.args[0])])
            clean = (rel, [_const(g[0].args[0]), py_lift_expr(g[0].func.value)], outs)
            continue
        raise Unsupported(f"DataFrame chain {names}")
    if clean is None or not isinstance(ret, ast.Dict):
        raise Unsupported("no clean output / return dict")
    rel, grp, outs = clean
    spec = dict(outputs=outs)
    if grp:
        spec["group"] = grp
    rj = rejects.get("rejects")
    if rj:
        q = rj["filters"][-1]
        if not rel["filters"] or rel["filters"][-1] != ["not", q] or rel["filters"][:-1] != rj["filters"][:-1] or \
                rel["dedup"] != rj["dedup"]:
            raise Unsupported("clean does not exclude the rejects")
        rel = dict(rel, filters=rel["filters"][:-1])
        spec["quarantine"] = q
    if rel["dedup"]:
        spec["dedup"] = rel["dedup"]
    if rel["filters"]:
        spec["filter"] = _and_all(rel["filters"])
    return spec


# ------------------------------------------------------------------ workspace I/O
def pipeline_file(ws):
    ws = Path(ws)
    for n, lang in (("pipeline.sql", "sql"), ("pipeline.py", "py")):
        if (ws / n).exists():
            return ws / n, lang
    raise Unsupported("no pipeline.sql / pipeline.py")


def read_pipeline(ws):
    p, lang = pipeline_file(ws)
    text = p.read_text()
    return text, lang, (lift_sql(text) if lang == "sql" else lift_py(text))


def write_patch(ws, spec, lang, out_dir="submission"):
    """Write the repaired pipeline file and a unified diff against the legacy file. Returns (path, diff text)."""
    p, _ = pipeline_file(ws)
    old = p.read_text()
    new = ir.lower(spec, lang)
    d = Path(ws) / out_dir
    d.mkdir(exist_ok=True)
    (d / p.name).write_text(new)
    diff = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{p.name}", f"b/{p.name}"))
    (d / "PATCH.diff").write_text(diff)
    return d / p.name, diff
