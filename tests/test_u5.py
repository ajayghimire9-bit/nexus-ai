"""u5 (unified 5-pillar) unit tests: toy budgets and smoke-only seeds; no experiment runs, no sealed data."""
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus import u5_seeds  # noqa: E402,F401
from nexus import u5_construct as K  # noqa: E402
from nexus import u5_world as W  # noqa: E402


def test_tasks_deterministic_and_oracle_counts():
    a, b = W.Task("x", "C.fee", 10000), W.Task("x", "C.fee", 10000)
    assert a.train == b.train and a.y_train == b.y_train and a.queries == 0
    a.oracle(a.test[0])
    assert a.queries == 1
    assert W.ref_size(W.Task("y", "L.net", 10000)) == 21


def test_three_construction_policies_solve_and_exec_scores_partial_programs():
    t = W.Task("n", "C.notional", 10001)
    for pol in ("baseline", "count", "exec"):
        cfg = K.default_config(pol)
        cfg["weights"] = [0.5] * K.N_FEAT
        node, st, s = K.solve(t.train, t.y_train, cfg, budget_s=3.0)
        assert node is not None and W.correct_on(t, node) == 1.0
        assert (st["scored"] > 0) == (pol == "exec")


def test_hybrid_decomposition_solves_large_formula():
    t = W.Task("n", "L.net", 10003)
    node, st, _ = K.solve_hybrid(t.train, t.y_train, K.default_config("baseline"), budget_s=6.0)
    assert node is not None and W.correct_on(t, node) == 1.0


def test_continuation_splitting_invents_exact_class_and_flat_dict_fails():
    from nexus import u5_stateful as SF, u5_statesplit as SP
    t = SF.StreamTask("C.clearing", 10001)
    r = SP.learn_class(t.train, t.y_train, t.query)
    assert r["source"] and r["machine"]["n"] >= 3 and len(r["machine"]["regs"]) >= 1
    assert any(w[0] == "mode" for w in r["witnesses"]) and any(w[0] == "register" for w in r["witnesses"])
    cls = SP.compile_class(r["source"], r["name"])
    assert t.score(lambda evs: SP.run_class(cls, evs))["exact"]
    assert not t.score(SP.FlatDict(t.train, t.y_train, r["fields"]).run)["exact"]
    assert t.n_queries > 0                                       # membership queries are counted
    assert "?unknown" in SP.run_class(cls, [dict(t.train[0], **{r["fields"]["ctrl"]: "NEVER_SEEN"})])[0][0][0]


def test_library_candidates_mdl_and_callable_in_search():
    from nexus import u5_library as LB
    progs = [("b", "*", ("u", "float", ("b", "get", ("var", "r"), ("const", a))), ("u", "float", ("b", "get", ("var", "r"), ("const", b))))
             for a, b in (("q", "p"), ("v", "i"), ("w", "d"))]
    cands = LB.candidates(progs)
    lib = LB.admit_mdl(progs, cands)
    assert lib, "a repeated float(r.get(k)) must compress the corpus"
    before = sum(LB.dl(p) for p in progs)
    after = sum(LB.dl(LB.rewrite(p, *lib[0])) for p in progs) + LB.size(lib[0][2])
    assert after < before
    t = W.Task("n", "I.power", 10002)
    node, st, _ = K.solve(t.train, t.y_train, K.default_config("baseline"), lib, budget_s=3.0)
    assert node is not None and W.correct_on(t, node) == 1.0


def test_curriculum_tasks_checkable_and_forgetting_check_rejects_regression():
    from nexus import u5_curriculum as CU
    src = [W.Task("a", "C.notional", 10000), W.Task("b", "I.power", 10000)]
    exp = CU.Experience()
    rnd = random.Random(1)
    for kind in ("random", "fixed"):
        g = CU.generate(kind, exp, src, rnd, 3)
        assert g is not None and all(abs(K._safe_ev(g.reference, e) - y) < 1e-6 for e, y in zip(g.train, g.y_train))
    good = K.default_config("baseline")
    bad = dict(good, max_level=2)                                # cannot build anything: loses every task
    cfg, lib, lost = CU.accept_no_forgetting(good, [], bad, [], src, {"a", "b"}, 2.0)
    assert cfg is good and lost


def test_meta_improver_respects_budget_and_cannot_touch_evaluator():
    from nexus import evolvable_learner as EL, meta_improver as MI
    L0 = EL.from_config(K.default_config("exec"), per_task_s=0.3)
    assert set(L0) == {"op_cost", "leaf_cost", "P", "adapt", "score", "lib", "lib_cost", "per_task_s"}
    pool = [W.Task(f"t{i}", f, 10000) for i, f in enumerate(("C.notional", "I.power", "I.delta"))]
    L, log, cpu = MI.improve(MI.M0, L0, pool, 2.0, seed=1, score_fn=lambda L, ts: EL.score(L, ts, 0.2))
    assert cpu < 6.0 and set(L) == set(L0)
    m, kind = MI.mutate_M(MI.M0, random.Random(3))
    assert set(m) == set(MI.M0)
    for mod in ("evolvable_learner", "meta_improver"):
        src = (ROOT / f"src/nexus/{mod}.py").read_text()
        assert "checker_kernel" not in src and "ledger_append" not in src


def test_platform_fixed_arm_and_crash_recovery_on_smoke_project():
    from nexus import u5_platform as PL
    p = PL.Project(8090, "dev")
    assert PL.Project(8090, "dev").ticks[3]["A"] == p.ticks[3]["A"]
    r = PL.run_project(p, PL.FixedArm("Fixed"))
    assert r["data_ok"] and r["crash_ok"] and r["human_repairs"] == 0
    conv = PL.run_project(PL.Project(8090, "dev"), PL.FixedArm("Conventional", monitored=False, handle_units=False))
    assert not conv["data_ok"] and conv["silent"]                # D1 ignored, no monitors -> silent error


def test_seed_ranges_and_budget_grant():
    from nexus import seed_registry as R
    assert ("u5", "test") in R.ONE_USE and ("u5", "val") in R.ONE_USE
    assert set(R.REGISTRY[("u5", "test")]).isdisjoint(R.REGISTRY[("u5", "pdev")])
    g = json.loads((ROOT / "artifacts/u5_grant.json").read_text())
    assert g["same_allocation_as"].startswith("GRANT-NEXUS-DE-OOP-36000S") and g["cumulative_s"] == 53990
    assert '"u5-"' in (ROOT / "scripts/u5_budget.py").read_text()


def test_learners_never_read_reference_programs():
    for mod in ("u5_construct", "u5_statesplit", "u5_library", "evolvable_learner", "meta_improver"):
        src = (ROOT / f"src/nexus/{mod}.py").read_text()
        assert not re.search(r"\.reference\b", src), mod
