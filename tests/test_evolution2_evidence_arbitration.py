"""Synthetic arbitration checks only; no development scoring or collection."""
import copy
import json

import numpy as np
import pytest

from nexus.core.strategy_memory_decide_bench import family_context
from nexus.evolution1.catalogue import digest
from nexus.evolution1.toy_loop import ANCHORS, TrainingFeedback, VARIANTS
from nexus.evolution2.observation_memory import (
    FamilyNormalizer, MemoryEntry, ObservationAwareAdaptive, SourceCalibration,
)


def fixture(mode="evidence", *, length=1.0, distance=0.0):
    m = ObservationAwareAdaptive(seed=7, arbitration=mode, quality_error=0.0)
    m.normalizers = {"pendulum": FamilyNormalizer("pendulum",np.zeros(3),np.ones(3),3,10)}
    m.calibration = SourceCalibration(length,1.505,length,1.505,{},"cross_bundle_lobo_p95",True)
    ctx = family_context("pendulum")
    m.observe("pendulum",np.zeros(3),ctx,provenance="current",support_digest="current")
    for i, a in enumerate(ANCHORS):
        m.update(TrainingFeedback(a.fingerprint,0.2+0.1*i,False,digest(["anchor",i])),ctx)
    available = tuple(v for v in VARIANTS if v not in ANCHORS)[:2]
    incumbent = m.inner.choose(available,ctx)
    candidate = next(v for v in available if v != incumbent)
    for source in range(2):
        scores = {incumbent.fingerprint:0.1,candidate.fingerprint:0.9,
                  ANCHORS[0].fingerprint:0.2,ANCHORS[1].fingerprint:0.3}
        for fp, score in scores.items():
            m._store.append(MemoryEntry(fp,score,(distance,0.,0.),"pendulum",3,
                                        f"source{source}",digest(["support",source])))
    return m, ctx, available, incumbent, candidate


def test_credible_paired_evidence_changes_actual_planner():
    m,ctx,available,inc,candidate = fixture()
    assert m.choose(available,ctx) == candidate
    trace = m.last_decision()
    assert trace["override"] and 0 < trace["confidence"] < 1
    assert trace["independent_contexts"] == 2
    assert trace["comparisons"][candidate.fingerprint]["ess"] == 2
    assert trace["comparisons"][candidate.fingerprint]["anchor_error"] < 1e-15


def test_open_gate_negligible_kernel_cannot_force_confidence_one():
    old,ctx,available,inc,_ = fixture("legacy",length=0.01,distance=1.0)
    old.choose(available,ctx)
    assert old.last_decision()["confidence"] == 1
    m,ctx,available,inc,_ = fixture(length=0.01,distance=1.0)
    assert m.choose(available,ctx) == inc
    assert m.last_decision()["confidence"] == 0
    assert all(c["mass"] == 0 for c in m.last_decision()["comparisons"].values())


def test_subnormal_squared_kernels_have_finite_ess():
    m,ctx,available,inc,candidate = fixture(length=1.0,distance=22.0)
    assert m.choose(available,ctx) == inc
    cell = m.last_decision()["comparisons"][candidate.fingerprint]
    assert np.isfinite(cell["ess"]) and cell["ess"] == 2
    assert 0 < cell["mass"] < 1e-200


def test_multiple_arm_rows_and_duplicate_task_aliases_not_independent():
    m,ctx,available,inc,_ = fixture()
    # Alias every source with the same support and observation identity.
    m._store = [MemoryEntry(r.fingerprint,r.score,r.embedding,r.family,r.obs_dim,
                           r.provenance,"one-support") for r in m._store]
    m._store *= 4
    assert m.choose(available,ctx) == inc
    assert m.last_decision()["independent_contexts"] == 1


def test_missing_arm_has_no_positive_prior_or_override():
    m,ctx,available,inc,candidate = fixture()
    m._store = [r for r in m._store if r.fingerprint != inc.fingerprint]
    assert m.choose(available,ctx) == inc
    assert m.last_decision()["comparisons"][candidate.fingerprint]["advantage"] is None


