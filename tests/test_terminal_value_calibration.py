"""Synthetic fixtures and existing-evidence checks; no new research simulation."""
import copy
import itertools
import json

import numpy as np
import pytest
import torch

import nexus.world.terminal_value_calibration as module
from nexus.world.terminal_value import NAMES,TerminalReadout
from nexus.world.prediction_control_gap import candidate_sequences


def fake_rows():
    rows=[]
    for d,t in itertools.product(range(10),range(11)):
        predictions={name:dict(imagined=[1.]*4,actual=[.5]*4,constant=[3.]*4) for name in NAMES}
        rows.append(dict(decoder=d,task=t,targets=[0.]*4,predictions=predictions,metrics=module.metrics(predictions,[0.]*4)))
    return rows


def test_budget_and_seed_closure():
    cfg=module.load_config();module.check_seeds(cfg)
    assert module.budget(cfg)==dict(prefix=704,tail=21120,model_states=5448960)
    for key,value in [('state_base',2050000),('candidate_base',1220000),('tail_base',2030000),('state_base',1200000)]:
        bad=copy.deepcopy(cfg);bad[key]=value
        with pytest.raises(ValueError):module.check_seeds(bad)
    assert len(module.tail_seeds(cfg,10))==48
    with pytest.raises(TypeError):module.tail_seeds(cfg,0,action=2)


def test_prepare_approval_and_audit_inputs_never_collect_or_refit(monkeypatch,tmp_path):
    def forbidden(*a,**kw):raise AssertionError('no new collection/fitting allowed')
    monkeypatch.setattr(module,'APPROVAL',tmp_path/'missing_approval.json')
    monkeypatch.setattr(module,'make_task_env',forbidden)
    monkeypatch.setattr(TerminalReadout,'fit',forbidden)
    result=module.prepare()
    assert result['new_environment_steps']==result['readout_fits']==result['network_updates']==0
    for arg in (None,'stale',module.LOCK):
        with pytest.raises(PermissionError):module.execute(arg)


def test_saved_contexts_reproduce_all_recorded_fingerprints_without_binaries():
    parent,stage=module.parent_evidence()
    for d,t in itertools.product(range(10),range(11)):
        contexts,checks=module.saved_contexts(parent,stage,d,t)
        assert set(contexts)==set(NAMES)
        assert all(z.dtype==np.float32 and z.shape==(8,) for z in contexts.values())
        assert all(len(v)==2 and all(len(h)==64 for h in v) for v in checks.values())


def test_saved_context_corruption_fails():
    parent,stage=module.parent_evidence()
    stage=copy.deepcopy(stage);stage['source_cells'][0]['inputs']['0'][0][3]+=1
    with pytest.raises(ValueError):module.saved_contexts(parent,stage,0,0)


def test_pairing_and_decoder_unit():
    summary=module.summarize(fake_rows(),module.load_config())
    assert summary['label']=='held_out_calibration_screen_pass'
    assert summary['summaries']['development']['benefit']['n']==10
    assert summary['summaries']['development']['benefit']['mean']==2
    assert summary['summaries']['development']['fractional_reduction']==pytest.approx(2/3)


def test_rmse_precedes_task_aggregation_and_students_are_averaged_inside_decoder():
    rows=fake_rows()
    for r in rows:
        r['predictions']['0']['imagined']=[float(r['task']-8)]*4
        r['metrics']=module.metrics(r['predictions'],r['targets'])
    result=module.summarize(rows,module.load_config())
    # Task RMSEs for seed0:0,1,2; four remaining students each have RMSE1.
    assert result['summaries']['development']['per_decoder']['imagined']==[1.]*10


@pytest.mark.parametrize('axis,value',[('decoder',9),('task',10)])
def test_missing_whole_planned_axes_fail(axis,value):
    with pytest.raises(ValueError):module.summarize([r for r in fake_rows() if r[axis]!=value],module.load_config())


@pytest.mark.parametrize('bad',[True,'1',float('nan'),float('inf')])
def test_invalid_required_values_fail(bad):
    rows=fake_rows();rows[0]['predictions']['zero']['imagined'][0]=bad
    with pytest.raises(ValueError):module.summarize(rows,module.load_config())


