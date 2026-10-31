"""Phase 13 unit tests (NOT LOCKED): program-aware proposals + Shadow-Edge Version Spaces, trainable selector + counterfactual regret,
out-of-sandbox SQL localize-and-lift, and the bounded runner's isolation / strict-cap guarantees. Standard-library unittest only."""
from __future__ import annotations

import os
import random
import sys
import tempfile
import unittest

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from nexus.de_phase11 import core11 as C                                      # noqa: E402
from nexus.de_phase12 import synth12 as S                                     # noqa: E402
from nexus.de_phase13 import WORK_CAPS                                        # noqa: E402
from nexus.de_phase13 import pipeline_lifter13 as PL                          # noqa: E402
from nexus.de_phase13 import proposals13 as P                                 # noqa: E402
from nexus.de_phase13 import runner13 as R                                    # noqa: E402
from nexus.de_phase13 import selector13 as L                                  # noqa: E402

col = lambda c: ("col", c)                                                   # noqa: E731


def _fam(name):
    for f in R._families():
        if f["name"] == name:
            return f
    raise unittest.SkipTest(f"family {name} unavailable in this core11 build")


def _rec(name, seed=999001):
    return R.build_task(_fam(name), seed, "test")


def _spec(name):
    for s in R._pipeline_specs():
        if s["name"] == name:
            return s
    raise unittest.SkipTest(f"pipeline spec {name} unavailable")


def _member(vs, edge=None, origin=None, ast=None):
    for m in vs.members:
        if (edge is None or m["edge"] == edge) and (origin is None or m["origin"] == origin) and (ast is None or m["ast"] == ast):
            return m
    return None


def _has_left():
    return "left" in tuple(getattr(C, "JOIN_KINDS", ()))


PASS_NULL = ("map", ("rel", "t"), (("id", col("id")), ("y", col("x"))))
COALESCE_NULL = ("map", ("rel", "t"), (("id", col("id")), ("y", ("branch", ("isnull", col("x")), ("const", 0, C.INT), col("x")))))
COUNT_STAR = ("map", ("fold", ("rel", "e"), ("g",), (("n", "count_star", None),)), (("g", col("g")), ("n", col("n"))))
COUNT_COL = ("map", ("fold", ("rel", "e"), ("g",), (("n", "count", col("v")),)), (("g", col("g")), ("n", col("n"))))


def _fake_scored():
    return [dict(id=0, kind="generic", base="vis_a", features={"bias": 1.0, "k_generic": 1.0}, outputs={0: "a", 1: "a"}),
            dict(id=1, kind="null", base="vis_a", features={"bias": 1.0, "k_null": 1.0}, outputs={0: "a", 1: "b"})]


# ------------------------------------------------------------------ relations and facts
class TestRelationsAndFacts(unittest.TestCase):
    def test_make_rel_round_trip(self):
        Rl = R.make_rel(("a", "b"), (C.INT, C.STR), [(1, "x"), (2, None)])
        back = C.run(("rel", "r"), {"r": Rl})
        self.assertEqual(tuple(back.cols), ("a", "b"))
        self.assertEqual(sorted(tuple(r) for r in back.rows), [(1, "x"), (2, None)])

    def test_program_facts_and_shortcut_tags(self):
        join = ("map", ("join", "left", ("rel", "orders"), ("rel", "custs"), ("cust",), ("cid",)),
                (("oid", col("oid")), ("tier", col("tier"))))
        f = P.program_facts(join)
        self.assertIn(("left", ("cust",), ("cid",), ("orders",), ("custs",)), f["joins"])
        self.assertTrue({"cust", "cid", "oid", "tier"} <= f["reads"])
        self.assertEqual(P.task_flags(f)["t_join"], 1.0)
        self.assertEqual(P.task_flags(f)["t_passthrough"], 1.0)
        g = P.program_facts(COUNT_STAR)
        self.assertTrue(g["count_star"])
        self.assertIn("g", g["groups"])
        flt = ("filter", ("rel", "t"), ("cmp", "ge", col("x"), ("const", 5, C.INT)))
        self.assertIn(("x", "ge", 5, C.INT), P.program_facts(flt)["bounds"])
        self.assertIn("passthrough", P.shortcut_tags(PASS_NULL))
        self.assertIn("coalesce", P.shortcut_tags(COALESCE_NULL))
        self.assertIn("count_star", P.shortcut_tags(COUNT_STAR))
        self.assertIn("agg:count", P.shortcut_tags(COUNT_COL))
        self.assertNotIn("count_star", P.shortcut_tags(COUNT_COL))
        self.assertIn("join:left", P.shortcut_tags(join))


