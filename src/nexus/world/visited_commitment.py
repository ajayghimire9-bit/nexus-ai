"""Phase-50 replication of the frozen correction-by-commitment interaction."""
from __future__ import annotations
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import time

import numpy as np
import yaml
from nexus.world import commitment_value as prior
from nexus.world.long_continuation_execution import ExecutionMeter,restore_at_phase
from nexus.world.planning import mpc_for_model
from nexus.world.receding_horizon import true_state,_reward_ok
from nexus.world.terminal_value_execution import checked_id_grid,fingerprints,save

CONFIG=Path('configs/visited_commitment.yaml')
PROTOCOL=Path('docs/NEXUS_VISITED_COMMITMENT_PROTOCOL.md')
OUTPUT=Path('artifacts/visited_commitment.json')
ALLOCATION=Path('configs/visited_commitment_allocation.json')


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    if cfg['decoders']!=list(range(10)) or cfg['students']!=list(range(5)) or cfg['states_per_task']!=2 or cfg['phase']!=50 or cfg['horizon']!=16 or cfg['n_candidates']!=16 or cfg['total_steps']!=64 or cfg['practical_margin']!=1.0:
        raise ValueError('locked design changed')
    if cfg['tasks']!=prior.load_config()['tasks']:raise ValueError('development physics changed')
    for filename,digest in cfg['parents'].items():
        if prior.sha(filename)!=digest:raise ValueError('historical evidence/ledger drift')
    budget(cfg);check_seeds(cfg)
    return cfg


def visitor_student(d,t):return (d+t)%5
def reset_seed(cfg,d,t):return cfg['reset_base']+100*d+t
def collection_seeds(cfg,d,t):return list(range(cfg['collection_base']+10000*d+100*t,cfg['collection_base']+10000*d+100*t+50))
def candidate_seed(cfg,d,t,v):return cfg['candidate_base']+100*d+10*t+v
def future_seeds(cfg,d,t,v):return list(range(cfg['future_base']+10000*d+1000*t+100*v,cfg['future_base']+10000*d+1000*t+100*v+64))


def check_seeds(cfg):
    # Compare exact sets against every older diagnostic's registered generators.
    groups=[{reset_seed(cfg,d,t) for d,t in itertools.product(range(10),range(3))},
        {s for d,t in itertools.product(range(10),range(3)) for s in collection_seeds(cfg,d,t)},
        {candidate_seed(cfg,d,t,v) for d,t,v in itertools.product(range(10),range(3),range(2))},
        {s for d,t,v in itertools.product(range(10),range(3),range(2)) for s in future_seeds(cfg,d,t,v)}]
    if [len(g) for g in groups]!=[30,1500,60,3840]:raise ValueError('duplicate registered seeds')
    closed=json.loads(prior.OUTPUT.read_text());blocked=set()
    for row in closed['prefixes']:
        t,j=row['task'],row['state'];old=prior.load_config()
        blocked.update([prior.state_seed(old,t,j),prior.candidate_seed(old,t,j),*prior.future_seeds(old,t,j)])
    from nexus.world.prediction_control_gap import diagnostic_seed_groups,load_prediction_config
    from nexus.world.receding_horizon import horizon_seed_groups,load_horizon_config
    from nexus.world.return_phase import phase_seed_groups,load_phase_config
    from nexus.world.late_control_gap_design import design_seed_groups
    from nexus.world.long_continuation import proposed_seeds,load_config as long_config
    from nexus.world.policy_switch import load_config as switch_config,seeds
    from nexus.world.planning_value import load_config as value_config,seed_groups as value_groups
    from nexus.world.terminal_value import seed_groups,load_config as terminal_config
    from nexus.world.terminal_value_calibration import load_config as cal_config,tail_seeds
    a,b=diagnostic_seed_groups(load_prediction_config())
    for registry in (a,b,horizon_seed_groups(load_horizon_config()),phase_seed_groups(load_phase_config()),design_seed_groups(),proposed_seeds(long_config())):
        for values in registry.values():blocked.update(values)
    old=switch_config();blocked.update([old['env_seed'],old['planner_seed']])
    blocked.update(s for p in range(2) for slot in range(6) for s in seeds(old,p,slot))
    for values in value_groups(value_config())+seed_groups(terminal_config()):blocked.update(values)
    cal=cal_config();blocked.update(cal['state_base']+t for t in range(11));blocked.update(cal['candidate_base']+t for t in range(11));blocked.update(s for t in range(11) for s in tail_seeds(cal,t))
    for g in groups:
        if g & blocked or min(g)<2500000:raise ValueError('closed or overlapping seeds')
        blocked.update(g)


