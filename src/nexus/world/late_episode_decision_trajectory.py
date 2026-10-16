"""Paired 200-step receding logs of executed-decision quality.

Does not repeat late-state three-action first-action forks. Collection is
blocked until a fresh human allocation is committed.
"""
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
from nexus.world import action_conditioned_q as acq
from nexus.world import decision_aware_world_model as dawm
from nexus.world import horizon_alignment as horizon
from nexus.world import receding_policy_consistency as recede
from nexus.world import same_set_planning as same
from nexus.world.planning_value import sha, finite_array
from nexus.world.long_continuation import paired_interval
from nexus.world.prediction_control_gap import candidate_sequences, planner_scores
from nexus.world.terminal_value_execution import checked_id_grid, save
from nexus.world.planning import mpc_for_model
from nexus.tasks.pendulum_family import PENDULUM_MAX_STEPS

CONFIG=Path('configs/late_episode_decision_trajectory.yaml')
PROTOCOL=Path('docs/NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_PROTOCOL.md')
ALLOCATION=Path('configs/late_episode_decision_trajectory_allocation.json')
AUDIT=Path('artifacts/late_episode_decision_trajectory_audit.json')
OUTPUT=Path('artifacts/late_episode_decision_trajectory.json')
PRIMARY='growth_diff'
FIELDS=('student_early_mae','student_late_mae','zero_early_mae','zero_late_mae','growth_student',
        'growth_zero','growth_diff','return_student','return_zero','return_gain','first_mismatch',
        'n_matched','plan_inconsistent_early','plan_inconsistent_late')
