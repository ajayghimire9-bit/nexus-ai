"""Phase 14 metered runner: matched Fixed / Random / Untrained / Trained arms on held-out multi-stage DAG pipelines lifted from
NATIVE sources across engines (NOT LOCKED; engineering machinery, not NEXUS learning).

WHAT THIS RUNNER DOES
  1  DAG SPECS        seven layered pipelines (stg_ -> int_ -> fct_; every stg_ node is 50+ columns wide) with injected faults:
                        D1_count_col (source) int_ COUNT(*) -> COUNT(v); D2_left_lookup (held out) int_ INNER -> LEFT JOIN;
                        D3_null_default (source) stg_ y = x -> COALESCE(x, 0); D4_filter_boundary (held out) int_ > -> >=;
                        D5_lookup_two_faults (held out) INNER JOIN + fct_ tier passthrough; D6_sum_measure (source) fct_ COUNT(*) ->
                        SUM(amt); D7_revenue_sum (held out) fct_ COUNT(*) -> SUM(revenue) over a renamed schema.
                      3 observed + 2 hidden batches per instance; the reference pipeline is reachable only as a budgeted oracle.
  2  NATIVE FRONTS    every spec carries ENGINEER-AUTHORED source text for its broken and reference DAG (written as SQL text / Polars /
                      PySpark method chains, NOT produced by the AST compiler). --fronts (default sql:sqlite,df:polars):
                        sql:<dialect>      authored SQL lifted with multi_engine14.from_sql; lifted broken AND reference must reproduce
                                           the spec pipelines on every batch (else build error: parser drift is never accepted).
                        df:<api>           authored DataFrame code lifted with multi_engine14.from_dataframe (parsed, never executed).
                                           The lifted authored REFERENCE is the ground truth ONLY when REFERENCE FIDELITY holds (the
                                           original reference source executed natively on every observed and hidden batch agrees
                                           with core11 on the lifted reference, fail-closed). Drift against the spec ASTs and fault
                                           observability are recorded per instance.
                        compiled_sql:<d>   diagnostic: compiler-generated SQL round trip (machine-written; not counted as native front).
                        ast                diagnostic: no native source.
  3  REFERENCE GATE   make_instance runs dag_repair14.source_fidelity on the lifted REFERENCE over all batches. 'unfaithful' (the
                      authored reference provably differs from its lift) is a build error (exit 1). 'unverified' (e.g. the engine is not
                      installed) marks the instance reference_gradable=False: grade() refuses it (graded=False), so such a row is never
                      counted verified NOR wrong (row field 'ungraded').
  4  FIDELITY GATE    solve runs the fail-closed native-source fidelity (dag_repair14._fidelity) on the ROW budget BEFORE either repair
                      path. The learned-operator path runs only on an established-faithful source; otherwise repair_dag runs and stops
                      (fidelity_unverified / unfaithful_parse). An unavailable engine never establishes fidelity.
  5  OPERATORS        verified source repairs are anti-unified into executable rewrite operators (OperatorLibrary; admitted when
                      verified - wrong >= OP_ADMIT). operator_stage executes them (single sites + depth-2 compositions on distinct nodes),
                      requires fit on every observed batch, splits survivors with probes + budgeted queries, challenges a lone survivor,
                      and accepts only after dag_repair14.verify_downstream (WITH the required engines) and a clean re-localisation.
  6  ONE ROW BUDGET   solve holds ONE strict synth12 Budget and ONE query allowance per row: fidelity, the operator stage (fork, merged),
                      then repair_dag on the SAME budget and query list. over_cap is computed on the row budget's total work.
  7  REQUIRED ENGINES the effective required engines (cfg['required_engines']; auto = sqlite + installed engines of --engines) are passed
                      to BOTH repair paths: verify_downstream executes the WHOLE repaired DAG natively on every required engine on the
                      shared row budget BEFORE a repair is accepted. An unavailable / disagreeing / erroring / unchecked required engine
                      fails 'required_engine_dag' and the repair is not submitted. Grading repeats the whole-DAG check on hidden batches.
  8  TRAINING         per stream an independent Selector, no-regret Selector, DeltaStateGuide and OperatorLibrary learn from source
                      episodes on --train-front (SourceMeter charged BEFORE use); all are frozen and fingerprinted.
  9  ARMS             fixed / random (static menu) | untrained (program-aware, uniform) | trained (frozen selector, prior, guide,
                      operators) + ablations trained_no_ops and trained_no_regret + single_shot (diagnostic heuristic, not an LLM).
 10  GRADING          verified = submitted AND reference gradable AND core11 matches every reference stage on every hidden batch AND
                      native SQLite pipeline agreement AND whole-DAG native agreement on every required engine.
 11  ACCEPTANCE       capability_acceptance is BLOCKING by default (exit 1; --advisory-acceptance makes it report-only): every charter
                      metric > 0 in every stream, a non-SQLite required engine, an authored SQL front, a DataFrame front whose engine is
                      installed, and >= 1 verified row on every native front.
 12  CHECKS           exit 1 on over-cap rows, isolation failure, supervision overrun, error rows / episodes, build errors, unavailable
                      required engines, failed conformance suite or failed (enforced) capability acceptance. Exit 2: no rows.

ATTRIBUTION  all of this is engineering machinery (authored sources, anti-unification rule, matcher, probe rule, admission threshold,
specs). NEXUS learns only selector weights, tag prior, no-regret weights, guide counts and admitted operators during source training."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
import random
import sys
import time
import traceback
from collections import Counter
from decimal import Decimal
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from nexus.de_phase11 import core11 as C                               # noqa: E402
from nexus.de_phase12 import synth12 as S12                            # noqa: E402
from nexus.de_phase13 import pipeline_lifter13 as L                    # noqa: E402
from nexus.de_phase13 import proposals13 as P                          # noqa: E402
from nexus.de_phase13 import selector13 as S13                         # noqa: E402
from nexus.de_phase14 import ARMS, WORK_CAPS, engine_availability, engine_available  # noqa: E402
from nexus.de_phase14 import dag_repair14 as D                         # noqa: E402
from nexus.de_phase14 import multi_engine14 as ME                      # noqa: E402

STREAMS = ("rep0", "rep1")
COMPARATORS = ("fixed", "random", "untrained")
ABLATION, NO_REGRET = "trained_no_ops", "trained_no_regret"
ABLATIONS = (ABLATION, NO_REGRET)
SOURCE_BASE, EVAL_BASE = 1410000, 142000
SOURCE_CAPS = dict(ref_answers=(512, 6000), grade_execs=(16, 400))
WORK_KEYS = ("full_checks", "probe_evals", "rel_evals", "micro_evals", "constructed_asts")
FC_MAX = 5000
FILL = tuple(f"f{i:02d}" for i in range(50))
F_SQL = ", ".join(FILL)
SUBSETS = ("all", "beyond_single_edit", "held_out")
FRONT_KINDS = ("sql", "df", "compiled_sql", "ast")
NATIVE_KINDS = ("sql", "df")
DEFAULT_FRONTS = ("sql:sqlite", "df:polars")
PROGRESSION_KEYS = ("learning_to_learn_gain", "transfer_efficiency", "self_evolution_delta", "unseen_domain_reuse_rate",
                    "enterprise_reliability_advantage")
OP_ADMIT, OP_SHARE, OP_CAND_CAP, OP_BEAM, OP_PROBE_CAP = 1, 0.4, 192, 4, 96
_AGG_KINDS = ("count_star", "count", "sum", "min", "max", "avg")


def _exc(e):
    """Error record with a traceback tail (so the coordinator's stdout tail can diagnose the failure)."""
    return dict(error=f"{type(e).__name__}: {str(e)[:200]}", traceback=traceback.format_exc()[-1500:])


def _required(cfg):
    """Effective required engines of a configuration (never empty: dag_repair14.DEFAULT_REQUIRED when unset)."""
    return tuple(cfg.get("required_engines") or D.DEFAULT_REQUIRED)


# ------------------------------------------------------------------ AST helpers and specs
def _col(c):
    return ("col", c)


def _k(v, t):
    return ("const", v, t)


def _pass(cols):
    return tuple((c, _col(c)) for c in cols)


def _fill(rng):
    return tuple(rng.randrange(10) for _ in FILL)


def _rel(cols, types, rows):
    return ME.make_rel(cols, types, rows)


def _coalesce(c, v, t):
    return ("branch", ("isnull", _col(c)), _k(v, t), _col(c))


class _Df:
    """Small writing helper for the engineer-authored Polars / PySpark source text (plain string formatting, no compiler)."""

    def __init__(self, api):
        self.p = api == "polars"

    def col(self, c):
        return f"{'pl' if self.p else 'F'}.col({c!r})"

    def sel(self, frame, items):
        return f"{frame}.select({', '.join(items)})"

    def names(self, cols):
        return [repr(c) for c in cols]

    def star(self):
        return "pl.len()" if self.p else "F.count(F.lit(1))"

    def agg(self, kind, c):
        return f"pl.col({c!r}).{kind}()" if self.p else f"F.{kind}({c!r})"

    def group(self, frame, key, agg, name):
        return f"{frame}.{'group_by' if self.p else 'groupBy'}({key!r}).agg({agg}.alias({name!r}))"

    def fill(self, c, v):
        return f"pl.col({c!r}).fill_null({v!r})" if self.p else f"F.coalesce(F.col({c!r}), F.lit({v!r}))"

    def join(self, l, r, lk, rk, how):
        if self.p:
            return f"{l}.join({r}, left_on={lk!r}, right_on={rk!r}, how={how!r})"
        return f"{l}.join({r}, {l}[{lk!r}] == {r}[{rk!r}], {how!r})"

    def where(self, frame, c, op, v):
        return f"{frame}.filter({self.col(c)} {op} {v!r})"


def _build_d1(broken):
    cols = ("eid", "g", "v", "w") + FILL
    meas = (("n", "count_star", None),) if broken else (("n", "count", _col("v")),)
    return [("stg_events", ("map", ("rel", "raw_events"), _pass(cols))),
            ("int_counts", ("fold", ("rel", "stg_events"), ("g",), meas)),
            ("fct_counts", ("map", ("rel", "int_counts"), (("g", _col("g")), ("n", _col("n")))))]


def _sql_d1(broken):
    return [("stg_events", f"SELECT eid, g, v, w, {F_SQL} FROM raw_events"),
            ("int_counts", f"SELECT g, {'COUNT(*)' if broken else 'COUNT(v)'} AS n FROM stg_events GROUP BY g"),
            ("fct_counts", "SELECT g, n FROM int_counts")]


def _df_d1(broken, api):
    d = _Df(api)
    return [("stg_events", d.sel("raw_events", d.names(("eid", "g", "v", "w") + FILL))),
            ("int_counts", d.group("stg_events", "g", d.star() if broken else d.agg("count", "v"), "n")),
            ("fct_counts", d.sel("int_counts", d.names(("g", "n"))))]


def _gen_d1(rng, mode):
    n = rng.randint(6, 9)
    v = [None if rng.random() < 0.35 else rng.randint(1, 50) for _ in range(n)]
    v[rng.randrange(n)] = None
    if all(x is None for x in v):
        v[0] = 7
    if mode == "obs":
        w = [None if x is None else rng.randint(1, 50) for x in v]
    else:
        w = [None if rng.random() < 0.35 else rng.randint(1, 50) for _ in range(n)]
        j = rng.randrange(n)
        w[j] = 3 if v[j] is None else None                             # hidden: null pattern of w differs from v
    rows = [(i, rng.choice("abc"), v[i], w[i]) + _fill(rng) for i in range(n)]
    return {"raw_events": _rel(("eid", "g", "v", "w") + FILL, (C.INT, C.STR, C.INT, C.INT) + (C.INT,) * len(FILL), rows)}


def _build_d2(broken):
    ocols = ("oid", "cid", "amt") + FILL
    return [("stg_orders", ("map", ("rel", "raw_orders"), _pass(ocols))),
            ("stg_custs", ("map", ("rel", "raw_custs"), _pass(("cust_id", "tier")))),
            ("int_enriched", ("join", "inner" if broken else "left", ("rel", "stg_orders"), ("rel", "stg_custs"), ("cid",),
                              ("cust_id",))),
            ("fct_tier", ("map", ("rel", "int_enriched"), (("oid", _col("oid")), ("amt", _col("amt")),
                                                           ("tier", _coalesce("tier", "none", C.STR)))))]


def _sql_d2(broken, tier_broken=False):
    return [("stg_orders", f"SELECT oid, cid, amt, {F_SQL} FROM raw_orders"),
            ("stg_custs", "SELECT cust_id, tier FROM raw_custs"),
            ("int_enriched", f"SELECT * FROM stg_orders AS o {'INNER' if broken else 'LEFT'} JOIN stg_custs AS c ON o.cid = c.cust_id"),
            ("fct_tier", "SELECT oid, amt, " + ("tier" if tier_broken else "COALESCE(tier, 'none') AS tier") + " FROM int_enriched")]


def _df_d2(broken, api, tier_broken=False):
    d = _Df(api)
    tier = repr("tier") if tier_broken else f"{d.fill('tier', 'none')}.alias('tier')"
    return [("stg_orders", d.sel("raw_orders", d.names(("oid", "cid", "amt") + FILL))),
            ("stg_custs", d.sel("raw_custs", d.names(("cust_id", "tier")))),
            ("int_enriched", d.join("stg_orders", "stg_custs", "cid", "cust_id", "inner" if broken else "left")),
            ("fct_tier", d.sel("int_enriched", d.names(("oid", "amt")) + [tier]))]


def _gen_d2(rng, mode):
    custs = [(cid, rng.choice(["gold", "silver", None])) for cid in range(10, 16)]
    n = rng.randint(6, 9)
    cids = [rng.randint(10, 14) for _ in range(n)]
    a, b = rng.sample(range(n), 2)
    cids[a], cids[b] = 90 + rng.randrange(9), None
    rows = [(i, cids[i], round(rng.uniform(1, 99), 2)) + _fill(rng) for i in range(n)]
    return {"raw_orders": _rel(("oid", "cid", "amt") + FILL, (C.INT, C.INT, C.NUM) + (C.INT,) * len(FILL), rows),
            "raw_custs": _rel(("cust_id", "tier"), (C.INT, C.STR), custs)}


def _build_d5(broken):
    stages = _build_d2(broken)
    if broken:
        stages[3] = ("fct_tier", ("map", ("rel", "int_enriched"), (("oid", _col("oid")), ("amt", _col("amt")),
                                                                   ("tier", _col("tier")))))
    return stages


def _sql_d5(broken):
    return _sql_d2(broken, tier_broken=broken)


def _df_d5(broken, api):
    return _df_d2(broken, api, tier_broken=broken)


def _build_d3(broken):
    y = _col("x") if broken else _coalesce("x", 0, C.INT)
    items = (("rid", _col("rid")), ("sensor", _col("sensor")), ("y", y)) + _pass(FILL)
    return [("stg_readings", ("map", ("rel", "raw_readings"), items)),
            ("int_sensor", ("fold", ("rel", "stg_readings"), ("sensor",), (("total", "sum", _col("y")),))),
            ("fct_sensor", ("map", ("rel", "int_sensor"), (("sensor", _col("sensor")), ("total", _col("total")))))]


def _sql_d3(broken):
    return [("stg_readings", f"SELECT rid, sensor, {'x' if broken else 'COALESCE(x, 0)'} AS y, {F_SQL} FROM raw_readings"),
            ("int_sensor", "SELECT sensor, SUM(y) AS total FROM stg_readings GROUP BY sensor"),
            ("fct_sensor", "SELECT sensor, total FROM int_sensor")]


def _df_d3(broken, api):
    d = _Df(api)
    y = f"{d.col('x') if broken else d.fill('x', 0)}.alias('y')"
    return [("stg_readings", d.sel("raw_readings", d.names(("rid", "sensor")) + [y] + d.names(FILL))),
            ("int_sensor", d.group("stg_readings", "sensor", d.agg("sum", "y"), "total")),
            ("fct_sensor", d.sel("int_sensor", d.names(("sensor", "total"))))]


def _gen_d3(rng, mode):
    n = rng.randint(6, 9)
    x = [None if rng.random() < 0.3 else rng.randint(-5, 20) for _ in range(n)]
    x[rng.randrange(n)] = None
    rows = [(i, rng.choice(["s1", "s2", "s3"]), x[i]) + _fill(rng) for i in range(n)]
    return {"raw_readings": _rel(("rid", "sensor", "x") + FILL, (C.INT, C.STR, C.INT) + (C.INT,) * len(FILL), rows)}


def _build_d4(broken):
    cols = ("pid", "acct", "amt") + FILL
    return [("stg_payments", ("map", ("rel", "raw_payments"), _pass(cols))),
            ("int_large", ("filter", ("rel", "stg_payments"), ("cmp", "gt" if broken else "ge", _col("amt"), _k(100, C.INT)))),
            ("fct_large", ("fold", ("rel", "int_large"), ("acct",), (("n", "count_star", None),)))]


def _sql_d4(broken):
    return [("stg_payments", f"SELECT pid, acct, amt, {F_SQL} FROM raw_payments"),
            ("int_large", f"SELECT * FROM stg_payments WHERE amt {'>' if broken else '>='} 100"),
            ("fct_large", "SELECT acct, COUNT(*) AS n FROM int_large GROUP BY acct")]


def _df_d4(broken, api):
    d = _Df(api)
    return [("stg_payments", d.sel("raw_payments", d.names(("pid", "acct", "amt") + FILL))),
            ("int_large", d.where("stg_payments", "amt", ">" if broken else ">=", 100)),
            ("fct_large", d.group("int_large", "acct", d.star(), "n"))]


def _gen_d4(rng, mode):
    n = rng.randint(6, 9)
    amts = [rng.choice([50, 99, 100, 101, 150, rng.randint(0, 200)]) for _ in range(n)]
    amts[rng.randrange(n)] = 100
    rows = [(i, rng.choice("ABC"), amts[i]) + _fill(rng) for i in range(n)]
    return {"raw_payments": _rel(("pid", "acct", "amt") + FILL, (C.INT, C.STR, C.INT) + (C.INT,) * len(FILL), rows)}


def _build_d6(broken):
    cols = ("pid", "acct", "amt") + FILL
    meas = (("total", "count_star", None),) if broken else (("total", "sum", _col("amt")),)
    return [("stg_payments", ("map", ("rel", "raw_payments"), _pass(cols))),
            ("int_amounts", ("map", ("rel", "stg_payments"), (("acct", _col("acct")), ("amt", _col("amt"))))),
            ("fct_totals", ("fold", ("rel", "int_amounts"), ("acct",), meas))]


def _sql_d6(broken):
    return [("stg_payments", f"SELECT pid, acct, amt, {F_SQL} FROM raw_payments"),
            ("int_amounts", "SELECT acct, amt FROM stg_payments"),
            ("fct_totals", f"SELECT acct, {'COUNT(*)' if broken else 'SUM(amt)'} AS total FROM int_amounts GROUP BY acct")]


def _df_d6(broken, api):
    d = _Df(api)
    return [("stg_payments", d.sel("raw_payments", d.names(("pid", "acct", "amt") + FILL))),
            ("int_amounts", d.sel("stg_payments", d.names(("acct", "amt")))),
            ("fct_totals", d.group("int_amounts", "acct", d.star() if broken else d.agg("sum", "amt"), "total"))]


def _gen_d6(rng, mode):
    n = rng.randint(6, 9)
    amts = [rng.randint(2, 60) for _ in range(n)]
    if mode == "hidden":
        amts[rng.randrange(n)] = None                                  # hidden: SUM skips NULL, COUNT(*) does not
    rows = [(i, rng.choice("ABC"), amts[i]) + _fill(rng) for i in range(n)]
    return {"raw_payments": _rel(("pid", "acct", "amt") + FILL, (C.INT, C.STR, C.INT) + (C.INT,) * len(FILL), rows)}


def _build_d7(broken):
    cols = ("sid", "region", "revenue", "units") + FILL
    meas = (("revenue_total", "count_star", None),) if broken else (("revenue_total", "sum", _col("revenue")),)
    return [("stg_sales", ("map", ("rel", "raw_sales"), _pass(cols))),
            ("int_sales", ("map", ("rel", "stg_sales"), _pass(("region", "revenue", "units")))),
            ("fct_region", ("fold", ("rel", "int_sales"), ("region",), meas))]


def _sql_d7(broken):
    return [("stg_sales", f"SELECT sid, region, revenue, units, {F_SQL} FROM raw_sales"),
            ("int_sales", "SELECT region, revenue, units FROM stg_sales"),
            ("fct_region", f"SELECT region, {'COUNT(*)' if broken else 'SUM(revenue)'} AS revenue_total FROM int_sales GROUP BY region")]


def _df_d7(broken, api):
    d = _Df(api)
    return [("stg_sales", d.sel("raw_sales", d.names(("sid", "region", "revenue", "units") + FILL))),
            ("int_sales", d.sel("stg_sales", d.names(("region", "revenue", "units")))),
            ("fct_region", d.group("int_sales", "region", d.star() if broken else d.agg("sum", "revenue"), "revenue_total"))]


def _gen_d7(rng, mode):
    n = rng.randint(6, 9)
    rev = [rng.randint(20, 80) for _ in range(n)]                     # revenue sums exceed every count / units / filler sum
    units = [rng.randint(1, 4) for _ in range(n)]
    if mode == "hidden":
        rev[rng.randrange(n)] = None
        units[rng.randrange(n)] = None
    rows = [(i, rng.choice(["north", "south", "east"]), rev[i], units[i]) + _fill(rng) for i in range(n)]
    return {"raw_sales": _rel(("sid", "region", "revenue", "units") + FILL, (C.INT, C.STR, C.INT, C.INT) + (C.INT,) * len(FILL), rows)}


def _spec(id_, name, held_out, faults, observed, build, gen, n_edits, edit_reachable, sql, df):
    return dict(id=id_, name=name, held_out=held_out, fault=faults[0], faults=tuple(faults), observed=tuple(observed), build=build,
                gen=gen, n_edits=n_edits, beyond_single_edit=n_edits != 1 or not edit_reachable, edit_reachable=edit_reachable,
                sql=sql, df=df)


SPECS = (
    _spec(0, "D1_count_col", False, ("int_counts",), ("stg_events", "fct_counts"), _build_d1, _gen_d1, 1, True, _sql_d1, _df_d1),
    _spec(1, "D2_left_lookup", True, ("int_enriched",), ("stg_orders", "stg_custs", "fct_tier"), _build_d2, _gen_d2, 1, True,
          _sql_d2, _df_d2),
    _spec(2, "D3_null_default", False, ("stg_readings",), ("stg_readings", "fct_sensor"), _build_d3, _gen_d3, 1, True, _sql_d3, _df_d3),
    _spec(3, "D4_filter_boundary", True, ("int_large",), ("stg_payments", "fct_large"), _build_d4, _gen_d4, 1, True, _sql_d4, _df_d4),
    _spec(4, "D5_lookup_two_faults", True, ("int_enriched", "fct_tier"), ("stg_orders", "stg_custs", "int_enriched", "fct_tier"),
          _build_d5, _gen_d2, 2, True, _sql_d5, _df_d5),
    _spec(5, "D6_sum_measure", False, ("fct_totals",), ("stg_payments", "int_amounts", "fct_totals"), _build_d6, _gen_d6, 1, False,
          _sql_d6, _df_d6),
    _spec(6, "D7_revenue_sum", True, ("fct_region",), ("stg_sales", "int_sales", "fct_region"), _build_d7, _gen_d7, 1, False,
          _sql_d7, _df_d7),
)


def source_seed(si, spec_id, i):
    return SOURCE_BASE + 10000 * si + 100 * spec_id + i


def eval_seed(spec_id, i):
    return EVAL_BASE + 100 * spec_id + i


def seed_overlap(source_instances, eval_instances):
    src = {source_seed(si, s["id"], i) for si in range(len(STREAMS)) for s in SPECS if not s["held_out"]
           for i in range(source_instances)}
    ev = {eval_seed(s["id"], i) for s in SPECS for i in range(eval_instances)}
    return sorted(src & ev)


# ------------------------------------------------------------------ native fronts
def parse_front(front, dialect="sqlite", api="polars"):
    """'sql[:dialect]' | 'df[:api]' | 'compiled_sql[:dialect]' | 'ast' -> (kind, variant)."""
    kind, _, var = str(front).partition(":")
    if kind in ("sql", "compiled_sql"):
        var = var or dialect
        if var not in D.SQL_ENGINE:
            raise ValueError(f"unknown SQL dialect {var!r}")
        return kind, var
    if kind == "df":
        var = var or api
        if var not in D.DF_ENGINE:
            raise ValueError(f"unknown DataFrame api {var!r}")
        return kind, var
    if kind == "ast" and not var:
        return "ast", None
    raise ValueError(f"unknown front {front!r}")


def front_engine(front):
    kind, var = parse_front(front)
    return D.SQL_ENGINE[var] if kind in ("sql", "compiled_sql") else D.DF_ENGINE.get(var)


def _differs(a, b, inputs):
    """Stage names whose outputs differ between pipelines a and b on any input batch."""
    bad = []
    for inp in inputs:
        oa, _ = a.run(inp)
        ob, _ = b.run(inp)
        bad += [n for n in a.names() if n not in bad and not L._same(oa.get(n), ob.get(n))]
    return bad


def _lift_native(broken, batches, dialect):
    """Diagnostic compiled front: compile the broken pipeline to SQL text in `dialect`, then LIFT it back (lift_sources)."""
    env, srcs = dict(batches[0]["inputs"]), []
    for st in broken.stages:
        srcs.append(dict(name=st["name"], sql=ME.to_engine_sql(st["ast"], dialect, L._cols_fn(dict(env))), dialect=dialect))
        R = L._run(st["ast"], env)
        if R is not None:
            env[st["name"]] = R
    lifted = D.lift_sources(srcs, batches[0]["inputs"])
    bad = _differs(broken, lifted, [b["inputs"] for b in batches])
    if bad:
        raise RuntimeError(f"lifted {dialect} pipeline differs from its source: {bad}")
    return srcs, lifted


def reference_fidelity(lref, inputs):
    """Fail-closed fidelity of the LIFTED REFERENCE: its ORIGINAL authored sources run natively on every observed and hidden batch
    and are compared with core11 on the lifted reference (evaluation-side, not learner work: not metered)."""
    fid = D.source_fidelity(lref, [dict(name=f"in{k}", inputs=inp, observed={}) for k, inp in enumerate(inputs)])
    return dict(checked=fid.get("checked"), faithful=bool(fid.get("faithful")), reason=fid.get("reason"), tally=fid.get("tally"),
                engines=fid.get("engines"))


def make_instance(spec, seed, n_obs=3, n_hidden=2, front="ast", dialect="sqlite", api="polars"):
    kind, var = parse_front(front, dialect, api)
    rng = random.Random(seed)
    inputs = [spec["gen"](rng, "obs" if k < n_obs else "hidden") for k in range(n_obs + n_hidden)]
    ref, broken = L.Pipeline(spec["build"](False)), L.Pipeline(spec["build"](True))
    sources, lref = None, None
    info = dict(drift_broken=[], drift_reference=[], reference_fidelity=None, reference_gradable=True)
    if kind == "sql":                                                  # authored SQL must mean exactly the spec pipelines
        sources = [dict(name=n, sql=s, dialect=var) for n, s in spec["sql"](True)]
        lifted = D.lift_sources(sources, inputs[0])
        lref = D.lift_sources([dict(name=n, sql=s, dialect=var) for n, s in spec["sql"](False)], inputs[0])
        bad = [f"broken:{n}" for n in _differs(lifted, broken, inputs)] + [f"reference:{n}" for n in _differs(lref, ref, inputs)]
        if bad:
            raise RuntimeError(f"{spec['name']}: authored {var} SQL lifts to a different pipeline on {bad}")
        broken = lifted
    elif kind == "df":                                                 # the authored DataFrame reference is the ground truth
        sources = [dict(name=n, code=c, api=var) for n, c in spec["df"](True, var)]
        lifted = D.lift_sources(sources, inputs[0])
        lref = D.lift_sources([dict(name=n, code=c, api=var) for n, c in spec["df"](False, var)], inputs[0])
        info.update(drift_broken=_differs(lifted, broken, inputs), drift_reference=_differs(lref, ref, inputs))
        ref, broken = lref, lifted
    if lref is not None:                                               # the authored reference must mean its own lift (fail-closed)
        rf = reference_fidelity(lref, inputs)
        info["reference_fidelity"] = rf
        if rf["reason"] == "unfaithful":
            raise RuntimeError(f"{spec['name']}: authored {kind}:{var} REFERENCE disagrees natively with its lift: {rf['tally']}")
        if kind == "df":                                               # the lifted df reference is ground truth only when faithful
            info["reference_gradable"] = rf["faithful"]
    batches, hidden = [], []
    for k, inp in enumerate(inputs):
        outs, errs = ref.run(inp)
        if errs:
            raise RuntimeError(f"{spec['name']}: reference failed on batch {k}: {errs}")
        if k < n_obs:
            batches.append(dict(name=f"obs{k}", inputs=inp, observed={s: outs[s] for s in spec["observed"]}))
        else:
            hidden.append(dict(name=f"hid{k - n_obs}", inputs=inp, ref=outs))
    if kind == "compiled_sql":
        sources, broken = _lift_native(broken, batches, var)
    info["fault_observable"] = L.localize(broken, batches)["broken"] is not None
    return dict(spec=spec, seed=seed, task=f"{spec['name']}#{seed}@{kind}" + (f":{var}" if var else ""), reference=ref, broken=broken,
                batches=batches, hidden=hidden, oracle=L.pipeline_oracle(ref), front=kind if var is None else f"{kind}:{var}",
                sources=sources, front_info=info)


# ------------------------------------------------------------------ learned executable operators (machinery: anti-unification rule)
def _diff(a, b):
    """Minimal differing sub-AST pair: descend while exactly one child (a sub-tuple on both sides) differs."""
    while isinstance(a, tuple) and isinstance(b, tuple) and len(a) == len(b) and a != b:
        idx = [i for i in range(len(a)) if a[i] != b[i]]
        if len(idx) == 1 and isinstance(a[idx[0]], tuple) and isinstance(b[idx[0]], tuple):
            a, b = a[idx[0]], b[idx[0]]
            continue
        break
    return None if a == b else (a, b)


def _wild(a, b):
    if not (isinstance(a, tuple) and isinstance(b, tuple) and len(a) == len(b)):
        return a, b
    wa, wb, n = list(a), list(b), 0
    for i in range(len(a)):
        if a[i] == b[i] and isinstance(a[i], tuple) and not (len(a[i]) == 2 and a[i][0] == "col"):
            wa[i] = wb[i] = f"?t{n}"
            n += 1
    return tuple(wa), tuple(wb)


def _abstract(x, m):
    if isinstance(x, tuple):
        if len(x) == 2 and x[0] == "col" and isinstance(x[1], str):
            return ("col", m.setdefault(("c", x[1]), f"?c{sum(k[0] == 'c' for k in m)}"))
        if len(x) == 3 and isinstance(x[0], str) and not x[0].startswith("?") and x[1] in _AGG_KINDS:
            return (m.setdefault(("o", x[0]), f"?o{sum(k[0] == 'o' for k in m)}"), x[1], _abstract(x[2], m))
        return tuple(_abstract(y, m) for y in x)
    return x


def _vars(x, out=None):
    out = set() if out is None else out
    if isinstance(x, str) and x.startswith("?"):
        out.add(x)
    elif isinstance(x, tuple):
        for y in x:
            _vars(y, out)
    return out


def extract_operator(old, new):
    """Executable rewrite operator anti-unified from a broken / repaired node pair (None when nothing generalises)."""
    d = _diff(old, new)
    if d is None:
        return None
    a, b = _wild(*d)
    m = {}
    pat, rep = _abstract(a, m), _abstract(b, m)
    if not isinstance(pat, tuple):
        return None
    extra = _vars(rep) - _vars(pat)
    free = tuple(sorted(v for v in extra if v.startswith("?c")))
    if len(free) != len(extra) or len(free) > 2:
        return None
    return dict(key=repr((pat, rep)), pattern=pat, replacement=rep, free=free)


def _match(p, t, b):
    if isinstance(p, str) and p.startswith("?"):
        if p in b:
            return b[p] == t
        if (p.startswith("?o") and not isinstance(t, str)) or (p.startswith("?t") and not isinstance(t, tuple)) or p.startswith("?c"):
            return False
        b[p] = t
        return True
    if isinstance(p, tuple):
        if len(p) == 2 and p[0] == "col" and isinstance(p[1], str) and p[1].startswith("?c"):
            if not (isinstance(t, tuple) and len(t) == 2 and t[0] == "col" and isinstance(t[1], str)):
                return False
            if p[1] in b:
                return b[p[1]] == t[1]
            b[p[1]] = t[1]
            return True
        return isinstance(t, tuple) and len(t) == len(p) and all(_match(x, y, b) for x, y in zip(p, t))
    return p == t


def _inst(r, b):
    if isinstance(r, str) and r.startswith("?"):
        return b[r]
    if isinstance(r, tuple):
        if len(r) == 2 and r[0] == "col" and isinstance(r[1], str) and r[1].startswith("?c"):
            return ("col", b[r[1]])
        return tuple(_inst(y, b) for y in r)
    return r


def _sites(x, path=()):
    yield path, x
    if isinstance(x, tuple):
        for i, y in enumerate(x):
            if isinstance(y, tuple):
                yield from _sites(y, path + (i,))


def _replace(x, path, new):
    return new if not path else x[:path[0]] + (_replace(x[path[0]], path[1:], new),) + x[path[0] + 1:]


class OperatorLibrary:
    """Executable rewrite operators of graded source repairs with verified (+) / wrong (-) counts; admitted when +/- >= OP_ADMIT."""

    def __init__(self, name="operators"):
        self.ops, self.pos, self.neg, self.name, self.frozen, self.n = {}, Counter(), Counter(), name, False, 0

    def freeze(self):
        self.frozen = True
        return self

    def observe(self, old_ast, new_ast, verified):
        if self.frozen:
            raise S13.FrozenSelectorError(f"{self.name}: observe attempted on a frozen operator library (evaluation isolation)")
        op = extract_operator(old_ast, new_ast)
        if op is None:
            return None
        self.ops[op["key"]] = op
        (self.pos if verified else self.neg)[op["key"]] += 1
        self.n += 1
        return op["key"]

    def weight(self, key):
        return self.pos.get(key, 0) - self.neg.get(key, 0)

    def admitted(self):
        return [self.ops[k] for k in sorted(self.ops, key=lambda k: (-self.weight(k), k)) if self.weight(k) >= OP_ADMIT]

    def copy(self, name=None, frozen=False):
        new = OperatorLibrary(name or self.name)
        new.ops, new.n, new.frozen = dict(self.ops), self.n, frozen
        new.pos.update(self.pos)
        new.neg.update(self.neg)
        return new

    def learned_state(self):
        return dict(pos=dict(sorted(self.pos.items())), neg=dict(sorted(self.neg.items())), n=self.n)

    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.learned_state(), sort_keys=True).encode()).hexdigest()

    def to_dict(self):
        return dict(name=self.name, frozen=self.frozen, admitted=[o["key"] for o in self.admitted()], **self.learned_state())


