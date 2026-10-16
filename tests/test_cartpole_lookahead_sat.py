"""Saturation-holdout lookahead protocol locks. The one-run allocation is consumed."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from nexus.tasks.cartpole_family import cartpole_h3_saturation, cartpole_physics_key
from nexus.world import cartpole_h3_saturation as sat
from nexus.world import cartpole_lookahead_sat as m
from nexus.world.planning_value import sha


def test_holdout_is_the_locked_six_task_saturation_split():
    cfg=m.load_config()
    hold=sat.holdout_from_rule()
    assert hold==[(13.2,0.27,0.23),(15.6,0.25,0.28),(15.4,0.27,0.2),(15.5,0.3,0.28),(16.0,0.34,0.2),(13.8,0.31,0.27)]
    specs=cartpole_h3_saturation()
    assert [tuple(cartpole_physics_key(s)) for s in specs]==hold
    assert sat.split_hash(specs)==m.HOLD_SPLIT=='a69833ab38a34ab4'
    assert cfg['eval_tasks']==6 and cfg['drop_ceilinged_tasks'] is False
    assert cfg['candidate_horizon']==3 and cfg['n_candidates']==16 and cfg['n_actions']==2
    assert cfg['pendulum_weights'] is False
    counts=m.budget(cfg)
    assert counts['train']==12800 and counts['control_max']==60000
    assert counts['model_states_max']==4380000


def test_one_run_allocation_is_consumed_and_output_exists():
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['drop_ceilinged_tasks'] is False
    assert record['config_sha256']==sha(m.CONFIG)==m.LOCKED_CONFIG
    assert record['protocol_sha256']==sha(m.PROTOCOL)==m.LOCKED_PROTOCOL
    with pytest.raises(PermissionError,match='session allowance exhausted'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is True
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    assert float(usage['remaining_session_allowance_s'])==0.0
    assert int(usage['retries'])==0
    assert usage['raw_sha256']==sha(m.OUTPUT)
    assert usage['label']=='cartpole_sat_lookahead_not_established'


def test_primary_labels_keep_the_25_point_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='cartpole_sat_lookahead_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='cartpole_sat_lookahead_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='cartpole_sat_lookahead_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_h3_was_not_retuned_and_parents_are_closed():
    cfg=m.load_config()
    assert cfg['candidate_horizon']==3 and cfg['pendulum_weights'] is False
    assert cfg['drop_ceilinged_tasks'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert sha(m.CONFIG)==m.LOCKED_CONFIG=='7fe2a70eaf88953f2203f9f70de586d69991e16741864075fcdfbe7148547dbe'
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL=='3c82cdd477082ea3898ac346e4d193eda5506e6aab947f259d76fe954d75dac8'
    audit=m.audit_results()
    assert audit['audit_passed'] is True
    assert audit['label']=='cartpole_sat_lookahead_not_established'
    assert audit['drop_ceilinged_tasks'] is False
    assert audit['retuned_h3'] is False
    assert audit['holdout_split_hash']=='a69833ab38a34ab4'