# ------------------------------------------------------------------ shadow-edge version space: no permanent lock
class TestVersionSpace(unittest.TestCase):
    def test_lone_passthrough_keeps_coalesce_shadow_and_is_falsified_by_program_aware_null(self):
        rec = _rec("null_default")
        vs = P.VersionSpace(rec["task"], [PASS_NULL], budget=S.Budget(wall=60))
        lead = _member(vs, origin="candidate")
        self.assertIsNotNone(lead)
        self.assertEqual(lead["status"], "alive")
        sh = _member(vs, ast=COALESCE_NULL)
        self.assertIsNotNone(sh)
        self.assertEqual(sh["origin"], "shadow")
        self.assertEqual(sh["edge"], "passthrough->coalesce")
        self.assertEqual(sh["status"], "alive")
        props = P.program_aware_proposals(vs)
        self.assertTrue(any(p["kind"] == "null" for p in props))
        self.assertTrue(any(p["kind"] == "null" and p["detail"].get("col") == "x" for p in props),
                        "the program reads x, so a NULL-in-x proposal must be synthesised from its AST")
        scored = P.score_proposals(vs, props, leader=vs.leader())
        self.assertTrue(any(s["kind"] == "null" and len(s["partition"]) > 1 for s in scored),
                        "a lone candidate must still be challengeable against its shadows")
        self.assertTrue(all(s["features"] and s["features"]["t_single"] == 1.0 for s in scored))
        # a NULL in the column the passthrough reads: the reference answer must separate leader and coalesce shadow
        target = []
        for s in scored:
            if s["kind"] != "null" or s["detail"].get("col") != "x" or len(s["partition"]) < 2:
                continue
            ref_fp = vs.run(rec["ref"], s["env"])
            if s["outputs"].get(lead["id"]) != ref_fp and s["outputs"].get(sh["id"]) == ref_fp:
                target.append(s)
        self.assertTrue(target, "some program-aware NULL-in-x proposal must split passthrough from coalesce")
        ch = target[0]
        E = C.run(rec["ref"], ch["env"])
        rep = vs.observe("q0", ch["env"], E)
        self.assertIn(lead["id"], rep["falsified"])
        self.assertIn("passthrough", rep["falsified_tags"])
        self.assertEqual(lead["status"], "falsified")
        self.assertEqual(sh["status"], "alive")
        self.assertIn(sh["id"], rep["survivors"])
        self.assertTrue(R.grade(sh["ast"], rec))
        self.assertGreaterEqual(vs.work["full_checks"], 1)
        self.assertGreaterEqual(vs.work["probe_evals"], 1)

    def test_lone_count_star_keeps_count_col_shadow(self):
        rec = _rec("count_col")
        vs = P.VersionSpace(rec["task"], [COUNT_STAR], budget=S.Budget(wall=60))
        sh = _member(vs, ast=COUNT_COL)
        self.assertIsNotNone(sh)
        self.assertEqual(sh["edge"], "count_star->count_col")
        self.assertEqual(sh["status"], "alive")
        scored = P.score_proposals(vs, P.program_aware_proposals(vs), leader=vs.leader())
        self.assertTrue(any(len(s["partition"]) > 1 for s in scored))
        self.assertTrue(any(s["kind"] in ("null", "dupkey") for s in scored))

    def test_inner_join_keeps_left_shadow_and_unmatched_key_proposal_splits(self):
        if not _has_left():
            self.skipTest("core11 has no left join")
        rec = _rec("left_lookup")
        inner = ("map", ("join", "inner", ("rel", "orders"), ("rel", "custs"), ("cust",), ("cid",)),
                 (("oid", col("oid")), ("tier", col("tier"))))
        vs = P.VersionSpace(rec["task"], [inner], budget=S.Budget(wall=60))
        if _member(vs, origin="candidate")["status"] != "alive":
            self.skipTest("visible batches already contain unmatched keys for this seed")
        self.assertTrue(any(m["edge"] == "join:inner->left" and m["status"] == "alive" for m in vs.members))
        scored = P.score_proposals(vs, P.program_aware_proposals(vs), leader=vs.leader())
        self.assertTrue(any(s["kind"] == "unmatched" and len(s["partition"]) > 1 for s in scored))

    def test_strict_metering_never_overruns_and_unchecked_is_not_alive(self):
        rec = _rec("null_default")
        b = S.Budget(wall=60, fc_cap=1)
        vs = P.VersionSpace(rec["task"], [PASS_NULL], budget=b)
        self.assertIsNotNone(vs.exhausted)
        self.assertIsNotNone(b.exhausted)
        self.assertLessEqual(b.c["full_checks"], 1)
        self.assertTrue(any(m["status"] == "unchecked" for m in vs.members))
        alive_ids = {m["id"] for m in vs.alive()}
        self.assertFalse(any(m["id"] in alive_ids for m in vs.members if m["status"] == "unchecked"))
        self.assertLessEqual(len(vs.alive()), 1)

    def test_generic_menu_and_choice_rules(self):
        rec = _rec("null_default")
        props = P.generic_proposals(P.base_envs(rec["task"]))
        self.assertTrue(props)
        self.assertTrue(all(p["kind"] == "generic" for p in props))
        self.assertEqual([p["id"] for p in props], list(range(len(props))))
        self.assertEqual(len({P.env_key(p["env"]) for p in props}), len(props))
        vs = P.VersionSpace(rec["task"], [PASS_NULL], budget=S.Budget(wall=60))
        scored = P.score_proposals(vs, props)
        self.assertTrue(scored)
        self.assertIs(P.choose(scored, "fixed"), scored[0])
        a = P.choose(scored, "random", rng=random.Random(7))
        b = P.choose(scored, "random", rng=random.Random(7))
        self.assertIs(a, b)
        self.assertIsNone(P.choose([], "weighted"))
        self.assertEqual(len(P.feature_vector(scored[0]["features"])), len(P.FEATURE_NAMES))


