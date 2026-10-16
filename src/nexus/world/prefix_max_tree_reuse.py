"""Prefix-max tree reuse versus frozen H=16 on MountainCar development models.

V(s'|a) is max remaining open-loop height at cached t=1 nodes whose first
action was a. No fitted critic. Confirmation unused. Collection unauthorized
until a bound one-run allocation exists.
"""
from __future__ import annotations
import itertools
import json
import math
import subprocess
from pathlib import Path
import numpy as np
import yaml
from nexus.cl.metrics import seed_level_ci
from nexus.tasks.mountaincar_family import (
    MOUNTAINCAR_MAX_STEPS,
    mountaincar_lookahead_confirmation,
    mountaincar_lookahead_development,
    mountaincar_physics_key,
)
from nexus.world import bellman_backup_control as bbc
from nexus.world import mountaincar_lookahead as base
from nexus.world import mountaincar_lookahead_confirm as confirm
from nexus.world import tree_reuse_lookahead as tree
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL
from nexus.world.planning_value import finite_array, sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.rewards import mountaincar_step_reward
from nexus.world.terminal_value_execution import checked_id_grid, save

CONFIG=Path('configs/prefix_max_tree_reuse.yaml')
PROTOCOL=Path('docs/NEXUS_PREFIX_MAX_TREE_REUSE_PROTOCOL.md')
ALLOCATION=Path('configs/prefix_max_tree_reuse_allocation.json')
OUTPUT=Path('artifacts/prefix_max_tree_reuse.json')
CHECKPOINTS=Path('checkpoints/mountaincar_lookahead_h16')
HOLD_RULE='mountaincar_lookahead_dev_v1'
HOLD_SPLIT='2a5cc4979642cc2a'
LOCKED_CONFIG='1d1a39c11076644fcc590fa378e0d19c3bff8ec68f4f92e078de894609daf440'
LOCKED_PROTOCOL='7f7a3ca13b267d9873fa0d2339db6cd82e5c6f313239bc9835b4e057a5b6a634'
PRIMARY='return_gain'
N_TASKS=3
HORIZON=16
N_CAND=16
N_ACTIONS=3
H16_IMAGINED=N_CAND*HORIZON
PREFIX_MAX_IMAGINED=H16_IMAGINED+N_ACTIONS


