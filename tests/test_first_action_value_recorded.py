"""Recorded first-action Q result integrity. No new environment collection."""
import json
import pytest
from nexus.world import first_action_value as m


def test_recorded_result_reproduces_and_rejects_tampering():
    cfg=m.load_config();p=json.loads(m.OUTPUT.read_text());parent,stage=m.visited.prior.parent_evidence();fit=m.require_fit(cfg)
    assert p['complete'] is True and p['label']=='aligned_first_action_gain_not_established'
    rebuilt=m.validate(p,cfg,parent,stage,fit)
    assert rebuilt['label']==p['label']
    assert rebuilt['groups']['pooled']['gain_vs_h16']['interval']['mean']==p['groups']['pooled']['gain_vs_h16']['interval']['mean']
    missing=json.loads(m.OUTPUT.read_text());missing['cells']=missing['cells'][:-1]
    with pytest.raises(ValueError):
        m.validate(missing,cfg,parent,stage,fit)
    wrong_fit=json.loads(m.OUTPUT.read_text());wrong_fit['fit_sha256']='0'*64
    with pytest.raises(ValueError):
        m.validate(wrong_fit,cfg,parent,stage,fit)
    assert m.audit()['audit_passed'] is True
