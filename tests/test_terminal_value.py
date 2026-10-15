"""Synthetic and unit integration checks; no registered research episodes are run."""
import copy
import itertools
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from nexus.world.terminal_value import (TerminalReadout,polynomial_features,predicted_endpoints,score_conditions,
    load_config,budget,prepare,assert_seeds,continuation_seeds,summarize,row_metrics,NAMES,support_hash)
from nexus.world.terminal_value_execution import (execute,require_fit_stage,validate_fit,checked_id_grid,TerminalMeter)
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.receding_horizon import chunked_scores
from test_receding_horizon import _Model


def test_budget_source_development_disjoint_and_closed_seed_guard():
    cfg=load_config();assert_seeds(cfg)
    b=budget(cfg)
    assert sum(v for k,v in b.items() if k!='model_states')==28800
    assert b['model_states']==7050240
    assert not set(map(tuple,cfg['train_physics'])) & set(map(tuple,cfg['eval_physics']))
    cfg['train_state_base']=1200000
    with pytest.raises(ValueError):assert_seeds(cfg)


def test_preparation_and_rejected_approval_cannot_create_environment(monkeypatch):
    import nexus.world.terminal_value_execution as module
    def forbidden(*a,**kw):raise AssertionError('collection must not be reached')
    monkeypatch.setattr(module,'make_task_env',forbidden)
    monkeypatch.setattr(module,'collect_support',forbidden)
    for approval in (None,'stale_hash'):
        with pytest.raises(PermissionError):execute(approval)
    p=prepare()
    assert p['new_environment_steps']==0
    assert p['env_steps']==28800
    assert p['readout_coefficients']==780


def test_source_ridge_fits_informative_task_and_reproduces():
    rng=np.random.default_rng(331);x=np.zeros((128,11));x[:,0]=rng.uniform(-2,2,128)
    y=3*x[:,0]**2-2*x[:,0]-5
    a=TerminalReadout.fit(x,y);b=TerminalReadout.fit(x,y)
    query=np.zeros((40,11));query[:,0]=np.linspace(-1.9,1.9,40)
    actual=3*query[:,0]**2-2*query[:,0]-5
    err=np.mean((a.predict(query)-actual)**2)
    constant=np.mean((np.mean(y)-actual)**2)
    assert err<constant*.4
    assert a.digest()==b.digest()
    saved=json.loads(json.dumps(a.state_dict()))
    restored=TerminalReadout(**saved)
    assert np.array_equal(a.predict(query),restored.predict(query))
    assert len(a.weights)==78 and polynomial_features(x).shape==(128,77)


def test_prediction_does_not_refit_source_normalization_or_use_query_labels():
    rng=np.random.default_rng(41);source=rng.normal(size=(64,11));targets=source[:,0]-4
    readout=TerminalReadout.fit(source,targets);before=readout.digest()
    query=rng.normal(30,2,(16,11));readout.predict(query)
    # Query labels are not accepted by fit or predict through any hidden state.
    query_outcomes=np.full(16,1e8);query_outcomes*=-1
    assert readout.digest()==before
    assert TerminalReadout.fit(source,targets).digest()==before
    with pytest.raises(TypeError):readout.predict(query,query_outcomes)


def test_raw_endpoint_projection_and_survival_keep_context_unchanged():
    class Integrator(_Model):
        def step(self,obs,action):
            state=np.asarray(obs,dtype=np.float32).copy();state[:,2]+=np.asarray(action)-1
            return state,np.full(len(state),.1)
    m=Integrator();m.z=torch.arange(8,dtype=torch.float32);before=m.z.clone()
    seq=candidate_sequences(531)
    endpoint,alive=predicted_endpoints(m,np.array([1.,0.,0.]),seq)
    assert np.array_equal(endpoint[:,2],np.sum(seq-1,axis=1))
    assert np.allclose(alive,.9**16)
    assert torch.equal(m.z,before)


def test_score_constant_shift_preserves_candidate_and_base_logic():
    model=_Model();seq=candidate_sequences(730)
    readout=TerminalReadout(np.zeros(77).tolist(),np.ones(77).tolist(),[7.]+[0.]*77)
    before=model.z.clone();scored=score_conditions(model,np.array([1.,0.,0.]),seq,readout)
    base=chunked_scores(model,np.array([1.,0.,0.]),seq)
    assert np.array_equal(base,scored['base'])
    assert np.allclose(scored['corrected'],base+7)
    assert np.argmax(scored['corrected'])==np.argmax(base)
    assert torch.equal(before,model.z)
    assert len(scored['base'])==len(scored['corrected'])==16