# ------------------------------------------------------------------ selector and counterfactual regret
class TestSelector(unittest.TestCase):
    def test_counterfactual_utilities_and_regret_demotion(self):
        sc = _fake_scored()
        u = L.counterfactual_utilities(sc, ["a", "a"], leader_id=1)
        self.assertEqual(u[0], 0.0)
        self.assertAlmostEqual(u[1], 0.5 + L.LEADER_BONUS)
        self.assertEqual(L.counterfactual_utilities(sc, [None, None]), [0.0, 0.0])
        sel = L.Selector()
        w_gen, w_null = sel.weights["k_generic"], sel.weights["k_null"]
        rec = sel.audit_choice(sc, sc[0], u)
        self.assertGreater(rec["regret"], 0)
        self.assertIn("k_generic", rec["demoted"])
        self.assertLess(sel.weights["k_generic"], w_gen)
        self.assertGreater(sel.weights["k_null"], w_null)
        self.assertIs(sel.choose(sc), sc[1])
        self.assertEqual(sel.audit_choice(sc, sc[1], u)["regret"], 0.0)
        before = dict(sel.weights)
        t = sel.train_step(sc, u)
        self.assertEqual(t["kind"], "train")
        self.assertFalse(t.get("skipped"))
        self.assertGreater(sel.weights["k_null"], before["k_null"])
        self.assertTrue(sel.train_step(sc, [0.3, 0.3])["skipped"])
        self.assertTrue(all(abs(v) <= L.W_CLIP for v in sel.weights.values()))

    def test_shortcut_demotion_orders_but_never_removes(self):
        rec = _rec("null_default")
        sel = L.Selector()
        sel.audit_submission(["passthrough"], True, ["coalesce"])
        self.assertIn("passthrough", sel.demoted_shortcuts())
        self.assertGreater(sel.tag_prior["coalesce"], 0)
        vs = P.VersionSpace(rec["task"], [PASS_NULL], budget=S.Budget(wall=60))
        n_alive = len(vs.alive())
        plain, guided = vs.leader(), vs.leader(sel.leader_prior)
        self.assertEqual(plain["origin"], "candidate")
        self.assertIn("passthrough", plain["tags"])
        self.assertIn("coalesce", guided["tags"])
        self.assertEqual(len(vs.alive()), n_alive)
        self.assertEqual(plain["status"], "alive")
        sel.audit_submission(["coalesce"], False)
        self.assertGreater(sel.tag_prior["coalesce"], 0.25)
        for _ in range(50):
            sel.audit_submission(["passthrough"], True)
        self.assertGreaterEqual(sel.tag_prior["passthrough"], -L.PRIOR_CLIP)

    def test_frozen_selector_and_guide_isolation(self):
        sc = _fake_scored()
        sel = L.Selector()
        sel.audit_choice(sc, 0, [0.0, 1.0])
        fz = sel.copy(name="frozen", frozen=True)
        fp = fz.fingerprint()
        self.assertEqual(fp, sel.fingerprint())
        with self.assertRaises(L.FrozenSelectorError):
            fz.train_step(sc, [0.0, 1.0])
        with self.assertRaises(L.FrozenSelectorError):
            fz.audit_choice(sc, 0, [0.0, 1.0])
        with self.assertRaises(L.FrozenSelectorError):
            fz.audit_submission(["passthrough"], True)
        fz.choose(sc)
        self.assertEqual(fz.fingerprint(), fp)
        self.assertEqual(L.Selector.from_dict(sel.to_dict()).fingerprint(), sel.fingerprint())
        g = L.DeltaStateGuide()
        self.assertEqual(g.table(), {})
        g.observe(COALESCE_NULL, True)
        g.observe(PASS_NULL, False)
        tab = g.table()
        self.assertTrue(all(tab[k] == 1 for k in L.PINNED))
        self.assertTrue(all(1 <= v <= S.MAX_COST for v in tab.values()))
        self.assertIsInstance(g.costs(), S.Costs)
        gfp = g.fingerprint()
        g.freeze()
        with self.assertRaises(L.FrozenSelectorError):
            g.observe(COALESCE_NULL, True)
        self.assertEqual(g.fingerprint(), gfp)
        self.assertEqual(L.DeltaStateGuide.from_dict(g.to_dict()).fingerprint(), gfp)

    def test_pick_arms_and_productions(self):
        sc = _fake_scored()
        self.assertIs(L.pick("fixed", sc), sc[0])
        self.assertIs(L.pick("random", sc, rng=random.Random(3)), L.pick("random", sc, rng=random.Random(3)))
        self.assertIn(L.pick("untrained", sc), sc)
        with self.assertRaises(ValueError):
            L.pick("trained", sc)
        with self.assertRaises(ValueError):
            L.pick("oracle", sc)
        pr = L.productions(COALESCE_NULL)
        self.assertEqual(pr["branch"], 1)
        self.assertEqual(pr["isnull"], 1)
        self.assertEqual(pr["rel"], 1)
        self.assertGreaterEqual(pr["col"], 2)
        self.assertEqual(L.productions(COUNT_COL)["fold:count"], 1)
        self.assertEqual(L.productions(COUNT_STAR, dict(relational=["F1"], scalar=[]))["call:F1"], 1)


