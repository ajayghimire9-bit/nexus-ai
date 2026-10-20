"""Synthetic question-learning contracts; no real/world/model collection."""
from copy import deepcopy
import inspect
import json
from pathlib import Path
import random
import subprocess
import sys
import pytest
from nexus.evolution1.catalogue import digest
from nexus.seed import question_utility as q
from test_seed_query_replication import replication
from test_seed_question_headroom import headroom_pack,headroom_result
from test_seed_question_selection import question_pack,question_result
from test_seed_sequential_consistency import synthetic_pack

ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/seed_question_utility.json').read_text())


@pytest.fixture(scope='module')
def utility_pack(replication,headroom_pack):
    r,old=replication;c=config();original=headroom_pack['questions']['source']['tasks']
    p=dict(parent_sha256=c['parent_sha256'],tasks={str(t['seed']):dict(arrays={k:t['arrays'][k] for k in ('support_x','support_y','old_x','old_y')},actions=list(range(8))) for t in original},
        frozen_folds=deepcopy(old['frozen_folds']),reference=deepcopy(headroom_pack['reference']),
        training_queries={t:v['selection']['arrays'] for t,v in r['queries'].items()},
        assessments={t:{b:dict(before={s:dict(check_mse=v['check_mse'],retention_mse=old['rows'][t][b]['before'][s]['retention_mse']) for s,v in cell['before'].items()},
            candidates={i:{s:dict(check_mse=v['check_mse'],retention_mse=old['rows'][t][b]['candidates'][i][s]['retention_mse']) for s,v in arms.items()} for i,arms in cell['candidates'].items()}) for b,cell in cells.items()} for t,cells in r['rows'].items()})
    assert q.validate_pack(p,c);return p


@pytest.fixture(scope='module')
def utility_result(utility_pack,tmp_path_factory):
    code='import json,sys;sys.path.insert(0,sys.argv[1]);from nexus.seed.question_utility import run;print(json.dumps(run(json.load(sys.stdin)),allow_nan=False))'
    p=subprocess.run([sys.executable,'-c',code,str(ROOT/'src')],input=json.dumps(dict(inputs=dict(study_config=config(),source_pack=utility_pack))),
        text=True,capture_output=True,check=True,cwd=tmp_path_factory.mktemp('utility-toy'),timeout=30)
    return json.loads(p.stdout)


def test_complete_synthetic_execution_and_actual_output_accounting(utility_result,utility_pack):
    r=utility_result;assert q.validate_output(r,config(),dict(cpu_s=30),utility_pack)
    assert r['study']['declared_complete'] is True and len(r['study']['folds'])==4
    assert r['resources']['cumulative_solves']==3132 and r['resources']['predictor_ridge_solves']==8
    assert r['resources']['real_steps']==r['resources']['imagined_transitions']==r['resources']['world_model_forwards']==0
    assert r['study']['frozen_before_sha256']==r['study']['frozen_after_sha256']
    assert r['study']['analysis']['learning_to_learn_established'] is False
    assert len(json.dumps(r,separators=(',',':'),allow_nan=False).encode())<10_000_000
    for f in r['study']['folds'].values():
        restored=json.loads(json.dumps(f['models']));assert q.decide(f['held_cases'],restored)==f['decisions']
        for cells in f['evaluation'].values():
            for cell in cells.values():assert cell['query_mse']['budget_mean']==cell['query_mse']['variance']
    changed=deepcopy(r);changed['resources']['training_initial_solves']-=1
    with pytest.raises(ValueError,match='utility_output_resources'):q.validate_output(changed,config(),dict(cpu_s=30),utility_pack)


def test_training_inputs_exclude_held_data_and_other_fold_constants(utility_pack):
    c=config();a=q.training_inputs(utility_pack,c,0);p=deepcopy(utility_pack)
    held=q.cum.partition(c,0)[1]
    for t in held:p['tasks'].pop(str(t));p['training_queries'].pop(str(t));p['assessments'][str(t)]={'poison':'never_visible'}
    for f in ('1','2','3'):p['frozen_folds'][f]['constants']={'poison':1}
    assert q.training_inputs(p,c,0)==a
    assert set(a[0])==set(map(str,q.cum.partition(c,0)[0]))
    assert all(t not in a[0] for t in map(str,held))


def test_query_poison_cannot_change_decisions_or_predictions(utility_result,utility_pack):
    f=utility_result['study']['folds']['0'];decision=q.decide(f['held_cases'],f['models']);poison=deepcopy(utility_pack['assessments'])
    for cells in poison.values():
        for cell in cells.values():
            for arms in [cell['before']]+list(cell['candidates'].values()):
                for v in arms.values():v['check_mse']+=999.;v['retention_mse']+=100.
    q.evaluate(decision,poison,config())
    assert decision==q.decide(f['held_cases'],f['models']) and f['models_sha256']==digest(f['models'])
    assert 'assessments' not in inspect.signature(q.decide).parameters
    assert 'query' not in str(inspect.signature(q.features))


def test_unasked_labels_cannot_change_pre_question_features(utility_pack):
    c=config();t='95000000';scale=utility_pack['frozen_folds']['0']['scale'];ref=utility_pack['reference'][t]
    task=q.scale_task(utility_pack['tasks'][t],scale);a=q.public_cases(task,ref,c)
    changed=deepcopy(task)
    for i in ref['order'][1:]:changed['arrays']['support_y'][i]+=1000
    b=q.public_cases(changed,ref,c)
    assert a['1']==b['1'] and a['2']==b['2']
    assert set(a['1']['0'])=={'index','budget','action','variance','features'}


