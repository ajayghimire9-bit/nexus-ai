"""Synthetic feedback-boundary tests; no world/model construction."""
import copy
from dataclasses import FrozenInstanceError

import pytest

from nexus.evolution1.catalogue import digest
from nexus.evolution1.toy_loop import ANCHORS,AdaptiveProposer,TrainingFeedback,VARIANTS
from nexus.core.strategy_memory_decide_bench import family_context
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import (
    FrozenTrainingFeedbackScale,TrustedEvaluator,feedback_reference_digest,
)

REFERENCE=tuple(ANCHORS)


def source_evaluator(values=(-10.,10.)):
    raw={REFERENCE[0]:values[0],REFERENCE[1]:values[1]}
    evaluator=TrustedEvaluator(VARIANTS,family="pendulum",bundle_id=0,produce_score=lambda v:raw.get(v,999.))
    for v in REFERENCE:evaluator.evaluate("persist",v)
    expected=feedback_reference_digest("pendulum",0,REFERENCE)
    return evaluator,expected


def freeze(evaluator,expected):
    return evaluator.freeze_feedback_scale("persist",reference=REFERENCE,expected_reference_digest=expected)


def test_query_extremes_do_not_change_feedback_weights_or_decision():
    evaluator,expected=source_evaluator();snapshot=freeze(evaluator,expected)
    outputs=[]
    for extreme in (-1e8,1e8):
        raw={REFERENCE[0]:2.,REFERENCE[1]:8.,VARIANTS[0]:extreme}
        query=TrustedEvaluator(VARIANTS,family="pendulum",bundle_id=1,produce_score=lambda v:raw[v])
        policy=AdaptiveProposer(seed=7);context=family_context("pendulum")
        for i,v in enumerate(REFERENCE):
            score=snapshot.unit(query.evaluate("persist",v))
            policy.update(TrainingFeedback(v.fingerprint,score,False,digest(["q",i])),context)
        available=tuple(v for v in VARIANTS if v not in REFERENCE)
        outputs.append((policy.learned_state(),policy.choose(available,context).fingerprint))
        assert query.physical==2 # unobserved extreme never requested
    assert outputs[0]==outputs[1]
    assert outputs[0][0]["updates"]==2
    assert any(abs(w)>0 for w in outputs[0][0]["weights"])


def test_missing_reference_extra_reference_and_foreign_method_are_rejected():
    evaluator,expected=source_evaluator()
    with pytest.raises(ValueError):
        evaluator.freeze_feedback_scale("random",reference=REFERENCE,expected_reference_digest=expected)
    evaluator.evaluate("persist",VARIANTS[0])
    with pytest.raises(ValueError,match="exact_exposed"):
        freeze(evaluator,expected)
    e=TrustedEvaluator(VARIANTS,family="pendulum",bundle_id=0,produce_score=lambda v:1.)
    e.evaluate("persist",REFERENCE[0])
    with pytest.raises(ValueError):freeze(e,expected)


def test_reference_scope_and_hidden_outcomes_rejected():
    evaluator,expected=source_evaluator()
    wrong=feedback_reference_digest("pendulum",1,REFERENCE)
    with pytest.raises(ValueError,match="digest_mismatch"):freeze(evaluator,wrong)
    evaluator.hide_development(REFERENCE[0],999.)
    with pytest.raises(ValueError,match="hidden_training_reference"):freeze(evaluator,expected)


def test_other_method_receipts_cannot_expand_snapshot():
    evaluator,expected=source_evaluator()
    evaluator.evaluate("random",VARIANTS[0])
    snapshot=freeze(evaluator,expected)
    assert snapshot.unit(0.)==0.5
    assert len(snapshot.reference_scores)==2


def test_future_cache_growth_does_not_change_snapshot_and_refit_is_blocked():
    evaluator,expected=source_evaluator();snapshot=freeze(evaluator,expected)
    before=snapshot.payload(),snapshot.snapshot_digest,snapshot.unit(2.)
    evaluator.evaluate("persist",VARIANTS[0])
    assert before==(snapshot.payload(),snapshot.snapshot_digest,snapshot.unit(2.))
    with pytest.raises(RuntimeError,match="already_frozen"):freeze(evaluator,expected)
    with pytest.raises(FrozenInstanceError):snapshot.bundle_id=5


