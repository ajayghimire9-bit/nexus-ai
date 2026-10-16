"""Repository-only recorded-result regression; frozen binaries not required."""
import importlib.util
import json
from pathlib import Path
import pytest


def module():
    spec=importlib.util.spec_from_file_location('visited_value_audit',Path('scripts/audit_visited_value_ranking.py'));result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def test_independent_scalar_arithmetic_reproduces_source_metrics(monkeypatch):
    a=module()
    def forbidden(*args,**kwargs):raise AssertionError('no environment or model inference')
    monkeypatch.setattr(a.m,'execute',forbidden)
    p=a.audit()
    assert p['audit_passed'] is True
    assert p['new_environment_steps']==p['new_imagined_transitions']==p['model_inference_calls']==0


@pytest.mark.parametrize('damage',['decoder','visitor','context','metric','summary'])
def test_result_corruption_rejected(monkeypatch,tmp_path,damage):
    a=module();p=json.loads(a.m.OUTPUT.read_text())
    if damage=='decoder':p['cells']=[r for r in p['cells'] if r['decoder']!=9]
    elif damage=='visitor':p['cells']=[r for r in p['cells'] if r['visitor']!=1]
    elif damage=='context':del p['cells'][0]['metrics']['zero']
    elif damage=='metric':p['cells'][0]['metrics']['zero']['tail_mse']=True
    else:p['groups']['pooled']['centered_benefit']['interval']['mean']+=1
    path=tmp_path/'corrupt.json';path.write_text(json.dumps(p));monkeypatch.setattr(a.m,'OUTPUT',path)
    with pytest.raises((ValueError,KeyError,RuntimeError)):a.audit()