def test_conflicting_task_memories_abstain():
    m,ctx,available,inc,candidate = fixture()
    m._store = [MemoryEntry(r.fingerprint,0.0 if r.fingerprint==candidate.fingerprint else r.score,
                           r.embedding,r.family,r.obs_dim,r.provenance,r.support_digest)
                if r.provenance=="source1" else r for r in m._store]
    assert m.choose(available,ctx) == inc
    assert m.last_decision()["comparisons"][candidate.fingerprint]["agreement"] == 0.5


def test_misleading_exact_neighbor_rejected_by_current_anchors():
    m,ctx,available,inc,_ = fixture()
    m._store = [MemoryEntry(r.fingerprint,0.0 if r.fingerprint in {a.fingerprint for a in ANCHORS} else r.score,
                           r.embedding,r.family,r.obs_dim,r.provenance,r.support_digest) for r in m._store]
    m._receipts = {a.fingerprint: 1.0 for a in ANCHORS}
    assert m.choose(available,ctx) == inc
    assert m.last_decision()["anchors_ready"]


def test_anchor_receipts_are_required_and_reset_between_tasks():
    m,ctx,available,inc,_ = fixture()
    m.observe("pendulum",np.zeros(3),ctx,provenance="next")
    assert not m._receipts
    assert m.choose(available,ctx) == inc
    assert not m.last_decision()["anchors_ready"]


def test_shuffled_coordinates_can_destroy_apparent_similarity():
    m,ctx,available,inc,candidate = fixture()
    m._embedding = np.asarray([4.,0.,0.])
    m._store = [MemoryEntry(r.fingerprint,r.score,(4.,0.,0.),r.family,r.obs_dim,
                           r.provenance,r.support_digest) for r in m._store]
    assert m.choose(available,ctx) == candidate
    m._embedding = m._embedding[[1,0,2]]
    assert m.choose(available,ctx) == inc
    assert m.last_decision()["confidence"] == 0


def test_prediction_and_retrieval_do_not_mutate_policy_or_read_future_scores():
    m,ctx,available,_,candidate = fixture()
    before = copy.deepcopy(m.inner.learned_state()), copy.deepcopy(m._store), dict(m._receipts)
    a = m.choose(available,ctx)
    b = m.choose(available,ctx)
    assert a == b == candidate
    assert before == (m.inner.learned_state(),m._store,m._receipts)
    # Two possible current tasks can have identical observations and anchors
    # but opposite free-arm outcomes. Neither unavailable outcome table is an
    # input to choose(): evidence alone cannot distinguish these worlds.
    worlds = ({a.fingerprint:1.0},{a.fingerprint:0.0})
    assert worlds[0][a.fingerprint] != worlds[1][a.fingerprint]
    assert m.choose(available,ctx) == a


def test_new_store_retains_distinct_contexts_without_arm_count_inflation():
    m,ctx,_,_,_ = fixture()
    m._store = []
    for i in range(2):
        m.observe("pendulum",np.zeros(3),ctx,provenance=f"t{i}",support_digest=f"s{i}")
        m.update(TrainingFeedback(VARIANTS[0].fingerprint,0.7,False,digest(["f",i])),ctx)
    m.observe("pendulum",np.zeros(3),ctx,provenance="next")
    assert len(m.task_evidence()) == 2


def test_conservative_empirical_error_can_veto_apparent_advantage():
    m,ctx,available,inc,_ = fixture()
    m.quality_error = 1.0
    assert m.choose(available,ctx) == inc


def test_input_feedback_is_typed_and_replay_rejected():
    from nexus.evolution1.catalogue import ContractError
    m,ctx,_,_,_ = fixture()
    with pytest.raises(ContractError):
        m.update({"hidden_score":1.0},ctx)
    f = TrainingFeedback(VARIANTS[0].fingerprint,0.8,False,digest("duplicate"))
    m.update(f,ctx)
    with pytest.raises(ContractError):
        m.update(f,ctx)


@pytest.mark.parametrize("kind", ["method","task","phase","proposal","nan","inf","string","bool","trace_nan"])
def test_complete_grid_rejects_missing_and_invalid_cells(kind):
    from nexus.evolution2.evidence_arbitration_bench import ROOT, validate_results
    p = json.loads((ROOT/"artifacts/evolution2_24_evidence_arbitration.json").read_text())
    block = p["rows"]["evidence_arbitration"]
    r = block["development"][0]
    if kind == "method": del p["rows"]["reset_adaptive"]
    elif kind == "task": block["development"].pop()
    elif kind == "phase": del block["collision"]
    elif kind == "proposal": r["variants"].pop()
    elif kind == "trace_nan": r["traces"][2]["confidence"] = float("nan")
    else: r["scores"][0] = {"nan":float("nan"),"inf":float("inf"),"string":"0.1","bool":True}[kind]
    with pytest.raises(ValueError): validate_results(p)


