"""Authored fixtures only: no real environments or learned network execution."""
from copy import deepcopy
import importlib.util
import itertools
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.evolution1.catalogue import digest
from nexus.evolution1.resources import Work,Operation,Clock
from nexus.evolution2 import post_probe as h
from nexus.evolution2.staged_study import StagedStudy
from test_e3_10_metered_model import ToyStep


ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/e3_11_post_probe.json').read_text())


class ToyEnv:
    """Fictional deterministic state with an independently copied RNG."""
    def __init__(self):
        self.state=np.array([0.]);self.np_random=np.random.default_rng(4);self._elapsed_steps=8
    @property
    def unwrapped(self):return self
    def step(self,action):
        self.state=self.state+action+self.np_random.normal();self._elapsed_steps+=1
        return self.state.copy(),float(self.state[0]),False,False,{}


def test_exact_copy_restores_rng_time_limit_and_independent_state():
    env=ToyEnv();a,ha=h.restore_copy(env);b,hb=h.restore_copy(env)
    assert ha==hb==h.simulator_fingerprint(env)
    for action in (0,2,1):
        aa=a.step(action);bb=b.step(action);np.testing.assert_array_equal(aa[0],bb[0]);assert aa[1:]==bb[1:]
    assert env._elapsed_steps==8 and a._elapsed_steps==11
    assert h.simulator_fingerprint(env)==ha!=h.simulator_fingerprint(a)


def example_evidence(gap=0.,dim=3):
    return {label:dict(scores=[float(gap if label=='rank_blend' else 0)]*16,
        actions=np.ones((16,16),dtype=int).tolist(),states=np.zeros((16,16,dim)).tolist(),
        termination_estimates=np.zeros((16,16)).tolist()) for label in ('successor_anchor','rank_blend')}


def training():
    c=config()
    return [dict(family=f,bundle=b,episode=e,role='training',features=[1.,float(e),.01*e,.1],
        returns=dict(successor_anchor=0.,rank_blend=float((e-1)*(b+1)))) for f,b,e in sorted(h.grid(c,'training'))]


def test_training_only_frozen_selector_no_query_feedback_path():
    rows=training();selector=h.ProbeSelector(rows,config());before=selector.fingerprint()
    a=selector.decide('pendulum',0,[1.,2.,.02,.1]);b=selector.decide('pendulum',0,[1.,2.,.02,.1])
    assert a==b and selector.fingerprint()==before
    assert all(m.fit_calls==1 for m in selector.models.values())
    poison=deepcopy(rows);poison[0]['role']='evaluation'
    with pytest.raises(ValueError):h.ProbeSelector(poison,config())
    with pytest.raises(ValueError):h.ProbeSelector(rows[1:],config())


def test_genuine_forecasts_and_probe_outcomes_can_change_features():
    a=h.feature_vector(example_evidence(),.1);b=h.feature_vector(example_evidence(3.),.1)
    assert a!=b and a[0]==1 and b[1]==3
    assert h.feature_vector(example_evidence(),.3)[3]==.3


def test_metered_host_counts_model_hook_and_environment_only_once():
    class Journal:
        def __init__(self):self.rows=[]
        def write(self,x):self.rows.append(json.loads(x))
    c=config();journal=Journal();host=h.Host(c,lambda:Clock(0,0),journal)
    wm=ToyStep();wm.net.obs_dim=1;host.bind(wm)
    ops=(Operation('m','model',Work(imagined_transitions=1,model_calls=1,network_forwards=1)),
         Operation('e','environment',Work(real_steps=1)))
    value,report=host.perform(ops,lambda d:(d.model('m',np.zeros((1,1)),[0]),d.environment('e',ToyEnv(),1)),{'fixture':True})
    assert host.completed==Work(real_steps=1,imagined_transitions=1,model_calls=1,network_forwards=1)
    assert len(journal.rows)==1 and report.status=='complete_execution' and host.instrument.network_forwards==1
    c['real_cap']=1
    with pytest.raises(ValueError,match='global_pre_dispatch_cap'):host.perform(ops,lambda d:None,{})


def test_seed_roles_pair_bundles_and_reject_closed_streams():
    c=config();proposed=h.registered_seeds(c)
    assert len(proposed)==2744
    manifest=h.manifest(c,'a'*40);StagedStudy(manifest)
    closed=[h.seeds(c,'pendulum',3)['planner']]
    with pytest.raises(ValueError,match='closed'):StagedStudy(manifest,closed_seeds=closed)
    manifest['cases']=[r for r in manifest['cases'] if r['task']!='pendulum:0']
    with pytest.raises(ValueError,match='complete_case_grid'):StagedStudy(manifest)


