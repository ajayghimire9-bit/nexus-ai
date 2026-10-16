"""Bounded visited-state pairing, clocks, strict schemas and equal weighting."""
import copy
import itertools
import json
from pathlib import Path
import numpy as np
import pytest
import torch
from nexus.world import visited_commitment as m
from nexus.world.long_continuation import split_rewards
from nexus.tasks.spec import make_task_env
from nexus.tasks.pendulum_family import pendulum_context_development
from nexus.world.receding_horizon import true_state,_walk_wrappers
from test_receding_horizon import _Model
from test_commitment_value import master_capture


def test_balanced_prespecified_visitor_not_chosen_by_outcome():
    assignments=[m.visitor_student(d,t) for d,t in itertools.product(range(10),range(3))]
    assert [assignments.count(s) for s in range(5)]==[6]*5


def test_exact_budgets_and_fresh_seed_sets():
    cfg=m.load_config();counts=m.budget(cfg)
    assert sum(v for k,v in counts.items() if k!='model_states')==75960
    assert counts['model_states']==14883840+3000*256+60*256
    bad={**cfg,'candidate_base':2400000}
    with pytest.raises(ValueError):m.check_seeds(bad)


def test_collection_replay_context_and_phase_restoration():
    model=_Model();model.z=torch.ones(8)
    before=model.z.clone();env=make_task_env(pendulum_context_development()[0])
    try:
        env.reset(seed=9709000);live=m.collect(env,model,[9709100,9709101])
        assert torch.equal(model.z,before) and len(live)==2
        state=true_state(env);seq=m.prior.candidate_sequences(9709200)[0]
        a=m.prefix(env,state,seq);b=m.prefix(env,state,seq)
        assert a==b
        assert [w._elapsed_steps for w in _walk_wrappers(env) if '_elapsed_steps' in vars(w)]==[66]
        for forced in (0,2):
            with pytest.raises(ValueError,match='zero-context'):m.prior.continue_locked(env,model,state,[9709300],first_action=forced,phase=50)
    finally:env.close()


@pytest.fixture(scope='module')
def visited_capture(master_capture):
    old,_,parent,stage=master_capture;cfg=m.load_config();rows=[]
    cost=lambda a: -.004 if a!=1 else 0.
    def trace(seeds,phase,forced=None):
        actions=[];decisions=[]
        for k,s in enumerate(seeds):
            force=k==0 and forced is not None;a=forced if force else int(m.prior.candidate_sequences(s)[0,0]);actions.append(a)
            decisions.append(dict(seed=s,original_step=phase+k,selected_index=None if force else 0,predicted_score=None if force else 0.,terminated=False,truncated=False))
        rewards=[cost(a) for a in actions]
        return dict(actions=actions,rewards=rewards,decisions=decisions,endpoint=[0.,0.],endpoint_obs=[1.,0.,0.],**split_rewards(rewards,horizon=len(seeds)))
    for oldrow in old['cells']:
        r=copy.deepcopy(oldrow);d,t,v=r['decoder'],r['task'],r['state'];seq=m.prior.candidate_sequences(m.candidate_seed(cfg,d,t,v));live=[]
        for k,s in enumerate(m.collection_seeds(cfg,d,t)):
            a=int(m.prior.candidate_sequences(s)[0,0]);live.append(dict(obs=[1.,0.,0.],true_state=[0.,0.],action=a,reward=cost(a),next_obs=[1.,0.,0.],seed=s,step=k,selected_index=0,scores=[0.]*16,terminated=False,truncated=False))
        prefixes=[dict(actions=actions.tolist(),rewards=[cost(int(a)) for a in actions],next_obs=[[1.,0.,0.]]*16,terminated=[False]*16,truncated=[False]*16,endpoint=[0.,0.]) for actions in seq]
        seeds=m.future_seeds(cfg,d,t,v);first=[trace(seeds,50,a) for a in range(3)];tails=[trace(seeds[16:],66) for _ in range(16)]
        r.update(visitor='student' if v==0 else 'zero',visitor_model=str(m.visitor_student(d,t)) if v==0 else 'zero',reset_seed=m.reset_seed(cfg,d,t),collection=live,live_replay_matched=True,true_state=[0.,0.],obs=[1.,0.,0.],restore_exact=True,sequences=seq.tolist(),prefixes=prefixes,first_traces=first,block_tails=tails)
        r['metrics']=m.prior.contrasts(r['scores'],seq,[m.prior.total(tr['rewards'],64) for tr in first],[m.prior.total(pre['rewards'],16)+m.prior.total(tail['rewards'],48) for pre,tail in zip(prefixes,tails)],[[1.,0.,0.]]*3,[[1.,0.,0.]]*16);rows.append(r)
    p=dict(cells=rows,counts=m.budget(cfg),config_sha256=m.prior.sha(m.CONFIG),protocol_sha256=m.prior.sha(m.PROTOCOL),parents=cfg['parents'],source_dirty=False,wall_clock_s=1.,checkpoint_before=dict(verified=120,missing=0,mismatched=0),checkpoint_after=dict(verified=120,missing=0,mismatched=0),implementation_sha=cfg['starting_sha'],allocation_sha256='a'*64,input_verification=dict(checkpoints=dict(verified=120,missing=0,mismatched=0),model_context_groups=30,readouts=10,new_environment_steps=0))
    return p,cfg,parent,stage


