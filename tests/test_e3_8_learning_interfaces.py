"""Synthetic contract tests; no real worlds, networks or fresh collections."""
import copy
import importlib.util
import json
import numpy as np
import pytest

from nexus.core.episode_context import EpisodeContext,from_cached_prefix
from nexus.evolution1.catalogue import digest
from nexus.evolution1.fixtures import verify_journal
from nexus.evolution1.resources import ReservationLedger,Limits,Work,Clock,Operation
from nexus.evolution1.toy_loop import VARIANTS
from nexus.evolution2.generated_strategies import AdvantagePredictor,StrategyGenerator,leaf,compose
from nexus.evolution2.compact_interactions import build,augment
from nexus.evolution2 import feature_informativeness as a
from nexus.evolution2.planner_adapter import FakeStepModel
from nexus.evolution2.planner_evidence import planner_evidence,evidence_operations
from nexus.evolution2.continual_state import TaskStream
from nexus.evolution2.staged_study import StagedStudy,SourcePrior
from nexus.evolution2.learning_lab import render
from nexus.evolution2.full_policy_source import ROOT
from test_e3_7_transition_evidence import toy as paired_toy


def toy():
    bank,x=paired_toy();return bank,augment(x)


def test_compact_builder_has_no_descriptor_padding_and_learns_interaction():
    additive,interaction=build(np.arange(6.),[2.,3.]);assert len(additive)==9 and len(interaction)==21
    np.testing.assert_array_equal(interaction[9:],np.outer(np.arange(6.),[2.,3.]).ravel())
    models=[AdvantagePredictor(),AdvantagePredictor()]
    for i,(z,c) in enumerate((z,c) for z in (-2.,-1.,1.,2.) for c in (-1.,1.)):
        xx=build([z,0,0,0,0,0],[c,0])
        for m,x in zip(models,xx):m.observe(x,z*c,event=str(i),provenance='revealed_source')
    xx=build([.5,0,0,0,0,0],[.8,0]);errors=[abs(m.predict(x)-.4) for m,x in zip(models,xx)]
    assert errors[1]<errors[0]


def test_compact_fold_isolation_replay_and_missing_cells(monkeypatch):
    monkeypatch.setattr(a,'PERMUTATIONS',(0,1));bank,x=toy();assert a.validate_bank(bank,x,'e3_8')
    first=a.predict_fold(bank,x,1,profile='e3_8');poison=copy.deepcopy(bank)
    for r in poison:
        if r['public']['episode']==1:r['advantage']=1e9;r['returns']['rank_blend']=1e9
    assert a.predict_fold(poison,x,1,profile='e3_8')==first
    folds=[a.predict_fold(bank,x,e,profile='e3_8') for e in range(9)]
    monkeypatch.setattr(AdvantagePredictor,'observe',lambda *args,**kw:(_ for _ in ()).throw(AssertionError('no refit')))
    assert a.verify_frozen_folds(folds,bank,x,'e3_8')==a.score_predictions(folds,bank,'e3_8')
    for mutate in ('model','row','nan'):
        bad=copy.deepcopy(folds)
        if mutate=='model':bad[0]['models'].pop('interaction')
        if mutate=='row':bad[0]['predictions'].pop()
        if mutate=='nan':bad[0]['predictions'][0]['estimates']['interaction']=float('nan')
        with pytest.raises(ValueError):a.verify_frozen_folds(bad,bank,x,'e3_8')


def test_episode_context_is_chronological_local_and_copied():
    c=EpisodeContext(1,3,window=2,source_context=[9.]);c.reset_episode('A',[0.]);c.predict_before_action([.5])
    c.observe([0.],0,[1.],1.,step=0,episode_id='A')
    assert c.features()['prediction_error_mean']==.5
    with pytest.raises(ValueError):c.observe([1.],0,[2.],1.,step=2)
    with pytest.raises(ValueError):c.observe([99.],0,[2.],1.)
    c.observe([1.],1,[2.],0.);c.observe([2.],1,[3.],-1.)
    assert c.features()['rolling_observed']==2 and c.features()['total_observed']==3
    c.reset_episode('B');assert c.features()['total_observed']==0 and c.features()['source_context']==(9.,)
    with pytest.raises(ValueError):from_cached_prefix([{}],decision_step=0,obs_dim=1,n_actions=3,episode_id='B')


def ledger_for(ops,cap=None):
    work=Work()
    for op in ops:work=work.plus(op.cost)
    return ReservationLedger(tuple(ops),Limits(cap or work,work,10**9,10**9))


