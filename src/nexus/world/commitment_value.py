"""Locked same-state value-correction by commitment-length diagnostic."""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import time

import numpy as np
import yaml

from nexus.tasks.pendulum_family import pendulum_context_development,pendulum_physics_key
from nexus.world.planning_value import sha,finite_array
from nexus.world.terminal_value import NAMES,TerminalReadout,score_conditions
from nexus.world.terminal_value_execution import checked_id_grid,fingerprints,save
from nexus.world.terminal_value_calibration import parent_evidence,load_models,saved_contexts
from nexus.world.long_continuation import continuation_trace,paired_interval
from nexus.world.long_continuation_execution import ExecutionMeter
from nexus.world.receding_horizon import true_state,restore_state,_reward_ok,_context_snapshot
from nexus.world.prediction_control_gap import candidate_sequences

CONFIG=Path('configs/commitment_value.yaml')
PROTOCOL=Path('docs/NEXUS_COMMITMENT_VALUE_PROTOCOL.md')
OUTPUT=Path('artifacts/commitment_value.json')
APPROVAL=Path('configs/commitment_value_approval.json')
LOCK='ebd9b2b5ebf4eff5d7c2248176da89a343b86898e7302bd2d13d7b7726e1f16c'
METRICS=('first_base','first_value','block_base','block_value','gain1','gain16','interaction',
    'first_regret_base','first_regret_value','block_regret_base','block_regret_value',
    'sequence_disagreement','action_disagreement','end_obs_distance_base','end_obs_distance_value')


