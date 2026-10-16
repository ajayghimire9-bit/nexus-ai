"""Unit fixtures and synthetic full grids; no registered commitment data collected."""
import copy
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pytest
import torch
from nexus.world import commitment_value as module
from nexus.world.terminal_value import NAMES,TerminalReadout
from nexus.world.prediction_control_gap import candidate_sequences


def sample_scores():
    seq=candidate_sequences(9700001);seq[0,0]=0;seq[1,0]=2
    scores={name:dict(base=[10.]+[0.]*15,corrected=[0.,10.]+[0.]*14) for name in NAMES}
    return scores,seq


def test_paired_interaction_uses_same_actual_counterfactuals_and_endpoints():
    scores,seq=sample_scores();first=[1.,5.,3.];blocks=[10.,20.]+[0.]*14
    fo=np.zeros((3,3));bo=np.zeros((16,3));bo[0]=[0,0,2];bo[1]=[0,0,-2]
    m=module.contrasts(scores,seq,first,blocks,fo.tolist(),bo.tolist())['0']
    assert (m['gain1'],m['gain16'],m['interaction'])==(2.,10.,8.)
    assert m['block_regret_base']-m['block_regret_value']==m['gain16']
    assert m['end_obs_distance_base']==m['end_obs_distance_value']==2.
    # Norms are computed before averaging; opposite endpoint differences cannot
    # cancel as they would in a distance between mean observations.
    assert np.linalg.norm((bo[0]+bo[1])/2)==0


def fake_rows(gain1=0.,gain16=5.):
    metrics={name:{k:0. for k in module.METRICS} for name in NAMES}
    for m in metrics.values():m.update(gain1=gain1,gain16=gain16,interaction=gain16-gain1)
    return [dict(decoder=d,task=t,state=j,metrics=copy.deepcopy(metrics)) for d,t,j in itertools.product(range(10),range(3),range(2))]


def test_decoder_aggregation_and_conjunctive_gain_label():
    cfg=module.load_config();result=module.summarize(fake_rows(),cfg)
    assert result['comparisons']['interaction']['interval']['n']==10
    assert result['comparisons']['interaction']['interval']['mean']==5
    assert result['label']=='commitment_sensitive_gain'
    result=module.summarize(fake_rows(-4.,-2.),cfg)
    assert result['label']=='relative_commitment_sensitivity_without_established_gain'
    assert module.summarize(fake_rows(5.,5.),cfg)['label']=='commitment_interaction_not_established'


def test_component_significance_does_not_establish_interaction():
    cfg=module.load_config();rows=fake_rows()
    for r in rows:
        g1=float(r['decoder']-4.5);g16=3.-g1
        for m in r['metrics'].values():m.update(gain1=g1,gain16=g16,interaction=g16-g1)
    result=module.summarize(rows,cfg)
    # Directly verify the interval comes from paired differences, not subtraction
    # of independently computed bounds or whether one component is significant.
    values=result['comparisons']['interaction']['per_decoder']
    from nexus.world.long_continuation import paired_interval
    assert result['comparisons']['interaction']['interval']==paired_interval(values)
    assert result['comparisons']['gain16']['interval']['lo']>0
    assert result['comparisons']['gain1']['interval']['lo']<0<result['comparisons']['gain1']['interval']['hi']
    assert result['comparisons']['interaction']['interval']['lo']<0
    assert result['label']=='commitment_interaction_not_established'


def test_students_and_states_are_equal_weight_inside_decoders():
    cfg=module.load_config();rows=fake_rows(0.,0.)
    rows[0]['metrics']['0'].update(gain16=30.,interaction=30.)
    result=module.summarize(rows,cfg)
    assert result['comparisons']['interaction']['per_decoder']==[1.]+[0.]*9
    assert result['zero_context']['interaction']['interval']['mean']==0.


@pytest.mark.parametrize('axis,value',[('decoder',9),('task',2),('state',1)])
def test_missing_full_axis_rejected(axis,value):
    with pytest.raises(ValueError):module.summarize([r for r in fake_rows() if r[axis]!=value],module.load_config())


