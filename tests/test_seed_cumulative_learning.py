"""Toy algebra, cross-fit isolation and source provenance only."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
import torch
from nexus.seed import learning_benchmark as lb
from nexus.seed.plasticity import PlasticityController
from nexus.seed.nonlinear_learning import fit_source
from nexus.seed.cumulative_learning import config_check,partition,source_pack,prepare_fold,posterior,curve,cumulative_updater,seed_interval,checkpoint_bytes,complete_grid
from nexus.seed.update_diagnosis import trajectory

ROOT=Path(__file__).resolve().parents[1]


def config():return json.loads((ROOT/'configs/seed_cumulative_learning.json').read_text())


def toy(seed=9):
    g=torch.Generator().manual_seed(seed);x=torch.randn(66,33,generator=g)/33**.5
    y=x@torch.randn(33,generator=g)
    return lb.LessonTask(x[:8],y[:8],x[12:39],y[12:39],x[8:12],y[8:12],x[39:],y[39:])


def toy_pack():
    return dict(tasks=[dict(seed=t,arrays={k:getattr(toy(i),k).tolist() for k in toy(i).__dataclass_fields__})
                      for i,t in enumerate(config()['tasks']['train'])])


def test_dual_posterior_matches_primal_optimum_and_has_precision_gradients():
    torch.manual_seed(71);x=torch.randn(9,5,dtype=torch.float64);y=torch.randn(9,dtype=torch.float64)
    initial=torch.randn(5,dtype=torch.float64);d=torch.rand(5,dtype=torch.float64,requires_grad=True)+.1
    result=posterior(initial,x,y,d,.1)
    primal=torch.linalg.solve(x.T@x+.1*torch.diag(1/d),x.T@y+.1*initial/d)
    assert torch.allclose(result,primal,atol=1e-10,rtol=1e-10)
    grad=torch.autograd.grad(result.square().sum(),d)[0]
    assert torch.isfinite(grad).all() and float(grad.abs().sum())>0


def test_queries_do_not_change_inner_states_and_later_labels_do_not_change_prefixes():
    task=toy();m=PlasticityController(33);_,a=curve(task,m,'learned')
    changed=deepcopy(task);object.__setattr__(changed,'query_y',task.query_y+999)
    _,b=curve(changed,m,'learned')
    assert all(torch.equal(a[k],b[k]) for k in a)
    labels=task.support_y.clone();labels[4:]+=10;object.__setattr__(changed,'support_y',labels)
    _,b=curve(changed,m,'learned')
    assert all(torch.equal(a[k],b[k]) for k in (1,2,4)) and not torch.equal(a[8],b[8])
    rows=trajectory(task,m,'learned',update_fn=cumulative_updater(.1))
    assert all(torch.equal(a[k],torch.tensor(rows[k]['theta'])) for k in a)


def test_four_folds_are_disjoint_and_cover_each_excluded_task_once():
    c=config();held=[]
    for f in range(4):
        a,b=partition(c,f);assert len(a)==9 and len(b)==3 and not set(a)&set(b);held+=b
    assert sorted(held)==c['tasks']['train']
    with pytest.raises(ValueError):partition(c,True)


def test_excluded_poison_cannot_change_preprocessing_or_fitted_rules():
    c=config();p=toy_pack();train,held,meta=prepare_fold(p,c,0)
    poisoned=deepcopy(p);excluded=set(partition(c,0)[1])
    for task in poisoned['tasks']:
        if task['seed'] in excluded:
            for k in task['arrays']:
                values=torch.tensor(task['arrays'][k])*100+10;task['arrays'][k]=values.tolist()
    other,_,new_meta=prepare_fold(poisoned,c,0)
    assert meta==new_meta
    c['meta_updates']=2;callback=lambda t,m,k,chk:curve(t,m,k,chk)
    a,logs=fit_source(train,71,False,c,lambda:None,curve_fn=callback)
    b,again=fit_source(other,71,False,c,lambda:None,curve_fn=callback)
    assert all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items())
    assert logs['training']==again['training'] and all(v['gradient_norm']>0 for v in logs['training'])


def test_static_is_strong_paired_source_fit_and_reproducible():
    c=config();c['meta_updates']=3;tasks=[toy(i) for i in range(3)];cb=lambda t,m,k,chk:curve(t,m,k,chk)
    a,info=fit_source(tasks,71,False,c,lambda:None,curve_fn=cb)
    b,static=fit_source(tasks,71,True,c,lambda:None,curve_fn=cb)
    assert info['source_schedule_sha256']==static['source_schedule_sha256']
    assert info['parameter_change_l2']>0 and static['parameter_change_l2']>0
    assert torch.equal(b.logits.weight,torch.zeros_like(b.logits.weight))
    again,_=fit_source(tasks,71,False,c,lambda:None,curve_fn=cb)
    assert all(torch.equal(v,again.state_dict()[k]) for k,v in a.state_dict().items())


def test_worker_source_payload_excludes_pretrained_rules_and_global_scale():
    p=source_pack(ROOT,config())
    assert set(p)=={'tasks'} and len(p['tasks'])==12


def test_intervals_use_three_update_rule_seeds_not_rows_tasks_or_folds():
    a=seed_interval([1.,2.,3.]);assert a['mean']==2
    assert a['ci95'][0]==pytest.approx(2-4.302652730/3**.5)
    assert 'one_core' in a['unit']
    for v in ([1,2],list(range(12)),[True]*3,[float('nan')]*3):
        with pytest.raises(ValueError):seed_interval(v)


def test_expected_compute_and_recipe_are_locked():
    c=config();assert config_check(c)==dict(real_steps=0,imagined_transitions=0,outer_updates=1536)
    assert c['fold_count']*len(c['outer_seeds'])*2*c['meta_updates']==1536
    assert 3*12*6*9==1944
    c['meta_updates']=128
    with pytest.raises(ValueError):config_check(c)


def test_new_checkpoint_bytes_survive_canonical_result_serialization(tmp_path):
    m=PlasticityController(33);provenance=dict(config_sha256='a'*64,fold=1,seed=7101,source_sha256='b'*64,source_only=True)
    path=tmp_path/'new.json';sha=m.export(path,provenance)
    info=dict(provenance=provenance,weights={k:v.tolist() for k,v in m.state_dict().items()},sha256=sha)
    wire=json.loads(json.dumps(info,sort_keys=True))
    assert checkpoint_bytes(wire)==path.read_bytes()


@pytest.mark.parametrize('fault',['fold','seed','task','method','prefix','fit_seed','fit_arm','update','checkpoint','nan','bool'])
def test_missing_or_nonfinite_planned_cells_fail_closed(fault):
    c=config()
    snapshots=[dict(prefix=p,theta=[0.]*33,query_mse=0.,retention_mse=0.,update_l2=0.,cumulative_update_l2=0.,
        support_error_before=0.,support_error_after=0.,residual_corrected_fraction=0.) for p in range(9)]
    rows={str(s):{str(t):{m:deepcopy(snapshots) for m in c['methods']} for t in c['tasks']['train']} for s in c['outer_seeds']}
    folds={str(f):dict(train_ids=partition(c,f)[0],excluded_ids=partition(c,f)[1],models={str(s):{
        m:dict(training=[dict(update=i) for i in range(1,65)],checkpoint='fixture.json',sha256='a'*64)
        for m in ('learned_cumulative','static_cumulative')} for s in c['outer_seeds']}) for f in range(4)}
    r=dict(rows=rows,folds=folds);assert complete_grid(r,c)
    cell=rows['7101']['95000000'];arms=folds['0']['models']['7101']
    if fault=='fold':del folds['0']
    elif fault=='seed':del rows['7101']
    elif fault=='task':del rows['7101']['95000000']
    elif fault=='method':del cell['learned_cumulative']
    elif fault=='prefix':cell['learned_cumulative'].pop()
    elif fault=='fit_seed':del folds['0']['models']['7101']
    elif fault=='fit_arm':del arms['static_cumulative']
    elif fault=='update':arms['learned_cumulative']['training'].pop()
    elif fault=='checkpoint':del arms['learned_cumulative']['checkpoint']
    elif fault=='nan':cell['learned_cumulative'][1]['query_mse']=float('nan')
    else:cell['learned_cumulative'][1]['query_mse']=True
    with pytest.raises((ValueError,KeyError)):complete_grid(r,c)
