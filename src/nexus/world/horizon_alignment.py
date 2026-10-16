"""Horizon-alignment diagnostic: remaining-horizon MPC versus fixed H=16.

Score-correction and same-set reuse stay closed. The 16-step window is an
artificial cutoff. Primary return is the 200-step TimeLimit episode.
Collection is blocked until a fresh human allocation is committed.
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
from nexus.world import receding_policy_consistency as recede
from nexus.world import same_set_planning as same
from nexus.world.planning_value import sha, finite_array
from nexus.world.long_continuation import paired_interval
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.terminal_value_execution import checked_id_grid, save
from nexus.world.planning import mpc_for_model
from nexus.tasks.pendulum_family import PENDULUM_MAX_STEPS

CONFIG=Path('configs/horizon_alignment.yaml')
PROTOCOL=Path('docs/NEXUS_HORIZON_ALIGNMENT_PROTOCOL.md')
ALLOCATION=Path('configs/horizon_alignment_allocation.json')
AUDIT=Path('artifacts/horizon_alignment_audit.json')
FEASIBILITY=Path('artifacts/horizon_alignment_feasibility.json')
OUTPUT=Path('artifacts/horizon_alignment.json')
PARENT=Path('artifacts/same_set_planning.json')
FIELDS=('short_fixed','short_aligned','gain_short','full_fixed','full_aligned','gain_full',
        'prefix_match','tail_gain','n_tail_mismatches','short_step0_match')


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),eval_tasks=3,visitors=2,horizon=16,
                n_candidates=16,n_actions=3,short_window=16,episode_steps=200,phase=0,
                practical_margin_full=25.0,practical_margin_short=1.0,time_cap_s=180,env_cap=25920,
                model_cap=6405120,reset_base=9000000,short_seed_base=9100000,full_seed_base=9200000,
                starting_sha='aa3a5fb5af0f0145ee5d63aa471813499bdb8eb1')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked horizon-alignment design/budget changed')
    if int(cfg['episode_steps'])!=int(PENDULUM_MAX_STEPS):raise ValueError('episode length is not PENDULUM_MAX_STEPS')
    from nexus.tasks.pendulum_family import pendulum_context_development,pendulum_physics_key
    if cfg['eval_task_ids']!=[s.task_id for s in pendulum_context_development()]:raise ValueError('development physics changed')
    if cfg['eval_physics']!=[list(pendulum_physics_key(s)) for s in pendulum_context_development()]:raise ValueError('development physics values changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    budget(cfg);check_seeds(cfg)
    return cfg


def visitor_student(d,t):return (d+t)%5
def reset_seed(cfg,d,t):return cfg['reset_base']+100*d+t
def short_seed(cfg,d,t,v,step):return cfg['short_seed_base']+1000*d+100*t+16*v+step
def full_seed(cfg,d,t,v,step):return cfg['full_seed_base']+10000*d+1000*t+200*v+step
def remaining_horizon(step,total,cap=16):
    left=int(total)-int(step)
    if left<1:raise ValueError('no remaining environment steps')
    return min(int(cap),left)


def seed_groups(cfg):
    return [
        {reset_seed(cfg,d,t) for d,t in itertools.product(range(10),range(3))},
        {short_seed(cfg,d,t,v,s) for d,t,v,s in itertools.product(range(10),range(3),range(2),range(16))},
        {full_seed(cfg,d,t,v,s) for d,t,v,s in itertools.product(range(10),range(3),range(2),range(200))},
    ]


def check_seeds(cfg):
    recede_cfg=yaml.safe_load(recede.CONFIG.read_text())
    same_cfg=yaml.safe_load(same.CONFIG.read_text())
    blocked=set().union(*acq.seed_groups(yaml.safe_load(acq.CONFIG.read_text())),
                         *recede.seed_groups(recede_cfg),*same.seed_groups(same_cfg))
    groups=seed_groups(cfg)
    if [len(g) for g in groups]!=[30,960,12000]:raise ValueError('duplicate registered horizon-alignment seeds')
    used=set().union(*groups)
    if used & blocked:raise ValueError('horizon-alignment seeds collide with a closed experiment')
    if min(used)<9000000:raise ValueError('seed block drifted below the locked base')


def imagined_aligned(total,cap=16,n_candidates=16):
    return int(n_candidates*sum(min(cap,total-t) for t in range(total)))


def imagined_fixed(total,cap=16,n_candidates=16):
    return int(total*n_candidates*cap)


def budget(cfg):
    n_cells=10*3*2
    counts=dict(short_fixed=n_cells*16,short_aligned=n_cells*16,full_fixed=n_cells*200,full_aligned=n_cells*200,
                model_states=n_cells*(imagined_fixed(16)+imagined_aligned(16)+imagined_fixed(200)+imagined_aligned(200)))
    env=sum(v for k,v in counts.items() if k!='model_states')
    if env!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:raise ValueError('horizon-alignment resource allocation mismatch')
    if imagined_aligned(16)>=imagined_fixed(16) or imagined_aligned(200)>=imagined_fixed(200):
        raise ValueError('aligned imagined budget must be strictly smaller than fixed H=16')
    return counts


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),time_cap_s=180,env_cap=25920,model_cap=6405120).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('horizon-alignment allocation drift')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before collection')
    usage=json.loads(Path(record['previous_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def classify_primary(full_mean,full_lo,full_hi,short_mean,short_lo,short_hi,n,complete=True,identity=True,
                     margin_full=25.0,margin_short=1.0):
    if not complete or not identity or int(n)!=10:return 'incomplete'
    if full_mean>=margin_full and full_lo>0:return 'horizon_alignment_gain'
    if full_hi<0 and full_mean<=-margin_full:return 'fixed_horizon_retained'
    if short_mean>=margin_short and short_lo>0:return 'boundary_specific_alignment'
    return 'horizon_alignment_not_established'


def first_mismatch(a,b):
    aa=list(map(int,a));bb=list(map(int,b))
    if len(aa)!=len(bb):raise ValueError('trace length mismatch')
    for i,(x,y) in enumerate(zip(aa,bb)):
        if x!=y:return i
    return None


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task','state'),set(itertools.product(range(10),range(3),range(2))))
    identity=True
    for row in cells.values():
        if set(row['metrics'])!=set(FIELDS):raise ValueError('missing horizon-alignment metric')
        finite_array([row['metrics'][k] for k in FIELDS],(len(FIELDS),))
        if not np.isclose(row['metrics']['gain_full'],row['metrics']['full_aligned']-row['metrics']['full_fixed'],atol=1e-8):
            raise ValueError('full-episode gain identity mismatch')
        if not np.isclose(row['metrics']['gain_short'],row['metrics']['short_aligned']-row['metrics']['short_fixed'],atol=1e-8):
            raise ValueError('short-window gain identity mismatch')
        if row['metrics']['prefix_match']!=1.0 or row['metrics']['short_step0_match']!=1.0:identity=False
        if int(row['n_steps_full_fixed'])!=200 or int(row['n_steps_full_aligned'])!=200:identity=False
        if int(row['n_steps_short_fixed'])!=16 or int(row['n_steps_short_aligned'])!=16:identity=False
    groups={}
    for name,tasks,visitors in (('pooled',range(3),range(2)),('student_visitor',range(3),[0]),('zero_visitor',range(3),[1])):
        groups[name]={}
        for metric in FIELDS:
            values=[statistics.mean(cells[d,t,v]['metrics'][metric] for t,v in itertools.product(tasks,visitors)) for d in range(10)]
            groups[name][metric]=dict(per_decoder=values,interval=paired_interval(values))
    for t in range(3):
        groups[f'task{t}']={}
        for metric in ('gain_full','gain_short','tail_gain'):
            values=[statistics.mean(cells[d,t,v]['metrics'][metric] for v in range(2)) for d in range(10)]
            groups[f'task{t}'][metric]=dict(per_decoder=values,interval=paired_interval(values))
    full=groups['pooled']['gain_full']['interval'];short=groups['pooled']['gain_short']['interval']
    label=classify_primary(full['mean'],full['lo'],full['hi'],short['mean'],short['lo'],short['hi'],10,True,identity,
                           cfg['practical_margin_full'],cfg['practical_margin_short'])
    return dict(label=label,identity_ok=identity,groups=groups)


class Meter:
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)};self.bucket='short_fixed'
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('horizon-alignment execution cap reached')
    def instrument_env(self,env):
        original=env.step
        def step(action):
            self.check();result=original(action);self.counts[self.bucket]+=1
            if sum(v for k,v in self.counts.items() if k!='model_states')>self.env_cap:raise TimeoutError('env cap reached')
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


def _score(planner,obs,sequences):
    return np.asarray(planner._score_batch(np.asarray(obs,dtype=np.float32),np.asarray(sequences,dtype=np.int64)),dtype=np.float64)


def _choose(planner,obs,seed,horizon):
    seq=candidate_sequences(int(seed),16,int(horizon),3)
    return recede.selected_plan(seq,_score(planner,obs,seq))


def planner_clips_elapsed_time():
    """Fixed H=16 scoring has no episode-clock input. TimeLimit is not applied."""
    return False


def retrospective_parent():
    raw=json.loads(PARENT.read_text())
    if raw.get('complete') is not True or raw.get('label')!='same_set_advantage_not_established':
        raise RuntimeError('parent same-set confirmation is not the locked complete result')
    g=raw['groups']['pooled']
    return dict(parent_sha256=sha(PARENT),parent_label=raw['label'],
                gain_same_fresh=g['gain_same_fresh']['interval'],
                gain_same_h16=g['gain_same_h16']['interval'],
                gain_fresh_h16=g['gain_fresh_h16']['interval'],
                short_window_only=True,artificial_cutoff=True,episode_termination=False)


def feasibility():
    cfg=load_config();load_allocation()
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.confirm_guard import inspect_source_tree
    from nexus.tasks.spec import make_task_env
    from nexus.tasks.pendulum_family import pendulum_context_development
    checks=verify_checkpoint_integrity();source=inspect_source_tree(cfg['starting_sha'])
    spec=list(pendulum_context_development())[0];env=make_task_env(spec,seed=0)
    try:
        max_steps=int(env.spec.max_episode_steps)
        if max_steps!=200:raise ValueError('Pendulum TimeLimit drifted')
    finally:env.close()
    a=candidate_sequences(11,16,16);b=candidate_sequences(11,16,16);c=candidate_sequences(11,16,15)
    if not np.array_equal(a,b) or c.shape!=(16,15):raise ValueError('shared-seed candidate identity failed')
    if remaining_horizon(0,200)!=16 or remaining_horizon(184,200)!=16 or remaining_horizon(185,200)!=15:
        raise ValueError('full-episode remaining-horizon schedule drifted')
    if remaining_horizon(0,16)!=16 or remaining_horizon(1,16)!=15:raise ValueError('short-window remaining-horizon schedule drifted')
    parent=retrospective_parent()
    report=dict(complete=True,new_environment_steps=0,new_imagined_transitions=0,authorized=False,
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                checkpoints=checks,source_inspection=dict(source_dirty=source['source_dirty'],source_changed=source['source_changed']),
                time_limit=dict(max_episode_steps=max_steps,true_terminal_state=False,planner_clips_elapsed_time=planner_clips_elapsed_time(),
                                note='TimeLimit truncates at 200 with terminated=False. MPC scores H=16 using model p, not elapsed time.'),
                identity=dict(shared_seed_full_h16=True,aligned_shortens_only_after_step_184=True),
                retrospective=parent,proposed_budget=budget(cfg),primary='gain_full',
                practical_margin_full=25.0,practical_margin_short=1.0,
                development_outcomes_used_for_tuning=False,score_correction_closed=True,confirmation_used=False,
                process_wall_includes=['checkpoint_loading','collection','validation','audit'])
    save(FEASIBILITY,report);save(AUDIT,dict(complete=True,retrospective=True,parent=parent,time_limit=report['time_limit'],
                                             new_environment_steps=0,new_imagined_transitions=0,authorized=False))
    return report


def _rollout(env,planner,seeds,horizons,total):
    obs=np.asarray(env.unwrapped._get_obs(),dtype=np.float32)
    rewards=[];actions=[];terminated=truncated=False
    for t,(seed,h) in enumerate(zip(seeds,horizons)):
        if terminated or truncated:raise ValueError('trajectory ended before the registered window')
        choice=_choose(planner,obs,seed,h)
        nxt,r,terminated,truncated,_=env.step(int(choice['first_action']))
        rewards.append(float(r));actions.append(int(choice['first_action']))
        obs=np.asarray(nxt,dtype=np.float32)
    if len(rewards)!=int(total):raise ValueError('rollout length drifted')
    return rewards,actions,bool(terminated),bool(truncated)


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing horizon-alignment overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    from nexus.tasks.spec import make_task_env
    from nexus.tasks.pendulum_family import pendulum_context_development
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.control_replication import load_replication_config,_confirmation_artifact
    from nexus.world.terminal_value_calibration import parent_evidence,load_models
    from nexus.world.receding_horizon import true_state
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
            spec=specs[t]
            for v in range(2):
                visitor=str(visitor_student(d,t)) if v==0 else 'zero'
                env=make_task_env(spec);obs,_=env.reset(seed=reset_seed(cfg,d,t));meter.instrument_env(env)
                try:
                    start_state=true_state(env)
                    planner=mpc_for_model(models[visitor],seed=full_seed(cfg,d,t,v,0),enforce_time_budget=False)
                    before=fingerprints(models)
                    short_seeds=[short_seed(cfg,d,t,v,s) for s in range(16)]
                    full_seeds=[full_seed(cfg,d,t,v,s) for s in range(200)]
                    meter.bucket='short_fixed';env.reset(seed=reset_seed(cfg,d,t))
                    sf_r,sf_a,sf_term,sf_trunc=_rollout(env,planner,short_seeds,[16]*16,16)
                    meter.bucket='short_aligned';env.reset(seed=reset_seed(cfg,d,t))
                    sa_r,sa_a,sa_term,sa_trunc=_rollout(env,planner,short_seeds,[remaining_horizon(s,16) for s in range(16)],16)
                    meter.bucket='full_fixed';env.reset(seed=reset_seed(cfg,d,t))
                    ff_r,ff_a,ff_term,ff_trunc=_rollout(env,planner,full_seeds,[16]*200,200)
                    meter.bucket='full_aligned';env.reset(seed=reset_seed(cfg,d,t))
                    fa_r,fa_a,fa_term,fa_trunc=_rollout(env,planner,full_seeds,[remaining_horizon(s,200) for s in range(200)],200)
                    after=fingerprints(models)
                    if before!=after:raise RuntimeError('frozen model/context drift')
                    if sf_term or sa_term or ff_term or fa_term:raise ValueError('Pendulum reported a true terminal state')
                    if (not ff_trunc) or (not fa_trunc):raise ValueError('full episode did not truncate at TimeLimit')
                    if sf_trunc or sa_trunc:raise ValueError('short diagnostic hit TimeLimit')
                    mismatch=first_mismatch(ff_a,fa_a)
                    prefix_ok=mismatch is None or mismatch>=185
                    tail_gain=float(math.fsum(fa_r[185:])-math.fsum(ff_r[185:])) if prefix_ok else float('nan')
                    metrics=dict(short_fixed=float(math.fsum(sf_r)),short_aligned=float(math.fsum(sa_r)),
                                 full_fixed=float(math.fsum(ff_r)),full_aligned=float(math.fsum(fa_r)))
                    metrics.update(gain_short=metrics['short_aligned']-metrics['short_fixed'],
                                   gain_full=metrics['full_aligned']-metrics['full_fixed'],
                                   prefix_match=1.0 if prefix_ok else 0.0,
                                   tail_gain=tail_gain,
                                   n_tail_mismatches=float(sum(int(x!=y) for x,y in zip(ff_a[185:],fa_a[185:]))),
                                   short_step0_match=1.0 if sf_a[0]==sa_a[0] else 0.0)
                    p['cells'].append(dict(decoder=d,task=t,state=v,visitor=visitor,reset_seed=reset_seed(cfg,d,t),
                                           metrics=metrics,true_state=start_state.tolist(),
                                           first_mismatch_step=mismatch,
                                           n_steps_short_fixed=len(sf_a),n_steps_short_aligned=len(sa_a),
                                           n_steps_full_fixed=len(ff_a),n_steps_full_aligned=len(fa_a),
                                           truncated_full=bool(ff_trunc and fa_trunc)))
                finally:env.close()
            print(f'decoder={d} task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['counts']=dict(meter.counts)
        summary=summarize(p['cells'],cfg);p.update(summary);meter.check()
        p['complete']=bool(summary.get('identity_ok') is True and len(p['cells'])==60)
        if p['complete'] is not True:p['label']='incomplete'
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
        p['complete']=False;p['label']='incomplete'
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def audit():
    cfg=load_config();p=json.loads(OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid horizon-alignment evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    if rebuilt['identity_ok'] is not True:raise ValueError('prefix identity failed')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'])