def test_previous_e223_choices_and_scores_reproduced_without_rewriting_artifact():
    from nexus.evolution2.evidence_arbitration_bench import ROOT, sha, validate_results
    p = json.loads((ROOT/"artifacts/evolution2_24_evidence_arbitration.json").read_text())
    old = json.loads((ROOT/"artifacts/evolution2_23_cross_bundle_memory.json").read_text())
    assert validate_results(p)
    for method in ("persistent_adaptive","reset_adaptive","observation_cross_bundle","observation_ungated_memory"):
        for phase in old["rows"][method]:
            for a,b in zip(old["rows"][method][phase],p["rows"][method][phase]):
                assert a["task_id"] == b["task_id"]
                assert a["variants"] == b["variants"]
                assert a["scores"] == b["scores"]
                assert a["first_free_regret"] == b["first_free_regret"]
    for path, h in p["historical_artifacts_sha256"].items():
        assert sha(ROOT/path) == h


def test_free_regret_recomputed_from_all_four_slots_and_accounting():
    from nexus.evolution2.evidence_arbitration_bench import ROOT, METHODS
    p = json.loads((ROOT/"artifacts/evolution2_24_evidence_arbitration.json").read_text())
    for method in METHODS:
        for rows in p["rows"][method].values():
            for row in rows:
                assert len(row["traces"]) == 6
                assert row["cumulative_free_regret"] == pytest.approx(sum(row["oracle"]-s for s in row["scores"][2:]))
                assert row["charged"] == row["physical"] == 6
    assert p["resources"]["logical_lookups_each"] == 60
    assert p["resources"]["actual_proxy_catalogue_evaluations"] == 312


def test_audit_result_is_not_silently_overwritten(tmp_path):
    from nexus.evolution2.evidence_arbitration_bench import write_artifact
    path = tmp_path/"existing.json"
    path.write_text("immutable")
    with pytest.raises(FileExistsError): write_artifact(path)
    assert path.read_text() == "immutable"


def test_failed_benchmark_persists_honest_failure(tmp_path, monkeypatch):
    from nexus.evolution2 import evidence_arbitration_bench as bench
    def failure(): raise RuntimeError("test_failure")
    monkeypatch.setattr(bench,"run_benchmark",failure)
    path = tmp_path/"failed.json"
    with pytest.raises(RuntimeError): bench.write_artifact(path)
    assert json.loads(path.read_text())["declared_complete"] is False


def test_source_calibration_reproduces_without_development_tasks(monkeypatch):
    from nexus.evolution2 import evidence_arbitration_bench as b
    from nexus.evolution2.observation_memory import calibrate_cross_bundle,fit_family_normalizers
    def forbidden(*args,**kwargs): raise AssertionError("development_access")
    monkeypatch.setattr(b,"make_e222_tasks",forbidden)
    norms = fit_family_normalizers()
    actual = b.source_quality_calibration(norms,calibrate_cross_bundle(norms,seed=7),seed=7)
    saved = json.loads((b.ROOT/"artifacts/evolution2_24_evidence_arbitration.json").read_text())["calibration"]
    assert actual == saved


def test_saved_audit_is_arithmetic_only(monkeypatch):
    from nexus.evolution2 import evidence_arbitration_bench as b
    def forbidden(*args,**kwargs): raise AssertionError("unexpected_scoring")
    monkeypatch.setattr(b,"score_table",forbidden)
    p = json.loads((b.ROOT/"artifacts/evolution2_24_evidence_arbitration.json").read_text())
    audit = b.audit_saved_results(p)
    assert audit["arithmetic_grid_valid"] and audit["historical_artifacts_preserved"]
    assert audit["decision_counts"]["evidence_arbitration"]["overrides"] == 0
    assert len(audit["same_zero_observation_ranking_reversals"][0]["reversals"]) == 2
