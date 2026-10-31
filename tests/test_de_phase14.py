"""Phase 14 unit tests (standard-library unittest): multi-engine compiler / conformance (including rank TIE and NULL-order
semantics, probed core11 tie rule, ROW_NUMBER compilation, reverse-parser rejection of tie-keeping windows), DAG localisation and
node-only repair, native SQL and DataFrame fronts, fail-closed REFERENCE fidelity (ungradable references are never graded), the
shared fail-closed fidelity gate in front of BOTH repair paths, REQUIRED-ENGINE whole-DAG verification gating BOTH repair paths on
the shared row budget, learned executable operators, shared row budgets, blocking capability acceptance and the metered runner.
Optional engines (duckdb, polars, pyspark) are exercised only when installed; never simulated."""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from nexus.de_phase11 import core11 as C                                # noqa: E402
from nexus.de_phase12 import synth12 as S                               # noqa: E402
from nexus.de_phase13 import pipeline_lifter13 as L                     # noqa: E402
from nexus.de_phase13 import selector13 as S13                          # noqa: E402
from nexus import de_phase14 as PKG                                     # noqa: E402
from nexus.de_phase14 import dag_repair14 as D                          # noqa: E402
from nexus.de_phase14 import multi_engine14 as ME                       # noqa: E402
from nexus.de_phase14 import runner14 as R                              # noqa: E402

I, N, STR = C.INT, C.NUM, C.STR
BIG = 2 ** 60


def col(c):
    return ("col", c)


def k(v, t):
    return ("const", v, t)


def simple_env():
    return {"t": ME.make_rel(("id", "x", "s"), (I, I, STR), [(1, 5, "a"), (2, 3, "b"), (3, 7, "a")])}


def tie_env():
    """The conformance suite's ranking data: ties on ts within uid 1, a NULL ts in uid 2, and a NULL partition key."""
    return {"e": ME.make_rel(("uid", "ts", "v"), (I, I, I),
                             [(1, 10, 1), (1, 20, 2), (1, 20, 3), (2, None, 4), (2, 5, 5), (None, 7, 6), (None, 7, 7)])}


def _core_error(ast, env):
    try:
        C.run(ast, env)
        return None
    except Exception as e:                                             # noqa: BLE001 - diagnostic only
        return f"{type(e).__name__}: {str(e)[:160]}"


RANK_CANON = ME.rank_ast(("rel", "t"), ("s",), ((col("x"), True),))
RANK_FOUR = RANK_CANON[:4]
RANK_TIES = ME.rank_ast(("rel", "e"), ("uid",), ((col("ts"), True),))
RANK_NULL_ORDER = ME.rank_ast(("rel", "e"), ("uid",), ((col("ts"), False),))


class _RaisingCounter(dict):
    def __missing__(self, key):
        return 0

    def __setitem__(self, key, value):
        raise S.WorkExhausted(f"{key} cap")


class _RefusingBudget:
    def __init__(self):
        self.c, self.exhausted = _RaisingCounter(), None

    def wall_bound(self):
        return False

    def out(self):
        return True


def _cfg(*extra):
    return R.config_from(R.parse_args(["--engines", "sqlite", "--no-suite"] + list(extra)))


# ------------------------------------------------------------------ package
class TestPackage(unittest.TestCase):
    def test_availability(self):
        av = PKG.engine_availability()
        self.assertEqual(set(av), set(PKG.ENGINES))
        self.assertTrue(av["core11"] and av["sqlite"])
        self.assertFalse(PKG.engine_available("no_such_engine"))

    def test_layers(self):
        self.assertEqual(PKG.layer_of("stg_orders"), "stg_")
        self.assertEqual(PKG.layer_of("int_x"), "int_")
        self.assertEqual(PKG.layer_of("fct_y"), "fct_")
        self.assertIsNone(PKG.layer_of("raw"))


# ------------------------------------------------------------------ multi_engine14
class TestValues(unittest.TestCase):
    def test_make_rel_round_trip(self):
        Rl = ME.make_rel(("a", "b"), (I, STR), [(1, "x"), (None, None)])
        self.assertEqual(tuple(Rl.cols), ("a", "b"))
        self.assertEqual(tuple(Rl.types), (I, STR))
        self.assertEqual([tuple(r) for r in Rl.rows], [(1, "x"), (None, None)])

    def test_norm(self):
        self.assertIsNone(ME.norm(None))
        self.assertEqual(ME.norm(True), 1)
        self.assertEqual(ME.norm(Decimal("2.5")), 2.5)
        self.assertEqual(ME.norm(Decimal("4")), 4)
        self.assertIsInstance(ME.norm(3), int)
        self.assertEqual(ME.norm(3.0), 3)
        self.assertEqual(ME.norm("s"), "s")

    def test_norm_large_integers_exact(self):
        self.assertNotEqual(ME.norm(BIG), ME.norm(BIG + 1))

    def test_bag_equal(self):
        E = ME.make_rel(("a", "b"), (I, I), [(1, 2), (3, 4)])
        self.assertTrue(ME.bag_equal(["b", "a"], [(4, 3), (2, 1)], E))
        self.assertFalse(ME.bag_equal(["a", "b"], [(1, 2)], E))
        self.assertFalse(ME.bag_equal(["a", "c"], [(1, 2), (3, 4)], E))
        Eb = ME.make_rel(("a",), (I,), [(BIG,)])
        self.assertFalse(ME.bag_equal(["a"], [(BIG + 1,)], Eb))


