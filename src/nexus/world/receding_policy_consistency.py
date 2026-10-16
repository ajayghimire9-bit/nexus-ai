"""Receding-horizon policy-consistency diagnostic.

Score-correction (terminal V and first-action Q) is closed. Frozen H=16 / 16
candidates, world models and checkpoints are not modified. Collection is blocked
until a fresh human allocation is committed.
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
from nexus.world import visited_commitment as visited
from nexus.world.planning_value import sha, finite_array
from nexus.world.long_continuation import paired_interval
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.terminal_value_execution import checked_id_grid, save
from nexus.world.planning import mpc_for_model

CONFIG=Path('configs/receding_policy_consistency.yaml')
PROTOCOL=Path('docs/NEXUS_RECEDING_POLICY_CONSISTENCY_PROTOCOL.md')
ALLOCATION=Path('configs/receding_policy_consistency_allocation.json')
OUTPUT=Path('artifacts/receding_policy_consistency.json')
FEASIBILITY=Path('artifacts/receding_policy_consistency_feasibility.json')
USAGE=Path('artifacts/research_session_first_action_value_usage.json')
FIELDS=('commit','recede_fresh','recede_same','common_zero','gain_commit_fresh','gain_commit_same',
        'gain_fresh_same','gain_fresh_zero','search_noise_switch','state_driven_switch','fresh_plan_switch')


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),source_tasks=8,visitors=2,horizon=16,
                n_candidates=16,n_actions=3,phase=0,practical_margin=1.0,time_cap_s=120,env_cap=8960,
                model_cap=1515520,reset_base=7000000,candidate_base=7100000,noise_base=7200000,recede_base=7300000,
                starting_sha='0aed2e3cb0283cc7c5ea60c9049bdf84ee51148a')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked receding-consistency design/budget changed')
    from nexus.tasks.pendulum_family import pendulum_context_train,pendulum_physics_key
    if cfg['source_task_ids']!=[s.task_id for s in pendulum_context_train()]:raise ValueError('source physics changed')
    if cfg['source_physics']!=[list(pendulum_physics_key(s)) for s in pendulum_context_train()]:raise ValueError('source physics values changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    budget(cfg);check_seeds(cfg)
    return cfg


def visitor_student(d,t):return (d+t)%5
def reset_seed(cfg,d,t):return cfg['reset_base']+100*d+t
def candidate_seed(cfg,d,t,v):return cfg['candidate_base']+100*d+10*t+v
def noise_seed(cfg,d,t,v):return cfg['noise_base']+100*d+10*t+v
def recede_seeds(cfg,d,t,v):
    base=cfg['recede_base']+10000*d+100*t+15*v
    return list(range(base,base+15))


def seed_groups(cfg):
    return [
        {reset_seed(cfg,d,t) for d,t in itertools.product(range(10),range(8))},
        {candidate_seed(cfg,d,t,v) for d,t,v in itertools.product(range(10),range(8),range(2))},
        {noise_seed(cfg,d,t,v) for d,t,v in itertools.product(range(10),range(8),range(2))},
        {s for d,t,v in itertools.product(range(10),range(8),range(2)) for s in recede_seeds(cfg,d,t,v)},
    ]


def check_seeds(cfg):
    blocked=set().union(*acq.seed_groups(yaml.safe_load(acq.CONFIG.read_text())))
    groups=seed_groups(cfg)
    if [len(g) for g in groups]!=[80,160,160,2400]:raise ValueError('duplicate registered seeds')
    used=set().union(*groups)
    if used & blocked:raise ValueError('receding-consistency seeds collide with a closed experiment')
    if min(used)<7000000:raise ValueError('seed block drifted below the locked base')


def budget(cfg):
    n_cells=10*8*2
    counts=dict(commit=n_cells*16,recede_same=n_cells*16,recede_fresh=n_cells*16,common_zero=80*16,
                model_states=1515520)
    env=sum(v for k,v in counts.items() if k!='model_states')
    if env!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:raise ValueError('receding-consistency resource allocation mismatch')
    return counts


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),time_cap_s=120,env_cap=8960,model_cap=1515520).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('receding-consistency allocation drift')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before collection')
    usage=json.loads(Path(record['previous_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def shift_suffixes(sequences,executed=1):
    seq=np.asarray(sequences)
    if seq.ndim!=2 or seq.shape[0]!=16 or seq.shape[1]<executed+1:raise ValueError('cannot shift a short candidate set')
    return seq[:,executed:]


def selected_plan(sequences,scores):
    seq=np.asarray(sequences)
    s=np.asarray(scores,dtype=np.float64).reshape(-1)
    if s.shape!=(len(seq),) or not np.isfinite(s).all():raise ValueError('invalid candidate scores')
    idx=int(np.argmax(s))
    return dict(index=idx,sequence=seq[idx].astype(int).tolist(),first_action=int(seq[idx,0]))


def first_action_switch(a,b):
    if type(a) is not int or type(b) is not int or a not in (0,1,2) or b not in (0,1,2):raise ValueError('invalid discrete action')
    return float(a!=b)


def live_suffix_mismatches(collection):
    """Offline reconstruction: intended plan[1] versus the next receding live action.

    This confounds new candidate-search draws with state change. It is not a
    same-state counterfactual of plan continuation.
    """
    if len(collection)<2:raise ValueError('live collection too short')
    rows=[]
    for k in range(len(collection)-1):
        cur,nxt=collection[k],collection[k+1]
        seq=candidate_sequences(int(cur['seed']))
        idx=int(cur['selected_index'])
        if not 0<=idx<16:raise ValueError('live selected index out of range')
        if int(cur['action'])!=int(seq[idx,0]):raise ValueError('live action is not the selected plan prefix')
        intended=int(seq[idx,1]);actual=int(nxt['action'])
        rows.append(dict(step=k,intended=intended,actual=actual,switch=first_action_switch(intended,actual),
                         reward=float(nxt['reward']) if 'reward' in nxt else None))
    return rows


def decoder_mismatch_interval(cells):
    values=[]
    for d in range(10):
        switches=[]
        for row in cells:
            if row['decoder']!=d:continue
            switches.extend(m['switch'] for m in live_suffix_mismatches(row['collection']))
        if not switches:raise ValueError('decoder missing live collection')
        values.append(float(np.mean(switches)))
    return dict(per_decoder=values,interval=paired_interval(values),n_steps=sum(len(c['collection'])-1 for c in cells))


def classify_primary(mean,lo,hi,n,threshold=1.0,complete=True):
    if not complete or int(n)!=10:return 'incomplete'
    if mean>=threshold and lo>0:return 'open_loop_commitment_gain'
    if hi<0 and mean<=-threshold:return 'receding_replanning_gain'
    return 'replan_consistency_not_established'


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('decoder','task','state'),set(itertools.product(range(10),range(8),range(2))))
    for row in cells.values():
        if set(row['metrics'])!=set(FIELDS):raise ValueError('missing consistency metric')
        finite_array([row['metrics'][k] for k in FIELDS],(len(FIELDS),))
        if not np.isclose(row['metrics']['gain_commit_fresh'],row['metrics']['commit']-row['metrics']['recede_fresh'],atol=1e-8):
            raise ValueError('primary gain identity mismatch')
    groups={}
    for name,tasks,visitors in (('pooled',range(8),range(2)),('student_visitor',range(8),[0]),('zero_visitor',range(8),[1])):
        groups[name]={}
        for metric in FIELDS:
            values=[statistics.mean(cells[d,t,v]['metrics'][metric] for t,v in itertools.product(tasks,visitors)) for d in range(10)]
            groups[name][metric]=dict(per_decoder=values,interval=paired_interval(values))
    primary=groups['pooled']['gain_commit_fresh']['interval']
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,cfg['practical_margin'],True)
    return dict(label=label,groups=groups)


class Meter:
    def __init__(self,cfg):
        self.deadline=time.perf_counter()+cfg['time_cap_s'];self.env_cap=cfg['env_cap'];self.model_cap=cfg['model_cap']
        self.counts={k:0 for k in budget(cfg)};self.bucket='commit'
    def check(self):
        if time.perf_counter()>=self.deadline:raise TimeoutError('receding-policy-consistency execution cap reached')
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


def offline_archived_live(path,kind):
    raw=json.loads(Path(path).read_text())
    cells=raw['cells']
    report=decoder_mismatch_interval(cells)
    later=[m['reward'] for row in cells for m in live_suffix_mismatches(row['collection']) if m['reward'] is not None]
    switched=[m['reward'] for row in cells for m in live_suffix_mismatches(row['collection']) if m['switch']==1.0 and m['reward'] is not None]
    stayed=[m['reward'] for row in cells for m in live_suffix_mismatches(row['collection']) if m['switch']==0.0 and m['reward'] is not None]
    return dict(kind=kind,n_cells=len(cells),n_steps=report['n_steps'],mismatch=report,
                mean_next_reward=float(np.mean(later)) if later else None,
                mean_next_reward_given_switch=float(np.mean(switched)) if switched else None,
                mean_next_reward_given_stay=float(np.mean(stayed)) if stayed else None,
                confounded=True,
                note='next live action uses a new candidate seed at a new state; subsequent reward is not the counterfactual of continuing the original suffix')


def feasibility():
    cfg=load_config();load_allocation()
    from nexus.world.checkpoint_integrity import verify_checkpoint_integrity
    from nexus.world.confirm_guard import inspect_source_tree
    checks=verify_checkpoint_integrity();source=inspect_source_tree(cfg['starting_sha'])
    seq=candidate_sequences(0)
    shifted=shift_suffixes(seq,1)
    if shifted.shape!=(16,15) or not np.array_equal(shifted,seq[:,1:]):raise ValueError('suffix shift identity failed')
    synthetic_scores=np.arange(16,dtype=np.float64)
    plan=selected_plan(seq,synthetic_scores)
    other=selected_plan(candidate_sequences(1),synthetic_scores)
    noise=first_action_switch(plan['first_action'],other['first_action'])
    flipped=np.zeros(16);flipped[0]=1.0
    after=selected_plan(shifted,flipped)
    state_driven=first_action_switch(int(plan['sequence'][1]),after['first_action'])
    if int(shifted[plan['index'],0])!=int(plan['sequence'][1]):raise ValueError('same-set suffix is not the original next action')
    visited_live=offline_archived_live('artifacts/visited_commitment.json','visited_commitment_development')
    q_live=offline_archived_live('artifacts/action_conditioned_q_completed.json','action_conditioned_development')
    report=dict(complete=True,new_environment_steps=0,new_imagined_transitions=0,authorized=False,
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                checkpoints=checks,source_inspection=dict(source_dirty=source['source_dirty'],source_changed=source['source_changed']),
                synthetic=dict(search_noise_example=noise,state_driven_same_set_example=state_driven,
                               suffix_preserves_original_tail=True),
                archived_live={'visited_commitment':visited_live,'action_conditioned_q':q_live},
                proposed_budget=budget(cfg),primary='gain_commit_fresh',practical_margin=1.0,
                development_outcomes_used_for_tuning=False,score_correction_closed=True,
                confirmation_used=False)
    save(FEASIBILITY,report);return report


def _score(planner,obs,sequences):
    return np.asarray(planner._score_batch(np.asarray(obs,dtype=np.float32),np.asarray(sequences,dtype=np.int64)),dtype=np.float64)


def _rollout(env,actions):
    rewards=[]
    obs=np.asarray(env.unwrapped._get_obs(),dtype=np.float32)
    for a in actions:
        nxt,r,term,trunc,_=env.step(int(a))
        if term or trunc:raise ValueError('short consistency trajectory')
        rewards.append(float(r));obs=np.asarray(nxt,dtype=np.float32)
    return rewards,obs


def _step(env,action):
    nxt,r,term,trunc,_=env.step(int(action))
    if term or trunc:raise ValueError('short consistency trajectory')
    return np.asarray(nxt,dtype=np.float32),float(r)


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing receding-consistency overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    from nexus.tasks.spec import make_task_env
    from nexus.tasks.pendulum_family import pendulum_context_train
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
        specs=list(pendulum_context_train())
        for d,t in itertools.product(cfg['decoders'],range(8)):
            models=load_models(d,t,rep,confirmation,parent,seq_stage)
            for model in models.values():meter.instrument_model(model)
            spec=specs[t]
            for v in range(2):
                visitor=str(visitor_student(d,t)) if v==0 else 'zero'
                env=make_task_env(spec);obs,_=env.reset(seed=reset_seed(cfg,d,t));meter.instrument_env(env)
                try:
                    start_state=true_state(env)
                    seq=candidate_sequences(candidate_seed(cfg,d,t,v))
                    planners={name:mpc_for_model(model,seed=candidate_seed(cfg,d,t,v),enforce_time_budget=False) for name,model in models.items()}
                    s0={name:_score(pl,obs,seq).tolist() for name,pl in planners.items()}
                    plan=selected_plan(seq,s0[visitor])
                    noise_seq=candidate_sequences(noise_seed(cfg,d,t,v))
                    noise=selected_plan(noise_seq,_score(planners[visitor],obs,noise_seq))
                    before=fingerprints(models)
                    meter.bucket='commit';env.reset(seed=reset_seed(cfg,d,t))
                    commit,_=_rollout(env,plan['sequence'])
                    meter.bucket='recede_same';env.reset(seed=reset_seed(cfg,d,t))
                    obs,r=_step(env,plan['first_action']);same=[r];remaining=shift_suffixes(seq,1);state_switch=None
                    for k in range(15):
                        choice=selected_plan(remaining,_score(planners[visitor],obs,remaining))
                        if k==0:state_switch=first_action_switch(int(plan['sequence'][1]),choice['first_action'])
                        obs,r=_step(env,choice['first_action']);same.append(r)
                        remaining=remaining[:,1:]
                    meter.bucket='recede_fresh';env.reset(seed=reset_seed(cfg,d,t))
                    obs,r=_step(env,plan['first_action']);fresh=[r];fresh_switch=None
                    for i,seed in enumerate(recede_seeds(cfg,d,t,v)):
                        planners[visitor].reset_episode(seed);action,info=planners[visitor].act(obs)
                        if info['n_scored']!=16:raise ValueError('fresh receding candidate budget changed')
                        if i==0:fresh_switch=first_action_switch(int(plan['sequence'][1]),int(action))
                        obs,r=_step(env,action);fresh.append(r)
                    if visitor=='zero':
                        zero=list(fresh)
                    else:
                        meter.bucket='common_zero';env.reset(seed=reset_seed(cfg,d,t));zero_planner=planners['zero']
                        obs,r=_step(env,plan['first_action']);zero=[r]
                        for seed in recede_seeds(cfg,d,t,v):
                            zero_planner.reset_episode(seed);action,info=zero_planner.act(obs)
                            if info['n_scored']!=16:raise ValueError('common-zero candidate budget changed')
                            obs,r=_step(env,action);zero.append(r)
                    after=fingerprints(models)
                    if before!=after:raise RuntimeError('frozen model/context drift')
                    metrics=dict(commit=float(math.fsum(commit)),recede_fresh=float(math.fsum(fresh)),
                                 recede_same=float(math.fsum(same)),common_zero=float(math.fsum(zero)))
                    metrics.update(gain_commit_fresh=metrics['commit']-metrics['recede_fresh'],
                                   gain_commit_same=metrics['commit']-metrics['recede_same'],
                                   gain_fresh_same=metrics['recede_fresh']-metrics['recede_same'],
                                   gain_fresh_zero=metrics['recede_fresh']-metrics['common_zero'],
                                   search_noise_switch=first_action_switch(plan['first_action'],noise['first_action']),
                                   state_driven_switch=float(state_switch),fresh_plan_switch=float(fresh_switch))
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
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid receding-consistency evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'])
