"""Nested H=8 protocol locks. Collection remains unauthorized."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.world import horizon_objective_control as m
from nexus.world import late_episode_decision_trajectory as late
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences


class Drift:
    def __init__(self,delta=0.01):
        self.delta=float(delta);self.uses_simulator=False
    def step(self,obs,actions):
        o=np.asarray(obs,dtype=np.float32).reshape(-1,3)
        nxt=o.copy();nxt[:,2]=o[:,2]+self.delta
        return nxt,np.zeros(len(o),dtype=np.float64)


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


def test_one_run_allocation_binds_the_registered_hashes_before_collection():
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['config_sha256']==sha(m.CONFIG)
    assert record['protocol_sha256']==sha(m.PROTOCOL)
    m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    assert usage['remaining_session_allowance_s']==90.0
    assert usage['status']=='authorized_not_executed'


def test_primary_labels_require_the_25_point_episode_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='shorter_horizon_improves_episode_return'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='shorter_horizon_hurts_episode_return'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='shorter_horizon_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_closed_parents_are_byte_identical():
    cfg=m.load_config()
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert sha(m.CONFIG)=='fc862b46b9ab1163e894acf4a57693282db8d0a20f9f4f35220e0f8f65999b56'
    assert sha(m.PROTOCOL)=='76894e91fe872fe600d652691203e2f38e5b611c96d22d8df527dffb24e93317'


def test_score_prefix_matches_mpc_reference_without_extra_api_drift():
    obs=np.array([1.0,0.0,0.2],dtype=np.float32)
    _seq,prefix=m.nested_candidates(11100000)
    model=Drift(0.03)
    scores,first=m.score_prefix_with_first(model,obs,prefix)
    ref=m.score_prefix_reference(Drift(0.03),obs,prefix)
    assert np.allclose(scores,ref)
    assert first.shape==(16,3)


def test_config_hash_lock_is_the_registered_value():
    assert m.sha(m.CONFIG).startswith('fc862b46')
