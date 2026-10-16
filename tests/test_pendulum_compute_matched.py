"""Pendulum compute-matched protocol locks. Collection remains unauthorized."""
from __future__ import annotations
import pytest
from nexus.tasks.pendulum_family import pendulum_context_development, pendulum_physics_key
from nexus.world import bellman_backup_control as bbc
from nexus.world import lookahead_transfer_confirmation as transfer
from nexus.world import pendulum_compute_matched as m
from nexus.world.planning_value import sha


def test_holdout_is_development_and_confirmation_stays_closed():
    cfg=m.load_config()
    specs=pendulum_context_development()
    hold=[tuple(pendulum_physics_key(s)) for s in specs]
    assert hold==[(6.0,1.0,1.0),(10.0,2.0,1.0),(10.0,1.0,1.55)]
    assert cfg['closed_confirmation_split_hash']==transfer.HOLD_SPLIT=='73844661addfa11b'
    assert cfg['reset_base']==15000000 and cfg['step_seed_base']==15100000
    ours=set().union(*m.seed_groups(cfg))
    blocked=set().union(*bbc.seed_groups(bbc.load_config()),*transfer.seed_groups(transfer.load_config()))
    assert ours.isdisjoint(blocked)
    assert min(ours)>=15000000


def test_forty_eight_candidates_are_a_prefix_of_frozen_sixteen():
    seq48,seq16=m.shared_candidates(15100000)
    assert seq48.shape==(48,16) and seq16.shape==(16,16)
    assert (seq48[:16]==seq16).all()
    counts=m.budget(m.load_config())
    assert counts['episode']==24000 and counts['model_states']==18468000
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
    assert m.classify_primary(25.1,0.1,50.0,10)=='pendulum_compute_matched_lookahead_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='pendulum_compute_matched_lookahead_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='pendulum_compute_matched_lookahead_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_frozen_lookahead_identity_and_prep():
    m.assert_controller_identity()
    cfg=m.load_config()
    assert cfg['compute_matched_control'] is True
    assert cfg['reuse_development_checkpoints'] is True
    assert cfg['training_updates']==0
    assert cfg['n_candidates']==16 and cfg['matched_candidates']==48
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