class TestRankSemantics(unittest.TestCase):
    """Native window ranking must reproduce core11 EXACTLY, including ties and NULL ordering (no skip, no waiver)."""

    def test_rank_ast_is_five_element(self):
        self.assertEqual(len(RANK_CANON), 5)
        self.assertEqual(RANK_CANON[4], 1)
        self.assertEqual(ME.rank_ast(("rel", "t"), ["s"], [], 3)[4], 3)

    def test_canonical_rank_executes(self):
        out = C.run(RANK_CANON, simple_env())
        xi = list(out.cols).index("x")
        self.assertEqual(sorted(r[xi] for r in out.rows), [3, 7])

    def test_null_order_probe_calibrated(self):
        self.assertTrue(ME.core11_null_order(refresh=True)["calibrated"])

    def test_tie_rule_probe_calibrated_unique(self):
        sem = ME.core11_rank_semantics(refresh=True)
        self.assertTrue(sem["calibrated"], sem)
        self.assertEqual(len(sem["candidates"]), 1, sem)
        self.assertIn(sem["mode"], ("rank", "row_input", "row_cols"))
        self.assertGreater(sem["probes"], 0)

    def test_compiler_follows_probed_tie_rule(self):
        sem = ME.core11_rank_semantics()
        sql = ME.to_engine_sql(RANK_TIES, "sqlite", L._cols_fn(tie_env()))
        if sem["mode"] == "rank":
            self.assertIn("RANK()", sql)
        else:
            self.assertIn("ROW_NUMBER()", sql)
            self.assertNotIn("RANK()", sql, "RANK() keeps tied rows; core11 does not")

    def test_uncalibrated_rank_never_compiled(self):
        for d in ME.SQL_DIALECTS:
            with self.assertRaises(ME.EngineUnsupported):
                ME.to_engine_sql(RANK_TIES, d, L._cols_fn(tie_env()), rank_sem=dict(calibrated=False))

    def test_reverse_rejects_tie_keeping_window(self):
        sem = ME.core11_rank_semantics()
        if sem["mode"] == "rank":
            self.skipTest("core11 keeps ties: RANK() is the faithful window")
        sql = ('SELECT "uid", "ts", "v" FROM (SELECT *, RANK() OVER (PARTITION BY "uid" ORDER BY "ts" DESC) AS "nx_rk" '
               'FROM "e") AS t2 WHERE "nx_rk" <= 1')
        with self.assertRaises(L.SqlUnsupported):
            ME.from_sql(sql, "sqlite", L._cols_fn(tie_env()))

    def test_rank_ties_conform_on_sqlite(self):
        env = tie_env()
        self.assertIsNone(_core_error(RANK_TIES, env))
        want = C.run(RANK_TIES, env)
        lite = ME.run_engine("sqlite", RANK_TIES, env)
        self.assertEqual(lite["status"], "ok", lite)
        self.assertTrue(ME.bag_equal(lite["names"], lite["rows"], want),
                        dict(sqlite=sorted(lite["rows"], key=repr), core11=sorted(map(tuple, want.rows), key=repr), sql=lite["artifact"]))
        r = ME.conformance(RANK_TIES, env, engines=("sqlite",), require=("sqlite",))
        self.assertTrue(r["conformant"], r)

    def test_rank_earliest_null_order_conforms(self):
        r = ME.conformance(RANK_NULL_ORDER, tie_env(), engines=("sqlite",), require=("sqlite",))
        self.assertTrue(r["conformant"], r)

    def test_rank_tie_round_trip_agrees(self):
        for d in ME.SQL_DIALECTS:
            for ast in (RANK_TIES, RANK_NULL_ORDER):
                r = ME.round_trip(ast, tie_env(), d)
                self.assertEqual(r["status"], "agree", (d, r))

    def test_rank_conforms_on_sqlite(self):
        self.assertTrue(ME.conformance(RANK_CANON, simple_env(), engines=("sqlite",), require=("sqlite",))["conformant"])

    @unittest.skipUnless(PKG.engine_available("polars"), "polars not installed")
    def test_rank_ties_conform_on_polars(self):
        r = ME.conformance(RANK_TIES, tie_env(), engines=("polars",), require=("polars",))
        self.assertTrue(r["conformant"], r)

    @unittest.skipUnless(PKG.engine_available("duckdb"), "duckdb not installed")
    def test_rank_ties_conform_on_duckdb(self):
        r = ME.conformance(RANK_TIES, tie_env(), engines=("duckdb",), require=("duckdb",))
        self.assertTrue(r["conformant"], r)


class TestSqlGeneration(unittest.TestCase):
    def test_unknown_dialect(self):
        with self.assertRaises(ME.EngineUnsupported):
            ME.to_engine_sql(("rel", "t"), "oracle")

    def test_spark_quoting_and_double_literal(self):
        sql = ME.to_engine_sql(("map", ("rel", "t"), (("y", k(1.5, N)),)), "spark")
        self.assertIn("`t`", sql)
        self.assertIn("1.5D", sql)

    def test_duckdb_typed_null_and_double(self):
        sql = ME.to_engine_sql(("map", ("rel", "t"), (("y", k(None, I)), ("z", k(2.0, N)))), "duckdb")
        self.assertIn("CAST(NULL AS BIGINT)", sql)
        self.assertIn("CAST(2.0 AS DOUBLE)", sql)

    def test_spark_anti_join(self):
        ast = ("join", "anti", ("rel", "a"), ("rel", "b"), ("k",), ("k",))
        self.assertIn("LEFT ANTI JOIN", ME.to_engine_sql(ast, "spark"))
        self.assertIn("NOT EXISTS", ME.to_engine_sql(ast, "sqlite"))

    def test_compile_all(self):
        out = ME.compile_all(("map", ("rel", "t"), (("id", col("id")),)), simple_env())
        self.assertEqual(set(out), set(ME.SQL_DIALECTS))
        for d in ME.SQL_DIALECTS:
            self.assertIsNotNone(out[d]["sql"], out[d])


class TestReverse(unittest.TestCase):
    def test_spark_normalisation(self):
        s = ME._spark_to_standard("SELECT `a` FROM `t` WHERE s = 'it\\'s' AND x > 1.5D")
        self.assertIn('"a"', s)
        self.assertIn("'it''s'", s)
        self.assertNotIn("1.5D", s)

    def test_round_trip_map_agrees(self):
        ast = ("map", ("rel", "t"), (("id", col("id")), ("y", ("branch", ("isnull", col("x")), k(0, I), col("x")))))
        for d in ME.SQL_DIALECTS:
            self.assertEqual(ME.round_trip(ast, simple_env(), d)["status"], "agree", d)

    def test_round_trip_rank_agrees(self):
        for d in ME.SQL_DIALECTS:
            r = ME.round_trip(RANK_CANON, simple_env(), d)
            self.assertEqual(r["status"], "agree", (d, r))

    def test_four_element_rank_never_agrees(self):
        if _core_error(RANK_FOUR, simple_env()) is None:
            self.skipTest("core11 also executes the four-element form here")
        for d in ME.SQL_DIALECTS:
            self.assertIn(ME.round_trip(RANK_FOUR, simple_env(), d)["status"], ("core_error", "unsupported"))

    def test_unsupported_sql_rejected(self):
        with self.assertRaises(L.SqlUnsupported):
            ME.from_sql('SELECT "id" FROM "t" ORDER BY "id"', "sqlite")


