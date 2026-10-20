"""Synthetic source-only feature/feedback tests, no scientific worlds or models."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
import numpy as np
import torch
from nexus.nn.ridge import fit_ridge,predict_ridge
from nexus.seed import prefix_consistency as audit
from nexus.seed import cumulative_learning as cum
from nexus.seed import learning_benchmark as lb
from test_seed_cumulative_learning import toy,toy_pack

ROOT=Path(__file__).resolve().parents[1]


def config():return json.loads((ROOT/'configs/seed_prefix_consistency.json').read_text())


def cases_for(pack,c,fold):
    tasks,held,meta=cum.prepare_fold(pack,c,fold,include_bound=False);train,_=cum.partition(c,fold)
    return {str(t):audit.label_trace(audit.support_trace(x.support_x,x.support_y,x.old_x,x.old_y),x) for t,x in zip(train,tasks)},meta


def test_ridge_extraction_preserves_original_augmented_solution_exactly():
    rng=np.random.default_rng(91)
    for shape in ((9,4),(3,12)):
        x=rng.normal(size=shape);y=rng.normal(size=shape[0]);xx=np.r_[x,-x];yy=np.r_[y,-y]
        scale=np.sqrt(np.mean(xx*xx,axis=0));scale=np.where(scale<1e-8,1.,scale);z=xx/scale
        beta=z.T@np.linalg.solve(z@z.T+np.eye(len(z)),yy) if shape[1]>len(z) else np.linalg.solve(z.T@z+np.eye(z.shape[1]),z.T@yy)
        a,b=fit_ridge(x,y);assert np.array_equal(a,scale) and np.array_equal(b,beta)
        assert predict_ridge((a,b),x[0])==float((x[0]/scale)@beta)


def test_query_poison_changes_labels_but_not_reference_states_or_features():
    a=toy();b=deepcopy(a);object.__setattr__(b,'query_y',a.query_y+10)
    trace=audit.support_trace(a.support_x,a.support_y,a.old_x,a.old_y)
    x=audit.label_trace(deepcopy(trace),a);y=audit.label_trace(deepcopy(trace),b)
    assert all(x[i][k]==y[i][k] for i in range(8) for k in ('features','before','proposal'))
    assert x[0]['utility']!=y[0]['utility']


def test_future_support_does_not_change_earlier_features():
    t=toy();labels=t.support_y.clone();labels[4:]+=10
    a=audit.support_trace(t.support_x,t.support_y,t.old_x,t.old_y)
    b=audit.support_trace(t.support_x,labels,t.old_x,t.old_y)
    assert a[:4]==b[:4] and a[4:]!=b[4:]


def test_consistent_and_conflicting_prefixes_produce_different_evidence():
    previous=[0.,0.];proposal=[1.,0.];x=[1.,0.];anchors=[[0.,1.]];old_y=[0.]
    good=audit.features(previous,proposal,x,1.,anchors,old_y,[x,x],[1.,1.])
    bad=audit.features(previous,proposal,x,1.,anchors,old_y,[x,x],[-1.,1.])
    assert good[:4]==bad[:4] and good[5]>0>bad[5]
    assert good[6]==0 and bad[6]==1 and good[7]>0>bad[7]


def test_excluded_poison_cannot_change_scale_or_any_fitted_predictor():
    c=config();p=toy_pack();q=deepcopy(p);held=set(cum.partition(c,0)[1])
    for t in q['tasks']:
        if t['seed'] in held:
            for k,v in t['arrays'].items():t['arrays'][k]=(torch.tensor(v)*100+50).tolist()
    a,am=cases_for(p,c,0);b,bm=cases_for(q,c,0)
    assert am==bm and a==b
    train,_=cum.partition(c,0);assert audit.fit_predictors(a,train,c,0)==audit.fit_predictors(b,train,c,0)
    poisoned=deepcopy(a);poisoned['unpermitted']=[{'utility':float('nan')}]
    assert audit.fit_predictors(a,train,c,0)==audit.fit_predictors(poisoned,train,c,0)


def test_permutation_preserves_prefix_and_marginal_features_but_not_task_matching():
    c=config();train,_=cum.partition(c,0);p=audit.permute_ids(train,c,0)
    assert sorted(p)==sorted(train) and all(a!=b for a,b in zip(p,train))
    assert p==audit.permute_ids(train,c,0)
    cases,_=cases_for(toy_pack(),c,0);a=audit.training_rows(cases,train);b=audit.training_rows(cases,p)
    for prefix in c['prefixes']:
        assert sorted(r['features'] for r in a if r['prefix']==prefix)==sorted(r['features'] for r in b if r['prefix']==prefix)


def test_no_unused_bound_fit_or_unregistered_work():
    c=config();lb.WORK.clear();tasks,_,meta=cum.prepare_fold(toy_pack(),c,0,include_bound=False)
    assert meta['tau'] is None and not lb.WORK
    t=tasks[0];audit.support_trace(t.support_x,t.support_y,t.old_x,t.old_y)
    assert lb.WORK=={'old_anchor_initial_solves':1,'cumulative_solves':8}
    assert audit.config_check(c)==dict(real_steps=0,imagined_transitions=0,outer_updates=0)
    c['predictor_ridge']=.1
    with pytest.raises(ValueError):audit.config_check(c)


def test_source_payload_is_tasks_only_and_host_rejects_unlocked_path(tmp_path):
    from nexus.seed.experimental import Sandbox
    assert set(audit.source_pack(ROOT,config()))=={'tasks'}
    host=Sandbox(ROOT,tmp_path/'host');host.grant('toy','owner','synthetic boundary check',
        dict(wall_s=30,cpu_s=30,memory_mb=2048,updates=0,real_steps=0,imagined_transitions=0),3600,0,memory_policy='sampled_rss')
    spec=dict(id='toy',mode='exploration',recipe=dict(adapter='seed_prefix_consistency_v1',
        config_path='configs/seed_prefix_consistency.json',config_sha256='a'*64,protocol_path='unlocked.md',protocol_sha256='b'*64),
        train=None,development=None,model_run=None,assessment=None,protocol=None,gate=None)
    with pytest.raises(ValueError,match='vetted_study_manifest'):host.execute(spec,'toy')
    assert host.records('reserved')==[]


@pytest.fixture(scope='module')
def synthetic_result(tmp_path_factory):
    # Entire execution path on generated linear arrays; zero scientific data.
    root=tmp_path_factory.mktemp('prefix-toy');previous=Path.cwd()
    import os
    os.chdir(root)
    try:
        c=config();pack=toy_pack();output=audit.run(dict(inputs=dict(study_config=c,source_pack=pack)))
    finally:os.chdir(previous)
    assert output['study']['declared_complete'] is True
    assert audit.validate_output(output,c,dict(cpu_s=30,updates=0),pack)
    return output,c,pack


def test_synthetic_full_path_is_complete_reproducible_and_not_control(synthetic_result):
    output,c,pack=synthetic_result
    assert audit.validate(output['study'],c,pack)
    assert len(output['study']['analysis']['per_task'])==12
    assert 'not realized' in output['study']['analysis']['trajectory_interpretation']
    assert output['resources']['world_model_forwards']==0


@pytest.mark.parametrize('fault',['fold','task','prefix','method','metric','coefficient','feature','state','scale','prediction','nan','boolean','permutation'])
def test_saved_complete_grid_and_math_reject_corruption(synthetic_result,fault):
    output,c,pack=synthetic_result;r=deepcopy(output['study']);f=r['folds']['0'];row=f['cases']['95000000'][0]
    if fault=='fold':del r['folds']['0']
    elif fault=='task':del f['cases']['95000000']
    elif fault=='prefix':f['cases']['95000000'].pop()
    elif fault=='method':del row['predictions']['current']
    elif fault=='metric':del row['retention_before']
    elif fault=='coefficient':f['models']['full']['beta'][0]+=.1
    elif fault=='feature':row['features'][6]+=.1
    elif fault=='state':row['proposal'][0]+=.1
    elif fault=='scale':f['scale'][0]*=2
    elif fault=='prediction':row['predictions']['full']+=.1
    elif fault=='nan':row['utility']=float('nan')
    elif fault=='boolean':row['utility']=False
    else:f['permutation'].reverse()
    with pytest.raises((ValueError,KeyError)):audit.validate(r,c,pack)
