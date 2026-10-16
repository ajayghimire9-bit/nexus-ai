"""Offline multi-step rollout versus objective-mismatch audit.

Uses archived late-episode (obs, action) traces and frozen FiLM models.
Does not step a simulator, train, fork three actions, or reopen confirmation.
"""
from __future__ import annotations
import itertools
import json
import math
import statistics
import subprocess
import time
from pathlib import Path
import numpy as np
from nexus.world.late_episode_decision_trajectory import (
    CONFIG as LATE_CONFIG, OUTPUT as LATE_OUTPUT, PROTOCOL as LATE_PROTOCOL, visitor_student,
    plan_inconsistency, first_mismatch, EARLY, LATE_START,
)
from nexus.world.long_continuation import paired_interval
from nexus.world.planning_value import sha, finite_array
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.terminal_value_execution import save

AUDIT=Path('docs/NEXUS_MULTISTEP_ROLLOUT_CONTROL_AUDIT.md')
PROTOCOL=Path('docs/NEXUS_HORIZON_OBJECTIVE_CONTROL_PROTOCOL.md')
OUTPUT=Path('artifacts/multistep_rollout_control_audit.json')
LATE_RAW_SHA='743b545d78910f7b0df8c83d15b4eb77190798b1dd803ad4daa51434a6214939'
HORIZONS=(1,2,4,8,16)
MAX_H=16
N_STEPS=200
N_STARTS=N_STEPS-MAX_H
PHASES=(('early',0,64),('middle',64,128),('late',128,N_STARTS))
LARGE_H16=0.5
TRACE_FIELDS=('actions','rewards','obs','scores','selected_index','planned_second','angvel_err','seeds')
ONE_STEP_ATOL=1e-5


def _angle(obs):
    x=np.asarray(obs,dtype=np.float64)
    return np.arctan2(x[...,1],x[...,0])


def angular_distance(pred,actual):
    d=_angle(pred)-_angle(actual)
    return np.abs((d+np.pi)%(2.0*np.pi)-np.pi)


def wrap_model(model,counts):
    if getattr(model,'uses_simulator',False):
        raise RuntimeError('refusing a simulator-backed model')
    original=model.step
    def step(obs,actions):
        result=original(obs,actions)
        counts['model_states']+=int(np.asarray(actions).size)
        counts['env_steps']+=0
        return result
    model.step=step
    return model


def free_run(model,obs0,actions):
    s=np.asarray(obs0,dtype=np.float32).reshape(-1,3)
    act=np.asarray(actions,dtype=np.int64)
    if act.ndim!=2 or act.shape[0]!=s.shape[0]:
        raise ValueError('batched teacher-forced actions are not paired with starts')
    begin=getattr(model,'begin_rollout',None)
    if begin is not None: begin(int(s.shape[0]))
    preds=np.empty((s.shape[0],act.shape[1],3),dtype=np.float32)
    for h in range(act.shape[1]):
        nxt,_p=model.step(s,act[:,h])
        s=np.asarray(nxt,dtype=np.float32).reshape(-1,3)
        preds[:,h]=s
    return preds


def path_arrays(trace):
    obs=np.asarray(trace['obs'],dtype=np.float32)
    act=np.asarray(trace['actions'],dtype=np.int64)
    if obs.shape!=(N_STEPS,3) or act.shape!=(N_STEPS,):
        raise ValueError('archived trace shape drifted')
    if not np.isfinite(obs).all(): raise ValueError('nonfinite archived observation')
    starts=np.arange(N_STARTS)
    obs0=obs[starts]
    actions=np.stack([act[t:t+MAX_H] for t in starts])
    actual=np.stack([obs[t+1:t+1+MAX_H] for t in starts])
    return obs,act,obs0,actions,actual


def horizon_errors(pred,actual):
    if pred.shape!=actual.shape or pred.shape[1]!=MAX_H:
        raise ValueError('free-run prediction is not paired with recorded observations')
    out={}
    for h in HORIZONS:
        p=pred[:,h-1]; a=actual[:,h-1]
        out[str(h)]=dict(angvel=float(np.mean(np.abs(p[:,2]-a[:,2]))),
                         angle=float(np.mean(angular_distance(p,a))),
                         obs_mae=float(np.mean(np.abs(p-a))),
                         n_starts=int(pred.shape[0]))
        finite_array([out[str(h)][k] for k in ('angvel','angle','obs_mae')],(3,))
    return out


def phase_angvel(pred,actual,start_index,stop_index,h):
    sl=slice(int(start_index),int(stop_index))
    p=pred[sl,h-1,2]; a=actual[sl,h-1,2]
    if p.size==0: return float('nan')
    return float(np.mean(np.abs(p-a)))


