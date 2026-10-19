"""Synthetic tests: no Gym construction, learned inference or training."""
import copy
import gzip
import itertools
import json

import numpy as np
import pytest

from nexus.evolution1.catalogue import digest
from nexus.evolution1.resources import Work, ReservationLedger, Limits, Clock
from nexus.evolution2 import full_policy_source as h
from nexus.evolution2.planner_adapter import FakeStepModel


def fixture():
    c=json.loads(h.CONFIG.read_text())
    rows=[]
    for f,b,e,label in itertools.product(c['families'],c['model_bundles'],c['episodes'],c['controllers']):
        reset,base=h.seeds(c,f,b,e)
        obs=[0.]*(3 if f=='pendulum' else 6)
        steps=[dict(tick=t,reward=-1.,obs=obs.copy(),next_obs=obs.copy(),action=1,
                    planner_seed=base+t,terminated=False,truncated=t==199) for t in range(200)]
        rows.append(dict(family=f,model_bundle=b,episode=e,controller=label,reset_seed=reset,
                         planner_base=base,initial_obs_hash=digest(obs),steps=steps,return_=-200.))
        rows[-1]['return']=rows[-1].pop('return_')
    return c,dict(episodes=rows,resources=dict(completed=Work(real_steps=6400).payload(),unknown_upper=Work().payload()))


def test_complete_grid_and_descriptive_analysis():
    c,p=fixture()
    assert h.validate_result(p,c)
    a=h.analyze(p['episodes'],c)
    assert not a['scientific_control_success']
    assert not any(a['point_screen_by_generated'].values())


@pytest.mark.parametrize('change',['model','condition','episode','duplicate','nan','infinite_return',
                                  'bool_reward','accounting','seed','planner','obs','continuity','early_end','unknown'])
def test_invalid_partial_or_unpaired_rejected(change):
    c,p=fixture();r=p['episodes'][0];s=r['steps'][0]
    if change=='model':p['episodes']=[x for x in p['episodes'] if x['model_bundle']!=0]
    if change=='condition':p['episodes']=[x for x in p['episodes'] if x['controller']!='switch']
    if change=='episode':p['episodes'].pop()
    if change=='duplicate':p['episodes'][-1]=copy.deepcopy(r)
    if change=='nan':s['reward']=float('nan')
    if change=='infinite_return':r['return']=float('inf')
    if change=='bool_reward':s['reward']=True
    if change=='accounting':r['return']+=1
    if change=='seed':r['reset_seed']+=1
    if change=='planner':s['planner_seed']+=1
    if change=='obs':s['obs']=[float('nan')]*3
    if change=='continuity':r['steps'][1]['obs'][0]=1.
    if change=='early_end':s['terminated']=True
    if change=='unknown':p['resources']['unknown_upper']['real_steps']=1
    with pytest.raises(ValueError):h.validate_result(p,c)


def test_seed_metadata_reuse_and_unique_schedule():
    c,_=fixture();seeds=h.requested_seeds(c)
    assert len(seeds)==1608
    seed=min(seeds)
    assert h.seed_collisions({'query_seeds':[seed]},seeds)=={seed}
    assert h.seed_collisions({'return':seed,'hash':str(seed),'seeds':[float(seed)]},seeds)==set()


def test_checkpoint_integrity_before_load(tmp_path):
    p=tmp_path/'model.pt';p.write_bytes(b'not a model')
    digest_=h.sha(p);h.verify_file(p,digest_)
    p.write_bytes(b'changed')
    with pytest.raises(ValueError):h.verify_file(p,digest_)
    with pytest.raises(FileNotFoundError):h.verify_file(tmp_path/'missing',digest_)
    c,_=fixture()
    with pytest.raises(ValueError):h.verify_checkpoints([],c)


@pytest.mark.parametrize('family,size',[('pendulum',3),('acrobot',6)])
@pytest.mark.parametrize('label',['flat_anchor','successor_anchor','switch','rank_blend'])
def test_actual_composed_call_shapes_equal_predeclared_plan(family,size,label):
    obs=np.ones(size,dtype=np.float32);strategy=h.controllers()[label]
    ops=h.operation_plan(strategy,obs,3)
    calls=[]
    class Counted(FakeStepModel):
        def step(self,o,a):
            calls.append(h.model_work(np.asarray(o).reshape(-1,size).shape,np.asarray(a).size))
            return super().step(o,a)
    action=h.execute(strategy,family,obs,Counted(size,3),seed=42)
    assert action in range(3)
    assert calls==[op.cost for op in ops[:-1]]
    assert sum(x.imagined_transitions for x in calls)<=1536
    assert ops[-1].cost==Work(real_steps=1)


def test_failed_step_is_not_free_and_gzip_journal_roundtrip(tmp_path):
    from dataclasses import asdict
    ops=h.operation_plan(h.controllers()['flat_anchor'],np.zeros(3),3)
    total=Work()
    for op in ops:total=total.plus(op.cost)
    ledger=ReservationLedger(ops,Limits(total,total,1000,1000))
    ticket=ledger.reserve(ops[0].key,Clock(1,1))
    ledger.settle(ticket,'interrupted',Clock(2,2))
    report=ledger.close(Clock(3,3))
    assert report.physical_unknown_upper_bound==ops[0].cost
    assert report.status!='complete_execution'
    path=tmp_path/'journal.gz'
    with gzip.open(path,'xb') as out:out.write(json.dumps([asdict(x) for x in report.events]).encode())
    with gzip.open(path,'rt') as src:assert len(json.load(src))==len(report.events)


def test_locked_config_rejects_quiet_reduction():
    c,_=fixture();c['episode_steps']=50
    with pytest.raises(ValueError):h.validate_config(c)
