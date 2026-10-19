"""Synthetic-only fitting until the protocol commit; never real collection."""
import copy
import importlib.util
import itertools
import json
from pathlib import Path

import numpy as np
import pytest

from nexus.evolution1.catalogue import digest
from nexus.evolution2.generated_strategies import AdvantagePredictor
from nexus.evolution2.planner_quality_diagnostic import fit_ridge,predict_ridge
from nexus.evolution2 import training_feedback_audit as a
from nexus.evolution2.full_policy_source import ROOT


def toy():
    bank=[];features=[]
    for f,b,e in itertools.product(a.FAMILIES,a.BUNDLES,range(9)):
        public=dict(family=f,model_bundle=b,episode=e,initial_obs=[float(e-4)]*(3 if f=='pendulum' else 6))
        values=dict(successor_anchor=-200.,rank_blend=-200.+80*b-40+10*(e-4))
        bank.append(dict(public=public,returns=values,advantage=values['rank_blend']-values['successor_anchor'],
            event=digest(dict(public=public,returns=values,reset_seed=2113000000+a.FAMILIES.index(f)*10000+b*100+e))))
    means=a.anchor_means(bank)
    for row in bank:
        f,b,e=a.identity(row);task=np.r_[1.,float(e-4),np.zeros(8),[means[f'{f}:{b}'][k]/100. for k in a.CONTROLLERS]]
        features.append(np.outer(task,np.r_[1.,.5,np.zeros(14)]).ravel().tolist())
    return bank,features


def folds(bank,x):return [a.predict_fold(bank,x,e,profile='e3_5') for e in range(9)]


def test_zero_baseline_preserves_original_direct_ridge():
    x=[[1.,v] for v in (-2.,0.,1.,3.)];y=[-4.,1.,2.,8.]
    m=AdvantagePredictor()
    for i,(v,target) in enumerate(zip(x,y)):m.observe(v,target,event=str(i),provenance='revealed_source')
    expected=fit_ridge(x,y)
    assert m.predict([1.,2.])==pytest.approx(predict_ridge(expected,[1.,2.]),abs=1e-12)
    np.testing.assert_array_equal(m.model[0],expected[0]);np.testing.assert_array_equal(m.model[1],expected[1])


def test_zero_residual_is_exact_mean_and_empty_model_retains_prior():
    m=AdvantagePredictor();assert m.predict([1.,99.],baseline=12.5)==12.5
    for i,prior in enumerate((100.,-50.,25.)):
        m.observe([1.,float(i)],prior,baseline=prior,event=str(i),provenance='revealed_source')
    assert m.y==[0.,0.,0.]
    assert m.predict([1.,900.],baseline=-123.)==-123.


def test_informative_context_residual_improves_independent_toy_prediction():
    m=AdvantagePredictor()
    for i,x in enumerate((-2.,-1.,0.,1.,2.)):
        prior=100. if i%2 else -100.
        m.observe([1.,x],prior+5*x,baseline=prior,event=str(i),provenance='revealed_source')
    assert m.y==[-10.,-5.,0.,5.,10.]
    predictions=[m.predict([1.,x],baseline=200.) for x in (-1.5,1.5)]
    truth=np.array([192.5,207.5]);assert np.mean(np.abs(predictions-truth))<7.5
    assert predictions[0]<200.<predictions[1] and m.fit_calls==1


@pytest.mark.parametrize('baseline',[True,'0',float('nan'),float('inf')])
def test_invalid_baselines_do_not_modify_feedback_state(baseline):
    m=AdvantagePredictor()
    with pytest.raises(ValueError):m.observe([1.],2.,baseline=baseline,event='x',provenance='revealed_source')
    with pytest.raises(ValueError):m.predict([1.],baseline=baseline)
    assert not m.x and not m.y and not m.events


def test_overflowing_residual_is_rejected_before_update():
    m=AdvantagePredictor()
    with pytest.raises(ValueError,match='finite_residual'):m.observe([1.],1e308,baseline=-1e308,event='x',provenance='revealed_source')
    assert not m.x and not m.events


def test_all_fold_statistics_exclude_heldout_outcomes():
    bank,x=toy();original=a.predict_fold(bank,x,4,profile='e3_5')
    modified=copy.deepcopy(bank)
    for row in modified:
        if row['public']['episode']==4:row['returns']['rank_blend']=999999.;row['advantage']=1000199.;row['event']='forbidden_query_label'
    assert a.predict_fold(modified,x,4,profile='e3_5')==original
    poisoned=copy.deepcopy(x)
    for row in poisoned:row[160:]=[1e10]*32
    assert a.predict_fold(bank,poisoned,4,profile='e3_5')==original


def test_residual_targets_means_scaling_and_queries_are_separate():
    bank,x=toy();assert a.validate_bank(bank,x,'e3_5');f=a.predict_fold(bank,x,2,profile='e3_5')
    assert len(f['train_ids'])==32 and len(f['query_ids'])==4
    assert not set(map(tuple,f['train_ids']))&set(map(tuple,f['query_ids']))
    rows=[row for row in bank if row['public']['episode']!=2]
    for i,row in enumerate(rows):
        family,b,_=a.identity(row);v=f['anchor_means'][f'{family}:{b}'];mu=v['rank_blend']-v['successor_anchor']
        assert f['training_targets']['residual_predictor'][i]==row['advantage']-mu
    for family,b in itertools.product(a.FAMILIES,a.BUNDLES):
        positions=[i for i,row in enumerate(rows) if a.identity(row)[:2]==(family,b)]
        assert sum(f['training_targets']['residual_predictor'][i] for i in positions)==pytest.approx(0.,abs=1e-10)
    assert f['training_targets']['shuffled_residual']==[f['training_targets']['residual_predictor'][i] for i in f['shuffle_permutation']]
    assert all(v['fit_calls']==1 and len(v['beta'])==192 for v in f['models'].values())