def test_complete_synthetic_capture_and_equal_visitor_weight(visited_capture):
    p,cfg,parent,stage=visited_capture;result=m.validate(p,cfg,parent,stage)
    assert result['comparisons']['interaction']['interval']['n']==10
    rows=copy.deepcopy(p['cells'])
    for r in rows:
        for metrics in r['metrics'].values():metrics.update(gain1=0.,gain16=100. if r['state']==0 else -20.,interaction=100. if r['state']==0 else -20.)
    summary=m.summarize(rows,cfg)
    assert summary['comparisons']['interaction']['interval']['mean']==40.
    assert summary['per_visitor']['student']['interaction']['interval']['mean']==100.
    assert summary['per_visitor']['zero']['interaction']['interval']['mean']==-20.


@pytest.mark.parametrize('damage',['decoder','task','visitor','context','first','tail','prefix','collection','live_reward','trace_reward','clock','rng','normalizer','replay','allocation_count','nonfinite'])
def test_raw_integrity_rejections(visited_capture,damage):
    original,cfg,parent,stage=visited_capture;p=copy.deepcopy(original);r=p['cells'][0]
    if damage=='decoder':p['cells']=[x for x in p['cells'] if x['decoder']!=9]
    elif damage=='task':p['cells']=[x for x in p['cells'] if x['task']!=2]
    elif damage=='visitor':p['cells']=[x for x in p['cells'] if x['state']!=1]
    elif damage=='context':del r['scores']['4']
    elif damage=='first':r['first_traces'].pop()
    elif damage=='tail':r['block_tails'].pop()
    elif damage=='prefix':r['prefixes'].pop()
    elif damage=='collection':r['collection'].pop()
    elif damage=='live_reward':r['collection'][0]['reward']+=1
    elif damage=='trace_reward':r['first_traces'][0]['rewards'][0]+=1
    elif damage=='clock':r['first_traces'][0]['decisions'][0]['original_step']=0
    elif damage=='rng':r['sequences'][0][0]=(r['sequences'][0][0]+1)%3
    elif damage=='normalizer':r['after']['zero'][0]='b'*64
    elif damage=='replay':r['live_replay_matched']=False
    elif damage=='allocation_count':p['counts']['collection']-=1
    else:r['scores']['zero']['base'][0]=float('nan')
    with pytest.raises((ValueError,KeyError,RuntimeError)):m.validate(p,cfg,parent,stage)


def test_no_execution_without_saved_allocation(monkeypatch,tmp_path):
    monkeypatch.setattr(m,'ALLOCATION',tmp_path/'missing.json')
    monkeypatch.setattr(m,'OUTPUT',tmp_path/'forbidden.json')
    with pytest.raises((FileNotFoundError,PermissionError)):m.execute()
    assert not m.OUTPUT.exists()


@pytest.mark.parametrize('key',['config_sha256','protocol_sha256','time_cap_s','env_cap','runs'])
def test_saved_allocation_must_match_locked_scope(monkeypatch,tmp_path,key):
    record=json.loads(m.ALLOCATION.read_text());record[key]='wrong'
    path=tmp_path/'stale.json';path.write_text(json.dumps(record));monkeypatch.setattr(m,'ALLOCATION',path)
    with pytest.raises(PermissionError):m.require_allocation(m.load_config())
