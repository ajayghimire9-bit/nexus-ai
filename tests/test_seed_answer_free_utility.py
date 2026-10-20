"""Arithmetic fixtures only. Never run the real source-bank experiment in tests."""
from copy import deepcopy
import inspect
import json
from pathlib import Path
import statistics as st
import subprocess
import sys
import pytest
from nexus.evolution1.catalogue import digest
from nexus.seed import answer_free_utility as q
from test_seed_question_utility import utility_pack
from test_seed_query_replication import replication
from test_seed_question_headroom import headroom_pack,headroom_result
from test_seed_question_selection import question_pack,question_result
from test_seed_sequential_consistency import synthetic_pack

ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/seed_answer_free_utility.json').read_text())


@pytest.fixture(scope='module')
def pack(utility_pack,replication,headroom_pack):
    p=deepcopy(utility_pack);r,old=replication
    p['cached_fits']=deepcopy(old['rows'])
    tasks=headroom_pack['questions']['source']['tasks']
    p['evaluator']={str(t['seed']):dict(check=r['queries'][str(t['seed'])]['check']['arrays'],
        retention={k:t['arrays'][k] for k in ('retention_x','retention_y')}) for t in tasks}
    return p


@pytest.fixture(scope='module')
def result(pack,tmp_path_factory):
    code='import json,sys;sys.path.insert(0,sys.argv[1]);from nexus.seed.answer_free_utility import run;print(json.dumps(run(json.load(sys.stdin)),allow_nan=False))'
    proc=subprocess.run([sys.executable,'-c',code,str(ROOT/'src')],input=json.dumps(dict(inputs=dict(study_config=config(),source_pack=pack))),text=True,capture_output=True,cwd=tmp_path_factory.mktemp('answerfree'),timeout=60)
    assert proc.returncode==0,proc.stderr
    return json.loads(proc.stdout)


def test_complete_fixture_grid_counts_and_frozen_state(result,pack):
    assert q.validate_output(result,config(),{'cpu_s':60},pack)
    assert result['study']['declared_complete']
    assert len(json.dumps(result,allow_nan=False))<10_000_000
    assert result['resources']['predictor_coefficients']==44
    assert result['resources']['predictor_ridge_solves']==4
    assert result['resources']['world_model_forwards']==result['resources']['real_steps']==0
    for f in result['study']['folds'].values():
        for bs in f['evaluation'].values():
            for b,v in bs.items():
                assert v['query_mse']['original_order']==v['query_mse']['source_mean']
                assert all(z['labels']==int(b) for z in v['reveals'].values())


def test_hidden_answers_and_assessment_poison_cannot_change_features_or_choices(result,pack):
    f=result['study']['folds']['0'];t=str(f['excluded_ids'][0]);ref=pack['reference'][t]
    task=q.base.scale_task(pack['tasks'][t],pack['frozen_folds']['0']['scale'])
    for budget in config()['budgets']:
        a=q.public_cases(task,ref,config())[str(budget)];changed=deepcopy(task)
        for i in ref['order'][budget-1:]:changed['arrays']['support_y'][i]+=999
        b=q.public_cases(changed,ref,config())[str(budget)]
        assert a==b
        assert q.decide({t:{str(budget):a}},f['model'])==q.decide({t:{str(budget):b}},f['model'])
    decision=q.decide(f['held_cases'],f['model']);p=deepcopy(pack)
    p['evaluator']={'poison':'unavailable'};p['assessments']={'poison':'unavailable'}
    assert decision==q.decide(f['held_cases'],f['model'])
    assert list(inspect.signature(q.features).parameters)==['candidate','anchors','anchor_y','observed_x','observed_y','thetas','variance','remaining']
    assert len(q.FEATURES)==10


