"""Acrobot compute-matched protocol locks. Collection remains unauthorized."""
from __future__ import annotations
import pytest
from nexus.tasks.acrobot_family import acrobot_lookahead_confirmation, acrobot_lookahead_development, acrobot_physics_key
from nexus.world import acrobot_compute_matched as m
from nexus.world import acrobot_lookahead as base
from nexus.world import acrobot_lookahead_confirm as confirm
from nexus.world.planning_value import sha


def test_holdout_is_development_and_confirmation_stays_closed():
    cfg=m.load_config()
    hold=base.holdout_from_rule()
    assert hold==[(0.95,1.2,0.8),(1.25,1.35,0.95),(0.75,1.4,1.4)]
    specs=acrobot_lookahead_development()
    assert [tuple(acrobot_physics_key(s)) for s in specs]==hold
    closed={acrobot_physics_key(s) for s in acrobot_lookahead_confirmation()}
    assert closed.isdisjoint(set(hold))
    assert cfg['holdout_split_hash']==m.HOLD_SPLIT=='911ea726b6ed2111'
    assert cfg['closed_confirmation_split_hash']==confirm.HOLD_SPLIT=='b309bd481fd8abcb'
    assert cfg['reset_base']==24000000 and cfg['step_seed_base']==24100000
    ours=set().union(*m.seed_groups(cfg))
    assert min(ours)>=24000000
    blocked={base.reset_seed(base.load_config(),s,t) for s in range(10) for t in range(3)}
    blocked|={base.reset_seed(confirm.load_config(),s,t) for s in range(10) for t in range(3)}
    assert ours.isdisjoint(blocked)


def test_forty_eight_candidates_are_a_prefix_of_frozen_sixteen():
    seq48,seq16=m.shared_candidates(24100000)
    assert seq48.shape==(48,16) and seq16.shape==(16,16)
    assert (seq48[:16]==seq16).all()
    counts=m.budget(m.load_config())
    assert counts['episode_max']==12000 and counts['model_states_max']==9234000
    assert counts['lookahead_imagined_per_step']==771
    assert counts['matched_h16_imagined_per_step']==768
    assert counts['original_h16_imagined_per_step']==256
    assert counts['training_updates']==0


def test_collection_stays_unauthorized_and_has_no_output():
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.execute()


def test_primary_labels_require_the_25_point_episode_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='acrobot_compute_matched_lookahead_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='acrobot_compute_matched_lookahead_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='acrobot_compute_matched_lookahead_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_frozen_checkpoints_and_lookahead_identity():
    m.load_frozen_models(m.load_config())
    cfg=m.load_config()
    assert cfg['compute_matched_control'] is True
    assert cfg['reuse_development_checkpoints'] is True
    assert cfg['training_updates']==0
    assert cfg['n_candidates']==16 and cfg['matched_candidates']==48
    assert cfg['pendulum_weights'] is False and cfg['cartpole_h3'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    report=m.prep()
    assert report['authorized'] is False
    assert report['confirmation_outcomes_read'] is False
    assert report['eligibility']['reused_confirmation_physics'] is False
    assert sha(m.CONFIG)==m.LOCKED_CONFIG
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL
    assert m.load_allocation()['config_sha256']==m.LOCKED_CONFIG
    assert m.load_allocation()['protocol_sha256']==m.LOCKED_PROTOCOL
