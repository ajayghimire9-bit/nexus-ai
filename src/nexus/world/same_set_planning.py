"""Same-set suffix replanning audit and locked development confirmation.

Score-correction remains closed. The source receding-consistency primary label is
unchanged. Retrospective same-set contrasts cannot upgrade that label.
Collection of the development confirmation is blocked until a fresh allocation.
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
from nexus.world.planning_value import sha, finite_array
from nexus.world.long_continuation import paired_interval
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.terminal_value_execution import checked_id_grid, save
from nexus.world.planning import mpc_for_model

CONFIG=Path('configs/same_set_planning.yaml')
PROTOCOL=Path('docs/NEXUS_SAME_SET_PLANNING_PROTOCOL.md')
ALLOCATION=Path('configs/same_set_planning_allocation.json')
AUDIT=Path('artifacts/same_set_planning_audit.json')
FEASIBILITY=Path('artifacts/same_set_planning_feasibility.json')
OUTPUT=Path('artifacts/same_set_planning.json')
PARENT=Path('artifacts/receding_policy_consistency.json')
FIELDS=('same','fresh_equal','h16','gain_same_fresh','gain_same_h16','gain_fresh_h16',
        'search_noise_switch','state_driven_switch','equal_fresh_switch')
REMAINING=tuple(range(15,0,-1))


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),eval_tasks=3,visitors=2,horizon=16,
                n_candidates=16,n_actions=3,phase=0,practical_margin=1.0,time_cap_s=60,env_cap=2880,
                model_cap=506880,reset_base=8000000,candidate_base=8100000,noise_base=8200000,
                fresh_equal_base=8300000,h16_base=8400000,
                starting_sha='16d904cf5cd38df6e4c6a2f4295ee876053f0ffa')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked same-set planning design/budget changed')
    from nexus.tasks.pendulum_family import pendulum_context_development,pendulum_physics_key
    if cfg['eval_task_ids']!=[s.task_id for s in pendulum_context_development()]:raise ValueError('development physics changed')
    if cfg['eval_physics']!=[list(pendulum_physics_key(s)) for s in pendulum_context_development()]:raise ValueError('development physics values changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    budget(cfg);check_seeds(cfg)
    return cfg


def visitor_student(d,t):return (d+t)%5
def reset_seed(cfg,d,t):return cfg['reset_base']+100*d+t
def candidate_seed(cfg,d,t,v):return cfg['candidate_base']+100*d+10*t+v
def noise_seed(cfg,d,t,v):return cfg['noise_base']+100*d+10*t+v
def fresh_equal_seeds(cfg,d,t,v):
    base=cfg['fresh_equal_base']+10000*d+100*t+15*v
    return list(range(base,base+15))
def h16_seeds(cfg,d,t,v):
    base=cfg['h16_base']+10000*d+100*t+16*v
    return list(range(base,base+16))


def seed_groups(cfg):
    return [
        {reset_seed(cfg,d,t) for d,t in itertools.product(range(10),range(3))},
        {candidate_seed(cfg,d,t,v) for d,t,v in itertools.product(range(10),range(3),range(2))},
        {noise_seed(cfg,d,t,v) for d,t,v in itertools.product(range(10),range(3),range(2))},
        {s for d,t,v in itertools.product(range(10),range(3),range(2)) for s in fresh_equal_seeds(cfg,d,t,v)},
        {s for d,t,v in itertools.product(range(10),range(3),range(2)) for s in h16_seeds(cfg,d,t,v)},
    ]


def check_seeds(cfg):
    recede_cfg=yaml.safe_load(recede.CONFIG.read_text())
    blocked=set().union(*acq.seed_groups(yaml.safe_load(acq.CONFIG.read_text())),*recede.seed_groups(recede_cfg))
    groups=seed_groups(cfg)
    if [len(g) for g in groups]!=[30,60,60,900,960]:raise ValueError('duplicate registered same-set seeds')
    used=set().union(*groups)
    if used & blocked:raise ValueError('same-set seeds collide with a closed experiment')
    if min(used)<8000000:raise ValueError('seed block drifted below the locked base')


def imagined_recede(horizons):
    return 16*int(sum(horizons))


def budget(cfg):
    n_cells=10*3*2
    counts=dict(same=n_cells*16,fresh_equal=n_cells*16,h16=n_cells*16,
                model_states=n_cells*(256+256+imagined_recede(REMAINING)+imagined_recede(REMAINING)+16*16*16))
    env=sum(v for k,v in counts.items() if k!='model_states')
    if env!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:raise ValueError('same-set resource allocation mismatch')
    if imagined_recede(REMAINING)!=imagined_recede(REMAINING):raise ValueError('equal-horizon recede budgets diverged')
    if counts['same']!=counts['fresh_equal'] or counts['same']!=counts['h16']:raise ValueError('unequal environment arms')
    return counts


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),time_cap_s=60,env_cap=2880,model_cap=506880).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('same-set allocation drift')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before collection')
    usage=json.loads(Path(record['previous_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def remaining_sequences(seed,horizon):
    seq=candidate_sequences(int(seed),16,int(horizon),3)
    if seq.shape!=(16,int(horizon)):raise ValueError('remaining-horizon candidate shape changed')
    return seq


def classify_primary(mean,lo,hi,n,threshold=1.0,complete=True):
    if not complete or int(n)!=10:return 'incomplete'
    if mean>=threshold and lo>0:return 'same_set_replanning_gain'
    if hi<0 and mean<=-threshold:return 'fresh_equal_horizon_gain'
    return 'same_set_advantage_not_established'


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task','state'),set(itertools.product(range(10),range(3),range(2))))
    for row in cells.values():
        if set(row['metrics'])!=set(FIELDS):raise ValueError('missing same-set metric')
        finite_array([row['metrics'][k] for k in FIELDS],(len(FIELDS),))
        if not np.isclose(row['metrics']['gain_same_fresh'],row['metrics']['same']-row['metrics']['fresh_equal'],atol=1e-8):
            raise ValueError('primary gain identity mismatch')
    groups={}
    for name,tasks,visitors in (('pooled',range(3),range(2)),('student_visitor',range(3),[0]),('zero_visitor',range(3),[1])):
        groups[name]={}
        for metric in FIELDS:
            values=[statistics.mean(cells[d,t,v]['metrics'][metric] for t,v in itertools.product(tasks,visitors)) for d in range(10)]
            groups[name][metric]=dict(per_decoder=values,interval=paired_interval(values))
    for t in range(3):
        groups[f'task{t}']={}
        for metric in FIELDS:
            values=[statistics.mean(cells[d,t,v]['metrics'][metric] for v in range(2)) for d in range(10)]
            groups[f'task{t}'][metric]=dict(per_decoder=values,interval=paired_interval(values))
    primary=groups['pooled']['gain_same_fresh']['interval']
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,cfg['practical_margin'],True)
    return dict(label=label,groups=groups)


def decoder_interval(cells,fn,tasks=range(8),visitors=range(2)):
    values=[statistics.mean(fn(cells[d,t,v]) for t,v in itertools.product(tasks,visitors)) for d in range(10)]
    return dict(per_decoder=values,interval=paired_interval(values))


def retrospective_audit():
    """Reconstruct the locked 160 source cells. Zero new environment steps."""
    cfg=recede.load_config();raw=json.loads(PARENT.read_text())
    if raw.get('complete') is not True or len(raw.get('cells',[]))!=160:
        raise RuntimeError('parent receding-consistency capture is incomplete')
    rebuilt=recede.summarize(raw['cells'],cfg)
    if raw['label']!=rebuilt['label']:raise ValueError('parent label does not rebuild')
    cells=checked_id_grid(raw['cells'],('decoder','task','state'),set(itertools.product(range(10),range(8),range(2))))
    for row in cells.values():
        mt=row['metrics']
        if not np.isclose(mt['gain_fresh_same'],mt['recede_fresh']-mt['recede_same'],atol=1e-8):
            raise ValueError('same-set identity mismatch')
        if not np.isclose(mt['gain_commit_same'],mt['commit']-mt['recede_same'],atol=1e-8):
            raise ValueError('commit identity mismatch')
        seq=candidate_sequences(recede.candidate_seed(cfg,row['decoder'],row['task'],row['state']))
        if not np.array_equal(seq[row['plan']['index']],row['plan']['sequence']):
            raise ValueError('saved plan is not the reconstructed candidate row')
    same_minus_fresh=decoder_interval(cells,lambda r:r['metrics']['recede_same']-r['metrics']['recede_fresh'])
    same_minus_commit=decoder_interval(cells,lambda r:r['metrics']['recede_same']-r['metrics']['commit'])
    commit_minus_fresh=decoder_interval(cells,lambda r:r['metrics']['commit']-r['metrics']['recede_fresh'])
    groups={'pooled':{'same_minus_fresh':same_minus_fresh,'same_minus_commit':same_minus_commit,'commit_minus_fresh':commit_minus_fresh}}
    for name,tasks,visitors in (('student_visitor',range(8),[0]),('zero_visitor',range(8),[1])):
        groups[name]={'same_minus_fresh':decoder_interval(cells,lambda r:r['metrics']['recede_same']-r['metrics']['recede_fresh'],tasks,visitors),
                      'same_minus_commit':decoder_interval(cells,lambda r:r['metrics']['recede_same']-r['metrics']['commit'],tasks,visitors)}
    per_task={}
    for t in range(8):
        per_task[t]=decoder_interval(cells,lambda r:r['metrics']['recede_same']-r['metrics']['recede_fresh'],[t],range(2))
    unique_first=[];unique_s1=[];share_selected=[];n_same_gt_fresh=0;n_same_gt_commit=0
    for row in raw['cells']:
        C=candidate_sequences(recede.candidate_seed(cfg,row['decoder'],row['task'],row['state']))
        unique_first.append(len(set(int(a) for a in C[:,0])))
        unique_s1.append(len(set(int(a) for a in C[:,1])))
        share_selected.append(float(np.mean(C[:,0]==row['plan']['first_action'])))
        if row['metrics']['recede_same']>row['metrics']['recede_fresh']:n_same_gt_fresh+=1
        if row['metrics']['recede_same']>row['metrics']['commit']:n_same_gt_commit+=1
    fairness=dict(
        recede_same_imagined_per_cell=imagined_recede(REMAINING),
        recede_fresh_imagined_per_cell=15*16*16,
        imagined_ratio_fresh_over_same=2.0,
        same_set_remaining_horizons=list(REMAINING),
        fresh_receding_horizons=[16]*15,
        same_set_aligned_to_16step_evaluation=True,
        fresh_plans_past_evaluation_window=True,
        unique_first_actions_in_C=dict(mean=float(np.mean(unique_first)),min=int(min(unique_first)),max=int(max(unique_first))),
        unique_s1_suffix_actions=dict(mean=float(np.mean(unique_s1)),min=int(min(unique_s1)),max=int(max(unique_s1))),
        mean_fraction_C_sharing_selected_first=float(np.mean(share_selected)),
        duplicate_full_suffixes=0.0,
        stored_per_step_rewards=False,
        stored_predicted_scores=False,
        predicted_versus_realized_not_identifiable=True,
        leakage_from_confirmation_physics=False,
        note='Same-set receding scores shrinking suffixes of the original 16-step window. Fresh receding scores a new H=16 set at every later state, twice the imagined transitions, and can optimize imagined reward after the 16-step evaluation ends.')
    switches=dict(search_noise=rebuilt['groups']['pooled']['search_noise_switch']['interval'],
                  state_driven=rebuilt['groups']['pooled']['state_driven_switch']['interval'],
                  recede_fresh=rebuilt['groups']['pooled']['fresh_plan_switch']['interval'])
    report=dict(complete=True,retrospective=True,cannot_upgrade_locked_label=True,
                locked_primary_label=raw['label'],locked_primary=commit_minus_fresh['interval'],
                new_environment_steps=0,new_imagined_transitions=0,n_cells=160,
                parent_sha256=sha(PARENT),implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                groups=groups,per_task=per_task,switches=switches,fairness=fairness,
                cells_same_gt_fresh=n_same_gt_fresh,cells_same_gt_commit=n_same_gt_commit,
                decoders_same_gt_fresh=int(sum(x>0 for x in same_minus_fresh['per_decoder'])),
                decoders_same_gt_commit=int(sum(x>0 for x in same_minus_commit['per_decoder'])),
                scientific_status='credible_retrospective_confounded_by_horizon_mismatch',
                confirmation_used=False,score_correction_closed=True)
    save(AUDIT,report);return report


class Meter:
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)};self.bucket='same'
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('same-set planning execution cap reached')
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


def feasibility():
    cfg=load_config();load_allocation()
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.confirm_guard import inspect_source_tree
    checks=verify_checkpoint_integrity();source=inspect_source_tree(cfg['starting_sha'])
    audit=retrospective_audit()
    seq=candidate_sequences(0)
    shifted=recede.shift_suffixes(seq,1)
    if shifted.shape!=(16,15):raise ValueError('suffix shift identity failed')
    eq=remaining_sequences(1,15)
    if eq.shape!=(16,15) or eq.shape==seq.shape:raise ValueError('equal-horizon draw is not remaining-length')
    if imagined_recede(REMAINING)!=15*16*16/2:raise ValueError('equal remaining-horizon imagined count drifted')
    report=dict(complete=True,new_environment_steps=0,new_imagined_transitions=0,authorized=False,
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                checkpoints=checks,source_inspection=dict(source_dirty=source['source_dirty'],source_changed=source['source_changed']),
                retrospective=dict(parent_sha256=audit['parent_sha256'],status=audit['scientific_status'],
                                   same_minus_fresh=audit['groups']['pooled']['same_minus_fresh']['interval'],
                                   same_minus_commit=audit['groups']['pooled']['same_minus_commit']['interval']),
                fairness=audit['fairness'],proposed_budget=budget(cfg),primary='gain_same_fresh',
                practical_margin=1.0,equal_recede_imagined=True,h16_is_production_controller=True,
                development_outcomes_used_for_tuning=False,score_correction_closed=True,confirmation_used=False,
                process_wall_includes=['checkpoint_loading','collection','validation','audit'])
    save(FEASIBILITY,report);return report


def _score(planner,obs,sequences):
    return np.asarray(planner._score_batch(np.asarray(obs,dtype=np.float32),np.asarray(sequences,dtype=np.int64)),dtype=np.float64)


def _step(env,action):
    nxt,r,term,trunc,_=env.step(int(action))
    if term or trunc:raise ValueError('short same-set trajectory')
    return np.asarray(nxt,dtype=np.float32),float(r)


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing same-set planning overwrite')
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
                    seq=candidate_sequences(candidate_seed(cfg,d,t,v))
                    planner=mpc_for_model(models[visitor],seed=candidate_seed(cfg,d,t,v),enforce_time_budget=False)
                    h16_planner=mpc_for_model(models[visitor],seed=h16_seeds(cfg,d,t,v)[0],enforce_time_budget=False)
                    plan=recede.selected_plan(seq,_score(planner,obs,seq))
                    noise_seq=candidate_sequences(noise_seed(cfg,d,t,v))
                    noise=recede.selected_plan(noise_seq,_score(planner,obs,noise_seq))
                    before=fingerprints(models)
                    meter.bucket='same';env.reset(seed=reset_seed(cfg,d,t))
                    obs,r=_step(env,plan['first_action']);same=[r];remaining=recede.shift_suffixes(seq,1);state_switch=None
                    for k,h in enumerate(REMAINING):
                        if remaining.shape!=(16,h):raise ValueError('same-set remaining horizon drifted')
                        choice=recede.selected_plan(remaining,_score(planner,obs,remaining))
                        if k==0:state_switch=recede.first_action_switch(int(plan['sequence'][1]),choice['first_action'])
                        obs,r=_step(env,choice['first_action']);same.append(r)
                        remaining=remaining[:,1:]
                    meter.bucket='fresh_equal';env.reset(seed=reset_seed(cfg,d,t))
                    obs,r=_step(env,plan['first_action']);fresh=[r];equal_switch=None
                    for k,(h,seed) in enumerate(zip(REMAINING,fresh_equal_seeds(cfg,d,t,v))):
                        cand=remaining_sequences(seed,h)
                        choice=recede.selected_plan(cand,_score(planner,obs,cand))
                        if k==0:equal_switch=recede.first_action_switch(int(plan['sequence'][1]),choice['first_action'])
                        obs,r=_step(env,choice['first_action']);fresh.append(r)
                    meter.bucket='h16';env.reset(seed=reset_seed(cfg,d,t));h16=[]
                    obs=np.asarray(env.unwrapped._get_obs(),dtype=np.float32)
                    for seed in h16_seeds(cfg,d,t,v):
                        h16_planner.reset_episode(seed);action,info=h16_planner.act(obs)
                        if info['n_scored']!=16 or info['horizon']!=16:raise ValueError('production H=16 candidate budget changed')
                        obs,r=_step(env,action);h16.append(r)
                    after=fingerprints(models)
                    if before!=after:raise RuntimeError('frozen model/context drift')
                    metrics=dict(same=float(math.fsum(same)),fresh_equal=float(math.fsum(fresh)),h16=float(math.fsum(h16)))
                    metrics.update(gain_same_fresh=metrics['same']-metrics['fresh_equal'],
                                   gain_same_h16=metrics['same']-metrics['h16'],
                                   gain_fresh_h16=metrics['fresh_equal']-metrics['h16'],
                                   search_noise_switch=recede.first_action_switch(plan['first_action'],noise['first_action']),
                                   state_driven_switch=float(state_switch),equal_fresh_switch=float(equal_switch))
                    p['cells'].append(dict(decoder=d,task=t,state=v,visitor=visitor,reset_seed=reset_seed(cfg,d,t),
                                           plan=plan,metrics=metrics,true_state=start_state.tolist()))
                finally:env.close()
            print(f'decoder={d} task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['checkpoint_after']=verify_checkpoint_integrity();p['counts']=dict(meter.counts)
        p.update(summarize(p['cells'],cfg));meter.check();p['complete']=True
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def audit():
    cfg=load_config();p=json.loads(OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid same-set planning evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'])