def inventory(payload):
    if sha(LATE_OUTPUT)!=LATE_RAW_SHA: raise ValueError('closed late-episode capture changed')
    if payload.get('complete') is not True or payload.get('label')!='late_error_growth_not_established':
        raise ValueError('late-episode result lock drifted')
    cells=payload['cells']
    if len(cells)!=30: raise ValueError('late-episode grid drifted')
    fields={name:True for name in TRACE_FIELDS}
    predicted_obs=selected_sequences=next_obs_after_199=False
    reconstructable={'teacher_forced_action_free_run':True,'planned_candidate_open_loop_vs_env':False,
                     'unevaluated_candidate_actual_returns':False}
    for row in cells:
        for name in ('student','zero'):
            tr=row[name]
            if set(TRACE_FIELDS)-set(tr): raise ValueError('missing per-step archive field')
            if 'predicted_obs' in tr: predicted_obs=True
            if 'sequences' in tr or 'selected_sequence' in tr: selected_sequences=True
            if len(tr['obs'])!=N_STEPS: raise ValueError('observation length drifted')
    return dict(
        n_cells=30,fields=fields,predicted_full_observations=predicted_obs,
        selected_imagined_sequences_stored=selected_sequences,
        next_observation_after_step_199=next_obs_after_199,
        planned_sequences_reconstructable_from_seed=True,
        teacher_forced_horizons_without_env=list(HORIZONS),
        last_start_index_for_h16=N_STARTS-1,n_starts_per_trace=N_STARTS,
        planned_candidate_rollout_is_not_executed_error=True,
        reconstructable=reconstructable,
        note='obs[t+h] is the recorded actual after h executed actions from obs[t] for t+h<=199',
    )


def plan_and_state(payload):
    rows=[]
    for cell in payload['cells']:
        mismatch=first_mismatch(cell['student']['actions'],cell['zero']['actions'])
        n_matched=int(mismatch if mismatch is not None else N_STEPS)
        rec={}
        for name in ('student','zero'):
            tr=cell[name]
            acts=np.asarray(tr['actions'],dtype=np.int64)
            planned=np.asarray(tr['planned_second'],dtype=np.int64)
            early=plan_inconsistency(acts,planned,0,EARLY)
            late=plan_inconsistency(acts,planned,LATE_START,199)
            suffix=[]
            for t in range(N_STARTS):
                seq=candidate_sequences(int(tr['seeds'][t]),16,16)
                chosen=seq[int(tr['selected_index'][t])]
                if int(chosen[0])!=int(acts[t]): raise ValueError('reconstructed plan first action drifted')
                if int(chosen[1])!=int(planned[t]): raise ValueError('reconstructed planned second action drifted')
                suffix.append(float(np.mean(chosen[1:]!=acts[t+1:t+MAX_H])))
            obs=np.asarray(tr['obs'],dtype=np.float64)
            rec[name]=dict(plan_inconsistent_early=early,plan_inconsistent_late=late,
                           receding_suffix_mismatch=float(np.mean(suffix)),
                           mean_abs_angvel=float(np.mean(np.abs(obs[:,2]))),
                           mean_upright_cost=float(np.mean(_angle(obs)**2)))
        so=np.asarray(cell['student']['obs'],dtype=np.float64)
        zo=np.asarray(cell['zero']['obs'],dtype=np.float64)
        after=slice(n_matched,N_STEPS)
        obs_l2=float(np.mean(np.linalg.norm(so[after]-zo[after],axis=1))) if n_matched<N_STEPS else 0.0
        rows.append(dict(decoder=int(cell['decoder']),task=int(cell['task']),n_matched=n_matched,
                         first_mismatch=float(n_matched if mismatch is not None else N_STEPS),
                         student=rec['student'],zero=rec['zero'],
                         post_mismatch_obs_l2=obs_l2,
                         prefix_h16_windows=max(0,n_matched-MAX_H)))
    return rows


def decoder_metric(rows,getter):
    values=[]
    for d in range(10):
        xs=[getter(r) for r in rows if r['decoder']==d]
        if len(xs)!=3: raise ValueError('task grid drifted')
        values.append(float(statistics.mean(xs)))
    return dict(per_decoder=values,interval=paired_interval(values))


