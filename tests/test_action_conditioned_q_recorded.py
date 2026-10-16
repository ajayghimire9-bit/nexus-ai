"""Recorded incomplete action-conditioned run. No new environment collection."""
import json
from pathlib import Path
import pytest
from nexus.world import action_conditioned_q as m
from nexus.world.planning_value import sha


def test_recorded_capture_is_incomplete_and_audit_rejects_it():
    p=json.loads(m.OUTPUT.read_text());fit=json.loads(m.FIT.read_text())
    assert p['complete'] is False and p['label']=='incomplete'
    assert p['failure']['type']=='TimeoutError'
    assert len(p['source_cells'])==160
    assert len(p['cells'])==59
    have={(c['decoder'],c['task'],c['state']) for c in p['cells']}
    assert (9,2,1) not in have
    assert fit['complete'] is True and fit['family']=='action_obs' and len(fit['readouts'])==10
    assert sha(m.OUTPUT)=='6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680'
    assert sha(m.FIT)=='2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae'
    with pytest.raises(RuntimeError,match='incomplete'):
        m.audit()
    v=json.loads(Path('artifacts/action_conditioned_q_verification.json').read_text())
    assert v['label']=='incomplete' and v['n_eval_cells']==59
    assert v['exhausted_session_ledger_unchanged'] is True
