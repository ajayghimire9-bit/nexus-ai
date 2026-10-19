"""Source-only regression: no simulator construction or learned inference."""
import copy
import itertools
import json

import numpy as np
import pytest

from nexus.core.strategy_memory import SupportBatch
from nexus.evolution1.catalogue import digest
from nexus.evolution1.resources import Work
from nexus.evolution2 import full_policy_source as h
from nexus.evolution2 import return_feedback as r


def capture():
    c=json.loads((h.ROOT/'configs/e3_2_return_feedback.json').read_text());rows=[]
    for f,b,e,k in itertools.product(c['families'],c['model_bundles'],c['episodes'],c['controllers']):
        reset,base=h.seeds(c,f,b,e);obs=[float(e)/10+b]*(3 if f=='pendulum' else 6)
        reward=-1. if k=='successor_anchor' else -0.5-b
        steps=[dict(tick=t,reward=reward,obs=obs.copy(),next_obs=obs.copy(),action=1,planner_seed=base+t,
                    terminated=False,truncated=t==199) for t in range(200)]
        rows.append(dict(family=f,model_bundle=b,episode=e,controller=k,reset_seed=reset,planner_base=base,
            initial_obs_hash=digest(obs),steps=steps,split='training' if e<3 else 'evaluation',**{'return':reward*200}))
    return c,dict(episodes=rows,resources=dict(completed=Work(real_steps=11200).payload(),unknown_upper=Work().payload()))


@pytest.fixture
def mocked_source(monkeypatch):
    def source(f,bundles):return np.arange(24*(3 if f=='pendulum' else 6)).reshape(24,-1)/100.
    def support(f,b,start,n):
        size=3 if f=='pendulum' else 6
        x=np.arange(n*size).reshape(n,size)/100.+b
        return SupportBatch(x,np.arange(n)%3,x+.01,np.zeros(n))
    monkeypatch.setattr(r,'load_source_train_obs',source);monkeypatch.setattr(r,'support_from_source',support)


def fit(c,p):
    selector=r.FrozenReturnSelector(c,persist=False)
    selector.fit([x for x in p['episodes'] if x['split']=='training']);return selector


def decisions(selector,p,c):
    for i,(f,b,e) in enumerate(itertools.product(c['families'],c['model_bundles'],range(3,7))):
        row=next(x for x in p['episodes'] if (x['family'],x['model_bundle'],x['episode'])==(f,b,e))
        selector.decide(dict(family=f,model_bundle=b,episode=e,initial_obs=row['steps'][0]['obs'],completed_real_steps=4800+i*400))
    p['selection_decisions']=selector.records


def test_frozen_replay_and_feedback_learning(mocked_source):
    c,p=capture();a=fit(c,p);decisions(a,p,c)
    assert a.manifest['feature_dimension']==192
    b=r.FrozenReturnSelector.restore(c,a.manifest);decisions(b,copy.deepcopy(p),c)
    assert a.records==b.records and a.learned_hash()==b.learned_hash()
    assert all(m.fit_calls==1 for m in b.predictors.values())
    assert a.records[0]['choices']['quality_predictor']!=a.records[4]['choices']['quality_predictor']
    changed=copy.deepcopy(p)
    for row in changed['episodes']:
        if row['split']=='training' and row['controller']=='rank_blend':
            for s in row['steps']:s['reward']=-2.
            row['return']=-400.
    assert fit(c,changed).learned_hash()!=a.learned_hash()
    with pytest.raises(RuntimeError):a.fit([])
    with pytest.raises(RuntimeError):r.FrozenReturnSelector(c,False).decide({})


def test_manifest_saved_before_choices_and_tamper_rejected(mocked_source,monkeypatch,tmp_path):
    monkeypatch.setattr(r,'MANIFEST',tmp_path/'weights.json');monkeypatch.setattr(r,'PREDICTIONS',tmp_path/'choices.jsonl')
    c,p=capture();a=r.FrozenReturnSelector(c);a.fit([x for x in p['episodes'] if x['split']=='training'])
    assert h.sha(r.MANIFEST)==a.manifest_sha and not r.PREDICTIONS.read_text()
    original=r.MANIFEST.read_text();r.MANIFEST.write_text(original+' ')
    with pytest.raises(ValueError,match='manifest_changed'):
        a.decide(dict(family='pendulum',model_bundle=0,episode=3,initial_obs=[0,0,0],completed_real_steps=4800))
    r.MANIFEST.write_text(original)
    decisions(a,p,c);assert len(r.PREDICTIONS.read_text().splitlines())==16
    with pytest.raises(ValueError):a.decide({k:a.records[0][k] for k in ('family','model_bundle','episode','initial_obs','completed_real_steps')})
    with pytest.raises(ValueError):a.features(dict(family='pendulum',model_bundle=0,initial_obs=[0,0,0],return_=1))


