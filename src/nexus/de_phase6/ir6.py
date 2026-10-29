"""Phase 6 IR extensions and multi-language adapters (NOT LOCKED). Extends de_phase4.ir / de_phase4.adapter WITHOUT editing
them: new operations are registered by wrapping the module-level renderers (their recursion resolves through the module
globals), and every new language has its own lower / lift pair.

New operations   le (<=), nonempty (NOT NULL and TRIM <> ''), and column-to-column comparisons (point-in-time joins use
                 cast_int(feature_ts) le / lt cast_int(label_ts)) - all four engines' semantics are the SQL ones.
Languages (a pipeline stage = legacy input language -> execution engine -> target language):
  sql        SQLite 3 script (Phase 4 lowering)
  hive / postgres / snowflake   legacy SQL written by sqlglot 26.16.4 transpilation of the SQLite script; LIFTED by
             transpiling back (read=<dialect>) - the dialect's own semantics are kept (e.g. Hive / Snowflake '/' is real
             division) and normalised into the IR (normalize())
  duckdb     DuckDB 1.1.3 script: the SQLite script transpiled by sqlglot, with DuckDB-native TRY_CAST /
             regexp_full_match for the integer tests (DuckDB does not guarantee CASE-guarded CAST evaluation order)
  py         PySpark 4 DataFrame script (Phase 4 lowering / ast lifting)
  j2         dbt-style model: one Jinja template per stage ({{ config(materialized='table') }}, FROM {{ ref('<input>') }})
             rendered by jinja2 3.1.4 into the SQLite script, plus schema.yml tests (written by world6)
  scala      READ-ONLY legacy Scala Spark DataFrame chains (val x = df.filter(col("a").cast("int") > lit(3)) ...);
             lifted by a lexical Scala -> Python rewrite (===, &&, !, .desc, .as, val, col / lit) and the PySpark ast lifter
Legacy files are input specifications; the evaluator executes only the SUBMITTED target file text."""
from __future__ import annotations

import ast
import contextlib
import re

import jinja2
import sqlglot
from sqlglot import exp

from nexus.de_phase4 import adapter as AD, ir

LANGS = ("sql", "hive", "postgres", "snowflake", "duckdb", "py", "j2", "scala")
_sql0, _py0, _ev0, _sqlift0, _pylift0 = ir.sql_expr, ir.py_expr, ir.ev, AD.sql_lift_expr, AD.py_lift_expr


def _sql(e, kw=str.upper):
    op = e[0]
    if op == "le":
        return f"({ir.sql_expr(e[1], kw)} <= {ir.sql_expr(e[2], kw)})"
    if op == "nonempty":
        x = ir.sql_expr(e[1], kw)
        return f"({x} {kw('is not null')} {kw('and')} {kw('trim')}({x}) <> '')"
    return _sql0(e, kw)


def _py(e):
    if e[0] == "le":
        return f"({ir.py_expr(e[1])} <= {ir.py_expr(e[2])})"
    if e[0] == "nonempty":
        x = ir.py_expr(e[1])
        return f'({x}.isNotNull() & (F.trim({x}) != F.lit("")))'
    return _py0(e)


def _ev(e, row, state):
    if e[0] == "le":
        a, b = ir.ev(e[1], row, state), ir.ev(e[2], row, state)
        return None if a is None or b is None else a <= b
    if e[0] == "nonempty":
        v = ir.ev(e[1], row, state)
        return v is not None and str(v).strip() != ""
    return _ev0(e, row, state)


def _sqlift(n):
    n0 = AD._strip(n)
    if isinstance(n0, exp.LTE):
        return ["le", AD.sql_lift_expr(n0.this), AD.sql_lift_expr(n0.expression)]
    if isinstance(n0, exp.And):
        l, r = AD._strip(n0.this), AD._strip(n0.expression)
        if isinstance(l, exp.Not) and isinstance(AD._strip(l.this), exp.Is):
            x = AD.sql_lift_expr(AD._strip(l.this).this)
            if AD._same(n0, ["nonempty", x]):
                return ["nonempty", x]
    return _sqlift0(n)