# ------------------------------------------------------------------ operator stage (executes admitted operators; metered, fail-closed)
def _pkey(pipe):
    return tuple(st["ast"] for st in pipe.stages)


def _changed(a, b):
    return [s["name"] for s, s0 in zip(b.stages, a.stages) if s["ast"] != s0["ast"]]


def _bagfp(R):
    if R is None:
        return ("ERR",)
    cols = sorted(R.cols)
    idx = [list(R.cols).index(c) for c in cols]
    return (tuple(cols), frozenset(Counter(tuple(C.enc(r[j]) for j in idx) for r in R.rows).items()))


def _fits(pipe, B, obs, budget):
    """(fits every observed batch, mismatching observed stages on batch 0); one metered full check per batch; None if refused."""
    mism0 = 0
    for k, b in enumerate(B):
        if not L._charge(budget, "full_checks"):
            return None
        outs, _ = pipe.run(b["inputs"])
        bad = sum(1 for n in obs if n in b["observed"] and not L._same(outs.get(n), b["observed"][n]))
        mism0 = bad if k == 0 else mism0
        if bad:
            return False, mism0
    return True, mism0


def _rewrites(pipe, B, ops, budget, skip=()):
    """(candidates, complete). Every candidate AST is charged one constructed_ast BEFORE it is built."""
    out = []
    for i, st in enumerate(pipe.stages):
        if st["name"] in skip:
            continue
        env = L._upstream_env(pipe, B[0], i)
        cols = sorted({c for r in P._base_rels(st["ast"]) if r in env for c in env[r].cols})
        for op in ops:
            for path, sub in _sites(st["ast"]):
                bnd = {}
                if not _match(op["pattern"], sub, bnd):
                    continue
                for combo in itertools.product(*([cols] * len(op["free"]))):
                    if not L._charge(budget, "constructed_asts"):
                        return out, False
                    new = _replace(st["ast"], path, _inst(op["replacement"], dict(bnd, **dict(zip(op["free"], combo)))))
                    if new != st["ast"]:
                        out.append((pipe.replace(i, new, origin="op14"), [(st["name"], op["key"])]))
                    if len(out) >= OP_CAND_CAP:
                        return out, True
    return out, True