# ------------------------------------------------------------------ SQL front end / compile back
class TestSql(unittest.TestCase):
    def test_parse_sql_subset(self):
        self.assertEqual(PL.parse_sql("SELECT g, COUNT(v) AS n FROM e GROUP BY g"), COUNT_COL)
        self.assertEqual(PL.parse_sql("SELECT g, COUNT(*) AS n FROM e GROUP BY g"), COUNT_STAR)
        self.assertEqual(PL.parse_sql("SELECT id, COALESCE(x, 0) AS y FROM t"), COALESCE_NULL)
        flt = PL.parse_sql("SELECT * FROM t WHERE x >= 3 AND x IS NOT NULL")
        self.assertEqual(flt[0], "filter")
        self.assertEqual(flt[2][0], "and")
        for bad in ("SELECT DISTINCT x FROM t", "SELECT x FROM t ORDER BY x", "SELECT x FROM a, b",
                    "WITH c AS (SELECT 1) SELECT * FROM c"):
            with self.assertRaises(PL.SqlUnsupported):
                PL.parse_sql(bad)
        st = PL.split_script("CREATE TABLE a AS SELECT * FROM t; -- c\nCREATE TEMP VIEW b AS SELECT id, x AS y FROM a;")
        self.assertEqual([n for n, _ in st], ["a", "b"])
        with self.assertRaises(PL.SqlParseError):
            PL.split_script("DROP TABLE t;")

    def test_left_join_parse_and_native_sqlite_check(self):
        if not _has_left():
            self.skipTest("core11 has no left join")
        env = R._g_lookup(random.Random(5), "edge")
        ast = PL.parse_sql("SELECT oid, tier FROM orders o LEFT JOIN custs k ON o.cust = k.cid", PL._cols_fn(env))
        self.assertEqual(ast[1][0], "join")
        self.assertEqual(ast[1][1], "left")
        self.assertEqual(ast[1][4], ("cust",))
        self.assertEqual(ast[1][5], ("cid",))
        nenv = {"t": R.make_rel(("id", "x"), (C.INT, C.INT), [(1, 4), (2, None), (3, 9)])}
        chk = PL.native_check(COALESCE_NULL, nenv)
        self.assertEqual(chk["status"], "agree", chk)
        self.assertIn("CASE WHEN", chk["sql"])


