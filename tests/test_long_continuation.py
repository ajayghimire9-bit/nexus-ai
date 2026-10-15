"""Offline safeguards: no real environment is created and no MPC experiment runs."""
import copy
import itertools
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from nexus.world.long_continuation import (load_config,budget,assert_unused_seeds,
    proposed_seeds,require_budget_approval,split_rewards,paired_interval,audit_parent,continuation_trace)


def test_exact_budget_arithmetic():
    cfg=load_config(); b=budget(cfg)
    assert b['restored_states']==480 and b['paired_cells']==800
    assert b['env_steps']==198832
    assert b['model_states']==50851840
    assert sum(b['env_by_bucket'].values())==b['env_steps']
    assert b['runtime_estimate_s']<cfg['time_cap_s']==1800


def test_no_closed_or_overlapping_seed_streams():
    cfg=load_config(); assert_unused_seeds(cfg)
    groups=proposed_seeds(cfg)
    assert {k:len(v) for k,v in groups.items()}=={'env':4,'planner':4,'candidate':48,'common':3072,'policy':3072}
    cfg['env_seed_base']=500000
    with pytest.raises(ValueError): assert_unused_seeds(cfg)


def test_no_execution_without_explicit_matching_approval():
    for value in (None,'','arbitrary'):
        with pytest.raises(PermissionError): require_budget_approval(value)


def test_reward_windows_are_disjoint_complete_and_exact():
    rewards=list(range(64)); result=split_rewards(rewards)
    assert result['early']==sum(range(16))
    assert result['late']==sum(range(16,64))
    assert result['early']+result['late']==result['total']
    for bad in ([0.]*63,[0.]*63+[float('nan')],[0.]*63+[float('inf')]):
        with pytest.raises(ValueError): split_rewards(bad)


def test_decoder_interval_not_episode_replication():
    ci=paired_interval([float(x) for x in range(10)])
    assert ci['mean']==4.5 and ci['df']==9
    assert ci['hi']==pytest.approx(4.5+2.262*np.std(range(10),ddof=1)/np.sqrt(10))
    for bad in ([1.]*9,[1.]*50,[True]*10,['1']*10,[float('nan')]*10):
        with pytest.raises(ValueError): paired_interval(bad)


@pytest.fixture(scope='module')
def parent():
    return json.loads(Path('artifacts/late_control_gap.json').read_text())


def test_independent_raw_to_decoder_recomputation(parent):
    audit=audit_parent(parent)
    assert audit['raw_comparisons']==1600
    assert audit['primary_recomputed']['mean']==pytest.approx(.031243175230177368)


@pytest.mark.parametrize('field,value',[('decoder',9),('task',3),('phase',150),('slot',5)])
def test_removed_raw_grid_cannot_reduce_expected_grid(parent,field,value):
    p=dict(parent); p['states']=[r for r in parent['states'] if r[field]!=value]
    with pytest.raises(ValueError): audit_parent(p)


def test_saved_summary_cannot_override_raw_data(parent):
    p=copy.deepcopy(parent); p['cells'][0]['primary']+=10
    with pytest.raises(ValueError): audit_parent(p)


def test_future_rollout_uses_shared_rng_and_records_all_rewards(monkeypatch):
    import nexus.world.planning as planning
    import nexus.world.receding_horizon as prior
    class Model:
        z=torch.zeros(8)
        def context_dim(self): return 8
    class Env:
        def step(self,action):
            self.state+=action-1
            return np.array([self.state]),float(self.state),False,False,{}
    class Planner:
        def reset_episode(self,seed): self.seed=seed
        def act(self,obs):
            calls.append(self.seed)
            return self.seed%3,{'n_scored':16}
    def restore(env,state): env.state=float(state[0]); return np.array(state)
    calls=[]
    monkeypatch.setattr(planning,'mpc_for_model',lambda *a,**kw:Planner())
    monkeypatch.setattr(prior,'restore_state',restore)
    monkeypatch.setattr(prior,'_reward_ok',lambda prev,action,nxt,reward:None)
    model=Model(); seeds=list(range(750000,750064)); traces=[]
    for first in range(3):
        calls.clear()
        result=continuation_trace(Env(),model,np.array([0.]),seeds,first_action=first)
        assert len(result['rewards'])==64 and len(result['actions'])==64
        assert result['total']==sum(result['rewards'])
        assert result['early']+result['late']==result['total']
        traces.append(calls.copy())
    assert traces[0]==traces[1]==traces[2]==seeds[1:]
    assert torch.equal(model.z,torch.zeros(8))
    with pytest.raises(ValueError): continuation_trace(Env(),model,[0.],seeds[:16])


def test_preparation_cannot_create_environment(monkeypatch):
    import nexus.tasks.spec as tasks
    from nexus.world.long_continuation import prepare
    def blocked(*args,**kwargs): raise AssertionError('real environment must not be created')
    monkeypatch.setattr(tasks,'make_task_env',blocked)
    result=prepare()
    assert result['simulation_executed'] is False
    assert result['parent_audit']['audit_passed']


def test_duplicate_harvest_cannot_pass_audit(parent):
    p=copy.deepcopy(parent); p['episodes'][-1]=p['episodes'][0]
    with pytest.raises(ValueError): audit_parent(p)
