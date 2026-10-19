"""Authored fixtures and saved metadata only; no environment/model execution."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.evolution2 import horizon_calibration as h
from nexus.evolution2 import calibration_execution as x
from nexus.evolution2 import forecast_calibration as a
from nexus.evolution2 import post_probe
from nexus.evolution2.rollout_headroom import walk
from nexus.evolution2.planner_adapter import iid_sequences
from nexus.world.rewards import pendulum_step_reward,acrobot_step_reward
from test_e3_11b_calibration_execution import fixture as old_fixture

ROOT=Path(__file__).resolve().parents[1]


def api():
    spec=importlib.util.spec_from_file_location('horizon_profile_test',ROOT/'scripts/run_e3_11_post_probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.configure_horizon();return m


def fixture():
    p,_,_,means=old_fixture();c,config=x.settings(api())
    for r in p['records']:
        s=post_probe.seeds(c,r['family'],r['episode']);obs=r['initial_observation'];reward=pendulum_step_reward if r['family']=='pendulum' else acrobot_step_reward
        for tick,action in enumerate(np.random.default_rng(s['probe']).integers(0,3,size=8)):
            r['prefix'][tick].update(action=int(action),planner_seed=s['probe'],reward=float(reward(np.asarray(obs),int(action),np.asarray(obs))[0]))
        r['prefix_hash']=a.digest(r['prefix']);r['forecast_planner_seeds']=[s['planner']+t for t in range(8,72)]
        for label in c['controllers']:
            r['paths'][label]=walk(obs,lambda o,t:(1,o,0.),reward,steps=64)
            tails=iid_sequences(s['evidence']+1,16,15,3);actions=np.column_stack((np.ones(16,dtype=int),tails));scores=np.zeros(16)
            for t in range(16):scores+=reward(np.tile(obs,(16,1)),actions[:,t],np.tile(obs,(16,1)))
            r['common'][label]['actions']=actions.tolist();r['common'][label]['scores']=scores.tolist()
            for step in r['actual'][label]['steps']:step['planner_seed']=s['planner']+step['tick']
    totals=dict(real_steps=6272,imagined_transitions=12224512,model_calls=485888,network_forwards=485888)
    p['resources']['completed']=totals;p['resources']['reserved']=totals;p['observed_calls']=p['observed_forwards']=485888
    return p,c,config,means


def test_complete_64_capture_and_prefix_analysis():
    p,c,config,means=fixture();assert x.validate(p,c,config,means)
    result=h.analyze(p,c,config)
    assert result['forecast_horizons']==[16,64] and result['primary_actual_steps']==192
    assert result['label']=='longer_horizon_utility_not_established'
    assert set(result['families']['pendulum']['paired'])=={'policy_16','training_mean'}
    assert set(result['families']['acrobot']['models'][0]['methods'])=={'policy_forecast','policy_16','common_tail','training_mean'}


def test_short_score_is_exact_continuous_prefix_and_ignores_later_changes():
    def evaluate(o,t):return 1,o+1,.01
    full=walk([0.],evaluate,lambda o,a,n:n[0],steps=64)
    short=walk([0.],evaluate,lambda o,a,n:n[0],steps=16)
    assert h.prefix_score(full)==short['predicted_score']
    modified=deepcopy(full);modified['steps'][20]['predicted_reward']+=1000
    assert h.prefix_score(modified)==h.prefix_score(full)
    modified['steps'][2]['predicted_reward']+=1
    assert h.prefix_score(modified)!=h.prefix_score(full)


@pytest.mark.parametrize('fault',['missing_model','missing_episode','missing_horizon_steps','wrong_seed','nan','changed_first16','counts','unknown'])
def test_long_capture_rejects_incomplete_or_corrupted_data(fault):
    p,c,config,means=fixture()
    if fault=='missing_model':p['models'].pop()
    elif fault=='missing_episode':p['rows'].pop()
    elif fault=='missing_horizon_steps':p['records'][0]['paths']['rank_blend']['steps'].pop()
    elif fault=='wrong_seed':p['records'][0]['forecast_planner_seeds'][-1]+=1
    elif fault=='nan':p['records'][0]['paths']['rank_blend']['steps'][20]['predicted_reward']=float('nan')
    elif fault=='changed_first16':p['records'][0]['paths']['rank_blend']['steps'][2]['predicted_reward']+=1
    elif fault=='counts':p['observed_forwards']-=1
    elif fault=='unknown':p['resources']['unknown_upper']['model_calls']=1
    with pytest.raises(ValueError):x.validate(p,c,config,means)


@pytest.mark.parametrize('key,value',[('forecast_steps',128),('time_cap_s',900),('env_seed_base',2131000000),('model_call_cap',485889)])
def test_locked_horizon_config_rejects_changes(tmp_path,key,value):
    m=api();c,_=x.settings(m);c[key]=value;path=tmp_path/'settings.json';path.write_text(json.dumps(c));m.CONFIG=path
    with pytest.raises(ValueError,match='locked_horizon'):x.settings(m)


def test_new_profile_paths_and_seed_roles_are_disjoint_from_closed_b():
    m=api();c,_=x.settings(m);old=json.loads((ROOT/'configs/e3_11b_forecast_calibration_execution.json').read_text())
    assert not post_probe.registered_seeds(c)&post_probe.registered_seeds(old)
    assert m.RESULT.name=='e3_11d_horizon_calibration.json' and m.HORIZON_PROFILE
    assert len(post_probe.registered_seeds(c))==1568


def test_closed_seed_reuse_is_rejected(tmp_path):
    m=api();c,_=x.settings(m);p=tmp_path/'closed.json';p.write_text(json.dumps({'planner_seed':min(post_probe.registered_seeds(c))}))
    with pytest.raises(ValueError,match='closed_or_reserved_seed_collision'):m.seed_audit(c,[str(p)])


def test_model_units_and_practical_screen_are_retained():
    p,c,config,means=fixture();result=h.analyze(p,c,config)
    for family in result['families'].values():
        assert family['paired']['policy_16']['accuracy']['n_models']==2
        assert family['paired']['policy_16']['accuracy']['df']==1
        assert family['point_screen'] is False
