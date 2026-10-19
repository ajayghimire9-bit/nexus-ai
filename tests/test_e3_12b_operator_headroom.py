"""Deterministic source-only panel contracts; no worlds or neural calls."""
from copy import deepcopy
import importlib.util
import itertools
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.evolution1.catalogue import digest
from nexus.evolution2 import operator_headroom as h
from nexus.evolution2.generated_strategies import StrategyGenerator
from nexus.world.rewards import pendulum_step_reward,acrobot_step_reward

ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/e3_12b_operator_headroom.json').read_text())


def fixture():
    c=config();rows=[];final={}
    for f,b in itertools.product(c['families'],c['model_bundles']):
        g=StrategyGenerator(7,mutation_credit=True)
        for e in c['training_episodes']+c['evaluation_episodes']:
            role='training' if e in c['training_episodes'] else 'evaluation';reset,planner=h.seed_pair(c,f,b,e)
            obs=[1.,0.,0.] if f=='pendulum' else [1.,0.,1.,0.,0.,0.]
            reward=pendulum_step_reward if f=='pendulum' else acrobot_step_reward
            r=float(reward(np.asarray(obs),1,np.asarray(obs))[0])
            steps=[dict(tick=t,obs=obs,next_obs=obs,action=1,reward=r,terminated=False,truncated=t==199,planner_seed=planner+t) for t in range(200)]
            q=dict(phase=role,pair_id=f'{f}:{b}:{e}',context_hash=digest(obs),reset_seed=reset,planner_seed=planner,horizon=200,planning_cap=1536)
            row=dict(family=f,bundle=b,episode=e,role=role,initial_observation=obs,restored_hash='same',protocol=q,
                strategies={k:v.payload() for k,v in h.operators().items()},before={'learned':g.mutation_probabilities()},
                paths={k:dict(steps=deepcopy(steps),restored_hash='same',cpu_s=1.,return_value=r*200) for k in ('parent',*h.KINDS)})
            for v in row['paths'].values():v['return']=v.pop('return_value')
            if role=='training':h.replay_feedback(g,row,c)
            else:row['decision']=h.decide(rows,c,f,b,g)
            row['after']={'learned':g.mutation_probabilities()};rows.append(row)
        final[f'{f}:{b}']={'learned':g.mutation_probabilities()}
    actual=dict(real_steps=28800,imagined_transitions=1,model_calls=1,network_forwards=1)
    return dict(rows=rows,final_policies=final,resources=dict(completed=actual,reserved=actual.copy(),unknown_upper={k:0 for k in actual}),
        observed={k:1 for k in actual if k!='real_steps'},models=[dict(family=f,bundle=b,before='x',after='x') for f,b in itertools.product(c['families'],c['model_bundles'])]),c


def test_complete_panel_has_no_false_success_and_exact_model_units():
    p,c=fixture();assert h.validate(p,c)
    a=h.analyze(p['rows'],c)
    assert a['label']=='stable_operator_selection_not_established'
    assert a['families']['pendulum']['contrasts']['training_mean-minus-uniform_expected']['ci95']==[0.,0.]
    assert len(a['families']['pendulum']['models'])==2


@pytest.mark.parametrize('fault',['seed','model','operator','tick','return','nan','bool','query_choice','query_update','restoration','fingerprint','counts','unknown','strategy','provenance'])
def test_invalid_or_shortened_panels_fail_closed(fault):
    p,c=fixture();r=p['rows'][0]
    if fault=='seed':p['rows'].pop()
    elif fault=='model':p['rows']=[x for x in p['rows'] if x['bundle']!=1]
    elif fault=='operator':del r['paths']['switch']
    elif fault=='tick':r['paths']['parent']['steps'].pop()
    elif fault=='return':r['paths']['switch']['return']+=1
    elif fault=='nan':r['paths']['switch']['return']=float('nan')
    elif fault=='bool':r['paths']['switch']['return']=True
    elif fault=='query_choice':next(x for x in p['rows'] if x['role']=='evaluation')['decision']['training_mean_kind']='rank_blend'
    elif fault=='query_update':next(x for x in p['rows'] if x['role']=='evaluation')['after']['learned']['switch']=.7
    elif fault=='restoration':r['paths']['parent']['restored_hash']='wrong'
    elif fault=='fingerprint':p['models'][0]['after']='changed'
    elif fault=='counts':p['resources']['completed']['real_steps']-=1
    elif fault=='unknown':p['resources']['unknown_upper']['model_calls']=1
    elif fault=='strategy':r['strategies']['switch']['threshold']=1.
    elif fault=='provenance':r['protocol']['phase']='evaluation'
    with pytest.raises(ValueError):h.validate(p,c)


