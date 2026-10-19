"""Source-only tests use an authored hookable step; no neural model inference."""
from copy import deepcopy
from dataclasses import asdict
import importlib.util
import itertools
import json
import hashlib
from pathlib import Path
import numpy as np
import pytest
from nexus.evolution1.resources import Clock,Operation,Work
from nexus.evolution2.planner_evidence import ForwardCheckedStep,planner_evidence,evidence_operations
from test_e3_8_learning_interfaces import ledger_for


class ToyNet:
    def __init__(self):self.hooks=[]
    def register_forward_pre_hook(self,hook):
        self.hooks.append(hook)
        class Handle:
            def remove(inner):self.hooks.remove(hook)
        return Handle()
    def __call__(self,obs):
        for hook in list(self.hooks):hook(self,(obs,))
        return obs+.01


class ToyStep:
    def __init__(self,repetitions=1):self.net=ToyNet();self.repetitions=repetitions
    def step(self,obs,action):
        for _ in range(self.repetitions):obs=self.net(obs)
        return obs,np.zeros(len(obs))


def test_hook_counts_reservation_and_removes_itself():
    wm=ToyStep();model=ForwardCheckedStep(wm)
    plans={'incumbent':np.zeros((2,3),dtype=int),'challenger':np.ones((2,3),dtype=int)}
    ledger=ledger_for(evidence_operations(plans,3))
    result=planner_evidence(plans,[1.],model,lambda o,a,n:n[:,0],n_actions=3,
        ledger=ledger,clock=lambda:Clock(0,0),fingerprint=lambda:'fixed')
    assert len(result)==2 and not wm.net.hooks
    assert (model.calls,model.rows,model.network_forwards)==(6,12,6)
    assert ledger.close(Clock(0,0)).physical_completed_reported.network_forwards==6


@pytest.mark.parametrize('repetitions,message',[(0,'missing_network'),(2,'extra_network')])
def test_missing_extra_forwards_fail_and_remain_charged(repetitions,message):
    wm=ToyStep(repetitions);model=ForwardCheckedStep(wm)
    plans={'a':np.zeros((1,1),dtype=int),'b':np.ones((1,1),dtype=int)}
    ledger=ledger_for(evidence_operations(plans,3))
    with pytest.raises(ValueError,match=message):planner_evidence(plans,[1.],model,
        lambda o,a,n:n[:,0],n_actions=3,ledger=ledger,clock=lambda:Clock(0,0),fingerprint=lambda:'fixed')
    assert not wm.net.hooks
    assert ledger.close(Clock(0,0)).physical_unknown_upper_bound.network_forwards==1
    assert model.network_forwards<=1


def test_wrong_forward_reservation_rejected_before_any_call():
    model=ForwardCheckedStep(ToyStep())
    op=Operation('step','model',Work(imagined_transitions=1,model_calls=1,network_forwards=2))
    ledger=ledger_for((op,));ticket=ledger.reserve('step',Clock(0,0))
    with pytest.raises(ValueError,match='reservation'):model.step_reserved(np.ones((1,1)),[0],ticket)
    assert model.network_forwards==model.calls==0