class TestDataFrameFrontEnd(unittest.TestCase):
    EXPECT = ("filter", ("rel", "t"), ("cmp", "gt", col("x"), k(4, I)))

    def _check(self, code, api):
        env = simple_env()
        ast = ME.from_dataframe(code, api, env)
        want = C.run(("map", self.EXPECT, (("id", col("id")), ("x", col("x")))), env)
        self.assertTrue(L._same(L._run(ast, env), want), (api, ast))

    def test_polars_filter_select(self):
        self._check("t.filter(pl.col('x') > 4).select('id', 'x')", "polars")

    def test_pyspark_filter_select(self):
        self._check("t.filter(F.col('x') > 4).select('id', 'x')", "pyspark")

    def test_unsupported_rejected(self):
        with self.assertRaises(L.SqlUnsupported):
            ME.from_dataframe("t.explode('x')", "polars", simple_env())
        with self.assertRaises(ME.EngineUnsupported):
            ME.from_dataframe("t", "pandas", simple_env())

    def test_fidelity_never_agrees_without_engine(self):
        r = ME.dataframe_fidelity("t.filter(pl.col('x') > 4).select('id', 'x')", simple_env(), "polars")
        self.assertEqual(r["status"], "agree" if PKG.engine_available("polars") else "unavailable", r)


class TestConformance(unittest.TestCase):
    AST = ("filter", ("map", ("rel", "t"), (("id", col("id")), ("x", col("x")))), ("cmp", "gt", col("x"), k(4, I)))

    def test_core11_and_sqlite_agree(self):
        self.assertTrue(ME.conformance(self.AST, simple_env(), engines=("sqlite",))["conformant"])

    def test_disagreement_fails_closed(self):
        wrong = ME.make_rel(("id", "x"), (I, I), [(1, 5)])
        r = ME.conformance(self.AST, simple_env(), expected=wrong, engines=("sqlite",))
        self.assertFalse(r["conformant"])
        self.assertEqual(r["reason"], "disagree")

    def test_unavailable_engine_never_agrees(self):
        r = ME.conformance(self.AST, simple_env(), engines=("sqlite", "no_such_engine"), require=("no_such_engine",))
        self.assertEqual(r["statuses"]["no_such_engine"], "unavailable")
        self.assertFalse(r["conformant"])

    def test_budget_refusal_is_unchecked(self):
        r = ME.conformance(self.AST, simple_env(), engines=("sqlite",), budget=_RefusingBudget())
        self.assertEqual(r["statuses"]["sqlite"], "unchecked")
        self.assertFalse(r["conformant"])

    def test_upsert_semantics(self):
        env = {"old": ME.make_rel(("k", "val"), (I, STR), [(1, "a"), (2, "b"), (3, "c")]),
               "new": ME.make_rel(("k", "val"), (I, STR), [(2, "B"), (4, "D")])}
        out = C.run(ME.upsert_ast(("rel", "old"), ("rel", "new"), ("k",), ("k", "val")), env)
        got = Counter(tuple(r) for r in L._run(("map", ("rel", "o"), (("k", col("k")), ("val", col("val")))), {"o": out}).rows)
        self.assertEqual(got, Counter([(1, "a"), (3, "c"), (2, "B"), (4, "D")]))

    def test_suite_structure_and_no_core_errors(self):
        rep = ME.conformance_suite(engines=("sqlite",), round_trips=True)
        self.assertIsNone(rep["build_error"])
        self.assertGreater(rep["n_cases"], 10)
        self.assertEqual(set(rep["by_feature"]), set(ME.FEATURES))
        self.assertEqual(rep["core_error_cases"], [])
        self.assertTrue(rep["null_order"]["calibrated"])
        self.assertTrue(rep["rank_semantics"]["calibrated"], rep["rank_semantics"])
        names = {r["case"] for r in rep["cases"]}
        self.assertIn("rank_latest_ties", names, "tie cases must stay in the suite")
        self.assertIn("rank_earliest_null_order", names)
        for r in [r for r in rep["cases"] if r["feature"] == "window_rank"]:
            self.assertEqual(r["statuses"]["sqlite"], "agree", r)
            for d, st in r["round_trip"].items():
                self.assertEqual(st, "agree", (r["case"], d, r["round_trip_detail"]))
        self.assertEqual(rep["failing_cases"], [])
        self.assertTrue(rep["required_ok"])


# ------------------------------------------------------------------ dag_repair14
def _inst(spec_idx=0, seed=999001, front="ast", dialect="sqlite"):
    return R.make_instance(R.SPECS[spec_idx], seed, front=front, dialect=dialect)


class TestDagView(unittest.TestCase):
    def test_dag_info_layered(self):
        info = D.dag_info(L.Pipeline(R._build_d1(True)))
        self.assertTrue(info["layered"])
        self.assertEqual(info["violations"], [])
        self.assertEqual(info["sinks"], ["fct_counts"])
        self.assertEqual(info["downstream"]["stg_events"], ["int_counts", "fct_counts"])

    def test_dag_violations_reported(self):
        p = L.Pipeline([("int_a", ("map", ("rel", "raw"), (("x", col("x")),))),
                        ("stg_b", ("map", ("rel", "int_a"), (("x", col("x")),)))])
        kinds = {v["kind"] for v in D.dag_info(p)["violations"]}
        self.assertIn("stg_reads_model", kinds)
        self.assertIn("layer_inversion", kinds)


class TestColumns(unittest.TestCase):
    def test_column_diff(self):
        A = ME.make_rel(("a", "b"), (I, I), [(1, 2), (3, 4)])
        E = ME.make_rel(("a", "b"), (I, I), [(1, 2), (3, 5)])
        self.assertEqual(D.column_diff(A, E)["mismatched"], ["b"])
        self.assertTrue(D.column_diff(None, E)["error"])

    def test_lineage(self):
        self.assertTrue({"total", "y", "sensor"} <= D.lineage(L.Pipeline(R._build_d3(True)), 2, [1], ["total"]))

    def test_narrow_and_splice(self):
        ast = ("map", ("rel", "t"), (("id", col("id")), ("y", col("x")), ("s", col("s"))))
        nast, kept = D.narrow_stage(ast, ["y"])
        self.assertEqual(kept, ["y"])
        fixed = ("map", ("rel", "t"), (("y", ("branch", ("isnull", col("x")), k(0, I), col("x"))),))
        full = D.splice_stage(ast, nast, fixed)
        self.assertEqual(full[2][0], ("id", col("id")))
        self.assertEqual(full[2][1][1][0], "branch")
        self.assertIsNone(D.narrow_stage(ast, ["id", "y", "s"]))


