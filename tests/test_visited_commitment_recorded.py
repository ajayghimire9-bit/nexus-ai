"""Tracked-result arithmetic only; no simulation or local binary requirements."""
import importlib.util
import json
from pathlib import Path
import pytest


def module():
    spec=importlib.util.spec_from_file_location('visited_reward_audit',Path('scripts/audit_visited_commitment.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def test_recorded_contrasts_and_intervals_without_new_environment_data(monkeypatch):
    audit=module()
    def forbidden(*args,**kwargs):raise AssertionError('no simulation permitted')
    monkeypatch.setattr(audit.m,'execute',forbidden)
    result=audit.audit()
    assert result['audit_passed'] is True
    assert result['new_environment_steps']==result['model_inference_calls']==0
    assert len(result['groups']['pooled']['interaction']['per_decoder'])==10


@pytest.mark.parametrize('damage',['decoder','visitor','unselected_reward','saved_summary'])
def test_recorded_audit_rejects_corrupt_grid_and_arithmetic(monkeypatch,tmp_path,damage):
    audit=module();p=json.loads(audit.m.OUTPUT.read_text())
    if damage=='decoder':p['cells']=[r for r in p['cells'] if r['decoder']!=9]
    elif damage=='visitor':p['cells']=[r for r in p['cells'] if r['state']!=1]
    elif damage=='unselected_reward':p['cells'][0]['first_traces'][0]['rewards'][0]+=1
    else:p['comparisons']['interaction']['interval']['mean']+=1
    target=tmp_path/'corrupt.json';target.write_text(json.dumps(p));monkeypatch.setattr(audit.m,'OUTPUT',target)
    with pytest.raises((ValueError,KeyError,RuntimeError)):audit.audit()