def test_query_labels_are_inaccessible_to_selector_and_incomplete_train_blocks():
    p,c=fixture();g=StrategyGenerator(7,mutation_credit=True)
    class Hidden(dict):
        def __getitem__(self,key):
            if key=='paths':raise AssertionError('query_data_read')
            return super().__getitem__(key)
    rows=[Hidden(r) if r['role']=='evaluation' else r for r in p['rows']]
    before=h.decide(rows,c,'pendulum',0,g)
    assert before['training_mean_kind']=='switch' and before['credit_kind']=='switch'
    train=[r for r in rows if r['role']=='training'];train.pop(0)
    with pytest.raises(ValueError,match='complete_training'):h.decide(train,c,'pendulum',0,g)


def test_raw_mean_and_cost_credit_are_separately_reported_not_conflated():
    p,c=fixture();g=StrategyGenerator(7,mutation_credit=True);g.mutation_stats={'switch':[1.,1],'rank_blend':[-1.,1]}
    for r in p['rows']:
        if r['role']=='training':r['paths']['rank_blend']['return']+=10
    d=h.decide(p['rows'],c,'pendulum',0,g)
    assert d['training_mean_kind']=='rank_blend' and d['credit_kind']=='switch'


def test_expected_uniform_is_analytic_not_an_extra_physical_episode():
    r=dict(paths={k:{'return':v} for k,v in [('parent',0.),('switch',2.),('rank_blend',8.)]},decision=dict(training_mean_kind='switch',credit_kind='rank_blend'))
    v=h.values(r)
    assert v['uniform_expected']==5. and v['retrospective_best']==8. and v['training_mean']==2.
    assert v['retrospective_best']-v['uniform_expected']==abs(2.-8.)/2


def runner():
    spec=importlib.util.spec_from_file_location('headroom_runner',ROOT/'scripts/run_e3_12_mutation_control.py')
    api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api);return api


def test_separate_profile_cannot_overwrite_closed_mutation_capture():
    api=runner();original=api.RESULT;api.configure_operator()
    assert api.RESULT!=original and api.RESULT.name=='e3_12b_operator_headroom.json'
    assert api.study_module() is h
    assert len(h.requested_seeds(config()))==9648


def test_no_duplicate_credit_events_when_parent_receipt_reused_for_two_kinds():
    p,c=fixture();g=StrategyGenerator(7,mutation_credit=True);r=p['rows'][0]
    h.replay_feedback(g,r,c)
    assert len(g.journal.snapshot())==2
    with pytest.raises(ValueError,match='duplicate'):h.replay_feedback(g,r,c)


def test_query_scores_cannot_change_replayed_training_policy():
    p,c=fixture();before=h.replay_learning(p['rows'],c)
    for r in p['rows']:
        if r['role']=='evaluation':
            for path in r['paths'].values():path['return']=100000.
    assert h.replay_learning(p['rows'],c)==before


def test_interval_uses_two_models_not_eight_query_episodes():
    p,c=fixture()
    for r in p['rows']:
        if r['role']=='evaluation':
            r['paths']['switch']['return']=4.+4.*r['bundle'];r['paths']['rank_blend']['return']=0.
    a=h.analyze(p['rows'],c)['families']['pendulum']
    contrast=a['contrasts']['training_mean-minus-uniform_expected']
    assert contrast['per_model']==[2.,4.] and contrast['mean']==3.
    assert contrast['ci95']==pytest.approx([3.-12.7062047364,3.+12.7062047364])
    assert not a['selection_screen']


def test_protocol_and_allocation_hashes_are_pinned():
    import hashlib
    grant=json.loads((ROOT/'configs/e3_12b_operator_headroom_allocation.json').read_text())
    for name,path in [('config','configs/e3_12b_operator_headroom.json'),('protocol','docs/NEXUS_E3_12B_OPERATOR_HEADROOM_PROTOCOL.md')]:
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==grant[name+'_sha256']