def capture():
    c=config();pairs=[]
    for role in ('training','evaluation'):
        for f,b,e in sorted(h.grid(c,role)):
            obs=[1.,0.,0.] if f=='pendulum' else [1.,0.,1.,0.,0.,0.]
            prefix=[dict(task=f'{f}:{b}',episode=e,step=i,phase='support',observation=obs,action=1,next_observation=obs,reward=0.) for i in range(8)]
            paths={}
            for label in c['controllers']:
                paths[label]=dict(restored_hash='same',steps=[dict(tick=i,obs=obs,next_obs=obs,action=1,reward=0.,terminated=False,truncated=i==199,planner_seed=h.seeds(c,f,e)['planner']+i) for i in range(8,200)])
            r=dict(family=f,bundle=b,episode=e,role=role,prefix=prefix,support_hash=digest(tuple(prefix)),features=[1.,0.,0.,.1],evidence=example_evidence(dim=len(obs)),support_prediction_mae=.1,
                restoration_hash='same',paths=paths,returns={k:0. for k in c['controllers']})
            if role=='evaluation':r['decision']=dict(recipe_hash='frozen',choices={m:'successor_anchor' for m in c['methods']},estimated_advantage=0.)
            pairs.append(r)
    return dict(pairs=pairs,selector_hash='frozen',resources=dict(completed=dict(real_steps=10976,imagined_transitions=16129288,model_calls=638596,network_forwards=638596),unknown_upper=dict(real_steps=0,imagined_transitions=0,model_calls=0,network_forwards=0)),
        observed_model_calls=638596,observed_forwards=638596,models=[dict(family=f,bundle=b,before='hash',after='hash') for f,b in itertools.product(c['families'],c['model_bundles'])])


@pytest.mark.parametrize('corrupt',['family','model','episode','controller','reward','support','tick','frozen','counts'])
def test_complete_grid_and_pairing_failures(corrupt):
    c=config();p=capture();assert h.validate(p,c)
    if corrupt=='family':p['pairs']=[r for r in p['pairs'] if r['family']!='pendulum']
    elif corrupt=='model':p['pairs']=[r for r in p['pairs'] if r['bundle']!=0]
    elif corrupt=='episode':p['pairs'].pop()
    elif corrupt=='controller':p['pairs'][0]['paths'].pop('rank_blend')
    elif corrupt=='reward':p['pairs'][0]['paths']['rank_blend']['steps'][0]['reward']=float('nan')
    elif corrupt=='support':p['pairs'][0]['support_hash']='changed'
    elif corrupt=='tick':p['pairs'][0]['paths']['rank_blend']['steps'][1]['planner_seed']+=1
    elif corrupt=='frozen':p['models'][0]['after']='changed'
    elif corrupt=='counts':p['resources']['completed']['real_steps']+=192
    with pytest.raises(ValueError):h.validate(p,c)


def test_equal_model_weighting_and_decoder_level_not_episode_ci():
    c=config();p=capture();rows=[r for r in p['pairs'] if r['role']=='evaluation']
    for r in rows:
        r['returns']['rank_blend']=2.+r['bundle']*2
        r['decision']['choices']['contextual_selector']='rank_blend'
    stats=h.analyze(rows,c)
    contrast=stats['families']['pendulum']['contrasts']['model_mean']
    assert contrast['per_model']==[2.,4.] and contrast['mean']==3.
    np.testing.assert_allclose(contrast['ci95'],[3-12.7062047364,3+12.7062047364])
    assert stats['label']=='development_point_screen_passed_not_confirmed'
    # Replicating already-used episodes cannot narrow a decoder-level interval.
    assert h.analyze(rows*3,c)['families']['pendulum']['contrasts']['model_mean']['ci95']==contrast['ci95']


def test_budget_and_shared_probe_difference_identity():
    c=config();assert c['real_cap']==28*(8+2*192)==10976
    assert c['imagined_cap']==28*(2*192*1536+2*1536+512+8)
    for probe,a,b in [(-5.,-20.,-30.),(1.,2.,-3.)]:assert (probe+a)-(probe+b)==a-b
