"""Authored source fixtures only before the experimental protocol commit."""
import copy
import importlib.util
import json

import numpy as np
import pytest

from nexus.evolution1.catalogue import digest
from nexus.core.strategy_memory import SupportBatch,support_from_arrays
from nexus.core.strategy_memory_decide_bench import family_context,near_zero_support
from nexus.evolution2.full_policy_source import ROOT,sha
from nexus.evolution2.generated_strategies import AdvantagePredictor
from nexus.evolution2 import feature_informativeness as a
from nexus.evolution2 import transition_evidence as t
from test_e3_6_feature_informativeness import toy as original_toy


def toy():
    bank,x=original_toy()
    stats={f'{f}:{b}':[.1+.2*b,.01*(k+1),1.] for k,(f,b) in enumerate(a.MODELS)}
    return bank,t.augment(bank,x,stats)


@pytest.fixture
def few(monkeypatch):monkeypatch.setattr(a,'PERMUTATIONS',(0,1))


def test_genuine_transition_outcomes_affect_summaries_and_units():
    ctx=family_context('pendulum');s=near_zero_support(ctx,7)
    first=t.summaries(s,ctx,np.zeros(3),np.ones(3))
    other=SupportBatch(s.obs,s.action,s.next_obs+np.arange(32)[:,None]**2*.01,s.reward)
    changed=t.summaries(other,ctx,np.zeros(3),np.ones(3))
    assert changed[0]>first[0] and changed[1]>first[1]
    assert first[2]==changed[2]==1.
    np.testing.assert_allclose(t.summaries(other,ctx,np.zeros(3),np.ones(3)*2)[:2],changed[:2]/2,atol=1e-12)


def test_linear_fit_failure_is_explicit_not_silent_fallback(monkeypatch):
    ctx=family_context('pendulum');s=near_zero_support(ctx,7)
    def fail(*args,**kwargs):raise np.linalg.LinAlgError('synthetic')
    monkeypatch.setattr(np.linalg,'lstsq',fail)
    with pytest.raises(np.linalg.LinAlgError):t.summaries(s,ctx,np.zeros(3),np.ones(3))


@pytest.mark.parametrize('bad',['std','dimension','action','nan'])
def test_invalid_support_cannot_become_a_feature(bad):
    ctx=family_context('pendulum');s=near_zero_support(ctx,7);std=np.ones(3)
    if bad=='std':std[0]=0
    if bad=='dimension':s=SupportBatch(s.obs[:16],s.action[:16],s.next_obs[:16],s.reward[:16])
    if bad=='action':s.action[0]=3
    if bad=='nan':s.next_obs[0,0]=float('nan')
    with pytest.raises(ValueError):t.summaries(s,ctx,np.zeros(3),std)


def test_only_three_slots_change_and_predictor_capacity_stays_fixed():
    bank,old=original_toy();_,x=toy();assert a.validate_bank(bank,x,'e3_7')
    for first,second in zip(old,x):
        assert first==second[:192]
        assert second[192:304]==first[:112] and second[352:]==first[160:]
    assert len(a.columns('original','e3_7'))==len(a.columns('transition','e3_7'))==192
    for value in a.variability(bank,x,'e3_7').values():
        assert value['original']['centered_rank']==value['transition']['centered_rank']
    bad=copy.deepcopy(x);bad[0][192]+=1
    with pytest.raises(ValueError):a.validate_bank(bank,bad,'e3_7')


def test_source_prefix_and_checkpoint_free_provenance(tmp_path,monkeypatch):
    bank,x=original_toy();specs=[];saved=dict(normalizers={},support_sha256={})
    for k,(f,b) in enumerate(a.MODELS):
        dim=3 if f=='pendulum' else 6;rng=np.random.default_rng(k)
        obs=rng.normal(size=(1024,dim));act=np.arange(1024)%3;nxt=obs+.01*act[:,None]
        path=tmp_path/f'{f}_{b}.npz';np.savez(path,obs=obs,action=act,next_obs=nxt)
        specs.append(dict(family=f,bundle=b,split='train',n=1024,path=str(path),sha256=sha(path)))
        saved['normalizers'][f]=dict(mean=[0.]*dim,std=[1.]*dim,source_n=2048)
        s=support_from_arrays(obs,act,nxt,n=32)
        saved['support_sha256'][f'{f}:{b}']=digest(dict(obs=s.obs.tolist(),action=s.action.tolist(),next_obs=s.next_obs.tolist()))
    monkeypatch.setattr(t,'SOURCES',specs);calls=[]
    new,records=t.prepare(saved,bank,x,on_descriptor=lambda:calls.append(1))
    assert len(calls)==4 and a.validate_bank(bank,new,'e3_7')
    assert set(records)=={f'{f}:{b}' for f,b in a.MODELS}
    assert all(v['support_rows']==32 and v['support_start']==0 and v['descriptor_lstsq_calls']==1 for v in records.values())
    specs[0]['sha256']='0'*64
    with pytest.raises(ValueError):t.prepare(saved,bank,x)
    specs[0]['path']=str(tmp_path/'missing.npz')
    with pytest.raises((FileNotFoundError,RuntimeError)):t.prepare(saved,bank,x)


