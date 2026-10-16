"""Saturation-holdout lookahead protocol locks. Collection remains unauthorized."""
from __future__ import annotations
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


def test_collection_stays_unauthorized():
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    assert record['drop_ceilinged_tasks'] is False
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False


def test_primary_labels_keep_the_25_point_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='cartpole_sat_lookahead_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='cartpole_sat_lookahead_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='cartpole_sat_lookahead_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_h3_was_not_retuned_and_parents_are_closed():
    cfg=m.load_config()
    assert cfg['candidate_horizon']==3 and cfg['pendulum_weights'] is False
    assert cfg['drop_ceilinged_tasks'] is False
    report=m.prep()
    assert report['retuned_h3'] is False and report['drop_ceilinged_tasks'] is False
    assert report['eligibility']['reused_v073_confirmation'] is False
    assert report['eligibility']['n_tasks']==6
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert sha(m.CONFIG)==m.LOCKED_CONFIG=='7fe2a70eaf88953f2203f9f70de586d69991e16741864075fcdfbe7148547dbe'
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL=='3c82cdd477082ea3898ac346e4d193eda5506e6aab947f259d76fe954d75dac8'