@pytest.mark.parametrize('bad',[True,'1',float('nan'),float('inf')])
def test_invalid_metric_types_rejected(bad):
    rows=fake_rows();rows[0]['metrics']['0']['gain1']=bad
    with pytest.raises(ValueError):module.summarize(rows,module.load_config())


def test_budgets_and_action_independent_future_seed_streams():
    cfg=module.load_config();module.check_seeds(cfg)
    assert module.budget(cfg)==dict(prefix=1536,block_tail=46080,first_common=11520,model_states=14883840)
    assert len(module.future_seeds(cfg,2,1))==64
    assert module.future_seeds(cfg,0,0)[16:]==list(range(cfg['continuation_base']+16,cfg['continuation_base']+64))
    with pytest.raises(TypeError):module.future_seeds(cfg,0,0,action=2)
    for key,val in [('state_base',2050000),('state_base',2200000),('candidate_base',2210000),('continuation_base',2220000)]:
        bad=copy.deepcopy(cfg);bad[key]=val
        with pytest.raises(ValueError):module.check_seeds(bad)


def test_read_only_preparation_and_rejected_approval_cannot_reach_environment(monkeypatch,tmp_path):
    from nexus.tasks import spec
    def forbidden(*a,**kw):raise AssertionError('research environment must not be constructed')
    monkeypatch.setattr(spec,'make_task_env',forbidden);monkeypatch.setattr(TerminalReadout,'fit',forbidden)
    monkeypatch.setattr(module,'APPROVAL',tmp_path/'absent.json')
    for value in (None,'old_hash',module.LOCK):
        with pytest.raises(PermissionError):module.execute(value)
    ready=module.prepare();assert ready['new_environment_steps']==ready['new_support_steps']==ready['readout_fits']==0


def test_stale_or_wrong_budget_approval_fails(monkeypatch,tmp_path):
    path=tmp_path/'approval.json';monkeypatch.setattr(module,'APPROVAL',path)
    path.write_text(json.dumps(dict(kind='human_approved_bounded_local_experiment',config_sha256=module.LOCK,time_cap_s=900,env_cap=59137,model_cap=14883840,runs=1,further_experiments_authorized=False)))
    with pytest.raises(PermissionError):module.require_approval(module.LOCK,module.load_config())


def test_explicit_checkpoint_audit_fails_on_missing_file(monkeypatch):
    import nexus.world.checkpoint_integrity as checks
    def missing():raise FileNotFoundError('required .pt missing')
    monkeypatch.setattr(checks,'verify_checkpoint_integrity',missing)
    with pytest.raises(FileNotFoundError):module.verify_inputs()


def test_compensated_float_accounting_and_hard_caps():
    assert module.total([1e16,1.,-1e16],3)==1.
    cfg=module.load_config();meter=module.CommitmentMeter(cfg);meter.deadline=0
    with pytest.raises(TimeoutError):meter.check()
    from test_receding_horizon import _Model
    meter=module.CommitmentMeter(cfg);meter.model_cap=0;m=_Model();meter.instrument_model(m)
    with pytest.raises(RuntimeError):m.step(np.array([[1.,0.,0.]]),np.array([1]))


def test_state_restore_reward_timing_and_context_locked_continuation():
    # Unit-only seeds/states: no registered initial state or trained checkpoint.
    from nexus.tasks.spec import make_task_env
    from nexus.tasks.pendulum_family import pendulum_context_development
    from test_receding_horizon import _Model
    env=make_task_env(pendulum_context_development()[0]);env.reset(seed=9700010)
    state=np.array([.3,-.2]);seq=np.array([0,1,2,1]*4,dtype=np.int64)
    try:
        a=module.execute_prefix(env,state,seq);b=module.execute_prefix(env,state,seq)
        from nexus.world.receding_horizon import _walk_wrappers
        assert a==b
        assert [w._elapsed_steps for w in _walk_wrappers(env) if '_elapsed_steps' in vars(w)]==[16]
        model=_Model();before=model.z.clone();seeds=list(range(9700020,9700024))
        first=module.continue_locked(env,model,state,seeds,first_action=0)
        replay=module.continue_locked(env,model,state,seeds,first_action=0)
        assert first==replay and torch.equal(before,model.z)
        assert [r['seed'] for r in first['decisions']]==seeds
        assert first['actions'][0]==0 and len(first['rewards'])==4
        # Starting a suffix at16 preserves original clocks and fixed context.
        tail=module.continue_locked(env,model,a['endpoint'],seeds,phase=16)
        assert [r['original_step'] for r in tail['decisions']]==list(range(16,20))
        assert torch.equal(before,model.z)
    finally:env.close()