def budget(cfg):
    control=10*N_TASKS*2*int(cfg['episode_steps'])
    imagined=10*N_TASKS*int(cfg['episode_steps'])*(H16_IMAGINED+PREFIX_MAX_IMAGINED)
    if int(cfg['training_updates'])!=0: raise ValueError('prefix-max protocol does not retrain')
    if control!=cfg['env_cap'] or imagined!=cfg['model_cap']:
        raise ValueError('prefix-max resource allocation mismatch')
    if imagined!=3090000: raise ValueError('locked imagined budget drifted')
    return dict(episode_max=control,train=0,control_max=control,model_states_max=imagined,
                time_cap_s=180,training_updates=0,prefix_max_imagined_per_step=PREFIX_MAX_IMAGINED,
                h16_imagined_per_step=H16_IMAGINED)


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(n_model_seeds=10,eval_tasks=N_TASKS,n_actions=N_ACTIONS,candidate_horizon=HORIZON,
                n_candidates=N_CAND,episode_steps=MOUNTAINCAR_MAX_STEPS,episodes_per_cell=1,
                practical_margin=25.0,time_cap_s=180,env_cap=12000,model_cap=3090000,
                training_updates=0,support_budget=0,n_train=1024,n_val=256,epochs=20,kind='residual',
                enforce_time_budget=False,prefix_max_control=True,reuse_development_checkpoints=True,
                pendulum_weights=False,cartpole_h3=False,acrobot_copy=False,
                mountaincar_continuous=False,fitted_critic=False,lookahead_arm=False,
                retune_from_confirmation=False,holdout_rule=HOLD_RULE,holdout_split_hash=HOLD_SPLIT,
                starting_sha='f3898f6c95e37ea3f91101e288b71056edae4603',
                reset_base=30000000,step_seed_base=30100000,
                checkpoint_dir='checkpoints/mountaincar_lookahead_h16',
                closed_confirmation_split_hash='bf4b4412f4f683dd')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:
            raise ValueError('locked prefix-max design/budget changed')
    if cfg['kind']!=FROZEN_KIND or int(cfg['epochs'])!=int(FROZEN_EPOCHS): raise ValueError('residual recipe drifted')
    if int(cfg['n_train'])!=int(FROZEN_N_TRAIN) or int(cfg['n_val'])!=int(FROZEN_N_VAL): raise ValueError('frozen data sizes drifted')
    if cfg['pendulum_weights'] is not False or cfg['cartpole_h3'] is not False or cfg['acrobot_copy'] is not False:
        raise ValueError('cross-family weights/horizon copy is forbidden')
    if cfg['mountaincar_continuous'] is not False: raise ValueError('MountainCarContinuous is not this experiment')
    if cfg['fitted_critic'] is not False: raise ValueError('prefix-max must not fit a critic')
    if cfg['lookahead_arm'] is not False: raise ValueError('771 lookahead arm is not this experiment')
    if cfg['retune_from_confirmation'] is not False:
        raise ValueError('confirmation outcomes must not retune this controller')
    specs=mountaincar_lookahead_development()
    if cfg['eval_task_ids']!=[s.task_id for s in specs]: raise ValueError('development task ids changed')
    if cfg['eval_physics']!=[list(mountaincar_physics_key(s)) for s in specs]: raise ValueError('development physics changed')
    if base.split_hash(specs)!=HOLD_SPLIT: raise ValueError('development split hash drifted')
    closed_confirm={mountaincar_physics_key(s) for s in mountaincar_lookahead_confirmation()}
    if any(tuple(row) in closed_confirm for row in cfg['eval_physics']):
        raise ValueError('prefix-max eval collides with confirmation physics')
    if confirm.HOLD_SPLIT!=cfg['closed_confirmation_split_hash']:
        raise ValueError('closed confirmation hash drifted')
    if len(cfg['checkpoint_sha256'])!=10: raise ValueError('need ten frozen development checkpoints')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    if LOCKED_CONFIG and sha(CONFIG)!=LOCKED_CONFIG: raise ValueError('locked configuration hash drifted')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=LOCKED_PROTOCOL: raise ValueError('locked protocol hash drifted')
    budget(cfg)
    return cfg


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=180,env_cap=12000,model_cap=3090000,training_updates=0).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:
            raise ValueError('prefix-max allocation drift')
    if record.get('holdout_split_hash')!=HOLD_SPLIT: raise ValueError('allocation holdout hash drifted')
    if record.get('retune_from_confirmation') is not False:
        raise ValueError('allocation must not retune from confirmation')
    if record.get('reuse_development_checkpoints') is not True:
        raise ValueError('allocation must reuse frozen development checkpoints')
    if record.get('fitted_critic') is not False:
        raise ValueError('allocation must not fit a critic')
    if record.get('lookahead_arm') is not False:
        raise ValueError('allocation must not include the 771 lookahead arm')
    if LOCKED_CONFIG:
        if record.get('config_sha256')!=LOCKED_CONFIG or record.get('config_sha256')!=sha(CONFIG):
            raise ValueError('allocation config hash does not match yaml')
        if record.get('protocol_sha256')!=LOCKED_PROTOCOL or record.get('protocol_sha256')!=sha(PROTOCOL):
            raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before prefix-max collection')
    if LOCKED_CONFIG and sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=record.get('protocol_sha256'):
        raise PermissionError('allocation does not bind this protocol hash')
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'prefix_max_tree_reuse_established'
    if mean<=-margin and hi<0: return 'prefix_max_tree_reuse_harm_established'
    return 'prefix_max_tree_reuse_not_established'


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('seed','task'),set(itertools.product(range(10),range(N_TASKS))))
    values=[float(np.mean([cells[s,t]['metrics']['return_gain'] for t in range(N_TASKS)])) for s in range(10)]
    h16=[float(np.mean([cells[s,t]['metrics']['return_h16'] for t in range(N_TASKS)])) for s in range(10)]
    reuse=[float(np.mean([cells[s,t]['metrics']['return_prefix_max'] for t in range(N_TASKS)])) for s in range(10)]
    hits=[float(np.mean([cells[s,t]['metrics']['prefix_hit_rate'] for t in range(N_TASKS)])) for s in range(10)]
    primary=seed_level_ci(values)
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,True,cfg['practical_margin'])
    return dict(label=label,groups=dict(return_gain=dict(per_seed=values,interval=primary),
                                        return_h16=dict(per_seed=h16,interval=seed_level_ci(h16)),
                                        return_prefix_max=dict(per_seed=reuse,interval=seed_level_ci(reuse)),
                                        prefix_hit_rate=dict(per_seed=hits,interval=seed_level_ci(hits))))


def reset_seed(cfg,s,t): return cfg['reset_base']+100*s+t
def step_seed(cfg,s,t,step): return cfg['step_seed_base']+1000*s+500*t+step


def seed_groups(cfg):
    resets={reset_seed(cfg,s,t) for s in range(10) for t in range(N_TASKS)}
    steps={step_seed(cfg,s,t,step) for s in range(10) for t in range(N_TASKS) for step in range(int(cfg['episode_steps']))}
    return resets,steps


