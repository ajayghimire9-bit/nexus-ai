"""Authored complete-grid fixtures only; no models or environments executed."""
from copy import deepcopy
import itertools
import json
from pathlib import Path
import pytest
from nexus.evolution2 import parent_retention as d
from nexus.evolution2 import operator_headroom as panel
from nexus.evolution2.generated_strategies import StrategyGenerator
from test_e3_12c_partial_feedback import load

ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/e3_12d_parent_retention.json').read_text())


def fixture():
    p,_=load('tests/test_e3_12b_operator_headroom.py','retention_panel').fixture();c=config();rows=[];final={}
    for f,b in itertools.product(c['families'],c['model_bundles']):
        g=StrategyGenerator(c['proposal_seed'],mutation_credit=True)
        for old in [r for r in p['rows'] if (r['family'],r['bundle'])==(f,b)]:
            row=deepcopy(old);e=row['episode'];reset,planner=d.seed_pair(c,f,b,e)
            row['protocol'].update(reset_seed=reset,planner_seed=planner);row['before']={'learned':g.mutation_probabilities()}
            if row['role']=='training':
                kind=d.training_operator(c,f,b,e);row['training_operator']=kind
                row['paths']={k:v for k,v in row['paths'].items() if k in ('parent',kind)}
                row['strategies']={kind:row['strategies'][kind]};panel.replay_feedback(g,row,c,kinds=(kind,))
            else:row['decision']=d.decide(rows,c,f,b,g)
            for path in row['paths'].values():
                for tick,step in enumerate(path['steps']):step['planner_seed']=planner+tick
            row['after']={'learned':g.mutation_probabilities()};rows.append(row)
        final[f'{f}:{b}']={'learned':g.mutation_probabilities()}
    p.update(rows=rows,final_policies=final);p['resources']['completed']['real_steps']=22400;p['resources']['reserved']['real_steps']=22400
    return p,c


def test_full_panel_equal_returns_keeps_parent_without_false_success():
    p,c=fixture();assert d.validate(p,c)
    a=d.analyze(p['rows'],c)
    assert a['label']=='parent_retention_not_established'
    for f in c['families']:
        assert a['families'][f]['retained_parent_models']==2
        assert a['families'][f]['contrasts']['parent_inclusive-minus-training_mean']['ci95']==[0.,0.]
    assert sum(len(r['paths']) for r in p['rows'])==112


@pytest.mark.parametrize('fault',['model','episode','parent','child','unobserved','choice','counts','schedule','policy','reward','nan','unknown','cap','method','threshold'])
def test_missing_or_corrupt_cells_fail_closed(fault):
    p,c=fixture();r=p['rows'][0];q=next(x for x in p['rows'] if x['role']=='evaluation')
    if fault=='model':p['rows']=[x for x in p['rows'] if x['bundle']!=1]
    elif fault=='episode':p['rows'].pop()
    elif fault=='parent':del r['paths']['parent']
    elif fault=='child':del r['paths'][r['training_operator']]
    elif fault=='unobserved':r['paths']['other']={}
    elif fault=='choice':q['decision']['parent_inclusive']['choice']='switch'
    elif fault=='counts':q['decision']['parent_inclusive']['observed_counts']['parent']=4
    elif fault=='schedule':r['training_operator']='other'
    elif fault=='policy':q['after']['learned']['switch']=.9
    elif fault=='reward':r['paths']['parent']['steps'][0]['reward']+=1.
    elif fault=='nan':r['paths']['parent']['return']=float('nan')
    elif fault=='unknown':p['resources']['unknown_upper']['real_steps']=1
    elif fault=='cap':c['real_cap']=22399
    elif fault=='method':c['model_bundles']=[0]
    elif fault=='threshold':c['uniform_margin']=0.
    with pytest.raises(ValueError):d.validate(p,c)


def test_query_outcomes_cannot_change_any_selector_or_training_seal():
    p,c=fixture();g=StrategyGenerator(7,mutation_credit=True)
    class Unreadable(dict):
        def __getitem__(self,key):
            if key=='paths':raise AssertionError('hidden_query_read')
            return super().__getitem__(key)
    rows=[Unreadable(r) if r['role']=='evaluation' else r for r in p['rows']]
    before=d.decide(rows,c,'pendulum',0,g)
    assert before['parent_inclusive']['choice']=='parent'
    assert d.replay_learning(rows,c)==p['final_policies']
    assert d.decide(rows,c,'pendulum',0,g)==before


def test_profile_cannot_accidentally_reuse_a_consumed_study():
    runner=load('scripts/run_e3_12_mutation_control.py','retention_runner')
    runner.configure_retention();assert runner.study_module() is d and runner.RETENTION_PROFILE and runner.PARTIAL_PROFILE
    assert runner.RESULT.name=='e3_12d_parent_retention.json' and runner.ALLOCATION.name=='e3_12d_parent_retention_allocation.json'
    assert len(d.requested_seeds(config()))==9648
    runner.configure_partial();assert not runner.RETENTION_PROFILE
    assert runner.RESULT.name=='e3_12c_partial_feedback.json'
    assert set(d.requested_seeds(config())).isdisjoint(d.requested_seeds(json.loads((ROOT/'configs/e3_12c_partial_feedback.json').read_text())))


def test_independent_export_recomputes_parent_means_and_failure_screen():
    p,c=fixture();p['analysis']=d.analyze(p['rows'],c)
    exporter=load('scripts/summarize_e3_12_mutation_control.py','retention_export')
    s=exporter.summarize_operator(p,c,partial=True,retention=True)
    assert s['phase_accounting']['training']['real_steps']==12800
    assert s['phase_accounting']['evaluation']['real_steps']==9600
    assert s['families']['pendulum']['parent_retention_screen'] is False
    q=next(r for r in p['rows'] if r['role']=='evaluation');q['decision']['parent_inclusive']['choice']='switch'
    with pytest.raises(ValueError,match='parent_choice'):exporter.summarize_operator(p,c,partial=True,retention=True)


def test_exact_allocation_pins_protocol_and_configuration():
    import hashlib
    a=json.loads((ROOT/'configs/e3_12d_parent_retention_allocation.json').read_text())
    for kind,path in [('config','configs/e3_12d_parent_retention.json'),('protocol','docs/NEXUS_E3_12D_PARENT_RETENTION_PROTOCOL.md')]:
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==a[kind+'_sha256']
    assert a['runs']==1 and a['automatic_retry'] is False
    assert a['time_cap_s']==300 and a['real_cap']==22400
    assert a['session_used_before_s']==1643.627562957004