def _probes(surv, broken, B):
    facts, lists, bases = P.empty_facts(), [], []
    for pipe, _ in surv:
        for n in _changed(broken, pipe):
            P.program_facts(pipe.stages[pipe.index(n)]["ast"], facts)
    for b in B[:2]:
        bases.append((b["name"], b["inputs"]))
        lists += [P._props_for_base(b["name"], b["inputs"], facts), P.generic_proposals([(b["name"], b["inputs"])])]
    return P._dedupe(lists, OP_PROBE_CAP, bases)


def _score(surv, probes, obs, budget):
    rows = []
    for p in probes:
        fps = []
        for pipe, _ in surv:
            if not L._charge(budget, "probe_evals"):
                return rows, False
            outs, _ = pipe.run(p["env"])
            fps.append(tuple(_bagfp(outs.get(n)) for n in obs))
        rows.append((p, fps))
    return rows, True


def _ask(surv, env, stage, oracle, budget):
    try:
        E = oracle(stage, env)
    except Exception:                                                  # noqa: BLE001 - an external oracle failure ends querying
        E = None
    if E is None:
        return None
    keep = []
    for s in surv:
        if not L._charge(budget, "full_checks"):
            return None
        outs, _ = s[0].run(env)
        if L._same(outs.get(stage), E):
            keep.append(s)
    return keep