def test_context_mutation_during_rollout_is_rejected():
    class Bad(_Model):
        def step(self,obs,action):
            self.z+=1
            return super().step(obs,action)
    with pytest.raises(RuntimeError):predicted_endpoints(Bad(),np.array([1.,0.,0.]),candidate_sequences(55))


def test_action_pairing_uses_same_actual_counterfactuals():
    seq=candidate_sequences(92)
    for a in range(3):seq[a,0]=a
    scored={name:dict(base=[0.]*16,corrected=[0.]*16) for name in NAMES}
    for name in NAMES:
        scored[name]['base'][0]=5
        scored[name]['corrected'][2]=5
    result=row_metrics(scored,[1.,10.,40.],seq)
    assert result['primary']==39.
    assert result['student_value_vs_zero']==39.
    assert result['zero_value_vs_zero']==39.
    assert result['student_value_vs_zero_value']==0.


def test_action_independent_rng_and_forced_first_action_contract(monkeypatch):
    cfg=load_config()
    assert continuation_seeds(cfg,'evaluation',0,0)!=continuation_seeds(cfg,'evaluation',0,1)
    assert len(continuation_seeds(cfg,'evaluation',0))==64
    # No action argument can silently select a different random stream.
    with pytest.raises(TypeError):continuation_seeds(cfg,'evaluation',0,action=2)
    from nexus.world.long_continuation import continuation_trace
    from nexus.tasks.spec import make_task_env
    from nexus.tasks.pendulum_family import pendulum_context_train
    from nexus.world.receding_horizon import true_state
    env=make_task_env(pendulum_context_train()[0]);env.reset(seed=49921)
    state=true_state(env);model=_Model();rng=list(range(49930,49934))
    # Unit fixture only: short replay, not any registered training/evaluation seed.
    a=continuation_trace(env,model,state,rng,first_action=2,horizon=4)
    b=continuation_trace(env,model,state,rng,first_action=2,horizon=4)
    assert a==b and a['actions'][0]==2
    assert [d['seed'] for d in a['decisions']]==rng
    env.close()


def test_full_support_hash_covers_outcomes_flags_metadata():
    class Support:
        obs=np.zeros((128,3),dtype=np.float32);next_obs=np.ones((128,3),dtype=np.float32)
        action=np.zeros(128,dtype=np.int64);reward=np.zeros(128,dtype=np.float32)
        terminated=np.zeros(128,dtype=bool);truncated=np.zeros(128,dtype=bool)
        seed=np.full(128,99,dtype=np.int64);episode_id=np.zeros(128,dtype=np.int64)
    ds=Support();old=support_hash(ds)
    assert len(old)==64
    ds.next_obs=ds.next_obs.copy();ds.next_obs[0,0]=4
    assert support_hash(ds)!=old
    new=support_hash(ds);ds.terminated=ds.terminated.copy();ds.terminated[0]=True
    assert support_hash(ds)!=new


def fake_rows():
    return [dict(decoder=d,task=t,state=j,metrics=dict(primary=float(d),student_value_vs_zero=0.,zero_value_vs_zero=0.,
        student_value_vs_zero_value=0.,corrected_student_regret=0.,student_regret=0.)) for d,t,j in itertools.product(range(10),range(3),range(2))]


def test_decoder_unit_is_not_student_or_episode_count():
    result=summarize(fake_rows(),load_config())
    assert result['comparisons']['primary']['per_decoder']==list(map(float,range(10)))
    assert result['comparisons']['primary']['interval']['n']==10
    assert result['label']=='local_first_action_gain'


@pytest.mark.parametrize('axis,value',[('decoder',9),('task',2),('state',1)])
def test_missing_full_axes_fail(axis,value):
    rows=[r for r in fake_rows() if r[axis]!=value]
    with pytest.raises(ValueError):summarize(rows,load_config())


@pytest.mark.parametrize('bad',[True,'1',float('nan'),float('inf')])
def test_invalid_metric_types_rejected(bad):
    rows=fake_rows();rows[0]['metrics']['primary']=bad
    with pytest.raises(ValueError):summarize(rows,load_config())


