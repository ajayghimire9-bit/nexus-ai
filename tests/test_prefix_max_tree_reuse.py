"""Prefix-max tree-reuse protocol locks. The one-run allocation is consumed."""
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
from nexus.world import prefix_max_tree_reuse as m
from nexus.world import tree_reuse_lookahead as tree
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


def test_holdout_is_development_and_prior_seeds_stay_closed():
    cfg=m.load_config()
    hold=base.holdout_from_rule()
    specs=mountaincar_lookahead_development()
    assert [tuple(mountaincar_physics_key(s)) for s in specs]==hold
    closed={mountaincar_physics_key(s) for s in mountaincar_lookahead_confirmation()}
    assert closed.isdisjoint(set(hold))
    assert cfg['holdout_split_hash']==m.HOLD_SPLIT=='2a5cc4979642cc2a'
    assert cfg['reset_base']==30000000 and cfg['step_seed_base']==30100000
    ours=set().union(*m.seed_groups(cfg))
    assert min(ours)>=30000000
    blocked={base.reset_seed(base.load_config(),s,t) for s in range(10) for t in range(3)}
    blocked|={base.reset_seed(confirm.load_config(),s,t) for s in range(10) for t in range(3)}
    blocked|={matched.reset_seed(matched.load_config(),s,t) for s in range(10) for t in range(3)}
    blocked|={tree.reset_seed(tree.load_config(),s,t) for s in range(10) for t in range(3)}
    assert ours.isdisjoint(blocked)


def test_budget_is_two_arms_at_256_and_259():
    counts=m.budget(m.load_config())
    assert counts['episode_max']==12000 and counts['model_states_max']==3090000
    assert counts['h16_imagined_per_step']==256
    assert counts['prefix_max_imagined_per_step']==259
    assert counts['training_updates']==0
    assert 10*3*200*(256+259)==3090000


def test_one_run_allocation_is_consumed_and_output_exists():
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['fitted_critic'] is False
    assert record['lookahead_arm'] is False
    assert record['config_sha256']==sha(m.CONFIG)==m.LOCKED_CONFIG
    assert record['protocol_sha256']==sha(m.PROTOCOL)==m.LOCKED_PROTOCOL
    with pytest.raises(PermissionError, match='session allowance exhausted'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is True
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    assert float(usage['remaining_session_allowance_s'])==0.0
    assert int(usage['retries'])==0
    assert usage['raw_sha256']==sha(m.OUTPUT)
    assert usage['label']=='prefix_max_tree_reuse_not_established'
    audit=m.audit_results()
    assert audit['audit_passed'] is True
    assert audit['label']=='prefix_max_tree_reuse_not_established'


def test_primary_labels_require_the_25_point_episode_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='prefix_max_tree_reuse_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='prefix_max_tree_reuse_harm_established'
    assert m.classify_primary(-14.8,-37.1,7.6,10)=='prefix_max_tree_reuse_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_frozen_checkpoints_and_no_fitted_critic_or_lookahead_arm():
    m.load_frozen_models(m.load_config())
    cfg=m.load_config()
    assert cfg['prefix_max_control'] is True
    assert cfg['fitted_critic'] is False
    assert cfg['lookahead_arm'] is False
    assert cfg['n_candidates']==16
    assert cfg['retune_from_confirmation'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest


def test_prefix_max_counts_259_and_uses_max_matching_tail_not_score_batch():
    counter=InferenceCounter(_Dummy())
    planner=RandomShootingMPC(model=counter,n_actions=3,horizon=16,n_candidates=16,seed=0,
                              objective='predicted_reward',step_reward=mountaincar_step_reward,
                              enforce_time_budget=False)
    seq=np.zeros((16,16),dtype=np.int64)
    seq[:5,0]=0; seq[5:11,0]=1; seq[11:,0]=2
    seq[:,1:]=1
    calls={'score':0}
    original=planner._score_batch
    def _blocked(obs,seqs):
        calls['score']+=1
        return original(obs,seqs)
    planner._score_batch=_blocked
    action,q,hit=m.prefix_max_first_action(planner,np.zeros(2,dtype=np.float32),seq)
    assert action in (0,1,2)
    assert len(q)==3
    assert counter.states==259
    assert calls['score']==0
    assert hit==1.0
    first,remaining=m.prefix_values(seq, tree.unroll_open_loop_tree(planner,np.zeros(2,dtype=np.float32),seq)[2])
    for a in range(3):
        value,matched,n=m.prefix_max_value(first,remaining,np.zeros((16,2),dtype=np.float32),a,np.zeros(2))
        assert matched is True and n>0
        assert value==float(np.max(remaining[first==a]))


def test_missing_prefix_falls_back_to_nearest_t1_not_whole_tree():
    first=np.zeros(16,dtype=np.int64)
    remaining=np.linspace(-1.0,1.0,16)
    t1=np.stack([np.linspace(0,1,16),np.zeros(16)],axis=1).astype(np.float32)
    value,hit,n=m.prefix_max_value(first,remaining,t1,2,np.asarray([1.0,0.0],dtype=np.float32))
    assert hit is False and n==0
    assert value==float(remaining[-1])


def test_prep_refuses_an_already_authorized_allocation():
    with pytest.raises(PermissionError, match='already authorized'):
        m.prep()
