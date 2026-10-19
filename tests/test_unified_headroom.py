"""No checkpoint loading, real neural inference, fitting or environments."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("headroom",ROOT/"scripts/audit_unified_headroom.py")
h = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(h)


def grid():
    c = json.loads(h.CONFIG.read_text())
    rows = [dict(family=f,model_bundle=b,query_bundle=1-b,offset=o,
                 anchor_best_raw=0.,grammar_best_raw=2.,headroom=2.)
            for f in c["families"] for b in c["model_bundles"] for o in c["offsets"]]
    return c,rows


def test_headroom_screen_is_not_improvement_of_a_learner():
    c,rows = grid()
    assert h.summarize(rows,c)["screen_pass"]
    for r in rows: r.update(grammar_best_raw=0.,headroom=0.)
    result = h.summarize(rows,c)
    assert not result["screen_pass"] and result["no_positive_headroom_states"]==16


@pytest.mark.parametrize("change",["family","model","duplicate","nan","same_source","index","boolean_id"])
def test_missing_or_invalid_source_grid_rejected(change):
    c,r = grid()
    if change=="family": r=[x for x in r if x["family"]!="pendulum"]
    if change=="model": r=[x for x in r if x["model_bundle"]!=0]
    if change=="duplicate": r[-1]=copy.deepcopy(r[0])
    if change=="nan": r[0]["headroom"]=float("nan")
    if change=="same_source": r[0]["query_bundle"]=r[0]["model_bundle"]
    if change=="index": r[0]["headroom"]+=1.
    if change=="boolean_id": r[0]["model_bundle"]=False
    with pytest.raises(ValueError): h.summarize(r,c)


def test_checkpoint_hash_required_before_loading(tmp_path):
    path=tmp_path/"known.pt"
    with pytest.raises(FileNotFoundError): h.verify_file(path,"0"*64)
    path.write_bytes(b"fixture bytes, not a checkpoint")
    known=hashlib.sha256(path.read_bytes()).hexdigest()
    assert h.verify_file(path,known)==known
    path.write_bytes(b"mutated")
    with pytest.raises(ValueError): h.verify_file(path,known)


def test_frozen_fingerprint_includes_normalization_and_weights():
    class Value:
        def __init__(self): self.a=np.array([1.,2.],np.float32)
        def detach(self): return self
        def cpu(self): return self
        def numpy(self): return self.a
    value=Value()
    from nexus.rl.running_stats import RunningMeanStd
    m=SimpleNamespace(net=SimpleNamespace(state_dict=lambda:{"weight":value}),obs_rms=RunningMeanStd((2,)))
    before=h.tensor_hash(m)
    assert h.tensor_hash(m)==before
    m.obs_rms.mean[0]+=1
    assert h.tensor_hash(m)!=before
    m.obs_rms.mean[0]-=1
    m.obs_rms.epsilon *= 2
    assert h.tensor_hash(m)!=before
    m.obs_rms.epsilon /= 2
    value.a[0]+=1
    assert h.tensor_hash(m)!=before


def test_saved_capture_arithmetic_frozen_state_and_execution_provenance():
    import subprocess
    path=ROOT/"artifacts/unified_headroom_audit.json"
    p=json.loads(path.read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()=="1fe3a89c736cec3c3cc8276a04e4afbbfe61bc57f258e5978ddef77a106b079c"
    assert p["declared_complete"]
    assert h.summarize(p["rows"],p["config"])==p["summary"]
    assert len(p["provenance"])==4
    assert all(r["state_before"]==r["state_after"] and r["unchanged"] for r in p["provenance"])
    from nexus.evolution2.generated_strategies import universe, leaf
    from nexus.evolution1.toy_loop import ANCHORS
    ids={s.fingerprint for s in universe()}
    for row in p["rows"]:
        assert set(row["strategies"])==ids
        anchor=max(row["strategies"][leaf(a).fingerprint]["raw_proxy"] for a in ANCHORS)
        best=max(r["raw_proxy"] for r in row["strategies"].values())
        assert best-anchor==row["headroom"]==0.
    for name,digest_ in p["code_sha256"].items():
        assert hashlib.sha256(subprocess.check_output(["git","show",p["execution_sha"]+":"+name],cwd=ROOT)).hexdigest()==digest_
    assert all(h.sha(ROOT/name)==digest_ for name,digest_ in p["historical_artifacts_sha256"].items())
