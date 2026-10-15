"""Objective diagnosis correctness; toy results are not scientific evidence."""
import copy
import itertools
import math

import numpy as np
import pytest

from nexus.world.planning_value import (load_config,assert_seeds,suffix_seeds,finite_array,build_metrics,
    validate_and_summarize,ValueMeter,NAMES)
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.long_continuation import paired_interval, continuation_trace
from nexus.world.receding_horizon import rollout_actions,restore_state,true_state
from nexus.tasks.pendulum_family import pendulum_context_train
from nexus.tasks.spec import make_task_env
from test_receding_horizon import _Model


def test_fixed_budget_fresh_seeds_and_source_only_registry():
    cfg=load_config(); assert_seeds(cfg)
    assert cfg['env_cap']==8*128+8*16*16+10*8*16*48
    assert cfg['model_cap']==10*8*6*256+10*8*16*48*256
    assert cfg['tasks'][0][0]=='pendulum_ctx_tr0'
    cfg['env_seed_base']=1000200
    with pytest.raises(ValueError): assert_seeds(cfg)


def test_exact_short_objective_can_miss_long_value_without_model_error():
    seq=candidate_sequences(3)
    short=np.arange(16,dtype=float); long=-short
    scores={name:short.tolist() for name in NAMES}
    metrics,conditions=build_metrics(scores,short,long,seq)
    assert metrics['primary']==15
    assert metrics['zero_regret16']==0
    assert conditions['zero']['reward16_mae']==0
    assert metrics['student_minus_zero64']==0
    metrics,_=build_metrics(scores,short,short,seq)
    assert metrics['primary']==0


def test_real_restore_prefix_endpoint_and_common_continuation_context_lock():
    cfg=load_config(); env=make_task_env(pendulum_context_train()[0])
    env.reset(seed=44221); state=true_state(env);actions=candidate_sequences(44222)[0]
    first=rollout_actions(env,state,actions); endpoint=true_state(env)
    second=rollout_actions(env,state,actions)
    assert np.array_equal(first['rewards'],second['rewards'])
    assert np.array_equal(endpoint,true_state(env))
    obs=restore_state(env,endpoint)
    assert np.array_equal(obs,first['next_obs'][-1])
    model=_Model(); before=model.z.clone();rng=suffix_seeds(cfg,0)
    a=continuation_trace(env,model,endpoint,rng,horizon=48,original_phase=16)
    b=continuation_trace(env,model,endpoint,rng,horizon=48,original_phase=16)
    assert a==b and len(a['rewards'])==48
    assert (before==model.z).all()
    assert env.get_wrapper_attr('_elapsed_steps')==64
    assert [r['seed'] for r in a['decisions']]==rng
    assert sum(first['rewards'])+sum(a['rewards'])==pytest.approx(sum(list(first['rewards'])+a['rewards']))
    env.close()


@pytest.fixture
def grid():
    cfg=load_config()
    p=dict(prefixes=[],cells=[],frozen_checks=[],supports=[],wall_clock_s=1.,
        counts=dict(support=1024,prefix=2048,suffix=61440,model_states=cfg['model_cap']),
        checkpoint_before=dict(verified=120,missing=0,mismatched=0),checkpoint_after=dict(verified=120,missing=0,mismatched=0))
    for t in range(8):
        seq=candidate_sequences(cfg['candidate_seed_base']+t)
        prefixes=[dict(rewards=[float(i)]*16,next_obs=[[1.,0.,0.]]*16,endpoint=[0.,0.]) for i in range(16)]
        p['prefixes'].append(dict(task=t,state=[0.,0.],obs=[1.,0.,0.],sequences=seq.tolist(),rollouts=prefixes,
            env_seed=cfg['env_seed_base']+t,candidate_seed=cfg['candidate_seed_base']+t))
        p['supports'].append(dict(task=t,rows=128,sha256='a'*64))
    # Reuse immutable synthetic data; tests deep-copy before mutation.
    for d,t in itertools.product(range(10),range(8)):
        seq=p['prefixes'][t]['sequences']; scores={k:list(map(float,range(16))) for k in NAMES}
        traces=[]
        for i in range(16):
            rng=suffix_seeds(cfg,t)
            traces.append(dict(rewards=[-float(i)]*48,actions=[int(candidate_sequences(seed)[0,0]) for seed in rng],
                decisions=[dict(seed=seed,selected_index=0,predicted_score=0.,original_step=16+k,terminated=False,truncated=False) for k,seed in enumerate(rng)]))
        metrics,conditions=build_metrics(scores,np.arange(16)*16.,np.arange(16)*-32.,seq)
        p['cells'].append(dict(decoder=d,task=t,scores=scores,suffixes=traces,metrics=metrics,conditions=conditions))
        frozen={name:['hash','context'] for name in NAMES}
        p['frozen_checks'].append(dict(decoder=d,task=t,before=frozen,after=copy.deepcopy(frozen)))
    return p


def test_complete_grid_raw_reconstruction_and_decoder_unit(grid):
    r=validate_and_summarize(grid,load_config())
    assert r['label']=='short_objective_misses_practical_value'
    assert r['comparisons']['primary']['per_decoder']==[480.]*10
    assert r['comparisons']['primary']['interval']==dict(n=10,df=9,mean=480.,lo=480.,hi=480.)


@pytest.mark.parametrize('axis',['seed','task','condition','candidate','decision','metric','frozen','checkpoint'])
def test_missing_whole_axes_and_required_cells_fail(grid,axis):
    if axis=='seed': grid['cells']=[r for r in grid['cells'] if r['decoder']!=9]
    if axis=='task': grid['prefixes']=grid['prefixes'][:-1]
    if axis=='condition': del grid['cells'][0]['scores']['4']
    if axis=='candidate': grid['cells'][0]['suffixes'].pop()
    if axis=='decision': grid['cells'][0]['suffixes'][0]['decisions'].pop()
    if axis=='metric': del grid['cells'][0]['metrics']['primary']
    if axis=='frozen': del grid['frozen_checks'][0]['before']['zero']
    if axis=='checkpoint': del grid['checkpoint_after']
    with pytest.raises(ValueError): validate_and_summarize(grid,load_config())


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),True,'1'])
def test_numeric_coercion_or_nonfinite_rejected(grid,bad):
    grid['cells'][0]['scores']['zero'][0]=bad
    with pytest.raises(ValueError): validate_and_summarize(grid,load_config())


@pytest.mark.parametrize('change',['seed','action','reward','context'])
def test_unpaired_rng_reward_or_mutation_fails(grid,change):
    r=grid['cells'][0]
    if change=='seed': r['suffixes'][0]['decisions'][0]['seed']+=1
    if change=='action': r['suffixes'][0]['actions'][0]=(r['suffixes'][0]['actions'][0]+1)%3
    if change=='reward': r['suffixes'][0]['rewards'][0]+=1000
    if change=='context': grid['frozen_checks'][0]['after']['zero'][1]='changed'
    with pytest.raises(ValueError): validate_and_summarize(grid,load_config())


def test_ten_decoder_interval_and_hard_caps():
    values=list(range(10)); ci=paired_interval(values)
    assert ci['n']==10 and ci['df']==9
    assert ci['mean']==4.5
    assert ci['lo']==pytest.approx(4.5-2.262*np.std(values,ddof=1)/math.sqrt(10))
    with pytest.raises(ValueError): paired_interval(values[:-1])
    meter=ValueMeter(load_config());meter.deadline=0
    with pytest.raises(TimeoutError): meter.check()
