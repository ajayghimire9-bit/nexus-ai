"""Harder CartPole lookahead protocol locks. Collection remains unauthorized."""
from __future__ import annotations
import pytest
from nexus.tasks.cartpole_family import cartpole_lookahead_development, cartpole_lookahead_hard, cartpole_physics_key
from nexus.world import cartpole_lookahead_hard as m
from nexus.world.freeze import v073_confirmation_targets
from nexus.world.planning_value import sha


def test_hard_holdout_is_in_region_and_avoids_closed_splits():
    cfg=m.load_config()
    hold=m.holdout_from_rule()
    assert hold==[(14.0,0.42,0.22),(13.3,0.43,0.25),(12.4,0.28,0.22)]
    occupied,_rows=m.occupied_physics()
    assert all(k not in occupied for k in hold)
    closed={cartpole_physics_key(s) for s in v073_confirmation_targets()}
    closed|={cartpole_physics_key(s) for s in cartpole_lookahead_development()}
    assert (13.0,0.35,0.18) in closed
    assert all(k not in closed for k in hold)
    specs=cartpole_lookahead_hard()
    assert [tuple(cartpole_physics_key(s)) for s in specs]==hold
    assert m.split_hash(specs)==m.HOLD_SPLIT=='9a60e48299b738ef'
    assert cfg['candidate_horizon']==3 and cfg['n_candidates']==16 and cfg['n_actions']==2
    assert cfg['pendulum_weights'] is False


def test_collection_stays_unauthorized():
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False


def test_primary_labels_keep_the_25_point_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='cartpole_hard_lookahead_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='cartpole_hard_lookahead_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='cartpole_hard_lookahead_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_h3_was_not_retuned_and_parents_are_closed():
    cfg=m.load_config()
    report=m.prep()
    assert report['retuned_h3'] is False
    assert report['eligibility']['reused_v073_confirmation'] is False
    assert report['eligibility']['reused_ceilinged_development'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert sha(m.CONFIG)==m.LOCKED_CONFIG=='0515452c75a45d94d610a21ddea91727c499b00a4aeae3d72f56f322a65f954c'
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL=='c2bb743a003544ee1ef6a310ea4c77633fa6f9b42db428a5cfe4a0b40cb26f6e'
