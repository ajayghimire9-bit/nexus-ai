"""Parameter-free one-step lookahead versus frozen H=16 receding.

Successor value is frozen open-loop H=16 score from s', not a learned or
Bellman-consistent receding-policy value. Collection requires a bound one-run
allocation. Does not rewrite the exhausted 3600-second ledger.
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
from nexus.world import receding_long_term_value_audit as audit
from nexus.world.planning_value import sha, finite_array
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.rewards import pendulum_step_reward
from nexus.world.long_continuation import paired_interval
from nexus.world.terminal_value_execution import checked_id_grid, save
from nexus.tasks.pendulum_family import pendulum_context_development,pendulum_physics_key

CONFIG=Path('configs/bellman_backup_control.yaml')
PROTOCOL=Path('docs/NEXUS_BELLMAN_BACKUP_CONTROL_PROTOCOL.md')
ALLOCATION=Path('configs/bellman_backup_control_allocation.json')
OUTPUT=Path('artifacts/bellman_backup_control.json')
USAGE=Path('artifacts/research_session_bellman_backup_control_usage.json')
LOCKED_CONFIG='1a50c953ceb5a20daf3c4e876adc6a8eb855cb5f4ecd1f7d7dffece4fcad625e'
LOCKED_PROTOCOL='6025b926475035677bcb4b7056ef7e0729275be169235f5b94bf956583c4e357'
PRIMARY='return_gain'
FIELDS=('return_lookahead_student','return_lookahead_zero','return_h16_student','return_h16_zero',
        'student_gain','zero_gain','return_gain','student_disagree','zero_disagree',
        'student_mae_h16','student_mae_lookahead','zero_mae_h16','zero_mae_lookahead',
        'student_first_mismatch','zero_first_mismatch')


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),eval_tasks=3,visitors=2,
                candidate_horizon=16,n_candidates=16,n_actions=3,episode_steps=200,phase=0,
                practical_margin=25.0,time_cap_s=180,env_cap=24000,model_cap=12324000,
                training_updates=0,reset_base=13000000,step_seed_base=13100000,
                paired_shared_candidates=True,new_network=False,three_action_counterfactuals=False,
                starting_sha='580dfb0d3e0df1c03d561339577f0a2da8f6e893')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked Bellman design/budget changed')
    specs=pendulum_context_development()
    if cfg['eval_task_ids']!=[s.task_id for s in specs]: raise ValueError('development physics changed')
    if cfg['eval_physics']!=[list(pendulum_physics_key(s)) for s in specs]: raise ValueError('development physics values changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    budget(cfg);check_seeds(cfg)
    return cfg


def reset_seed(cfg,d,t): return cfg['reset_base']+100*d+t
def step_seed(cfg,d,t,step): return cfg['step_seed_base']+1000*d+200*t+step
def visitor_student(d,t): return late.visitor_student(d,t)


def seed_groups(cfg):
    resets={reset_seed(cfg,d,t) for d in range(10) for t in range(3)}
    steps={step_seed(cfg,d,t,s) for d in range(10) for t in range(3) for s in range(200)}
    return [resets,steps]


def check_seeds(cfg):
    groups=seed_groups(cfg)
    if [len(g) for g in groups]!=[30,6000]: raise ValueError('duplicate Bellman seeds')
    used=set().union(*groups)
    blocked=set().union(*late.seed_groups(late.load_config()))
    if used & blocked: raise ValueError('Bellman seeds collide with late-episode/H=8 paired seeds')
    if min(used)<13000000: raise ValueError('seed block drifted below 13000000')


def budget(cfg):
    counts=audit.budget()
    if counts['episode']!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:
        raise ValueError('Bellman resource allocation mismatch')
    if int(cfg['training_updates'])!=0: raise ValueError('training is not part of this protocol')
    return counts


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=180,env_cap=24000,model_cap=12324000,training_updates=0).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('Bellman allocation drift')
    if record.get('config_sha256')!=sha(CONFIG): raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256')!=sha(PROTOCOL): raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before Bellman collection')
    if sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')
    if sha(PROTOCOL)!=record.get('protocol_sha256'):
        raise PermissionError('allocation does not bind this protocol hash')
    if sha('artifacts/research_session_first_action_value_usage.json')!=record.get('previous_exhausted_session_sha256'):
        raise PermissionError('exhausted 3600-second ledger was modified')
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'bellman_backup_improves_episode_return'
    if mean<=-margin and hi<0: return 'bellman_backup_hurts_episode_return'
    return 'bellman_backup_not_established'


def shared_candidates(seed):
    seq=candidate_sequences(int(seed),16,16)
    if seq.shape!=(16,16): raise ValueError('shared candidate shape drifted')
    return seq


def _score_open_loop(model,obs,sequences):
    sequences=np.asarray(sequences,dtype=np.int64)
    if sequences.shape!=(16,16): raise ValueError('shared candidate array drifted')
    n=16
    s=np.repeat(np.asarray(obs,dtype=np.float32).reshape(1,-1),n,axis=0)
    begin=getattr(model,'begin_rollout',None)
    if begin is not None: begin(n)
    alive=np.ones(n,dtype=np.float64);score=np.zeros(n,dtype=np.float64);first=None
    for t in range(16):
        pred,p=model.step(s,sequences[:,t])
        pred=np.asarray(pred,dtype=np.float32).reshape(n,-1)
        if t==0: first=pred.copy()
        p=np.clip(np.asarray(p,dtype=np.float64).reshape(n),0.0,1.0)
        rr=np.asarray(pendulum_step_reward(s,sequences[:,t],pred),dtype=np.float64).reshape(n)
        score+=alive*rr
        alive=alive*(1.0-p)
        s=pred
    if first is None: raise RuntimeError('missing first-step predictions')
    return score,first


def h16_first_action(model,obs,sequences):
    scores,first=_score_open_loop(model,obs,sequences)
    idx=int(np.argmax(scores))
    return int(sequences[idx,0]),scores,idx,first[idx]


def lookahead_first_action(model,obs,sequences):
    """One-step backup of frozen open-loop H=16 value. Not a receding-policy Q."""
    sequences=np.asarray(sequences,dtype=np.int64)
    if sequences.shape!=(16,16): raise ValueError('shared candidate array drifted')
    obs=np.asarray(obs,dtype=np.float32).reshape(1,-1)
    q=[];preds=[]
    for a in range(3):
        nxt,_p=model.step(obs,np.asarray([a],dtype=np.int64))
        nxt=np.asarray(nxt,dtype=np.float32).reshape(1,-1)
        r=float(np.asarray(pendulum_step_reward(obs,a,nxt),dtype=np.float64).reshape(-1)[0])
        scores,_first=_score_open_loop(model,nxt,sequences)
        q.append(r+float(np.max(scores)))
        preds.append(nxt.reshape(-1))
    action=int(np.argmax(q))
    return action,q,preds[action]


def first_mismatch(a,b):
    aa=list(map(int,a));bb=list(map(int,b))
    if len(aa)!=len(bb): raise ValueError('trace length mismatch')
    for i,(x,y) in enumerate(zip(aa,bb)):
        if x!=y: return i
    return None


def cell_metrics(student_h16,zero_h16,student_look,zero_look):
    rs_h=float(math.fsum(student_h16['rewards'])); rz_h=float(math.fsum(zero_h16['rewards']))
    rs_l=float(math.fsum(student_look['rewards'])); rz_l=float(math.fsum(zero_look['rewards']))
    sg=rs_l-rs_h; zg=rz_l-rz_h
    sm=first_mismatch(student_look['actions'],student_h16['actions'])
    zm=first_mismatch(zero_look['actions'],zero_h16['actions'])
    return dict(return_lookahead_student=rs_l,return_lookahead_zero=rz_l,
                return_h16_student=rs_h,return_h16_zero=rz_h,
                student_gain=sg,zero_gain=zg,return_gain=0.5*(sg+zg),
                student_disagree=float(np.mean(np.asarray(student_look['actions'])!=np.asarray(student_h16['actions']))),
                zero_disagree=float(np.mean(np.asarray(zero_look['actions'])!=np.asarray(zero_h16['actions']))),
                student_mae_h16=float(np.mean(student_h16['angvel_err'])),
                student_mae_lookahead=float(np.mean(student_look['angvel_err'])),
                zero_mae_h16=float(np.mean(zero_h16['angvel_err'])),
                zero_mae_lookahead=float(np.mean(zero_look['angvel_err'])),
                student_first_mismatch=float(sm if sm is not None else 200),
                zero_first_mismatch=float(zm if zm is not None else 200))


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task'),set(itertools.product(range(10),range(3))))
    for row in cells.values():
        if set(row['metrics'])!=set(FIELDS): raise ValueError('missing lookahead metric')
        finite_array([row['metrics'][k] for k in FIELDS],(len(FIELDS),))
        for key in ('n_steps_student_h16','n_steps_zero_h16','n_steps_student_lookahead','n_steps_zero_lookahead'):
            if int(row[key])!=200: raise ValueError('episode length drifted')
        if not np.isclose(row['metrics']['return_gain'],
                          0.5*(row['metrics']['student_gain']+row['metrics']['zero_gain']),atol=1e-8):
            raise ValueError('return_gain identity mismatch')
    groups={}
    for metric in FIELDS:
        values=[float(np.mean([cells[d,t]['metrics'][metric] for t in range(3)])) for d in range(10)]
        groups[metric]=dict(per_decoder=values,interval=paired_interval(values))
    task_gain=[]
    for t in range(3):
        values=[float(cells[d,t]['metrics']['return_gain']) for d in range(10)]
        task_gain.append(dict(task=t,interval=paired_interval(values)))
    primary=groups[PRIMARY]['interval']
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,True,cfg['practical_margin'])
    return dict(label=label,groups=groups,task_gain=task_gain)


class Meter:
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts=dict(episode=0,model_states=0)
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('lookahead execution cap reached')
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


def _rollout(env,model,cfg,d,t,kind):
    obs=np.asarray(env.unwrapped._get_obs(),dtype=np.float32)
    actions=[];rewards=[];scores_list=[];selected=[];err=[];seeds=[];terminated=truncated=False
    for step in range(200):
        if terminated or truncated:raise ValueError('trajectory ended before TimeLimit')
        seed=step_seed(cfg,d,t,step);seq=shared_candidates(int(seed))
        if kind=='h16':
            action,scores,idx,pred=h16_first_action(model,obs,seq)
            scores_out=np.asarray(scores,dtype=np.float64).tolist()
        else:
            action,q,pred=lookahead_first_action(model,obs,seq)
            idx=int(action);scores_out=[float(v) for v in q]
        nxt,r,terminated,truncated,_=env.step(action)
        nxt=np.asarray(nxt,dtype=np.float32)
        pred=np.asarray(pred,dtype=np.float32).reshape(-1)
        actions.append(int(action));rewards.append(float(r));scores_list.append(scores_out)
        selected.append(int(idx));err.append(float(abs(float(pred[2])-float(nxt[2]))))
        seeds.append(int(seed));obs=nxt
    if len(actions)!=200 or terminated or (not truncated):raise ValueError('episode did not truncate at 200')
    return dict(kind=kind,actions=actions,rewards=rewards,scores=scores_list,selected_index=selected,
                angvel_err=err,seeds=seeds)


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing lookahead overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    from nexus.tasks.spec import make_task_env
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.control_replication import load_replication_config,_confirmation_artifact
    from nexus.world.terminal_value_calibration import parent_evidence,load_models
    from nexus.world.receding_horizon import true_state,restore_state
    from nexus.world.terminal_value_execution import fingerprints
    started=time.perf_counter();meter=Meter(cfg)
    p=dict(complete=False,label='incomplete',cells=[],counts=meter.counts,
           implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
           parents=cfg['parents'],confirmation_physics_used=False,training_updates=0,
           successor_value='frozen_open_loop_h16_score',new_network=False)
    try:
        if p['config_sha256']!=LOCKED_CONFIG: raise ValueError('locked configuration hash drifted')
        if p['protocol_sha256']!=LOCKED_PROTOCOL: raise ValueError('locked protocol hash drifted')
        p['checkpoint_before']=verify_checkpoint_integrity()
        parent,seq_stage=parent_evidence();rep=load_replication_config();confirmation=_confirmation_artifact(rep)
        specs=list(pendulum_context_development())
        if [s.task_id for s in specs]!=cfg['eval_task_ids']: raise ValueError('development task ids drifted')
        for d,t in itertools.product(cfg['decoders'],range(3)):
            models=load_models(d,t+8,rep,confirmation,parent,seq_stage)
            for model in models.values():meter.instrument_model(model)
            spec=specs[t];env=make_task_env(spec);obs,_=env.reset(seed=reset_seed(cfg,d,t));meter.instrument_env(env)
            try:
                start=true_state(env);before=fingerprints(models)
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start)
                student_h16=_rollout(env,models[str(visitor_student(d,t))],cfg,d,t,'h16')
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start)
                zero_h16=_rollout(env,models['zero'],cfg,d,t,'h16')
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start)
                student_look=_rollout(env,models[str(visitor_student(d,t))],cfg,d,t,'lookahead')
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start)
                zero_look=_rollout(env,models['zero'],cfg,d,t,'lookahead')
                after=fingerprints(models)
                if before!=after:raise RuntimeError('frozen model/context drift')
                seeds=student_h16['seeds']
                if zero_h16['seeds']!=seeds or student_look['seeds']!=seeds or zero_look['seeds']!=seeds:
                    raise ValueError('step seeds were not shared')
                metrics=cell_metrics(student_h16,zero_h16,student_look,zero_look)
                p['cells'].append(dict(decoder=d,task=t,reset_seed=reset_seed(cfg,d,t),
                                       visitor_student=visitor_student(d,t),true_state=start.tolist(),
                                       student_h16=student_h16,zero_h16=zero_h16,
                                       student_lookahead=student_look,zero_lookahead=zero_look,
                                       metrics=metrics,n_steps_student_h16=len(student_h16['actions']),
                                       n_steps_zero_h16=len(zero_h16['actions']),
                                       n_steps_student_lookahead=len(student_look['actions']),
                                       n_steps_zero_lookahead=len(zero_look['actions'])))
            finally:env.close()
            print(f'decoder={d} task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['counts']=dict(meter.counts)
        if int(p['counts']['episode'])!=24000:raise ValueError('env step count drifted')
        if int(p['counts']['model_states'])!=12324000:raise ValueError('imagined count drifted')
        summary=summarize(p['cells'],cfg);p.update(summary);meter.check()
        p['complete']=len(p['cells'])==30
        p['n_episodes']=120
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
        p['complete']=False;p['label']='incomplete'
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def audit_results():
    cfg=load_config();p=json.loads(OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid lookahead evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    n_traces=0
    for row in p['cells']:
        for name,trace,kind in (('student_h16',row['student_h16'],'h16'),('zero_h16',row['zero_h16'],'h16'),
                                ('student_lookahead',row['student_lookahead'],'lookahead'),
                                ('zero_lookahead',row['zero_lookahead'],'lookahead')):
            n_traces+=1
            key={'student_h16':'return_h16_student','zero_h16':'return_h16_zero',
                 'student_lookahead':'return_lookahead_student','zero_lookahead':'return_lookahead_zero'}[name]
            if not np.isclose(math.fsum(trace['rewards']),row['metrics'][key],atol=1e-8):
                raise ValueError('reward reconstruction drifted')
            for step,seed in enumerate(trace['seeds']):
                seq=shared_candidates(int(seed))
                idx=int(trace['selected_index'][step])
                if kind=='h16':
                    if int(trace['actions'][step])!=int(seq[idx,0]): raise ValueError('H=16 selected action/seed mismatch')
                    if int(np.argmax(trace['scores'][step]))!=idx: raise ValueError('H=16 score argmax mismatch')
                    if len(trace['scores'][step])!=16: raise ValueError('H=16 score width drifted')
                else:
                    if int(trace['actions'][step])!=idx: raise ValueError('lookahead action is not argmax Q')
                    if int(np.argmax(trace['scores'][step]))!=idx: raise ValueError('lookahead Q argmax mismatch')
                    if len(trace['scores'][step])!=3: raise ValueError('lookahead Q width drifted')
                    if idx not in (0,1,2): raise ValueError('lookahead action not in {0,1,2}')
        rebuilt_metrics=cell_metrics(row['student_h16'],row['zero_h16'],row['student_lookahead'],row['zero_lookahead'])
        for key in FIELDS:
            if not np.isclose(row['metrics'][key],rebuilt_metrics[key],atol=1e-8):
                raise ValueError(f'metric rebuild drifted: {key}')
        if row['student_h16']['seeds']!=row['zero_lookahead']['seeds']:
            raise ValueError('candidate-seed schedule drifted across arms')
    if n_traces!=120: raise ValueError('120-episode grid drifted')
    if int(p['counts']['episode'])!=24000: raise ValueError('env accounting drifted')
    if int(p['counts']['model_states'])!=12324000: raise ValueError('imagined accounting drifted')
    if p.get('confirmation_physics_used') is not False: raise ValueError('confirmation physics flag drifted')
    if int(p.get('training_updates',1))!=0: raise ValueError('training updates were recorded')
    if p['checkpoint_before']['verified']!=120 or p['checkpoint_after']['verified']!=120:
        raise ValueError('checkpoint audit drifted')
    if p['checkpoint_before'].get('missing') or p['checkpoint_after'].get('missing'):
        raise ValueError('checkpoint missing')
    if p['checkpoint_before'].get('mismatched') or p['checkpoint_after'].get('mismatched'):
        raise ValueError('checkpoint mismatched')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'],
                n_episodes=120,new_environment_steps=int(p['counts']['episode']),
                new_imagined_transitions=int(p['counts']['model_states']),
                confirmation_physics_used=False,training_updates=0)