class TestLocalizeAndRepair(unittest.TestCase):
    def test_localize_unobserved_fault_without_queries(self):
        loc = D.localize_dag(_inst(0)["broken"], _inst(0)["batches"])
        self.assertEqual(loc["broken"], "fct_counts")
        self.assertEqual(loc["status"], "localized", loc)
        self.assertEqual(loc["fault"], "int_counts")
        self.assertIsNone(loc["variant"])

    def test_repair_dag_with_oracle_node_only(self):
        inst = _inst(0)
        res = D.repair_dag(inst["broken"], inst["batches"], oracle=inst["oracle"], query_budget=2, engines=("sqlite",))
        self.assertEqual(res["over_cap"], [])
        self.assertEqual(res["status"], "repaired", res["reason"])
        self.assertEqual(res["changed_nodes"], ["int_counts"])
        self.assertTrue(res["node_isolated"])
        self.assertGreaterEqual(res["invariants"]["max_width"], 50)
        self.assertTrue(R.grade(inst, res["pipeline"])["verified"])

    def test_repair_dag_abstains_without_oracle(self):
        inst = _inst(0)
        res = D.repair_dag(inst["broken"], inst["batches"], oracle=None, engines=("sqlite",))
        self.assertNotEqual(res["status"], "repaired")
        self.assertEqual(res["queries_used"], 0)

    def test_unknown_lift_option_rejected(self):
        inst = _inst(0)
        with self.assertRaises(ValueError):
            D.repair_dag(inst["broken"], inst["batches"], bogus_option=1)

    def test_verify_downstream(self):
        inst = _inst(0)
        ref = inst["reference"]
        ok = D.verify_downstream(ref, ref, inst["batches"], [], engines=("sqlite",), require_engines=("sqlite",))
        self.assertTrue(ok["ok"], ok["failed"])
        bad = ref.replace(2, ("map", ("rel", "int_counts"), (("g", col("g")),)), origin="test")
        rep = D.verify_downstream(ref, bad, inst["batches"], [], engines=("sqlite",))
        self.assertIn("untouched_nodes_changed", rep["failed"])
        req = D.verify_downstream(ref, ref, inst["batches"], [], engines=("sqlite",), require_engines=("no_such_engine",))
        self.assertIn("required_engine_dag", req["failed"])


# ------------------------------------------------------------------ native fronts
class TestNativeSqlFront(unittest.TestCase):
    def test_every_spec_lifts_from_authored_sqlite_source(self):
        for idx, spec in enumerate(R.SPECS):
            with self.subTest(spec=spec["name"]):
                inst = _inst(idx, 999400 + idx, front="sql:sqlite")
                self.assertEqual(inst["front"], "sql:sqlite")
                for st in inst["broken"].stages:
                    self.assertEqual(st["origin"], "sql:sqlite")
                    self.assertTrue(st["source"])
                self.assertTrue(D.source_fidelity(inst["broken"], inst["batches"])["faithful"])

    def test_other_dialects_fidelity_fail_closed(self):
        for dialect in ("duckdb", "spark"):
            with self.subTest(dialect=dialect):
                inst = _inst(0, 999500, front=f"sql:{dialect}")
                fid = D.source_fidelity(inst["broken"], inst["batches"])
                if PKG.engine_available(D.SQL_ENGINE[dialect]):
                    self.assertTrue(fid["faithful"], fid)
                else:
                    self.assertFalse(fid["faithful"])
                    self.assertEqual(fid["reason"], "unverified")

    def test_repair_lifted_sql_dag(self):
        inst = _inst(0, 999600, front="sql:sqlite")
        res = D.repair_dag(inst["broken"], inst["batches"], oracle=inst["oracle"], query_budget=2, engines=("sqlite",))
        self.assertIsNone(res["source_fidelity"].get("reason"), res["source_fidelity"])
        self.assertEqual(res["status"], "repaired", res["reason"])
        self.assertTrue(R.grade(inst, res["pipeline"], required=("sqlite",))["verified"])
        self.assertTrue(all(o["sql"] for o in D.compile_dag(res["pipeline"], inst["batches"][0]["inputs"], "spark")))


class TestDataFrameFront(unittest.TestCase):
    def test_every_spec_lifts_from_authored_dataframe_source(self):
        for api in ("polars", "pyspark"):
            for idx, spec in enumerate(R.SPECS):
                with self.subTest(api=api, spec=spec["name"]):
                    inst = _inst(idx, 999900 + idx, front=f"df:{api}")
                    self.assertEqual(inst["front"], f"df:{api}")
                    self.assertEqual(len(inst["sources"]), len(spec["build"](True)))
                    for st in inst["broken"].stages:
                        self.assertEqual(st["origin"], f"df:{api}")
                    for key in ("drift_broken", "drift_reference", "fault_observable", "reference_fidelity", "reference_gradable"):
                        self.assertIn(key, inst["front_info"])
                    fid = D.source_fidelity(inst["broken"], inst["batches"])
                    if not PKG.engine_available(api):
                        self.assertFalse(fid["faithful"], "an uninstalled DataFrame engine never establishes fidelity")
                        self.assertEqual(fid["reason"], "unverified")

    @unittest.skipUnless(PKG.engine_available("polars"), "polars not installed")
    def test_polars_front_row_executes(self):
        inst = _inst(0, 999950, front="df:polars")
        fid = D.source_fidelity(inst["broken"], inst["batches"])
        self.assertTrue(fid["faithful"], fid)
        cfg = dict(fc_cap=5000, invariant_engines=("sqlite", "polars"), required_engines=("sqlite", "polars"))
        res, _ = R.solve(inst, 2, {}, cfg, 20.0)
        self.assertIsNone(res["fidelity_gate"])
        self.assertEqual(R._combined(res, 2, 5000)[2], [])


