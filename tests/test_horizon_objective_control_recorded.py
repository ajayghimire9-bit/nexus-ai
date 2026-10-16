"""Recorded nested H=8 screen. No retry and no new collection."""
from __future__ import annotations
import json
import pytest
from nexus.world import horizon_objective_control as m
from nexus.world import late_episode_decision_trajectory as late
from nexus.world.planning_value import sha

RAW='bd25f642b6caab86d09d46a7af5c512ead4383f5a61e4ec68b4519935cae24cf'


def test_recorded_h8_screen_hurt_and_stayed_inside_budget():
    assert sha(m.OUTPUT)==RAW
    p=json.loads(m.OUTPUT.read_text())
    assert p['complete'] is True
    assert p['label']=='shorter_horizon_hurts_episode_return'
    assert p['counts']=={'episode':12000,'model_states':1536000}
    assert p['n_episodes']==60 and len(p['cells'])==30
    g=p['groups']['return_gain']['interval']
    assert g['mean']<=-25 and g['hi']<0
    assert p['checkpoint_before']=={'verified':120,'missing':0,'mismatched':0}
    assert p['checkpoint_after']=={'verified':120,'missing':0,'mismatched':0}
    assert p['late_episode_sha256']==sha(late.OUTPUT)
    assert p['config_sha256']=='fc862b46b9ab1163e894acf4a57693282db8d0a20f9f4f35220e0f8f65999b56'


def test_one_run_remaining_is_exhausted_and_late_capture_is_untouched():
    usage=json.loads(m.USAGE.read_text())
    assert usage['remaining_session_allowance_s']==0.0
    assert usage['status']=='complete'
    with pytest.raises(PermissionError,match='session allowance exhausted'):
        m.require_allocation(m.load_config())
    assert sha(late.OUTPUT)=='743b545d78910f7b0df8c83d15b4eb77190798b1dd803ad4daa51434a6214939'
    assert sha('artifacts/research_session_first_action_value_usage.json')=='c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462'
