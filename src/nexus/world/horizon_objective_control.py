"""Nested H=8 scoring versus archived H=16 receding.

Collection requires a bound one-run allocation. Does not rewrite the
exhausted 3600-second ledger or the late-episode capture.
"""
from __future__ import annotations
import itertools
import json
import math
import subprocess
import time
from pathlib import Path
import numpy as np
import yaml
from nexus.world import late_episode_decision_trajectory as late
from nexus.world.planning import RandomShootingMPC
from nexus.world.planning_value import sha, finite_array
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.rewards import pendulum_step_reward
from nexus.world.long_continuation import paired_interval
from nexus.world.terminal_value_execution import checked_id_grid, save

CONFIG=Path('configs/horizon_objective_control.yaml')
PROTOCOL=Path('docs/NEXUS_HORIZON_OBJECTIVE_CONTROL_PROTOCOL.md')
ALLOCATION=Path('configs/horizon_objective_control_allocation.json')
OUTPUT=Path('artifacts/horizon_objective_control.json')
USAGE=Path('artifacts/research_session_horizon_objective_control_usage.json')
PRIMARY='return_gain'
SCORE_H=8
CAND_H=16
FIELDS=('return_h8_student','return_h8_zero','return_h16_student','return_h16_zero',
        'student_gain','zero_gain','return_gain','student_mae','zero_mae',
        'student_first_mismatch','zero_first_mismatch','student_step0_disagree','zero_step0_disagree')


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),eval_tasks=3,visitors=2,
                candidate_horizon=CAND_H,score_horizon=SCORE_H,n_candidates=16,n_actions=3,
                episode_steps=200,phase=0,practical_margin=25.0,time_cap_s=90,env_cap=12000,
                model_cap=1536000,reset_base=11000000,step_seed_base=11100000,
                paired_late_episode_seeds=True,reuse_archived_h16_returns=True,
                three_action_counterfactuals=False,matched_state_first_action_forks=False,
                starting_sha='a9ada15ac3ae758b75187074aaae98eab089d2a9')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked H=8 design/budget changed')
    late_cfg=late.load_config()
    if cfg['reset_base']!=late_cfg['reset_base'] or cfg['step_seed_base']!=late_cfg['step_seed_base']:
        raise ValueError('H=8 seeds must pair with the archived H=16 traces')
    if cfg['eval_task_ids']!=late_cfg['eval_task_ids'] or cfg['eval_physics']!=late_cfg['eval_physics']:
        raise ValueError('development physics drifted')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    budget(cfg)
    return cfg


def budget(cfg):
    counts=dict(episode=10*3*2*200,model_states=10*3*2*200*16*SCORE_H)
    if counts['episode']!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:
        raise ValueError('H=8 resource allocation mismatch')
    return counts


def nested_candidates(seed):
    seq=candidate_sequences(int(seed),16,CAND_H)
    prefix=seq[:,:SCORE_H]
    if prefix.shape!=(16,SCORE_H): raise ValueError('nested prefix shape drifted')
    return seq,prefix


def score_prefix(model,obs,prefix):
    scores,first=score_prefix_with_first(model,obs,prefix)
    del first
    return scores


def score_prefix_with_first(model,obs,prefix):
    prefix=np.asarray(prefix,dtype=np.int64)
    if prefix.shape!=(16,SCORE_H): raise ValueError('H=8 prefix is not 16x8')
    n=16
    s=np.repeat(np.asarray(obs,dtype=np.float32).reshape(1,-1),n,axis=0)
    begin=getattr(model,'begin_rollout',None)
    if begin is not None: begin(n)
    alive=np.ones(n,dtype=np.float64);score=np.zeros(n,dtype=np.float64);first=None
    for t in range(SCORE_H):
        nxt,p=model.step(s,prefix[:,t])
        nxt=np.asarray(nxt,dtype=np.float32).reshape(n,-1)
        if t==0: first=nxt.copy()
        p=np.clip(np.asarray(p,dtype=np.float64).reshape(n),0.0,1.0)
        r=np.asarray(pendulum_step_reward(s,prefix[:,t],nxt),dtype=np.float64).reshape(n)
        score+=alive*r
        alive=alive*(1.0-p)
        s=nxt
    if first is None: raise RuntimeError('missing first-step predictions')
    return score,first


