"""Nested H=8 protocol locks. Collection remains unauthorized."""
from __future__ import annotations
import json
import numpy as np
import pytest
from nexus.world import horizon_objective_control as m
from nexus.world import late_episode_decision_trajectory as late
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences


def test_nested_prefix_is_not_an_independent_draw():
    seed=11100000
    full,prefix=m.nested_candidates(seed)
    assert full.shape==(16,16) and prefix.shape==(16,8)
    assert np.array_equal(prefix,full[:,:8])
    independent=candidate_sequences(seed,16,8)
    assert not np.array_equal(prefix,independent)


def test_budget_and_paired_seeds_match_late_episode_resets():
    cfg=m.load_config()
    late_cfg=late.load_config()
    assert cfg['reset_base']==late_cfg['reset_base']
    assert cfg['step_seed_base']==late_cfg['step_seed_base']
    counts=m.budget(cfg)
    assert counts==dict(episode=12000,model_states=1536000)
    archived=m.archived_h16_returns()
    assert len(archived)==30
    assert (0,0) in archived


def test_collection_stays_unauthorized_and_has_no_output():
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False


def test_primary_labels_require_the_25_point_episode_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='shorter_horizon_improves_episode_return'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='shorter_horizon_hurts_episode_return'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='shorter_horizon_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_closed_parents_are_byte_identical():
    cfg=m.load_config()
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