@pytest.fixture(scope='module')
def master_capture():
    cfg=module.load_config();parent,stage=module.parent_evidence()
    checks=dict(verified=120,missing=0,mismatched=0)
    p=dict(prefixes=[],cells=[],config_sha256=module.LOCK,protocol_sha256=module.sha(module.PROTOCOL),parents=cfg['parents'],
        counts=module.budget(cfg),wall_clock_s=1.,checkpoint_before=checks,checkpoint_after=checks,source_dirty=False,
        implementation_sha=cfg['starting_sha'],approval_sha256='a'*64,input_verification=dict(checkpoints=checks,model_context_groups=30,readouts=10,new_environment_steps=0))
    cost=lambda a: -.004 if a!=1 else 0.
    for t,j in itertools.product(range(3),range(2)):
        seq=candidate_sequences(module.candidate_seed(cfg,t,j));prefixes=[]
        for actions in seq:
            prefixes.append(dict(actions=actions.tolist(),rewards=[cost(a) for a in actions],next_obs=[[1.,0.,0.]]*16,
                terminated=[False]*16,truncated=[False]*16,endpoint=[0.,0.]))
        p['prefixes'].append(dict(task=t,state=j,reset_seed=module.state_seed(cfg,t,j),restore_exact=True,true_state=[0.,0.],obs=[1.,0.,0.],sequences=seq.tolist(),rollouts=prefixes))
    traces={}
    for t,j in itertools.product(range(3),range(2)):
        seeds=module.future_seeds(cfg,t,j)
        def trace(rng,phase,forced=None):
            actions=[];decisions=[]
            for k,seed in enumerate(rng):
                is_forced=k==0 and forced is not None
                actions.append(forced if is_forced else int(candidate_sequences(seed)[0,0]))
                decisions.append(dict(seed=seed,selected_index=None if is_forced else 0,predicted_score=None if is_forced else 0.,
                    original_step=phase+k,terminated=False,truncated=False))
            return dict(actions=actions,decisions=decisions,rewards=[cost(a) for a in actions],endpoint=[0.,0.],endpoint_obs=[1.,0.,0.])
        traces[t,j]=dict(first=[trace(seeds,0,a) for a in range(3)],tail=trace(seeds[16:],16))
    prefix_index={(r['task'],r['state']):r for r in p['prefixes']}
    for d,t,j in itertools.product(range(10),range(3),range(2)):
        contexts,before=module.saved_contexts(parent,stage,d,t+8);readout=TerminalReadout(**stage['readouts'][str(d)]['state']);scores={}
        for name in NAMES:
            x=np.column_stack([np.tile([1.,0.,0.],(16,1)),np.tile(contexts[name],(16,1))]);values=readout.predict(x);base=np.arange(16,dtype=float)
            scores[name]=dict(base=base.tolist(),corrected=(base+values).tolist(),survival=[1.]*16,terminal=values.tolist(),inputs=x.tolist(),endpoint=[[1.,0.,0.]]*16)
        first=copy.deepcopy(traces[t,j]['first']);tails=[copy.deepcopy(traces[t,j]['tail']) for _ in range(16)];prefix=prefix_index[t,j]
        fr=[module.total(tr['rewards'],64) for tr in first];br=[module.total(pre['rewards'],16)+module.total(tail['rewards'],48) for pre,tail in zip(prefix['rollouts'],tails)]
        p['cells'].append(dict(decoder=d,task=t,state=j,before=before,after=copy.deepcopy(before),readout_sha256=readout.digest(),scores=scores,first_traces=first,block_tails=tails,
            metrics=module.contrasts(scores,prefix['sequences'],fr,br,[tr['endpoint_obs'] for tr in first],[tr['endpoint_obs'] for tr in tails])))
    return p,cfg,parent,stage