def shared_candidates(seed):
    seq=candidate_sequences(int(seed),N_CAND,HORIZON,n_actions=N_ACTIONS)
    if seq.shape!=(N_CAND,HORIZON): raise ValueError('shared prefix-max candidate shape drifted')
    return seq


def prefix_values(sequences,cache_values):
    seqs=np.asarray(sequences)
    n,h=seqs.shape
    if h<2: raise ValueError('prefix-max requires horizon at least 2')
    remaining=np.asarray(cache_values[:n*h],dtype=np.float64).reshape(n,h)
    return seqs[:,0].astype(np.int64),remaining[:,1]


def prefix_max_value(first_actions,remaining_t1,t1_states,action,query):
    mask=first_actions==int(action)
    if np.any(mask):
        return float(np.max(remaining_t1[mask])),True,int(mask.sum())
    value,_dist,_idx=tree.nearest_remaining(t1_states,remaining_t1,query)
    return float(value),False,0


def prefix_max_first_action(planner,obs,sequences):
    """One-step backup of max remaining among cached tails that started with a."""
    obs=np.asarray(obs,dtype=np.float32).reshape(-1)
    seqs=np.asarray(sequences)
    n,h=seqs.shape
    _scores,cache_states,cache_values=tree.unroll_open_loop_tree(planner,obs,seqs)
    first,remaining_t1=prefix_values(seqs,cache_values)
    t1_states=np.asarray(cache_states[:n*h],dtype=np.float32).reshape(n,h,-1)[:,1]
    q=[];hits=[]
    cur=obs.reshape(1,-1)
    for a in range(N_ACTIONS):
        nxt,p=planner.model.step(cur,np.asarray([a],dtype=np.int64))
        nxt=np.asarray(nxt,dtype=np.float32).reshape(1,-1)
        r=float(np.asarray(mountaincar_step_reward(cur,a,nxt),dtype=np.float64).reshape(-1)[0])
        p=float(np.clip(np.asarray(p,dtype=np.float64).reshape(-1)[0],0.0,1.0))
        value,hit,_n=prefix_max_value(first,remaining_t1,t1_states,a,nxt)
        q.append(r+(1.0-p)*value);hits.append(bool(hit))
    action=int(np.argmax(q))
    return action,q,float(np.mean(hits))


def _rollout(env,planner,cfg,s,t,kind,meter,obs):
    obs=np.asarray(obs,dtype=np.float32).reshape(-1)
    actions=[];rewards=[];seeds=[];hits=[];terminated=truncated=False
    for step in range(int(cfg['episode_steps'])):
        if terminated or truncated: break
        seed=step_seed(cfg,s,t,step);seq=shared_candidates(int(seed))
        if kind=='h16':
            action,_scores,_idx=base.h16_first_action(planner,obs,seq)
        else:
            action,_q,hit=prefix_max_first_action(planner,obs,seq);hits.append(hit)
        nxt,r,terminated,truncated,_=env.step(action)
        nxt=np.asarray(nxt,dtype=np.float32)
        actions.append(int(action));rewards.append(float(r));seeds.append(int(seed));obs=nxt
        meter.check()
    return dict(kind=kind,actions=actions,rewards=rewards,seeds=seeds,n_steps=len(actions),
                prefix_hit_rate=float(np.mean(hits)) if hits else None,
                terminated=bool(terminated),truncated=bool(truncated),
                episode_return=float(math.fsum(rewards)))


