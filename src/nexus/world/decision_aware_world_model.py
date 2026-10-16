"""Decision-aware world-model diagnostic: near-best versus dominated score error.

Score-correction, remaining-horizon alignment, same-set reuse and confirmation
physics stay closed. Collection is blocked until a fresh human allocation.
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
from nexus.world import horizon_alignment as horizon
from nexus.world import receding_policy_consistency as recede
from nexus.world import same_set_planning as same
from nexus.world.planning_value import sha, finite_array
from nexus.world.long_continuation import paired_interval
from nexus.world.prediction_control_gap import candidate_sequences, planner_scores, decision_metrics
from nexus.world.control_replication import _pearson
from nexus.world.terminal_value_execution import checked_id_grid, save
from nexus.world.planning import mpc_for_model

CONFIG=Path('configs/decision_aware_world_model.yaml')
PROTOCOL=Path('docs/NEXUS_DECISION_AWARE_WORLD_MODEL_PROTOCOL.md')
ALLOCATION=Path('configs/decision_aware_world_model_allocation.json')
AUDIT=Path('artifacts/decision_aware_world_model_audit.json')
FEASIBILITY=Path('artifacts/decision_aware_world_model_feasibility.json')
OUTPUT=Path('artifacts/decision_aware_world_model.json')
PLANNING=Path('artifacts/planning_value.json')
PCG=Path('artifacts/prediction_control_gap.json')
FIRST_ACTION=Path('artifacts/first_action_value.json')
VISITED=Path('artifacts/visited_commitment.json')
NAMES=('zero','0','1','2','3','4')
FIELDS=('student_contrast','zero_contrast','student_regret16','zero_regret16','student_rank16',
        'zero_rank16','student_mae','zero_mae','student_angvel_contrast','zero_angvel_contrast',
        'first_action_regret16','episode_student','episode_zero','episode_gain')
PRIMARY='student_contrast'


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),eval_tasks=3,horizon=16,
                n_candidates=16,n_actions=3,episode_steps=200,phase=0,near_best_tau=1.0,
                practical_margin=1.0,time_cap_s=90,env_cap=19680,model_cap=3164160,
                reset_base=10000000,candidate_base=10100000,episode_student_base=10200000,
                episode_zero_base=10300000,starting_sha='9cf3d198060d2bb2df7f13a4dfa1ddb2403ba81a')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked decision-aware design/budget changed')
    from nexus.tasks.pendulum_family import pendulum_context_development,pendulum_physics_key
    if cfg['eval_task_ids']!=[s.task_id for s in pendulum_context_development()]:raise ValueError('development physics changed')
    if cfg['eval_physics']!=[list(pendulum_physics_key(s)) for s in pendulum_context_development()]:raise ValueError('development physics values changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    budget(cfg);check_seeds(cfg)
    return cfg


def visitor_student(d,t):return (d+t)%5
def reset_seed(cfg,d,t):return cfg['reset_base']+100*d+t
def candidate_seed(cfg,d,t):return cfg['candidate_base']+100*d+t
def episode_seeds(cfg,d,t,visitor):
    base=(cfg['episode_student_base'] if visitor=='student' else cfg['episode_zero_base'])+10000*d+1000*t
    return list(range(base,base+200))


def seed_groups(cfg):
    return [
        {reset_seed(cfg,d,t) for d,t in itertools.product(range(10),range(3))},
        {candidate_seed(cfg,d,t) for d,t in itertools.product(range(10),range(3))},
        {s for d,t in itertools.product(range(10),range(3)) for s in episode_seeds(cfg,d,t,'student')},
        {s for d,t in itertools.product(range(10),range(3)) for s in episode_seeds(cfg,d,t,'zero')},
    ]


def check_seeds(cfg):
    recede_cfg=yaml.safe_load(recede.CONFIG.read_text())
    same_cfg=yaml.safe_load(same.CONFIG.read_text())
    horizon_cfg=yaml.safe_load(horizon.CONFIG.read_text())
    blocked=set().union(*acq.seed_groups(yaml.safe_load(acq.CONFIG.read_text())),
                         *recede.seed_groups(recede_cfg),*same.seed_groups(same_cfg),
                         *horizon.seed_groups(horizon_cfg))
    groups=seed_groups(cfg)
    if [len(g) for g in groups]!=[30,30,6000,6000]:raise ValueError('duplicate registered decision-aware seeds')
    used=set().union(*groups)
    if used & blocked:raise ValueError('decision-aware seeds collide with a closed experiment')
    if min(used)<10000000:raise ValueError('seed block drifted below the locked base')


def budget(cfg):
    n_states=10*3
    counts=dict(prefix=n_states*16*16,episode=n_states*2*200,
                model_states=n_states*(6*16*16+6*16*16+2*200*16*16))
    env=counts['prefix']+counts['episode']
    if env!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:raise ValueError('decision-aware resource allocation mismatch')
    return counts


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),time_cap_s=90,env_cap=19680,model_cap=3164160).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('decision-aware allocation drift')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before collection')
    usage=json.loads(Path(record['previous_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def near_best_mask(actual,tau=1.0):
    a=np.asarray(actual,dtype=np.float64).reshape(-1)
    if a.shape!=(16,) or not np.isfinite(a).all():raise ValueError('sixteen finite actual returns required')
    if type(tau) not in (int,float) or not math.isfinite(tau) or tau<=0:raise ValueError('invalid near-best threshold')
    return a>=(float(a.max())-float(tau))


def score_error_contrast(scores,actual,tau=1.0):
    s=np.asarray(scores,dtype=np.float64).reshape(-1)
    a=np.asarray(actual,dtype=np.float64).reshape(-1)
    if s.shape!=a.shape or s.shape!=(16,):raise ValueError('scores and actuals are not a paired 16-set')
    if not np.isfinite(s).all() or not np.isfinite(a).all():raise ValueError('nonfinite score/actual')
    mask=near_best_mask(a,tau)
    if int(mask.sum())<1 or int((~mask).sum())<1:raise ValueError('near-best/dominated split empty')
    err=np.abs(s-a)
    near=float(err[mask].mean());dom=float(err[~mask].mean())
    return dict(near_mae=near,dominated_mae=dom,contrast=near-dom,n_near=int(mask.sum()),n_dominated=int((~mask).sum()))


def first_action_regret(scores,actual,sequences):
    s=np.asarray(scores,dtype=np.float64).reshape(-1)
    a=np.asarray(actual,dtype=np.float64).reshape(-1)
    seq=np.asarray(sequences,dtype=np.int64)
    if s.shape!=(16,) or a.shape!=(16,) or seq.shape!=(16,16):raise ValueError('first-action inputs are not paired')
    first=seq[:,0]
    if np.any((first<0)|(first>2)):raise ValueError('invalid discrete first action')
    chosen=int(first[int(np.argmax(s))])
    by_action={}
    for action in (0,1,2):
        hits=first==action
        if hits.any():by_action[action]=float(a[hits].max())
    if chosen not in by_action:raise ValueError('selected first action missing from the measured set')
    return dict(regret=float(max(by_action.values())-by_action[chosen]),n_actions=len(by_action),chosen=chosen)


def candidate_one_step_angvel(model,obs0,sequences,actual_next):
    sequences=np.asarray(sequences,dtype=np.int64)
    actual_next=np.asarray(actual_next,dtype=np.float32)
    n,horizon=sequences.shape
    if actual_next.shape!=(n,horizon,3):raise ValueError('actual next observations are not paired with candidates')
    teacher=np.repeat(np.asarray(obs0,dtype=np.float32).reshape(1,-1),n,axis=0)
    errs=np.zeros(n,dtype=np.float64)
    for step in range(horizon):
        nxt,_p=model.step(teacher,sequences[:,step])
        errs+=np.abs(np.asarray(nxt,dtype=np.float64)[:,2]-actual_next[:,step,2].astype(np.float64))
        teacher=actual_next[:,step]
    return errs/float(horizon)


def scores_exclude_returns(func=planner_scores):
    names=set(func.__code__.co_varnames[:func.__code__.co_argcount])
    banned={'actual','returns','rewards','regret','prefix'}
    return names.isdisjoint(banned)


def classify_primary(mean,lo,hi,n,complete=True,margin=1.0):
    if not complete or int(n)!=10:return 'incomplete'
    if mean>=margin and lo>0:return 'decision_relevant_error_concentrated'
    if mean<=-margin and hi<0:return 'ordinary_error_larger'
    return 'decision_relevant_error_not_established'


def cell_metrics(scores,actual16,sequences,angvel,episode_student,episode_zero,tau=1.0):
    actual16=np.asarray(actual16,dtype=np.float64)
    student=[score_error_contrast(scores[str(s)],actual16,tau) for s in range(5)]
    zero=score_error_contrast(scores['zero'],actual16,tau)
    student_rank=[decision_metrics(scores[str(s)],actual16,sequences) for s in range(5)]
    zero_rank=decision_metrics(scores['zero'],actual16,sequences)
    student_fa=[first_action_regret(scores[str(s)],actual16,sequences) for s in range(5)]
    student_ang=[_angvel_contrast(angvel[str(s)],actual16,tau) for s in range(5)]
    zero_ang=_angvel_contrast(angvel['zero'],actual16,tau)
    return dict(student_contrast=statistics.mean(r['contrast'] for r in student),
                zero_contrast=zero['contrast'],
                student_regret16=statistics.mean(r['regret'] for r in student_rank),
                zero_regret16=zero_rank['regret'],
                student_rank16=statistics.mean(r['spearman'] for r in student_rank),
                zero_rank16=zero_rank['spearman'],
                student_mae=statistics.mean(r['reward_mae'] for r in student_rank),
                zero_mae=zero_rank['reward_mae'],
                student_angvel_contrast=statistics.mean(r['contrast'] for r in student_ang),
                zero_angvel_contrast=zero_ang['contrast'],
                first_action_regret16=statistics.mean(r['regret'] for r in student_fa),
                episode_student=float(episode_student),episode_zero=float(episode_zero),
                episode_gain=float(episode_student)-float(episode_zero))


def _angvel_contrast(errors,actual16,tau):
    err=np.asarray(errors,dtype=np.float64).reshape(-1)
    if err.shape!=(16,) or not np.isfinite(err).all():raise ValueError('sixteen finite one-step errors required')
    mask=near_best_mask(actual16,tau)
    if int(mask.sum())<1 or int((~mask).sum())<1:raise ValueError('near-best/dominated split empty')
    return dict(contrast=float(err[mask].mean()-err[~mask].mean()))


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task'),set(itertools.product(range(10),range(3))))
    for row in cells.values():
        if set(row['metrics'])!=set(FIELDS):raise ValueError('missing decision-aware metric')
        finite_array([row['metrics'][k] for k in FIELDS],(len(FIELDS),))
        if not np.isclose(row['metrics']['episode_gain'],row['metrics']['episode_student']-row['metrics']['episode_zero'],atol=1e-8):
            raise ValueError('episode gain identity mismatch')
        if int(row['n_near'])<1 or int(row['n_dominated'])<1:raise ValueError('empty near-best split')
        if int(row['n_steps_student'])!=200 or int(row['n_steps_zero'])!=200:raise ValueError('episode length drifted')
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
        self.counts={k:0 for k in budget(cfg)};self.bucket='prefix'
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('decision-aware execution cap reached')
    def instrument_env(self,env):
        original=env.step
        def step(action):
            self.check();result=original(action);self.counts[self.bucket]+=1
            if self.counts['prefix']+self.counts['episode']>self.env_cap:raise TimeoutError('env cap reached')
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


def _rollout(env,planner,seeds,total=200):
    obs=np.asarray(env.unwrapped._get_obs(),dtype=np.float32)
    rewards=[];actions=[];terminated=truncated=False
    for seed in seeds:
        if terminated or truncated:raise ValueError('trajectory ended before the registered window')
        seq=candidate_sequences(int(seed),16,16)
        scores=np.asarray(planner._score_batch(obs,seq),dtype=np.float64)
        action=int(seq[int(np.argmax(scores)),0])
        nxt,r,terminated,truncated,_=env.step(action)
        rewards.append(float(r));actions.append(action);obs=np.asarray(nxt,dtype=np.float32)
    if len(rewards)!=int(total):raise ValueError('rollout length drifted')
    return rewards,actions,bool(terminated),bool(truncated)


def inventory():
    rows=[]
    catalog=(
        ('artifacts/planning_value.json','source','scores+prefix+suffix64','source eight-task ranking versus actual 16/64 returns'),
        ('artifacts/first_action_value.json','source','three first-action 64 returns; no 16-candidate scores','first-action spread only'),
        ('artifacts/action_conditioned_q_completed.json','source+dev','three-action Q labels; development evaluation closed','score-correction closed'),
        ('artifacts/visited_commitment.json','development','scores+prefixes+first_traces','closed score-correction sample'),
        ('artifacts/prediction_control_gap.json','confirmation/replication','decoder aggregates; no per-candidate arrays','closed splits; published only'),
        ('artifacts/horizon_alignment.json','development','episode returns; selected plans','no per-candidate actuals'),
        ('artifacts/same_set_planning.json','development','16-step selected returns','no per-candidate actuals'),
        ('artifacts/receding_policy_consistency.json','source','16-step selected returns','no per-candidate actuals'),
    )
    for path,split,present,missing in catalog:
        rows.append(dict(path=path,sha256=sha(path) if Path(path).exists() else None,split=split,
                         present=present,missing_or_limit=missing,exists=Path(path).exists()))
    return rows


def _planning_source_audit(tau=1.0):
    payload=json.loads(PLANNING.read_text())
    prefixes={row['task']:row for row in payload['prefixes']}
    rows=[]
    for cell in payload['cells']:
        actual=np.array([float(math.fsum(r['rewards'])) for r in prefixes[cell['task']]['rollouts']],dtype=np.float64)
        student=[score_error_contrast(cell['scores'][str(s)],actual,tau) for s in range(5)]
        zero=score_error_contrast(cell['scores']['zero'],actual,tau)
        student_rank=[decision_metrics(np.asarray(cell['scores'][str(s)],dtype=np.float64),actual,prefixes[cell['task']]['sequences']) for s in range(5)]
        zero_rank=decision_metrics(np.asarray(cell['scores']['zero'],dtype=np.float64),actual,prefixes[cell['task']]['sequences'])
        rows.append(dict(decoder=cell['decoder'],task=cell['task'],
                         student_contrast=statistics.mean(r['contrast'] for r in student),
                         zero_contrast=zero['contrast'],
                         student_regret16=statistics.mean(r['regret'] for r in student_rank),
                         zero_regret16=zero_rank['regret'],
                         student_rank16=statistics.mean(r['spearman'] for r in student_rank),
                         zero_rank16=zero_rank['spearman'],
                         student_mae=statistics.mean(r['reward_mae'] for r in student_rank),
                         zero_mae=zero_rank['reward_mae'],
                         n_near=student[0]['n_near'],n_dominated=student[0]['n_dominated']))
    if len(rows)!=80:raise ValueError('planning-value source grid incomplete')
    summary={}
    for metric in ('student_contrast','zero_contrast','student_regret16','zero_regret16','student_rank16','zero_rank16','student_mae','zero_mae'):
        values=[statistics.mean(r[metric] for r in rows if r['decoder']==d) for d in range(10)]
        summary[metric]=dict(per_decoder=values,interval=paired_interval(values))
    mae=summary['student_mae']['per_decoder'];reg=summary['student_regret16']['per_decoder']
    summary['observational_pearson_mae_regret16']=_pearson(mae,reg)
    summary['label']='source_h1_not_established'
    if classify_primary(summary['student_contrast']['interval']['mean'],summary['student_contrast']['interval']['lo'],
                        summary['student_contrast']['interval']['hi'],10,True,1.0)!='decision_relevant_error_not_established':
        summary['label']='source_h1_recomputed_label_mismatch'
    return dict(n_cells=80,tau=tau,historical=True,retuned=False,causal=False,**summary)


def _first_action_source_spread():
    payload=json.loads(FIRST_ACTION.read_text())
    cells=payload['source_cells']
    if len(cells)!=80:raise ValueError('first-action source grid incomplete')
    values=[]
    for d in range(10):
        spreads=[]
        for row in cells:
            if row['decoder']!=d:continue
            returns=finite_array(row['returns'],(3,))
            spreads.append(float(returns.max()-returns.min()))
            if 'scores' in row or 'sequences' in row:raise ValueError('unexpected ranking fields on first-action source cells')
        values.append(statistics.mean(spreads))
    return dict(n_cells=80,has_model_scores=False,spread64=dict(per_decoder=values,interval=paired_interval(values)))


def _visited_exploratory(tau=1.0):
    payload=json.loads(VISITED.read_text())
    rows=[]
    for cell in payload['cells']:
        actual=np.array([float(math.fsum(pre['rewards'])) for pre in cell['prefixes']],dtype=np.float64)
        scores=cell['scores']
        names=[k for k in scores if k!='zero']
        visitor=cell.get('visitor')
        ctx='zero' if visitor=='zero' else (str(cell.get('visitor_model')) if str(cell.get('visitor_model')) in scores else names[0])
        block=scores[ctx]
        sc=np.asarray(block['base'] if isinstance(block,dict) else block,dtype=np.float64)
        contrast=score_error_contrast(sc,actual,tau)
        rows.append(dict(decoder=cell['decoder'],task=cell['task'],visitor=visitor,contrast=contrast['contrast']))
    values=[statistics.mean(r['contrast'] for r in rows if r['decoder']==d) for d in range(10)]
    return dict(n_cells=len(rows),historical=True,closed_sample=True,retuned=False,
                visitor_scored_context_only=True,contrast=dict(per_decoder=values,interval=paired_interval(values)))


def offline_audit():
    cfg=load_config();load_allocation()
    planning=_planning_source_audit(cfg['near_best_tau'])
    first=_first_action_source_spread()
    visited=_visited_exploratory(cfg['near_best_tau'])
    pcg=json.loads(PCG.read_text())
    report=dict(complete=True,new_environment_steps=0,new_imagined_transitions=0,authorized=False,
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                inventory=inventory(),source_planning_value=planning,source_first_action=first,
                visited_commitment_exploratory=visited,
                prediction_control_gap=dict(primary_decision=pcg.get('primary_decision'),
                                            recommendation=pcg.get('recommendation'),
                                            control_improvement=pcg.get('control_improvement'),
                                            full_episode_remeasured=pcg.get('full_episode_remeasured'),
                                            per_candidate_arrays_stored=False,closed=True,retuned=False),
                missing=['predicted_next_obs_by_action_on_source','per_candidate_pcg_arrays',
                         'counterfactual_returns_on_archived_executed_plans_only'],
                h1_established_on_source=False,decision_aware_training_justified=False,
                smallest_next_experiment='development near-best minus dominated H=16 score error',
                proposed_budget=budget(cfg),primary=PRIMARY,practical_margin=1.0,
                confirmation_used=False,score_correction_closed=True,training_authorized=False,
                exhausted_session_unmodified=True)
    save(AUDIT,report);return report


def feasibility():
    cfg=load_config();record=load_allocation()
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.confirm_guard import inspect_source_tree
    checks=verify_checkpoint_integrity();source=inspect_source_tree(cfg['starting_sha'])
    report=dict(complete=True,new_environment_steps=0,new_imagined_transitions=0,authorized=bool(record.get('authorized')),
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                checkpoints=checks,source_inspection=dict(source_dirty=source['source_dirty'],source_changed=source['source_changed']),
                scores_exclude_returns=scores_exclude_returns(),proposed_budget=budget(cfg),primary=PRIMARY,
                development_outcomes_used_for_tuning=False,score_correction_closed=True,confirmation_used=False,
                process_wall_includes=['checkpoint_loading','collection','validation','audit'],training=0)
    save(FEASIBILITY,report);return report


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing decision-aware overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    from nexus.tasks.spec import make_task_env
    from nexus.tasks.pendulum_family import pendulum_context_development
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.control_replication import load_replication_config,_confirmation_artifact
    from nexus.world.terminal_value_calibration import parent_evidence,load_models
    from nexus.world.receding_horizon import true_state,restore_state
    from nexus.world.commitment_value import prefix as block_prefix
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
                start_state=true_state(env)
                seq=candidate_sequences(candidate_seed(cfg,d,t),16,16)
                before=fingerprints(models)
                scores={name:planner_scores(models[name],obs,seq).tolist() for name in NAMES}
                meter.bucket='prefix'
                prefixes=[block_prefix(env,start_state,actions) for actions in seq]
                actual16=np.array([float(math.fsum(pre['rewards'])) for pre in prefixes],dtype=np.float64)
                next_obs=np.array([pre['next_obs'] for pre in prefixes],dtype=np.float32)
                if int(near_best_mask(actual16,cfg['near_best_tau']).sum())<1 or int((~near_best_mask(actual16,cfg['near_best_tau'])).sum())<1:
                    raise ValueError('near-best/dominated split empty')
                angvel={name:candidate_one_step_angvel(models[name],obs,seq,next_obs).tolist() for name in NAMES}
                meter.bucket='episode'
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start_state)
                planner_s=mpc_for_model(models[str(visitor_student(d,t))],seed=episode_seeds(cfg,d,t,'student')[0],enforce_time_budget=False)
                es_r,es_a,es_term,es_trunc=_rollout(env,planner_s,episode_seeds(cfg,d,t,'student'))
                env.reset(seed=reset_seed(cfg,d,t));restore_state(env,start_state)
                planner_z=mpc_for_model(models['zero'],seed=episode_seeds(cfg,d,t,'zero')[0],enforce_time_budget=False)
                ez_r,ez_a,ez_term,ez_trunc=_rollout(env,planner_z,episode_seeds(cfg,d,t,'zero'))
                after=fingerprints(models)
                if before!=after:raise RuntimeError('frozen model/context drift')
                if es_term or ez_term:raise ValueError('Pendulum reported a true terminal state')
                if (not es_trunc) or (not ez_trunc):raise ValueError('full episode did not truncate at TimeLimit')
                metrics=cell_metrics(scores,actual16,seq,angvel,math.fsum(es_r),math.fsum(ez_r),cfg['near_best_tau'])
                split=score_error_contrast(scores['0'],actual16,cfg['near_best_tau'])
                p['cells'].append(dict(decoder=d,task=t,reset_seed=reset_seed(cfg,d,t),candidate_seed=candidate_seed(cfg,d,t),
                                       visitor_student=visitor_student(d,t),true_state=start_state.tolist(),
                                       sequences=seq.tolist(),scores=scores,angvel=angvel,prefixes=prefixes,
                                       metrics=metrics,n_near=split['n_near'],n_dominated=split['n_dominated'],
                                       n_steps_student=len(es_a),n_steps_zero=len(ez_a),truncated=bool(es_trunc and ez_trunc)))
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
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid decision-aware evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'])