# ------------------------------------------------------------------ out-of-sandbox localize-and-lift
class TestPipelineLift(unittest.TestCase):
    def test_localize_preserves_working_stage(self):
        case = R.build_pipeline_case(_spec("P3_null_default"), 990101)
        loc = PL.localize(case["broken"], case["batches"])
        self.assertEqual(loc["broken_name"], "out")
        self.assertEqual(loc["statuses"][0], "verified")
        self.assertEqual(loc["statuses"][1], "broken")
        self.assertLessEqual(loc["work"]["full_checks"], S.FC_CAP)
        self.assertTrue(case["bug_visible"])

    def test_lift_repairs_count_star_to_count_col(self):
        case = R.build_pipeline_case(_spec("P2_count_col"), 990202)
        self.assertTrue(case["bug_visible"])
        res = PL.lift_stage(case["broken"], case["batches"], require_unique=False, native=False, widen=False, wall=20.0)
        self.assertEqual(res["status"], "repaired", (res["status"], res["reason"], res["attempts"]))
        self.assertIn("agg:count", res["leader_tags"])
        self.assertNotIn("count_star", res["leader_tags"])
        self.assertTrue(R._grade_pipeline(res["pipeline"], case))
        self.assertLessEqual(res["work"]["full_checks"], S.FC_CAP)
        self.assertTrue(res["sql"])
        self.assertIn("COUNT(", res["sql"])

    def test_lift_abstains_when_alternatives_unresolved_without_queries(self):
        case = R.build_pipeline_case(_spec("P2_count_col"), 990202)
        res = PL.lift_stage(case["broken"], case["batches"], native=False, widen=False, wall=20.0)
        self.assertIn(res["status"], ("abstained", "repaired"))
        if res["status"] == "abstained":
            self.assertTrue(res["unresolved"])
            self.assertEqual(res["reason"], "unresolved_alternatives")
        else:
            self.assertFalse(res["unresolved"])
        self.assertEqual(res["queries_used"], 0)