def operator_stage(broken, batches, ops, *, oracle=None, bq=0, fc_cap=2000, wall=5.0, engines=("sqlite",), budget=None,
                   queries_left=None, require_engines=D.DEFAULT_REQUIRED, dag_engines=()):
    """Execute admitted learned operators on the DAG; accept only a unique, challenged, downstream-verified repair (whole-DAG native
    execution on every required engine, metered on `budget`), else decline."""
    t0, B = time.time(), L._batches(batches)
    budget = budget if budget is not None else S12.Budget(wall=wall, fc_cap=fc_cap)
    qa = (queries_left if queries_left is not None else [int(bq)]) if oracle is not None else [0]
    q0 = qa[0]
    obs = [n for n in broken.names() if any(n in b["observed"] for b in B)]
    out = dict(status="declined", pipeline=None, changed_nodes=[], applied=[], candidates=0, survivors=0, queries=[], queries_used=0,
               invariants=None, agreement_unproven=False, max_width=0, required_engines=list(require_engines or ()),
               required_engine_dag={})

    def done(reason=None):
        out.update(reason=reason, queries_used=q0 - qa[0], work=dict(budget.c), exhausted=budget.exhausted,
                   wall=round(time.time() - t0, 3))
        return out
    if not ops or not B:
        return done("no_operators" if not ops else "no_batches")
    base = _fits(broken, B, obs, budget)
    if base is None or base[0]:
        return done("budget" if base is None else "no_fault")
    seen, surv, partial = {_pkey(broken)}, [], []

    def consider(pipe, app):
        if _pkey(pipe) in seen:
            return True
        seen.add(_pkey(pipe))
        out["candidates"] += 1
        r = _fits(pipe, B, obs, budget)
        if r is None:
            return False
        if r[0]:
            surv.append((pipe, app))
        elif r[1] < base[1]:
            partial.append((r[1], len(partial), pipe, app))
        return True
    cands, complete = _rewrites(broken, B, ops, budget)
    if not complete or not all(consider(p, a) for p, a in cands):
        return done("budget")
    if not surv:                                                       # depth-2 composition on a different node (multi-fault)
        for _, _, pipe, app in sorted(partial, key=lambda x: x[:2])[:OP_BEAM]:
            c2, ok2 = _rewrites(pipe, B, ops, budget, skip=[n for n, _ in app])
            if not ok2 or not all(consider(p2, app + a2) for p2, a2 in c2):
                return done("budget")
    out["survivors"] = len(surv)
    if not surv:
        return done("no_fitting_candidate")
    probes = _probes(surv, broken, B)
    while len(surv) > 1 and qa[0] > 0:
        scored, ok = _score(surv, probes, obs, budget)
        split = [(p, f) for p, f in scored if len(set(f)) > 1]
        if not ok or not split:
            break
        p, f = max(split, key=lambda pf: len(set(pf[1])))
        stage = next(obs[k] for k in reversed(range(len(obs))) if len({x[k] for x in f}) > 1)
        keep = _ask(surv, p["env"], stage, oracle, budget)
        if keep is None:
            return done("budget_or_oracle")
        qa[0] -= 1
        out["queries"].append(dict(phase="disambiguate", kind=p["kind"], stage=stage, before=len(surv), after=len(keep)))
        surv = keep
    if not surv:
        return done("all_falsified")
    if len(surv) > 1:                                                  # resolution test over the complete probe menu
        scored, ok = _score(surv, probes, obs, budget)
        if not ok:
            return done("incomplete_scoring")
        if any(len(set(f)) > 1 for _, f in scored):
            return done("unresolved_alternatives")
        out["agreement_unproven"] = True
    elif qa[0] > 0 and probes:                                         # challenge a lone survivor
        keep = _ask(surv, probes[0]["env"], obs[-1], oracle, budget)
        if keep is None:
            return done("budget_or_oracle")
        qa[0] -= 1
        out["queries"].append(dict(phase="challenge", kind=probes[0]["kind"], stage=obs[-1], before=1, after=len(keep)))
        if not keep:
            return done("challenge_falsified")
    pipe, app = min(surv, key=lambda s: (len(_changed(broken, s[0])), sum(L._size(st["ast"]) or 0 for st in s[0].stages)))
    changed = _changed(broken, pipe)
    inv = D.verify_downstream(broken, pipe, B, changed, budget=budget, engines=engines, dag_engines=dag_engines,
                              require_engines=require_engines)
    fin = L.localize(pipe, B, budget)
    out.update(changed_nodes=changed, applied=app, invariants=dict(ok=inv["ok"], failed=inv["failed"]), max_width=inv["max_width"],
               required_engines=inv["required_engines"], required_engine_dag={e: inv["dag_statuses"].get(e) for e in inv["required_engines"]})
    if not (inv["ok"] and fin["complete"] and fin["broken"] is None):
        return done("invariants_failed:" + ",".join(inv["failed"] or ["final_localization"]))
    out.update(status="repaired", pipeline=pipe)
    return done(None)