def load_frozen_models(cfg):
    models=[]
    for s,digest in enumerate(cfg['checkpoint_sha256']):
        path=CHECKPOINTS/f'seed{s}.pt'
        if sha(path)!=digest: raise ValueError(f'frozen development checkpoint seed{s} changed')
        models.append(WorldModel.load(path))
    return models


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing prefix-max overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():
        raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    from nexus.tasks.spec import make_task_env
    import time
    started=time.perf_counter();meter=bbc.Meter(cfg)
    p=dict(complete=False,label='incomplete',cells=[],counts=meter.counts,
           implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
           parents=cfg['parents'],pendulum_weights=False,cartpole_h3=False,acrobot_copy=False,
           mountaincar_continuous=False,fitted_critic=False,lookahead_arm=False,
           successor_value='prefix_max_cached_t1_remaining',prefix_max_control=True,
           reuse_development_checkpoints=True,retune_from_confirmation=False,
           holdout_split_hash=HOLD_SPLIT,training_updates=0,new_family='mountaincar')
    try:
        specs=list(mountaincar_lookahead_development());models=load_frozen_models(cfg)
        for s in range(10):
            model=models[s];meter.instrument_model(model);planner=base.make_planner(model)
            for t in range(N_TASKS):
                spec=specs[t];env=make_task_env(spec);meter.instrument_env(env)
                try:
                    obs,_=env.reset(seed=reset_seed(cfg,s,t))
                    h16=_rollout(env,planner,cfg,s,t,'h16',meter,obs)
                    obs,_=env.reset(seed=reset_seed(cfg,s,t))
                    reuse=_rollout(env,planner,cfg,s,t,'prefix_max',meter,obs)
                    n=min(len(h16['seeds']),len(reuse['seeds']))
                    if h16['seeds'][:n]!=reuse['seeds'][:n]:
                        raise ValueError('step seeds were not shared on the common prefix')
                    metrics=dict(return_h16=h16['episode_return'],return_prefix_max=reuse['episode_return'],
                                 return_gain=reuse['episode_return']-h16['episode_return'],
                                 n_steps_h16=h16['n_steps'],n_steps_prefix_max=reuse['n_steps'],
                                 prefix_hit_rate=reuse['prefix_hit_rate'])
                    finite_array([metrics['return_h16'],metrics['return_prefix_max'],metrics['return_gain']],(3,))
                    p['cells'].append(dict(seed=s,task=t,reset_seed=reset_seed(cfg,s,t),
                                           h16=h16,prefix_max=reuse,metrics=metrics))
                finally:
                    env.close()
                print(f'seed={s} task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['counts']=dict(meter.counts)
        if int(p['counts']['episode'])>cfg['env_cap']:raise ValueError('env step count exceeded cap')
        if int(p['counts']['model_states'])>cfg['model_cap']:raise ValueError('imagined count exceeded cap')
        summary=summarize(p['cells'],cfg);p.update(summary);meter.check()
        p['complete']=len(p['cells'])==30
        p['n_episodes']=60
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
        p['complete']=False;p['label']='incomplete'
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def audit_results():
    cfg=load_config();p=json.loads(OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid prefix-max evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    if p.get('fitted_critic') is not False: raise ValueError('fitted critic flag drifted')
    if p.get('lookahead_arm') is not False: raise ValueError('lookahead arm flag drifted')
    if p.get('retune_from_confirmation') is not False: raise ValueError('confirmation retune flag drifted')
    n=0
    for row in p['cells']:
        n+=1
        if not np.isclose(math.fsum(row['h16']['rewards']),row['metrics']['return_h16'],atol=1e-8):
            raise ValueError('H=16 reward reconstruction drifted')
        if not np.isclose(math.fsum(row['prefix_max']['rewards']),row['metrics']['return_prefix_max'],atol=1e-8):
            raise ValueError('prefix-max reward reconstruction drifted')
        if not np.isclose(row['metrics']['return_gain'],row['metrics']['return_prefix_max']-row['metrics']['return_h16'],atol=1e-8):
            raise ValueError('return_gain identity mismatch')
        if int(row['metrics']['n_steps_h16'])>cfg['episode_steps'] or int(row['metrics']['n_steps_prefix_max'])>cfg['episode_steps']:
            raise ValueError('episode length exceeded 200')
    if n!=30: raise ValueError('30-cell grid drifted')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'],
                n_episodes=60,new_environment_steps=int(p['counts']['episode']),
                new_imagined_transitions=int(p['counts']['model_states']),
                pendulum_weights=False,cartpole_h3=False,fitted_critic=False,lookahead_arm=False,
                retune_from_confirmation=False,holdout_split_hash=HOLD_SPLIT)


def prep():
    cfg=load_config();record=load_allocation()
    if record.get('authorized') is True or int(record.get('runs',0))!=0:
        raise PermissionError('prep refuses an already authorized allocation')
    ours=set().union(*seed_groups(cfg))
    if min(ours)<30000000: raise ValueError('prefix-max seeds drifted below 30000000')
    load_frozen_models(cfg)
    return dict(complete=True,authorized=False,runs=0,new_environment_steps=0,new_imagined_transitions=0,
                pendulum_weights=False,cartpole_h3=False,fitted_critic=False,lookahead_arm=False,
                confirmation_outcomes_read=False,starting_sha=cfg['starting_sha'],
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                controller=dict(h16='frozen_mountaincar_h16x16',prefix_max='max_cached_t1_remaining_matching_first_action',
                                horizon=16,n_candidates=16,n_actions=3,
                                h16_imagined_per_step=H16_IMAGINED,prefix_max_imagined_per_step=PREFIX_MAX_IMAGINED),
                eligibility=dict(selected_holdout=base.holdout_from_rule(),split_hash=HOLD_SPLIT,
                                 reused_confirmation_physics=False,reused_development_episode_seeds=False,
                                 reused_tree_reuse_seeds=False,reused_cartpole=False,reused_pendulum_weights=False,
                                 dense_height_reward=True),
                proposed_budget=budget(cfg),primary=PRIMARY,practical_margin=25.0,
                labels=('prefix_max_tree_reuse_established','prefix_max_tree_reuse_harm_established',
                        'prefix_max_tree_reuse_not_established','incomplete'))