def test_predictor_recovers_contextual_residual_on_independent_toy_inputs():
    # Same action/budget average is uninformative, contextual coordinate helps.
    c=config();cases={};train=list(range(9))
    for t in train:
        cases[str(t)]={}
        for b in c['budgets']:
            cases[str(t)][str(b)]={str(i):dict(index=i,budget=b,action=0,variance=float(i+1),features=[x]+[0.]*53,utility=2*x) for i,x in enumerate((-1.+t*.01,1.-t*.01))}
    models,perm=q.fit_models(cases,train,c,0)
    row=dict(budget=1,action=0,features=[.7]+[0.]*53)
    assert abs(q.predict(models['learned'],'learned',row)-1.4)<.02
    assert abs(q.predict(models['action_mean'],'action_mean',row)-1.4)>1.
    assert q.fit_models(cases,train,c,0)==(models,perm)
    random.seed(999);random.random();assert q.fit_models(cases,train,c,0)==(models,perm)
    assert models['learned']['beta']!=models['shuffled_residual']['beta']


def test_mean_baseline_fallback_and_deterministic_ties():
    model=dict(action_means={'1/0':.5},budget_means={'1':.2});assert q.mean_prediction(model,dict(budget=1,action=8))==.2
    rows={'2':{'variance':1.},'1':{'variance':1.},'0':{'variance':.5}}
    assert q.choose(rows,dict.fromkeys(rows,0.))==1
    with pytest.raises(ValueError):q.choose(rows,{'2':0.})
    with pytest.raises(ValueError):q.choose(rows,dict.fromkeys(rows,True))


def test_saved_lock_required_and_exact(tmp_path):
    path=tmp_path/'lock.json';lock=dict(models={'0':'frozen'},decisions={'0':{'question':2}})
    with pytest.raises(ValueError):q.require_lock(path,lock)
    path.write_text(json.dumps(lock));q.require_lock(path,lock)
    tampered=deepcopy(lock);tampered['decisions']['0']['question']=3
    with pytest.raises(ValueError):q.require_lock(path,tampered)


@pytest.mark.parametrize('fault',['fold','train_task','held_task','budget','candidate','fit','prefix','feature','label','beta','scale','decision','method','nan','infinity','boolean','string','lock','frozen'])
def test_complete_grid_and_numeric_rejections(utility_result,utility_pack,fault):
    r=deepcopy(utility_result['study']);f=r['folds']['0'];tid=str(f['train_ids'][0]);hid=str(f['excluded_ids'][0]);row=next(iter(f['training_cases'][tid]['1'].values()))
    if fault=='fold':del r['folds']['0']
    elif fault=='train_task':del f['training_cases'][tid]
    elif fault=='held_task':del f['held_cases'][hid]
    elif fault=='budget':del f['held_cases'][hid]['4']
    elif fault=='candidate':f['training_cases'][tid]['1'].pop(next(iter(f['training_cases'][tid]['1'])))
    elif fault=='fit':next(iter(f['training_fits'][tid]['1'].values())).pop('7201')
    elif fault=='prefix':f['training_references'][tid]['paths']['7201'].pop()
    elif fault=='feature':row['features'][0]+=.5
    elif fault=='label':row['utility']+=.1
    elif fault=='beta':f['models']['learned']['beta'][0]+=.1
    elif fault=='scale':f['models']['learned']['scale'][0]*=2
    elif fault=='decision':f['decisions'][hid]['1']['choices']['learned']=99
    elif fault=='method':del f['models']['action_mean']
    elif fault=='nan':row['utility']=float('nan')
    elif fault=='infinity':row['features'][0]=float('inf')
    elif fault=='boolean':row['features'][0]=True
    elif fault=='string':row['variance']='1'
    elif fault=='lock':r['locked_before_evaluation']=False
    elif fault=='frozen':r['frozen_after_sha256']='changed'
    with pytest.raises((ValueError,KeyError)):q.validate(r,config(),utility_pack)


def test_source_preflight_is_stdlib_only_and_hash_verified():
    code='import json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.question_utility import source_pack;c=json.load(open(Path(sys.argv[2])/"configs/seed_question_utility.json"));p=source_pack(Path(sys.argv[2]),c);assert len(p["tasks"])==12;assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True,timeout=30)
    c=config();c['parent_sha256']='0'*64
    with pytest.raises(ValueError,match='utility_parent_hash'):q.source_pack(ROOT,c)


def test_verifier_imports_under_isolated_stdlib_python():
    code='import runpy,sys;r=runpy.run_path(sys.argv[1],run_name="import_only");assert callable(r["verify"]);assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'scripts/verify_seed_question_utility.py')],check=True,timeout=10)


@pytest.mark.parametrize('k,v',[('budgets',[1,2,4]),('feature_width',53),('ridge',.1),('max_wall_s',31),('minimum_fraction',0.),('constant_seeds',[7201]),('fold_count',3)])
def test_locked_recipe_cannot_change_after_results(k,v):
    c=config();c[k]=v
    with pytest.raises(ValueError):q.config_check(c)
