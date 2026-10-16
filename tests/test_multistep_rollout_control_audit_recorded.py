"""Recorded offline audit. No environment collection."""
from __future__ import annotations
import json
from nexus.world import multistep_rollout_control_audit as m
from nexus.world.planning_value import sha

RAW_SHA='9695d4c950a0a20a37e9d070be76da496eca90ade76d8fc156e284436eb1da2a'


def test_recorded_audit_used_zero_environment_steps():
    assert sha(m.OUTPUT)==RAW_SHA
    report=json.loads(m.OUTPUT.read_text())
    assert report['complete'] is True
    assert report['new_environment_steps']==0
    assert report['new_imagined_transitions']==353280
    assert report['training']==0
    assert report['authorized'] is False
    assert report['confirmation_used'] is False
    assert report['checkpoint']=={'verified':120,'missing':0,'mismatched':0}
    assert report['recommendation']['choice']=='shorter_horizon_control'
    assert report['recommendation']['authorized'] is False
    assert report['rollouts']['horizons']['16']['student_on_student']['interval']['mean']>0.5
    assert report['plan_consistency']['receding_suffix_mismatch_is_not_model_error'] is True