@pytest.mark.parametrize('missing',['context','condition','candidate','duplicate','summary'])
def test_missing_raw_conditions_and_inconsistent_summaries_fail(missing):
    rows=fake_rows()
    if missing=='context':del rows[0]['predictions']['4']
    if missing=='condition':del rows[0]['predictions']['zero']['actual']
    if missing=='candidate':rows[0]['targets'].pop()
    if missing=='duplicate':rows.append(copy.deepcopy(rows[0]))
    if missing=='summary':rows[0]['metrics']['zero']['actual']=2
    with pytest.raises(ValueError):module.summarize(rows,module.load_config())


def test_zero_baseline_denominator_cannot_pass():
    rows=fake_rows()
    for r in rows:
        for p in r['predictions'].values():p['constant']=[0.]*4
        r['metrics']=module.metrics(r['predictions'],r['targets'])
    result=module.summarize(rows,module.load_config())
    assert result['label']=='held_out_calibration_not_established'
    assert result['summaries']['development']['fractional_reduction'] is None


def test_explicit_checkpoint_audit_propagates_missing_binary_failure(monkeypatch):
    import nexus.world.checkpoint_integrity as checks
    def missing():raise FileNotFoundError('required checkpoint missing')
    monkeypatch.setattr(checks,'verify_checkpoint_integrity',missing)
    with pytest.raises(FileNotFoundError):module.verify_inputs()


def test_hard_caps():
    meter=module.CalibrationMeter(module.load_config());meter.deadline=0
    with pytest.raises(TimeoutError):meter.check()
    from test_receding_horizon import _Model
    meter=module.CalibrationMeter(module.load_config());meter.model_cap=0;m=_Model();meter.instrument_model(m)
    with pytest.raises(RuntimeError):m.step(np.array([[1.,0.,0.]]),np.array([1]))


def test_only_endpoint_inputs_change_not_model_context_or_readout():
    from nexus.world.context_model import ContextWorldModel
    from nexus.world.long_continuation_execution import frozen_hash,context_hash
    model=ContextWorldModel.create(3,3,seed=998).clone_frozen();model.z=torch.arange(8,dtype=torch.float32)
    frozen=(frozen_hash(model),context_hash(model))
    readout=TerminalReadout(np.zeros(77).tolist(),np.ones(77).tolist(),np.arange(78,dtype=float).tolist());before=readout.digest()
    seq=candidate_sequences(9157)[[0,4,8,12]]
    endpoints,_=module.predicted_endpoints(model,np.array([1.,0.,0.]),seq)
    x=module.value_inputs(endpoints,model);readout.predict(x)
    assert (frozen_hash(model),context_hash(model))==frozen and readout.digest()==before
    assert np.array_equal(x[:,3:],np.tile(np.arange(8),(4,1)))


