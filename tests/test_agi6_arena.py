"""Phase 6 unit checks (no learner search, no experiment outcome; one-use agi6de targets / panel are never built here).
Run in its own process (each phase's seed registry asserts its ranges are above all others registered in the process)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase5 import admission5 as A5  # noqa: E402
from nexus.de_phase6 import ir6, lineage6 as L6, seeds6 as S6, trust6 as T6, world6 as W6  # noqa: E402

TMP = ROOT / "var/agi6_ws/test"
DEV = S6.RANGES[("agi6de", "dev")].start + 1800


def test_phase6_ranges_fresh_one_use():
    mine = {k: r for k, r in R.REGISTRY.items() if k[0] == "agi6de"}
    assert set(mine) == set(S6.RANGES)
    assert all(not set(r) & set(m) for k, r in R.REGISTRY.items() if k[0] != "agi6de" for m in mine.values())
    assert S6.ONE_USE == {("agi6de", "target"), ("agi6de", "panel")} and S6.ONE_USE <= R.ONE_USE
    m = S6.target_manifest()
    assert len(m) == 72 and [sum(t["tier"] == k for t in m) for k in (1, 2, 3)] == [24, 32, 16]
    assert all(t["seed"] in S6.RANGES[("agi6de", "target")] for t in m) and len(S6.panel_manifest()) == 18


def test_tier3_never_in_source_or_admission():
    assert not {s["paradigm"] for s in L6.SOURCE_SPECS} & set(W6.TIER3)
    assert {W6.TIER[s["paradigm"]] for s in L6.SOURCE_SPECS} == {1, 2}
    assert not {tuple(map(tuple, W6.HYBRIDS[h])) for h in W6.HYBRIDS} & {tuple(map(tuple, v)) for v in W6.COMPOSITES.values()}


def test_every_language_round_trips():
    spec = dict(dedup=dict(key="k", order=["cast_int", ["col", "v"]]),
                filter=["and", ["le", ["cast_int", ["col", "fts"]], ["cast_int", ["col", "lts"]]], ["ne", ["col", "op"], ["lit", "D"]]],
                quarantine=["not", ["and", ["valid_int", ["col", "amt"]], ["nonempty", ["col", "region"]]]],
                outputs=[["id", ["col", "id"]], ["x", ["round2", ["div_real", ["try_int", ["col", "amt"]], ["nullif_zero", ["cast_int", ["col", "q"]]]]]]])
    for lang in ("sql", "hive", "postgres", "snowflake", "py", "j2", "scala"):
        assert ir6.lift(ir6.lower(spec, lang), lang) == spec, lang


def _claims(effects, statuses, files=("docs/runbook.json", "docs/ticket.json")):
    return [dict(effect_at_boundary=e, status=s, version=v, updated=d, provenance=dict(file=f))
            for e, s, f, v, d in zip(effects, statuses, files, (3, 7), ("2026-02-01", "2026-09-30"))]


def test_calibrated_trust_never_resolves_draft_against_draft_and_ignores_surface_cues():
    tm = T6.empty()
    for i in range(6):                                                  # approved claims were verified right
        T6.record(tm, f"p{i}", _claims(("kept", "excluded"), ("approved", "draft")), "kept", "verified submission")
    pick, _ = T6.decide(tm, _claims(("excluded", "kept"), ("approved", "draft")))
    assert pick is not None and pick["effect_at_boundary"] == "excluded"
    pick, why = T6.decide(tm, _claims(("kept", "excluded"), ("draft", "draft")))
    assert pick is None and "equally authoritative" in why
    mut = lambda c: dict(c, version=99, updated="2030-01-01", provenance=dict(file="docs/zz_renamed.json") if c["provenance"]["file"] != "contract.json" else c["provenance"])  # noqa: E731
    assert T6.invariance(tm, _claims(("excluded", "kept"), ("approved", "draft")), mut)


def test_undetermined_answers_are_negative_evidence():
    tm = T6.empty()
    for i in range(3):
        T6.record(tm, f"u{i}", _claims(("kept", "excluded"), ("approved", "draft")), None, "stakeholder undetermined")
    assert tm["weights"]["status:approved"] < 0
    assert T6.decide(tm, _claims(("kept", "excluded"), ("approved", "draft")))[0] is None


def test_stakeholder_answers_one_row_only():
    p = W6.make_project6(dict(paradigm="P7", engine="sqlite", dp_mode="undecided"), DEV, TMP)
    header, rows = W6.W.read_csv(Path(p["ws"]) / "data" / "visible.csv")
    assert W6.stakeholder_answer(p, rows[:2])["answer"] == "refused"
    a = W6.stakeholder_answer(p, rows[:1])
    assert set(a) <= {"answer", "reason", "output"}


def test_corrected_admission_rejects_equal_zero_and_lost_projects():
    z = {f"p{i}": dict(correct=False, completed=False, wrong=False, cost=dict(wall_s=w, questions=0)) for i, w in enumerate((5.0, 5.0))}
    t = {k: dict(v, cost=dict(wall_s=0.1, questions=0)) for k, v in z.items()}
    assert not A5.admit(z, t)[0]


def test_budget_phase6_and_grant():
    import agi6_budget as B
    assert json.loads((ROOT / "artifacts/agi6_grant.json").read_text())["amount_s"] == 4000
    assert B.alloc()["total_cap_s"] == 3600 and sum(B.alloc()["ceilings"].values()) == 3600
    assert B.stage_of("a6-eval-targets-c0") == "eval"