EARLY=64
LATE_START=64


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),eval_tasks=3,visitors=2,horizon=16,
                n_candidates=16,n_actions=3,episode_steps=200,early_steps=64,phase=0,practical_margin=0.05,
                time_cap_s=90,env_cap=12000,model_cap=3084000,reset_base=11000000,step_seed_base=11100000,
                three_action_counterfactuals=False,matched_state_first_action_forks=False,
                starting_sha='e2da92c521b9c69b0520b144ac43bcf68d62ab01')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked late-episode design/budget changed')
    if int(cfg['episode_steps'])!=int(PENDULUM_MAX_STEPS) or int(cfg['early_steps'])!=EARLY:
        raise ValueError('episode window drifted')
    from nexus.tasks.pendulum_family import pendulum_context_development,pendulum_physics_key
    if cfg['eval_task_ids']!=[s.task_id for s in pendulum_context_development()]:raise ValueError('development physics changed')
    if cfg['eval_physics']!=[list(pendulum_physics_key(s)) for s in pendulum_context_development()]:raise ValueError('development physics values changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    budget(cfg);check_seeds(cfg)
    return cfg


def visitor_student(d,t):return (d+t)%5
def reset_seed(cfg,d,t):return cfg['reset_base']+100*d+t
def step_seed(cfg,d,t,step):return cfg['step_seed_base']+1000*d+200*t+step


def seed_groups(cfg):
    return [
        {reset_seed(cfg,d,t) for d,t in itertools.product(range(10),range(3))},
        {step_seed(cfg,d,t,s) for d,t,s in itertools.product(range(10),range(3),range(200))},
    ]


def check_seeds(cfg):
    recede_cfg=yaml.safe_load(recede.CONFIG.read_text())
    same_cfg=yaml.safe_load(same.CONFIG.read_text())
    horizon_cfg=yaml.safe_load(horizon.CONFIG.read_text())
    dawm_cfg=yaml.safe_load(dawm.CONFIG.read_text())
    blocked=set().union(*acq.seed_groups(yaml.safe_load(acq.CONFIG.read_text())),
                         *recede.seed_groups(recede_cfg),*same.seed_groups(same_cfg),
                         *horizon.seed_groups(horizon_cfg),*dawm.seed_groups(dawm_cfg))
    groups=seed_groups(cfg)
    if [len(g) for g in groups]!=[30,6000]:raise ValueError('duplicate registered late-episode seeds')
    used=set().union(*groups)
    if used & blocked:raise ValueError('late-episode seeds collide with a closed experiment')
    if min(used)<11000000:raise ValueError('seed block drifted below the locked base')
    student={step_seed(cfg,d,t,s) for d,t,s in itertools.product(range(10),range(3),range(200))}
    # Shared across visitors: no visitor factor in the seed.
    if len(student)!=6000:raise ValueError('step seeds must be visitor-independent')


def budget(cfg):
    n_traces=10*3*2
    counts=dict(episode=n_traces*200,model_states=n_traces*200*16*16+n_traces*200)
    if counts['episode']!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:
        raise ValueError('late-episode resource allocation mismatch')
    if cfg['three_action_counterfactuals'] or cfg['matched_state_first_action_forks']:
        raise ValueError('three-action forks are closed and must stay false')
    return counts


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),time_cap_s=90,env_cap=12000,model_cap=3084000).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('late-episode allocation drift')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before collection')
    usage=json.loads(Path(record['previous_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def first_mismatch(a,b):
    aa=list(map(int,a));bb=list(map(int,b))
    if len(aa)!=len(bb):raise ValueError('trace length mismatch')
    for i,(x,y) in enumerate(zip(aa,bb)):
        if x!=y:return i
    return None


def window_mae(err,start,stop):
    sl=np.asarray(err,dtype=np.float64)[start:stop]
    if sl.size==0 or not np.isfinite(sl).all():raise ValueError('empty/nonfinite error window')
    return float(sl.mean())


def plan_inconsistency(actions,planned_second,start,stop):
    acts=np.asarray(actions,dtype=np.int64)
    plan=np.asarray(planned_second,dtype=np.int64)
    if acts.shape!=(200,) or plan.shape!=(200,):raise ValueError('plan-consistency length drifted')
    stop=min(int(stop),199)
    if stop<=start:return float('nan')
    hits=[float(acts[t+1]!=plan[t]) for t in range(start,stop)]
    return float(np.mean(hits))


def classify_primary(mean,lo,hi,n,complete=True,margin=0.05):
    if not complete or int(n)!=10:return 'incomplete'
    if mean>=margin and lo>0:return 'student_late_error_grows_faster'
    if mean<=-margin and hi<0:return 'zero_late_error_grows_faster'
    return 'late_error_growth_not_established'


def cell_metrics(student,zero):
    mismatch=first_mismatch(student['actions'],zero['actions'])
    n_matched=int(mismatch if mismatch is not None else 200)
    sm,zm=student['angvel_err'],zero['angvel_err']
    se=window_mae(sm,0,EARLY);sl=window_mae(sm,LATE_START,200)
    ze=window_mae(zm,0,EARLY);zl=window_mae(zm,LATE_START,200)
    gs=sl-se;gz=zl-ze
    rs=float(math.fsum(student['rewards']));rz=float(math.fsum(zero['rewards']))
    return dict(student_early_mae=se,student_late_mae=sl,zero_early_mae=ze,zero_late_mae=zl,
                growth_student=gs,growth_zero=gz,growth_diff=gs-gz,
                return_student=rs,return_zero=rz,return_gain=rs-rz,
                first_mismatch=float(n_matched if mismatch is not None else 200),
                n_matched=float(n_matched),
                plan_inconsistent_early=plan_inconsistency(student['actions'],student['planned_second'],0,EARLY),
                plan_inconsistent_late=plan_inconsistency(student['actions'],student['planned_second'],LATE_START,199))


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task'),set(itertools.product(range(10),range(3))))
    for row in cells.values():
        if set(row['metrics'])!=set(FIELDS):raise ValueError('missing late-episode metric')
        finite_array([row['metrics'][k] for k in FIELDS],(len(FIELDS),))
        if int(row['n_steps_student'])!=200 or int(row['n_steps_zero'])!=200:raise ValueError('episode length drifted')
        if not np.isclose(row['metrics']['growth_diff'],
                          row['metrics']['growth_student']-row['metrics']['growth_zero'],atol=1e-8):
            raise ValueError('growth_diff identity mismatch')
        if not np.isclose(row['metrics']['return_gain'],
                          row['metrics']['return_student']-row['metrics']['return_zero'],atol=1e-8):
            raise ValueError('return gain identity mismatch')
    groups={}
    for metric in FIELDS:
        values=[statistics.mean(cells[d,t]['metrics'][metric] for t in range(3)) for d in range(10)]
        groups[metric]=dict(per_decoder=values,interval=paired_interval(values))
    primary=groups[PRIMARY]['interval']
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,True,cfg['practical_margin'])
    return dict(label=label,groups=groups)


class Meter:
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)};self.bucket='episode'
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('late-episode execution cap reached')
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
    planner=mpc_for_model(model,seed=step_seed(cfg,d,t,0),enforce_time_budget=False)
    for step in range(200):
        if terminated or truncated:raise ValueError('trajectory ended before TimeLimit')
        seed=step_seed(cfg,d,t,step);seq=candidate_sequences(int(seed),16,16)
        scores=planner_scores(model,obs,seq)
        idx=int(np.argmax(scores));action=int(seq[idx,0]);second=int(seq[idx,1])
        pred,_p=model.step(obs.reshape(1,-1),np.asarray([action],dtype=np.int64))
        nxt,r,terminated,truncated,_=env.step(action)
        nxt=np.asarray(nxt,dtype=np.float32)
        actions.append(action);rewards.append(float(r));obs_list.append(obs.tolist())
        scores_list.append(np.asarray(scores,dtype=np.float64).tolist());selected.append(idx)
        planned.append(second);err.append(float(abs(float(pred[0,2])-float(nxt[2]))))
        seeds.append(int(seed));obs=nxt
    if len(actions)!=200 or terminated or (not truncated):raise ValueError('episode did not truncate at 200')
    return dict(actions=actions,rewards=rewards,obs=obs_list,scores=scores_list,selected_index=selected,
                planned_second=planned,angvel_err=err,seeds=seeds)


