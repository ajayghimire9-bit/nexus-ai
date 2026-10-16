"""Repository-only checks; no local checkpoints or environment collection."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest


def audit_module():
    spec=importlib.util.spec_from_file_location('commitment_arithmetic_audit',Path('scripts/audit_commitment_value.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_recorded_reward_contrasts_reconstruct_without_checkpoint_files():
    module=audit_module(); result=module.audit()
    assert result['audit_passed'] is True
    assert result['new_environment_steps']==result['model_inference_calls']==0
    assert len(result['groups']['pooled']['interaction']['per_decoder'])==10


@pytest.mark.parametrize('corruption',['decoder','reward','summary'])
def test_recorded_audit_rejects_missing_replication_or_bad_arithmetic(tmp_path,corruption):
    module=audit_module();p=copy.deepcopy(json.loads(module.OUTPUT.read_text()))
    if corruption=='decoder':p['cells']=[r for r in p['cells'] if r['decoder']!=9]
    elif corruption=='reward':p['cells'][0]['first_traces'][0]['rewards'][0]+=1
    else:p['comparisons']['interaction']['interval']['mean']+=1
    dst=tmp_path/'corrupt.json';dst.write_text(json.dumps(p));module.OUTPUT=dst
    with pytest.raises((ValueError,KeyError,RuntimeError)):module.audit()