def test_fit_stage_absence_blocks_evaluation(monkeypatch,tmp_path):
    import nexus.world.terminal_value_execution as module
    monkeypatch.setattr(module,'FIT',tmp_path/'missing.json')
    with pytest.raises(RuntimeError):require_fit_stage(load_config())


def test_source_stage_requires_all_planned_seed_task_contexts():
    cfg=load_config();stage=dict(complete=True,config_sha256=prepare()['config_sha256'],source_cells=[],readouts={})
    # Expected IDs come from locked config, not from whatever results survived.
    with pytest.raises(ValueError):validate_fit(stage,cfg)
    with pytest.raises(ValueError):checked_id_grid([dict(decoder=False)],('decoder',),{(0,)})


def test_hard_time_and_interaction_caps():
    cfg=load_config();meter=TerminalMeter(cfg);meter.deadline=0
    with pytest.raises(TimeoutError):meter.check()
    meter=TerminalMeter(cfg);meter.model_cap=0;model=_Model();meter.instrument_model(model)
    with pytest.raises(RuntimeError):model.step(np.array([[1.,0.,0.]]),np.array([1]))


def test_actual_network_normalizer_and_context_survive_readout_fit_and_scoring():
    from nexus.world.context_model import ContextWorldModel
    from nexus.world.long_continuation_execution import frozen_hash,context_hash
    model=ContextWorldModel.create(3,3,seed=811).clone_frozen()
    before=(frozen_hash(model),context_hash(model))
    seq=candidate_sequences(817);obs=np.array([1.,0.,0.],dtype=np.float32)
    endpoints,_=predicted_endpoints(model,obs,seq)
    from nexus.world.terminal_value import value_inputs
    inputs=value_inputs(endpoints,model);readout=TerminalReadout.fit(inputs,np.arange(16,dtype=float))
    score_conditions(model,obs,seq,readout)
    assert before==(frozen_hash(model),context_hash(model))


@pytest.fixture
def fitting_stage():
    from nexus.world.terminal_value_execution import source_training_arrays
    cfg=load_config();cells=[];readouts={}
    for d,t in itertools.product(range(10),range(8)):
        cells.append(dict(role='source',task_id=cfg['train_task_ids'][t],decoder=d,task=t,
            inputs={name:[[0.]*11 for _ in range(4)] for name in NAMES},
            traces=[dict(rewards=[-1.]*48) for _ in range(4)]))
    for d in range(10):
        x,y=source_training_arrays(d,cells,cfg);model=TerminalReadout.fit(x,y)
        readouts[str(d)]=dict(state=model.state_dict(),sha256=model.digest(),rows=192,fit_rmse=float(np.sqrt(np.mean((model.predict(x)-y)**2))))
    return dict(complete=True,config_sha256=prepare()['config_sha256'],source_cells=cells,readouts=readouts)


def test_source_manifest_matches_fitted_objective(fitting_stage):
    assert len(validate_fit(fitting_stage,load_config()))==80


@pytest.mark.parametrize('missing',['seed','task','context','readout'])
def test_saved_fitting_stage_missing_axes_fail(fitting_stage,missing):
    if missing=='seed':fitting_stage['source_cells']=[r for r in fitting_stage['source_cells'] if r['decoder']!=9]
    if missing=='task':fitting_stage['source_cells']=[r for r in fitting_stage['source_cells'] if r['task']!=7]
    if missing=='context':del fitting_stage['source_cells'][0]['inputs']['zero']
    if missing=='readout':del fitting_stage['readouts']['9']
    with pytest.raises(ValueError):validate_fit(fitting_stage,load_config())


def test_development_labels_cannot_enter_registered_source_fit(fitting_stage):
    from nexus.world.terminal_value_execution import source_training_arrays
    cfg=load_config();row=fitting_stage['source_cells'][0]
    row['role']='evaluation';row['task_id']=cfg['eval_task_ids'][0]
    with pytest.raises(ValueError):source_training_arrays(0,fitting_stage['source_cells'],cfg)


def test_wrong_weights_and_non_source_normalization_fail_even_with_updated_digest(fitting_stage):
    record=fitting_stage['readouts']['0'];record['state']['weights'][0]+=1
    record['sha256']=TerminalReadout(**record['state']).digest()
    with pytest.raises(ValueError):validate_fit(fitting_stage,load_config())


