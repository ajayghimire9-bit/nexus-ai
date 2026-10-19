"""Synthetic fixtures only until the protocol commit; no worlds or networks."""
import copy
import importlib.util
import json

import numpy as np
import pytest

from nexus.evolution2 import feature_informativeness as a
from nexus.evolution2 import training_feedback_audit as base
from nexus.evolution2.generated_strategies import AdvantagePredictor,advantage_features,leaf
from nexus.evolution2.full_policy_source import ROOT
from nexus.evolution2.observation_memory import FamilyNormalizer
from nexus.core.strategy_memory_decide_bench import family_context,near_zero_support
from nexus.core.strategy_memory import SupportBatch,describe_support
from nexus.evolution1.toy_loop import VARIANTS
from test_e3_5_residual_advantage import toy as old_toy


def toy():
    bank,x=old_toy()
    for row,phi in zip(bank,x):
        dim=3 if row['public']['family']=='pendulum' else 6
        matrix=np.asarray(phi).reshape(12,16)
        matrix[7:10]=np.outer([dim/16.,3/16.,200/16.],matrix[0])
        phi[:]=matrix.ravel().tolist()
    return bank,x


@pytest.fixture
def few(monkeypatch):
    # Only authored toy tests use fewer permutations; executable config rejects it.
    monkeypatch.setattr(a,'PERMUTATIONS',(0,1))


def test_existing_support_coordinates_ignore_all_transition_evidence():
    ctx=family_context('pendulum');s=near_zero_support(ctx,1)
    other=SupportBatch(s.obs*1000,s.action[::-1],s.next_obs*-999,s.reward+1000)
    assert not np.allclose(describe_support(s,ctx)[3:],describe_support(other,ctx)[3:])
    norm=FamilyNormalizer('pendulum',np.zeros(3),np.ones(3),3,32)
    strategy=leaf(VARIANTS[0]);obs=np.array([.2,.3,.4])
    np.testing.assert_array_equal(advantage_features(strategy,obs,s,ctx,norm,(1.,2.)),
                                  advantage_features(strategy,obs,other,ctx,norm,(1.,2.)))


def test_exact_group_slices_and_schema_validation():
    bank,x=toy();assert a.validate_bank(bank,x)
    assert {g:len(a.columns(g)) for g in a.GROUP_ROWS}==dict(full=192,observation=112,support_schema=64,anchor=48)
    altered=copy.deepcopy(x);altered[0][7*16]+=1
    with pytest.raises(ValueError,match='schema'):a.validate_bank(bank,altered)
    result=a.variability(bank,x)
    for value in result.values():
        assert value['observation']['varying_columns']>0
        assert value['anchor']['varying_columns']==value['support_schema']['varying_columns']==0


def test_permutations_preserve_models_labels_means_and_exclude_query(few):
    bank,x=toy();train,query,means,xx,q,y,maps,priors=a.layout(bank,x,4)
    assert len(train)==32 and len(query)==4 and not set(train)&set(query)
    for mapping in maps.values():
        assert sorted(mapping)==list(range(32))
        assert any(i!=v for i,v in enumerate(mapping))
        for i,v in enumerate(mapping):assert base.identity(bank[train[i]])[:2]==base.identity(bank[train[v]])[:2]
        np.testing.assert_array_equal(np.sort(a.design('full_perm_0',xx,maps),axis=0),np.sort(xx,axis=0))
    fold=a.predict_fold(bank,x,4)
    assert fold['training_targets']==y and fold['anchor_means']==means
    for key in a.MODELS:
        ids=[j for j,i in enumerate(train) if base.identity(bank[i])[:2]==key]
        assert sum(y[j] for j in ids)==pytest.approx(0.,abs=1e-10)


def test_query_labels_and_saved_all_bank_anchors_cannot_affect_fit(few):
    bank,x=toy();original=a.predict_fold(bank,x,2)
    poisoned=copy.deepcopy(bank)
    for row in poisoned:
        if row['public']['episode']==2:row['advantage']=1e9;row['returns']['rank_blend']=1e9;row['event']='withheld'
    assert a.predict_fold(poisoned,x,2)==original
    poisoned_x=copy.deepcopy(x)
    for row in poisoned_x:row[160:]=[1e8]*32
    assert a.predict_fold(bank,poisoned_x,2)==original


def test_full_group_reproduces_existing_residual_and_is_deterministic(few):
    bank,x=toy();fold=a.predict_fold(bank,x,1)
    assert fold==a.predict_fold(bank,x,1)
    previous=base.predict_fold(bank,x,1,profile='e3_5')
    for new,old in zip(fold['predictions'],previous['predictions']):
        assert new['estimates']['full']==pytest.approx(old['estimates']['residual_predictor'],abs=1e-10,rel=1e-12)