def test_evidence_uses_common_scoring_and_charges_before_model_call():
    plans={'incumbent':np.array([[0,0,0],[2,2,2]]),'challenger':np.array([[1,1,1],[2,0,2]])}
    model=FakeStepModel(1,3);ops=evidence_operations(plans,3);ledger=ledger_for(ops)
    evidence=planner_evidence(plans,[0.],model,lambda o,a,n: -n[:,0]**2,n_actions=3,ledger=ledger,clock=lambda:Clock(0,0),fingerprint=lambda:'fixed')
    report=ledger.close(Clock(0,0));assert report.physical_completed_reported.imagined_transitions==12
    assert all(r['kind']=='forecast_not_observed_return' and r['common_horizon']==3 for r in evidence.values())
    with pytest.raises(ValueError):evidence_operations({**plans,'third':plans['incumbent']},3)
    with pytest.raises(ValueError):evidence_operations({'a':plans['incumbent'],'b':np.array([[0]])},3)
    blocked=ledger_for(ops,Work(imagined_transitions=1,model_calls=1,network_forwards=1))
    with pytest.raises(ValueError):planner_evidence(plans,[0.],model,lambda o,a,n:n[:,0],n_actions=3,ledger=blocked,clock=lambda:Clock(0,0),fingerprint=lambda:'fixed')


def mutation_rows(parent,child,event='1',gain=100.):
    common=dict(kind='observed_full_policy_return',phase='training',pair_id='pair'+event,context_hash=digest('ctx'),reset_seed=1,planner_seed=2,horizon=200,planning_cap=1536,cpu_s=.1)
    return ({**common,'strategy':parent.fingerprint,'return':0.,'event':'parent'+event},
            {**common,'strategy':child.fingerprint,'return':gain,'event':'child'+event})


def test_mutation_credit_changes_structural_policy_without_crediting_leaves():
    parent=leaf(VARIANTS[0]);child=compose('switch',VARIANTS[0],VARIANTS[-1],.25)
    g=StrategyGenerator(7,mutation_credit=True);before=g.inner.learned_state();rows=mutation_rows(parent,child)
    assert g.observe_mutation(parent,child,*rows)>0 and g.mutation_probabilities()['switch']>.5
    assert g.inner.learned_state()==before and verify_journal(g.journal.snapshot())
    with pytest.raises(ValueError):g.observe_mutation(parent,child,*rows)
    for field,value in (('phase','final'),('kind','forecast_not_observed_return'),('planner_seed',999)):
        p,c=mutation_rows(parent,child,'2');c[field]=value
        with pytest.raises(ValueError):g.observe_mutation(parent,child,p,c)
    fixed=StrategyGenerator(7,adaptive=False,mutation_credit=True);fixed.observe_mutation(parent,child,*mutation_rows(parent,child))
    assert fixed.mutation_probabilities()['switch']==.5


def test_task_stream_retains_feedback_and_stops_noise_with_reset_controls():
    c=EpisodeContext(1,3);persistent=TaskStream(max_choices=12);reset=TaskStream(max_choices=12,control='reset')
    for stream in (persistent,reset):
        stream.begin_task('A',c)
        for i,gain in enumerate((10.,0.,-1.)):
            assert stream.choose_experiment()==stream.ACTIONS[i]
            stream.reveal(event=str(i),observed_return_gain=gain,cpu_s=1.)
        stream.begin_task('B',c)
    assert persistent.rates['test_challenger'][1]==1 and reset.rates['test_challenger'][1]==0
    assert verify_journal(persistent.journal.snapshot()) and verify_journal(reset.journal.snapshot())
    noisy=TaskStream(max_choices=12);noisy.begin_task('A',c)
    for i in range(3):noisy.choose_experiment();noisy.reveal(event=str(i),observed_return_gain=0.,cpu_s=1.)
    assert noisy.choose_experiment()=='stop'


def receipt(steps):
    ops=tuple(Operation('step'+str(i),'environment',Work(real_steps=1)) for i in range(steps))
    ledger=ledger_for(ops)
    for op in ops:ticket=ledger.reserve(op.key,Clock(0,0));ledger.settle(ticket,'success',Clock(0,0))
    return ledger.close(Clock(0,0))


