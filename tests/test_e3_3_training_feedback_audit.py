"""Synthetic-only fitting tests; no research input scoring before protocol lock."""
import copy
import importlib.util
import itertools
import json

import numpy as np
import pytest

from nexus.evolution1.catalogue import digest
from nexus.evolution2 import training_feedback_audit as a
from nexus.evolution2.generated_strategies import advantage_features
from nexus.evolution2.return_feedback import FrozenReturnSelector
from nexus.evolution2.full_policy_source import ROOT,controllers
from nexus.evolution2.observation_memory import FamilyNormalizer
from nexus.core.strategy_memory import SupportBatch
from nexus.core.strategy_memory_decide_bench import family_context


def toy():
    bank=[];raw=[]
    for f,b,e in itertools.product(a.FAMILIES,a.BUNDLES,a.EPISODES):
        p=dict(family=f,model_bundle=b,episode=e,initial_obs=[float(e-1)]*(3 if f=='pendulum' else 6))
        values=dict(successor_anchor=-200.,rank_blend=-200.+100*(e-1)+20*b)
        bank.append(dict(public=p,returns=values,advantage=values['rank_blend']-values['successor_anchor'],
            event=digest(dict(public=p,returns=values,reset_seed=2111000000+a.FAMILIES.index(f)*10000+b*100+e))))
    means=a.anchor_means(bank)
    for r in bank:
        f,b,e=a.identity(r);task=np.r_[1.,float(e-1),np.zeros(8),[means[f'{f}:{b}'][k]/100. for k in a.CONTROLLERS]]
        arm=np.r_[1.,.5,np.zeros(14)];raw.append(np.outer(task,arm).ravel().tolist())
    return bank,raw


def folds(bank,x):return [a.predict_fold(bank,x,e) for e in a.EPISODES]


def test_complete_reproducible_learning_and_no_refit_audit(monkeypatch):
    bank,x=toy();assert a.validate_bank(bank,x)
    first=folds(bank,x);assert first==folds(bank,x)
    def forbidden(*args,**kwargs):raise AssertionError('verification_refit')
    monkeypatch.setattr(a.AdvantagePredictor,'observe',forbidden)
    result=a.verify_frozen_folds(first,bank,x)
    assert result['by_family']['pendulum']['advantage_mae']['quality_predictor']<result['by_family']['pendulum']['advantage_mae']['model_mean']
    assert [m['fit_calls'] for f in first for m in f['models'].values()]==[1]*6


def test_query_labels_do_not_change_any_fold_prediction_or_weight():
    bank,x=toy();original=a.predict_fold(bank,x,1)
    mutated=copy.deepcopy(bank)
    for row in mutated:
        if row['public']['episode']==1:row['returns']['rank_blend']=99999.;row['advantage']=100199.;row['event']='ignored_query_event'
    assert a.predict_fold(mutated,x,1)==original


def test_heldout_anchor_blocks_and_scaling_cannot_leak():
    bank,x=toy();first=a.predict_fold(bank,x,1)
    changed=copy.deepcopy(x)
    for v in changed:v[160:]=[1000000.]*32
    assert a.predict_fold(bank,changed,1)==first
    assert all(len(f['train_ids'])==8 and len(f['query_ids'])==4 for f in folds(bank,x))
    assert not set(map(tuple,first['train_ids']))&set(map(tuple,first['query_ids']))


@pytest.mark.parametrize('family,size',[('pendulum',3),('acrobot',6)])
def test_anchor_rebuild_matches_existing_feature_function(family,size):
    obs=np.linspace(.1,.5,size);hist=np.arange(32*size).reshape(32,size)/100.
    support=SupportBatch(hist,np.arange(32)%3,hist+.01,np.zeros(32))
    context=family_context(family);norm=FamilyNormalizer.fit(family,hist)
    def feature(anchors):
        return advantage_features(controllers()['rank_blend'],obs,support,context,norm,anchors)-advantage_features(controllers()['successor_anchor'],obs,support,context,norm,anchors)
    rebuilt=a.fold_features(feature((-2.,-1.)),dict(successor_anchor=-375.,rank_blend=-250.))
    np.testing.assert_allclose(rebuilt,feature((-3.75,-2.5)),rtol=1e-12,atol=1e-12)