class TestReferenceFidelity(unittest.TestCase):
    """The lifted authored REFERENCE is ground truth only when its original source agrees natively with its lift (fail-closed)."""

    def test_sql_reference_faithful_and_gradable(self):
        inst = _inst(0, 999960, front="sql:sqlite")
        rf = inst["front_info"]["reference_fidelity"]
        self.assertTrue(rf["faithful"], rf)
        self.assertTrue(inst["front_info"]["reference_gradable"])
        self.assertTrue(R.grade(inst, inst["reference"], required=("sqlite",))["graded"])

    def test_df_reference_graded_only_when_faithful(self):
        inst = _inst(0, 999961, front="df:polars")
        rf, info = inst["front_info"]["reference_fidelity"], inst["front_info"]
        g = R.grade(inst, inst["reference"], required=("sqlite",))
        self.assertEqual(info["reference_gradable"], rf["faithful"])
        if not PKG.engine_available("polars"):
            self.assertFalse(rf["faithful"])
            self.assertEqual(rf["reason"], "unverified")
            self.assertFalse(g["graded"])
            self.assertFalse(g["verified"])
            self.assertEqual(g["reason"], "reference_fidelity_unverified")
        else:
            self.assertEqual(g["graded"], rf["faithful"])

    def test_unfaithful_reference_is_build_error(self):
        def fake(p, b, budget=None):
            return dict(checked=True, faithful=False, reason="unfaithful", tally={"disagree": 1}, rows=[], failures={}, engines=["sqlite"])
        with mock.patch.object(R.D, "source_fidelity", fake):
            with self.assertRaises(RuntimeError):
                _inst(0, 999962, front="sql:sqlite")


# ------------------------------------------------------------------ operators
def _d6_operator():
    inst = R.make_instance(R.SPECS[5], 999200)
    i = inst["broken"].index("fct_totals")
    return R.extract_operator(inst["broken"].stages[i]["ast"], inst["reference"].stages[i]["ast"]), inst


class TestOperators(unittest.TestCase):
    def test_extract_operator_anti_unifies(self):
        op, _ = _d6_operator()
        self.assertEqual(op["pattern"], ("?o0", "count_star", None))
        self.assertEqual(op["replacement"], ("?o0", "sum", ("col", "?c0")))
        self.assertIsNone(R.extract_operator(("rel", "t"), ("rel", "t")))

    def test_library_admission_and_isolation(self):
        _, inst = _d6_operator()
        i = inst["broken"].index("fct_totals")
        old, new = inst["broken"].stages[i]["ast"], inst["reference"].stages[i]["ast"]
        lib = R.OperatorLibrary()
        key = lib.observe(old, new, True)
        self.assertEqual([o["key"] for o in lib.admitted()], [key])
        lib.observe(old, new, False)
        self.assertEqual(lib.admitted(), [])
        frozen = lib.copy(frozen=True)
        with self.assertRaises(S13.FrozenSelectorError):
            frozen.observe(old, new, True)
        self.assertEqual(frozen.fingerprint(), lib.fingerprint())

    def test_operator_transfers_to_held_out_d7(self):
        op, _ = _d6_operator()
        inst = R.make_instance(R.SPECS[6], 999300)
        res = R.operator_stage(inst["broken"], inst["batches"], [op], oracle=inst["oracle"], bq=2, fc_cap=2000, wall=20.0)
        self.assertEqual(res["status"], "repaired", res.get("reason"))
        self.assertEqual(res["changed_nodes"], ["fct_region"])
        self.assertGreater(res["work"].get("constructed_asts", 0), 0)
        self.assertTrue(R.grade(inst, res["pipeline"], required=("sqlite",))["verified"])

    def test_operator_stage_declines_without_operators(self):
        inst = R.make_instance(R.SPECS[6], 999301)
        res = R.operator_stage(inst["broken"], inst["batches"], [], oracle=inst["oracle"], bq=2)
        self.assertEqual((res["status"], res["reason"], res["queries_used"]), ("declined", "no_operators", 0))


class TestFidelityGate(unittest.TestCase):
    """The shared fail-closed source-fidelity gate runs BEFORE either repair path (learned operators or repair_dag)."""
    CFG = dict(fc_cap=5000, invariant_engines=("sqlite",))

    def test_faithful_source_allows_operator_path(self):
        op, _ = _d6_operator()
        inst = R.make_instance(R.SPECS[6], 999710, front="sql:sqlite")
        res, opr = R.solve(inst, 2, {}, self.CFG, 20.0, operators=[op])
        self.assertIsNone(res["fidelity_gate"])
        self.assertIsNotNone(opr)
        self.assertEqual(res["status"], "repaired", (res.get("reason"), opr.get("reason")))
        self.assertTrue(res.get("operator_path"))
        self.assertIsNone((res.get("source_fidelity") or {}).get("reason"))

    def test_unfaithful_source_blocks_operator_path(self):
        op, _ = _d6_operator()
        inst = R.make_instance(R.SPECS[6], 999711, front="sql:sqlite")
        st = inst["broken"].stages[inst["broken"].index("fct_region")]
        st["source"] = "SELECT region, SUM(units) AS revenue_total FROM int_sales GROUP BY region"   # native text != lifted AST
        self.assertFalse(D.source_fidelity(inst["broken"], inst["batches"])["faithful"])
        res, opr = R.solve(inst, 2, {}, self.CFG, 20.0, operators=[op])
        self.assertEqual(res["fidelity_gate"], "unfaithful_parse")
        self.assertIsNone(opr, "the operator stage must not run on an unfaithful source")
        self.assertFalse(res.get("operator_path"))
        self.assertNotEqual(res["status"], "repaired")
        self.assertEqual(R._combined(res, 2, 5000)[2], [])

    @unittest.skipIf(PKG.engine_available("duckdb"), "duckdb installed: fidelity can be established")
    def test_unavailable_engine_source_never_submits(self):
        op, _ = _d6_operator()
        inst = R.make_instance(R.SPECS[6], 999712, front="sql:duckdb")
        res, opr = R.solve(inst, 2, {}, self.CFG, 20.0, operators=[op])
        self.assertEqual(res["fidelity_gate"], "fidelity_unverified")
        self.assertIsNone(opr)
        self.assertNotEqual(res["status"], "repaired")

    def test_fidelity_blocked_rows_counted(self):
        rows = [dict(stream="rep0", budget=2, arm="trained", status="fidelity_unverified", fidelity_gate="fidelity_unverified",
                     verified=False, submitted=False, wrong=False, abstained=True, work={}, over_cap=[], queries_used=0)]
        self.assertEqual(R.summarize(rows)["rep0|B2|trained"]["fidelity_blocked"], 1)


