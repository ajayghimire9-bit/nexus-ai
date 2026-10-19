"""Pure synthetic transition/feedback contracts; no scientific execution."""
from copy import deepcopy
import importlib.util
import itertools
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.evolution2 import partial_feedback as h
from nexus.evolution2 import operator_headroom as panel
from nexus.evolution2.generated_strategies import StrategyGenerator

ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/e3_12c_partial_feedback.json').read_text())
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api);return api


def fixture():
    # Reuse the existing complete authored panel; remove unavailable training
    # outcomes before ANY limited-feedback selector/update sees the rows.
    p,_=load('tests/test_e3_12b_operator_headroom.py','panel_fixture').fixture();c=config();rows=[];final={}
    for f,b in itertools.product(c['families'],c['model_bundles']):
        g=StrategyGenerator(c['proposal_seed'],mutation_credit=True)
        for old in [r for r in p['rows'] if (r['family'],r['bundle'])==(f,b)]:
            row=deepcopy(old);e=row['episode'];reset,planner=h.seed_pair(c,f,b,e)
            row['protocol'].update(reset_seed=reset,planner_seed=planner);row['before']={'learned':g.mutation_probabilities()}
            if row['role']=='training':
                kind=h.training_operator(c,f,b,e);row['training_operator']=kind
                row['paths']={k:v for k,v in row['paths'].items() if k in ('parent',kind)}
                row['strategies']={kind:row['strategies'][kind]}
                panel.replay_feedback(g,row,c,kinds=(kind,))
            else:row['decision']=h.decide(rows,c,f,b,g)
            for path in row['paths'].values():
                for t,step in enumerate(path['steps']):step['planner_seed']=planner+t
            row['after']={'learned':g.mutation_probabilities()};rows.append(row)
        final[f'{f}:{b}']={'learned':g.mutation_probabilities()}
    p.update(rows=rows,final_policies=final)
    p['resources']['completed']['real_steps']=22400;p['resources']['reserved']['real_steps']=22400
    return p,c


def test_full_limited_grid_and_frozen_queries_validate_without_success():
    p,c=fixture();assert h.validate(p,c)
    assert h.analyze(p['rows'],c)['label']=='partial_feedback_selection_not_established'
    assert sum(len(r['paths']) for r in p['rows'])==112
    for r in p['rows']:
        if r['role']=='evaluation':assert r['decision']['observed_counts']=={'switch':4,'rank_blend':4}


@pytest.mark.parametrize('fault',['model','episode','child','unobserved_child','schedule','query_update','query_choice','reward','nan','boolean','checkpoint','counts','cap','unknown'])
def test_missing_or_leaking_feedback_fails_closed(fault):
    p,c=fixture();r=p['rows'][0]
    if fault=='model':p['rows']=[x for x in p['rows'] if x['bundle']!=1]
    elif fault=='episode':p['rows'].pop()
    elif fault=='child':del r['paths'][r['training_operator']]
    elif fault=='unobserved_child':
        absent=next(k for k in h.KINDS if k!=r['training_operator']);r['paths'][absent]=deepcopy(r['paths'][r['training_operator']])
    elif fault=='schedule':r['training_operator']=next(k for k in h.KINDS if k!=r['training_operator'])
    elif fault=='query_update':next(x for x in p['rows'] if x['role']=='evaluation')['after']['learned']['switch']=.8
    elif fault=='query_choice':next(x for x in p['rows'] if x['role']=='evaluation')['decision']['guarded_kind']='switch'
    elif fault=='reward':r['paths']['parent']['steps'][0]['reward']+=1
    elif fault=='nan':r['paths']['parent']['return']=float('nan')
    elif fault=='boolean':r['paths']['parent']['cpu_s']=True
    elif fault=='checkpoint':p['models'][0]['after']='changed'
    elif fault=='counts':p['resources']['completed']['real_steps']-=1
    elif fault=='cap':c['real_cap']+=200
    elif fault=='unknown':p['resources']['unknown_upper']['model_calls']=1
    with pytest.raises(ValueError):h.validate(p,c)


def test_balanced_schedule_independent_of_global_rng_and_query_evaluation():
    c=config()
    for f,b in itertools.product(c['families'],c['model_bundles']):
        before=[h.training_operator(c,f,b,e) for e in c['training_episodes']]
        np.random.default_rng(12).random(1000)
        assert before==[h.training_operator(c,f,b,e) for e in c['training_episodes']]
        assert before.count('switch')==before.count('rank_blend')==4


