"""E2.25 deterministic synthetic checks: no collection or neural fitting."""
import copy

import numpy as np
import pytest

from nexus.core.strategy_memory import SupportBatch
from nexus.core.strategy_memory_decide_bench import family_context
from nexus.evolution1.catalogue import digest,plan_bound
from nexus.evolution1.toy_loop import ANCHORS,VARIANTS
from nexus.evolution2.observation_memory import FamilyNormalizer
from nexus.evolution2.planner_adapter import generate_candidates
from nexus.evolution2.planner_quality_diagnostic import (
    OFFSETS,PublicQualityContext,candidate_descriptor,evaluate_fold,fit_ridge,
    predict_ridge,quality_features,validate,validate_source_separation,write_artifact,
)


def context(family="pendulum",seed=3):
    ctx=family_context(family)
    rng=np.random.default_rng(seed)
    obs=rng.normal(size=(32,ctx.obs_dim)); act=rng.integers(0,3,size=32)
    support=SupportBatch(obs,act,obs+0.03*act[:,None],-np.mean(obs*obs,axis=1))
    public=PublicQualityContext(family,obs[0],support,seed,(0.1,0.7))
    return public,FamilyNormalizer.fit(family,obs)


def toy_records(family,bundle):
    selected=tuple(ANCHORS)+tuple(v for v in VARIANTS if v not in ANCHORS)[:4]
    out=[]
    for offset in OFFSETS:
        pub,_=context(family,10+offset+bundle)
        truth={v.fingerprint:float(i/12+0.001*bundle) for i,v in enumerate(VARIANTS)}
        out.append({"family":family,"bundle":bundle,"offset":offset,"public":pub,
                    "truth":truth,"revealed":{v.fingerprint:truth[v.fingerprint] for v in selected}})
    return out


@pytest.fixture
def payload():
    rows,folds,receipts=[],[],[]
    for family in ("pendulum","acrobot"):
        banks=[toy_records(family,b) for b in (0,1)]
        for block in banks:
            receipts.extend({k:r[k] for k in ("family","bundle","offset","revealed")} for r in block)
        for held in (0,1):
            _,norm=context(family)
            raw,fold=evaluate_fold(banks[1-held],banks[held],norm,family=family,
                                   held_bundle=held,deadline=float("inf"))
            rows.extend(raw);folds.append(fold)
    return {"rows":rows,"folds":folds,"source_receipts":receipts}


def test_candidate_arrays_exactly_match_existing_generator():
    ctx=family_context("pendulum")
    for v in VARIANTS:
        bound=plan_bound(v,3,1536)
        seq=generate_candidates(v,bound.candidates_per_root,3,91)
        descriptor,h=candidate_descriptor(v,ctx,91)
        assert h==digest(seq.tolist())
        assert descriptor.shape==(8,) and np.isfinite(descriptor).all()


def test_public_features_exclude_outcomes_and_are_repeatable():
    pub,norm=context()
    a=quality_features(pub,VARIANTS[0],norm,candidates=True)
    assert np.array_equal(a,quality_features(pub,VARIANTS[0],norm,candidates=True))
    assert a.shape==(294,)
    with pytest.raises(TypeError):
        quality_features({"hidden_score":1.0},VARIANTS[0],norm,candidates=True)


def test_ridge_recovers_toy_signal_and_is_antisymmetric():
    rng=np.random.default_rng(7)
    x=rng.normal(size=(128,5));coef=np.asarray([1.,-.4,0.,.3,.1]);y=x@coef
    model=fit_ridge(x,y)
    q=rng.normal(size=(16,5))
    pred=np.asarray([predict_ridge(model,row) for row in q])
    assert np.mean((pred-q@coef)**2)<0.001
    assert predict_ridge(model,q[0])==pytest.approx(-predict_ridge(model,-q[0]),abs=1e-12)
    model2=fit_ridge(x,y)
    assert all(np.array_equal(a,b) for a,b in zip(model,model2))


def test_changing_query_outcomes_cannot_change_predictions():
    bank,query=toy_records("pendulum",0),toy_records("pendulum",1)
    _,norm=context()
    a,_=evaluate_fold(bank,query,norm,family="pendulum",held_bundle=1,deadline=float("inf"))
    altered=copy.deepcopy(query)
    for r in altered: r["truth"]={k:1-v for k,v in r["truth"].items()}
    b,_=evaluate_fold(bank,altered,norm,family="pendulum",held_bundle=1,deadline=float("inf"))
    assert [r["predictions"] for r in a]==[r["predictions"] for r in b]
    assert [r["actual_delta"] for r in a]!=[r["actual_delta"] for r in b]