def inventory():
    missing=[]
    rp=json.loads(Path('artifacts/return_phase_decomposition.json').read_text())
    ep=rp['paired_episodes'][0]
    missing.append(dict(artifact='return_phase_decomposition.json',has='200 rewards, obs L2 at 0/16/199',
                        missing='actions, scores, candidates, predicted next-obs'))
    if 'actions' in ep or 'scores' in ep:raise ValueError('return-phase unexpectedly stores actions/scores')
    hz=json.loads(Path('artifacts/horizon_alignment.json').read_text())
    if 'actions' in hz['cells'][0]:raise ValueError('horizon-alignment unexpectedly stores actions')
    missing.append(dict(artifact='horizon_alignment.json',has='aggregate 200-step returns, first_mismatch of remaining vs H=16',
                        missing='student/zero actions and scores; visitor-specific candidate seeds'))
    missing.append(dict(artifact='late_control_gap.json',has='same-state 16-step first-action forks at phases 16/50/100/150',
                        missing='live 200-step receding log; not repeated here'))
    missing.append(dict(artifact='prediction_control_gap.json',has='one-shot ranking at registered states',
                        missing='receding 200-step traces'))
    return missing


def offline_audit():
    cfg=load_config();load_allocation()
    report=dict(complete=True,new_environment_steps=0,new_imagined_transitions=0,authorized=False,
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                inventory=inventory(),three_action_forks=False,matched_state_first_action_forks=False,
                confirmation_used=False,score_correction_closed=True,decision_aware_still_unauthorized=True,
                proposed_budget=budget(cfg),primary=PRIMARY,practical_margin=0.05,
                process_wall_includes=['checkpoint_loading','collection','validation','audit'],training=0)
    save(AUDIT,report);return report


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing late-episode overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    from nexus.tasks.spec import make_task_env
    from nexus.tasks.pendulum_family import pendulum_context_development
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.control_replication import load_replication_config,_confirmation_artifact
    from nexus.world.terminal_value_calibration import parent_evidence,load_models
    from nexus.world.receding_horizon import true_state,restore_state
    from nexus.world.terminal_value_execution import fingerprints
    started=time.perf_counter();meter=Meter(cfg)
    p=dict(complete=False,label='incomplete',cells=[],counts=meter.counts,
           implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),parents=cfg['parents'])
    try:
        p['checkpoint_before']=verify_checkpoint_integrity()
        parent,seq_stage=parent_evidence();rep=load_replication_config();confirmation=_confirmation_artifact(rep)
        specs=list(pendulum_context_development())
        for d,t in itertools.product(cfg['decoders'],range(3)):
            models=load_models(d,t+8,rep,confirmation,parent,seq_stage)
            for model in models.values():meter.instrument_model(model)
            spec=specs[t];env=make_task_env(spec);obs,_=env.reset(seed=reset_seed(cfg,d,t));meter.instrument_env(env)
            try:
                start=true_state(env);before=fingerprints(models)
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start)
                student=_rollout(env,models[str(visitor_student(d,t))],cfg,d,t)
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start)
                zero=_rollout(env,models['zero'],cfg,d,t)
                after=fingerprints(models)
                if before!=after:raise RuntimeError('frozen model/context drift')
                if student['seeds']!=zero['seeds']:raise ValueError('step seeds were not shared')
                metrics=cell_metrics(student,zero)
                p['cells'].append(dict(decoder=d,task=t,reset_seed=reset_seed(cfg,d,t),
                                       visitor_student=visitor_student(d,t),true_state=start.tolist(),
                                       student=student,zero=zero,metrics=metrics,
                                       n_steps_student=len(student['actions']),n_steps_zero=len(zero['actions'])))
            finally:env.close()
            print(f'decoder={d} task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['counts']=dict(meter.counts)
        summary=summarize(p['cells'],cfg);p.update(summary);meter.check()
        p['complete']=len(p['cells'])==30
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
        p['complete']=False;p['label']='incomplete'
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def audit_results():
    cfg=load_config();p=json.loads(OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid late-episode evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    for row in p['cells']:
        for name,trace in (('student',row['student']),('zero',row['zero'])):
            for step,seed in enumerate(trace['seeds']):
                seq=candidate_sequences(int(seed),16,16)
                idx=int(trace['selected_index'][step])
                if int(trace['actions'][step])!=int(seq[idx,0]):raise ValueError('selected action/seed mismatch')
                if int(np.argmax(trace['scores'][step]))!=idx:raise ValueError('score argmax mismatch')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'])
