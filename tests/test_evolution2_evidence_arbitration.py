"""Synthetic arbitration checks only; no development scoring or collection."""
import copy

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
