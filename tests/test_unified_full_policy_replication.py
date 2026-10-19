"""Deterministic source-only tests; no worlds or learned inference."""
import copy
import importlib.util
import itertools
import json

import pytest

from nexus.evolution1.catalogue import digest
from nexus.evolution1.resources import Work
from nexus.evolution2 import full_policy_source as h

SPEC=importlib.util.spec_from_file_location('replicate',h.ROOT/'scripts/run_unified_full_policy_replication.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)


def grid():
    c=json.loads(r.CONFIG.read_text());rows=[]
    for f,b,e,label in itertools.product(c['families'],c['model_bundles'],c['episodes'],c['controllers']):
        obs=[0.]*(3 if f=='pendulum' else 6);reset,base=h.seeds(c,f,b,e)
        reward=(-.99 if f=='acrobot' else -1.01) if label=='rank_blend' else -1.
        steps=[dict(tick=t,reward=reward,obs=obs.copy(),next_obs=obs.copy(),action=1,
                    planner_seed=base+t,terminated=False,truncated=t==199) for t in range(200)]
        rows.append(dict(family=f,model_bundle=b,episode=e,controller=label,reset_seed=reset,
                         planner_base=base,initial_obs_hash=digest(obs),steps=steps))
        rows[-1]['return']=sum(s['reward'] for s in steps)
    return dict(config=c,episodes=rows,resources=dict(completed=Work(real_steps=9600).payload(),unknown_upper=Work().payload()))


def test_profile_and_fresh_seeds_preserve_old_profile():
    new=json.loads(r.CONFIG.read_text());old=json.loads(h.CONFIG.read_text())
    assert h.run_paths(new)['result']!=h.RESULT
    assert h.run_paths(old)['result']==h.RESULT
    assert len(h.requested_seeds(new))==3216
    assert not h.requested_seeds(new)&h.requested_seeds(old)
    prior=json.loads(h.RESULT.read_text())
    assert all(not h.seed_collisions(row,h.requested_seeds(new)) for row in prior['episodes'])
    assert h.analyze(prior['episodes'],old)==prior['analysis']


def test_correct_four_episode_aggregation_and_directional_screen():
    p=grid();assert h.validate_result(p,p['config'])
    a=h.analyze(p['episodes'],p['config'])
    assert a['paired_contrasts']['acrobot']['rank_blend']['flat_anchor']['mean']==pytest.approx(2.)
    s=r.directional_screen(p)
    assert s['acrobot_gain_replicated_point_screen'] and s['pendulum_harm_replicated_point_screen']
    assert not s['scientific_control_success'] and s['new_independent_models']==0


def test_model_sign_consistency_not_pooled_episode_count():
    p=grid()
    for row in p['episodes']:
        if row['family']=='acrobot' and row['model_bundle']==1 and row['controller']=='rank_blend':
            for s in row['steps']:s['reward']=-1.001
            row['return']=sum(s['reward'] for s in row['steps'])
    assert not r.directional_screen(p)['acrobot_gain_replicated_point_screen']


@pytest.mark.parametrize('change',['seed','model','condition','episode','duplicate','planner','nan','unknown','shortened'])
def test_incomplete_or_invalid_replication_rejected(change):
    p=grid();c=p['config']
    if change=='seed':p['episodes'][0]['reset_seed']=2103000000
    if change=='model':p['episodes']=[x for x in p['episodes'] if x['model_bundle']!=1]
    if change=='condition':p['episodes']=[x for x in p['episodes'] if x['controller']!='rank_blend']
    if change=='episode':p['episodes']=[x for x in p['episodes'] if x['episode']!=3]
    if change=='duplicate':p['episodes'][-1]=copy.deepcopy(p['episodes'][0])
    if change=='planner':p['episodes'][0]['steps'][0]['planner_seed']+=1
    if change=='nan':p['episodes'][0]['return']=float('nan')
    if change=='unknown':p['resources']['unknown_upper']['real_steps']=1
    if change=='shortened':c['episodes']=[0,1]
    with pytest.raises(ValueError):r.directional_screen(p)


def test_resource_plans_retain_registered_ceilings():
    import numpy as np
    c=json.loads(r.CONFIG.read_text())
    per_set=0
    for name in c['controllers']:
        strategy=h.controllers()[name]
        plan=h.operation_plan(strategy,np.zeros(3),3)
        assert sum(op.cost.imagined_transitions for op in plan)<=1536
        per_set+=sum(op.cost.model_calls for op in plan)
    assert per_set*16*200==428800
    assert c['env_cap']==48*200 and c['imagined_cap']==c['env_cap']*1536


def test_new_exact_allocation_and_parent_hashes_are_separate():
    c=json.loads(r.CONFIG.read_text());paths=h.run_paths(c)
    allocation=json.loads(paths['allocation'].read_text())
    assert allocation['config_sha256']==h.sha(paths['config'])
    assert allocation['protocol_sha256']==h.sha(paths['protocol'])
    assert allocation['session_used_before_s']==383.939872001008
    assert allocation['env_cap']==9600 and allocation['runs']==1 and not allocation['automatic_retry']
    for name,expected in allocation['parent_artifacts_sha256'].items():h.verify_file(h.ROOT/name,expected)
    assert paths['usage']!=h.USAGE
