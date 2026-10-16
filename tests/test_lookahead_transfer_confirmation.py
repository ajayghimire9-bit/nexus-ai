"""Lookahead transfer protocol locks. Collection remains unauthorized."""
from __future__ import annotations
import pytest
from nexus.tasks.pendulum_family import pendulum_amortized_confirmation, pendulum_lookahead_transfer_holdout, pendulum_physics_key
from nexus.world import bellman_backup_control as bbc
from nexus.world import late_episode_decision_trajectory as late
from nexus.world import lookahead_transfer_confirmation as m
from nexus.world.planning_value import sha


def test_holdout_rule_is_disjoint_and_reproducible():
    cfg=m.load_config()
    hold=m.holdout_from_rule()
    assert hold==[(17.1,1.5,0.8),(12.5,0.65,0.9),(4.2,3.2,1.7)]
    occupied,_rows=m.occupied_physics()
    assert all(k not in occupied for k in hold)
    specs=pendulum_lookahead_transfer_holdout()
    assert [tuple(pendulum_physics_key(s)) for s in specs]==hold
    assert m.split_hash(specs)==m.HOLD_SPLIT=='73844661addfa11b'
    amortized={pendulum_physics_key(s) for s in pendulum_amortized_confirmation()}
    assert amortized.isdisjoint(set(hold))
    counts=m.budget(cfg)
    assert counts['episode']==27840 and counts['support']==3840 and counts['control']==24000
    assert counts['model_states']==12324000
    assert counts['lookahead_imagined_per_step']==771 and counts['h16_imagined_per_step']==256


def test_seeds_do_not_reuse_development_lookahead_or_late_episode():
    cfg=m.load_config()
    ours=set().union(*m.seed_groups(cfg))
    blocked=set().union(*late.seed_groups(late.load_config()),*bbc.seed_groups(bbc.load_config()))
    assert ours.isdisjoint(blocked)
    assert min(ours)>=14000000


def test_collection_stays_unauthorized_and_has_no_output():
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.execute()


def test_primary_labels_require_the_25_point_episode_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='lookahead_transfer_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='lookahead_transfer_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='lookahead_transfer_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_frozen_controller_is_the_development_lookahead_pair():
    m.assert_controller_identity()
    cfg=m.load_config()
    assert cfg['new_network'] is False
    assert cfg['compute_matched_control'] is False
    assert cfg['training_updates']==0
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert 'artifacts/latent_control.json' not in cfg['parents']
    assert 'artifacts/control_replication.json' not in cfg['parents']
    report=m.prep()
    assert report['authorized'] is False
    assert report['confirmation_outcomes_read'] is False
    assert report['eligibility']['reused_closed_confirmation_outcomes'] is False
    assert report['eligibility']['holdout_collides_registered'] is False
    assert sha(m.CONFIG)==m.LOCKED_CONFIG=='385285edca761d60c1759bf8ef951c2682794e7b3d6066e9223aad5236c9cae8'
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL=='5c2e0d7300e497c65c0564990aa2a86ab4d08e79979c40d8ce7d2ea51735c942'
    assert m.load_allocation()['config_sha256']==m.LOCKED_CONFIG
    assert m.load_allocation()['protocol_sha256']==m.LOCKED_PROTOCOL