def test_informative_observation_toy_beats_mean_and_constant_slices_do_not(few):
    bank,x=toy();folds=[a.predict_fold(bank,x,e) for e in range(9)]
    result=a.score_predictions(folds,bank)
    for row in result['per_model'].values():
        assert row['metrics']['observation']['mae']<row['metrics']['model_mean']['mae']
        for group in ('anchor','support_schema'):
            assert row['metrics'][group]['mae']==pytest.approx(row['metrics']['model_mean']['mae'],abs=1e-10)


@pytest.fixture
def frozen(few):
    bank,x=toy();return bank,x,[a.predict_fold(bank,x,e) for e in range(9)]


def test_independent_replay_does_not_fit(frozen,monkeypatch):
    bank,x,folds=frozen
    def forbidden(*args,**kwargs):raise AssertionError('no fitting in verifier')
    monkeypatch.setattr(AdvantagePredictor,'observe',forbidden)
    assert a.verify_frozen_folds(folds,bank,x)==a.score_predictions(folds,bank)


@pytest.mark.parametrize('bad',['fold','query','condition','model','permutation','coefficient','scale','targets','bool','string','nan','inf','train_ids'])
def test_incomplete_or_corrupt_cells_fail_before_aggregation(frozen,bad):
    bank,x,folds=frozen
    if bad=='fold':folds.pop()
    if bad=='query':folds[0]['predictions'].pop()
    if bad=='condition':folds[0]['predictions'][0]['estimates'].pop('observation')
    if bad=='model':folds[0]['models'].pop('anchor')
    if bad=='permutation':folds[0]['within_model_permutations']['0'][0]=folds[0]['within_model_permutations']['0'][1]
    if bad=='coefficient':folds[0]['models']['full']['beta'][0]+=1
    if bad=='scale':folds[0]['models']['full']['scale'][0]+=1
    if bad=='targets':folds[0]['training_targets'][0]+=1
    if bad in ('bool','string','nan','inf'):folds[0]['predictions'][0]['estimates']['full']={'bool':True,'string':'0','nan':float('nan'),'inf':float('inf')}[bad]
    if bad=='train_ids':folds[0]['train_ids'].pop()
    with pytest.raises(ValueError):a.verify_frozen_folds(folds,bank,x)


@pytest.mark.parametrize('bad',['missing_model','missing_reset','duplicate','bool_id','nonfinite'])
def test_locked_bank_grid_cannot_shrink(bad):
    bank,x=toy()
    if bad=='missing_model':
        pairs=[(r,v) for r,v in zip(bank,x) if base.identity(r)[:2]!=('acrobot',1)];bank=[p[0] for p in pairs];x=[p[1] for p in pairs]
    if bad=='missing_reset':bank.pop();x.pop()
    if bad=='duplicate':bank[-1]=copy.deepcopy(bank[0])
    if bad=='bool_id':bank[0]['public']['model_bundle']=False
    if bad=='nonfinite':x[0][0]=float('nan')
    with pytest.raises(ValueError):a.validate_bank(bank,x)


def test_fit_guard_failure_is_charged_before_fit(few):
    bank,x=toy();events=[]
    def guard(stage):
        events.append(stage)
        if stage=='reserve':raise TimeoutError('cap')
    with pytest.raises(TimeoutError):a.predict_fold(bank,x,0,fit_guard=guard)
    assert events==['reserve']


def runner():
    spec=importlib.util.spec_from_file_location('feature_runner',ROOT/'scripts/run_e3_3_training_feedback_audit.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.configure_features();return m


def test_runner_config_is_executable_locked_and_one_run(tmp_path,monkeypatch):
    m=runner();c=json.loads(m.CONFIG.read_text());m.validate_config(c)
    assert c['ridge_fit_cap']==9*len(a.modes())==720
    for key,value in (('ridge',.1),('permutation_ids',[0]),('minimum_mae_reduction',0)):
        altered=copy.deepcopy(c);altered[key]=value
        with pytest.raises(ValueError):m.validate_config(altered)
    for name in ('RESULT','FROZEN','USAGE'):monkeypatch.setattr(m,name,tmp_path/name)
    m.USAGE.write_text('{}')
    with pytest.raises(FileExistsError):m.run(c)
    m.USAGE.unlink();monkeypatch.delenv('OPENBLAS_NUM_THREADS',raising=False)
    with pytest.raises(ValueError,match='thread'):m.run(c)