def _op_result(op, fidelity=None):
    keys = [k for _, k in op["applied"]]
    return dict(status="repaired", reason=None, pipeline=op["pipeline"], steps=[], changed_nodes=op["changed_nodes"],
                node_isolated=True, repaired_nodes=len(op["changed_nodes"]), operator_path=True,
                repair_methods=[dict(node=n, scope="node", mode="operator", method="operator", edge=[k for m, k in op["applied"] if m == n])
                                for n in op["changed_nodes"]],
                attribution=dict(learned=dict(library_functions=keys)), source_fidelity=fidelity,
                invariants=dict(ok=True, failed=[], max_width=op["max_width"]), required_engines=op.get("required_engines"),
                required_engine_dag=op.get("required_engine_dag"), exhausted=op["exhausted"], work=op["work"], over_cap=[],
                queries_used=op["queries_used"])


def solve(inst, bq, kw, cfg, wall, operators=None):
    """ONE strict row budget and ONE query allowance: native-source fidelity gate (fail-closed, before EITHER repair path), the
    operator stage in a fork (merged back, only on a faithful source), then repair_dag on the SAME budget. Both repair paths verify
    the whole repaired DAG natively on every REQUIRED engine (cfg['required_engines']) on that budget before accepting."""
    budget = S12.Budget(wall=wall, fc_cap=cfg["fc_cap"])
    oracle = inst["oracle"] if bq > 0 else None
    ql = [int(bq) if oracle is not None else 0]
    req = _required(cfg)
    q0, op, res, fid, gate = ql[0], None, None, None, None
    if inst.get("sources"):
        fid = D._fidelity(inst["broken"], inst["batches"], budget)
        gate = L._fidelity_stop(fid)
    if operators and gate is None:
        el, fc_now = time.time() - budget.t0, budget.c["full_checks"]
        ob = budget.fork(fc_cap=fc_now + max(1, int(OP_SHARE * (budget.fc_cap - fc_now))), wall=el + OP_SHARE * max(0.0, budget.wall - el))
        op = operator_stage(inst["broken"], inst["batches"], operators, oracle=oracle, engines=cfg["invariant_engines"], budget=ob,
                            queries_left=ql, require_engines=req)
        L._merge(budget, ob)
        if op["status"] == "repaired":
            res = _op_result(op, None if fid is None else {k: v for k, v in fid.items() if k != "rows"})
    if res is None:
        res = D.repair_dag(inst["broken"], inst["batches"], oracle=oracle, budget=budget, queries_left=ql,
                           engines=cfg["invariant_engines"], require_engines=req, **kw)
    res.update(row_work={k: int(v) for k, v in budget.c.items()}, row_queries=q0 - ql[0], row_exhausted=budget.exhausted,
               fidelity_gate=gate)
    return res, op


def _combined(res, bq, fc_cap):
    work = {k: int(res["row_work"].get(k, 0)) for k in WORK_KEYS}
    q = res["row_queries"]
    caps = dict(WORK_CAPS, full_checks=fc_cap)
    over = sorted(set(res.get("over_cap") or []) | {k for k, c in caps.items() if work.get(k, 0) > c}) + (["queries"] if q > bq else [])
    return work, q, over


# ------------------------------------------------------------------ source supervision meter
class SourceMeter:
    """Privileged source supervision, charged BEFORE use; a refusal skips the learning / grading step."""

    def __init__(self, caps=SOURCE_CAPS):
        self.caps, self.stream, self.ep, self.max_ep, self.refused = dict(caps), Counter(), Counter(), Counter(), Counter()

    def new_episode(self):
        self.ep = Counter()

    def charge(self, unit, n=1):
        per_ep, per_stream = self.caps[unit]
        if self.ep[unit] + n > per_ep or self.stream[unit] + n > per_stream:
            self.refused[unit] += 1
            return False
        self.ep[unit] += n
        self.stream[unit] += n
        self.max_ep[unit] = max(self.max_ep[unit], self.ep[unit])
        return True

    def over(self):
        return sorted(u for u, (pe, ps) in self.caps.items() if self.stream[u] > ps or self.max_ep[u] > pe)

    def report(self):
        return dict(used=dict(self.stream), max_per_episode=dict(self.max_ep), refused=dict(self.refused), caps=self.caps,
                    over=self.over())


# ------------------------------------------------------------------ grading (evaluation only; not learner work)
def _plain(v):
    if isinstance(v, Decimal):
        return int(v) if v.is_finite() and v == v.to_integral_value() else float(v)
    return v


def engine_dag(pipeline, inputs, engine, ref):
    """Execute the WHOLE pipeline natively on one engine (each stage reading that engine's OWN upstream outputs) and compare every
    stage with the reference outputs. 'unavailable' engines are skipped (never agreement)."""
    if not engine_available(engine):
        return dict(engine=engine, status="unavailable", stages=0)
    core, _ = pipeline.run(inputs)
    env, n = dict(inputs), 0
    for st in pipeline.stages:
        name, R0, E = st["name"], core.get(st["name"]), ref.get(st["name"])
        if R0 is None or E is None:
            return dict(engine=engine, status="core_error", stage=name, stages=n)
        r = ME.run_engine(engine, st["ast"], {x: env[x] for x in P._base_rels(st["ast"]) if x in env})
        if r["status"] != "ok":
            return dict(engine=engine, status=r["status"], stage=name, detail=r["detail"], stages=n)
        if not ME.bag_equal(r["names"], r["rows"], E):
            return dict(engine=engine, status="disagree", stage=name, stages=n)
        types = dict(zip(R0.cols, R0.types))
        try:
            env[name] = ME.make_rel(r["names"], [types[c] for c in r["names"]],
                                    [tuple(ME._coerce(_plain(v), types[c]) for v, c in zip(row, r["names"])) for row in r["rows"]])
        except (KeyError, TypeError, ValueError, L.SqlUnsupported) as e:
            return dict(engine=engine, status="error", stage=name, detail=f"{type(e).__name__}: {str(e)[:120]}", stages=n)
        n += 1
    return dict(engine=engine, status="agree", stages=n)


def grade(inst, pipeline, meter=None, engines=(), required=()):
    """Hidden-batch grading. An instance whose lifted reference is not established-faithful to its authored source is NOT graded
    (graded=False, reason 'reference_fidelity_unverified'): it is never counted verified nor wrong."""
    if not (inst.get("front_info") or {}).get("reference_gradable", True):
        return dict(graded=False, verified=False, core_ok=None, native_ok=None, engine_dag={}, multi_engine_verified=False,
                    reason="reference_fidelity_unverified")
    core_ok, nb = True, []
    for h in inst["hidden"]:
        if meter is not None and not meter.charge("grade_execs"):
            return dict(graded=False, verified=False, core_ok=None, native_ok=None, engine_dag={}, multi_engine_verified=False,
                        reason="supervision_refused")
        outs, _ = pipeline.run(h["inputs"])
        for s, R in h["ref"].items():
            if R is None or not L._same(outs.get(s), R):
                core_ok = False
        nb.append(dict(name=h["name"], inputs=h["inputs"], observed={s: R for s, R in h["ref"].items() if R is not None}))
    nat = L.native_pipeline_check(pipeline, nb)
    native_ok, ed = bool(nat["all_agree"]), {}
    for e in dict.fromkeys(tuple(required) + tuple(engines)):
        if not (core_ok and native_ok):
            ed[e] = "skipped" if engine_available(e) else "unavailable"
            continue
        sts = [engine_dag(pipeline, h["inputs"], e, h["ref"])["status"] for h in inst["hidden"]]
        ed[e] = next((s for s in sts if s != "agree"), "agree")
    verified = core_ok and native_ok and all(ed.get(e) == "agree" for e in required)
    multi = verified and any(v == "agree" for e, v in ed.items() if e != "sqlite") and \
        all(v in ("agree", "unavailable") for v in ed.values())
    return dict(graded=True, core_ok=core_ok, native_ok=native_ok, verified=verified, native_tally=nat["tally"], engine_dag=ed,
                multi_engine_verified=multi, reason=None)


# ------------------------------------------------------------------ source training
def _fp(R, outn):
    if R is None:
        return None
    if set(R.cols) != set(outn):
        R = D.project(R, list(outn))
        if R is None:
            return ("SCHEMA",)
    if len(R.cols) != len(outn):
        return ("SCHEMA",)
    Pr = C.project_like(R, list(outn))
    return frozenset(Counter(tuple(C.enc(v) for v in r) for r in Pr.rows).items())


def _train_observer(sel, nr, oracle, meter, log):
    """Counterfactual learning on every query event: sel gets listwise steps AND regret audits; nr (no-regret) listwise steps only."""
    def observer(ev):
        lst, vs = ev.get("splitting") or ev.get("scored") or [], ev["vs"]
        if not lst:
            return
        refs = []
        for s in lst:
            if not meter.charge("ref_answers"):
                log["skipped_learning_steps"] += 1
                return
            try:
                R = oracle(ev["stage"], s["env"])
            except Exception:                                          # noqa: BLE001 - reference failure: no answer
                R = None
            refs.append(_fp(R, vs.outn))
        leader = vs.leader()
        utils = S13.counterfactual_utilities(lst, refs, leader_id=leader["id"] if leader else None)
        ctx = dict(stage=ev["stage"], phase=ev.get("phase", "lift"))
        sel.train_step(lst, utils, context=ctx)
        nr.train_step(lst, utils, context=ctx)
        rec = sel.audit_choice(lst, ev["chosen"], utils, context=ctx)
        log["learning_steps"] += 1
        log["regret_total"] += float(rec.get("regret", 0.0))
    return observer


def train_stream(si, cfg, deadline):
    stream = STREAMS[si]
    sel, nr = S13.Selector(name=f"trained_{stream}"), S13.Selector(name=f"no_regret_{stream}")
    guide, meter, ops = S13.DeltaStateGuide(name=f"guide_{stream}"), SourceMeter(), OperatorLibrary(name=f"operators_{stream}")
    episodes, log, bq = [], Counter(), max(cfg["budgets"])
    front = cfg.get("train_front", DEFAULT_FRONTS[0])
    for spec in [s for s in SPECS if not s["held_out"]]:
        for i in range(cfg["source_instances"]):
            if time.time() >= deadline:
                episodes.append(dict(spec=spec["name"], i=i, status="not_run_deadline"))
                continue
            seed = source_seed(si, spec["id"], i)
            meter.new_episode()
            ep = dict(spec=spec["name"], seed=seed, front=front)
            try:
                inst = make_instance(spec, seed, front=front)
                kw = dict(chooser=sel.choose, prior=sel.leader_prior, costs=guide.costs() if guide.n else None,
                          observer=_train_observer(sel, nr, inst["oracle"], meter, log))
                res, op = solve(inst, bq, kw, cfg, cfg["row_wall"], operators=ops.admitted() or None)
                work, q, over = _combined(res, bq, cfg["fc_cap"])
                ep.update(status=res["status"], reason=res.get("reason"), queries_used=q, over_cap=over, changed=res["changed_nodes"],
                          operator_path=bool(res.get("operator_path")),
                          operator_reason=None if op is None else op.get("reason"))
                if res["status"] == "repaired":
                    g = grade(inst, res["pipeline"], meter, required=_required(cfg))
                    if not g["graded"]:
                        ep["grading"] = "ungradable" if g.get("reason") == "reference_fidelity_unverified" else "refused"
                    else:
                        ep["grading"] = "verified" if g["verified"] else "wrong"
                    if g["graded"]:
                        names, tags, keys = res["pipeline"].names(), set(), []
                        old = {s["name"]: s["ast"] for s in inst["broken"].stages}
                        for n in res["changed_nodes"]:
                            ast = res["pipeline"].stages[names.index(n)]["ast"]
                            guide.observe(ast, g["verified"])
                            tags |= P.shortcut_tags(ast)
                            key = ops.observe(old[n], ast, g["verified"])
                            if key:
                                keys.append(key)
                        ep["operators"] = keys
                        sel.audit_submission(sorted(tags), falsified=not g["verified"], context=dict(task=inst["task"]))
            except Exception as e:                                     # noqa: BLE001 - recorded as an error episode (with traceback)
                ep.update(status="error", **_exc(e))
            episodes.append(ep)
    return sel, guide, ops, meter, episodes, dict(log), nr