def test_selector_cannot_read_query_paths_or_unobserved_child_returns():
    p,c=fixture();g=StrategyGenerator(7,mutation_credit=True)
    class Hidden(dict):
        def __getitem__(self,key):
            if key=='paths':raise AssertionError('query_outcome_read')
            return super().__getitem__(key)
    rows=[Hidden(r) if r['role']=='evaluation' else r for r in p['rows']]
    assert h.decide(rows,c,'pendulum',0,g)['guarded_kind']=='parent'
    r=next(x for x in rows if x['role']=='training');other=next(k for k in h.KINDS if k!=r['training_operator'])
    r['paths'][other]=dict(__hidden=True)
    with pytest.raises(ValueError,match='unrevealed'):h.decide(rows,c,'pendulum',0,g)


def test_raw_return_and_paired_gain_controls_differ_under_reset_difficulty():
    p,c=fixture();g=StrategyGenerator(7,mutation_credit=True)
    for r in p['rows']:
        if r['role']=='training':
            k=r['training_operator'];r['paths'][k]['return']=10. if k=='switch' else 0.
            r['paths']['parent']['return']=100. if k=='switch' else 0.
    d=h.decide(p['rows'],c,'pendulum',0,g)
    assert d['training_mean_kind']=='switch' and d['paired_gain_kind']=='rank_blend'
    assert d['guarded_kind']=='parent'
    for r in p['rows']:
        if r['role']=='training' and r['training_operator']=='rank_blend':r['paths']['rank_blend']['return']=1.
    assert h.decide(p['rows'],c,'pendulum',0,g)['guarded_kind']=='rank_blend'


def test_query_outcomes_do_not_change_fitted_policy_or_training_hash():
    p,c=fixture();a=h.replay_learning(p['rows'],c)
    for r in p['rows']:
        if r['role']=='evaluation':
            for path in r['paths'].values():path['return']=999999.
    assert h.replay_learning(p['rows'],c)==a


def test_profile_isolation_and_exact_physical_seed_grid():
    api=load('scripts/run_e3_12_mutation_control.py','partial_runner');old=api.RESULT
    api.configure_partial();assert api.RESULT!=old and api.PARTIAL_PROFILE and api.OPERATOR_PROFILE
    assert api.study_module() is h and len(h.requested_seeds(config()))==9648
    assert api.RESULT.name=='e3_12c_partial_feedback.json'
    api.configure_operator()
    assert not api.PARTIAL_PROFILE and api.study_module() is panel


def test_incomplete_exploration_cannot_select_a_query_policy():
    p,c=fixture();rows=[r for r in p['rows'] if r['role']=='training'];rows.pop(0)
    with pytest.raises(ValueError,match='complete_partial'):h.decide(rows,c,'pendulum',0,StrategyGenerator(1,mutation_credit=True))


def test_configuration_pins_and_schedule_cannot_silently_drift():
    import hashlib
    grant=json.loads((ROOT/'configs/e3_12c_partial_feedback_allocation.json').read_text())
    for key,path in [('config','configs/e3_12c_partial_feedback.json'),('protocol','docs/NEXUS_E3_12C_PARTIAL_FEEDBACK_PROTOCOL.md')]:
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==grant[key+'_sha256']
    c=config();c['training_schedule']['pendulum:0'].reverse()
    with pytest.raises(ValueError,match='registered_schedule'):h.training_operator(c,'pendulum',0,0)


def test_independent_summary_counts_single_child_training_and_guard_replay():
    p,c=fixture();p['analysis']=h.analyze(p['rows'],c)
    api=load('scripts/summarize_e3_12_mutation_control.py','partial_summary')
    s=api.summarize_operator(p,c,partial=True)
    assert s['phase_accounting']['training']['real_steps']==12800
    assert s['phase_accounting']['evaluation']['real_steps']==9600
    assert s['families']['pendulum']['contrasts']['credit_argmax-minus-guarded']['mean']==0.


@pytest.mark.parametrize('fault',['missing','schedule','guard','interval'])
def test_independent_summary_rejects_unplanned_or_corrupt_results(fault):
    p,c=fixture();p['analysis']=h.analyze(p['rows'],c)
    if fault=='missing':p['rows'].pop()
    elif fault=='schedule':p['rows'][0]['training_operator']='wrong'
    elif fault=='guard':next(r for r in p['rows'] if r['role']=='evaluation')['decision']['guarded_kind']='switch'
    elif fault=='interval':p['analysis']['families']['pendulum']['contrasts']['training_mean-minus-uniform_expected']['ci95']=[10.,20.]
    api=load('scripts/summarize_e3_12_mutation_control.py','partial_summary')
    with pytest.raises(ValueError):api.summarize_operator(p,c,partial=True)
