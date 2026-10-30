"""Phase 10D legacy input languages and LIFTERS (NOT LOCKED). A project's legacy DAG is written as text in one language and
NEXUS reads it back into the IR (the legacy semantics are what the text means; the generator's spec is never read by NEXUS).

  snowflake / postgres / hive   one file per DAG node (models/stg.sql, int.sql, fct.sql): CREATE TABLE ... AS SELECT with JSON
             extraction (JSON_EXTRACT_PATH_TEXT / get_json_object), QUALIFY (Snowflake) or ROW_NUMBER() subqueries, pre-aggregated
             joins, GROUP BY, and a real MERGE INTO ... WHEN MATCHED AND s.op = 'd' THEN DELETE / UPDATE / WHEN NOT MATCHED INSERT.
             Lifted with sqlglot 26.16.4 in the SOURCE dialect (Hive CAST = NULL on invalid input = try_int; Postgres regex-guarded
             CAST = try_int)
  dbt        Jinja models ({{ config(materialized=...) }}, {{ ref('...') }}) rendered by jinja2 then lifted as DuckDB SQL; the
             fct model carries the MERGE statement (incremental merge); tests in models/schema.yml
  scala      Spark Scala DataFrame code (val x = df.select(...).filter(...).withColumn("rn__", row_number().over(Window...)),
             .groupBy(...).agg(...), joins, Delta Lake DeltaTable.forName(..).merge(..).whenMatched("s.op = 'd'").delete()...);
             lifted by a lexical Scala -> Python rewrite and Python's ast (no as-of form: Scala projects have <= 4 tables)"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import jinja2
import sqlglot
from sqlglot import exp

from nexus.de_phase10d import engines10d as EN

EXT = dict(snowflake="sql", postgres="sql", hive="hql", dbt="sql", scala="scala")
RELS = ("cdc_customers", "orders", "order_items", "payments", "fx_rates", "stg_customers_latest", "stg_customers", "stg_orders", "stg_order_items",
        "stg_payments", "stg_fx_rates", "int_orders", "fct_src", "merge_src", "fct_target")


class Unsupported(Exception):
    pass


# ------------------------------------------------------------------ writers
def node_texts(spec, lang):
    if lang == "scala":
        return gen_scala(spec)
    ns = EN.node_sql(spec, lang)
    out = {}
    for node, sts in ns.items():
        txt = ";\n".join(sts) + ";\n"
        if lang == "dbt":
            for r in sorted(RELS, key=len, reverse=True):
                txt = re.sub(rf"(FROM|JOIN|USING) {r}\b", rf"\1 {{{{ ref('{r}') }}}}", txt)
            mat = "incremental', incremental_strategy='merge', unique_key='cust_key" if node == "fct" else "table"
            txt = "{{ config(materialized='" + mat + "') }}\n" + txt
        out[node] = txt
    return out


def write_legacy(spec, lang, ws):
    files = {}
    for node, txt in node_texts(spec, lang).items():
        f = f"models/{node}.{EXT[lang]}"
        (Path(ws) / f).write_text(txt)
        files[node] = f
    return files


# ------------------------------------------------------------------ SQL lifter
def conj(e):
    if e is None:
        return []
    if isinstance(e, exp.Paren):
        return conj(e.this)
    if isinstance(e, exp.And):
        return conj(e.this) + conj(e.expression)
    return [e]


def lx(e):
    if isinstance(e, exp.Paren):
        return lx(e.this)
    if isinstance(e, exp.Column):
        return ["col", e.name]
    if isinstance(e, exp.Literal):
        return ["lit", e.this if e.is_string else int(e.this)]
    if isinstance(e, exp.Null):
        return ["lit", None]
    if isinstance(e, exp.TryCast):
        return ["try_int", lx(e.this)]
    if isinstance(e, exp.Trim):
        return lx(e.this)
    if isinstance(e, exp.Cast):
        t = e.args["to"].this
        if t in (exp.DataType.Type.VARCHAR, exp.DataType.Type.TEXT, exp.DataType.Type.JSON):
            return lx(e.this)
        if t == exp.DataType.Type.INT:
            return ["try_int", lx(e.this)]
        raise Unsupported(f"cast to {t}")
    if isinstance(e, exp.Case):
        ifs = e.args.get("ifs") or []
        if len(ifs) == 1 and isinstance(ifs[0].this, exp.RegexpLike) and isinstance(ifs[0].args["true"], exp.Cast):
            return ["try_int", lx(ifs[0].args["true"].this)]
        raise Unsupported("CASE form")
    if isinstance(e, (exp.JSONExtractScalar, exp.JSONExtract)):
        path = e.expression
        keys = [s.this for s in path.expressions if isinstance(s, exp.JSONPathKey)] if isinstance(path, exp.JSONPath) else str(path.this).lstrip("$.").split(".")
        src = lx(e.this)
        return ["json", src[1], ".".join(keys)]
    if isinstance(e, exp.Coalesce):
        return ["coalesce", lx(e.this), lx(e.expressions[0])]
    if isinstance(e, exp.NEQ):
        return ["ne", lx(e.this), lx(e.expression)]
    if isinstance(e, exp.EQ):
        return ["eq", lx(e.this), lx(e.expression)]
    if isinstance(e, exp.Not) and isinstance(e.this, exp.Is) and isinstance(e.this.expression, exp.Null):
        return ["notnull", lx(e.this.this)]
    raise Unsupported(f"SQL node {type(e).__name__}")


AGGS = {exp.Sum: "sum", exp.Count: "count", exp.Max: "max"}


def lagg(e):
    for k, v in AGGS.items():
        if isinstance(e, k):
            return v, lx(e.this)
    return None


def table_of(e):
    return e.this.name if isinstance(e, exp.Table) else None


def parse_inner(sel):
    """SELECT proj FROM src  |  SELECT * FROM (SELECT proj FROM src) AS s0 WHERE pre"""
    f = sel.args["from"].this
    if isinstance(f, exp.Subquery) and f.alias == "s0":
        src, cols, _ = parse_inner(f.this)
        return src, cols, [lx(c) for c in conj(sel.args.get("where").this if sel.args.get("where") else None)]
    return table_of(f), [[p.alias, lx(p.this)] for p in sel.expressions], []


def window_parts(w):
    k = lx(w.args["partition_by"][0])
    o = w.args["order"].expressions[0]
    return dict(key=k, order=lx(o.this), desc=bool(o.args.get("desc")))


def parse_ded(sel):
    """-> (src, cols, pre, dedup)"""
    if sel.args.get("qualify"):
        inner = sel.args["from"].this.this
        q = sel.args["qualify"].this
        src, cols, pre = parse_inner(inner)
        return src, cols, pre, window_parts(q.this)
    f = sel.args["from"].this
    if isinstance(f, exp.Subquery) and any(isinstance(p, exp.Alias) and p.alias == "rn__" for p in f.this.expressions):
        mid = f.this
        w = next(p.this for p in mid.expressions if isinstance(p, exp.Alias) and p.alias == "rn__")
        src, cols, pre = parse_inner(mid.args["from"].this.this)
        return src, cols, pre, window_parts(w)
    src, cols, pre = parse_inner(sel)
    return src, cols, pre, None


def lift_stg(stmts):
    rels, latest = {}, {}
    for name, sel in stmts:
        f = sel.args["from"].this
        star = len(sel.expressions) == 1 and isinstance(sel.expressions[0], exp.Star)
        post = [lx(c) for c in conj(sel.args.get("where").this if sel.args.get("where") else None)]
        if star and isinstance(f, exp.Table) and f.name in latest:
            t = dict(latest[f.name], post=post, latest_as=f.name)
            rels[name] = t
            continue
        if star and isinstance(f, exp.Subquery) and f.alias == "d" and not sel.args.get("qualify"):
            src, cols, pre, ded = parse_ded(f.this)
            rels[name] = dict(src=src, cols=cols, pre=pre, dedup=ded, post=post)
            continue
        src, cols, pre, ded = parse_ded(sel)
        t = dict(src=src, cols=cols, pre=pre, dedup=ded, post=[])
        if name.endswith("_latest"):
            latest[name] = t
        else:
            rels[name] = t
    return rels


def lift_int(sel):
    out = [[p.alias, lx(p.this)] for p in sel.expressions]
    inner = sel.args["from"].this.this
    base = table_of(inner.args["from"].this)
    base_cols, takes, asof = [], {}, []
    for p in inner.expressions:
        x = p.this
        if isinstance(x, exp.Column) and x.table == "b":
            base_cols.append(x.name)
        elif isinstance(x, exp.Column):
            takes.setdefault(x.table, []).append([p.alias, x.name])
        elif isinstance(x, exp.Subquery):
            q = x.this
            rel = table_of(q.args["from"].this)
            cs = conj(q.args["where"].this)
            by = [cs[0].expression.name, cs[0].this.name]
            cmp = cs[1]
            strategy = "backward" if isinstance(cmp, exp.LTE) else "forward"
            asof.append(dict(rel=rel, how="asof", lkey=lx(cmp.expression), rkey=lx(cmp.this), by=by, strategy=strategy, agg=None,
                             take=[[p.alias, q.expressions[0].name]]))
        else:
            raise Unsupported("int projection")
    joins = []
    for jn in inner.args.get("joins") or []:
        a = jn.this.alias
        how = "left" if (jn.args.get("side") or "").upper() == "LEFT" else "inner"
        if isinstance(jn.this, exp.Subquery):
            q = jn.this.this
            by = q.expressions[0].name
            ms = [[p.alias] + list(lagg(p.this)) for p in q.expressions[1:]]
            rel, agg = table_of(q.args["from"].this), dict(by=by, measures=[[m, a_, x] for m, a_, x in ms])
        else:
            rel, agg = jn.this.name, None
        on = jn.args["on"]
        joins.append(dict(rel=rel, how=how, lkey=lx(on.this), rkey=lx(on.expression), agg=agg, take=takes.get(a, [])))
    return dict(base=base, base_cols=base_cols, joins=joins + asof, out=out)


def lift_fct(stmts, merge_stmt):
    sel = dict(stmts)["fct_src"]
    group, meas = [], []
    for p in sel.expressions:
        g = lagg(p.this)
        if g:
            meas.append([p.alias, g[0], g[1]])
        else:
            group.append([p.alias, lx(p.this)])
    f = dict(src=table_of(sel.args["from"].this), group=group, measures=meas, merge=None)
    if merge_stmt is None:
        return f
    whens = merge_stmt.args["whens"].expressions
    delete = any(w.args.get("matched") and isinstance(w.args.get("then"), exp.Var) and w.args["then"].name.upper() == "DELETE" for w in whens)
    update = any(w.args.get("matched") and isinstance(w.args.get("then"), exp.Update) for w in whens)
    key = merge_stmt.args["on"].this.name
    ms = dict(stmts)["merge_src"]
    union = ms if isinstance(ms, exp.Union) else None
    deletes = None
    if union is not None:
        dsel = union.expression.args["from"].this.this
        if dsel.args.get("from"):
            w = dsel.args["where"].this                         # key NOT IN (SELECT key FROM minus WHERE key IS NOT NULL)
            if isinstance(w, exp.Not):                         # NOT (key IN (subquery))
                sub = w.this.args["query"].this
            elif isinstance(w, exp.NEQ) and isinstance(w.expression, exp.All):   # Snowflake: key <> ALL (subquery)
                sub = w.expression.this
            else:
                raise Unsupported("deletes form")
            sub = sub.this if isinstance(sub, exp.Subquery) else sub
            deletes = dict(rel=table_of(dsel.args["from"].this), key=lx(dsel.expressions[0].this), minus=table_of(sub.args["from"].this))
    f["merge"] = dict(key=key, update=update, delete=delete, deletes=deletes)
    return f


def lift_sql(texts, lang):
    d = "duckdb" if lang == "dbt" else lang
    nodes = {}
    for node, txt in texts.items():
        if lang == "dbt":
            txt = jinja2.Environment().from_string(txt).render(ref=lambda r: r, config=lambda **k: "")
        try:
            sts = [s for s in sqlglot.parse(txt, read=d) if s is not None]
        except sqlglot.errors.ParseError as e:
            raise Unsupported(f"{lang} parse error: {str(e)[:80]}")
        creates, merge_stmt = [], None
        for s in sts:
            if isinstance(s, exp.Create):
                creates.append((s.this.name, s.expression))
            elif isinstance(s, exp.Merge):
                merge_stmt = s
            elif isinstance(s, (exp.Transaction, exp.Commit)):
                continue
            else:
                raise Unsupported(f"statement {type(s).__name__}")
        nodes[node] = (creates, merge_stmt)
    return dict(stg=lift_stg(nodes["stg"][0]), int=lift_int(dict(nodes["int"][0])["int_orders"]),
                fct=lift_fct(nodes["fct"][0], nodes["fct"][1]))


# ------------------------------------------------------------------ Scala
def S(e):
    op = e[0]
    if op == "col":
        return f'col("{e[1]}")'
    if op == "lit":
        return f'lit("{e[1]}")' if isinstance(e[1], str) else f"lit({e[1]})"
    if op == "try_int":
        return f'{S(e[1])}.cast("int")'
    if op == "json":
        return f'get_json_object(col("{e[1]}"), "$.{e[2]}")'
    if op == "coalesce":
        return f"coalesce({S(e[1])}, {S(e[2])})"
    if op in ("ne", "eq"):
        return f"({S(e[1])} {'=!=' if op == 'ne' else '==='} {S(e[2])})"
    if op == "notnull":
        return f"{S(e[1])}.isNotNull"
    raise ValueError(op)


def SQ(e, q):
    """qualified columns (join conditions)"""
    if e[0] == "col":
        return f'col("{q}.{e[1]}")'
    if e[0] == "try_int":
        return f'{SQ(e[1], q)}.cast("int")'
    return S(e)


def gen_scala(spec):
    L = {"stg": [], "int": [], "fct": []}
    for name in sorted(spec["stg"]):
        t = spec["stg"][name]
        ch = f"{t['src']}.select({', '.join(f'{S(x)}.as(\"{n}\")' for n, x in t['cols'])})"
        for c in t.get("pre", []):
            ch += f".filter({S(c)})"
        if t.get("dedup"):
            dd = t["dedup"]
            ch += (f'.withColumn("rn__", row_number().over(Window.partitionBy({S(dd["key"])}).orderBy({S(dd["order"])}.{"desc" if dd.get("desc", True) else "asc"})))'
                   f'.filter(col("rn__") === 1).drop("rn__")')
        if t.get("latest_as"):
            L["stg"].append(f"val {t['latest_as']} = {ch}")
            ch = t["latest_as"]
        for c in t.get("post", []):
            ch += f".filter({S(c)})"
        L["stg"].append(f"val {name} = {ch}")
    s = spec["int"]
    ch = f'{s["base"]}.as("b")'
    sel = [f'col("b.{c}").as("{c}")' for c in s["base_cols"]]
    for k, j in enumerate(s["joins"]):
        if j["how"] == "asof":
            raise Unsupported("Scala legacy has no as-of form")
        a = f"j{k}"
        rel = j["rel"]
        if j.get("agg"):
            g = j["agg"]
            rel = f'{rel}.groupBy(col("{g["by"]}")).agg({", ".join(f"{ag}({S(x)}).as(\"{m}\")" for m, ag, x in g["measures"])})'
        ch += f'.join({rel}.as("{a}"), {SQ(j["lkey"], "b")} === {SQ(j["rkey"], a)}, "{j["how"]}")'
        sel += [f'col("{a}.{c}").as("{o}")' for o, c in j["take"]]
    ch += f".select({', '.join(sel)}).select({', '.join(f'{S(x)}.as(\"{n}\")' for n, x in s['out'])})"
    L["int"].append(f"val int_orders = {ch}")
    f = spec["fct"]
    L["fct"].append(f"val fct_src = {f['src']}.groupBy({', '.join(f'{S(x)}.as(\"{n}\")' for n, x in f['group'])})"
                    f".agg({', '.join(f'{a}({S(x)}).as(\"{n}\")' for n, a, x in f['measures'])})")
    m = f.get("merge")
    if not m:
        L["fct"].append('fct_src.write.mode("overwrite").saveAsTable("fct_out")')
    else:
        if m.get("deletes"):
            dl = m["deletes"]
            L["fct"].append(f'val deletes = {dl["rel"]}.select({S(dl["key"])}.as("k")).distinct().join({dl["minus"]}.select({S(dl["key"])}.as("k")), Seq("k"), "left_anti")')
        k = m["key"]
        L["fct"].append(f'val merge_src = fct_src.join(deletes, fct_src("{k}") === deletes("k"), "left_anti").withColumn("op", lit("u"))'
                        f'.unionByName(deletes.withColumnRenamed("k", "{k}").withColumn("op", lit("d")), allowMissingColumns = true)')
        b = f'DeltaTable.forName("fct_target").as("t").merge(merge_src.as("s"), "t.{k} = s.{k}")'
        if m["delete"]:
            b += '.whenMatched("s.op = \'d\'").delete()'
        if m["update"]:
            b += ".whenMatched().updateAll()"
        b += '.whenNotMatched("s.op <> \'d\'").insertAll().execute()'
        L["fct"].append(b)
    return {n: "import org.apache.spark.sql.functions._\nimport org.apache.spark.sql.expressions.Window\nimport io.delta.tables._\n\n" + "\n".join(v) + "\n" for n, v in L.items()}


def _py(scala):
    s = scala.replace("=!=", "!=").replace("===", "==").replace('.as("', '.alias("')
    s = re.sub(r"\.isNotNull\b(?!\()", ".isNotNull()", s)
    s = re.sub(r"\.(desc|asc)\)", r".\1())", s)
    s = s.replace("allowMissingColumns = true", "allowMissingColumns=True").replace('Seq("k")', '["k"]')
    return s


def chain(node):
    out = []
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        out.append((node.func.attr, node.args))
        node = node.func.value
    return (node.id if isinstance(node, ast.Name) else None), list(reversed(out))


def px(n):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
        f, a = n.func.id, n.args
        if f == "col":
            return ["col", a[0].value.split(".")[-1]]
        if f == "lit":
            return ["lit", a[0].value]
        if f == "get_json_object":
            return ["json", px(a[0])[1], a[1].value.lstrip("$.")]
        if f == "coalesce":
            return ["coalesce", px(a[0]), px(a[1])]
        raise Unsupported(f"scala function {f}")
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
        if n.func.attr == "cast":
            return ["try_int", px(n.func.value)]
        if n.func.attr == "isNotNull":
            return ["notnull", px(n.func.value)]
        raise Unsupported(f"scala method {n.func.attr}")
    if isinstance(n, ast.Compare):
        op = "ne" if isinstance(n.ops[0], ast.NotEq) else "eq"
        return [op, px(n.left), px(n.comparators[0])]
    raise Unsupported(f"scala expr {type(n).__name__}")


def named(n):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "alias":
        return n.args[0].value, n.func.value
    raise Unsupported("unnamed scala column")


def pagg(n):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("sum", "count", "max"):
        return n.func.id, px(n.args[0])
    raise Unsupported("scala aggregate")


def lift_scala(texts):
    vals, merge_line, overwrite = {}, None, False
    for node in ("stg", "int", "fct"):
        for line in texts[node].splitlines():
            line = line.strip()
            if line.startswith("val "):
                name, rhs = line[4:].split(" = ", 1)
                vals[name] = ast.parse(_py(rhs), mode="eval").body
            elif line.startswith("DeltaTable"):
                merge_line = line
            elif "saveAsTable" in line:
                overwrite = True
    stg, latest = {}, {}
    for name, body in vals.items():
        if not name.startswith("stg_"):
            continue
        base, ops = chain(body)
        if base in latest:
            stg[name] = dict(latest[base], post=[px(a[0]) for m, a in ops if m == "filter"], latest_as=base)
            continue
        t = dict(src=base, cols=[], pre=[], dedup=None, post=[])
        seen_rn = False
        for m, a in ops:
            if m == "select":
                t["cols"] = [[nm_, px(x)] for nm_, x in map(named, a)]
            elif m == "withColumn":
                over = a[1]
                _, wops = chain(over.args[0])
                dd = dict(wops)
                o = dd["orderBy"][0]
                t["dedup"] = dict(key=px(dd["partitionBy"][0]), order=px(o.func.value), desc=o.func.attr == "desc")
                seen_rn = True
            elif m == "filter":
                c = a[0]
                if isinstance(c, ast.Compare) and isinstance(c.left, ast.Call) and getattr(c.left.func, "id", "") == "col" and c.left.args[0].value == "rn__":
                    continue
                (t["post"] if seen_rn else t["pre"]).append(px(c))
        if name.endswith("_latest"):
            latest[name] = t
        else:
            stg[name] = t
    base, ops = chain(vals["int_orders"])
    joins, sels = [], [a for m, a in ops if m == "select"]
    takes = {}
    for nm_, x in map(named, sels[0]):
        q = x.args[0].value.split(".")
        if q[0] != "b":
            takes.setdefault(q[0], []).append([nm_, q[1]])
    for m, a in ops:
        if m != "join":
            continue
        relnode, alias = a[0].func.value, a[0].args[0].value
        rb, rops = chain(relnode)
        agg = None
        if rops:
            g = dict(rops)
            agg = dict(by=px(g["groupBy"][0])[1], measures=[[nm_] + list(pagg(x)) for nm_, x in map(named, g["agg"])])
        cond = a[1]
        joins.append(dict(rel=rb, how=a[2].value, lkey=px(cond.left), rkey=px(cond.comparators[0]), agg=agg, take=takes.get(alias, [])))
    intspec = dict(base=base, base_cols=[nm_ for nm_, x in map(named, sels[0]) if x.args[0].value.startswith("b.")], joins=joins,
                   out=[[nm_, px(x)] for nm_, x in map(named, sels[1])])
    fb, fops = chain(vals["fct_src"])
    g = dict(fops)
    fct = dict(src=fb, group=[[nm_, px(x)] for nm_, x in map(named, g["groupBy"])], measures=[[nm_] + list(pagg(x)) for nm_, x in map(named, g["agg"])], merge=None)
    if merge_line and not overwrite:
        key = re.search(r'"t\.(\w+) = s\.\1"', merge_line).group(1)
        deletes = None
        if "deletes" in vals:
            db, dops = chain(vals["deletes"])
            dd = dict(dops)
            mb, _ = chain(dd["join"][0])
            deletes = dict(rel=db, key=px(named(dd["select"][0])[1]), minus=mb)
        fct["merge"] = dict(key=key, update=".updateAll()" in merge_line, delete=".delete()" in merge_line, deletes=deletes)
    return dict(stg=stg, int=intspec, fct=fct)


def lift(texts, lang):
    return lift_scala(texts) if lang == "scala" else lift_sql(texts, lang)


def read_and_lift(ws, contract):
    texts = {n: (Path(ws) / f).read_text() for n, f in contract["files"].items()}
    return lift(texts, contract["legacy_language"])