def test_withheld_labels_and_anchor_blocks_never_enter_fit(few):
    bank,x=toy();first=a.predict_fold(bank,x,3,profile='e3_7')
    poison=copy.deepcopy(bank)
    for row in poison:
        if row['public']['episode']==3:row['advantage']=1e8;row['returns']['rank_blend']=1e8;row['event']='withheld'
    assert a.predict_fold(poison,x,3,profile='e3_7')==first
    xx=copy.deepcopy(x)
    for row in xx:row[160:192]=[1e9]*32;row[352:]=[1e9]*32
    assert a.predict_fold(bank,xx,3,profile='e3_7')==first


def test_original_condition_reproduces_e3_6_without_changing_schedule(few):
    bank,x=toy();_,old=original_toy();new=a.predict_fold(bank,x,2,profile='e3_7');prior=a.predict_fold(bank,old,2)
    assert new['within_model_permutations']==prior['within_model_permutations']
    for first,second in zip(new['predictions'],prior['predictions']):
        assert first['estimates']['original']==pytest.approx(second['estimates']['full'],abs=1e-10,rel=1e-12)
    assert new==a.predict_fold(bank,x,2,profile='e3_7')


@pytest.fixture
def frozen(few):
    bank,x=toy();return bank,x,[a.predict_fold(bank,x,e,profile='e3_7') for e in range(9)]


def test_coefficient_replay_never_refits(frozen,monkeypatch):
    bank,x,folds=frozen
    def forbidden(*args,**kwargs):raise AssertionError('audit cannot refit')
    monkeypatch.setattr(AdvantagePredictor,'observe',forbidden)
    assert a.verify_frozen_folds(folds,bank,x,'e3_7')==a.score_predictions(folds,bank,'e3_7')


@pytest.mark.parametrize('bad',['fold','model','query','mode','permutation','coefficient','target','nan','bool'])
def test_complete_grid_and_finite_evidence_are_required(frozen,bad):
    bank,x,folds=frozen
    if bad=='fold':folds.pop()
    if bad=='model':folds[0]['models'].pop('transition')
    if bad=='query':folds[0]['predictions'].pop()
    if bad=='mode':folds[0]['predictions'][0]['estimates'].pop('transition')
    if bad=='permutation':folds[0]['within_model_permutations']['0'][0]=folds[0]['within_model_permutations']['0'][1]
    if bad=='coefficient':folds[0]['models']['transition']['beta'][0]+=1
    if bad=='target':folds[0]['training_targets'][0]+=1
    if bad=='nan':folds[0]['predictions'][0]['estimates']['transition']=float('nan')
    if bad=='bool':folds[0]['predictions'][0]['estimates']['transition']=False
    with pytest.raises(ValueError):a.verify_frozen_folds(folds,bank,x,'e3_7')


def runner():
    spec=importlib.util.spec_from_file_location('transition_runner',ROOT/'scripts/run_e3_3_training_feedback_audit.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.configure_transitions();return m


def test_exact_source_config_and_one_run_guard(tmp_path,monkeypatch):
    m=runner();c=json.loads(m.CONFIG.read_text());m.validate_config(c)
    assert c['ridge_fit_cap']==9*len(a.modes('e3_7'))==360
    for key,value in (('ridge',.5),('source_arrays',[]),('support_rows',64),('support_statistics',[])):
        bad=copy.deepcopy(c);bad[key]=value
        with pytest.raises(ValueError):m.validate_config(bad)
    for name in ('RESULT','FROZEN','USAGE'):monkeypatch.setattr(m,name,tmp_path/name)
    m.USAGE.write_text('{}')
    with pytest.raises(FileExistsError):m.run(c)
    m.USAGE.unlink();monkeypatch.delenv('OPENBLAS_NUM_THREADS',raising=False)
    with pytest.raises(ValueError,match='thread'):m.run(c)


def test_legacy_artifacts_restored_and_incident_budget_not_hidden():
    record=json.loads((ROOT/'artifacts/e3_7_preflight_recovery.json').read_text())
    for path,values in record['evidence']['captures'].items():
        assert sha(ROOT/path)==values['original_sha256']
    assert sha(ROOT/record['evidence']['archive_path'])==record['evidence']['archive_sha256']
    assert record['neural_inference_occurred'] and record['neural_forward_count'] is None
    ledger=record['session_ledger']
    assert ledger['used_after_s']-ledger['used_before_s']==pytest.approx(10.44)
