"""Tree-reuse protocol locks. The one-run allocation is consumed."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.tasks.mountaincar_family import (
    mountaincar_lookahead_confirmation,
    mountaincar_lookahead_development,
    mountaincar_physics_key,
)
from nexus.world import mountaincar_compute_matched as matched
from nexus.world import mountaincar_lookahead as base
from nexus.world import mountaincar_lookahead_confirm as confirm
from nexus.world import tree_reuse_lookahead as m
from nexus.world.planning import InferenceCounter, RandomShootingMPC
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.rewards import mountaincar_step_reward


class _Dummy:
    def step(self, obs, action):
        o=np.asarray(obs,dtype=np.float32)
        if o.ndim==1:
            o=o.reshape(1,-1)
        a=np.asarray(action).reshape(-1)
        nxt=o.copy()
        nxt[:,0]=o[:,0]+0.01*(a-1.0)
        return nxt, np.zeros(o.shape[0], dtype=np.float64)


def test_holdout_is_development_and_confirmation_stays_closed():
    cfg=m.load_config()
    hold=base.holdout_from_rule()
    assert hold==[(0.0035,0.0006,0.075),(0.0025,0.0013,0.07),(0.0015,0.0013,0.085)]
    specs=mountaincar_lookahead_development()
    assert [tuple(mountaincar_physics_key(s)) for s in specs]==hold
    closed={mountaincar_physics_key(s) for s in mountaincar_lookahead_confirmation()}
    assert closed.isdisjoint(set(hold))
    assert cfg['holdout_split_hash']==m.HOLD_SPLIT=='2a5cc4979642cc2a'
    assert cfg['closed_confirmation_split_hash']==confirm.HOLD_SPLIT=='bf4b4412f4f683dd'
    assert cfg['reset_base']==29000000 and cfg['step_seed_base']==29100000
    ours=set().union(*m.seed_groups(cfg))
    assert min(ours)>=29000000
    blocked={base.reset_seed(base.load_config(),s,t) for s in range(10) for t in range(3)}
    blocked|={base.reset_seed(confirm.load_config(),s,t) for s in range(10) for t in range(3)} # confirm uses base.reset_seed
    blocked|={matched.reset_seed(matched.load_config(),s,t) for s in range(10) for t in range(3)}
    assert ours.isdisjoint(blocked)


def test_budget_is_three_arms_at_256_259_and_771():
    counts=m.budget(m.load_config())
    assert counts['episode_max']==18000 and counts['model_states_max']==7716000
    assert counts['h16_imagined_per_step']==256
    assert counts['tree_reuse_imagined_per_step']==259
    assert counts['lookahead_imagined_per_step']==771
    assert counts['training_updates']==0
    assert 10*3*200*(256+259+771)==7716000


def test_one_run_allocation_is_consumed_and_output_exists():
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['fitted_critic'] is False
    assert record['retune_from_confirmation'] is False
    assert record['config_sha256']==sha(m.CONFIG)==m.LOCKED_CONFIG
    assert record['protocol_sha256']==sha(m.PROTOCOL)==m.LOCKED_PROTOCOL
    with pytest.raises(PermissionError, match='session allowance exhausted'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is True
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    assert float(usage['remaining_session_allowance_s'])==0.0
    assert int(usage['retries'])==0
    assert usage['raw_sha256']==sha(m.OUTPUT)
    assert usage['label']=='tree_reuse_lookahead_not_established'
    audit=m.audit_results()
    assert audit['audit_passed'] is True
    assert audit['label']=='tree_reuse_lookahead_not_established'


def test_primary_labels_require_the_25_point_episode_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='tree_reuse_lookahead_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='tree_reuse_lookahead_harm_established'
    assert m.classify_primary(12.8,3.8,21.9,10)=='tree_reuse_lookahead_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_frozen_checkpoints_and_no_fitted_critic():
    m.load_frozen_models(m.load_config())
    cfg=m.load_config()
    assert cfg['tree_reuse_control'] is True
    assert cfg['fitted_critic'] is False
    assert cfg['reuse_development_checkpoints'] is True
    assert cfg['training_updates']==0
    assert cfg['n_candidates']==16
    assert cfg['pendulum_weights'] is False and cfg['cartpole_h3'] is False
    assert cfg['mountaincar_continuous'] is False
    assert cfg['retune_from_confirmation'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest


def test_tree_reuse_counts_259_imagined_states_and_does_not_search_from_successor():
    counter=InferenceCounter(_Dummy())
    planner=RandomShootingMPC(model=counter,n_actions=3,horizon=16,n_candidates=16,seed=0,
                              objective='predicted_reward',step_reward=mountaincar_step_reward,
                              enforce_time_budget=False)
    seq=candidate_sequences(29100000,16,16,n_actions=3)
    calls={'score':0}
    original=planner._score_batch
    def _blocked(obs,seqs):
        calls['score']+=1
        return original(obs,seqs)
    planner._score_batch=_blocked
    action,q,dist=m.tree_reuse_first_action(planner,np.zeros(2,dtype=np.float32),seq)
    assert action in (0,1,2)
    assert len(q)==3
    assert counter.states==259
    assert calls['score']==0
    assert dist>=0.0
    look_counter=InferenceCounter(_Dummy())
    look_planner=RandomShootingMPC(model=look_counter,n_actions=3,horizon=16,n_candidates=16,seed=0,
                                   objective='predicted_reward',step_reward=mountaincar_step_reward,
                                   enforce_time_budget=False)
    base.lookahead_first_action(look_planner,np.zeros(2,dtype=np.float32),seq)
    assert look_counter.states==771


def test_prep_refuses_an_already_authorized_allocation():
    with pytest.raises(PermissionError, match='already authorized'):
        m.prep()