def summarize_plan(rows):
    def get(path):
        def _g(r):
            cur=r
            for key in path.split('.'): cur=cur[key]
            return float(cur)
        return _g
    out={}
    for key in ('student.plan_inconsistent_early','student.plan_inconsistent_late',
                'zero.plan_inconsistent_early','zero.plan_inconsistent_late',
                'student.receding_suffix_mismatch','zero.receding_suffix_mismatch',
                'post_mismatch_obs_l2','first_mismatch','n_matched'):
        out[key.replace('.','_')]=decoder_metric(rows,get(key) if '.' in key else lambda r,k=key: float(r[k]))
    out['n_cells_prefix_h16']=int(sum(r['prefix_h16_windows']>0 for r in rows))
    out['causal_components']=dict(
        new_observed_state=True,new_candidate_draw=True,shortened_horizon=False,changed_context=False,
        separable_from_this_log=False,
        note='Fixed H=16 and frozen context. New state and new candidates both change every step and cannot be identified separately here.',
    )
    out['receding_suffix_mismatch_is_not_model_error']=True
    return out


def errors_for_pair(pred,actual,n_matched):
    packed=horizon_errors(pred,actual)
    packed['phase']={name:{str(h):phase_angvel(pred,actual,a,b,h) for h in HORIZONS} for name,a,b in PHASES}
    cap=max(0,int(n_matched)-MAX_H)
    if cap==0:
        packed['prefix_matched']={str(h):dict(angvel=None,n_starts=0) for h in HORIZONS}
    else:
        packed['prefix_matched']=horizon_errors(pred[:cap],actual[:cap])
    return packed


def cell_rollouts(cell,student_model,zero_model,counts):
    mismatch=first_mismatch(cell['student']['actions'],cell['zero']['actions'])
    n_matched=int(mismatch if mismatch is not None else N_STEPS)
    paths={}
    for name,tr in (('student',cell['student']),('zero',cell['zero'])):
        _obs,_act,obs0,actions,actual=path_arrays(tr)
        paths[name]=dict(obs0=obs0,actions=actions,actual=actual,angvel_err=np.asarray(tr['angvel_err'][:N_STARTS],dtype=np.float64))
    combos={}
    for model_name,model in (('student',student_model),('zero',zero_model)):
        for path_name,path in paths.items():
            pred=free_run(model,path['obs0'],path['actions'])
            if model_name==path_name:
                recon=np.abs(pred[:,0,2]-path['actual'][:,0,2])
                if float(np.max(np.abs(recon-path['angvel_err'])))>ONE_STEP_ATOL:
                    raise ValueError(f'teacher-forced one-step angvel drifted on {model_name} own path')
            combos[f'{model_name}_on_{path_name}']=errors_for_pair(pred,path['actual'],n_matched)
    return dict(n_matched=n_matched,combos=combos,imagined=int(4*N_STARTS*MAX_H))


def isolation_cell(combos,h='16',metric='angvel'):
    s_s=combos['student_on_student'][h][metric]
    z_s=combos['zero_on_student'][h][metric]
    s_z=combos['student_on_zero'][h][metric]
    z_z=combos['zero_on_zero'][h][metric]
    return dict(student_minus_zero_on_student_path=s_s-z_s,
                student_minus_zero_on_zero_path=s_z-z_z,
                mean_isolation=0.5*((s_s-z_s)+(s_z-z_z)),
                own_path_student_minus_zero=s_s-z_z)


def summarize_rollouts(cells):
    def combo_mean(combo,h,metric):
        return decoder_metric(cells,lambda r: float(r['combos'][combo][str(h)][metric]))
    out={'horizons':{},'isolation':{},'own_path':{},'phase':{},'prefix_matched_coverage':int(sum(r['n_matched']>=MAX_H for r in cells))}
    for h in HORIZONS:
        hs=str(h)
        out['horizons'][hs]={combo:combo_mean(combo,h,'angvel') for combo in
                             ('student_on_student','zero_on_zero','student_on_zero','zero_on_student')}
        out['horizons'][hs]['angle_student_on_student']=combo_mean('student_on_student',h,'angle')
        out['horizons'][hs]['angle_zero_on_zero']=combo_mean('zero_on_zero',h,'angle')
        out['isolation'][hs]=decoder_metric(cells,lambda r,hh=hs: isolation_cell(r['combos'],hh)['mean_isolation'])
        out['own_path'][hs]=decoder_metric(cells,lambda r,hh=hs: isolation_cell(r['combos'],hh)['own_path_student_minus_zero'])
        out['phase'][hs]={}
        for phase,_a,_b in PHASES:
            out['phase'][hs][phase]=dict(
                student=decoder_metric(cells,lambda r,p=phase,hh=hs: float(r['combos']['student_on_student']['phase'][p][hh])),
                zero=decoder_metric(cells,lambda r,p=phase,hh=hs: float(r['combos']['zero_on_zero']['phase'][p][hh])),
            )
    return out