def budget(cfg):
    result=dict(collection=3000,prefix=15360,block_tail=46080,first_common=11520,model_states=15667200)
    if cfg['env_cap']!=75960 or cfg['model_cap']!=result['model_states'] or not 0<cfg['time_cap_s']<=600:raise ValueError('budget changed')
    return result


class Meter(ExecutionMeter):
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)};self.bucket='collection'
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('visited-state execution cap reached')


def require_allocation(cfg):
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=prior.sha(CONFIG),protocol_sha256=prior.sha(PROTOCOL),runs=1,time_cap_s=600,env_cap=75960,model_cap=15667200).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise PermissionError('stale/missing allocation')
    usage=json.loads(Path('artifacts/research_session_commitment_usage.json').read_text())
    if usage['remaining_session_allowance_s']<cfg['time_cap_s']:raise PermissionError('session budget exhausted')


def collect(env,model,seeds):
    planner=mpc_for_model(model,seed=seeds[0],enforce_time_budget=False);records=[]
    for k,seed in enumerate(seeds):
        obs=np.asarray(env.unwrapped._get_obs(),dtype=np.float32);state=true_state(env)
        planner.reset_episode(seed);action,info=planner.act(obs)
        if info['n_scored']!=16:raise ValueError('live candidate budget changed')
        nxt,reward,term,trunc,_=env.step(int(action));_reward_ok(obs,int(action),nxt,reward)
        if term or trunc:raise ValueError('short live trajectory')
        records.append(dict(obs=obs.tolist(),true_state=state.tolist(),action=int(action),reward=float(reward),next_obs=np.asarray(nxt,dtype=np.float32).tolist(),seed=seed,step=k,
            selected_index=int(np.argmax(info['candidate_scores'])),scores=np.asarray(info['candidate_scores']).tolist(),terminated=bool(term),truncated=bool(trunc)))
    last=records[-1];planner.reset_episode(last['seed']);action,info=planner.act(last['obs'])
    if action!=last['action'] or not np.allclose(info['candidate_scores'],last['scores'],rtol=0,atol=1e-5):raise ValueError('recorded live decision did not reproduce')
    return records


def prefix(env,state,actions):
    obs=restore_at_phase(env,state,50);rewards=[];observations=[]
    for a in actions:
        nxt,r,term,trunc,_=env.step(int(a));_reward_ok(obs,int(a),nxt,r)
        if term or trunc:raise ValueError('short candidate prefix')
        rewards.append(float(r));observations.append(np.asarray(nxt,dtype=np.float32).tolist());obs=nxt
    return dict(actions=np.asarray(actions).tolist(),rewards=rewards,next_obs=observations,terminated=[False]*16,truncated=[False]*16,endpoint=true_state(env).tolist())


def trace_sums(trace):
    for key,part in (('early',trace['rewards'][:16]),('late',trace['rewards'][16:]),('total',trace['rewards'])):
        value=trace.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or not math.isclose(value,math.fsum(part),rel_tol=0,abs_tol=1e-8):raise ValueError('reward summary mismatch')


def summarize(rows,cfg):
    main=prior.summarize(rows,cfg)
    # state index is visitor group, not independent sampling replication.
    for v in range(2):
        reduced=[]
        for r in rows:
            if r['state']==v:
                reduced.extend([{**r,'state':0},{**r,'state':1}])
        main.setdefault('per_visitor',{})['student' if v==0 else 'zero']=prior.summarize(reduced,cfg)['comparisons']
    return main