def load_config():
    if sha(CONFIG)!=LOCK or LOCK not in PROTOCOL.read_text():raise ValueError('locked configuration/protocol drift')
    cfg=yaml.safe_load(CONFIG.read_text())
    if cfg['tasks']!=[dict(task_id=s.task_id,physics=list(pendulum_physics_key(s))) for s in pendulum_context_development()]:raise ValueError('registered development physics changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('frozen input/proposal changed')
    return cfg


def state_seed(cfg,t,j):return cfg['state_base']+10*t+j

def candidate_seed(cfg,t,j):return cfg['candidate_base']+10*t+j

def future_seeds(cfg,t,j):return list(range(cfg['continuation_base']+256*t+128*j,cfg['continuation_base']+256*t+128*j+64))


def check_seeds(cfg):
    from nexus.world.prediction_control_gap import diagnostic_seed_groups,load_prediction_config
    from nexus.world.receding_horizon import horizon_seed_groups,load_horizon_config
    from nexus.world.return_phase import phase_seed_groups,load_phase_config
    from nexus.world.late_control_gap_design import design_seed_groups
    from nexus.world.long_continuation import proposed_seeds,load_config as long_config
    from nexus.world.policy_switch import load_config as switch_config,seeds
    from nexus.world.planning_value import load_config as value_config,seed_groups as value_groups
    from nexus.world.terminal_value import seed_groups,load_config as terminal_config
    from nexus.world.terminal_value_calibration import load_config as cal_config,tail_seeds
    a,b=diagnostic_seed_groups(load_prediction_config());blocked=set()
    for group in (a,b,horizon_seed_groups(load_horizon_config()),phase_seed_groups(load_phase_config()),design_seed_groups(),proposed_seeds(long_config())):
        for values in group.values():blocked.update(values)
    prior=switch_config();blocked.update([prior['env_seed'],prior['planner_seed']])
    blocked.update(x for p in range(2) for slot in range(6) for x in seeds(prior,p,slot))
    for group in value_groups(value_config())+seed_groups(terminal_config()):blocked.update(group)
    cal=cal_config();blocked.update(cal['state_base']+t for t in range(11));blocked.update(cal['candidate_base']+t for t in range(11))
    blocked.update(s for t in range(11) for s in tail_seeds(cal,t))
    groups=[{state_seed(cfg,t,j) for t,j in itertools.product(range(3),range(2))},
        {candidate_seed(cfg,t,j) for t,j in itertools.product(range(3),range(2))},
        {s for t,j in itertools.product(range(3),range(2)) for s in future_seeds(cfg,t,j)}]
    if [len(g) for g in groups]!=[6,6,384]:raise ValueError('duplicated planned RNG seeds')
    for group in groups:
        if group & blocked:raise ValueError('closed or overlapping episode/RNG seeds')
        blocked.update(group)


def budget(cfg):
    d=len(cfg['decoders']);states=len(cfg['tasks'])*cfg['states_per_task'];contexts=len(cfg['students'])+1
    counts=dict(prefix=states*16*16,block_tail=d*states*16*48,first_common=d*states*3*64,
        model_states=d*states*16*48*256+d*states*3*63*256+d*states*contexts*512)
    if sum(v for k,v in counts.items() if k!='model_states')!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:raise ValueError('resource allocation mismatch')
    return counts


def total(rewards,n):return math.fsum(finite_array(rewards,(n,)).tolist())


def execute_prefix(env,state,actions):
    seq=np.asarray(actions)
    if seq.shape!=(16,) or not np.issubdtype(seq.dtype,np.integer) or np.any((seq<0)|(seq>2)):raise ValueError('sixteen discrete actions required')
    obs=restore_state(env,state);rewards=[];observations=[];terms=[];truncs=[]
    for a in seq:
        nxt,reward,term,trunc,_=env.step(int(a));_reward_ok(obs,int(a),nxt,float(reward))
        if term or trunc:raise ValueError('unexpected terminated/truncated prefix')
        rewards.append(float(reward));observations.append(np.asarray(nxt,dtype=np.float32).tolist());terms.append(bool(term));truncs.append(bool(trunc));obs=nxt
    return dict(actions=seq.tolist(),rewards=rewards,next_obs=observations,terminated=terms,truncated=truncs,endpoint=true_state(env).tolist())


def continue_locked(env,model,state,seeds,*,first_action=None,phase=0):
    if bool((_context_snapshot(model)!=0).any()):raise ValueError('both commitment arms require exact zero-context continuation')
    trace=continuation_trace(env,model,state,seeds,first_action=first_action,horizon=len(seeds),original_phase=phase)
    trace['endpoint']=true_state(env).tolist();trace['endpoint_obs']=np.asarray(env.unwrapped._get_obs(),dtype=np.float32).tolist()
    return trace


def contrasts(scores,sequences,first_returns,block_returns,first_obs,block_obs):
    first=finite_array(first_returns,(3,));block=finite_array(block_returns,(16,))
    fo=finite_array(first_obs,(3,3));bo=finite_array(block_obs,(16,3));seq=np.asarray(sequences)
    if seq.shape!=(16,16) or not np.issubdtype(seq.dtype,np.integer) or np.any((seq<0)|(seq>2)):raise ValueError('invalid shared candidates')
    if set(scores)!=set(NAMES):raise ValueError('missing scoring context')
    result={}
    for name,s in scores.items():
        idx={k:int(np.argmax(finite_array(s[k],(16,)))) for k in ('base','corrected')}
        a={k:int(seq[i,0]) for k,i in idx.items()}
        m=dict(first_base=float(first[a['base']]),first_value=float(first[a['corrected']]),block_base=float(block[idx['base']]),block_value=float(block[idx['corrected']]))
        m.update(gain1=m['first_value']-m['first_base'],gain16=m['block_value']-m['block_base'])
        m['interaction']=m['gain16']-m['gain1']
        m.update(first_regret_base=float(max(first))-m['first_base'],first_regret_value=float(max(first))-m['first_value'],
            block_regret_base=float(max(block))-m['block_base'],block_regret_value=float(max(block))-m['block_value'],
            sequence_disagreement=float(idx['base']!=idx['corrected']),action_disagreement=float(a['base']!=a['corrected']),
            end_obs_distance_base=float(np.linalg.norm(bo[idx['base']]-fo[a['base']])),end_obs_distance_value=float(np.linalg.norm(bo[idx['corrected']]-fo[a['corrected']])))
        result[name]=m
    return result


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task','state'),set(itertools.product(cfg['decoders'],range(3),range(cfg['states_per_task']))))
    for row in cells.values():
        if set(row['metrics'])!=set(NAMES):raise ValueError('missing context metrics')
        for m in row['metrics'].values():
            if set(m)!=set(METRICS):raise ValueError('missing required metric')
            finite_array([m[k] for k in METRICS],(len(METRICS),))
            if not math.isclose(m['interaction'],m['gain16']-m['gain1'],abs_tol=1e-8):raise ValueError('interaction identity mismatch')
    def aggregate(tasks,students):
        result={}
        for metric in METRICS:
            values=[statistics.mean(cells[d,t,j]['metrics'][s][metric] for t,j,s in itertools.product(tasks,range(cfg['states_per_task']),students)) for d in cfg['decoders']]
            result[metric]=dict(per_decoder=values,interval=paired_interval(values))
        return result
    primary=aggregate(range(3),[str(s) for s in cfg['students']]);ci=primary['interaction']['interval'];full=primary['gain16']['interval']
    label='commitment_interaction_not_established'
    if ci['mean']>=cfg['practical_margin'] and ci['lo']>0:
        label='commitment_sensitive_gain' if full['lo']>0 else 'relative_commitment_sensitivity_without_established_gain'
    return dict(label=label,comparisons=primary,zero_context=aggregate(range(3),['zero']),per_task={str(t):aggregate([t],[str(s) for s in cfg['students']]) for t in range(3)})


def validate_endpoint(state,obs):
    state=finite_array(state,(2,));obs=finite_array(obs,(3,))
    if not np.allclose(obs,[np.cos(state[0]),np.sin(state[0]),state[1]],atol=1e-6,rtol=0):raise ValueError('simulator state/observation mismatch')


def validate_trace(trace,seeds,phase,forced=None):
    n=len(seeds);finite_array(trace['rewards'],(n,));validate_endpoint(trace['endpoint'],trace['endpoint_obs'])
    if len(trace['actions'])!=n or len(trace['decisions'])!=n:raise ValueError('incomplete continuation')
    for k,(a,dec) in enumerate(zip(trace['actions'],trace['decisions'])):
        if type(a) is not int or a not in (0,1,2) or type(dec['seed']) is not int or type(dec['original_step']) is not int or dec['seed']!=seeds[k] or dec['original_step']!=phase+k or dec['terminated'] is not False or dec['truncated'] is not False:raise ValueError('invalid reward/action/seed/clock trace')
        idx=dec['selected_index']
        if k==0 and forced is not None:
            if a!=forced or idx is not None or dec['predicted_score'] is not None:raise ValueError('wrong forced first action')
        else:
            if type(idx) is not int or not 0<=idx<16 or a!=int(candidate_sequences(seeds[k])[idx,0]):raise ValueError('future candidate RNG/action mismatch')
            finite_array([dec['predicted_score']],(1,))


def validate(p,cfg,parent,stage):
    prefixes=checked_id_grid(p['prefixes'],('task','state'),set(itertools.product(range(3),range(cfg['states_per_task']))))
    for (t,j),r in prefixes.items():
        if not np.issubdtype(np.asarray(r['sequences']).dtype,np.integer) or r['reset_seed']!=state_seed(cfg,t,j) or r['restore_exact'] is not True or not np.array_equal(r['sequences'],candidate_sequences(candidate_seed(cfg,t,j))):raise ValueError('state/candidate restoration or pairing failure')
        validate_endpoint(r['true_state'],r['obs'])
        if len(r['rollouts'])!=16:raise ValueError('missing cached prefix')
        for i,tr in enumerate(r['rollouts']):
            finite_array(tr['rewards'],(16,));finite_array(tr['next_obs'],(16,3))
            if tr['actions']!=r['sequences'][i] or any(type(a) is not int for a in tr['actions']) or len(tr['terminated'])!=16 or len(tr['truncated'])!=16 or any(flag is not False for flag in tr['terminated']+tr['truncated']):raise ValueError('prefix actions/termination changed')
            validate_endpoint(tr['endpoint'],tr['next_obs'][-1])
            obs=r['obs']
            for a,nxt,reward in zip(tr['actions'],tr['next_obs'],tr['rewards']):_reward_ok(np.array(obs),a,np.array(nxt),reward);obs=nxt
    cells=checked_id_grid(p['cells'],('decoder','task','state'),set(itertools.product(cfg['decoders'],range(3),range(cfg['states_per_task']))))
    for (d,t,j),row in cells.items():
        prefix=prefixes[t,j];_,expected=saved_contexts(parent,stage,d,t+8)
        if row['before']!=expected or row['after']!=expected:raise ValueError('frozen model/normalizer/context changed')
        if len(row['first_traces'])!=3 or len(row['block_tails'])!=16 or set(row['scores'])!=set(NAMES):raise ValueError('missing arm/candidate/context')
        seeds=future_seeds(cfg,t,j)
        for a,tr in enumerate(row['first_traces']):validate_trace(tr,seeds,0,a)
        for tr in row['block_tails']:validate_trace(tr,seeds[16:],16)
        readout=TerminalReadout(**stage['readouts'][str(d)]['state'])
        if row['readout_sha256']!=readout.digest():raise ValueError('readout changed')
        for name,s in row['scores'].items():
            base=finite_array(s['base'],(16,));corrected=finite_array(s['corrected'],(16,));alive=finite_array(s['survival'],(16,));values=finite_array(s['terminal'],(16,))
            x=finite_array(s['inputs'],(16,11));end=finite_array(s['endpoint'],(16,3))
            import hashlib
            z=np.asarray(x[0,3:],dtype=np.float32)
            if not np.all(x[:,3:]==x[0,3:]) or hashlib.sha256(z.tobytes()).hexdigest()!=expected[name][1] or not np.array_equal(x[:,:3],end):raise ValueError('score context or endpoint changed')
            if np.any((alive<0)|(alive>1)) or not np.allclose(values,readout.predict(x),atol=1e-8,rtol=0) or not np.allclose(corrected,base+alive*values,atol=1e-8,rtol=0):raise ValueError('frozen scoring arithmetic changed')
        first=[total(tr['rewards'],64) for tr in row['first_traces']]
        blocks=[total(pref['rewards'],16)+total(tail['rewards'],48) for pref,tail in zip(prefix['rollouts'],row['block_tails'])]
        rebuilt=contrasts(row['scores'],prefix['sequences'],first,blocks,[tr['endpoint_obs'] for tr in row['first_traces']],[tr['endpoint_obs'] for tr in row['block_tails']])
        if set(row['metrics'])!=set(rebuilt):raise ValueError('metric schema changed')
        for name in rebuilt:
            if set(row['metrics'][name])!=set(METRICS):raise ValueError('missing saved metric')
            values=finite_array([row['metrics'][name][k] for k in METRICS],(len(METRICS),))
            if not np.allclose(values,[rebuilt[name][k] for k in METRICS],atol=1e-8,rtol=0):raise ValueError('raw/metric mismatch')
    if p['config_sha256']!=sha(CONFIG) or p['protocol_sha256']!=sha(PROTOCOL) or p['parents']!=cfg['parents']:raise ValueError('provenance changed')
    if p['counts']!=budget(cfg):raise ValueError('missing/duplicated resource counts')
    if p.get('input_verification')!=dict(checkpoints=dict(verified=120,missing=0,mismatched=0),model_context_groups=30,readouts=10,new_environment_steps=0):raise ValueError('missing before-collection model reconstruction audit')
    if p.get('source_dirty') is not False or not isinstance(p.get('implementation_sha'),str) or len(p['implementation_sha'])!=40 or any(c not in '0123456789abcdef' for c in p['implementation_sha']):raise ValueError('missing clean implementation provenance')
    for k in ('checkpoint_before','checkpoint_after'):
        if p[k]!=dict(verified=120,missing=0,mismatched=0):raise ValueError('missing checkpoint audit')
    if not isinstance(p.get('approval_sha256'),str) or len(p['approval_sha256'])!=64 or any(c not in '0123456789abcdef' for c in p['approval_sha256']):raise ValueError('missing approval-record digest')
    finite_array([p['wall_clock_s']],(1,))
    if not 0<=p['wall_clock_s']<=cfg['time_cap_s']:raise ValueError('time cap exceeded')
    return summarize(p['cells'],cfg)


class CommitmentMeter(ExecutionMeter):
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)};self.bucket='prefix'
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('900-second commitment cap reached')


