"""Real simulator integration and execution gates; no diagnostic task scoring."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from nexus.tasks.pendulum_family import pendulum_latent_confirmation
from nexus.tasks.spec import make_task_env
from nexus.world.long_continuation import continuation_trace, load_config
from nexus.world.long_continuation_execution import (ExecutionMeter, restore_at_phase,
    execute, validate_execution, context_hash)
from nexus.world.receding_horizon import true_state
from test_receding_horizon import _Model


def test_exact_restore_with_original_episode_clock():
    env=make_task_env(pendulum_latent_confirmation()[0])
    obs,_=env.reset(seed=99117); state=true_state(env)
    assert np.array_equal(restore_at_phase(env,state,100),obs)
    for _ in range(63): env.step(1)
    assert env.get_wrapper_attr("_elapsed_steps")==163
    assert np.array_equal(restore_at_phase(env,state,100),obs)
    assert env.get_wrapper_attr("_elapsed_steps")==100
    env.close()


def test_real_64_step_continuation_reward_rng_context_and_boundary():
    env=make_task_env(pendulum_latent_confirmation()[0]); env.reset(seed=99118)
    model=_Model(); state=true_state(env); before=model.z.clone()
    seeds=list(range(910000,910064))
    a=continuation_trace(env,model,state,seeds,original_phase=100)
    b=continuation_trace(env,model,state,seeds,original_phase=100)
    assert a==b
    assert len(a['rewards'])==64 and len(a['decisions'])==64
    assert env.get_wrapper_attr("_elapsed_steps")==164
    assert a['early']+a['late']==pytest.approx(a['total'])
    assert torch.equal(before,model.z)
    with pytest.raises(ValueError): continuation_trace(env,model,state,seeds,original_phase=150)
    env.close()


def test_common_policy_stream_is_action_independent_on_real_env():
    env=make_task_env(pendulum_latent_confirmation()[0]); env.reset(seed=99119)
    state=true_state(env); model=_Model(); seeds=list(range(920000,920064))
    traces=[continuation_trace(env,model,state,seeds,first_action=a,original_phase=50) for a in range(3)]
    assert all([r['seed'] for r in t['decisions'][1:]]==seeds[1:] for t in traces)
    model.z=torch.ones(8)
    with pytest.raises(ValueError): continuation_trace(env,model,state,seeds,first_action=0,original_phase=50)
    env.close()


def test_deadline_and_interaction_caps_are_hard():
    cfg=load_config(); meter=ExecutionMeter(cfg)
    meter.deadline=0
    with pytest.raises(TimeoutError): meter.check()
    meter=ExecutionMeter(cfg); meter.counts['support']=meter.env_cap
    class Env:
        def step(self,a): raise AssertionError('must fail before stepping')
    env=Env(); meter.instrument_env(env)
    with pytest.raises(RuntimeError): env.step(1)


def test_execution_blocked_before_model_loading_without_budget_lock(monkeypatch,tmp_path):
    import nexus.world.long_continuation_execution as runner
    monkeypatch.setattr(runner,'OUTPUT',tmp_path/'out.json')
    with pytest.raises(PermissionError): execute(None)
    assert not (tmp_path/'out.json').exists()


def test_incomplete_execution_cannot_be_called_valid():
    with pytest.raises(ValueError): validate_execution({'cells':[],'states':[]},load_config())


def test_context_hash_detects_mutation():
    model=_Model(); before=context_hash(model)
    model.z[0]=1
    assert before!=context_hash(model)


def test_complete_execution_validator_reconstructs_traces_and_rejects_corruption():
    import itertools
    from nexus.world.long_continuation import state_seed,budget
    from nexus.world.prediction_control_gap import candidate_sequences
    cfg=load_config()
    def trace(phase,seeds,first=None):
        actions=[1]*64
        if first is not None: actions[0]=first
        return dict(rewards=[0.]*64,actions=actions,early=0.,late=0.,total=0.,
            decisions=[dict(seed=seed,selected_index=None if k==0 and first is not None else 0,
                            predicted_score=None if k==0 and first is not None else 0.,
                            original_step=phase+k,terminated=False,truncated=False) for k,seed in enumerate(seeds)])
    payload={'cells':[],'states':[],'episodes':[],'frozen_checks':[],'wall_clock_s':1.,
             'counts':{**budget(cfg)['env_by_bucket'],'model_states':budget(cfg)['model_states']}}
    for d,t,phase,slot in itertools.product(range(10),range(4),cfg['phases'],range(6)):
        pi=cfg['phases'].index(phase); seed=state_seed(cfg,'candidate',t,pi,slot)
        sequences=candidate_sequences(seed,16,16,3)
        students=range(5) if slot==5 else [slot]
        names=[str(s) for s in students]+['zero']
        seeds=[state_seed(cfg,'policy',t,pi,slot)+k for k in range(64)]
        full_trace=trace(phase,seeds)
        common_seeds=[state_seed(cfg,'common',t,pi,slot)+k for k in range(64)]
        payload['states'].append(dict(decoder=d,task=t,phase=phase,slot=slot,capture={'reproduced':True},
            restore_exact=True,candidate_seed=seed,sequences=sequences,
            selected={name:dict(scores=[0.]*16,index=0,action=int(sequences[0,0])) for name in names},
            full={name:full_trace for name in names},common=[trace(phase,common_seeds,a) for a in range(3)]))
        for s in students:
            payload['cells'].append(dict(decoder=d,task=t,phase=phase,visitor='zero' if slot==5 else 'student',student=s,
                **{f'{p}_{w}':0. for p in ('full','common') for w in ('early','late','total')}))
    payload['episodes']=[dict(decoder=d,task=t,slot=s,rewards=[0.]*101,stop_reason='diagnostic_cut',
                             reset_seed=cfg['env_seed_base']+t*100,planner_seed=cfg['planner_seed_base']+t*100)
                         for d,t,s in itertools.product(range(10),range(4),range(6))]
    payload['frozen_checks']=[dict(decoder=d,task=t,before={k:'x' for k in ['zero','0','1','2','3','4']},after={k:'x' for k in ['zero','0','1','2','3','4']},
                                    contexts_before={k:'z' for k in ['zero','0','1','2','3','4']},contexts_after={k:'z' for k in ['zero','0','1','2','3','4']})
                              for d,t in itertools.product(range(10),range(4))]
    assert validate_execution(payload,cfg)['paired_cells']==800
    first=payload['states'][0]
    first['common'][0]['rewards'][0]=1.
    with pytest.raises(ValueError): validate_execution(payload,cfg)
    first['common'][0]['rewards'][0]=0.
    first['full']['zero']['decisions'][0]['seed']+=1
    with pytest.raises(ValueError): validate_execution(payload,cfg)