# ------------------------------------------------------------------ arms and rows
def _static_menu(vs):
    return P.generic_proposals(P.base_envs(vs.task))


def arm_kwargs(arm, stream, task, bq, frozen=None):
    if arm == "fixed":
        return dict(menu=_static_menu, chooser=lambda lst: P.choose(lst, "fixed"))
    if arm == "random":
        rng = random.Random(int(hashlib.sha256(f"{stream}|{task}|{bq}".encode()).hexdigest()[:12], 16))
        return dict(menu=_static_menu, chooser=lambda lst: P.choose(lst, "random", rng=rng))
    if arm == "untrained":
        w = P.uniform_weights()
        return dict(chooser=lambda lst: P.choose(lst, "weighted", w))
    if arm in ("trained",) + ABLATIONS:
        sel, guide = frozen[0], frozen[1]
        if arm == NO_REGRET:
            if len(frozen) < 4:
                raise ValueError("trained_no_regret needs the frozen no-regret selector")
            sel = frozen[3]
        kw = dict(chooser=sel.choose, prior=sel.leader_prior, costs=guide.costs() if guide.n else None)
        if arm != ABLATION and len(frozen) > 2:
            kw["operators"] = frozen[2].admitted()
        return kw
    if arm == "single_shot":
        return dict(require_unique=False, holdout=False)
    raise ValueError(f"unknown arm {arm!r}")


def run_row(inst, arm, stream, bq, kw, cfg, wall):
    t0, spec = time.time(), inst["spec"]
    kw = dict(kw)
    operators = kw.pop("operators", None)
    fi = inst.get("front_info") or {}
    rec = dict(task=inst["task"], spec=spec["name"], held_out=spec["held_out"], seed=inst["seed"], stream=stream, arm=arm, budget=bq,
               fault_nodes=list(spec["faults"]), beyond_single_edit=spec["beyond_single_edit"], n_operators=len(operators or []),
               front=inst.get("front"), fault_observable=fi.get("fault_observable"),
               reference_gradable=bool(fi.get("reference_gradable", True)))
    try:
        res, op = solve(inst, bq, kw, cfg, wall, operators=operators)
    except Exception as e:                                             # noqa: BLE001 - recorded with traceback, never imputed
        rec.update(status="error", submitted=False, verified=False, wrong=False, abstained=False, ungraded=False, over_cap=[], work={},
                   queries_used=0, wall=round(time.time() - t0, 3), **_exc(e))
        return rec
    work, q, over = _combined(res, bq, cfg["fc_cap"])
    submitted = res["status"] == "repaired"
    g = grade(inst, res["pipeline"], engines=cfg["engines"], required=_required(cfg)) if submitted else None
    graded = bool(g and g["graded"])
    loc = res["steps"][0]["localization"] if res["steps"] else None
    changed = list(res["changed_nodes"])
    rec.update(status=res["status"], reason=res["reason"], submitted=submitted, verified=bool(g and g["verified"]),
               wrong=bool(submitted and graded and not g["verified"]), ungraded=bool(submitted and not graded),
               abstained=not submitted, grading=g,
               multi_engine_verified=bool(g and g["multi_engine_verified"]), work=work, over_cap=over, queries_used=q,
               changed_nodes=changed, fault_repaired_at_true_node=set(spec["faults"]) <= set(changed),
               exact_fault_nodes=set(changed) == set(spec["faults"]), node_isolated=res["node_isolated"],
               repair_methods=[{k: m.get(k) for k in ("node", "scope", "mode", "method", "edge")} for m in res["repair_methods"]],
               operator_executed=bool(res.get("operator_path")), library_provenance=res["attribution"]["learned"]["library_functions"],
               source_fidelity=(res.get("source_fidelity") or {}).get("reason"), fidelity_gate=res.get("fidelity_gate"),
               required_engines=list(res.get("required_engines") or _required(cfg)),
               required_engine_dag=res.get("required_engine_dag"),
               operator_stage=None if op is None else {k: op.get(k) for k in ("status", "reason", "candidates", "survivors",
                                                                                "queries_used", "agreement_unproven", "queries",
                                                                                "required_engine_dag")},
               localization=None if loc is None else dict(status=loc.get("status"), method=loc.get("method"), fault=loc.get("fault"),
                                                          correct=loc.get("fault") in spec["faults"],
                                                          n_columns=(loc.get("columns") or {}).get("n_columns")),
               invariants=dict(ok=res["invariants"]["ok"], failed=res["invariants"]["failed"], max_width=res["invariants"]["max_width"]),
               exhausted=res.get("row_exhausted"), wall=round(time.time() - t0, 3))
    return rec


# ------------------------------------------------------------------ summaries, contrasts, verdict, progression
def summarize(rows):
    out = {}
    for r in rows:
        s = out.setdefault(f"{r['stream']}|B{r['budget']}|{r['arm']}", Counter())
        s["rows"] += 1
        for k in ("submitted", "verified", "wrong", "abstained", "multi_engine_verified", "ungraded"):
            s[k] += int(bool(r.get(k)))
        v = bool(r.get("verified"))
        s["errors"] += int(r["status"] == "error")
        s["over_cap"] += int(bool(r.get("over_cap")))
        s["queries"] += r.get("queries_used", 0)
        s["held_out_verified"] += int(v and bool(r.get("held_out")))
        s["beyond_single_edit_verified"] += int(v and bool(r.get("beyond_single_edit")))
        s["node_isolated_verified"] += int(v and bool(r.get("node_isolated")))
        s["operator_verified"] += int(v and bool(r.get("operator_executed")))
        s["held_out_operator_verified"] += int(v and bool(r.get("held_out")) and bool(r.get("operator_executed")))
        ops = r.get("operator_stage")
        s["operator_attempted"] += int(ops is not None)
        s["operator_declined"] += int(ops is not None and ops.get("status") != "repaired")
        s["synth_verified"] += int(v and any(m.get("method") == "synth" for m in r.get("repair_methods", [])))
        s["localized_correct"] += int(bool((r.get("localization") or {}).get("correct")))
        s["fidelity_blocked"] += int(bool(r.get("fidelity_gate")))
        s["reference_ungradable"] += int(r.get("reference_gradable") is False)
        for k in ("full_checks", "probe_evals"):
            s[k] += r.get("work", {}).get(k, 0)
            s[f"max_{k}"] = max(s[f"max_{k}"], r.get("work", {}).get(k, 0))
    return {k: dict(v) for k, v in sorted(out.items())}


def operator_reasons(rows):
    """Diagnostic: operator-stage outcome reasons per (arm, spec), so a zero held-out reuse rate can be traced to its cause."""
    out = {}
    for r in rows:
        ops = r.get("operator_stage")
        if ops is None:
            continue
        out.setdefault(f"{r['arm']}|{r['spec']}", Counter())[ops.get("reason") or ops.get("status")] += 1
    return {k: dict(v) for k, v in sorted(out.items())}


def _index(rows):
    return {(r["stream"], r["budget"], r["arm"], r["task"]): r for r in rows}


def matched_tasks(idx, stream, bq, arms):
    tasks = {t for (s, b, a, t) in idx if s == stream and b == bq}
    return sorted(t for t in tasks if all((stream, bq, a, t) in idx for a in arms))


def _subset(rows, name):
    if name == "beyond_single_edit":
        return [r for r in rows if r.get("beyond_single_edit")]
    if name == "held_out":
        return [r for r in rows if r.get("held_out")]
    if name.startswith("front:"):
        return [r for r in rows if r.get("front") == name[len("front:"):]]
    return list(rows)


def contrasts(rows, budgets):
    idx, out = _index(rows), {}
    for st in STREAMS:
        for bq in budgets:
            tasks = matched_tasks(idx, st, bq, ARMS)
            ver = {a: sum(idx[(st, bq, a, t)]["verified"] for t in tasks) for a in ARMS}
            wr = {a: sum(idx[(st, bq, a, t)]["wrong"] for t in tasks) for a in ARMS}
            out[f"{st}|B{bq}"] = dict(matched_tasks=len(tasks), verified=ver, wrong=wr,
                                      trained_minus={x: ver["trained"] - ver[x] for x in COMPARATORS},
                                      untrained_minus_fixed=ver["untrained"] - ver["fixed"])
    return out


def ablation(rows, budgets, arm=ABLATION, label="no_ops"):
    idx, out = _index(rows), {}
    for st in STREAMS:
        for bq in budgets:
            tasks = matched_tasks(idx, st, bq, ("trained", arm))
            tr, ab = [idx[(st, bq, "trained", t)] for t in tasks], [idx[(st, bq, arm, t)] for t in tasks]
            out[f"{st}|B{bq}"] = {"matched_tasks": len(tasks), "trained_verified": sum(r["verified"] for r in tr),
                                  "trained_wrong": sum(r["wrong"] for r in tr), f"{label}_verified": sum(r["verified"] for r in ab),
                                  f"{label}_wrong": sum(r["wrong"] for r in ab),
                                  "verified_diff": sum(r["verified"] for r in tr) - sum(r["verified"] for r in ab)}
    return out


def verdict(con, primary):
    cs = [con.get(f"{st}|B{primary}") for st in STREAMS]
    if any(c is None or c["matched_tasks"] == 0 for c in cs):
        return "insufficient"
    pos = all(all(c["trained_minus"][x] >= 2 for x in COMPARATORS) and all(c["wrong"]["trained"] <= c["wrong"][x] for x in COMPARATORS)
              for c in cs)
    neg = all(any(c["trained_minus"][x] <= -2 for x in COMPARATORS) for c in cs)
    return "positive" if pos else ("negative" if neg else "mixed")


def _score_rows(rs):
    return None if not rs else (sum(r["verified"] for r in rs) - sum(r["wrong"] for r in rs)) / len(rs)


def _delta(idx, st, bq, arm):
    """(verified - wrong) / rows of trained minus `arm` on their matched tasks (None without matched tasks)."""
    tasks = matched_tasks(idx, st, bq, ("trained", arm))
    a, b = _score_rows([idx[(st, bq, "trained", t)] for t in tasks]), _score_rows([idx[(st, bq, arm, t)] for t in tasks])
    return None if a is None or b is None else round(a - b, 4)


