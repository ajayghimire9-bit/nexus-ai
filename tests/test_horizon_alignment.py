"""Horizon-alignment locks. These tests do not collect the registered grid."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pytest
import yaml
from nexus.tasks.pendulum_family import PENDULUM_MAX_STEPS, pendulum_context_development
from nexus.tasks.spec import make_task_env
from nexus.world import horizon_alignment as m
from nexus.world import same_set_planning as same
from nexus.world import receding_policy_consistency as recede
from nexus.world import action_conditioned_q as acq
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences


def test_pendulum_time_limit_is_truncation_not_termination():
    assert PENDULUM_MAX_STEPS==200
    env=make_task_env(pendulum_context_development()[0],seed=0)
    try:
        assert int(env.spec.max_episode_steps)==200
        env.reset(seed=0);term=trunc=False;n=0
        while not (term or trunc):
            _,_,term,trunc,_=env.step(0);n+=1
            if n>205:break
        assert n==200 and term is False and trunc is True
    finally:env.close()


def test_planner_scores_horizon_length_not_elapsed_time():
    class Dummy:
        uses_simulator=False
        def step(self,obs,action):
            n=np.asarray(obs).reshape(-1,3).shape[0]
            return np.zeros((n,3),dtype=np.float32),np.zeros(n)
    from nexus.world.planning import RandomShootingMPC
    from nexus.world.rewards import pendulum_step_reward
    planner=RandomShootingMPC(model=Dummy(),n_actions=3,horizon=16,n_candidates=16,seed=0,
                              enforce_time_budget=False,step_reward=pendulum_step_reward)
    obs=np.array([1.0,0.0,0.0],dtype=np.float32)
    long=planner._score_batch(obs,candidate_sequences(0,16,16))
    short=planner._score_batch(obs,candidate_sequences(0,16,1))
    assert long.shape==(16,) and short.shape==(16,)
    assert m.planner_clips_elapsed_time() is False


def test_shared_step_seed_matches_only_when_horizons_match():
    full=candidate_sequences(21,16,16);again=candidate_sequences(21,16,16);short=candidate_sequences(21,16,15)
    assert np.array_equal(full,again) and short.shape==(16,15)
    assert m.remaining_horizon(0,200)==16 and m.remaining_horizon(184,200)==16
    assert m.remaining_horizon(185,200)==15 and m.remaining_horizon(199,200)==1
    assert m.remaining_horizon(0,16)==16 and m.remaining_horizon(1,16)==15
    a=[0]*185+[1]*15;b=[0]*185+[2]*15
    assert m.first_mismatch(a,b)==185
    assert m.first_mismatch(a,a) is None


def test_labels_do_not_promote_the_short_window():
    assert m.classify_primary(30.0,1.0,40.0,0.0,-1.0,1.0,10,True,True)=='horizon_alignment_gain'
    assert m.classify_primary(-30.0,-40.0,-1.0,2.0,1.0,3.0,10,True,True)=='fixed_horizon_retained'
    assert m.classify_primary(4.0,-1.0,8.0,2.0,1.1,3.0,10,True,True)=='boundary_specific_alignment'
    assert m.classify_primary(4.0,-1.0,8.0,0.2,-1.0,1.0,10,True,True)=='horizon_alignment_not_established'
    assert m.classify_primary(30.0,1.0,40.0,2.0,1.1,3.0,10,True,False)=='incomplete'


def test_budget_seeds_one_run_authorization_and_parents_frozen():
    cfg=m.load_config();counts=m.budget(cfg)
    assert counts['short_fixed']+counts['short_aligned']+counts['full_fixed']+counts['full_aligned']==25920
    assert counts['model_states']==6405120
    assert counts['short_aligned']==counts['short_fixed'] and counts['full_aligned']==counts['full_fixed']
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['authority_commit']=='b4691dbdd3661db52399b709edf3148b8cdd0bf6'
    assert record['time_cap_s']==180 and record['env_cap']==25920 and record['model_cap']==6405120
    with pytest.raises(PermissionError,match='session allowance exhausted'):
        m.require_allocation(cfg)
    recede_cfg=yaml.safe_load(recede.CONFIG.read_text());same_cfg=yaml.safe_load(same.CONFIG.read_text())
    blocked=set().union(*acq.seed_groups(yaml.safe_load(acq.CONFIG.read_text())),*recede.seed_groups(recede_cfg),*same.seed_groups(same_cfg))
    used=set().union(*m.seed_groups(cfg))
    assert not (used & blocked) and min(used)>=9000000
    assert sha('artifacts/same_set_planning.json')=='2aac48a16c7dbce512fdf190d5fc4694f7aed3eba2189a0a953b7a704500368d'
    text=Path('docs/NEXUS_HORIZON_ALIGNMENT_PROTOCOL.md').read_text()
    assert 'authorized: false' in text and 'primary: gain_full' in text
    assert 'confirmation_physics_authorized: false' in text
    assert m.OUTPUT.exists()
