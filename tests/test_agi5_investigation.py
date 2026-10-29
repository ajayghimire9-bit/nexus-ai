"""Phase 5 unit checks (no learner search and no experiment outcome; one-use agi5de/target projects are never built here).
Run in its own process (each phase's seed registry asserts its ranges are above all others registered in the process)."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from nexus import seed_registry as R  # noqa: E402
from nexus.de_phase5 import admission5 as A5, investigate as IV, policy_learn as PL, seeds5 as S5, world5 as W5  # noqa: E402

TMP = ROOT / "var/agi5_ws/test"
DEV = S5.RANGES[("agi5de", "dev")].start + 700


def test_phase5_ranges_fresh_and_target_one_use():
    mine = {k: r for k, r in R.REGISTRY.items() if k[0] == "agi5de"}
    assert set(mine) == set(S5.RANGES)
    others = [r for k, r in R.REGISTRY.items() if k[0] != "agi5de"]
    assert all(not set(r) & set(m) for r in others for m in mine.values())
    assert S5.ONE_USE == {("agi5de", "target")} and S5.ONE_USE <= R.ONE_USE
    m = S5.target_manifest()
    assert len(m) == 72 and all(t["seed"] in S5.RANGES[("agi5de", "target")] for t in m)


def test_source_never_contains_held_out_structure():
    for sp in S5.source_specs(60):
        assert len(sp["dps"]) == 1 and sp["runtime"] == "sqlite" and sp.get("names", "base") == "base"
    kinds = {t["kind"] for t in S5.target_manifest()}
    assert {"two_dp_heldout_combo", "single_heldout_schema", "spark_engine"} <= kinds


def test_workspace_exposes_no_hidden_material_and_claims_have_provenance():
    p = W5.make_project5(dict(dps={"watermark": "conflict_approved"}, runtime="sqlite"), DEV, TMP)
    ws = Path(p["ws"])
    names = {q.name for q in ws.rglob("*") if q.is_file()}
    assert not names & {"stakeholder.json", "hidden1.csv", "hidden2.csv"} and "truth" not in (ws / "contract.json").read_text()
    claims = [c for s in W5.SOURCES for c in IV.read_claims(p["ws"], s)]
    assert len(claims) == 2 and {c["effect_at_boundary"] for c in claims} == {"kept", "excluded"}
    assert all(c["provenance"]["file"] in W5.SOURCES and c["provenance"]["claim_id"] for c in claims)


def test_business_decision_reverses_across_projects():
    seen = {W5.make_project5(dict(dps={"checkpoint": "explicit"}, runtime="sqlite"), DEV + 10 + i, TMP)["inclusive"]["checkpoint"]
            for i in range(10)}
    assert seen == {True, False}


def test_stakeholder_limits():
    p = W5.make_project5(dict(dps={"watermark": "undecided"}, runtime="sqlite"), DEV + 30, TMP)
    header, rows = W5.W.read_csv(Path(p["ws"]) / "data" / "visible.csv")
    assert W5.stakeholder_answer(p, rows[:2])["answer"] == "refused"
    assert W5.stakeholder_answer(p, [])["answer"] == "refused"
    st = W5.W.state_of(p["ws"])
    t = W5._threshold("watermark", st)
    probe = dict(rows[0], **{p["names"]["ts"]: str(t)})
    a = W5.stakeholder_answer(p, [probe])
    assert a["answer"] in ("undetermined", "output") and set(a) <= {"answer", "reason", "output"}


def _synthetic(modes):
    """A cache entry with one decision point per mode (no engine): options gt / ge, boundary effects, probe, answers."""
    dps, reads, combos = [], {s: [] for s in W5.SOURCES}, {}
    n = 0
    for pos, (dp, mode) in enumerate(modes):
        ref = W5.REF[dp]
        opts = [f"c{pos} gt {json.dumps(ref)}", f"c{pos} ge {json.dumps(ref)}"]
        dps.append(dict(pos=pos, op="filter_file", options=opts, ref=ref, col=f"c{pos}", resolved=None, via=None, conflict=False,
                        undecided=False, claims=[], specs=[{}, {}], boundary_effect=["excluded", "kept"], probe={"id": "q"},
                        option_keys=["A", "B"]))
        if mode == "conflict_approved":
            for src, eff, status in (("contract.json", "kept", "approved"), ("docs/ticket.json", "excluded", "draft")):
                n += 1
                reads[src].append(dict(id=f"R{n}", subject=dict(state_ref=ref), effect_at_boundary=eff, status=status, version=1,
                                       updated="2026-01-01", provenance=dict(file=src, claim_id=f"R{n}")))
    entry = dict(pid="synthetic", reads=reads, search=dict(outcome="abstain_ambiguous", has_candidate=True, path=[], dps=dps,
                                                         cost=dict(sqlite_runs=1, spark_runs=0, wall_s=0.1)),
                 answers={str(i): dict(answer="output", key="B", option_keys=["A", "B"]) for i in range(len(dps))})
    for a in ("c0 gt", "c0 ge"):
        for b in ("c1 gt", "c1 ge"):
            combos[json.dumps([f"{a} {json.dumps(dps[0]['ref'])}", f"{b} {json.dumps(dps[1]['ref'])}"])] = \
                dict(verified=a.endswith("ge") and b.endswith("ge"), wrong=not (a.endswith("ge") and b.endswith("ge")))
    entry["combos"], entry["any_verifiable"] = combos, True
    return entry


def test_one_question_and_learned_trust_compose_on_two_decision_points():
    e = _synthetic([("watermark", "conflict_approved"), ("checkpoint", "missing")])
    proj = dict(pid="synthetic", ws=str(TMP))
    mem = dict(_digest="x")
    st = IV.investigate(proj, PL.Cached({"synthetic": e}), IV.empty_evidence(), mem, IV.F0)
    assert st.cost["questions"] == 1 and st.decision["kind"] == "abstain"        # no trust memory: one question is not enough
    em = IV.empty_evidence()
    em["trust"] = {"status:approved": 1.0, "status:draft": -1.0}
    st = IV.investigate(proj, PL.Cached({"synthetic": e}), em, mem, IV.F0)
    assert st.cost["questions"] == 1 and st.decision["kind"] == "submit"
    assert PL.replay_row(proj, e, st)["completed"] and [d["via"] for d in st.dps] == ["trust:learned", "clarification"]
    assert any(t["action"] == "ask" for t in st.trace) and st.executed                       # execution coverage is recorded


def test_second_question_is_never_asked():
    e = _synthetic([("watermark", "missing"), ("checkpoint", "missing")])
    prog = [["search"], ["ask", "first"], ["ask", "first"], ["submit_or_abstain"]]
    st = IV.investigate(dict(pid="synthetic", ws=str(TMP)), PL.Cached({"synthetic": e}), IV.empty_evidence(), dict(_digest="x"), prog)
    assert st.cost["questions"] == 1 and st.decision["kind"] == "abstain"


def _rows(spec):
    return {f"p{i}": dict(correct=c, completed=c, wrong=w, cost=dict(wall_s=x, questions=0)) for i, (c, w, x) in enumerate(spec)}


def test_admission_closes_the_equal_zero_loophole_and_needs_the_same_completed_set():
    zero_b, zero_t = _rows([(False, False, 5.0)] * 3), _rows([(False, False, 1.0)] * 3)
    ok, why = A5.admit(zero_b, zero_t)
    assert not ok and "no common" in why["reason"]
    b = _rows([(True, False, 4.0), (True, False, 4.0), (False, False, 1.0)])
    t = _rows([(True, False, 1.0), (False, False, 0.1), (True, False, 1.0)])          # cheaper, same count, but loses p1
    ok, why = A5.admit(b, t)
    assert not ok and why["lost"] == ["p1"]
    t2 = _rows([(True, False, 1.0), (True, False, 1.0), (False, False, 1.0)])
    assert A5.admit(b, t2)[0]
    assert not A5.admit(b, _rows([(True, True, 0.1), (True, False, 0.1), (True, False, 0.1)]))[0]   # more wrong never wins


def test_budget_phase5():
    import agi5_budget as B
    assert B.TOTAL == 600.0 and sum(B.ceilings().values()) == 600
    assert B.stage_of("mi-agi5-eval-sqlite") == "eval"