@pytest.fixture
def synthetic_capture():
    cfg=module.load_config();parent,stage=module.parent_evidence()
    p=dict(prefixes=[],cells=[],config_sha256=module.LOCK,protocol_sha256=module.sha(module.PROTOCOL),parents=cfg['parents'],
        counts=module.budget(cfg),wall_clock_s=1.,checkpoint_before=dict(verified=120,missing=0,mismatched=0),checkpoint_after=dict(verified=120,missing=0,mismatched=0))
    for t in range(11):
        p['prefixes'].append(dict(task=t,reset_seed=cfg['state_base']+t,sequences=candidate_sequences(cfg['candidate_base']+t)[cfg['candidate_indices']].tolist(),
            obs=[1.,0.,0.],state=[0.,0.],restore_exact=True,rollouts=[dict(rewards=[-1.]*16,endpoint=[0.,0.],endpoint_obs=[1.,0.,0.]) for _ in range(4)]))
    # Cache planned action/RNG traces; no simulator or model scoring is executed.
    traces={}
    for t in range(11):
        seeds=module.tail_seeds(cfg,t);actions=[int(candidate_sequences(seed)[0,0]) for seed in seeds]
        decisions=[dict(seed=seed,selected_index=0,predicted_score=0.,original_step=16+k,terminated=False,truncated=False) for k,seed in enumerate(seeds)]
        traces[t]=dict(rewards=[-1.]*48,actions=actions,decisions=decisions)
    for d,t in itertools.product(range(10),range(11)):
        contexts,expected=module.saved_contexts(parent,stage,d,t);readout=TerminalReadout(**stage['readouts'][str(d)]['state'])
        constant=float(np.mean([sum(tr['rewards']) for r in stage['source_cells'] if r['decoder']==d for tr in r['traces']]))
        inputs={};predictions={}
        for name in NAMES:
            x=np.column_stack([np.tile([1.,0.,0.],(4,1)),np.tile(contexts[name],(4,1))]).tolist()
            inputs[name]=dict(actual=x,imagined=copy.deepcopy(x))
            predictions[name]=dict(actual=readout.predict(x).tolist(),imagined=readout.predict(x).tolist(),constant=[constant]*4)
        p['cells'].append(dict(decoder=d,task=t,before=expected,after=copy.deepcopy(expected),readout_sha256=readout.digest(),
            inputs=inputs,predictions=predictions,targets=[-48.]*4,traces=[copy.deepcopy(traces[t]) for _ in range(4)],metrics=module.metrics(predictions,[-48.]*4)))
    return p,cfg,parent,stage


def test_complete_capture_recomputes_labels_predictions_baseline_and_intervals(synthetic_capture):
    p,cfg,parent,stage=synthetic_capture
    result=module.validate(p,cfg,parent,stage)
    assert result['summaries']['development']['benefit']['n']==10


@pytest.mark.parametrize('bad',['prefix','seed','task','actual','context','readout','constant','rng','endpoint','count','prediction','stored_bool'])
def test_complete_capture_corruption_rejected(synthetic_capture,bad):
    p,cfg,parent,stage=synthetic_capture;cell=p['cells'][0]
    if bad=='prefix':p['prefixes'].pop()
    if bad=='seed':p['cells']=[r for r in p['cells'] if r['decoder']!=9]
    if bad=='task':p['cells']=[r for r in p['cells'] if r['task']!=10]
    if bad=='actual':cell['inputs']['zero']['actual'][0][0]=7.
    if bad=='context':cell['inputs']['zero']['imagined'][0][3]+=1.
    if bad=='readout':cell['readout_sha256']='wrong'
    if bad=='constant':cell['predictions']['zero']['constant'][0]+=1.
    if bad=='rng':cell['traces'][0]['decisions'][0]['seed']+=1
    if bad=='endpoint':p['prefixes'][0]['rollouts'][0]['endpoint'][0]=1.
    if bad=='count':p['counts']['prefix']+=16
    if bad=='prediction':cell['predictions']['zero']['imagined'][0]+=1.
    if bad=='stored_bool':cell['metrics']['zero']['imagined']=True
    with pytest.raises(ValueError):module.validate(p,cfg,parent,stage)


def test_real_capture_nonuniform_reward_sums_and_all_axes(monkeypatch):
    import nexus.world.checkpoint_integrity as checkpoints
    def forbidden():raise AssertionError('repository-only audit cannot require .pt binaries')
    monkeypatch.setattr(checkpoints,'verify_checkpoint_integrity',forbidden)
    p=json.loads(module.OUTPUT.read_text());parent,stage=module.parent_evidence()
    assert p['complete'] is False and p['failure']['message']=='wrong continuation label'
    # Recorded nonuniform float rewards catch compensated-Python versus NumPy
    # scalar accumulation differences that the all-minus-one fixture missed.
    assert any(sum(tr['rewards'])!=sum(np.array(tr['rewards'])) for r in p['cells'] for tr in r['traces'])
    result=module.validate(p,module.load_config(),parent,stage)
    assert result['summaries']['development']['benefit']['n']==10
    assert result['label']=='held_out_calibration_screen_pass'
    assert result['summaries']['development']['benefit']['mean']==pytest.approx(42.887241647087194)