def progression(rows, primary):
    idx, out = _index(rows), {}
    for st in STREAMS:
        tasks = matched_tasks(idx, st, primary, ("trained", "untrained"))
        tr, un = [idx[(st, primary, "trained", t)] for t in tasks], [idx[(st, primary, "untrained", t)] for t in tasks]

        def per_ver(rs, f):
            v = sum(r["verified"] for r in rs)
            return None if not v else sum(f(r) for r in rs) / v
        work = lambda r: r.get("work", {}).get("full_checks", 0) + r.get("work", {}).get("probe_evals", 0)   # noqa: E731
        wt, wu = per_ver(tr, work), per_ver(un, work)
        ho_tr, ho_un = [r for r in tr if r["held_out"]], [r for r in un if r["held_out"]]
        ver_ho = [r for r in ho_tr if r["verified"]]
        ss_tasks = [t for t in tasks if (st, 0, "single_shot", t) in idx]
        s_ss = _score_rows([idx[(st, 0, "single_shot", t)] for t in ss_tasks])
        s_trss = _score_rows([idx[(st, primary, "trained", t)] for t in ss_tasks])
        st_tr, st_un = _score_rows(tr), _score_rows(un)
        out[st] = dict(
            learning_to_learn_gain=None if not (wt and wu) else round((wu - wt) / wu, 4),
            work_per_verified=dict(trained=wt, untrained=wu),
            queries_per_verified=dict(trained=per_ver(tr, lambda r: r.get("queries_used", 0)),
                                      untrained=per_ver(un, lambda r: r.get("queries_used", 0))),
            transfer_efficiency=sum(r["verified"] for r in ho_tr) - sum(r["verified"] for r in ho_un) if ho_tr else None,
            self_evolution_delta=_delta(idx, st, primary, NO_REGRET),
            self_evolution_combined=None if st_tr is None or st_un is None else round(st_tr - st_un, 4),
            operator_delta=_delta(idx, st, primary, ABLATION),
            self_evolution_note="self_evolution_delta isolates regret updates (trained vs trained_no_regret); self_evolution_combined is "
                                "trained vs untrained; operator_delta is trained vs trained_no_ops",
            unseen_domain_reuse_rate=None if not ver_ho else round(sum(bool(r.get("operator_executed")) for r in ver_ho) / len(ver_ho), 4),
            unseen_domain_reuse_note="share of trained verified held-out rows whose accepted repair EXECUTED a learned operator",
            enterprise_reliability_advantage=None if s_ss is None or s_trss is None else round(s_trss - s_ss, 4),
            matched_tasks=len(tasks))
    return out


def _fronts_of(cfg):
    return list(cfg.get("fronts") or ([cfg["front"]] if cfg.get("front") else []))


def capability_acceptance(prog, cfg, rows=None):
    """Mandatory-capability check (charter section 10 + native multi-engine fronts). BLOCKING (exit 1) unless the configuration sets
    require_acceptance=False (--advisory-acceptance)."""
    failed = [f"{st}:{k}={p.get(k)}" for st, p in sorted(prog.items()) for k in PROGRESSION_KEYS if p.get(k) is None or p.get(k) <= 0]
    if not [e for e in cfg.get("required_engines", ()) if e not in ("sqlite", "core11")]:
        failed.append("multi_engine:no_non_sqlite_required_engine_available")
    fronts = _fronts_of(cfg)
    kinds = {str(f).partition(":")[0] for f in fronts}
    if "sql" not in kinds:
        failed.append("front:no_authored_native_sql_front")
    if "df" not in kinds:
        failed.append("front:no_dataframe_front")
    for f in fronts:
        kind = str(f).partition(":")[0]
        if kind not in NATIVE_KINDS:
            continue
        try:
            eng = front_engine(f if ":" in str(f) else f"{kind}:{'sqlite' if kind == 'sql' else 'polars'}")
        except ValueError:
            eng = None
        if eng is None or not engine_available(eng):
            failed.append(f"front:{f}:engine_unavailable:{eng}")
        if rows is not None and not any(r.get("verified") and r.get("front") == f for r in rows):
            failed.append(f"front:{f}:no_verified_repair")
    enforced = bool(cfg.get("require_acceptance", cfg.get("require_progression", True)))
    return dict(accepted=not failed, failed=failed, required=list(PROGRESSION_KEYS), fronts=fronts, enforced=enforced)


def semantic_check(suite, allow_core_gaps=False):
    """Fail-closed verdict on the conformance suite (None = suite not run)."""
    if suite is None:
        return dict(checked=False, ok=True, reason="suite_not_run")
    if suite.get("error") or suite.get("build_error"):
        return dict(checked=True, ok=False, reason="suite_error", detail=suite.get("error") or suite.get("build_error"))
    failing, core = suite.get("failing_cases") or [], suite.get("core_error_cases") or []
    unexercised = sorted(f for f in ME.FEATURES if not any(r["feature"] == f and r["reason"] != "core_error"
                                                           for r in suite.get("cases", [])))
    strict = bool(suite.get("required_ok"))
    ok = strict or (allow_core_gaps and not failing and not unexercised)
    reason = None if ok else ("failing_cases" if failing else "unexercised_features" if unexercised else "core_error_cases")
    return dict(checked=True, ok=ok, reason=reason, failing_cases=failing, core_error_cases=core, unexercised_features=unexercised,
                core_gaps_waived=bool(allow_core_gaps and core and ok and not strict))


# ------------------------------------------------------------------ experiment
def _learned(sel, guide, ops, meter, episodes, log, nr):
    top = lambda s: [(k, round(v, 4)) for k, v in sorted(s.weights.items(), key=lambda kv: (-abs(kv[1] - 1.0), kv[0]))[:12]]  # noqa: E731
    return dict(top_weights=top(sel), no_regret_top_weights=top(nr), tag_prior=dict(sel.tag_prior),
                demoted_shortcuts=sel.demoted_shortcuts(), selector_stats=dict(sel.stats), ledger_len=len(sel.ledger),
                guide_table=guide.table(), guide_observations=guide.n, operators=ops.to_dict(),
                admitted_operators=[o["key"] for o in ops.admitted()], learning_log=log, supervision=meter.report(), episodes=episodes,
                episode_outcomes=dict(Counter(e.get("grading", e.get("status")) for e in episodes)))