def test_held_data_cannot_change_fitter_or_preprocessing(result,pack):
    c=config();inputs=q.base.training_inputs(pack,c,0);p=deepcopy(pack)
    for t in result['study']['folds']['0']['excluded_ids']:
        for key in ('tasks','training_queries','assessments','evaluator','cached_fits'):p[key].pop(str(t))
    for f in ('1','2','3'):p['frozen_folds'][f]['constants']={'poison':999}
    assert q.base.training_inputs(p,c,0)==inputs
    # Same permitted fixture cases give exactly the same coefficients and scales.
    f=result['study']['folds']['0'];assert q.fit(f['training_cases'],inputs[2]['train_ids'],c)==f['model']


def test_informative_toy_utility_and_fixed_training_only_scaling():
    c=config();cases={str(t):{str(b):{str(i):dict(features=[x]+[0.]*9,utility=2*x,index=i,budget=b,variance=1.) for i,x in enumerate((-.9+t*.01,.9-t*.01))} for b in c['budgets']} for t in range(9)}
    m=q.fit(cases,list(range(9)),c)
    assert abs(q.predict(m,dict(features=[.6]+[0.]*9))-1.2)<.02
    assert q.fit(cases,list(range(9)),c)==m


def test_primary_aggregation_excludes_singleton_and_independent_interval(result):
    r=deepcopy(result['study']);a=q.summarize(r['folds'],config())
    for f in r['folds'].values():
        for cells in f['evaluation'].values():cells['8']['query_mse']['learned']+=1000
    assert q.summarize(r['folds'],config())['primary_means']==a['primary_means']
    for m in ('variance','keep'):
        values=[a['per_task'][str(t)][m]-a['per_task'][str(t)]['learned'] for t in config()['tasks']['train']]
        half=2.200985160*st.stdev(values)/12**.5
        assert a['contrasts'][m]['mean']==st.mean(values)
        assert a['contrasts'][m]['ci95']==pytest.approx([st.mean(values)-half,st.mean(values)+half],abs=1e-15)


@pytest.mark.parametrize('fault',['fold','task','held','budget','candidate','seed','feature','beta','nan','bool','string','choice','lock','cache'])
def test_incomplete_or_invalid_grid_rejected(result,pack,fault):
    r=deepcopy(result['study']);p=deepcopy(pack);f=r['folds']['0'];t=str(f['train_ids'][0]);h=str(f['excluded_ids'][0]);row=next(iter(f['training_cases'][t]['1'].values()))
    if fault=='fold':r['folds'].pop('0')
    elif fault=='task':f['training_cases'].pop(t)
    elif fault=='held':f['held_cases'].pop(h)
    elif fault=='budget':f['held_cases'][h].pop('4')
    elif fault=='candidate':f['training_cases'][t]['1'].pop(next(iter(f['training_cases'][t]['1'])))
    elif fault=='seed':next(iter(f['training_fits'][t]['1'].values())).pop('7201')
    elif fault=='feature':row['features'][0]+=.1
    elif fault=='beta':f['model']['beta'][0]+=.1
    elif fault=='nan':row['features'][0]=float('nan')
    elif fault=='bool':row['variance']=True
    elif fault=='string':row['variance']='1'
    elif fault=='choice':f['decisions'][h]['1']['choices']['learned']=99
    elif fault=='lock':r['locked_before_evaluation']=False
    elif fault=='cache':p['assessments'][h]['1']['before']['7201']['check_mse']+=.1
    with pytest.raises((ValueError,KeyError)):q.validate(r,config(),p)


def test_label_budget_and_persisted_lock(tmp_path):
    oracle=q.qs.LabelOracle(list(range(8)),2);oracle.reveal(0);oracle.reveal(1)
    with pytest.raises(ValueError):oracle.reveal(2)
    lock={'models':{'0':'frozen'}};path=tmp_path/'lock.json'
    with pytest.raises(ValueError):q.base.require_lock(path,lock)
    path.write_text(json.dumps(lock));q.base.require_lock(path,lock)


def test_source_hash_audit_without_optional_libraries():
    code='import json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.answer_free_utility import source_pack;r=Path(sys.argv[2]);p=source_pack(r,json.load(open(r/"configs/seed_answer_free_utility.json")));assert len(p["tasks"])==12;assert "torch" not in sys.modules and "numpy" not in sys.modules'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True,timeout=30)