def test_staged_study_charges_shared_probe_once_and_freezes_recipe():
    config=dict(registered=True,authorized=True,protocol_commit='synthetic',kind='synthetic_contract',conditions=['mean','context'],
        cases=[dict(task='A',condition=c,episode=0,reset_seed=1,planner_seed=2,probe_steps=8,remaining_steps=192) for c in ('mean','context')],
        per_case_real_cap=192,per_case_imagined_cap=0,total_real_cap=392,total_imagined_cap=0)
    study=StagedStudy(config);study.fit_source([{'phase':'training'}],lambda rows:{'w':1},digest)
    prefix=[dict(task='A',episode=0,step=i,phase='support',observation=[i],action=0,next_observation=[i+1],reward=-1.) for i in range(8)]
    study.adapt_support('A',prefix,lambda policy,rows:{'count':len(rows)},receipt(8))
    result=study.evaluate(lambda case,policy,context:(dict(evaluation_rewards=[1.]*192,support_hash=digest(tuple(prefix))),receipt(192)))
    assert result['real_steps']==392 and all(r['full_accounted_return']==184 for r in result['rows'])
    with pytest.raises(ValueError):study.evaluate(None)
    with pytest.raises(ValueError):StagedStudy(config,closed_seeds=[1])
    config['cases'].pop()
    with pytest.raises(ValueError):StagedStudy(config)
    prior=SourcePrior([dict(phase='training',kind='observed_full_policy_advantage',family='f',model=m,advantage=v) for m,v in (('a',10.),('b',-5.))])
    assert prior.value('f','a',known_source_model=True)==10.
    assert prior.value('f','a',known_source_model=False)==2.5


def runner():
    spec=importlib.util.spec_from_file_location('compact_runner',ROOT/'scripts/run_e3_3_training_feedback_audit.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.configure_compact();return m


def test_compact_and_fresh_configs_are_locked():
    m=runner();c=json.loads(m.CONFIG.read_text());m.validate_config(c)
    assert len(a.columns('additive','e3_8'))==9 and len(a.columns('interaction','e3_8'))==21
    bad=copy.deepcopy(c);bad['ridge']=.1
    with pytest.raises(ValueError):m.validate_config(bad)
    with pytest.raises(ValueError):StagedStudy(json.loads((ROOT/'configs/fresh_contextual_selection_design.json').read_text()))


def test_viewer_is_offline_read_only_and_escapes_artifact_text():
    data=dict(kind='historical_training_replay',live=False,source='</script><script>bad()</script>',execution_sha='fixture',decision='fixture',rows=[{}])
    page=render(data,engineering_events=[{'kind':'synthetic','text':'<script>bad()</script>'}])
    assert 'fetch(' not in page and 'localhost' not in page and '&lt;script&gt;' in page
    assert '</script><script>bad()' not in page
    with pytest.raises(ValueError):render({**data,'live':True})


def test_evidence_context_mutation_and_failed_calls_are_not_free():
    plans={'a':np.array([[0,0]]),'b':np.array([[1,1]])};ops=evidence_operations(plans,3)
    class Bad(FakeStepModel):
        def step(self,*args):raise RuntimeError('synthetic failure')
    ledger=ledger_for(ops)
    with pytest.raises(RuntimeError):planner_evidence(plans,[0.],Bad(1,3),lambda o,a,n:n[:,0],n_actions=3,ledger=ledger,clock=lambda:Clock(0,0),fingerprint=lambda:'fixed')
    report=ledger.close(Clock(0,0));assert report.physical_unknown_upper_bound.imagined_transitions==1
    state=['before'];model=FakeStepModel(1,3);original=model.step
    def changed(*args):state[0]='after';return original(*args)
    model.step=changed;ledger=ledger_for(ops)
    with pytest.raises(ValueError,match='changed'):planner_evidence(plans,[0.],model,lambda o,a,n:n[:,0],n_actions=3,ledger=ledger,clock=lambda:Clock(0,0),fingerprint=lambda:state[0])


def test_random_fixed_and_shuffled_stream_controls_are_reproducible():
    def trace(control,schedule):
        s=TaskStream(7,max_choices=8,control=control,schedule=schedule);c=EpisodeContext(1,3);out=[]
        for i,task in enumerate(('A','B','A','C')):
            s.begin_task(task,c)
            for j in range(2):
                action=s.choose_experiment();out.append(action)
                if action!='stop':s.reveal(event=f'{i}:{j}',observed_return_gain=1. if action=='refine_strategy' else 0.,cpu_s=1.)
        assert s.remaining>=0 and verify_journal(s.journal.snapshot());return out
    for mode in ('persistent','reset','shuffled'):
        for schedule in ('adaptive','random','fixed'):assert trace(mode,schedule)==trace(mode,schedule)