def run_experiment(cfg):
    t0 = time.time()
    grant = float(cfg["grant_seconds"])
    dl_eval = t0 + 0.92 * grant
    if cfg["fc_cap"] > FC_MAX:
        raise ValueError(f"fc_cap {cfg['fc_cap']} exceeds the pre-registered maximum {FC_MAX}")
    overlap = seed_overlap(cfg["source_instances"], cfg["eval_instances"])
    if overlap:
        raise ValueError(f"source / evaluation seed overlap: {overlap[:5]}")
    fronts = _fronts_of(cfg) or ["ast"]
    out_dir = Path(cfg["out"])
    out_dir.mkdir(parents=True, exist_ok=True)
    suite = None
    if cfg["suite"]:
        try:
            suite = ME.conformance_suite(engines=cfg["engines"])
        except Exception as e:                                         # noqa: BLE001
            suite = dict(_exc(e))
    trained, learned, fp_before = {}, {}, {}
    for si, st in enumerate(STREAMS):
        parts = train_stream(si, cfg, t0 + (si + 1) * 0.30 * grant / len(STREAMS))
        sel, guide, ops, meter, eps, log = parts[:6]
        nr = parts[6] if len(parts) > 6 else S13.Selector(name=f"no_regret_{st}")
        fs, fnr = sel.copy(name=f"frozen_{st}", frozen=True), nr.copy(name=f"frozen_no_regret_{st}", frozen=True)
        fg = S13.DeltaStateGuide.from_dict(guide.to_dict()).freeze()
        fo = ops.copy(name=f"frozen_ops_{st}", frozen=True)
        trained[st] = (fs, fg, fo, fnr)
        fp_before[st] = dict(selector=fs.fingerprint(), guide=fg.fingerprint(), operators=fo.fingerprint(), no_regret=fnr.fingerprint())
        learned[st] = _learned(sel, guide, ops, meter, eps, log, nr)
    t_source = time.time() - t0
    instances, build_errors, front_info = [], [], {}
    for front in fronts:
        fi = front_info.setdefault(front, dict(instances=0, build_errors=0, fault_observable=0, reference_gradable=0,
                                               reference_fidelity=Counter(), drift_broken=Counter(), drift_reference=Counter(),
                                               engine=None))
        try:
            fi["engine"] = front_engine(front)
        except ValueError:
            fi["engine"] = None
        for spec in SPECS:
            for i in range(cfg["eval_instances"]):
                try:
                    inst = make_instance(spec, eval_seed(spec["id"], i), front=front)
                except Exception as e:                                 # noqa: BLE001
                    fi["build_errors"] += 1
                    build_errors.append(dict(spec=spec["name"], i=i, front=front, **_exc(e)))
                    continue
                instances.append(inst)
                info = inst["front_info"]
                fi["instances"] += 1
                fi["fault_observable"] += int(bool(info["fault_observable"]))
                fi["reference_gradable"] += int(bool(info.get("reference_gradable", True)))
                rf = info.get("reference_fidelity")
                fi["reference_fidelity"]["none" if rf is None else ("faithful" if rf["faithful"] else str(rf["reason"]))] += 1
                fi["drift_broken"].update(f"{spec['name']}:{n}" for n in info["drift_broken"])
                fi["drift_reference"].update(f"{spec['name']}:{n}" for n in info["drift_reference"])
    front_info = {f: dict(v, drift_broken=dict(v["drift_broken"]), drift_reference=dict(v["drift_reference"]),
                          reference_fidelity=dict(v["reference_fidelity"]),
                          engine_available=bool(v["engine"] and engine_available(v["engine"]))) for f, v in front_info.items()}
    arms = tuple(ARMS) + (ABLATIONS if cfg.get("ablation", True) else ())
    rows, missing, plan = [], [], []
    for inst in instances:
        for st in STREAMS:
            plan += [(inst, st, bq, arm) for bq in cfg["budgets"] for arm in arms]
            if cfg["single_shot"]:
                plan.append((inst, st, 0, "single_shot"))
    for inst, st, bq, arm in plan:
        now = time.time()
        if now >= dl_eval:
            missing.append(dict(task=inst["task"], stream=st, budget=bq, arm=arm))
            continue
        kw = arm_kwargs(arm, st, inst["task"], bq, trained.get(st))
        rows.append(run_row(inst, arm, st, bq, kw, cfg, min(cfg["row_wall"], max(1.0, dl_eval - now))))
    iso = dict(seed_overlap=overlap, streams={})
    for st, objs in trained.items():
        after = dict(selector=objs[0].fingerprint(), guide=objs[1].fingerprint(), operators=objs[2].fingerprint(),
                     no_regret=objs[3].fingerprint())
        iso["streams"][st] = dict(before=fp_before[st], after=after, frozen=all(o.frozen for o in objs), unchanged=after == fp_before[st])
    iso["ok"] = not overlap and all(v["frozen"] and v["unchanged"] for v in iso["streams"].values())
    primary = max(cfg["budgets"])
    subsets = SUBSETS + tuple(f"front:{f}" for f in fronts)
    con = {name: contrasts(_subset(rows, name), cfg["budgets"]) for name in subsets}
    prog = progression(rows, primary)
    accept = capability_acceptance(prog, cfg, rows)
    src_over = {st: learned[st]["supervision"]["over"] for st in STREAMS if learned[st]["supervision"]["over"]}
    src_over_rows = sum(bool(e.get("over_cap")) for st in STREAMS for e in learned[st]["episodes"])
    src_err = [dict(stream=st, spec=e.get("spec"), seed=e.get("seed"), error=e.get("error"), traceback=e.get("traceback"))
               for st in STREAMS for e in learned[st]["episodes"] if e.get("status") == "error"]
    sem = semantic_check(suite, cfg.get("allow_core_gaps", False))
    req_unavail = [e for e in cfg["required_engines"] if not engine_available(e)]
    err_rows = [dict(task=r["task"], stream=r["stream"], arm=r["arm"], budget=r["budget"], error=r.get("error"),
                     traceback=r.get("traceback")) for r in rows if r["status"] == "error"]
    checks = dict(over_cap_rows=sum(bool(r.get("over_cap")) for r in rows), error_rows=len(err_rows), error_row_details=err_rows[:20],
                  source_over_cap_episodes=src_over_rows, source_error_episodes=src_err, source_supervision_over_cap=src_over,
                  isolation_ok=iso["ok"], build_errors=build_errors, missing_rows=len(missing), semantic=sem,
                  required_engines=list(cfg["required_engines"]), required_engines_unavailable=req_unavail, fronts=fronts,
                  required_engines_gate_repairs=True,
                  ungraded_rows=sum(bool(r.get("ungraded")) for r in rows),
                  reference_ungradable_rows=sum(r.get("reference_gradable") is False for r in rows),
                  capability_accepted=accept["accepted"], capability_enforced=accept["enforced"],
                  max_full_checks=max((r.get("work", {}).get("full_checks", 0) for r in rows), default=0), fc_cap=cfg["fc_cap"])
    failures = [k for k, bad in (("over_cap_rows", checks["over_cap_rows"]), ("isolation", not iso["ok"]),
                                 ("source_supervision", src_over or src_over_rows), ("error_rows", err_rows),
                                 ("source_error_episodes", src_err), ("build_errors", build_errors),
                                 ("required_engine_unavailable", req_unavail), ("semantic_suite", sem["checked"] and not sem["ok"]),
                                 ("capability_acceptance", accept["enforced"] and not accept["accepted"])) if bad]
    checks["failures"] = failures
    results = dict(
        phase=14, config=dict(cfg), availability=engine_availability(),
        verdict=dict({name: verdict(con[name], primary) for name in subsets}, dag=verdict(con["all"], primary), primary_budget=primary,
                     rule="positive: trained-X >= +2 verified for every X in every stream and trained wrong <= each; negative: some "
                          "trained-X <= -2 in every stream; else mixed (matched tasks only; insufficient without matched tasks)"),
        contrasts=con, operator_ablation=ablation(rows, cfg["budgets"]),
        regret_ablation=ablation(rows, cfg["budgets"], NO_REGRET, "no_regret"), summaries=summarize(rows),
        summaries_by_front={f: summarize(_subset(rows, f"front:{f}")) for f in fronts}, front_info=front_info, progression=prog,
        operator_reasons=operator_reasons(rows),
        capability_acceptance=accept, checks=checks, isolation=iso, learned_by_nexus=learned, conformance_suite=suite, missing=missing,
        specs=[dict(id=s["id"], name=s["name"], held_out=s["held_out"], faults=list(s["faults"]), observed=list(s["observed"]),
                    n_edits=s["n_edits"], edit_reachable=s["edit_reachable"], beyond_single_edit=s["beyond_single_edit"]) for s in SPECS],
        attribution=dict(machinery="runner14 + dag_repair14 + multi_engine14 + pipeline_lifter13 + proposals13 + selector13 + synth12 "
                                   "(engineering team; external engineering), including the engineer-authored SQL / DataFrame sources, "
                                   "the anti-unification rule, operator matching, the operator-stage probe rule and the admission threshold",
                         learned="learned_by_nexus: selector and no-regret weights, tag prior, guide counts and admitted executable "
                                 "operators with counts, from source training only"),
        environment=dict(python=sys.version.split()[0], platform=platform.platform(), sqlite=L.sqlite3.sqlite_version),
        wall=dict(total=round(time.time() - t0, 2), source=round(t_source, 2)))
    with open(out_dir / "rows.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    code = 2 if not rows else (1 if failures else 0)
    results["exit_code"] = code
    with open(out_dir / "results.json", "w") as fh:
        json.dump(results, fh, sort_keys=True, indent=1, default=str)
    return results, code


def _brief(results):
    suite = results.get("conformance_suite") or {}
    lb = results["learned_by_nexus"]
    skip = ("build_errors", "error_row_details", "source_error_episodes")
    return dict(verdict=results["verdict"], checks={k: v for k, v in results["checks"].items() if k not in skip},
                contrasts=results["contrasts"], operator_ablation=results["operator_ablation"],
                regret_ablation=results["regret_ablation"], summaries=results["summaries"],
                summaries_by_front=results["summaries_by_front"], front_info=results["front_info"], progression=results["progression"],
                operator_reasons=results.get("operator_reasons"),
                capability_acceptance=results["capability_acceptance"],
                demoted_shortcuts={st: v["demoted_shortcuts"] for st, v in lb.items()},
                admitted_operators={st: v["admitted_operators"] for st, v in lb.items()},
                supervision={st: v["supervision"]["used"] for st, v in lb.items()},
                episode_outcomes={st: v["episode_outcomes"] for st, v in lb.items()},
                conformance=dict(by_engine=suite.get("by_engine"), fully=suite.get("fully_conformant_engines"), error=suite.get("error"),
                                 core_error_cases=suite.get("core_error_cases"), failing_cases=suite.get("failing_cases"),
                                 null_order=suite.get("null_order"), rank_semantics=suite.get("rank_semantics"),
                                 round_trip=suite.get("round_trip")),
                availability=results["availability"], wall=results["wall"], exit_code=results["exit_code"])


def _errors_line(results):
    ch = results["checks"]
    return dict(error_rows=ch["error_rows"], first_row_errors=ch["error_row_details"][:3],
                source_error_episodes=len(ch["source_error_episodes"]), first_source_errors=ch["source_error_episodes"][:3],
                build_errors=ch["build_errors"][:3], failures=ch["failures"],
                capability_failed=results["capability_acceptance"]["failed"])


def _engines(spec, engines):
    if spec == "auto":
        return ("sqlite",) + tuple(e for e in engines if e not in ("sqlite", "core11") and engine_available(e))
    return tuple(e for e in spec.split(",") if e)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="NEXUS Phase 14 metered multi-engine DAG repair runner")
    ap.add_argument("--grant-seconds", type=float, default=600.0)
    ap.add_argument("--execute", action="store_true", help="run the experiment (without it: print the plan only)")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default="artifacts/agi14_eval")
    ap.add_argument("--budgets", default="1,2")
    ap.add_argument("--eval-instances", type=int, default=2)
    ap.add_argument("--source-instances", type=int, default=3)
    ap.add_argument("--fc-cap", type=int, default=FC_MAX)
    ap.add_argument("--row-wall", type=float, default=12.0)
    ap.add_argument("--fronts", default=",".join(DEFAULT_FRONTS),
                    help="comma list of sql:<dialect> | df:<api> | compiled_sql:<dialect> | ast (authored native sources by default)")
    ap.add_argument("--train-front", default=DEFAULT_FRONTS[0])
    ap.add_argument("--engines", default="sqlite,duckdb,polars", help="engines executing the whole repaired DAG at grading (reported)")
    ap.add_argument("--required-engines", default="auto",
                    help="'auto' = sqlite + every installed engine of --engines; required engines gate BOTH repair paths and grading")
    ap.add_argument("--invariant-engines", default="auto")
    ap.add_argument("--with-pyspark", action="store_true")
    ap.add_argument("--no-suite", action="store_true")
    ap.add_argument("--no-single-shot", action="store_true")
    ap.add_argument("--no-ablation", action="store_true")
    ap.add_argument("--advisory-acceptance", action="store_true",
                    help="non-default: report capability_acceptance without failing the run (smoke / unit runs only)")
    ap.add_argument("--require-progression", action="store_true", help="kept for compatibility; acceptance is enforced by default")
    ap.add_argument("--allow-core-gaps", action="store_true",
                    help="non-default: do not fail on suite cases core11 cannot evaluate (disagreements / errors still fail)")
    return ap.parse_args(argv)


def config_from(a):
    engines = [e for e in a.engines.split(",") if e]
    if a.with_pyspark and "pyspark" not in engines:
        engines.append("pyspark")
    fronts = tuple(f for f in a.fronts.split(",") if f)
    for f in fronts + (a.train_front,):
        parse_front(f)
    cfg = dict(grant_seconds=a.grant_seconds, out=a.out, budgets=sorted({int(b) for b in a.budgets.split(",") if b}),
               eval_instances=a.eval_instances, source_instances=a.source_instances, fc_cap=a.fc_cap, row_wall=a.row_wall,
               fronts=fronts, train_front=a.train_front, engines=tuple(engines),
               required_engines=_engines(a.required_engines, engines), invariant_engines=_engines(a.invariant_engines, engines),
               suite=not a.no_suite, single_shot=not a.no_single_shot, ablation=not a.no_ablation, quick=a.quick,
               allow_core_gaps=a.allow_core_gaps, require_acceptance=not a.advisory_acceptance)
    if a.quick:
        cfg.update(eval_instances=1, source_instances=1, budgets=[max(cfg["budgets"])], row_wall=min(a.row_wall, 6.0))
    return cfg


def main(argv=None):
    a = parse_args(argv)
    cfg = config_from(a)
    if not a.execute:
        print(json.dumps(dict(plan=cfg, specs=[s["name"] for s in SPECS], arms=list(ARMS) + list(ABLATIONS), streams=list(STREAMS),
                              availability=engine_availability(),
                              seed_overlap=seed_overlap(cfg["source_instances"], cfg["eval_instances"]),
                              note="dry plan only; pass --execute to run"), indent=1, default=str))
        return 0
    results, code = run_experiment(cfg)
    print(json.dumps(_brief(results), indent=1, sort_keys=True, default=str))
    print("ERRORS " + json.dumps(_errors_line(results), sort_keys=True, default=str))
    print(f"exit_code={code}")
    return code


__all__ = ["SPECS", "STREAMS", "SOURCE_CAPS", "ABLATION", "NO_REGRET", "ABLATIONS", "DEFAULT_FRONTS", "SourceMeter", "OperatorLibrary",
           "extract_operator", "operator_stage", "solve", "engine_dag", "make_instance", "reference_fidelity", "parse_front",
           "front_engine", "grade", "arm_kwargs", "run_row", "train_stream", "summarize", "operator_reasons", "contrasts", "ablation",
           "verdict", "progression", "capability_acceptance", "semantic_check", "seed_overlap", "run_experiment", "config_from",
           "parse_args", "main", "engine_available"]


if __name__ == "__main__":
    sys.exit(main())
