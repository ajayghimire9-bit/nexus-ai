"""Synthetic arrays/pure callbacks only; no environments or neural inference."""
from copy import deepcopy
from dataclasses import asdict
import itertools
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.evolution2 import mutation_control as m
from nexus.evolution2.generated_strategies import StrategyGenerator
from nexus.evolution2.full_policy_source import controllers
from nexus.evolution1.catalogue import digest
from nexus.world.rewards import pendulum_step_reward,acrobot_step_reward

ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/e3_12_mutation_control.json').read_text())


def fixture():
    c=config();rows=[]
    for f,b,e,role in sorted(m.expected(c)):
        obs=[1.,0.,0.] if f=='pendulum' else [1.,0.,1.,0.,0.,0.]
        reward=pendulum_step_reward if f=='pendulum' else acrobot_step_reward
        r=float(reward(np.asarray(obs),1,np.asarray(obs))[0]);reset,planner=m.seed_pair(c,f,b,e)
        strategies={key:StrategyGenerator(7,adaptive=key=='learned',mutation_credit=True).paired_child(controllers()['successor_anchor'],controllers()['flat_anchor'].left,m.proposal_uniform(c,f,b,e)).payload() for key in m.METHODS}
        steps=[dict(tick=t,planner_seed=planner+t,obs=obs,next_obs=obs,action=1,reward=r,terminated=False,truncated=t==199) for t in range(200)]
        labels=['parent',*m.METHODS]+(['fixed_blend'] if role=='evaluation' else [])
        rows.append(dict(family=f,bundle=b,episode=e,role=role,strategies=strategies,
            initial_observation=obs,restored_hash='fixed',before={x:dict(switch=.5,rank_blend=.5) for x in m.METHODS},after={x:dict(switch=.5,rank_blend=.5) for x in m.METHODS},
            paths={label:dict(steps=deepcopy(steps),restored_hash='fixed',cpu_s=1.,return_value=200*r) for label in labels},
            protocol=dict(reset_seed=reset,planner_seed=planner,context_hash=digest(obs),pair_id=f'{f}:{b}:{e}')))
    for row in rows:
        for path in row['paths'].values():path['return']=path.pop('return_value')
    p=dict(rows=rows,final_policies={f'{f}:{b}':{x:dict(switch=.5,rank_blend=.5) for x in m.METHODS} for f,b in itertools.product(c['families'],c['model_bundles'])},
        models=[dict(family=f,bundle=b,before='same',after='same') for f,b in itertools.product(c['families'],c['model_bundles'])],
        observed=dict(model_calls=0,network_forwards=0,imagined_transitions=0),resources=dict(completed=dict(real_steps=32000,model_calls=0,network_forwards=0,imagined_transitions=0),unknown_upper=dict(real_steps=0)))
    return p,c


def test_full_grid_and_statistics_are_model_level():
    p,c=fixture();assert m.validate(p,c)
    a=m.analyze(p['rows'],c)
    assert a['label']=='useful_mutation_learning_not_established'
    assert a['families']['pendulum']['contrasts']['random']['ci95']==[0.,0.]
    assert len(a['families']['pendulum']['models'])==2


@pytest.mark.parametrize('fault',['seed','model','method','tick','return','nan','continuity','boundary','frozen','forward','query_update','proposed_child','reset'])
def test_missing_invalid_or_leaking_data_fails_closed(fault):
    p,c=fixture();row=p['rows'][0]
    if fault=='seed':p['rows'].pop()
    elif fault=='model':p['rows']=[r for r in p['rows'] if r['bundle']!=1]
    elif fault=='method':del row['paths']['learned']
    elif fault=='tick':row['paths']['parent']['steps'].pop()
    elif fault=='return':row['paths']['parent']['return']+=1
    elif fault=='nan':row['paths']['parent']['return']=float('nan')
    elif fault=='continuity':row['paths']['parent']['steps'][1]['obs']=[0.]*6
    elif fault=='boundary':row['paths']['parent']['steps'][0]['truncated']=True
    elif fault=='frozen':p['models'][0]['after']='other'
    elif fault=='forward':p['observed']['network_forwards']=1
    elif fault=='query_update':next(r for r in p['rows'] if r['role']=='evaluation')['after']['learned']['switch']=.6
    elif fault=='proposed_child':row['strategies']['learned']['threshold']=.99
    elif fault=='reset':row['protocol']['reset_seed']+=1
    with pytest.raises(ValueError):m.validate(p,c)


def test_seed_registration_covers_every_tick_and_disjoint_roles():
    c=config();seeds=m.requested_seeds(c)
    assert len(seeds)==4*12*201
    train={s for f,b,e in itertools.product(c['families'],c['model_bundles'],c['training_episodes']) for a,z in [m.seed_pair(c,f,b,e)] for s in [a,*range(z,z+200)]}
    test={s for f,b,e in itertools.product(c['families'],c['model_bundles'],c['evaluation_episodes']) for a,z in [m.seed_pair(c,f,b,e)] for s in [a,*range(z,z+200)]}
    assert not train&test


