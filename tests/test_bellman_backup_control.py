"""Bellman-backup protocol locks. Collection remains unauthorized."""
from __future__ import annotations
import pytest
from nexus.world import bellman_backup_control as m
from nexus.world import late_episode_decision_trajectory as late
from nexus.world.planning_value import sha


def test_fresh_seeds_do_not_reuse_late_episode_or_h8_resets():
    cfg=m.load_config()
    late_cfg=late.load_config()
    ours=set().union(*m.seed_groups(cfg))
    theirs=set().union(*late.seed_groups(late_cfg))
    assert ours.isdisjoint(theirs)
    assert min(ours)>=13000000
    counts=m.budget(cfg)
    assert counts['episode']==24000 and counts['model_states']==12324000


def test_collection_stays_unauthorized_and_has_no_output():
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False


def test_primary_labels_require_the_25_point_episode_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='bellman_backup_improves_episode_return'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='bellman_backup_hurts_episode_return'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='bellman_backup_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_closed_parents_are_byte_identical():
    cfg=m.load_config()
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert cfg['new_network'] is False
    assert cfg['training_updates']==0
