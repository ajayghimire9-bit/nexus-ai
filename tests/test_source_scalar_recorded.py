"""Repository-only audits of the locked source scalar and fresh outcomes."""
import importlib.util
import json
from pathlib import Path
import pytest


def module():
    spec=importlib.util.spec_from_file_location('source_scalar_audit',Path('scripts/audit_source_scalar_calibration.py'));out=importlib.util.module_from_spec(spec);spec.loader.exec_module(out);return out


def test_independent_source_fit_and_return_arithmetic_need_no_simulation(monkeypatch):
    a=module()
    def forbidden(*args,**kwargs):raise AssertionError('offline audit must not simulate')
    monkeypatch.setattr(a.m,'execute',forbidden)
    p=a.audit();assert p['audit_passed'] is True
    assert p['new_environment_steps']==p['new_imagined_transitions']==0


@pytest.mark.parametrize('damage',['decoder','visitor','scalar','summary','fit_hash'])
def test_closed_result_rejects_corruption(monkeypatch,tmp_path,damage):
    a=module();p=json.loads(a.m.OUTPUT.read_text())
    if damage=='decoder':p['cells']=[r for r in p['cells'] if r['decoder']!=9]
    elif damage=='visitor':p['cells']=[r for r in p['cells'] if r['state']!=1]
    elif damage=='scalar':p['beta']+=.01
    elif damage=='summary':p['scalar_groups']['pooled']['gain_vs_base']['interval']['mean']+=1
    else:p['source_fit_sha256']='b'*64
    path=tmp_path/'corrupt.json';path.write_text(json.dumps(p));monkeypatch.setattr(a.m,'OUTPUT',path)
    with pytest.raises((ValueError,KeyError,RuntimeError)):a.audit()