class TestRequiredEnginesGateRepairs(unittest.TestCase):
    """Whole-DAG native verification on every REQUIRED engine gates BOTH repair paths on the shared row budget, BEFORE a repair is
    accepted (not deferred to unmetered grading). Unavailable / disagreeing / unchecked required engines block submission."""

    @staticmethod
    def _cfg(required):
        return dict(fc_cap=5000, invariant_engines=("sqlite",), required_engines=tuple(required))

    @staticmethod
    def _disagree(p, b, engine, budget=None):
        return dict(engine=engine, status="disagree", compared=1)

    def test_successful_repair_records_required_engine_agreement(self):
        inst = _inst(0, 999720)
        res, _ = R.solve(inst, 2, {}, self._cfg(("sqlite",)), 20.0)
        self.assertEqual(res["status"], "repaired", res.get("reason"))
        self.assertEqual(res["required_engine_dag"], {"sqlite": "agree"})
        self.assertIn("sqlite", res["required_engines"])

    def test_unavailable_required_engine_blocks_repair_dag_path(self):
        inst = _inst(0, 999721)
        res, op = R.solve(inst, 2, {}, self._cfg(("sqlite", "no_such_engine")), 20.0)
        self.assertIsNone(op)
        self.assertNotEqual(res["status"], "repaired")
        self.assertIn("required_engine_dag", res["invariants"]["failed"])
        self.assertEqual(res["required_engine_dag"].get("no_such_engine"), "unavailable")
        self.assertIn("no_such_engine", res["required_engines"])
        self.assertEqual(R._combined(res, 2, 5000)[2], [])

    def test_unavailable_required_engine_blocks_operator_path(self):
        op, _ = _d6_operator()
        inst = R.make_instance(R.SPECS[6], 999722)
        opr = R.operator_stage(inst["broken"], inst["batches"], [op], oracle=inst["oracle"], bq=2, fc_cap=2000, wall=20.0,
                               require_engines=("sqlite", "no_such_engine"))
        self.assertNotEqual(opr["status"], "repaired")
        self.assertTrue(str(opr["reason"]).startswith("invariants_failed"), opr["reason"])
        self.assertIn("required_engine_dag", opr["reason"])
        res, opr2 = R.solve(inst, 2, {}, self._cfg(("sqlite", "no_such_engine")), 20.0, operators=[op])
        self.assertIsNotNone(opr2)
        self.assertNotEqual(opr2["status"], "repaired")
        self.assertFalse(res.get("operator_path"))
        self.assertNotEqual(res["status"], "repaired")
        self.assertEqual(R._combined(res, 2, 5000)[2], [])

    def test_required_engine_disagreement_blocks_both_paths(self):
        op, _ = _d6_operator()
        inst = R.make_instance(R.SPECS[6], 999723)
        with mock.patch.object(D, "engine_dag_check", self._disagree):
            res, opr = R.solve(inst, 2, {}, self._cfg(("sqlite",)), 20.0, operators=[op])
        self.assertIsNotNone(opr)
        self.assertNotEqual(opr["status"], "repaired")
        self.assertNotEqual(res["status"], "repaired")
        self.assertIn("required_engine_dag", res["invariants"]["failed"])

    def test_required_engine_check_is_metered_on_caller_budget(self):
        inst = _inst(0, 999724)
        r = D.engine_dag_check(inst["reference"], inst["batches"], "sqlite", budget=_RefusingBudget())
        self.assertEqual(r["status"], "unchecked", r)
        ok = D.engine_dag_check(inst["reference"], inst["batches"], "sqlite")
        self.assertEqual(ok["status"], "agree", ok)
        self.assertGreater(ok["compared"], 0)

    def test_operator_path_records_required_engine_agreement(self):
        op, _ = _d6_operator()
        inst = R.make_instance(R.SPECS[6], 999725)
        res, opr = R.solve(inst, 2, {}, self._cfg(("sqlite",)), 20.0, operators=[op])
        self.assertEqual(opr["status"], "repaired", opr.get("reason"))
        self.assertTrue(res.get("operator_path"))
        self.assertEqual(res["required_engine_dag"], {"sqlite": "agree"})


class TestSharedBudget(unittest.TestCase):
    def _check_row(self, inst, operators, bq=2, fc_cap=5000):
        res, op = R.solve(inst, bq, {}, dict(fc_cap=fc_cap, invariant_engines=("sqlite",)), 20.0, operators=operators)
        work, q, over = R._combined(res, bq, fc_cap)
        self.assertEqual(over, [], (work, q))
        self.assertLessEqual(q, bq)
        self.assertLessEqual(work.get("full_checks", 0), fc_cap)
        return res, op, work

    def test_operator_path_within_row_caps(self):
        op, _ = _d6_operator()
        res, opr, _ = self._check_row(R.make_instance(R.SPECS[6], 999700), [op])
        self.assertEqual(opr["status"], "repaired", opr.get("reason"))

    def test_forced_fallback_shares_one_budget(self):
        op, _ = _d6_operator()
        res, opr, work = self._check_row(R.make_instance(R.SPECS[0], 999701), [op])
        self.assertNotEqual(opr["status"], "repaired")
        self.assertGreaterEqual(work.get("full_checks", 0), opr["work"].get("full_checks", 0))

    def test_small_cap_never_overruns(self):
        op, _ = _d6_operator()
        self._check_row(R.make_instance(R.SPECS[6], 999702), [op], fc_cap=60)


