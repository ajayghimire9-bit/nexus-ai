"""Synthetic algebra/decision contracts only; no worlds or scientific data fit."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import pytest
import torch
from nexus.evolution1.catalogue import digest
from nexus.seed import learning_choice as lc
from nexus.seed.learning_decision import decide
from nexus.seed import prefix_consistency as ev
from nexus.seed import cumulative_learning as cum
from nexus.seed.update_diagnosis import trajectory
from test_seed_cumulative_learning import toy
from test_seed_sequential_consistency import synthetic_pack,synthetic_result

ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/seed_learning_choice.json').read_text())


@pytest.mark.parametrize('gain,scale,damage,remaining,expected,reason',[
    (1.,.1,0.,7,'learn','predicted_benefit'),
    (1.,.1,.02,7,'ask','known_memory_risk'),
    (1.,.1,.02,0,'retain','known_memory_risk'),
    (-1.,.1,0.,7,'retain','predicted_harm'),
    (.02,.1,0.,7,'ask','uncertain_benefit'),
    (.02,.1,0.,0,'retain','uncertain_benefit'),
    (.1,.1,0.,7,'ask','uncertain_benefit')])
def test_all_decisions_budget_ties_and_explicit_questions(gain,scale,damage,remaining,expected,reason):
    d=decide(predicted_gain=gain,error_scale=scale,known_damage=damage,damage_cap=.01,remaining_examples=remaining)
    assert (d.action,d.reason)==(expected,reason)
    assert bool(d.payload()['question'])==(expected=='ask')
    with pytest.raises(FrozenInstanceError):d.action='learn'


@pytest.mark.parametrize('changes',[{'predicted_gain':True},{'error_scale':float('nan')},{'known_damage':float('inf')},{'damage_cap':-.1},{'remaining_examples':True},{'remaining_examples':-1}])
def test_invalid_learning_evidence_fails(changes):
    args=dict(predicted_gain=1.,error_scale=.1,known_damage=0.,damage_cap=.01,remaining_examples=1);args.update(changes)
    with pytest.raises(ValueError):decide(**args)


def test_observed_memory_conflict_asks_then_retains_without_changing_fit():
    from nexus.seed.learning_benchmark import LessonTask
    x=torch.zeros(8,33);x[:,0]=1.;old=torch.zeros(4,33);old[:,0]=1.
    task=LessonTask(x,torch.ones(8),x,torch.ones(8),old,torch.zeros(4),x,torch.zeros(8))
    info=dict(model=dict(columns=list(range(4,10)),center=[0.]*6,scale=[1.]*6,beta=[0.]*6,mean=10.),error_scale=0.)
    trace=[];before=digest(info);r=trajectory(task,None,'fixed',update_fn=lc.updater(info,True,config(),trace))
    assert all(v['theta']==r[0]['theta'] for v in r) and all(v['known_damage']>.01 for v in trace)
    assert [v['decision']['action'] for v in trace]==['ask']*7+['retain']
    assert digest(info)==before and all(v['retention_mse']==0 for v in r)


def test_support_only_trace_selector_and_subset_fit_preserve_old_behavior():
    task=toy();a=ev.support_trace(task.support_x,task.support_y,task.old_x,task.old_y)
    b=ev.support_trace(task.support_x,task.support_y,task.old_x,task.old_y,selector=lambda r:True)
    assert a==b
    held=ev.support_trace(task.support_x,task.support_y,task.old_x,task.old_y,selector=lambda r:False)
    assert all(r['before']==held[0]['before'] for r in held) and held[1]['features']!=a[1]['features']
    cases={str(i):[dict(r,utility=.01*(i+1)*r['prefix']) for r in a] for i in range(9)}
    c=dict(prefixes=list(range(1,9)),predictor_ridge=1.,permutation_seed=7301)
    full=ev.fit_predictors(cases,list(range(9)),c,0);small=ev.fit_predictors(cases,list(range(9)),c,0,methods=['consistency'])
    assert small=={'consistency':full['consistency']}


def test_beneficial_toy_update_changes_only_residual_fit_and_is_reversible():
    from nexus.seed.learning_benchmark import LessonTask
    x=torch.zeros(8,33);x[:,0]=1.;old=torch.zeros(4,33);old[:,1]=1.
    task=LessonTask(x,torch.ones(8),x,torch.ones(8),old,torch.zeros(4),old,torch.zeros(4))
    info=dict(model=dict(columns=list(range(4,10)),center=[0.]*6,scale=[1.]*6,beta=[0.]*6,mean=1.),error_scale=0.)
    original=deepcopy(info);tr=[];rows=trajectory(task,None,'fixed',update_fn=lc.updater(info,True,config(),tr))
    assert all(r['decision']['action']=='learn' for r in tr)
    assert rows[-1]['query_mse']<rows[0]['query_mse'] and all(r['retention_mse']==0 for r in rows)
    assert info==original and rows[0]['theta']==[0.]*33
    installed=torch.tensor(rows[-1]['theta']);restored=torch.tensor(rows[0]['theta'])
    assert not torch.equal(installed,restored) and torch.equal(restored,torch.zeros(33))


@pytest.fixture(scope='module')
def choice_pack(synthetic_pack,synthetic_result):
    return dict(source=synthetic_pack,baseline_analysis=synthetic_result['study']['analysis'],parent_sha256=config()['parent_sha256'])


def test_query_future_and_retention_changes_cannot_change_inner_choices(choice_pack):
    c=config();meta=choice_pack['source']['frozen_folds']['0'];tasks,_,_=cum.prepare_fold(choice_pack['source'],c,0,include_bound=False)
    ids=meta['train_ids'];cases=lc.training_cases(tasks,ids,meta,'rollin');info=lc.fit_rule(cases,ids,c,0)
    a=toy();b=deepcopy(a);object.__setattr__(b,'query_y',a.query_y+999);object.__setattr__(b,'retention_y',a.retention_y-999)
    tr=[];other=[];x=trajectory(a,None,'fixed',update_fn=lc.updater(info,True,c,tr));y=trajectory(b,None,'fixed',update_fn=lc.updater(info,True,c,other))
    assert tr==other and [r['theta'] for r in x]==[r['theta'] for r in y]
    labels=b.support_y.clone();labels[4:]+=10;object.__setattr__(b,'support_y',labels)
    third=[];trajectory(b,None,'fixed',update_fn=lc.updater(info,True,c,third));assert third[:4]==tr[:4]


def test_excluded_labels_cannot_change_training_models(choice_pack):
    c=config();p=deepcopy(choice_pack['source']);meta=p['frozen_folds']['0'];train,_,_=cum.prepare_fold(p,c,0,include_bound=False)
    a=lc.training_cases(train,meta['train_ids'],meta,'rollin');model=lc.fit_rule(a,meta['train_ids'],c,0)
    for t in p['tasks']:
        if t['seed'] in meta['excluded_ids']:
            for k in ('query_y','retention_y','support_y'):t['arrays'][k]=[v+999 for v in t['arrays'][k]]
    b,_,_=cum.prepare_fold(p,c,0,include_bound=False);again=lc.training_cases(b,meta['train_ids'],meta,'rollin')
    assert a==again and model==lc.fit_rule(again,meta['train_ids'],c,0)
    a['999']=a[str(meta['train_ids'][0])]
    with pytest.raises(ValueError):lc.fit_rule(a,meta['train_ids'],c,0)


@pytest.fixture(scope='module')
def choice_result(choice_pack,tmp_path_factory):
    before=Path.cwd();os.chdir(tmp_path_factory.mktemp('choice-toy'))
    try:r=lc.run(dict(inputs=dict(study_config=config(),source_pack=choice_pack)))
    finally:os.chdir(before)
    assert lc.validate_output(r,config(),dict(cpu_s=30,updates=0),choice_pack)
    return r


def test_complete_toy_comparison_and_frozen_state(choice_result,choice_pack):
    r=choice_result['study'];assert r['declared_complete'] is True and r['frozen_before_sha256']==r['frozen_after_sha256']
    assert sum(r['analysis']['choices'].values())==96 and r['analysis']['known_anchor_cap_pass'] is True
    assert choice_result['resources']['predictor_fits']==8 and r['analysis']['fresh_validation'] is False
    assert r['analysis']['curve_means']['constant_damping']==choice_pack['baseline_analysis']['curve_means']['constant_damping']


@pytest.mark.parametrize('fault',['task','fold','method','prefix','metric','model','utility','decision','gate','frozen','nonfinite'])
def test_incomplete_or_corrupt_results_rejected(choice_result,choice_pack,fault):
    r=deepcopy(choice_result['study']);row=r['rows']['95000000']['protected_rollin'][1]
    if fault=='task':del r['rows']['95000000']
    elif fault=='fold':del r['folds']['0']
    elif fault=='method':del r['rows']['95000000']['reference_refit']
    elif fault=='prefix':r['rows']['95000000']['protected_rollin'].pop()
    elif fault=='metric':del row['known_damage']
    elif fault=='model':r['folds']['0']['models']['rollin']['model']['beta'][0]+=.1
    elif fault=='utility':r['folds']['0']['cases']['rollin']['95010000'][0]['utility']+=1
    elif fault=='decision':row['decision']['action']='bogus'
    elif fault=='gate':row['gate']=1-row['gate']
    elif fault=='frozen':r['frozen_after_sha256']='0'*64
    else:row['retention_mse']=True
    with pytest.raises((ValueError,KeyError)):lc.validate(r,config(),choice_pack)


def test_source_hash_checks_and_locked_budget():
    c=config();p=lc.source_pack(ROOT,c);assert p['parent_sha256']==c['parent_sha256']
    c['memory_damage_cap']=.02
    with pytest.raises(ValueError):lc.config_check(c)


def test_unvetted_host_manifest_rejected_before_reservation(tmp_path):
    from nexus.seed.experimental import Sandbox
    h=Sandbox(ROOT,tmp_path/'host');h.grant('toy','owner','synthetic preflight',dict(wall_s=30,cpu_s=30,memory_mb=2048,updates=0,real_steps=0,imagined_transitions=0),3600,0,memory_policy='sampled_rss')
    spec=dict(id='toy',mode='exploration',recipe=dict(adapter='seed_learning_choice_v1',config_path='configs/seed_learning_choice.json',config_sha256='a'*64,protocol_path='unlocked.md',protocol_sha256='b'*64),train=None,development=None,model_run=None,assessment=None,protocol=None,gate=None)
    with pytest.raises(ValueError,match='vetted_study_manifest'):h.execute(spec,'toy')
    assert h.records('reserved')==[]