def require_approval(approved_hash,cfg):
    if approved_hash!=LOCK or not APPROVAL.is_file():raise PermissionError('new exact-budget commitment experiment approval required')
    record=json.loads(APPROVAL.read_text());required=dict(kind='human_approved_bounded_local_experiment',config_sha256=LOCK,time_cap_s=cfg['time_cap_s'],env_cap=cfg['env_cap'],model_cap=cfg['model_cap'],runs=1,further_experiments_authorized=False)
    if any(type(record.get(k)) is not type(v) or record[k]!=v for k,v in required.items()):raise PermissionError('stale or wrong-scope approval')


def prepare():
    cfg=load_config();check_seeds(cfg);budget(cfg);parent_evidence()
    return dict(status='awaiting_budget_approval',config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),counts=budget(cfg),new_environment_steps=0,
        estimated_minutes=[4,6],time_cap_s=cfg['time_cap_s'],new_support_steps=0,network_updates=0,readout_fits=0,
        implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()))


def verify_inputs():
    cfg=load_config();parent,stage=parent_evidence()
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.control_replication import load_replication_config,_confirmation_artifact
    checks=verify_checkpoint_integrity();rep=load_replication_config();confirmation=_confirmation_artifact(rep)
    for d,t in itertools.product(cfg['decoders'],range(3)):load_models(d,t+8,rep,confirmation,parent,stage)
    return dict(checkpoints=checks,model_context_groups=30,readouts=10,new_environment_steps=0)


