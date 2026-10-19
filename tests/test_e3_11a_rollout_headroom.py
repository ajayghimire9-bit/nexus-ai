"""Synthetic callbacks and metadata only; no learned inference or env steps."""
from copy import deepcopy
import importlib.util
import itertools
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.evolution2 import rollout_headroom as h
from nexus.world.rewards import pendulum_step_reward,acrobot_step_reward

ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/e3_11a_rollout_headroom.json').read_text())


def test_same_first_action_can_hide_later_policy_disagreement():
    def run(change):
        return h.walk([0.],lambda obs,t:(int(change and t>0),obs+int(change and t>0),0.),lambda o,a,n:n[0],steps=4)
    a,b=run(False),run(True)
    assert a['steps'][0]['action']==b['steps'][0]['action']
    assert a['steps'][1]['action']!=b['steps'][1]['action']
    assert b['predicted_score']>a['predicted_score']


def test_published_reward_timing_survival_and_no_state_aliasing():
    initial=np.array([1.,0.,2.],dtype=np.float32)
    result=h.walk(initial,lambda o,t:(1,np.array([1.,0.,0.]),1. if t==0 else 0.),pendulum_step_reward)
    assert result['predicted_score']==-.4 and result['final_survival']==0
    np.testing.assert_array_equal(initial,[1.,0.,2.])
    result['steps'][0]['obs'][0]=99;assert initial[0]==1


def fixture():
    c=config();rows=[]
    for f,b,offset in itertools.product(c['families'],c['model_bundles'],c['source_offsets']):
        initial=[1.,0.,0.] if f=='pendulum' else [1.,0.,1.,0.,0.,0.]
        reward=pendulum_step_reward if f=='pendulum' else acrobot_step_reward
        path=h.walk(initial,lambda obs,t:(1,obs,0.),reward)
        common=dict(actions=np.ones((16,16),dtype=int).tolist(),states=np.tile(initial,(16,16,1)).tolist(),
            termination_estimates=np.zeros((16,16)).tolist(),scores=[path['predicted_score']]*16)
        rows.append(dict(family=f,bundle=b,offset=offset,initial_observation=initial,
            paths={label:deepcopy(path) for label in c['controllers']},common={label:deepcopy(common) for label in c['controllers']}))
    return dict(rows=rows,resources=dict(completed=dict(real_steps=0,imagined_transitions=772096,model_calls=31232,network_forwards=31232),unknown_upper=dict(real_steps=0,imagined_transitions=0,model_calls=0,network_forwards=0)),
        observed_calls=31232,observed_forwards=31232,models=[dict(family=f,bundle=b,before='fixed',after='fixed') for f,b in itertools.product(c['families'],c['model_bundles'])])


@pytest.mark.parametrize('fault',['model','observation','controller','step','reward','state','nan','counts','fingerprint','common'])
def test_raw_completeness_reward_and_resource_rejection(fault):
    c=config();p=fixture();assert h.validate(p,c)
    if fault=='model':p['rows']=[r for r in p['rows'] if r['bundle']!=0]
    elif fault=='observation':p['rows'].pop()
    elif fault=='controller':p['rows'][0]['paths'].pop('rank_blend')
    elif fault=='step':p['rows'][0]['paths']['rank_blend']['steps'].pop()
    elif fault=='reward':p['rows'][0]['paths']['rank_blend']['steps'][0]['predicted_reward']=5.
    elif fault=='state':p['rows'][0]['paths']['rank_blend']['steps'][1]['obs'][0]=3.
    elif fault=='nan':p['rows'][0]['paths']['rank_blend']['predicted_score']=float('nan')
    elif fault=='counts':p['observed_forwards']-=1
    elif fault=='fingerprint':p['models'][0]['after']='changed'
    elif fault=='common':p['rows'][0]['common']['rank_blend']['scores'][0]+=1
    with pytest.raises(ValueError):h.validate(p,c)


def test_screen_does_not_upgrade_difference_without_later_action_change():
    c=config();p=fixture();assert h.analyze(p['rows'],c)['label']=='controller_specific_headroom_not_established'
    for family in c['families']:
        row=next(r for r in p['rows'] if r['family']==family)
        row['paths']['rank_blend']['predicted_score']+=1
    assert h.analyze(p['rows'],c)['label']=='controller_specific_headroom_not_established'
    for family in c['families']:
        row=next(r for r in p['rows'] if r['family']==family)
        row['paths']['rank_blend']['steps'][1]['action']=2
    assert h.analyze(p['rows'],c)['label']=='controller_specific_forecast_headroom_visible'
    for row in p['rows']:
        if row['family']=='pendulum':row['paths']['rank_blend']['steps'][0]['action']=2
    assert h.analyze(p['rows'],c)['label']=='headroom_unassessable'


def test_profile_uses_existing_runner_and_separate_consumed_paths():
    path=ROOT/'scripts/run_e3_11_post_probe.py';spec=importlib.util.spec_from_file_location('rollout_host_profile',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    old=(m.RESULT,m.FROZEN,m.PREDICTIONS);m.configure_rollout()
    assert m.RESULT!=old[0] and m.FROZEN==old[1] and m.PREDICTIONS==old[2]
    c=config();assert c['imagined_cap']==16*(16*2*(1491+1)+512)
    assert c['model_call_cap']==16*(16*(51+1+67+1)+32)
    assert c['real_cap']==0


def test_runtime_config_cannot_silently_ignore_changed_settings():
    c=config();h.validate_config(c)
    for key,value in [('rollout_steps',8),('source_offsets',[0,1,2,3]),('real_cap',1),('forecast_difference_threshold',.1)]:
        bad=deepcopy(c);bad[key]=value
        with pytest.raises(ValueError,match='locked_rollout'):h.validate_config(bad)