def score_prefix_reference(model,obs,prefix):
    prefix=np.asarray(prefix,dtype=np.int64)
    planner=RandomShootingMPC(model=model,n_actions=3,horizon=SCORE_H,n_candidates=16,seed=0,
                              objective='predicted_reward',step_reward=pendulum_step_reward,
                              enforce_time_budget=False)
    return np.asarray(planner._score_batch(np.asarray(obs,dtype=np.float32),prefix),dtype=np.float64)


def archived_h16_returns():
    payload=json.loads(late.OUTPUT.read_text())
    if payload.get('complete') is not True: raise ValueError('archived H=16 capture is incomplete')
    out={}
    for cell in payload['cells']:
        out[(int(cell['decoder']),int(cell['task']))]=dict(
            student=float(cell['metrics']['return_student']),zero=float(cell['metrics']['return_zero']),
            student_actions=list(map(int,cell['student']['actions'])),
            zero_actions=list(map(int,cell['zero']['actions'])),
            true_state=list(cell['true_state']),
            seeds=list(map(int,cell['student']['seeds'])))
    if len(out)!=30: raise ValueError('archived H=16 grid drifted')
    return out


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'shorter_horizon_improves_episode_return'
    if mean<=-margin and hi<0: return 'shorter_horizon_hurts_episode_return'
    return 'shorter_horizon_not_established'


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=90,env_cap=12000,model_cap=1536000).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('H=8 allocation drift')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before H=8 collection')
    if sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')
    if sha(PROTOCOL)!=record.get('protocol_sha256'):
        raise PermissionError('allocation does not bind this protocol hash')
    if sha('artifacts/research_session_first_action_value_usage.json')!=record.get('previous_exhausted_session_sha256'):
        raise PermissionError('exhausted 3600-second ledger was modified')
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def decoder_gain(h8_rows,archived):
    values=[]
    for d in range(10):
        xs=[]
        for t in range(3):
            arch=archived[(d,t)]; row=h8_rows[(d,t)]
            xs.append(0.5*((row['student']-arch['student'])+(row['zero']-arch['zero'])))
        values.append(float(sum(xs)/3.0))
    return paired_interval(values)


def cell_metrics(student,zero,archived):
    rs=float(math.fsum(student['rewards'])); rz=float(math.fsum(zero['rewards']))
    h16s=float(archived['student']); h16z=float(archived['zero'])
    sg=rs-h16s; zg=rz-h16z
    sm=late.first_mismatch(student['actions'],archived['student_actions'])
    zm=late.first_mismatch(zero['actions'],archived['zero_actions'])
    return dict(return_h8_student=rs,return_h8_zero=rz,return_h16_student=h16s,return_h16_zero=h16z,
                student_gain=sg,zero_gain=zg,return_gain=0.5*(sg+zg),
                student_mae=float(np.mean(student['angvel_err'])),zero_mae=float(np.mean(zero['angvel_err'])),
                student_first_mismatch=float(sm if sm is not None else 200),
                zero_first_mismatch=float(zm if zm is not None else 200),
                student_step0_disagree=float(int(student['actions'][0])!=int(archived['student_actions'][0])),
                zero_step0_disagree=float(int(zero['actions'][0])!=int(archived['zero_actions'][0])))


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task'),set(itertools.product(range(10),range(3))))
    for row in cells.values():
        if set(row['metrics'])!=set(FIELDS): raise ValueError('missing H=8 metric')
        finite_array([row['metrics'][k] for k in FIELDS],(len(FIELDS),))
        if int(row['n_steps_student'])!=200 or int(row['n_steps_zero'])!=200: raise ValueError('episode length drifted')
        if not np.isclose(row['metrics']['return_gain'],
                          0.5*(row['metrics']['student_gain']+row['metrics']['zero_gain']),atol=1e-8):
            raise ValueError('return_gain identity mismatch')
    groups={}
    for metric in FIELDS:
        values=[float(np.mean([cells[d,t]['metrics'][metric] for t in range(3)])) for d in range(10)]
        groups[metric]=dict(per_decoder=values,interval=paired_interval(values))
    primary=groups[PRIMARY]['interval']
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,True,cfg['practical_margin'])
    return dict(label=label,groups=groups)


