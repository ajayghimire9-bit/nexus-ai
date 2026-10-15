"""Factorial intervention tests; synthetic correctness is not research success."""
import copy
import itertools

import numpy as np
import pytest

from nexus.world.policy_switch import load_config,assert_seeds,seeds,switch_trace,contrasts,validate_and_summarize,SwitchMeter
from nexus.world.long_continuation import continuation_trace
from nexus.tasks.pendulum_family import pendulum_latent_confirmation
from nexus.tasks.spec import make_task_env
from nexus.world.receding_horizon import true_state
from test_receding_horizon import _Model


def test_registered_budget_and_seed_pairing():
    cfg=load_config();assert_seeds(cfg)
    assert 128+10*6*101+10*2*36*64==cfg['env_cap']
    assert (10*6*101+120+10*2*36*64)*256==cfg['model_cap']
    assert len({x for p in range(2) for s in range(6) for x in seeds(cfg,p,s)})==768
    cfg['env_seed']=600000
    with pytest.raises(ValueError): assert_seeds(cfg)


def test_switch_uses_correct_models_and_identical_prefix(monkeypatch):
    import nexus.world.policy_switch as module
    class Model:
        def __init__(self,tag): self.tag=tag
    class Env:
        def __init__(self): self.state=np.zeros(2); self.unwrapped=self
    calls=[]
    def fake(env,model,state,rng,**kw):
        env.state=np.array(state).copy(); rewards=[]
        for _ in rng:
            env.state[0]+=model.tag; rewards.append(float(env.state[0]))
        calls.append((model.tag,len(rng),kw['original_phase']))
        return {'rewards':rewards,'actions':[model.tag]*len(rng),'decisions':[{'seed':s} for s in rng]}
    monkeypatch.setattr(module,'continuation_trace',fake)
    env=Env();student=Model(1);zero=Model(0);rng=list(range(64))
    results={k:switch_trace(env,student,zero,np.zeros(2),rng,50,k) for k in ('SS','SZ','ZS','ZZ')}
    assert calls[:4]==[(1,16,50),(1,48,66),(1,16,50),(0,48,66)]
    assert results['SS']['middle_state']==results['SZ']['middle_state']==[16.,0.]
    assert contrasts(results)['suffix']>0
    results['SZ']['middle_state'][0]+=1
    with pytest.raises(ValueError): contrasts(results)


def test_split_restore_matches_uninterrupted_real_rollout():
    env=make_task_env(pendulum_latent_confirmation()[0]);env.reset(seed=99120)
    state=true_state(env);model=_Model();rng=list(range(1300000,1300064))
    ordinary=continuation_trace(env,model,state,rng,original_phase=50)
    split=switch_trace(env,model,model,state,rng,50,'SS')
    assert ordinary['rewards']==split['rewards']
    assert ordinary['actions']==split['actions']
    assert env.get_wrapper_attr('_elapsed_steps')==114
    env.close()


@pytest.fixture
def synthetic_grid():
    cfg=load_config()
    payload={'cells':[],'states':[],'frozen_checks':[],'episodes':[],'wall_clock_s':1.,
             'counts':{'support':128,'harvest':6060,'switch':46080,'model_states':13378560}}
    def trace(name,phase,rng):
        rewards=[0.]*16+([-1.]*48 if name=='SS' else [0.]*48)
        return dict(schedule=name,rewards=rewards,early=0.,late=sum(rewards),total=sum(rewards),
            middle_state=[0.,0.],actions=[1]*64,
            decisions=[dict(seed=s,original_step=phase+i,terminated=False,truncated=False) for i,s in enumerate(rng)])
    for d,p,slot in itertools.product(range(10),cfg['phases'],range(6)):
        rng=seeds(cfg,cfg['phases'].index(p),slot);students=range(5) if slot==5 else [slot]
        groups={'ZZ':trace('ZZ',p,rng)}
        for s in students:
            groups[str(s)]={k:trace(k,p,rng) for k in ('SS','SZ','ZS')}
            payload['cells'].append(dict(decoder=d,phase=p,visitor='zero' if slot==5 else 'student',student=s,
                suffix=-48.,inheritance=0.,overall=-48.,zero_prefix_suffix=0.,interaction=-48.))
        payload['states'].append(dict(decoder=d,phase=p,slot=slot,capture={'reproduced':True},restore_exact=True,traces=groups))
    names=['zero','0','1','2','3','4']
    payload['frozen_checks']=[dict(decoder=d,before={k:['hash','context'] for k in names},after={k:['hash','context'] for k in names}) for d in range(10)]
    payload['episodes']=[dict(decoder=d,slot=s,reset_seed=cfg['env_seed'],planner_seed=cfg['planner_seed'],stop_reason='diagnostic_cut',rewards=[0.]*101) for d,s in itertools.product(range(10),range(6))]
    return payload


def test_complete_factorial_grid_and_decision(synthetic_grid):
    result=validate_and_summarize(synthetic_grid,load_config())
    assert result['label']=='continued_student_suffix_worse'
    assert result['comparisons']['suffix']['per_decoder']==[-48.]*10
    synthetic_grid['states'][0]['traces']['0']['SZ']['rewards'][0]=1.
    with pytest.raises(ValueError):validate_and_summarize(synthetic_grid,load_config())


@pytest.mark.parametrize('axis,value',[('decoder',9),('phase',100),('visitor','zero'),('student',4)])
def test_removed_axes_fail_not_reduce_grid(synthetic_grid,axis,value):
    synthetic_grid['cells']=[r for r in synthetic_grid['cells'] if r[axis]!=value]
    with pytest.raises(ValueError):validate_and_summarize(synthetic_grid,load_config())


@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,'1'])
def test_invalid_metric_rejected(synthetic_grid,value):
    synthetic_grid['cells'][0]['suffix']=value
    with pytest.raises(ValueError):validate_and_summarize(synthetic_grid,load_config())


def test_caps_and_duplicate_cells_fail(synthetic_grid):
    cfg=load_config();meter=SwitchMeter(cfg);meter.deadline=0
    with pytest.raises(TimeoutError):meter.check()
    synthetic_grid['cells'].append(synthetic_grid['cells'][0])
    with pytest.raises(ValueError):validate_and_summarize(synthetic_grid,cfg)