def _pylift(n):
    if isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], ast.LtE):
        return ["le", AD.py_lift_expr(n.left), AD.py_lift_expr(n.comparators[0])]
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitAnd) and AD._method(n.left, "isNotNull"):
        return ["nonempty", AD.py_lift_expr(n.left.func.value)]
    return _pylift0(n)


ir.sql_expr, ir.py_expr, ir.ev = _sql, _py, _ev                 # registration (runtime; the Phase 4 files are unchanged)
AD.sql_lift_expr, AD.py_lift_expr = _sqlift, _pylift


# ------------------------------------------------------------------ normalisation of lifted dialect semantics
OPNAMES = {"col", "lit", "file", "cast_int", "cast_real", "valid_int", "try_int", "add", "sub", "mul", "div", "div_real", "nullif_zero",
           "round2", "coalesce", "nullif_empty", "norm_text", "gt", "ge", "eq", "lt", "ne", "and", "not", "le", "nonempty"}


def normalize(e):
    if isinstance(e, dict):
        return {k: normalize(v) for k, v in e.items()}
    if not isinstance(e, list) or not e:
        return e
    if not isinstance(e[0], str) or e[0] not in OPNAMES:
        return [normalize(x) for x in e]
    e = [e[0]] + [normalize(x) for x in e[1:]]
    if e[0] == "div" and isinstance(e[1], list) and e[1][0] == "cast_real":          # dialect real division
        num = e[1][1]
        if isinstance(num, list) and num[0] == "mul" and num[2] == ["lit", 1.0]:
            num = num[1]
        return ["div_real", num, e[2]]
    if e[0] in ("nullif_zero",) and isinstance(e[1], list) and e[1][0] == "nullif_zero":
        return e[1]
    if e[0] in ("div", "div_real") and isinstance(e[2], list) and e[2][0] == "nullif_zero" and isinstance(e[2][1], list) \
            and e[2][1][0] == "nullif_zero":
        return [e[0], e[1], e[2][1]]
    return e


def norm_spec(spec):
    s = normalize(spec)
    s["outputs"] = [list(o) for o in s["outputs"]]
    return s


# ------------------------------------------------------------------ DuckDB lowering
def _duck_expr(e, kw=str.upper):
    if e[0] == "try_int":
        return f"TRY_CAST(TRIM({ir.sql_expr(e[1], kw)}) AS INTEGER)"
    if e[0] == "valid_int":
        return f"COALESCE(regexp_full_match(TRIM({ir.sql_expr(e[1], kw)}), '[0-9]+'), FALSE)"
    return _sql(e, kw)


@contextlib.contextmanager
def _renderer(fn):
    old = ir.sql_expr
    ir.sql_expr = fn
    try:
        yield
    finally:
        ir.sql_expr = old


def lower_duckdb(spec, style=None):
    with _renderer(_duck_expr):
        s = ir.lower_sql(spec, style)
    return ";\n".join(sqlglot.transpile(s, read="sqlite", write="duckdb")) + ";\n"


# ------------------------------------------------------------------ Scala (read-only legacy input)
def _scala_expr(e):
    py = ir.py_expr(e)
    s = py.replace("F.col(", "col(").replace("F.lit(", "lit(").replace(" == ", " === ").replace(" != ", " =!= ")
    s = s.replace(" & ", " && ").replace("(~", "(!").replace(".desc()", ".desc")
    s = re.sub(r'state\["([^"]+)"\]\["([^"]+)"\]', r'state("\1")("\2")', s)
    s = s.replace("F.", "")
    return s


def lower_scala(spec, style=None):
    """A Scala Spark DataFrame job equivalent to the PySpark lowering (legacy input only; never executed here)."""
    py = ir.lower_py(spec, style)
    out = ["// legacy Scala Spark job (read-only migration input)", "import org.apache.spark.sql.functions._",
           "import org.apache.spark.sql.expressions.Window", "", "object Job {",
           "  def run(spark: SparkSession, raw: DataFrame, state: Map[String, Map[String, Int]]): Map[String, DataFrame] = {"]
    for line in py.splitlines():
        t = line.strip()
        if not t or t.startswith(('"""', "from ", "def ", "import ")):
            continue
        if t.startswith("#"):
            out.append("    //" + t[1:])
            continue
        if t.startswith("return"):
            out.append('    Map("clean" -> clean, "rejects" -> rejects)')
            continue
        name, rhs = t.split(" = ", 1)
        rhs = _py_to_scala(rhs)
        out.append(f"    val {name} = {rhs}")
    out += ["  }", "}"]
    return "\n".join(out) + "\n"


