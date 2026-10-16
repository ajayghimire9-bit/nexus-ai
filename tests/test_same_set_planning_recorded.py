"""Recorded complete same-set confirmation. No new environment collection."""
import json
from pathlib import Path
import pytest
from nexus.world import same_set_planning as m
from nexus.world.planning_value import sha


def test_recorded_same_set_confirmation_is_complete_and_inconclusive():
    p=json.loads(m.OUTPUT.read_text())
    assert p['complete'] is True
    assert p['label']=='same_set_advantage_not_established'
    assert len(p['cells'])==60
    assert p['counts']==dict(same=960,fresh_equal=960,h16=960,model_states=506880)
    assert p['checkpoint_after']==dict(verified=120,missing=0,mismatched=0)
    primary=p['groups']['pooled']['gain_same_fresh']['interval']
    assert primary['n']==10
    assert primary['mean']<1.0 and primary['lo']<0<primary['hi']
    rebuilt=m.summarize(p['cells'],m.load_config())
    assert rebuilt['label']==p['label']
    assert rebuilt['groups']['pooled']['gain_same_fresh']['interval']==primary
    assert sha(m.OUTPUT)=='2aac48a16c7dbce512fdf190d5fc4694f7aed3eba2189a0a953b7a704500368d'
    audit=m.audit()
    assert audit['audit_passed'] is True and audit['raw_sha256']==sha(m.OUTPUT)
    v=json.loads(Path('artifacts/same_set_planning_verification.json').read_text())
    assert v['audit_passed'] is True and v['n_cells']==60
    assert v['exhausted_session_ledger_unchanged'] is True
    usage=json.loads(Path('artifacts/research_session_same_set_planning_usage.json').read_text())
    assert usage['remaining_session_allowance_s']==0.0
    assert usage['new_real_environment_steps']==2880
    assert usage['new_imagined_transitions']==506880
    assert sha('artifacts/research_session_first_action_value_usage.json')=='c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462'
    assert sha('artifacts/receding_policy_consistency.json')=='48736a499e0d650dbf8138cc29e03cdbb623f0e3b413dec7b2b6b552adc2e149'
    with pytest.raises(PermissionError,match='session allowance exhausted'):
        m.execute()
