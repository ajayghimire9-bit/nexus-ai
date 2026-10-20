"""Synthetic algebra and boundary checks; never collect or score research tasks."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
import torch
from nexus.seed import update_gate as gate
from nexus.seed import cumulative_learning as cum
from nexus.seed.nonlinear_learning import fit_source
from nexus.seed.update_diagnosis import trajectory
from nexus.seed.experimental import Sandbox
from test_seed_cumulative_learning import toy,toy_pack

ROOT=Path(__file__).resolve().parents[1]


def config():return json.loads((ROOT/'configs/seed_update_gate.json').read_text())


def test_exact_retain_and_full_update_endpoints():
    t=toy();initial=torch.zeros(33);m=gate.factory(31,False)
    for bias in (-4.,4.):
        with torch.no_grad():m.logits.weight.zero_();m.logits.bias.fill_(bias)
        trace=[];out=gate.step(initial,initial,t.support_x[0],t.support_y[0],t.old_x,t.old_y,
            t.support_x[:1],t.support_y[:1],m,trace=trace)
        if bias<0:assert torch.equal(out,initial) and trace[0]['gate']==0
        else:
            p=cum.posterior(initial,torch.cat((t.old_x,t.support_x[:1])),torch.cat((t.old_y,t.support_y[:1])),torch.ones(33))
            assert torch.equal(out,p) and trace[0]['gate']==1


def test_finite_nonzero_meta_gradient_reaches_gate_only_and_evaluation_is_fixed():
    task=toy();m=gate.factory(71,False);before=deepcopy(m.state_dict())
    rows,snapshots=gate.curve(task,m,'learned');torch.stack([e for _,e,_ in rows]).mean().backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in m.parameters())
    assert sum(float(p.grad.abs().sum()) for p in m.parameters())>0
    trace=[];a=trajectory(task,m,'learned',update_fn=gate.updater(trace))
    assert len(trace)==8 and all(0<=x['gate']<=1 for x in trace)
    assert all(torch.equal(v,m.state_dict()[k]) for k,v in before.items())
    assert all(torch.equal(v,torch.tensor(a[p]['theta'])) for p,v in snapshots.items())


def test_assessment_poison_cannot_change_inner_states_or_gate_traces():
    task=toy();other=deepcopy(task)
    object.__setattr__(other,'query_y',task.query_y+1000)
    object.__setattr__(other,'retention_y',task.retention_y-1000)
    m=gate.factory(71,False);traces=[];again=[]
    a=trajectory(task,m,'learned',update_fn=gate.updater(traces))
    b=trajectory(other,m,'learned',update_fn=gate.updater(again))
    assert traces==again and all(x['theta']==y['theta'] for x,y in zip(a,b))
    assert a[1]['query_mse']!=b[1]['query_mse']


def test_future_teaching_rows_cannot_change_earlier_prefixes():
    task=toy();other=deepcopy(task);y=task.support_y.clone();y[4:]+=50
    object.__setattr__(other,'support_y',y);m=gate.factory(71,False)
    _,a=gate.curve(task,m,'learned');_,b=gate.curve(other,m,'learned')
    assert all(torch.equal(a[p],b[p]) for p in (1,2,4)) and not torch.equal(a[8],b[8])


def test_paired_initialization_schedule_constant_capacity_and_reproduction():
    c=config();c['meta_updates']=3;tasks=[toy(i) for i in range(3)]
    a=gate.factory(71,False);b=gate.factory(71,True)
    assert all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items())
    fitted,logs=fit_source(tasks,71,False,c,lambda:None,curve_fn=gate.curve,model_factory=gate.factory)
    static,slog=fit_source(tasks,71,True,c,lambda:None,curve_fn=gate.curve,model_factory=gate.factory)
    assert logs['source_schedule_sha256']==slog['source_schedule_sha256']
    assert logs['trainable_parameters']==5 and slog['trainable_parameters']==1
    assert logs['parameter_change_l2']>0 and slog['parameter_change_l2']>0
    assert torch.equal(static.logits.weight,torch.zeros_like(static.logits.weight))
    repeated,again=fit_source(tasks,71,False,c,lambda:None,curve_fn=gate.curve,model_factory=gate.factory)
    assert logs['training']==again['training']
    assert all(torch.equal(v,repeated.state_dict()[k]) for k,v in fitted.state_dict().items())


def test_excluded_tasks_cannot_change_training_scale_bound_or_fitted_gate():
    c=config();pack=toy_pack();changed=deepcopy(pack);held=set(cum.partition(c,0)[1])
    for t in changed['tasks']:
        if t['seed'] in held:
            for k,arr in t['arrays'].items():t['arrays'][k]=(torch.tensor(arr)*100+10).tolist()
    train,_,meta=cum.prepare_fold(pack,c,0);other,_,info=cum.prepare_fold(changed,c,0)
    assert meta==info;c['meta_updates']=2
    a,logs=fit_source(train,77,False,c,lambda:None,curve_fn=gate.curve,model_factory=gate.factory)
    b,again=fit_source(other,77,False,c,lambda:None,curve_fn=gate.curve,model_factory=gate.factory)
    assert logs['training']==again['training']
    assert all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items())


def test_source_payload_and_locked_resource_boundaries():
    c=config();assert set(gate.source_pack(ROOT,c))=={'tasks'}
    assert gate.config_check(c)['outer_updates']==1536
    for key,value in [('meta_updates',65),('gate_slope',.5),('max_wall_s',900),('ridge',True)]:
        bad=deepcopy(c);bad[key]=value
        with pytest.raises(ValueError):gate.config_check(bad)


def test_checkpoint_roundtrip_is_scalar_not_33_diagonal(tmp_path):
    m=gate.factory(71,False);path=tmp_path/'gate.json'
    provenance=dict(config_sha256='a'*64,fold=0,seed=7201,source_sha256='b'*64,source_only=True)
    sha=m.export(path,provenance);info=dict(provenance=provenance,sha256=sha,weights={k:v.tolist() for k,v in m.state_dict().items()})
    assert cum.checkpoint_bytes(json.loads(json.dumps(info,sort_keys=True)),width=1)==path.read_bytes()
    with pytest.raises(ValueError):cum.checkpoint_bytes(info)


@pytest.mark.parametrize('fault',['seed','task','condition','prefix','fold','fitted_seed','arm','update','checkpoint','nan','infinity','numeric_string','boolean'])
def test_planned_grid_cannot_shrink_or_admit_invalid_metrics(fault):
    c=config();snapshots=[dict(prefix=p,theta=[0.]*33,query_mse=0.,retention_mse=0.,update_l2=0.,cumulative_update_l2=0.,
        support_error_before=0.,support_error_after=0.,residual_corrected_fraction=0.) for p in c['prefixes']]
    rows={str(s):{str(t):{m:deepcopy(snapshots) for m in gate.METHODS} for t in c['tasks']['train']} for s in c['outer_seeds']}
    folds={str(f):dict(train_ids=cum.partition(c,f)[0],excluded_ids=cum.partition(c,f)[1],models={str(s):{
        m:dict(training=[dict(update=i) for i in range(1,65)],checkpoint='toy.json',sha256='a'*64)
        for m in gate.METHODS[:2]} for s in c['outer_seeds']}) for f in range(4)}
    r=dict(rows=rows,folds=folds);assert cum.complete_grid(r,c,methods=gate.METHODS)
    cell=rows['7201']['95000000'];arms=folds['0']['models']['7201']
    if fault=='seed':del rows['7201']
    elif fault=='task':del rows['7201']['95000000']
    elif fault=='condition':del cell['learned_gate']
    elif fault=='prefix':cell['learned_gate'].pop()
    elif fault=='fold':del folds['0']
    elif fault=='fitted_seed':del folds['0']['models']['7201']
    elif fault=='arm':del arms['constant_gate']
    elif fault=='update':arms['learned_gate']['training'].pop()
    elif fault=='checkpoint':del arms['learned_gate']['sha256']
    else:cell['learned_gate'][1]['query_mse']={'nan':float('nan'),'infinity':float('inf'),'numeric_string':'0','boolean':False}[fault]
    with pytest.raises((ValueError,KeyError)):cum.complete_grid(r,c,methods=gate.METHODS)


def test_host_rejects_unvetted_protocol_path_before_reserving(tmp_path):
    h=Sandbox(ROOT,tmp_path/'host');h.grant('toy','owner','source boundary test',
        dict(wall_s=60,cpu_s=60,memory_mb=2048,updates=1536,real_steps=0,imagined_transitions=0),3600,0,memory_policy='sampled_rss')
    spec=dict(id='toy',mode='exploration',recipe=dict(adapter='seed_update_gate_v1',
        config_path='configs/seed_update_gate.json',config_sha256='a'*64,protocol_path='elsewhere.md',protocol_sha256='b'*64),
        train=None,development=None,model_run=None,assessment=None,protocol=None,gate=None)
    with pytest.raises(ValueError,match='vetted_study_manifest'):h.execute(spec,'toy')
    assert h.records('reserved')==[]


@pytest.mark.parametrize('fault',[None,'gate','context','proposal','state'])
def test_independent_saved_gate_and_normal_equation_audit(fault):
    task=toy();cell={};models={}
    for static,method in ((False,'learned_gate'),(True,'constant_gate')):
        m=gate.factory(71,static);trace=[];cell[method]=trajectory(task,m,'learned',update_fn=gate.updater(trace))
        for row,t in zip(cell[method][1:],trace):row.update(t)
        models[method]={'weights':{k:v.tolist() for k,v in m.state_dict().items()}}
    arrays={k:getattr(task,k).tolist() for k in task.__dataclass_fields__}
    r=dict(config=config(),folds={'0':dict(scale=[1.]*33,excluded_ids=[1],models={'7201':models})},rows={'7201':{'1':cell}})
    pack=dict(tasks=[dict(seed=1,arrays=arrays)]);assert gate.validate_traces(r,pack)
    row=cell['learned_gate'][1]
    if fault is None:return
    if fault=='gate':row['gate']+=.1
    elif fault=='context':row['gate_context'][0]+=.1
    elif fault=='proposal':row['proposal'][0]+=.1
    else:row['theta'][0]+=.1
    with pytest.raises(ValueError):gate.validate_traces(r,pack)