def test_deterministic_frozen_replay_requires_no_fits(monkeypatch):
    bank,x=toy();first=folds(bank,x);assert first==folds(bank,x)
    def forbidden(*args,**kwargs):raise AssertionError('no_refit')
    monkeypatch.setattr(a.AdvantagePredictor,'observe',forbidden)
    result=a.verify_frozen_folds(first,bank,x,'e3_5')
    assert len(result['raw'])==36 and result['independent_models_per_family']==2
    for row in result['raw']:
        assert row['regret']['residual_predictor']-row['regret']['model_mean']==pytest.approx(row['returns']['model_mean']-row['returns']['residual_predictor'])


@pytest.mark.parametrize('bad',['model','episode','evaluation','duplicate','bool','string','nan','feature','receipt'])
def test_training_input_is_exact_finite_grid(bad):
    bank,x=toy()
    if bad=='model':bank=[row for row in bank if row['public']['model_bundle']!=1]
    if bad=='episode':bank.pop()
    if bad=='evaluation':bank[0]['public']['episode']=9
    if bad=='duplicate':bank[-1]=copy.deepcopy(bank[0])
    if bad=='bool':bank[0]['returns']['rank_blend']=True
    if bad=='string':x[0][0]='1'
    if bad=='nan':x[0][0]=float('nan')
    if bad=='feature':x[0].pop()
    if bad=='receipt':bank[0]['event']='forged'
    with pytest.raises(ValueError):a.validate_bank(bank,x,'e3_5')


@pytest.mark.parametrize('bad',['fold','model','condition','row','nan','bool_fold','bool_target','scaling','prior','target','coefficient','correction','ids'])
def test_incomplete_or_corrupt_frozen_result_is_rejected(bad):
    bank,x=toy();f=folds(bank,x)
    if bad=='fold':f.pop()
    if bad=='model':f[0]['models'].pop('residual_predictor')
    if bad=='condition':f[0]['predictions'][0]['choices'].pop('residual_predictor')
    if bad=='row':f[0]['predictions'].pop()
    if bad=='nan':f[0]['predictions'][0]['estimates']['residual_predictor']=float('nan')
    if bad=='bool_fold':f[0]['held_out']=False
    if bad=='bool_target':f[0]['training_targets']['residual_predictor'][0]=False
    if bad=='scaling':f[0]['models']['residual_predictor']['scale'][0]+=1
    if bad=='prior':f[0]['predictions'][0]['prior_mean']+=1
    if bad=='target':f[0]['training_targets']['residual_predictor'][0]+=1
    if bad=='coefficient':f[0]['models']['residual_predictor']['beta'][0]+=1
    if bad=='correction':f[0]['predictions'][0]['residual_corrections']['residual_predictor']+=1
    if bad=='ids':f[0]['train_ids'][0][-1]=0
    with pytest.raises(ValueError):a.verify_frozen_folds(f,bank,x,'e3_5')


def test_missing_feedback_budget_stops_before_fitting():
    bank,x=toy();events=[]
    def guard(stage):
        events.append(stage)
        if stage=='reserve':raise TimeoutError('synthetic_cap')
    with pytest.raises(TimeoutError):a.predict_fold(bank,x,0,fit_guard=guard,profile='e3_5')
    assert events==['reserve']


def runner():
    spec=importlib.util.spec_from_file_location('residual_runner',ROOT/'scripts/run_e3_3_training_feedback_audit.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.configure_residual();return module


def test_locked_runner_config_one_run_and_thread_guards(tmp_path,monkeypatch):
    m=runner();c=json.loads(m.CONFIG.read_text());m.validate_config(c)
    altered=copy.deepcopy(c);altered['ridge']=.5
    with pytest.raises(ValueError):m.validate_config(altered)
    monkeypatch.setattr(m,'RESULT',tmp_path/'result.json');monkeypatch.setattr(m,'FROZEN',tmp_path/'frozen.json')
    marker=tmp_path/'used.json';marker.write_text('{}');monkeypatch.setattr(m,'USAGE',marker)
    with pytest.raises(FileExistsError):m.run(c)
    marker.unlink();monkeypatch.delenv('OPENBLAS_NUM_THREADS',raising=False)
    with pytest.raises(ValueError,match='thread'):m.run(c)


def test_zero_residual_and_means_are_dependent_controls():
    bank,x=toy()
    for row in bank:
        row['advantage']=80*row['public']['model_bundle']-40.
        row['returns']['rank_blend']=row['returns']['successor_anchor']+row['advantage']
    result=a.score_predictions(folds(bank,x),bank,'e3_5')
    assert not result['point_screen']
    for row in result['raw']:assert row['returns']['residual_predictor']==row['returns']['model_mean']
