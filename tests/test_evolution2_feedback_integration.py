"""Prospective integration: synthetic callbacks only, no model/environment."""
import copy
import hashlib
import json

import pytest

from nexus.evolution1.toy_loop import ANCHORS,VARIANTS
from nexus.evolution2 import persist_reset_science as science
from nexus.evolution2.persist_reset_scoring import prospective_hidden_evaluator
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator,feedback_reference_digest


@pytest.fixture
def manifest(tmp_path):
    reference=tuple(ANCHORS)
    ref=feedback_reference_digest("pendulum",0,reference)
    source=TrustedEvaluator(reference,family="pendulum",bundle_id=0,
                            produce_score=lambda v:-10. if v==reference[0] else 10.)
    for v in reference:source.evaluate("persist",v)
    scale=source.freeze_feedback_scale("persist",reference=reference,expected_reference_digest=ref)
    p={"version":"prospective_feedback_manifest_v1","scale":scale.payload(),
       "snapshot_digest":scale.snapshot_digest,"reference_digest":ref,"query_family":"pendulum",
       "query_bundle_id":1,"query_slots":[0,1],"allowed_variant_ids":[v.fingerprint for v in reference]}
    path=tmp_path/"manifest.json"
    path.write_text(json.dumps(p))
    return path,hashlib.sha256(path.read_bytes()).hexdigest(),ref,p


def open_evaluator(manifest,producer):
    path,h,ref,_=manifest
    return prospective_hidden_evaluator(path,expected_manifest_sha256=h,
                expected_reference_digest=ref,produce_score=producer)


def test_manifest_validated_without_calling_query_callback(manifest):
    def forbidden(v,key):raise AssertionError("early_query")
    e=open_evaluator(manifest,forbidden)
    assert e.logical==e.physical==e.cached==0


@pytest.mark.parametrize("change",["missing_file","wrong_hash","tampered_scale","wrong_reference",
                                   "family","bundle_bool","slot_bool","variant","duplicate","schema"])
def test_invalid_manifest_fails_before_any_query(manifest,change):
    path,h,ref,p=manifest
    def forbidden(v,key):raise AssertionError("unauthorized_query")
    if change=="missing_file":path=path.with_name("absent.json")
    elif change=="wrong_hash":h="0"*64
    elif change=="wrong_reference":ref="0"*64
    else:
        p=copy.deepcopy(p)
        if change=="tampered_scale":p["scale"]["reference_scores"][0][1]=-999.
        elif change=="family":p["query_family"]="acrobot"
        elif change=="bundle_bool":p["query_bundle_id"]=True
        elif change=="slot_bool":p["query_slots"]=[False]
        elif change=="variant":p["allowed_variant_ids"]=["unregistered"]
        elif change=="duplicate":p["allowed_variant_ids"]*=2
        elif change=="schema":del p["query_slots"]
        path.write_text(json.dumps(p));h=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises((ValueError,FileNotFoundError)):
        prospective_hidden_evaluator(path,expected_manifest_sha256=h,expected_reference_digest=ref,produce_score=forbidden)


def test_method_selected_scores_cache_pairing_and_hidden_feedback_barrier(manifest):
    calls=[]
    def produce(v,key):calls.append(v);return 2. if v==ANCHORS[0] else 8.
    e=open_evaluator(manifest,produce)
    key=science.matched_hidden_seed(1,"pendulum",0)
    assert e.evaluate("persist",ANCHORS[0],seed_key=key)==0.6
    assert e.evaluate("reset",ANCHORS[1],seed_key=key)==0.9
    assert e.evaluate("random",ANCHORS[0],seed_key=key)==0.6
    assert (e.physical,e.cached,e.logical)==(2,1,3) and len(calls)==2
    assert e._hidden_outcomes[0]["raw"]==2.
    with pytest.raises(RuntimeError,match="hidden_development_leaked"):
        e.training_must_not_see(e._hidden_outcomes)


@pytest.mark.parametrize("key",[("hidden",1,"acrobot",0),("hidden",2,"pendulum",0),
                               ("hidden",1,"pendulum",9),("hidden",True,"pendulum",False)])
def test_scope_checked_before_cache_even_boolean_aliases(manifest,key):
    calls=[]
    e=open_evaluator(manifest,lambda v,k:calls.append(v) or 2.)
    e.evaluate("persist",ANCHORS[0],seed_key=("hidden",1,"pendulum",0))
    with pytest.raises(ValueError,match="outside_frozen_manifest"):
        e.evaluate("persist",ANCHORS[0],seed_key=key)
    assert len(calls)==1 and e.logical==1


def test_disallowed_variant_rejected_before_callback(manifest):
    def forbidden(v,key):raise AssertionError("unexpected_variant")
    e=open_evaluator(manifest,forbidden)
    with pytest.raises(ValueError):e.evaluate("persist",VARIANTS[0],seed_key=("hidden",1,"pendulum",0))


@pytest.mark.parametrize("bad",[True,"2.0",float("nan"),float("inf")])
def test_invalid_raw_query_return_not_coerced_or_cached(manifest,bad):
    e=open_evaluator(manifest,lambda v,k:bad)
    with pytest.raises(ValueError):e.evaluate("persist",ANCHORS[0],seed_key=("hidden",1,"pendulum",0))
    assert e._cache=={} and e._hidden_outcomes==[] and e.logical==1


def test_snapshot_and_scope_survive_manifest_file_change(manifest):
    path,h,ref,p=manifest
    e=open_evaluator(manifest,lambda v,k:2.)
    p["query_slots"]=[9];path.write_text(json.dumps(p))
    assert e.evaluate("persist",ANCHORS[0],seed_key=("hidden",1,"pendulum",0))==0.6
    with pytest.raises(ValueError):e.evaluate("persist",ANCHORS[0],seed_key=("hidden",1,"pendulum",9))


def test_clipping_record_preserves_raw_primary_measurement(manifest):
    e=open_evaluator(manifest,lambda v,k:1000.)
    assert e.evaluate("persist",ANCHORS[0],seed_key=("hidden",1,"pendulum",0))==1.
    assert e._hidden_outcomes[0]["raw"]==1000.
    assert e._hidden_outcomes[0]["clipped"] is True
    assert e._hidden_outcomes[0]["feedback_snapshot_digest"]==manifest[3]["snapshot_digest"]
