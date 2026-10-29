"""Phase 3 unit checks (no experiment outcomes; untouched C7 / C8 / E7 / E8 and DE holdouts G5 / G6 are only built)."""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nexus import seed_registry as R  # noqa: E402
from nexus.campaign3 import seeds as SD, de_world as W, de_learner as DL, agent_loop as AL  # noqa: E402
from nexus.campaign3.worlds3 import UNTOUCHED3  # noqa: E402

TMP = ROOT / "var/agi3_ws/test"


def test_phase3_seeds_fresh_disjoint_one_use():
    mine = {k: r for k, r in R.REGISTRY.items() if k[0] in ("agi3", "agi3de")}
    assert len(mine) == 12
    assert min(r.start for r in mine.values()) >= max(r.stop for k, r in R.REGISTRY.items() if k[0] not in ("agi3", "agi3de"))
    assert SD.ONE_USE <= R.ONE_USE and not (set(mine) - SD.ONE_USE) & R.ONE_USE


def test_untouched3_only_in_their_panel():
    p = SD.panels()
    assert {(w, f) for w, f, *_ in p["untouched3"]} == set(UNTOUCHED3)
    for k, v in p.items():
        if k != "untouched3":
            assert not {(w, f) for w, f, *_ in v} & set(UNTOUCHED3)
    assert not set(UNTOUCHED3) & set(SD.LEARN + SD.ADMIT + SD.WITHHELD)


def test_de_source_never_holdout():
    cells = AL.Curriculum3(random.Random(0)).cells
    assert {c[1] for c in cells if c[0] == "DE"} == set(SD.DE_SOURCE)
    assert not set(SD.DE_SOURCE) & set(SD.DE_HOLDOUT)


def test_legacy_fails_and_known_repair_verifies_sqlite():
    p = W.make_project("G3", 1, 51490, "sqlite", TMP)
    rt = W.SQLiteRuntime()
    legacy = json.loads((Path(p["ws"]) / "pipeline.json").read_text())
    assert not W.evaluate(p, legacy, rt)["ok"]
    nm = p["params"]["names"]
    fixed = dict(legacy, dedup=dict(key=nm["key"], order=["cast_int", ["col", nm["ver"]]]))
    assert W.evaluate(p, fixed, rt)["ok"]


def test_render_dialects_differ_where_semantics_differ():
    e = ["try_int", ["col", "qty"]]
    assert "GLOB" in W.render_expr(e, "sqlite") and "try_cast" in W.render_expr(e, "spark")
    assert W.render_expr(["div", ["col", "a"], ["col", "b"]], "spark") == "(`a` / `b`)"


def test_solved_only_learns_no_refutations():
    de = DL.empty_de()
    rec = dict(edits=[("dedup_latest", "k by v")], edit_pre=[["fail:unique"]], refutations=[dict(op="try_parse", pre=["fail:unique"])],
               partials=[dict(op="round2", prm="x", pre=["fail:x"], gain=1)])
    DL.learn(de, rec, dict(pid="p"), dict(lr=1.0, neg_lr=0.5, use_failures=False), True)
    assert de["w"] == {"fail:unique": {"dedup_latest": 1.0}} and de["P"] == []
    DL.learn(de, rec, dict(pid="p"), dict(lr=1.0, neg_lr=0.5, use_failures=True), False)
    assert de["w"]["fail:unique"]["try_parse"] == -0.5 and len(de["P"]) == 1


def test_graded_penalises_missing_and_constant_outputs():
    contract = dict(public_checks=[dict(kind="example_rows", cols=["id", "v"], rows=[["a", 1], ["b", 2]])])
    assert DL.graded(dict(output=[]), contract) == 0.0
    const = DL.graded(dict(output=[{"id": "a", "v": 0}, {"id": "b", "v": 0}]), contract)
    exact = DL.graded(dict(output=[{"id": "a", "v": 1}, {"id": "b", "v": 2}]), contract)
    assert const < exact and exact == 0.95


def test_de_placebo_is_matched():
    import agi3_eval as E
    de = DL.empty_de()
    de["skills"]["S0"] = dict(ops=["dedup_latest", "try_parse"], pre=["fail:unique", "fail:row_count"])
    de["w"] = {"fail:unique": {"dedup_latest": 2.0}}
    pl = E.de_placebo(de, random.Random(1))
    assert len(pl["skills"]["S0"]["ops"]) == 2 and len(pl["skills"]["S0"]["pre"]) == 2
    assert sorted(v for f in pl["w"] for v in pl["w"][f].values()) == [2.0]


def test_budget_phase3():
    import agi3_budget as B
    assert B.TOTAL == 3200.0 and sum(B.ceilings().values()) == 3200
    assert B.stage_of("mi-agi3-eval-de-spark") == "eval"
