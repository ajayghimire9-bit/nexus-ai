"""Phase 4 unit checks (no learner searches and no experiment outcomes; one-use agi4de/eval and agi4de/panel projects are
never built here)."""
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase4 import seeds as SD, world as W, adapter as AD, ir, accept as AC, learner as L, lineage as LG, ops as O  # noqa: E402

TMP = ROOT / "var/agi4_ws/test"
DEV = SD.RANGES[("agi4de", "dev")].start + 450                  # a dev block never used by Stage 1 runs (53600-53999)


def test_phase4_seeds_fresh_disjoint_one_use():
    mine = {k: r for k, r in R.REGISTRY.items() if k[0] == "agi4de"}
    assert len(mine) == 6
    assert min(r.start for r in mine.values()) >= max(r.stop for k, r in R.REGISTRY.items() if k[0] != "agi4de")
    assert SD.ONE_USE == {("agi4de", "eval"), ("agi4de", "panel")} and SD.ONE_USE <= R.ONE_USE
    assert not (set(mine) - SD.ONE_USE) & R.ONE_USE
    assert all(t["seed"] in SD.RANGES[("agi4de", "eval")] for t in SD.eval_manifest())
    assert all(t["seed"] in SD.RANGES[("agi4de", "panel")] for t in SD.panel_manifest())


def test_untouched_families_only_in_stage4_targets():
    assert not {c[0] for c in SD.CELLS} & set(W.UNTOUCHED_FAMS)
    m = SD.eval_manifest()
    assert len(m) == 24 and {t["family"] for t in m} == set(SD.EVAL_FAMS) and len(SD.EVAL_FAMS) == 6
    assert sum(t["runtime"] == "spark" for t in m) == 12 and sum(t["panel"] == "de_untouched" for t in m) == 8
    assert not {t["family"] for t in SD.panel_manifest()} & set(W.UNTOUCHED_FAMS)
    with pytest.raises(ValueError):
        W._make("F7", 1, DEV, "sqlite", TMP, 0, W.SOURCE_FAMS)
    for s in range(DEV, DEV + 12):                              # secondary faults of source projects are never untouched
        p = W.make_project(W.SOURCE_FAMS[s % 6], 3, s, "sqlite", TMP)
        assert not set(p["faults"] + p["oks"]) & set(W.UNTOUCHED_FAMS)


def test_real_files_lift_to_the_generator_legacy_and_round_trip():
    for i, (fam, k, rt) in enumerate([(f, k, rt) for f in W.SOURCE_FAMS for k in (1, 3) for rt in ("sqlite", "spark")]):
        p = W.make_project(fam, k, DEV + 20 + i, rt, TMP)
        text, lang, spec = AD.read_pipeline(p["ws"])
        _, legacy = W.build(p["shape"], p["faults"], p["oks"], p["names"], p["params"])
        assert spec == legacy, p["pid"]
        assert AD.lift_sql(ir.lower_sql(spec)) == spec and AD.lift_py(ir.lower_py(spec)) == spec
        assert lang == ("sql" if rt == "sqlite" else "py")


def test_unsupported_sql_is_refused_not_guessed():
    with pytest.raises(AD.Unsupported):
        AD.lift_sql("CREATE TABLE clean AS SELECT a FROM raw JOIN other USING (k);")


def test_truth_runs_on_sqlite_as_the_reference_and_legacy_fails():
    for i, fam in enumerate(W.SOURCE_FAMS):
        p = W.make_project(fam, 2, DEV + 60 + i, "sqlite", TMP)
        truth, legacy = W.build(p["shape"], p["faults"], p["oks"], p["names"], p["params"])
        assert W.evaluate(p, ir.lower_sql(truth))["ok"]
        assert not W.evaluate(p, ir.lower_sql(legacy))["ok"]


def test_heldback_folds_partition_the_golden_rows():
    rows = [[f"k{i}", i] for i in range(9)]
    fs = AC.folds(rows, ["r1", "r2", "r3", "r4"], "x")
    assert len(fs) == 5
    held = [tuple(map(tuple, f[1])) for f in fs]
    assert sorted(r for h in held for r in h) == sorted(map(tuple, rows))
    assert all(sorted(map(tuple, f[0] + f[1])) == sorted(map(tuple, rows)) for f in fs)
    assert AC.folds(rows[:3], None, "x") == [(rows[:3], [], [], [])]


def test_relabelling_invariant_rejects_a_measure_used_as_a_dedup_key():
    p = next(q for q in (W.make_project("F4", 1, DEV + 70 + j, "sqlite", TMP) for j in range(10)) if q["shape"] in ("agg", "row"))
    inv = L.Investigation(p, W.SQLiteCode())
    truth, _ = W.build(p["shape"], p["faults"], p["oks"], p["names"], p["params"])
    assert AC.invariants(inv, truth) == []
    bad = dict(truth, dedup=dict(key=p["names"]["offset"]))                 # positional key instead of the event id
    assert "relabelling" in AC.invariants(inv, bad)


def test_solved_only_learns_nothing_from_failures():
    rec = dict(outcome="submitted", edits=[("round2", "x")], edit_pre=[["fail:x"]], refutations=[dict(op="try_parse", pre=["fail:y"])],
               partials=[dict(op="round2", prm="x", stage=3, pre=["fail:x"], fixes=["fail:x"], gain=1, verified=True)],
               choices=[dict(chosen="filter_file:gt:sub", rejected=["filter_file:ge:sub"])])
    so, full = L.empty_de(), L.empty_de()
    L.learn(so, rec, dict(pid="p"), dict(lr=1.0, neg_lr=0.5, partial_lr=0.5, use_failures=False), False)
    assert so == L.empty_de()
    L.learn(full, rec, dict(pid="p"), dict(lr=1.0, neg_lr=0.5, partial_lr=0.5, use_failures=True), False)
    assert full["prefs"] == {"filter_file:gt:sub": -1.0, "filter_file:ge:sub": 0.5}
    assert full["w"]["fail:y"]["try_parse"] == -0.5 and {r["kind"] for r in full["P"]} == {"refuted_submission", "partial"}


def test_placebo_is_matched():
    import agi4_eval as E
    de = L.empty_de()
    de["skills"]["S0"] = dict(ops=["dedup_latest", "try_parse"], pre=["fail:unique", "fail:row_count"], kind="full")
    de["w"] = {"fail:unique": {"dedup_latest": 2.0}}
    de["prefs"] = {"filter_file:ge:sub": 1.5}
    pl = E.placebo(dict(DE=de, M=LG.M0), random.Random(1))["DE"]
    assert len(pl["skills"]["S0"]["ops"]) == 2 and len(pl["skills"]["S0"]["pre"]) == 2
    assert sorted(v for f in pl["w"] for v in pl["w"][f].values()) == [2.0] and sorted(pl["prefs"].values()) == [1.5]


def test_budget_phase4():
    import agi4_budget as B
    assert B.TOTAL == 1800.0 and sum(B.ceilings().values()) == 1800
    assert B.stage_of("mi-agi4-eval-de-c0") == "eval" and B.stage_of("mi-agi4-src-Full-r0") == "src"


def test_improver_space_has_at_least_ten_distinct_priority_first_edits():
    e = LG.edits_of(LG.M0, random.Random(0), set())
    assert len(set(e)) >= 10 and [x[:2] for x in e[:4]] == LG.PRIORITY
    M = LG.m_random(random.Random(3))
    assert [n for n, _ in M] == [n for n, _ in LG.M0]