# ------------------------------------------------------------------ runner14
class TestRunnerParts(unittest.TestCase):
    def test_seed_disjoint(self):
        self.assertEqual(R.seed_overlap(20, 20), [])

    def test_parse_front(self):
        self.assertEqual(R.parse_front("sql"), ("sql", "sqlite"))
        self.assertEqual(R.parse_front("df:pyspark"), ("df", "pyspark"))
        self.assertEqual(R.parse_front("ast"), ("ast", None))
        self.assertEqual(R.front_engine("sql:spark"), "pyspark")
        for bad in ("sql:oracle", "df:pandas", "bogus"):
            with self.assertRaises(ValueError):
                R.parse_front(bad)

    def test_specs_instances_and_observable_faults(self):
        for idx, spec in enumerate(R.SPECS):
            with self.subTest(spec=spec["name"]):
                inst = _inst(idx, 999100 + idx)
                self.assertEqual((len(inst["batches"]), len(inst["hidden"])), (3, 2))
                outs, errs = inst["reference"].run(inst["batches"][0]["inputs"])
                self.assertEqual(errs, {})
                self.assertGreaterEqual(max(len(o.cols) for o in outs.values()), 50)
                changed = [s["name"] for s, s0 in zip(inst["broken"].stages, inst["reference"].stages) if s["ast"] != s0["ast"]]
                self.assertEqual(changed, list(spec["faults"]))
                self.assertIsNotNone(L.localize(inst["broken"], inst["batches"])["broken"])

    def test_grade_and_engine_dag(self):
        inst = _inst(0)
        self.assertTrue(R.grade(inst, inst["reference"], required=("sqlite",))["verified"])
        self.assertFalse(R.grade(inst, inst["broken"])["verified"])
        self.assertFalse(R.grade(inst, inst["reference"], required=("no_such_engine",))["verified"])
        h = inst["hidden"][0]
        self.assertEqual(R.engine_dag(inst["reference"], h["inputs"], "sqlite", h["ref"])["status"], "agree")
        self.assertEqual(R.engine_dag(inst["reference"], h["inputs"], "no_such_engine", h["ref"])["status"], "unavailable")

    def test_source_meter(self):
        m = R.SourceMeter(dict(ref_answers=(2, 3)))
        self.assertTrue(m.charge("ref_answers") and m.charge("ref_answers"))
        self.assertFalse(m.charge("ref_answers"))
        m.new_episode()
        self.assertTrue(m.charge("ref_answers"))
        self.assertFalse(m.charge("ref_answers"))
        self.assertEqual(m.over(), [])

    def test_arm_kwargs(self):
        self.assertIs(R.arm_kwargs("fixed", "rep0", "t", 2)["menu"], R._static_menu)
        self.assertNotIn("menu", R.arm_kwargs("untrained", "rep0", "t", 2))
        self.assertFalse(R.arm_kwargs("single_shot", "rep0", "t", 0)["require_unique"])
        with self.assertRaises(ValueError):
            R.arm_kwargs("oracle_cheat", "rep0", "t", 2)
        op, _ = _d6_operator()
        lib = R.OperatorLibrary()
        lib.ops[op["key"]], lib.pos[op["key"]] = op, 1
        frozen = (S13.Selector(name="sel").freeze(), S13.DeltaStateGuide().freeze(), lib.copy(frozen=True),
                  S13.Selector(name="nr").freeze())
        self.assertEqual([o["key"] for o in R.arm_kwargs("trained", "rep0", "t", 2, frozen)["operators"]], [op["key"]])
        self.assertNotIn("operators", R.arm_kwargs(R.ABLATION, "rep0", "t", 2, frozen))
        self.assertEqual(R.arm_kwargs(R.NO_REGRET, "rep0", "t", 2, frozen)["chooser"].__self__.name, "nr")

    def _rows(self, ver, arms=PKG.ARMS):
        rows = []
        for st in R.STREAMS:
            for arm in arms:
                for t in range(4):
                    v = t < ver[arm]
                    rows.append(dict(stream=st, budget=2, arm=arm, task=f"T{t}", verified=v, wrong=False, submitted=v, abstained=not v,
                                     status="repaired" if v else "abstained", held_out=t % 2 == 1, over_cap=[], queries_used=1,
                                     work=dict(full_checks=10, probe_evals=5)))
        return rows

    def test_contrasts_and_verdict(self):
        con = R.contrasts(self._rows(dict(fixed=0, random=1, untrained=1, trained=4)), [2])
        self.assertEqual(con["rep0|B2"]["trained_minus"], dict(fixed=4, random=3, untrained=3))
        self.assertEqual(R.verdict(con, 2), "positive")
        self.assertEqual(R.verdict(R.contrasts(self._rows(dict(fixed=4, random=4, untrained=4, trained=1)), [2]), 2), "negative")
        self.assertEqual(R.verdict({}, 2), "insufficient")

    def test_progression_isolates_regret(self):
        arms = tuple(PKG.ARMS) + R.ABLATIONS
        prog = R.progression(self._rows(dict(fixed=0, random=0, untrained=1, trained=3, trained_no_ops=2, trained_no_regret=2),
                                        arms=arms), 2)
        for st in R.STREAMS:
            self.assertEqual(prog[st]["self_evolution_delta"], 0.25)
            self.assertEqual(prog[st]["self_evolution_combined"], 0.5)
            self.assertIsNone(prog[st]["enterprise_reliability_advantage"])

    def test_capability_acceptance(self):
        good = {st: {k2: 0.5 for k2 in R.PROGRESSION_KEYS} for st in R.STREAMS}
        fronts = ("sql:sqlite", "df:polars")
        rows = [dict(front=f, verified=True) for f in fronts]
        with mock.patch.object(R, "engine_available", lambda e: True):
            ok = R.capability_acceptance(good, dict(required_engines=("sqlite", "duckdb"), fronts=fronts), rows)
            self.assertTrue(ok["accepted"], ok)
            self.assertTrue(ok["enforced"], "acceptance is blocking by default")
            nover = R.capability_acceptance(good, dict(required_engines=("sqlite", "duckdb"), fronts=fronts), rows[:1])
            self.assertIn("front:df:polars:no_verified_repair", nover["failed"])
            adv = R.capability_acceptance(good, dict(required_engines=("sqlite", "duckdb"), fronts=fronts, require_acceptance=False))
            self.assertFalse(adv["enforced"])
        bad = dict(good, rep0=dict(good["rep0"], transfer_efficiency=0))
        r = R.capability_acceptance(bad, dict(required_engines=("sqlite",), fronts=("ast",)))
        self.assertFalse(r["accepted"])
        for f in ("rep0:transfer_efficiency=0", "multi_engine:no_non_sqlite_required_engine_available",
                  "front:no_authored_native_sql_front", "front:no_dataframe_front"):
            self.assertIn(f, r["failed"])
        with mock.patch.object(R, "engine_available", lambda e: e in ("sqlite", "core11")):
            r2 = R.capability_acceptance(good, dict(required_engines=("sqlite", "duckdb"), fronts=fronts))
            self.assertIn("front:df:polars:engine_unavailable:polars", r2["failed"])

    def test_semantic_check_fail_closed(self):
        self.assertTrue(R.semantic_check(None)["ok"])
        self.assertFalse(R.semantic_check(dict(build_error="boom"))["ok"])
        cases = [dict(feature=f, reason=None) for f in ME.FEATURES]
        self.assertTrue(R.semantic_check(dict(required_ok=True, cases=cases))["ok"])
        bad = dict(required_ok=False, cases=cases, failing_cases=[dict(case="rank_latest_ties", feature="window_rank", engine="sqlite",
                                                                     status="disagree")])
        self.assertEqual(R.semantic_check(bad, allow_core_gaps=True)["reason"], "failing_cases")

    def test_live_suite_passes_semantic_check(self):
        sem = R.semantic_check(ME.conformance_suite(engines=("sqlite",)))
        self.assertTrue(sem["ok"], sem)
        self.assertFalse(sem["core_gaps_waived"])

    def test_config(self):
        cfg = R.config_from(R.parse_args(["--quick", "--budgets", "1,2"]))
        self.assertEqual((cfg["eval_instances"], cfg["budgets"]), (1, [2]))
        self.assertEqual(tuple(cfg["fronts"]), R.DEFAULT_FRONTS)
        self.assertTrue(cfg["require_acceptance"])
        self.assertFalse(R.config_from(R.parse_args(["--advisory-acceptance"]))["require_acceptance"])
        self.assertEqual(cfg["required_engines"][0], "sqlite")
        for e in cfg["required_engines"][1:]:
            self.assertTrue(PKG.engine_available(e))
        self.assertEqual(_cfg()["required_engines"], ("sqlite",))
        with self.assertRaises(ValueError):
            R.config_from(R.parse_args(["--fronts", "sql:oracle"]))

    def test_fc_cap_above_max_rejected(self):
        with self.assertRaises(ValueError):
            R.run_experiment(R.config_from(R.parse_args(["--fc-cap", str(R.FC_MAX + 1)])))