def validate(p,cfg,parent,stage,*,config_path=None,protocol_path=None):
    config_path=CONFIG if config_path is None else config_path
    protocol_path=PROTOCOL if protocol_path is None else protocol_path
    cells=checked_id_grid(p['cells'],('decoder','task','state'),set(itertools.product(cfg['decoders'],range(3),range(2))))
    for (d,t,v),row in cells.items():
        _,expected=prior.saved_contexts(parent,stage,d,t+8)
        if row['before']!=expected or row['after']!=expected:raise ValueError('frozen weights/context changed')
        if row['visitor']!=('student' if v==0 else 'zero') or row['visitor_model']!=(str(visitor_student(d,t)) if v==0 else 'zero') or row['reset_seed']!=reset_seed(cfg,d,t):raise ValueError('visitor assignment changed')
        live=row['collection']
        if len(live)!=50 or row['live_replay_matched'] is not True:raise ValueError('missing live trajectory/replay')
        previous=None
        for k,r in enumerate(live):
            prior.validate_endpoint(r['true_state'],r['obs'])
            if previous is not None and r['obs']!=previous:raise ValueError('discontinuous live trajectory')
            previous=r['next_obs'];scores=prior.finite_array(r['scores'],(16,));index=int(np.argmax(scores))
            if r['step']!=k or r['seed']!=collection_seeds(cfg,d,t)[k] or type(r['action']) is not int or r['selected_index']!=index or r['action']!=int(prior.candidate_sequences(r['seed'])[index,0]) or r['terminated'] is not False or r['truncated'] is not False:raise ValueError('live RNG/action/episode mismatch')
            _reward_ok(np.asarray(r['obs']),r['action'],np.asarray(r['next_obs']),r['reward'])
        prior.validate_endpoint(row['true_state'],row['obs'])
        if row['obs']!=previous or row['restore_exact'] is not True:raise ValueError('visited state not collection endpoint')
        seq=prior.candidate_sequences(candidate_seed(cfg,d,t,v))
        if not np.issubdtype(np.asarray(row['sequences']).dtype,np.integer) or not np.array_equal(row['sequences'],seq) or len(row['prefixes'])!=16 or len(row['first_traces'])!=3 or len(row['block_tails'])!=16:raise ValueError('candidate grid mismatch')
        for actions,pre in zip(seq,row['prefixes']):
            if pre['actions']!=actions.tolist() or len(pre['terminated'])!=16 or len(pre['truncated'])!=16 or any(flag is not False for flag in pre['terminated']+pre['truncated']):raise ValueError('prefix changed')
            prior.finite_array(pre['rewards'],(16,));prior.finite_array(pre['next_obs'],(16,3));obs=row['obs']
            for a,nxt,r in zip(actions,pre['next_obs'],pre['rewards']):_reward_ok(np.asarray(obs),int(a),np.asarray(nxt),r);obs=nxt
            prior.validate_endpoint(pre['endpoint'],obs)
        seeds=future_seeds(cfg,d,t,v)
        for a,tr in enumerate(row['first_traces']):prior.validate_trace(tr,seeds,50,a);trace_sums(tr)
        for tr in row['block_tails']:prior.validate_trace(tr,seeds[16:],66);trace_sums(tr)
        readout=prior.TerminalReadout(**stage['readouts'][str(d)]['state'])
        if row['readout_sha256']!=readout.digest() or set(row['scores'])!=set(prior.NAMES):raise ValueError('readout/context changed')
        for name,s in row['scores'].items():
            base=prior.finite_array(s['base'],(16,));value=prior.finite_array(s['corrected'],(16,));alive=prior.finite_array(s['survival'],(16,));terminal=prior.finite_array(s['terminal'],(16,));x=prior.finite_array(s['inputs'],(16,11))
            z=np.asarray(x[0,3:],dtype=np.float32)
            if hashlib.sha256(z.tobytes()).hexdigest()!=expected[name][1] or not np.all(x[:,3:]==x[0,3:]) or not np.array_equal(x[:,:3],prior.finite_array(s['endpoint'],(16,3))):raise ValueError('score context drift')
            if np.any((alive<0)|(alive>1)) or not np.allclose(terminal,readout.predict(x),rtol=0,atol=1e-8) or not np.allclose(value,base+alive*terminal,rtol=0,atol=1e-8):raise ValueError('score arithmetic changed')
        fr=[prior.total(tr['rewards'],64) for tr in row['first_traces']]
        br=[prior.total(pre['rewards'],16)+prior.total(tail['rewards'],48) for pre,tail in zip(row['prefixes'],row['block_tails'])]
        rebuilt=prior.contrasts(row['scores'],seq,fr,br,[tr['endpoint_obs'] for tr in row['first_traces']],[tr['endpoint_obs'] for tr in row['block_tails']])
        if row['metrics']!=rebuilt:raise ValueError('raw metrics mismatch')
    if p['counts']!=budget(cfg) or p['config_sha256']!=prior.sha(config_path) or p['protocol_sha256']!=prior.sha(protocol_path) or p['parents']!=cfg['parents'] or p['source_dirty'] is not False:raise ValueError('accounting/provenance mismatch')
    for key in ('checkpoint_before','checkpoint_after'):
        if p[key]!=dict(verified=120,missing=0,mismatched=0):raise ValueError('missing binary audit')
    if p.get('input_verification')!=dict(checkpoints=dict(verified=120,missing=0,mismatched=0),model_context_groups=30,readouts=10,new_environment_steps=0):raise ValueError('missing before-collection verification')
    for key,length in (('implementation_sha',40),('allocation_sha256',64)):
        digest=p.get(key)
        if not isinstance(digest,str) or len(digest)!=length or any(c not in '0123456789abcdef' for c in digest):raise ValueError('missing execution/allocation provenance')
    if not 0<p['wall_clock_s']<=cfg['time_cap_s']:raise ValueError('time exceeded')
    return summarize(p['cells'],cfg)