@pytest.fixture
def capture(master_capture):
    p,cfg,parent,stage=master_capture
    return copy.deepcopy(p),cfg,parent,stage


def test_synthetic_complete_raw_grid_validates_without_registered_simulation(capture):
    p,cfg,parent,stage=capture;result=module.validate(p,cfg,parent,stage)
    assert result['label']=='commitment_interaction_not_established'
    assert result['comparisons']['interaction']['interval']['n']==10
    assert result['comparisons']['interaction']['interval']['mean']==0


@pytest.mark.parametrize('corruption',['seed','task','state','prefix','context','arm','tail','rng','clock','reward','score','frozen','count','boolean_flag','boolean_metric','input_audit','approval'])
def test_full_capture_corruptions_fail(capture,corruption):
    p,cfg,parent,stage=capture;r=p['cells'][0]
    if corruption=='seed':p['cells']=[r for r in p['cells'] if r['decoder']!=9]
    if corruption=='task':p['cells']=[r for r in p['cells'] if r['task']!=2]
    if corruption=='state':p['cells']=[r for r in p['cells'] if r['state']!=1]
    if corruption=='prefix':p['prefixes'].pop()
    if corruption=='context':del r['scores']['4']
    if corruption=='arm':r['first_traces'].pop()
    if corruption=='tail':r['block_tails'].pop()
    if corruption=='rng':r['first_traces'][0]['decisions'][1]['seed']+=1
    if corruption=='clock':r['block_tails'][0]['decisions'][0]['original_step']=0
    if corruption=='reward':p['prefixes'][0]['rollouts'][0]['rewards'][0]+=1
    if corruption=='score':r['scores']['zero']['corrected'][0]+=1
    if corruption=='frozen':r['after']['zero'][0]='b'*64
    if corruption=='count':p['counts']['first_common']+=64
    if corruption=='boolean_flag':p['prefixes'][0]['rollouts'][0]['terminated'][0]=0
    if corruption=='boolean_metric':r['metrics']['zero']['gain1']=False
    if corruption=='input_audit':del p['input_verification']
    if corruption=='approval':del p['approval_sha256']
    with pytest.raises((ValueError,KeyError,RuntimeError)):module.validate(p,cfg,parent,stage)


def test_unforced_suffix_cannot_use_student_context_instead_of_zero():
    from test_receding_horizon import _Model
    model=_Model();model.z=torch.ones(8)
    # Reject before touching an environment, for full tails as well as first actions.
    for kwargs in ({'phase':16},{'first_action':0}):
        with pytest.raises(ValueError,match='zero-context continuation'):
            module.continue_locked(None,model,[0.,0.],[9700030,9700031],**kwargs)


def test_meter_counts_unique_executed_steps_and_batch_elements():
    class CounterEnv:
        calls=0
        def step(self,action):self.calls+=1;return None
    meter=module.CommitmentMeter(module.load_config());env=CounterEnv();meter.env_cap=2;meter.instrument_env(env)
    env.step(1);env.step(1)
    with pytest.raises(RuntimeError):env.step(1)
    assert env.calls==2 and meter.counts['prefix']==2
    from test_receding_horizon import _Model
    model=_Model();meter.model_cap=3;meter.instrument_model(model)
    model.step(np.array([[1.,0.,0.]]),np.array([0,1,2]))
    with pytest.raises(RuntimeError):model.step(np.array([[1.,0.,0.]]),np.array([1]))
    assert meter.counts['model_states']==3 and len(model.seen)==1