def _py_to_scala(s):
    s = s.replace("F.col(", "col(").replace("F.lit(", "lit(").replace(" == ", " === ").replace(" != ", " =!= ")
    s = s.replace(" & ", " && ").replace("(~", "(!").replace(".filter(~", ".filter(!").replace(".desc()", ".desc")
    s = s.replace(".alias(", ".as(").replace("F.", "").replace("None", "null")
    s = re.sub(r'state\["([^"]+)"\]\["([^"]+)"\]', r'state("\1")("\2")', s)
    return s


_FNS = ("col", "lit", "trim", "upper", "coalesce", "nullif", "round", "sum", "row_number", "try_divide")


def lift_scala(text):
    body = [l.strip() for l in text.splitlines() if l.strip().startswith("val ") or l.strip().startswith("Map(\"clean\"")]
    if not body:
        raise AD.Unsupported("no Scala DataFrame statements")
    py = ["from pyspark.sql import functions as F", "from pyspark.sql.window import Window", "", "def run(spark, raw, state):"]
    for l in body:
        if l.startswith("Map("):
            py.append('    return {"clean": clean, "rejects": rejects}')
            continue
        name, rhs = l[4:].split(" = ", 1)
        r = rhs.replace("=!=", "!=").replace("===", "==").replace("&&", "&").replace("(!", "(~").replace(".filter(!", ".filter(~")
        r = re.sub(r"\.desc\b(?!\()", ".desc()", r).replace(".as(", ".alias(")
        r = re.sub(r"\bnull\b", "None", r)
        r = re.sub(r'state\("([^"]+)"\)\("([^"]+)"\)', r'state["\1"]["\2"]', r)
        r = re.sub(r"(?<![\w.])(" + "|".join(_FNS) + r")\(", r"F.\1(", r)
        py.append(f"    {name} = {r}")
    return AD.lift_py("\n".join(py) + "\n")


# ------------------------------------------------------------------ dbt-style Jinja templates
def lower_j2(spec, style=None, input_ref="raw"):
    s = ir.lower_sql(spec, style)
    s = re.sub(r"\bFROM raw\b", "FROM {{ ref('" + input_ref + "') }}", s, flags=re.I)
    return "{{ config(materialized='table') }}\n" + s


def render_j2(text):
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    return env.from_string(text).render(ref=lambda name: "raw", config=lambda **k: "")


# ------------------------------------------------------------------ dispatch
def lower(spec, lang, style=None):
    if lang in ("sql",):
        return ir.lower_sql(spec, style)
    if lang in ("hive", "postgres", "snowflake"):
        return ";\n".join(sqlglot.transpile(ir.lower_sql(spec, style), read="sqlite", write=lang)) + ";\n"
    if lang == "duckdb":
        return lower_duckdb(spec, style)
    if lang == "py":
        return ir.lower_py(spec, style)
    if lang == "j2":
        return lower_j2(spec, style)
    if lang == "scala":
        return lower_scala(spec, style)
    raise ValueError(lang)


def lift(text, lang):
    if lang == "sql":
        return norm_spec(AD.lift_sql(text))
    if lang in ("hive", "postgres", "snowflake"):
        try:
            back = ";\n".join(sqlglot.transpile(text, read=lang, write="sqlite"))
        except sqlglot.errors.ParseError as e:
            raise AD.Unsupported(f"{lang} parse error: {str(e)[:80]}")
        return norm_spec(AD.lift_sql(back))
    if lang == "py":
        return norm_spec(AD.lift_py(text))
    if lang == "j2":
        return norm_spec(AD.lift_sql(render_j2(text)))
    if lang == "scala":
        return norm_spec(lift_scala(text))
    raise AD.Unsupported(f"cannot lift {lang}")