def evidence_matrix():
    return [
        dict(claim='Student executed one-step angvel MAE stays below zero on live development paths',
             status='demonstrated',source='late_episode_decision_trajectory.json',
             number='student early 0.089 / late 0.085; zero early 0.123 / late 0.104',
             limit='Own-path after first mismatch; not same-state first-action quality'),
        dict(claim='Student late executed-error growth exceeds zero by a practical 0.05',
             status='inconclusive',source='late_episode_decision_trajectory.json',
             number='+0.016 [+0.003, +0.029]; label late_error_growth_not_established',
             limit='Mean below 0.05; cannot pass control'),
        dict(claim='Student beats zero on 200-step development return in the late-episode sample',
             status='inconclusive',source='late_episode_decision_trajectory.json',
             number='−5.414 [−92.420, +81.592]',limit='Includes 0; far below 25-point screen'),
        dict(claim='Student H=16 candidate ranking is strong on source prefixes',
             status='demonstrated',source='planning_value.json / decision-aware source audit',
             number='Spearman 0.923; selected16 regret 0.336',
             limit='One-shot complete-sequence ranking, not receding 200-step control'),
        dict(claim='Exact H=16 sequence selection misses 64-step value under common-zero continuation',
             status='demonstrated',source='planning_value.json',
             number='+34.685 [+22.677, +46.694]; short_objective_misses_practical_value',
             limit='Committing 16 actions then 48 zero-policy steps is not receding first-action control'),
        dict(claim='Best complete 16-sequence first action is optimal for first-action+zero-replan',
             status='demonstrated_gap',source='action_value_alignment.json',
             number='regret 20.254 [11.382, 29.127]; optimal in 18/60 states',
             limit='Finite 16-candidate set; not a deployed controller'),
        dict(claim='Learned first-action Q/V improves 64-step or 200-step receding return versus H=16',
             status='inconclusive',source='first_action_value / action_conditioned_q_completed',
             number='linear Q −3.535 [−9.840, +2.769]; conditioned Q −4.293 [−15.751, +7.165]',
             limit='Score-correction stays closed'),
        dict(claim='Open-loop 16-action commitment beats receding on 16-step source return',
             status='inconclusive',source='receding_policy_consistency.json',
             number='commit−recede-fresh −1.787 [−4.324, +0.751]',
             limit='16-step return only; not 200-step episodes'),
        dict(claim='Remaining-horizon clipping beats fixed H=16 on 200-step development return',
             status='inconclusive',source='horizon_alignment.json',
             number='+0.523 [−0.077, +1.123]; boundary_specific_alignment',
             limit='All episode difference sat in the last 15 steps'),
        dict(claim='Better one-shot prediction and ranking on fresh physics',
             status='demonstrated',source='prediction_control_gap.json',
             number='one-step angvel improvement 0.1148; regret −1.313; Spearman +0.0597',
             limit='Closed episode return still favored zero by −19.4; open-loop candidate angvel 1.159 vs 1.823'),
        dict(claim='Same-state late first-action quality separates student from zero',
             status='inconclusive',source='late_control_gap.json',
             number='+0.0312 [−0.0827, +0.1452]; action_quality_not_separated',
             limit='16-step common-zero continuation; not 184-step loss'),
        dict(claim='True 2/4/8/16-step teacher-forced executed-action error from archives',
             status='measured_this_audit',source='late_episode_decision_trajectory.json plus frozen models',
             number='see rollout summary',limit='Descriptive; not a preregistered late-episode primary'),
        dict(claim='Planned 16-action trajectory equals the next 16 receding actions',
             status='not_available_as_identity',source='late_episode traces',
             number='receding suffix mismatch is a plan-consistency statistic',
             limit='Disagreement is not world-model prediction error'),
        dict(claim='Simulator-executed candidate open-loop error on these development episodes',
             status='not_available',source='would require new env transitions',
             number=None,limit='PCG already measured candidate open-loop on closed confirmation/replication splits'),
    ]