def test_feedback_changes_only_learned_structural_proposals_not_leaves():
    p=controllers()['successor_anchor'];partner=controllers()['flat_anchor'].left
    learned=StrategyGenerator(1,mutation_credit=True);random=StrategyGenerator(1,adaptive=False,mutation_credit=True)
    child=learned.paired_child(p,partner,.2)
    common=dict(kind='observed_full_policy_return',phase='training',pair_id='p',context_hash='h',reset_seed=1,planner_seed=2,horizon=200,planning_cap=1536,cpu_s=.01)
    a=dict(common,strategy=p.fingerprint,event='a');a['return']=0.
    b=dict(common,strategy=child.fingerprint,event='b');b['return']=300.
    for g in (learned,random):g.observe_mutation(p,child,a,b)
    assert learned.paired_child(p,partner,.55).kind=='switch'
    assert random.paired_child(p,partner,.55).kind=='rank_blend'
    assert learned.inner.learned_state()==random.inner.learned_state()
    with pytest.raises(ValueError):learned.observe_mutation(p,child,a,b)
    a['phase']='evaluation'
    with pytest.raises(ValueError):learned.observe_mutation(p,child,a,b)


@pytest.mark.parametrize('value',[True,-1.,1.,float('nan')])
def test_proposal_rejects_invalid_uniform(value):
    with pytest.raises(ValueError):StrategyGenerator(1).paired_child(controllers()['successor_anchor'],controllers()['flat_anchor'].left,value)


def test_no_proposal_rng_change_and_deterministic_uniforms():
    c=config();g=StrategyGenerator(1,mutation_credit=True);state=g.rng.getstate()
    child=g.paired_child(controllers()['successor_anchor'],controllers()['flat_anchor'].left,m.proposal_uniform(c,'pendulum',0,0))
    assert state==g.rng.getstate()
    assert child==g.paired_child(controllers()['successor_anchor'],controllers()['flat_anchor'].left,m.proposal_uniform(c,'pendulum',0,0))


def test_query_outcomes_do_not_change_policy_replay():
    p,c=fixture();before=m.replay_learning(p['rows'],c)
    for row in p['rows']:
        if row['role']=='evaluation':
            for path in row['paths'].values():path['steps'][0]['reward']=100000.
    assert m.replay_learning(p['rows'],c)==before


def test_generic_dispatch_preserves_anchor_action_and_exact_call_schedule():
    from nexus.evolution2.post_probe import Dispatch
    from nexus.evolution2.full_policy_source import operation_plan
    class SyntheticDispatch(Dispatch):
        def __init__(self):self.trace=[]
        def model(self,key,obs,actions):
            self.trace.append((key,np.asarray(actions).tolist()))
            return np.asarray(obs).copy(),np.zeros(len(obs))
    obs=np.array([1.,0.,0.]);a=SyntheticDispatch();b=SyntheticDispatch()
    x=a.action('successor_anchor','pendulum',obs,7,'x_')
    y=b.action_strategy(controllers()['successor_anchor'],'pendulum',obs,7,'x_')
    assert x==y and a.trace==b.trace
    assert len(a.trace)==sum(o.kind=='model' for o in operation_plan(controllers()['successor_anchor'],obs,3))


def test_allocation_and_protocol_are_exactly_pinned():
    import hashlib
    a=json.loads((ROOT/'configs/e3_12_mutation_control_allocation.json').read_text())
    assert a['config_sha256']==hashlib.sha256((ROOT/'configs/e3_12_mutation_control.json').read_bytes()).hexdigest()
    assert a['protocol_sha256']==hashlib.sha256((ROOT/'docs/NEXUS_E3_12_MUTATION_CONTROL_PROTOCOL.md').read_bytes()).hexdigest()


def runner():
    import importlib.util
    spec=importlib.util.spec_from_file_location('mutation_runner',ROOT/'scripts/run_e3_12_mutation_control.py')
    api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api);return api


def test_worker_rejects_direct_unmetered_launch_before_runtime_imports(tmp_path):
    api=runner();api.USAGE=tmp_path/'use.json';api.USAGE.write_text(json.dumps(dict(parent_pid=-1)))
    with pytest.raises(ValueError,match='metered_parent'):api.worker()


def test_consumed_run_rejected_before_any_environment_or_model(tmp_path):
    api=runner();api.git=lambda *args:''
    api.RESULT=tmp_path/'existing.json';api.RESULT.write_text('{}')
    with pytest.raises(ValueError,match='one_run_consumed'):api.run()


def test_modified_configuration_is_not_authorized(tmp_path):
    api=runner();c=config();c['training_episodes'].append(99)
    api.CONFIG=tmp_path/'changed.json';api.CONFIG.write_text(json.dumps(c))
    with pytest.raises(ValueError,match='locked_one_run_allocation'):api.run()