def execute(*,configuration=None,config_path=None,protocol_path=None,output=None,allocation_path=None,preflight=None,finalize=None,prior_execution_s=0.,execution_metadata=None):
    config_path=CONFIG if config_path is None else config_path
    protocol_path=PROTOCOL if protocol_path is None else protocol_path
    output=OUTPUT if output is None else output
    allocation_path=ALLOCATION if allocation_path is None else allocation_path
    if configuration is None:
        cfg=load_config();require_allocation(cfg)
    else:
        cfg=configuration
        if preflight is None:raise PermissionError('custom protocol requires its own locked preflight')
        preflight(cfg)
    if not 0<=prior_execution_s<cfg['time_cap_s']:raise ValueError('invalid carried execution time')
    if output.exists():raise RuntimeError('refusing repeat/overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol and implementation first')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    started=time.perf_counter();meter=Meter({**cfg,'time_cap_s':cfg['time_cap_s']-prior_execution_s});parent,stage=prior.parent_evidence()
    p=dict(complete=False,label='incomplete',cells=[],counts=meter.counts,implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_dirty=False,config_sha256=prior.sha(config_path),protocol_sha256=prior.sha(protocol_path),allocation_sha256=prior.sha(allocation_path),parents=cfg['parents'])
    if set(execution_metadata or {}) & set(p):raise ValueError('custom metadata cannot replace standard provenance')
    p.update(execution_metadata or {})
    try:
        import sys,torch,gymnasium
        from nexus.tasks.spec import make_task_env
        from nexus.tasks.pendulum_family import pendulum_context_development
        from nexus.world.control_replication import load_replication_config,_confirmation_artifact
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        p['dependencies']=dict(python=sys.version,numpy=np.__version__,torch=torch.__version__,gymnasium=gymnasium.__version__)
        p['input_verification']=prior.verify_inputs();p['checkpoint_before']=p['input_verification']['checkpoints']
        rep=load_replication_config();confirmation=_confirmation_artifact(rep)
        for d in cfg['decoders']:
            readout=prior.TerminalReadout(**stage['readouts'][str(d)]['state'])
            for t,spec in enumerate(pendulum_context_development()):
                models=prior.load_models(d,t+8,rep,confirmation,parent,stage)
                for m in models.values():meter.instrument_model(m)
                for v in range(2):
                    before=fingerprints(models);env=make_task_env(spec);env.reset(seed=reset_seed(cfg,d,t));meter.instrument_env(env)
                    try:
                        visitor=str(visitor_student(d,t)) if v==0 else 'zero';meter.bucket='collection';live=collect(env,models[visitor],collection_seeds(cfg,d,t))
                        state=true_state(env);obs=np.asarray(env.unwrapped._get_obs(),dtype=np.float32)
                        if not np.array_equal(restore_at_phase(env,state,50),obs):raise ValueError('exact restoration failed')
                        seq=prior.candidate_sequences(candidate_seed(cfg,d,t,v));scores={name:prior.score_conditions(m,obs,seq,readout) for name,m in models.items()}
                        meter.bucket='prefix';prefixes=[prefix(env,state,a) for a in seq];seeds=future_seeds(cfg,d,t,v)
                        meter.bucket='first_common';first=[prior.continue_locked(env,models['zero'],state,seeds,first_action=a,phase=50) for a in range(3)]
                        meter.bucket='block_tail';tails=[prior.continue_locked(env,models['zero'],pre['endpoint'],seeds[16:],phase=66) for pre in prefixes]
                    finally:env.close()
                    after=fingerprints(models)
                    if before!=after:raise RuntimeError('frozen model/context drift')
                    fr=[prior.total(tr['rewards'],64) for tr in first];br=[prior.total(pre['rewards'],16)+prior.total(tail['rewards'],48) for pre,tail in zip(prefixes,tails)]
                    metrics=prior.contrasts(scores,seq,fr,br,[tr['endpoint_obs'] for tr in first],[tr['endpoint_obs'] for tr in tails])
                    p['cells'].append(dict(decoder=d,task=t,state=v,visitor='student' if v==0 else 'zero',visitor_model=visitor,reset_seed=reset_seed(cfg,d,t),collection=live,live_replay_matched=True,true_state=state.tolist(),obs=obs.tolist(),restore_exact=True,sequences=seq.tolist(),prefixes=prefixes,first_traces=first,block_tails=tails,scores=scores,before=before,after=after,readout_sha256=readout.digest(),metrics=metrics))
                p['wall_clock_s']=prior_execution_s+time.perf_counter()-started;save(output,p)
            print(f'visited decoder={d} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['wall_clock_s']=prior_execution_s+time.perf_counter()-started;p.update(validate(p,cfg,parent,stage,config_path=config_path,protocol_path=protocol_path))
        if finalize is not None:p.update(finalize(p,cfg,parent,stage))
        meter.check();p['complete']=True
    except Exception as exc:p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
    p['evaluation_wall_s']=time.perf_counter()-started;p['wall_clock_s']=prior_execution_s+p['evaluation_wall_s'];save(output,p);return p
