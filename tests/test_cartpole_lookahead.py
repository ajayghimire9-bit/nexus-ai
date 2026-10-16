"""CartPole lookahead protocol locks. Collection remains unauthorized."""
from __future__ import annotations
import pytest
from nexus.tasks.cartpole_family import cartpole_lookahead_development, cartpole_physics_key
from nexus.world import cartpole_lookahead as m
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_PRIMARY_HORIZON
from nexus.world.planning_value import sha


def test_holdout_is_disjoint_and_uses_frozen_h3():
    cfg=m.load_config()
    hold=m.holdout_from_rule()
    assert hold==[(8.5,0.39,0.19),(11.6,0.9,0.07),(7.9,0.88,0.29)]
    occupied,_rows=m.occupied_physics()
    assert all(k not in occupied for k in hold)
    specs=cartpole_lookahead_development()
    assert [tuple(cartpole_physics_key(s)) for s in specs]==hold
    assert m.split_hash(specs)==m.HOLD_SPLIT=='4bc1f5866ac6c753'
    assert cfg['candidate_horizon']==FROZEN_PRIMARY_HORIZON==3
    assert cfg['n_candidates']==FROZEN_CANDIDATES[3]==16
    assert cfg['n_actions']==2
    assert cfg['pendulum_weights'] is False
    counts=m.budget(cfg)
    assert counts['train']==12800 and counts['control_max']==30000
    assert counts['model_states_max']==2190000
    assert counts['lookahead_imagined_per_step']==98 and counts['h3_imagined_per_step']==48


def test_collection_stays_unauthorized_and_has_no_output():
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.execute()


def test_primary_labels_require_the_25_point_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='cartpole_lookahead_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='cartpole_lookahead_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='cartpole_lookahead_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_shared_candidates_are_cartpole_not_pendulum():
    seq=m.shared_candidates(18100000)
    assert seq.shape==(16,3) and int(seq.max())<=1
    report=m.prep()
    assert report['authorized'] is False
    assert report['pendulum_weights'] is False
    assert report['eligibility']['reused_closed_cartpole_confirmation'] is False
    cfg=m.load_config()
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert sha(m.CONFIG)==m.LOCKED_CONFIG=='de1113d814ef506eba7e477fc314c48a9d289a497bab018a02cd1acaa6673ece'
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL=='6bbd5caa29fc4156adfb13f72d00466d0d640812b62b7ca4215ddc8e0335c112'