@pytest.fixture
def capture(fitting_stage,monkeypatch,tmp_path):
    import hashlib
    import nexus.world.terminal_value_execution as module
    cfg=load_config();stage=fitting_stage
    def trace(task,state,n,role,action=None):
        seeds=continuation_seeds(cfg,role,task,state);actions=[];decisions=[]
        for k,seed in enumerate(seeds):
            forced=action is not None and k==0
            actions.append(action if forced else int(candidate_sequences(seed)[0,0]))
            decisions.append(dict(seed=seed,selected_index=None if forced else 0,predicted_score=None if forced else 0.,
                original_step=k+(16 if role=='source' else 0),terminated=False,truncated=False))
        return dict(actions=actions,decisions=decisions,rewards=[-1. if action is None else float(action)]*n)
    for row in stage['source_cells']:
        row['traces']=[trace(row['task'],0,48,'source') for _ in range(4)]
    path=tmp_path/'fit.json';path.write_text(json.dumps(stage));monkeypatch.setattr(module,'FIT',path)
    p=dict(fit_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),prefixes=[],supports=[],frozen_checks=[],cells=[],
        counts=budget(cfg),wall_clock_s=.1,checkpoint_before=dict(verified=120,missing=0,mismatched=0),checkpoint_after=dict(verified=120,missing=0,mismatched=0))
    ctx=hashlib.sha256(np.zeros(8,dtype=np.float32).tobytes()).hexdigest()
    for role,n in [('source',8),('evaluation',3)]:
        for t in range(n):
            p['supports'].append(dict(role=role,task=t,rows=128,sha256='a'*64))
            for d in range(10):
                before={name:['b'*64,ctx] for name in NAMES}
                p['frozen_checks'].append(dict(role=role,decoder=d,task=t,before=before,after=copy.deepcopy(before)))
    for t in range(8):
        p['prefixes'].append(dict(task=t,obs=[1.,0.,0.],state=[0.,0.],
            sequences=candidate_sequences(cfg['train_candidate_base']+t)[cfg['train_candidate_indices']].tolist(),
            rollouts=[dict(rewards=[-1.]*16,endpoint=[0.,0.]) for _ in range(4)]))
    for d,t,j in itertools.product(range(10),range(3),range(2)):
        seq=candidate_sequences(cfg['eval_candidate_base']+10*t+j)
        readout=TerminalReadout(**stage['readouts'][str(d)]['state']);inputs=np.zeros((16,11));values=readout.predict(inputs)
        scores={name:dict(base=[0.]*16,corrected=values.tolist(),endpoint=np.zeros((16,3)).tolist(),
            survival=[1.]*16,terminal=values.tolist(),inputs=inputs.tolist()) for name in NAMES}
        traces=[trace(t,j,64,'evaluation',a) for a in range(3)]
        p['cells'].append(dict(decoder=d,task=t,state=j,reset_seed=cfg['eval_state_base']+10*t+j,true_state=[0.,0.],obs=[1.,0.,0.],
            restore_exact=True,sequences=seq.tolist(),scores=scores,traces=traces,
            metrics=row_metrics(scores,[sum(tr['rewards']) for tr in traces],seq)))
    return p,stage


def test_complete_synthetic_execution_reconstructs_raw_scores_and_returns(capture):
    from nexus.world.terminal_value_execution import validate_capture
    p,stage=capture;result=validate_capture(p,load_config(),stage)
    assert result['label']=='local_first_action_inconclusive'
    assert result['comparisons']['primary']['per_decoder']==[0.]*10


@pytest.mark.parametrize('bad',['condition','rng','score','frozen','count'])
def test_full_capture_corruption_rejected(capture,bad):
    from nexus.world.terminal_value_execution import validate_capture
    p,stage=capture
    if bad=='condition':del p['cells'][0]['scores']['4']
    if bad=='rng':p['cells'][0]['traces'][0]['decisions'][1]['seed']+=1
    if bad=='score':p['cells'][0]['scores']['zero']['corrected'][0]+=1
    if bad=='frozen':p['frozen_checks'][0]['after']['zero'][0]='c'*64
    if bad=='count':p['counts']['eval_common']-=64
    with pytest.raises(ValueError):validate_capture(p,load_config(),stage)