# ------------------------------------------------------------------ runner: isolation, verdict, caps
class TestRunner(unittest.TestCase):
    def test_seed_isolation_and_verdict_logic(self):
        src = {R.source_seed(si, fi, i) for si in range(2) for fi in range(8) for i in range(20)}
        ev = {R.eval_seed(fi, i) for fi in range(8) for i in range(20)}
        pipe = {R.pipeline_seed(pi, i) for pi in range(8) for i in range(20)}
        self.assertFalse(src & ev)
        self.assertFalse(src & pipe)
        self.assertFalse(ev & pipe)
        s, e, p = R.planned_seeds(dict(R.DEFAULT), len(R._families()), len(R._pipeline_specs()))
        self.assertFalse(s & e or s & p or e & p)
        with self.assertRaises(ValueError):
            R.eval_seed(0, 100)
        con = {"trained-fixed": [2, 3], "trained-random": [2, 2], "trained-untrained": [4, 2],
               "wrong": {"fixed": [1, 2], "random": [1, 1], "untrained": [2, 1], "trained": [0, 1]}}
        self.assertEqual(R.verdict(con, ("rep0", "rep1")), "positive")
        con["wrong"]["trained"] = [3, 1]
        self.assertEqual(R.verdict(con, ("rep0", "rep1")), "mixed")
        neg = {"trained-fixed": [-2, -3], "trained-random": [0, 1], "trained-untrained": [0, 0],
               "wrong": {a: [0, 0] for a in R.ARMS}}
        self.assertEqual(R.verdict(neg, ("rep0", "rep1")), "negative")
        self.assertEqual(R._over_cap(dict(full_checks=5001), 5000), ["full_checks"])
        self.assertEqual(R._over_cap(dict(full_checks=5000), 5000), [])
        self.assertEqual(R._caps(4000)["full_checks"], 4000)
        self.assertEqual(WORK_CAPS["full_checks"], 5000)
        rows = [dict(stream="rep0", B_q=1, arm="trained", status="verified", n_queries=1, counters=dict(full_checks=10)),
                dict(stream="rep0", B_q=1, arm="trained", status="wrong", n_queries=1, counters=dict(full_checks=20))]
        sm = R.summarize(rows)["rep0|B1|trained"]
        self.assertEqual(sm["verified"], 1)
        self.assertEqual(sm["wrong"], 1)
        self.assertEqual(sm["submitted"], 2)
        self.assertEqual(sm["max_full_checks"], 20)

    def test_run_experiment_tiny_strict_caps_and_isolation(self):
        with self.assertRaises(ValueError):
            R.run_experiment(10, out_dir=None, fc_cap=6000)
        with tempfile.TemporaryDirectory() as tmp:
            res = R.run_experiment(90, out_dir=tmp, quick=True, streams=("rep0",), pipelines=False, eval_instances=1,
                                   source_instances=1, collect_wall=0.5, investigate_wall=1.0)
            ch = res["checks"]
            self.assertEqual(ch["over_cap_rows"], 0)
            self.assertEqual(ch["error_rows"], 0, [r.get("error") for r in res["rows"] if r["status"] == "error"])
            self.assertTrue(ch["isolation_ok"])
            self.assertFalse(res["isolation"]["seed_overlap"])
            iso = res["isolation"]["streams"]["rep0"]
            self.assertTrue(iso["selector_unchanged"] and iso["guide_unchanged"] and iso["selector_frozen"] and iso["guide_frozen"])
            self.assertGreaterEqual(ch["ambiguous_rows"], len(R.ARMS))
            self.assertEqual({r["arm"] for r in res["rows"]}, set(R.ARMS))
            self.assertTrue(all((r.get("counters") or {}).get("full_checks", 0) <= 5000 for r in res["rows"]))
            self.assertEqual(res["learned_by_nexus"]["rep0"]["admitted_library_functions"], [])
            prog = res["progression"]
            for name in ("learning_to_learn_gain", "transfer_efficiency", "self_evolution_delta", "unseen_domain_reuse_rate",
                         "enterprise_reliability_advantage"):
                self.assertIn(name, prog["per_stream"]["rep0"])
                self.assertIn(prog["per_stream"]["rep0"][name]["flag"], ("positive", "non_positive", "undefined"))
            self.assertTrue(os.path.exists(os.path.join(tmp, "results.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "rows.jsonl")))


if __name__ == "__main__":
    unittest.main()