def test_query_bundle_cannot_enter_training():
    bank=toy_records("pendulum",1);_,norm=context()
    with pytest.raises(ValueError,match="held_bundle_in_training"):
        evaluate_fold(bank,bank,norm,family="pendulum",held_bundle=1,deadline=float("inf"))


@pytest.mark.parametrize("bad",[float("nan"),float("inf")])
def test_nonfinite_training_rejected(bad):
    with pytest.raises(ValueError): fit_ridge([[bad,1.]], [0.])


def test_complete_synthetic_grid(payload):
    assert validate(payload)


@pytest.mark.parametrize("kind",["family","fold","context","pair","method","nan","bool","shrunk_schema"])
def test_missing_or_invalid_grid_fails(payload,kind):
    if kind=="family": payload["source_receipts"]=[r for r in payload["source_receipts"] if r["family"]!="acrobot"]
    elif kind=="fold": payload["folds"].pop()
    elif kind=="context": payload["rows"]=[r for r in payload["rows"] if r["offset"]!=0]
    elif kind=="pair": payload["rows"].pop()
    elif kind=="method": del payload["rows"][0]["predictions"]["paired_mean"]
    elif kind=="shrunk_schema":
        f=payload["folds"][0];a,b=f["supported_pairs"].pop()
        payload["rows"]=[r for r in payload["rows"] if not (r["family"]==f["family"] and
                         r["held_bundle"]==f["held_bundle"] and r["arms"]==[a,b])]
    else: payload["rows"][0]["actual_delta"]=float("nan") if kind=="nan" else True
    with pytest.raises(ValueError):validate(payload)


def test_source_result_is_never_overwritten(tmp_path):
    path=tmp_path/"result.json";path.write_text("original")
    with pytest.raises(FileExistsError):write_artifact(path)
    assert path.read_text()=="original"


def test_source_episode_overlap_is_rejected():
    assert validate_source_separation({0:{10,11},1:{12,13}})
    with pytest.raises(ValueError):validate_source_separation({0:{10},1:{10}})


def test_unused_full_training_table_cannot_change_fit():
    bank,queries=toy_records("pendulum",0),toy_records("pendulum",1)
    _,norm=context()
    a,fa=evaluate_fold(bank,queries,norm,family="pendulum",held_bundle=1,deadline=float("inf"))
    for r in bank: r["truth"]={fp:999. for fp in r["truth"]}
    b,fb=evaluate_fold(bank,queries,norm,family="pendulum",held_bundle=1,deadline=float("inf"))
    assert a==b and fa["model_hashes"]==fb["model_hashes"]


def test_saved_aggregation_is_equal_context_not_pair_pooled():
    import json
    from nexus.evolution2.planner_quality_diagnostic import ROOT,METHODS
    p=json.loads((ROOT/"artifacts/evolution2_25_planner_quality.json").read_text())
    assert validate(p)
    for family in ("pendulum","acrobot","pooled"):
        for method in METHODS:
            means=[]
            for f in ("pendulum","acrobot"):
                if family!="pooled" and f!=family:continue
                for bundle in (0,1):
                    for offset in OFFSETS:
                        rows=[r for r in p["rows"] if (r["family"],r["held_bundle"],r["offset"])==(f,bundle,offset)]
                        means.append(np.mean([abs(r["predictions"][method]-r["actual_delta"]) for r in rows]))
            assert p["summary"][family][method]["mae"]==pytest.approx(np.mean(means),abs=1e-14)


def test_saved_provenance_and_previous_artifacts_are_immutable():
    import hashlib,json,subprocess
    from nexus.evolution2.planner_quality_diagnostic import ROOT,sha
    p=json.loads((ROOT/"artifacts/evolution2_25_planner_quality.json").read_text())
    for path,h in p["historical_artifacts_sha256"].items(): assert sha(ROOT/path)==h
    code=subprocess.check_output(["git","show",p["execution_sha"]+":src/nexus/evolution2/planner_quality_diagnostic.py"],cwd=ROOT)
    protocol=subprocess.check_output(["git","show",p["execution_sha"]+":docs/NEXUS_E2_25_PLANNER_QUALITY.md"],cwd=ROOT)
    assert hashlib.sha256(code).hexdigest()==p["implementation_sha256"]
    assert hashlib.sha256(protocol).hexdigest()==p["protocol_sha256"]


def test_inherited_oracle_scaling_exposes_indirect_query_information():
    from nexus.evolution2.persist_reset_science import FrozenRevealedScale
    # Raw anchors unchanged; an unobserved extreme changes scaled receipts.
    a=FrozenRevealedScale({"anchor_a":1.,"anchor_b":2.,"unobserved":3.})
    b=FrozenRevealedScale({"anchor_a":1.,"anchor_b":2.,"unobserved":5.})
    assert a.unit(2.) != b.unit(2.)
