"""Crossed-reset correctness on synthetic records, no world construction."""
import importlib.util
import itertools
import json

import pytest

from nexus.evolution1.catalogue import digest
from nexus.evolution1.resources import Work
from nexus.evolution2 import full_policy_source as h

CONFIG=h.ROOT/'configs/unified_crossed_reset.json'
spec=importlib.util.spec_from_file_location('crossed_runner',h.ROOT/'scripts/run_unified_full_policy_replication.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)


def grid():
    c=json.loads(CONFIG.read_text());rows=[]
    for b,e,label in itertools.product(c['model_bundles'],c['episodes'],c['controllers']):
        seed,base=h.seeds(c,'pendulum',b,e);obs=[1.,0.,0.]
        reward=(-.99 if b==0 else -1.01) if label=='rank_blend' else -1.
        steps=[dict(tick=t,obs=obs.copy(),next_obs=obs.copy(),action=1,reward=reward,
                    planner_seed=base+t,terminated=False,truncated=t==199) for t in range(200)]
        rows.append(dict(family='pendulum',model_bundle=b,episode=e,controller=label,reset_seed=seed,
            planner_base=base,initial_obs_hash=digest(obs),steps=steps))
        rows[-1]['return']=sum(s['reward'] for s in steps)
    return dict(config=c,episodes=rows,resources=dict(completed=Work(real_steps=3200).payload(),unknown_upper=Work().payload()))


def test_shared_seeds_cross_models_and_exclude_both_closed_samples():
    c=json.loads(CONFIG.read_text());requested=h.requested_seeds(c)
    assert len(requested)==804
    for e in c['episodes']:assert h.seeds(c,'pendulum',0,e)==h.seeds(c,'pendulum',1,e)
    for path in (h.CONFIG,r.CONFIG):
        assert not requested & h.requested_seeds(json.loads(path.read_text()))
    for path in (h.RESULT,h.ROOT/'artifacts/unified_full_policy_replication.json'):
        assert not h.seed_collisions(json.loads(path.read_text()),requested)


def test_complete_crossed_grid_and_paired_interaction():
    p=grid();assert h.validate_result(p,p['config'])
    a=r.directional_screen(p)
    assert a['per_model_means']['0']==pytest.approx(2.)
    assert a['per_model_means']['1']==pytest.approx(-2.)
    assert a['mean_interaction']==pytest.approx(4.)
    assert a['label']=='model_preference_split_descriptive'
    assert not a['scientific_control_success'] and a['new_independent_models']==0
    assert list(h.analyze(p['episodes'],p['config'])['paired_contrasts']['pendulum']['rank_blend'])==['successor_anchor']


def test_cross_model_initial_state_mismatch_is_rejected_even_if_methods_pair():
    p=grid()
    for row in p['episodes']:
        if row['model_bundle']==1 and row['episode']==0:
            for s in row['steps']:s['obs'][0]=.5;s['next_obs'][0]=.5
            row['initial_obs_hash']=digest(row['steps'][0]['obs'])
    with pytest.raises(ValueError,match='uncrossed_initial_states'):r.directional_screen(p)


@pytest.mark.parametrize('change',['missing_model','missing_reset','missing_policy','nan','seed','planner','unknown','reduced'])
def test_incomplete_crossed_results_fail_closed(change):
    p=grid()
    if change=='missing_model':p['episodes']=[x for x in p['episodes'] if x['model_bundle']!=1]
    if change=='missing_reset':p['episodes']=[x for x in p['episodes'] if x['episode']!=3]
    if change=='missing_policy':p['episodes']=[x for x in p['episodes'] if x['controller']!='rank_blend']
    if change=='nan':p['episodes'][0]['return']=float('nan')
    if change=='seed':p['episodes'][0]['reset_seed']+=100
    if change=='planner':p['episodes'][0]['steps'][0]['planner_seed']+=1
    if change=='unknown':p['resources']['unknown_upper']['real_steps']=1
    if change=='reduced':p['config']['episodes']=[0,1]
    with pytest.raises(ValueError):r.directional_screen(p)


def test_mean_split_without_per_reset_consistency_does_not_pass():
    p=grid()
    for row in p['episodes']:
        if row['model_bundle']==0 and row['controller']=='rank_blend':
            value=-.90 if row['episode']<2 else -1.01
            for s in row['steps']:s['reward']=value
            row['return']=sum(s['reward'] for s in row['steps'])
    a=r.directional_screen(p)
    assert a['per_model_means']['0']>1.
    assert a['label']=='model_preference_split_not_established'


def test_profile_paths_and_nominal_plan_costs_are_isolated():
    import numpy as np
    c=json.loads(CONFIG.read_text());paths=h.run_paths(c)
    assert paths['result']!=h.RESULT
    assert paths['usage']!=h.USAGE
    calls=states=0
    for label in c['controllers']:
        plan=h.operation_plan(h.controllers()[label],np.zeros(3),3)
        calls+=sum(op.cost.model_calls for op in plan)
        states+=sum(op.cost.imagined_transitions for op in plan)
    assert calls*1600==188800 and states*1600==4771200


def test_exact_allocation_and_parent_integrity():
    c=json.loads(CONFIG.read_text());paths=h.run_paths(c)
    a=json.loads(paths['allocation'].read_text())
    assert a['config_sha256']==h.sha(CONFIG) and a['protocol_sha256']==h.sha(paths['protocol'])
    assert a['session_used_before_s']==455.41404345900935
    assert a['runs']==1 and not a['automatic_retry'] and a['env_cap']==3200 and a['time_cap_s']==90
    for path,expected in a['parent_artifacts_sha256'].items():h.verify_file(h.ROOT/path,expected)