@pytest.mark.parametrize('bad',['missing','evaluation','oldseed','nan','short'])
def test_reject_unrevealed_closed_or_incomplete_training(bad):
    c,p=capture();rows=[x for x in p['episodes'] if x['split']=='training']
    if bad=='missing':rows=rows[1:]
    if bad=='evaluation':rows[0]['split']='evaluation'
    if bad=='oldseed':rows[0]['reset_seed']-=100000
    if bad=='nan':rows[0]['return']=float('nan')
    if bad=='short':rows[0]['steps'].pop()
    with pytest.raises(ValueError):r.paired_training(rows,c)


def test_test_returns_cannot_change_fitted_predictor(mocked_source):
    c,p=capture();a=fit(c,p)
    for row in p['episodes']:
        if row['split']=='evaluation':row['return']=-999999.
    assert fit(c,p).learned_hash()==a.learned_hash()


def test_seeds_jobs_and_hook_requirements():
    c,p=capture();assert len(h.requested_seeds(c))==5628
    jobs=h.model_jobs(c,[1,2,3,4]);assert [x[1] for x in jobs]==['training']*4+['evaluation']*4
    with pytest.raises(ValueError,match='feedback_hooks_required'):h.run(c)
    for name in ('unified_full_policy_source.json','unified_full_policy_replication.json','unified_crossed_reset.json'):
        old=json.loads((h.ROOT/'configs'/name).read_text());assert not h.requested_seeds(c)&h.requested_seeds(old)
    c['episodes']=[0]
    with pytest.raises(ValueError):h.validate_config(c)


def test_aggregation_regret_dependency_and_primary_grid(mocked_source):
    c,p=capture();a=fit(c,p);decisions(a,p,c);result=r.analyze_selection(p,c)
    assert result['independent_model_count_per_family']==2
    for f,v in result['by_family'].items():
        assert v['mean_returns']['model_mean']==-150.
        assert not result['point_screen_by_family'][f]
    for v in result['outcomes']:
        for m in r.METHODS:
            assert v['regret'][m]-v['regret']['model_mean']==pytest.approx(v['returns']['model_mean']-v['returns'][m])


@pytest.mark.parametrize('bad',['model','decision','method','count','nan','phase'])
def test_missing_or_invalid_primary_cells_rejected(mocked_source,bad):
    c,p=capture();a=fit(c,p);decisions(a,p,c)
    if bad=='model':p['episodes']=[x for x in p['episodes'] if x['model_bundle']!=0]
    if bad=='decision':p['selection_decisions'].pop()
    if bad=='method':p['selection_decisions'][0]['choices'].pop('uniform')
    if bad=='count':p['selection_decisions'][0]['completed_real_steps']=0
    if bad=='nan':p['selection_decisions'][0]['estimates']['model_mean']=float('nan')
    if bad=='phase':p['episodes'][0]['split']='evaluation'
    with pytest.raises(ValueError):r.analyze_selection(p,c)


def test_saved_capture_reconciles_repository_only():
    p=json.loads((h.ROOT/'artifacts/e3_2_return_feedback.json').read_text())
    assert r.analyze_selection(p,p['config'])==p['selection_analysis']
    assert p['resources']['completed']==dict(real_steps=11200,imagined_transitions=16699200,model_calls=660800,network_forwards=660800)
    assert all(m['before']==m['after'] for m in p['models']) and len(p['models'])==4
    assert h.sha(r.MANIFEST)==p['predictor_manifest_sha256']
    assert h.sha(r.PREDICTIONS)==p['predecision_file_sha256']
    assert [json.loads(line) for line in r.PREDICTIONS.read_text().splitlines()]==p['selection_decisions']


def test_saved_training_provenance_and_previous_artifacts_immutable():
    p=json.loads((h.ROOT/'artifacts/e3_2_return_feedback.json').read_text());m=json.loads(r.MANIFEST.read_text())
    assert r.paired_training([x for x in p['episodes'] if x['split']=='training'],p['config'])==m['training_pairs']
    for name,expected in p['historical_artifacts_sha256'].items():assert h.sha(h.ROOT/name)==expected
    validation=json.loads((h.ROOT/'artifacts/e3_2_return_feedback_validation.json').read_text())
    assert validation['capture_sha256']==h.sha(h.run_paths(p['config'])['result'])


def test_saved_primary_negative_is_not_incomplete_or_positive():
    p=json.loads((h.ROOT/'artifacts/e3_2_return_feedback.json').read_text());a=r.analyze_selection(p,p['config'])
    gains=[a['by_family'][f]['predictor_minus_baselines']['model_mean'] for f in ('pendulum','acrobot')]
    assert gains==pytest.approx([-31.91222501167988,0.3171733015456084])
    assert p['declared_complete'] and not a['point_screen']
    for f in ('pendulum','acrobot'):
        assert len(a['by_family'][f]['per_model_returns'])==2
