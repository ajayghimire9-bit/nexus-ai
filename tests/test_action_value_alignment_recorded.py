"""Tracked-data arithmetic and corruption tests, no local model binaries."""
import importlib.util
import json
from pathlib import Path
import pytest


def module():
    spec=importlib.util.spec_from_file_location('action_alignment_audit',Path('scripts/audit_action_value_alignment.py'));out=importlib.util.module_from_spec(spec);spec.loader.exec_module(out);return out


def test_primary_reward_indices_and_intervals_are_independently_reconstructed(monkeypatch):
    a=module()
    def forbidden(*args,**kwargs):raise AssertionError('no experiment or simulation')
    monkeypatch.setattr(a.m,'execute',forbidden)
    p=a.audit();assert p['audit_passed'] is True
    assert p['new_environment_steps']==p['new_imagined_transitions']==0


@pytest.mark.parametrize('damage',['decoder','visitor','index','regret','summary'])
def test_recorded_result_corruption_rejected(monkeypatch,tmp_path,damage):
    a=module();p=json.loads(a.m.OUTPUT.read_text())
    if damage=='decoder':p['cells']=[r for r in p['cells'] if r['decoder']!=9]
    elif damage=='visitor':p['cells']=[r for r in p['cells'] if r['visitor']!=1]
    elif damage=='index':p['cells'][0]['geometry']['selected_sequence']=False
    elif damage=='regret':p['cells'][0]['geometry']['metrics']['total_regret']+=1
    else:p['groups']['pooled']['state']['total_regret']['interval']['mean']+=1
    path=tmp_path/'bad.json';path.write_text(json.dumps(p));monkeypatch.setattr(a.m,'OUTPUT',path)
    with pytest.raises((ValueError,KeyError,RuntimeError)):a.audit()