def runner():
    path=Path(__file__).resolve().parents[1]/'scripts/run_e3_10_metered_model.py'
    spec=importlib.util.spec_from_file_location('metered_e310',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def capture():
    m=runner();c=json.loads(m.CONFIG.read_text());p=dict(rows=[])
    for f,b,o in itertools.product(c['families'],c['model_bundles'],c['observation_indices']):
        obs=[1.,0.,0.] if f=='pendulum' else [1.,0.,1.,0.,0.,0.]
        forecasts={}
        row=dict(family=f,bundle=b,observation_index=o,observation=obs)
        for name in c['candidate_sets']:
            x=dict(actions=np.ones((16,16),dtype=int).tolist(),states=np.tile(obs,(16,16,1)).tolist(),
                termination_estimates=np.zeros((16,16)).tolist(),selected_candidate=0)
            x['scores']=m.reward_replay(row,x).tolist();forecasts[name]=x
        row.update(evidence=forecasts,reference=deepcopy(forecasts),fingerprint_before='same',fingerprint_after='same',
            observed=dict(model_calls=64,imagined_transitions=1024,network_forwards=64,denied_forwards=0),
            receipt=dict(status='complete_execution',physical_unknown_upper_bound=asdict(Work()),
                physical_completed_reported=asdict(Work(imagined_transitions=1024,model_calls=64,network_forwards=64)),
                completed_keys=[f'{path}_{name}_{t}' for path in ('evidence','reference') for name in c['candidate_sets'] for t in range(16)]))
        p['rows'].append(row)
    ready=json.loads((m.ROOT/c['source_readiness_path']).read_text())
    p['files_after']=[dict(path=r['path'],sha256=r['sha256'],matches=True) for r in ready['integrity']['checkpoints']+ready['integrity']['source_arrays']]
    return m,c,p


@pytest.mark.parametrize('corruption',['model','observation','condition','horizon','nan','calls','frozen','files','operation'])
def test_complete_raw_grid_and_integrity_rejection(corruption):
    m,c,p=capture();assert m.validate(p,c)['imagined_transitions']==8192
    if corruption=='model':p['rows']=[r for r in p['rows'] if r['bundle']!=0]
    elif corruption=='observation':p['rows']=[r for r in p['rows'] if r['observation_index']!=0]
    elif corruption=='condition':p['rows'][0]['evidence'].pop('incumbent')
    elif corruption=='horizon':p['rows'][0]['evidence']['incumbent']['states'].pop()
    elif corruption=='nan':p['rows'][0]['evidence']['incumbent']['scores'][0]=float('nan')
    elif corruption=='calls':p['rows'][0]['observed']['model_calls']=63
    elif corruption=='frozen':p['rows'][0]['fingerprint_after']='changed'
    elif corruption=='files':p['files_after'].pop()
    elif corruption=='operation':p['rows'][0]['receipt']['completed_keys'].pop()
    with pytest.raises(ValueError):m.validate(p,c)


def test_reward_replay_checks_current_state_and_cumulative_survival():
    m,c,p=capture();row=p['rows'][0];f=row['evidence']['incumbent']
    row['observation']=[1.,0.,2.]
    f['termination_estimates'][0]=[1.]*16
    # Current-state Pendulum reward is -0.4. No later reward survives.
    np.testing.assert_allclose(m.reward_replay(row,f),[-.4]*16,rtol=0,atol=1e-12)


def test_worker_cannot_be_launched_as_an_ungated_second_run(tmp_path,monkeypatch):
    m=runner();path=tmp_path/'usage.json';path.write_text(json.dumps(dict(parent_pid=-1)))
    monkeypatch.setattr(m,'USAGE',path);monkeypatch.delenv('NEXUS_E310_PARENT',raising=False)
    with pytest.raises(ValueError,match='parent_launch'):m.worker()


def test_caps_derive_from_the_locked_full_grid():
    m=runner();c=json.loads(m.CONFIG.read_text());cells=len(m.expected(c))
    assert c['imagined_cap']==cells*2*2*16*16==8192
    assert c['network_forward_cap']==c['model_call_cap']==cells*2*2*16==512
    assert c['time_cap_s']<=c['session_remaining_before_s'] and c['real_cap']==0


def test_parent_timeout_saves_incomplete_and_refuses_a_retry(tmp_path,monkeypatch):
    m=runner();original_root=m.ROOT;c=json.loads(m.CONFIG.read_text())
    (tmp_path/'artifacts').mkdir()
    ready=tmp_path/c['source_readiness_path']
    ready.write_bytes((original_root/c['source_readiness_path']).read_bytes())
    config=tmp_path/'config.json';config.write_text(json.dumps(c))
    protocol=tmp_path/'protocol.md';protocol.write_text('synthetic timeout contract')
    allocation=tmp_path/'allocation.json';allocation.write_text(json.dumps(dict(
        authorized=True,runs=1,config_sha256=m.sha(config),protocol_sha256=m.sha(protocol))))
    for key,path in [('ROOT',tmp_path),('CONFIG',config),('PROTOCOL',protocol),
        ('ALLOCATION',allocation),('RESULT',tmp_path/'result.json'),('USAGE',tmp_path/'usage.json')]:monkeypatch.setattr(m,key,path)
    monkeypatch.setattr(m,'sha',lambda path:__import__('hashlib').sha256(Path(path).read_bytes()).hexdigest() if Path(path).exists() else 'synthetic_source_hash')
    def run(args,**kw):
        if args[0]=='git':
            class Clean:returncode=0
            return Clean()
        raise m.subprocess.TimeoutExpired(args,30)
    monkeypatch.setattr(m.subprocess,'run',run)
    monkeypatch.setattr(m.subprocess,'check_output',lambda *a,**kw:'a'*40)
    assert m.run()==1
    partial=json.loads(m.RESULT.read_text())
    assert not partial['declared_complete'] and partial['outcome']=='incomplete_time_cap'
    assert json.loads(m.USAGE.read_text())['consumed']
    with pytest.raises(ValueError,match='result_already_exists'):m.run()


def test_learning_lab_requires_verified_integration_and_labels_it_separately(tmp_path):
    from nexus.evolution2.learning_lab import load_integration,render
    folder=tmp_path/'artifacts';folder.mkdir()
    p=dict(declared_complete=True,outcome='metered_inference_equivalence_verified',execution_sha='fixture',
        rows=[{}]*8,wall_s=1.,resources=dict(real_steps=0,imagined_transitions=8192,model_calls=512,network_forwards=512))
    raw=json.dumps(p).encode();(folder/'e3_10_metered_model.json').write_bytes(raw)
    val=dict(valid=True,capture_sha256=hashlib.sha256(raw).hexdigest(),resources_verified=p['resources'])
    (folder/'e3_10_metered_model_validation.json').write_text(json.dumps(val))
    status=load_integration(tmp_path)
    data=dict(kind='historical_training_replay',live=False,rows=[{}])
    page=render(data,integration=status)
    assert 'no new environment returns' in page and 'Separate from the historical return replay' in page
    assert 'fetch(' not in page
    p['wall_s']=99.;(folder/'e3_10_metered_model.json').write_text(json.dumps(p))
    with pytest.raises(ValueError):load_integration(tmp_path)