class TestRowsNeverError(unittest.TestCase):
    def test_rows_per_spec_and_front_no_error(self):
        cfg = _cfg()
        for front in cfg["fronts"]:
            for idx, spec in enumerate(R.SPECS):
                inst = R.make_instance(spec, 999800 + idx, front=front)
                for arm in ("fixed", "untrained", "single_shot"):
                    bq = 0 if arm == "single_shot" else 2
                    with self.subTest(front=front, spec=spec["name"], arm=arm):
                        rec = R.run_row(inst, arm, "rep0", bq, R.arm_kwargs(arm, "rep0", inst["task"], bq), cfg, 12.0)
                        self.assertNotEqual(rec["status"], "error", (rec.get("error"), rec.get("traceback")))
                        self.assertEqual(rec["over_cap"], [])
                        self.assertEqual(rec["front"], front)
                        self.assertLessEqual(rec["queries_used"], bq)
                        if rec["fidelity_gate"]:
                            self.assertFalse(rec["submitted"], "a fidelity-blocked row is never submitted")
                        if not rec["reference_gradable"]:
                            self.assertFalse(rec["verified"] or rec["wrong"], "an ungradable reference is never graded")
                        if rec["submitted"]:
                            for e in rec["required_engines"]:
                                self.assertEqual((rec["required_engine_dag"] or {}).get(e), "agree",
                                                 "a submitted row passed whole-DAG verification on every required engine")

    def test_source_training_no_error_episodes(self):
        parts = R.train_stream(0, dict(_cfg(), source_instances=1), time.time() + 120.0)
        self.assertTrue(parts[4])
        self.assertEqual([(e.get("spec"), e.get("error")) for e in parts[4] if e.get("status") == "error"], [])
        self.assertEqual(parts[3].over(), [])
        self.assertEqual(len(parts), 7)


def _trivial_train(si, cfg, deadline):
    return S13.Selector(), S13.DeltaStateGuide(), R.OperatorLibrary(), R.SourceMeter(), [], {}, S13.Selector(name="nr")


def _error_row(inst, arm, stream, bq, kw, cfg, wall):
    return dict(task=inst["task"], spec=inst["spec"]["name"], held_out=inst["spec"]["held_out"], seed=inst["seed"], stream=stream,
                arm=arm, budget=bq, beyond_single_edit=False, status="error", error="RuntimeError: injected", traceback="tb",
                submitted=False, verified=False, wrong=False, abstained=False, over_cap=[], work={}, queries_used=0, wall=0.0)


def _quick(tmp, *extra):
    return R.config_from(R.parse_args(["--quick", "--grant-seconds", "300", "--out", tmp, "--engines", "sqlite", "--no-suite",
                                       "--fronts", "sql:sqlite"] + list(extra)))


class TestRunnerEndToEnd(unittest.TestCase):
    def test_error_rows_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(R, "SPECS", (R.SPECS[0],)), mock.patch.object(R, "train_stream", _trivial_train), \
                    mock.patch.object(R, "run_row", _error_row):
                results, code = R.run_experiment(_quick(tmp, "--advisory-acceptance"))
            self.assertEqual(code, 1)
            self.assertIn("error_rows", results["checks"]["failures"])
            self.assertEqual(results["checks"]["error_row_details"][0]["traceback"], "tb")

    def test_acceptance_enforced_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(R, "SPECS", (R.SPECS[0],)), mock.patch.object(R, "train_stream", _trivial_train):
                results, code = R.run_experiment(_quick(tmp))
            self.assertTrue(results["capability_acceptance"]["enforced"])
            self.assertFalse(results["capability_acceptance"]["accepted"])
            self.assertIn("front:no_dataframe_front", results["capability_acceptance"]["failed"])
            self.assertIn("capability_acceptance", results["checks"]["failures"])
            self.assertEqual(code, 1)

    def test_tiny_experiment_advisory(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _quick(tmp, "--advisory-acceptance")
            with mock.patch.object(R, "SPECS", (R.SPECS[0],)):
                results, code = R.run_experiment(cfg)
            ch = results["checks"]
            self.assertEqual(ch["over_cap_rows"], 0)
            self.assertEqual(ch["error_rows"], 0, ch.get("error_row_details"))
            self.assertEqual(ch["source_error_episodes"], [])
            self.assertTrue(ch["isolation_ok"])
            self.assertEqual(ch["failures"], [])
            self.assertFalse(ch["capability_enforced"])
            self.assertTrue(ch["required_engines_gate_repairs"])
            self.assertEqual(code, 0)
            self.assertLessEqual(ch["max_full_checks"], cfg["fc_cap"])
            self.assertTrue((Path(tmp) / "results.json").exists())
            for st in R.STREAMS:
                for arm in tuple(PKG.ARMS) + R.ABLATIONS:
                    self.assertEqual(results["summaries"][f"{st}|B2|{arm}"]["rows"], 1)
                self.assertIn("no_regret", results["isolation"]["streams"][st]["before"])
                self.assertIn("admitted_operators", results["learned_by_nexus"][st])
            self.assertIn("sql:sqlite", results["front_info"])
            self.assertIn("front:sql:sqlite", results["verdict"])


if __name__ == "__main__":
    unittest.main()
