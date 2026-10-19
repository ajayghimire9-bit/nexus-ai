"""Deterministic numeric fixtures; no real simulator/model execution."""
from copy import deepcopy
import importlib.util
import itertools
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from nexus.evolution2 import calibration_execution as x
from nexus.evolution2 import forecast_calibration as a
from nexus.evolution2 import post_probe as h
from nexus.evolution2.rollout_headroom import walk
from nexus.evolution2.planner_adapter import iid_sequences
from nexus.world.rewards import pendulum_step_reward, acrobot_step_reward

ROOT=Path(__file__).resolve().parents[1]


def api():
    spec=importlib.util.spec_from_file_location('calibration_host_test',ROOT/'scripts/run_e3_11_post_probe.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.configure_calibration()
    return module


def fixture():
    c,analysis=x.settings(api());records=[];rows=[]
    means={f'{f}:{b}':float(b+1) for f,b in itertools.product(c['families'],c['model_bundles'])}
    for f,b,e in sorted(a.expected_grid(analysis)):
        s=h.seeds(c,f,e);obs=[1.,0.,0.] if f=='pendulum' else [1.,0.,1.,0.,0.,0.]
        reward=pendulum_step_reward if f=='pendulum' else acrobot_step_reward
        prefix=[]
        for tick,action in enumerate(np.random.default_rng(s['probe']).integers(0,3,size=8)):
            prefix.append(dict(tick=tick,planner_seed=s['probe'],obs=obs,next_obs=obs,action=int(action),
                reward=float(reward(np.asarray(obs),int(action),np.asarray(obs))[0]),terminated=False,truncated=False))
        paths={label:walk(obs,lambda o,t:(1,o,0.),reward) for label in c['controllers']}
        tails=iid_sequences(s['evidence']+1,16,15,3);common={}
        for label in c['controllers']:
            actions=np.column_stack((np.ones(16,dtype=int),tails));scores=np.zeros(16)
            for tick in range(16):scores+=reward(np.tile(obs,(16,1)),actions[:,tick],np.tile(obs,(16,1)))
            common[label]=dict(actions=actions.tolist(),states=np.tile(obs,(16,16,1)).tolist(),termination_estimates=np.zeros((16,16)).tolist(),scores=scores.tolist())
        actual={label:dict(restored_hash='same',steps=[dict(tick=tick,planner_seed=s['planner']+tick,obs=obs,next_obs=obs,action=1,
            reward=float(reward(np.asarray(obs),1,np.asarray(obs))[0]),terminated=False,truncated=tick==199) for tick in range(8,200)]) for label in c['controllers']}
        predictions=dict(policy_forecast=0.,common_tail=0.,training_mean=means[f'{f}:{b}'])
        row=a.capture_pair((f,b,e),predictions,lambda r:r['forecast_sha256'],lambda label:[t['reward'] for t in actual[label]['steps']],analysis)
        records.append(dict(family=f,bundle=b,episode=e,prefix=prefix,prefix_hash=a.digest(prefix),paths=paths,common=common,
            actual=actual,restoration_hash='same',initial_observation=obs,forecast_sha256=row['forecast_sha256'],forecast_planner_seeds=[s['planner']+t for t in range(8,24)]));rows.append(row)
    totals=dict(real_steps=6272,imagined_transitions=9932800,model_calls=393728,network_forwards=393728)
    p=dict(rows=rows,records=records,resources=dict(reserved=totals,completed=totals,unknown_upper={k:0 for k in totals}),observed_calls=393728,observed_forwards=393728,
        models=[dict(family=f,bundle=b,before='fixed',after='fixed') for f,b in itertools.product(c['families'],c['model_bundles'])])
    return p,c,analysis,means


def test_complete_raw_capture_replays_rewards_forecasts_and_budget():
    assert x.validate(*fixture())


@pytest.mark.parametrize('fault',['model','case','path','reward','boundary','continuity','restoration',
    'first_action','common_tails','forecast_seed','prediction','prefix_hash','probe_action','fingerprint','counts','unknown','forwards'])
def test_raw_capture_rejects_missing_or_inconsistent_execution(fault):
    p,c,config,means=fixture();r=p['records'][0]
    if fault=='model':p['models'].pop()
    elif fault=='case':p['records'].pop()
    elif fault=='path':r['actual']['rank_blend']['steps'].pop()
    elif fault=='reward':r['actual']['rank_blend']['steps'][0]['reward']+=1
    elif fault=='boundary':r['actual']['rank_blend']['steps'][0]['terminated']=True
    elif fault=='continuity':r['actual']['rank_blend']['steps'][0]['obs']=[0.,1.,0.,1.,0.,0.]
    elif fault=='restoration':r['actual']['rank_blend']['restored_hash']='different'
    elif fault=='first_action':r['actual']['rank_blend']['steps'][0]['action']=2
    elif fault=='common_tails':r['common']['rank_blend']['actions'][0][2]=(r['common']['rank_blend']['actions'][0][2]+1)%3
    elif fault=='forecast_seed':r['forecast_planner_seeds'][0]+=1
    elif fault=='prediction':p['rows'][0]['predictions']['training_mean']+=1
    elif fault=='prefix_hash':r['prefix'][0]['reward']+=1
    elif fault=='probe_action':
        r['prefix'][0]['action']=(r['prefix'][0]['action']+1)%3;r['prefix_hash']=a.digest(r['prefix'])
    elif fault=='fingerprint':p['models'][0]['after']='changed'
    elif fault=='counts':p['resources']['completed']=dict(p['resources']['completed'],real_steps=6271)
    elif fault=='unknown':p['resources']['unknown_upper']['model_calls']=1
    elif fault=='forwards':p['observed_forwards']-=1
    with pytest.raises(ValueError):x.validate(p,c,config,means)


def test_profile_preserves_original_results_and_preparation():
    host=api();c,config=x.settings(host)
    assert host.CALIBRATION_PROFILE and host.ROLLOUT_PROFILE
    assert host.FROZEN.name=='e3_11_frozen_selector.json'
    assert host.RESULT.name=='e3_11b_forecast_calibration.json'
    assert host.PREDICTIONS.name=='e3_11b_forecast_predecision.jsonl'
    assert config['execution_authorized'] is False
    assert len(h.registered_seeds(c))==1568


def test_seed_audit_detects_closed_config_metadata_before_collection(tmp_path):
    host=api();c,_=x.settings(host);proposed=min(h.registered_seeds(c))
    path=tmp_path/'closed.json';path.write_text(json.dumps({'env_seed':proposed}))
    with pytest.raises(ValueError,match='closed_or_reserved_seed_collision'):
        host.seed_audit(c,[str(path)])


@pytest.mark.parametrize('key,value',[('real_cap',6273),('time_cap_s',181),('training_episodes',[0]),('env_seed_base',2121000000)])
def test_execution_configuration_changes_fail_closed(tmp_path,key,value):
    host=api();c,_=x.settings(host);c[key]=value
    path=tmp_path/'config.json';path.write_text(json.dumps(c));host.CONFIG=path
    with pytest.raises(ValueError,match='locked_calibration'):x.settings(host)


def test_worker_cannot_launch_without_consumed_parent_receipt(tmp_path):
    host=api();host.USAGE=tmp_path/'usage.json';host.USAGE.write_text(json.dumps({'parent_pid':-1}))
    with pytest.raises(ValueError,match='parent_launch'):x.worker(host)


def test_preflight_refuses_reused_consumed_paths(tmp_path):
    host=api();host.USAGE=tmp_path/'used.json';host.USAGE.write_text('{}')
    with pytest.raises(ValueError,match='one_run_only'):x.preflight(host)


def test_saved_complete_capture_replays_without_checkpoint_deserialization():
    host=api();p=json.loads(host.RESULT.read_text());c,config=x.settings(host)
    validation=json.loads(host.VALIDATION.read_text())
    assert p['declared_complete'] and validation['valid']
    assert validation['capture_sha256']==host.sha(host.RESULT)
    means=a.training_means(host.ROOT/config['training_prior'],config['training_prior_sha256'],config)
    assert x.validate(p,c,config,means)
    expected=a.analyze(p['rows'],config);expected['label']='development_forecast_point_screen_passed_not_confirmed' if expected['point_screen'] else 'forecast_utility_not_established'
    assert expected==p['analysis']
    assert validation['resources_verified']==p['resources']['completed']
    assert validation['new_real_steps']==validation['new_imagined_transitions']==0
    assert validation['model_inference'] is False