@pytest.mark.parametrize('bad',['seed','episode','duplicate','heldout','bool','string','nan','inf','feature','receipt'])
def test_exact_training_schema_rejects_missing_or_invalid(bad):
    bank,x=toy()
    if bad=='seed':bank=bank[3:];x=x[3:]
    if bad=='episode':bank=[r for r in bank if r['public']['episode']!=1]
    if bad=='duplicate':bank[-1]=copy.deepcopy(bank[0])
    if bad=='heldout':bank[0]['public']['episode']=3
    if bad=='bool':bank[0]['returns']['rank_blend']=True
    if bad=='string':x[0][0]='1.0'
    if bad=='nan':bank[0]['advantage']=float('nan')
    if bad=='inf':x[0][0]=float('inf')
    if bad=='feature':x[0]=x[0][:-1]
    if bad=='receipt':bank[0]['event']='forged'
    with pytest.raises(ValueError):a.validate_bank(bank,x)


@pytest.mark.parametrize('bad',['fold','model','condition','row','nan','bool','scaling','anchors','coefficients','choice','train_ids'])
def test_complete_result_and_independent_arithmetic_rejects(bad):
    bank,x=toy();f=folds(bank,x)
    if bad=='fold':f.pop()
    if bad=='model':f[0]['models'].pop('quality_predictor')
    if bad=='condition':f[0]['predictions'][0]['choices'].pop('uniform')
    if bad=='row':f[0]['predictions'].pop()
    if bad=='nan':f[0]['predictions'][0]['estimates']['model_mean']=float('nan')
    if bad=='bool':f[0]['predictions'][0]['public']['model_bundle']=True
    if bad=='scaling':f[0]['models']['quality_predictor']['scale'][0]+=1
    if bad=='anchors':f[0]['anchor_means']['pendulum:0']['rank_blend']+=1
    if bad=='coefficients':f[0]['models']['quality_predictor']['beta'][0]+=1
    if bad=='choice':f[0]['predictions'][0]['choices']['always_rank_blend']='successor_anchor'
    if bad=='train_ids':f[0]['train_ids'][0][-1]=0
    with pytest.raises(ValueError):a.verify_frozen_folds(f,bank,x)


def test_all_selectors_can_tie_and_screen_can_fail():
    bank,x=toy()
    for r in bank:
        r['returns']['rank_blend']=r['returns']['successor_anchor'];r['advantage']=0.
    f=folds(bank,x);result=a.score_predictions(f,bank)
    assert not result['point_screen']
    assert all(v==0. for v in result['by_family']['pendulum']['predictor_minus_baselines'].values())
    for row in result['raw']:
        assert row['regret']['quality_predictor']-row['regret']['model_mean']==pytest.approx(row['returns']['model_mean']-row['returns']['quality_predictor'])


def test_fit_failure_is_reserved_not_free():
    bank,x=toy();events=[]
    def guard(stage):
        events.append(stage)
        if stage=='reserve':raise TimeoutError('synthetic_budget_stop')
    with pytest.raises(TimeoutError):a.predict_fold(bank,x,0,fit_guard=guard)
    assert events==['reserve']


def test_runner_refuses_changed_config_and_used_marker(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('e3_3_runner',ROOT/'scripts/run_e3_3_training_feedback_audit.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    c=json.loads(runner.CONFIG.read_text());runner.validate_config(c)
    wrong=copy.deepcopy(c);wrong['ridge']=.1
    with pytest.raises(ValueError):runner.validate_config(wrong)
    marker=tmp_path/'used.json';marker.write_text('{}');monkeypatch.setattr(runner,'USAGE',marker)
    with pytest.raises(FileExistsError):runner.run(c)


def test_scoring_averages_resets_inside_models():
    bank,x=toy();f=folds(bank,x);result=a.score_predictions(f,bank)
    assert result['independent_models_per_family']==2 and not result['folds_are_independent_models']
    for family in a.FAMILIES:
        by=result['by_family'][family]
        for m in a.METHODS:
            assert by['mean_returns'][m]==pytest.approx(np.mean([by['per_model_returns'][str(b)][m] for b in a.BUNDLES]))