def recommend(rollouts,plan):
    h16=rollouts['horizons']['16']
    student_h16=h16['student_on_student']['interval']['mean']
    zero_h16=h16['zero_on_zero']['interval']['mean']
    isolation=rollouts['isolation']['16']['interval']
    large=bool(student_h16>=LARGE_H16 and zero_h16>=LARGE_H16)
    student_better=bool(isolation['hi']<0)
    if large and not student_better:
        choice='shorter_horizon_control'
        reason='H=16 teacher-forced angvel MAE is at least 0.5 on both own paths and the student is not more accurate on matched recorded actions. Lengthening imagination would add compounding. Test H=8 versus frozen H=16 on 200-step return.'
    else:
        choice='longer_horizon_objective'
        reason='H=16 teacher-forced error is below the 0.5 compounding threshold and/or the student remains more accurate on matched recorded actions. Exact H=16 sequence selection already misses 64-step value. Test H=32 versus frozen H=16 on 200-step return as an objective-horizon intervention, not a prediction-loss retrain.'
    return dict(
        choice=choice,reason=reason,large_compounding=large,student_more_accurate_at_h16=student_better,
        student_h16_own=student_h16,zero_h16_own=zero_h16,isolation_h16=isolation,
        ranking_loss_training=False,three_action_forks=False,authorized=False,
        primary_estimand='visitor-averaged 200-step return of the new horizon arm minus archived H=16 receding on the same development resets',
        practical_threshold=25.0,statistical_units='ten independent decoders',
        full_episode_return_is_primary=True,frozen_baselines=True,
        development_only=True,confirmation_closed=True,
        env_cap=12000,model_cap=6144000 if choice=='longer_horizon_objective' else 1536000,
        time_cap_s=90 if choice=='shorter_horizon_control' else 120,
        imagined_formula='10*3*2*200*16*H_new',
        reused_h16_returns='artifacts/late_episode_decision_trajectory.json',
        invalid_if=['any env.step beyond 12000','training','confirmation physics','overwrite of closed captures','incomplete 30-cell grid'],
    )


def load_frozen_models(d,t,rep,confirmation,parent,seq_stage):
    from nexus.world.terminal_value_calibration import load_models
    return load_models(d,t+8,rep,confirmation,parent,seq_stage)


def run(model_loader=None):
    started=time.perf_counter()
    if sha(LATE_OUTPUT)!=LATE_RAW_SHA: raise ValueError('closed late-episode capture changed')
    payload=json.loads(LATE_OUTPUT.read_text())
    inv=inventory(payload)
    plan_rows=plan_and_state(payload)
    plan=summarize_plan(plan_rows)
    counts=dict(env_steps=0,model_states=0)
    cells=[]
    checkpoint=None
    if model_loader is None:
        from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
        from nexus.world.control_replication import load_replication_config,_confirmation_artifact
        from nexus.world.terminal_value_calibration import parent_evidence
        from nexus.world.terminal_value_execution import fingerprints
        checkpoint=verify_checkpoint_integrity()
        parent,seq_stage=parent_evidence();rep=load_replication_config();confirmation=_confirmation_artifact(rep)
        def model_loader(d,t):
            models=load_frozen_models(d,t,rep,confirmation,parent,seq_stage)
            before=fingerprints(models)
            student=wrap_model(models[str(visitor_student(d,t))],counts)
            zero=wrap_model(models['zero'],counts)
            return student,zero,before,models,fingerprints
    for cell in payload['cells']:
        d,t=int(cell['decoder']),int(cell['task'])
        loaded=model_loader(d,t)
        student,zero,before,models,fp_fn=loaded
        rolled=cell_rollouts(cell,student,zero,counts)
        after=fp_fn(models)
        if before!=after: raise RuntimeError('frozen model/context drift during offline rollout')
        cells.append(dict(decoder=d,task=t,n_matched=rolled['n_matched'],combos=rolled['combos']))
        print(f'decoder={d} task={t} imagined={counts["model_states"]} seconds={time.perf_counter()-started:.1f}',flush=True)
    rollouts=summarize_rollouts(cells)
    rec=recommend(rollouts,plan)
    report=dict(
        complete=True,new_environment_steps=int(counts['env_steps']),new_imagined_transitions=int(counts['model_states']),
        training=0,authorized=False,confirmation_used=False,three_action_forks=False,
        starting_sha='a9ada15ac3ae758b75187074aaae98eab089d2a9',
        implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        late_episode_sha256=LATE_RAW_SHA,late_config_sha256=sha(LATE_CONFIG),late_protocol_sha256=sha(LATE_PROTOCOL),
        checkpoint=checkpoint,inventory=inv,plan_consistency=plan,rollouts=rollouts,recommendation=rec,
        evidence_matrix=evidence_matrix(),descriptive=True,preregistered_primary=False,
        wall_clock_s=time.perf_counter()-started,
        note='Teacher-forced executed-action free-run is not a planned-candidate rollout and not a new environment experiment.',
    )
    if report['new_environment_steps']!=0: raise RuntimeError('offline audit collected environment steps')
    save(OUTPUT,report);return report
