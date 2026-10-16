"""Recorded complete receding-consistency screen. No new environment collection."""
import json
from pathlib import Path
import pytest
from nexus.world import receding_policy_consistency as m
from nexus.world.planning_value import sha


def test_recorded_receding_consistency_is_complete_and_inconclusive():
    p=json.loads(m.OUTPUT.read_text())
    assert p['complete'] is True
    assert p['label']=='replan_consistency_not_established'
    assert len(p['cells'])==160
    assert p['counts']==dict(commit=2560,recede_same=2560,recede_fresh=2560,common_zero=1280,model_states=1515520)
    assert p['checkpoint_after']==dict(verified=120,missing=0,mismatched=0)
    primary=p['groups']['pooled']['gain_commit_fresh']['interval']
    assert primary['n']==10
    assert primary['mean']<0 and primary['lo']<0<primary['hi']
    rebuilt=m.summarize(p['cells'],m.load_config())
    assert rebuilt['label']==p['label']
    assert rebuilt['groups']['pooled']['gain_commit_fresh']['interval']==primary
    assert sha(m.OUTPUT)=='48736a499e0d650dbf8138cc29e03cdbb623f0e3b413dec7b2b6b552adc2e149'
    audit=m.audit()
    assert audit['audit_passed'] is True and audit['raw_sha256']==sha(m.OUTPUT)
    v=json.loads(Path('artifacts/receding_policy_consistency_verification.json').read_text())
    assert v['audit_passed'] is True and v['n_cells']==160
    assert v['exhausted_session_ledger_unchanged'] is True
    usage=json.loads(Path('artifacts/research_session_receding_policy_consistency_usage.json').read_text())
    assert usage['remaining_session_allowance_s']==0.0
    assert usage['new_real_environment_steps']==8960
    assert usage['new_imagined_transitions']==1515520
    assert sha('artifacts/research_session_first_action_value_usage.json')=='c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462'
    assert sha('artifacts/action_conditioned_q_completed.json')=='aa78514a5a2bb560089453000d8049284aafe3136c83f03c1a88de9dc01a3793'
    assert sha('artifacts/action_conditioned_q_fit.json')=='2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae'
    with pytest.raises(PermissionError,match='session allowance exhausted'):
        m.execute()