def execute(approved_hash=None):
    cfg=load_config();require_approval(approved_hash,cfg)
    if OUTPUT.exists():raise RuntimeError('refusing repeat/overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean implementation and approval before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    check_seeds(cfg);budget(cfg);parent,stage=parent_evidence()
    started=time.perf_counter();meter=CommitmentMeter(cfg)
    p=dict(complete=False,label='incomplete',implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_dirty=False,
        config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),approval_sha256=sha(APPROVAL),parents=cfg['parents'],prefixes=[],cells=[],counts=meter.counts)
    try:
        import sys
        import torch
        import gymnasium
        from nexus.tasks.spec import make_task_env
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        from nexus.world.control_replication import load_replication_config,_confirmation_artifact
        p['dependencies']=dict(python=sys.version,numpy=np.__version__,torch=torch.__version__,gymnasium=gymnasium.__version__)
        p['input_verification']=verify_inputs();p['checkpoint_before']=p['input_verification']['checkpoints']
        rep=load_replication_config();confirmation=_confirmation_artifact(rep);specs=pendulum_context_development()
        for t,spec in enumerate(specs):
            for j in range(cfg['states_per_task']):
                meter.check();env=make_task_env(spec)
                try:
                    obs,_=env.reset(seed=state_seed(cfg,t,j));state=true_state(env);seq=candidate_sequences(candidate_seed(cfg,t,j))
                    if not np.array_equal(restore_state(env,state),obs):raise RuntimeError('initial simulator restoration failed')
                    meter.instrument_env(env);meter.bucket='prefix'
                    rollouts=[execute_prefix(env,state,actions) for actions in seq]
                    p['prefixes'].append(dict(task=t,state=j,reset_seed=state_seed(cfg,t,j),true_state=state.tolist(),obs=obs.tolist(),sequences=seq.tolist(),restore_exact=True,rollouts=rollouts))
                finally:env.close()
                p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p)
        prefixes={(r['task'],r['state']):r for r in p['prefixes']}
        for d in cfg['decoders']:
            readout=TerminalReadout(**stage['readouts'][str(d)]['state']);readout_hash=readout.digest()
            for t,spec in enumerate(specs):
                models=load_models(d,t+8,rep,confirmation,parent,stage)
                for m in models.values():meter.instrument_model(m)
                for j in range(cfg['states_per_task']):
                    prefix=prefixes[t,j];seq=np.asarray(prefix['sequences'],dtype=np.int64);before=fingerprints(models)
                    scores={name:score_conditions(m,prefix['obs'],seq,readout) for name,m in models.items()}
                    seeds=future_seeds(cfg,t,j);env=make_task_env(spec)
                    try:
                        env.reset(seed=state_seed(cfg,t,j));meter.instrument_env(env);meter.bucket='first_common'
                        first=[continue_locked(env,models['zero'],prefix['true_state'],seeds,first_action=a) for a in range(3)]
                        meter.bucket='block_tail'
                        tails=[continue_locked(env,models['zero'],r['endpoint'],seeds[16:],phase=16) for r in prefix['rollouts']]
                    finally:env.close()
                    after=fingerprints(models)
                    if before!=after or readout_hash!=readout.digest():raise RuntimeError('frozen model/context/normalizer/readout changed')
                    fr=[total(tr['rewards'],64) for tr in first]
                    br=[total(pre['rewards'],16)+total(tail['rewards'],48) for pre,tail in zip(prefix['rollouts'],tails)]
                    metrics=contrasts(scores,seq,fr,br,[r['endpoint_obs'] for r in first],[r['endpoint_obs'] for r in tails])
                    p['cells'].append(dict(decoder=d,task=t,state=j,before=before,after=after,readout_sha256=readout_hash,scores=scores,first_traces=first,block_tails=tails,metrics=metrics))
            p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p)
            print(f'commitment decoder={d} seconds={p["wall_clock_s"]:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['wall_clock_s']=time.perf_counter()-started
        p.update(validate(p,cfg,parent,stage));meter.check();p['complete']=True
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p)
    return p