class Meter:
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)}
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('H=8 execution cap reached')
    def instrument_env(self,env):
        original=env.step
        def step(action):
            self.check();result=original(action);self.counts['episode']+=1
            if self.counts['episode']>self.env_cap:raise TimeoutError('env cap reached')
            return result
        env.step=step
    def instrument_model(self,model):
        original=model.step
        def step(obs,actions):
            self.check();result=original(obs,actions)
            self.counts['model_states']+=int(np.asarray(actions).size)
            if self.counts['model_states']>self.model_cap:raise TimeoutError('imagined cap reached')
            return result
        model.step=step


def _rollout(env,model,cfg,d,t):
    obs=np.asarray(env.unwrapped._get_obs(),dtype=np.float32)
    actions=[];rewards=[];obs_list=[];scores_list=[];selected=[];planned=[];err=[];seeds=[];terminated=truncated=False
    for step in range(200):
        if terminated or truncated:raise ValueError('trajectory ended before TimeLimit')
        seed=late.step_seed(cfg,d,t,step)
        seq,prefix=nested_candidates(int(seed))
        scores,first=score_prefix_with_first(model,obs,prefix)
        idx=int(np.argmax(scores));action=int(seq[idx,0]);second=int(seq[idx,1])
        nxt,r,terminated,truncated,_=env.step(action)
        nxt=np.asarray(nxt,dtype=np.float32)
        actions.append(action);rewards.append(float(r));obs_list.append(obs.tolist())
        scores_list.append(np.asarray(scores,dtype=np.float64).tolist());selected.append(idx)
        planned.append(second);err.append(float(abs(float(first[idx,2])-float(nxt[2]))))
        seeds.append(int(seed));obs=nxt
    if len(actions)!=200 or terminated or (not truncated):raise ValueError('episode did not truncate at 200')
    return dict(actions=actions,rewards=rewards,obs=obs_list,scores=scores_list,selected_index=selected,
                planned_second=planned,angvel_err=err,seeds=seeds)


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing H=8 overwrite')
    if late.OUTPUT.exists() is False:raise RuntimeError('archived H=16 capture missing')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    from nexus.tasks.spec import make_task_env
    from nexus.tasks.pendulum_family import pendulum_context_development
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.control_replication import load_replication_config,_confirmation_artifact
    from nexus.world.terminal_value_calibration import parent_evidence,load_models
    from nexus.world.receding_horizon import true_state,restore_state
    from nexus.world.terminal_value_execution import fingerprints
    archived=archived_h16_returns()
    started=time.perf_counter();meter=Meter(cfg)
    p=dict(complete=False,label='incomplete',cells=[],counts=meter.counts,
           implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
           parents=cfg['parents'],late_episode_sha256=sha(late.OUTPUT))
    try:
        if p['config_sha256']!='fc862b46b9ab1163e894acf4a57693282db8d0a20f9f4f35220e0f8f65999b56':
            raise ValueError('locked configuration hash drifted')
        p['checkpoint_before']=verify_checkpoint_integrity()
        parent,seq_stage=parent_evidence();rep=load_replication_config();confirmation=_confirmation_artifact(rep)
        specs=list(pendulum_context_development())
        for d,t in itertools.product(cfg['decoders'],range(3)):
            models=load_models(d,t+8,rep,confirmation,parent,seq_stage)
            for model in models.values():meter.instrument_model(model)
            spec=specs[t];env=make_task_env(spec);obs,_=env.reset(seed=late.reset_seed(cfg,d,t));meter.instrument_env(env)
            try:
                start=true_state(env);before=fingerprints(models)
                if not np.allclose(start,np.asarray(archived[(d,t)]['true_state'],dtype=np.float64)):
                    raise ValueError('paired initial state drifted from archived H=16')
                env.reset(seed=late.reset_seed(cfg,d,t));restore_state(env,start)
                student=_rollout(env,models[str(late.visitor_student(d,t))],cfg,d,t)
                env.reset(seed=late.reset_seed(cfg,d,t));restore_state(env,start)
                zero=_rollout(env,models['zero'],cfg,d,t)
                after=fingerprints(models)
                if before!=after:raise RuntimeError('frozen model/context drift')
                if student['seeds']!=zero['seeds']:raise ValueError('step seeds were not shared')
                if student['seeds']!=archived[(d,t)]['seeds']:raise ValueError('step seeds drifted from archived H=16')
                metrics=cell_metrics(student,zero,archived[(d,t)])
                p['cells'].append(dict(decoder=d,task=t,reset_seed=late.reset_seed(cfg,d,t),
                                       visitor_student=late.visitor_student(d,t),true_state=start.tolist(),
                                       student=student,zero=zero,metrics=metrics,
                                       n_steps_student=len(student['actions']),n_steps_zero=len(zero['actions'])))
            finally:env.close()
            print(f'decoder={d} task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['counts']=dict(meter.counts)
        if int(p['counts']['episode'])!=12000:raise ValueError('env step count drifted')
        if int(p['counts']['model_states'])>1536000:raise ValueError('imagined cap exceeded')
        summary=summarize(p['cells'],cfg);p.update(summary);meter.check()
        p['complete']=len(p['cells'])==30
        p['n_episodes']=60
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
        p['complete']=False;p['label']='incomplete'
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def audit_results():
    cfg=load_config();p=json.loads(OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid H=8 evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    archived=archived_h16_returns()
    n_traces=0
    for row in p['cells']:
        arch=archived[(int(row['decoder']),int(row['task']))]
        for name,trace in (('student',row['student']),('zero',row['zero'])):
            n_traces+=1
            if not np.isclose(math.fsum(trace['rewards']),row['metrics'][f'return_h8_{name}'],atol=1e-8):
                raise ValueError('reward reconstruction drifted')
            for step,seed in enumerate(trace['seeds']):
                seq,prefix=nested_candidates(int(seed))
                idx=int(trace['selected_index'][step])
                if int(trace['actions'][step])!=int(seq[idx,0]):raise ValueError('selected action/seed mismatch')
                if int(np.argmax(trace['scores'][step]))!=idx:raise ValueError('score argmax mismatch')
                if prefix.shape!=(16,8) or seq.shape!=(16,16):raise ValueError('nested candidate shape drifted')
                if not np.array_equal(prefix,seq[:,:8]):raise ValueError('prefix is not nested')
            if trace['seeds']!=arch['seeds']:raise ValueError('candidate-seed schedule drifted')
        rebuilt_metrics=cell_metrics(row['student'],row['zero'],arch)
        for key in FIELDS:
            if not np.isclose(row['metrics'][key],rebuilt_metrics[key],atol=1e-8):
                raise ValueError(f'metric rebuild drifted: {key}')
    if n_traces!=60:raise ValueError('60-episode grid drifted')
    if int(p['counts']['episode'])!=12000:raise ValueError('env accounting drifted')
    if int(p['counts']['model_states'])>1536000:raise ValueError('imagined accounting drifted')
    if p.get('late_episode_sha256')!=sha(late.OUTPUT):raise ValueError('late-episode capture was modified')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'],
                n_episodes=60,new_environment_steps=int(p['counts']['episode']),
                new_imagined_transitions=int(p['counts']['model_states']))