def test_constant_reference_range_fails_closed():
    evaluator,expected=source_evaluator((2.,2.))
    with pytest.raises(ValueError,match="degenerate"):freeze(evaluator,expected)


@pytest.mark.parametrize("value",[True,"1.0",None,float("nan"),float("inf"),-float("inf")])
def test_invalid_raw_feedback_rejected(value):
    evaluator,expected=source_evaluator();snapshot=freeze(evaluator,expected)
    with pytest.raises(ValueError):snapshot.unit(value)


@pytest.mark.parametrize("values",[(float("nan"),1.),(-1e308,1e308),(float("inf"),1.)])
def test_nonfinite_or_overflowing_reference_rejected(values):
    evaluator,expected=source_evaluator(values)
    with pytest.raises(ValueError):freeze(evaluator,expected)


def test_clipping_is_explicit_and_bounds_do_not_move():
    evaluator,expected=source_evaluator();snapshot=freeze(evaluator,expected)
    assert snapshot.transform(-20.)["unit"]==0.
    assert snapshot.transform(20.)["unit"]==1.
    assert snapshot.transform(20.)["clipped"]
    assert not snapshot.transform(10.)["clipped"]
    assert snapshot.unit(0.)==0.5


def test_roundtrip_and_tamper_rejection():
    evaluator,expected=source_evaluator();snapshot=freeze(evaluator,expected)
    import json
    restored=FrozenTrainingFeedbackScale.from_payload(json.loads(json.dumps(snapshot.payload())),
                                                      expected_snapshot_digest=snapshot.snapshot_digest)
    assert restored==snapshot and restored.unit(3.)==snapshot.unit(3.)
    tampered=copy.deepcopy(snapshot.payload());tampered["reference_scores"][0][1]=-30.
    with pytest.raises(ValueError,match="integrity_failure"):
        FrozenTrainingFeedbackScale.from_payload(tampered,expected_snapshot_digest=snapshot.snapshot_digest)


def test_freeze_never_calls_score_producer():
    evaluator,expected=source_evaluator()
    def forbidden(v):raise AssertionError("unplanned_evaluation")
    evaluator._produce=forbidden
    freeze(evaluator,expected)
    assert evaluator.physical==evaluator.charged==2


def test_historical_evaluator_still_returns_unmodified_raw_values():
    evaluator,_=source_evaluator()
    assert evaluator.training_feedback("persist")[REFERENCE[0]]==-10.
    assert evaluator.evaluate("persist",REFERENCE[1])==10.


def test_comparison_methods_share_identical_training_snapshot():
    evaluator,expected=source_evaluator()
    a=freeze(evaluator,expected)
    for v in REFERENCE:evaluator.evaluate("random",v)
    b=evaluator.freeze_feedback_scale("random",reference=REFERENCE,expected_reference_digest=expected)
    assert a==b and a.snapshot_digest==b.snapshot_digest
    assert evaluator.physical==2 and evaluator.cached==2


def test_duplicate_reference_plan_is_rejected():
    with pytest.raises(ValueError):feedback_reference_digest("pendulum",0,(REFERENCE[0],REFERENCE[0]))


def test_saved_capture_invariants_and_accounting():
    import json,hashlib
    from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import ROOT
    path=ROOT/"artifacts/evolution2_26_feedback_boundary.json"
    p=json.loads(path.read_text())
    v=json.loads((ROOT/"artifacts/evolution2_26_feedback_boundary_validation.json").read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==v["capture_sha256"]
    assert sum(c["policy_state"]["updates"] for c in p["cases"])==v["proposer_feedback_updates"]==4
    assert p["cases"][0]["public_feedback"]==p["cases"][1]["public_feedback"]==[0.6,0.9]
    assert p["same_feedback_weights_choice"] and p["refit_blocked"]
    assert p["resources"]["synthetic_raw_lookups"]==7


def test_saved_execution_sources_and_history_verify():
    import json,hashlib,subprocess
    from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import ROOT,file_sha256
    p=json.loads((ROOT/"artifacts/evolution2_26_feedback_boundary.json").read_text())
    assert all(file_sha256(ROOT/path)==h for path,h in p["historical_artifacts_sha256"].items())
    for path,h in p["source_sha256"].items():
        raw=subprocess.check_output(["git","show",p["execution_sha"]+":"+path],cwd=ROOT)
        assert hashlib.sha256(raw).hexdigest()==h
