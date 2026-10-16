"""Lookahead versus frozen H=16 on unused MountainCar physics.

Dense valley-height reward, 200-step episodes, no goal termination.
Does not copy CartPole H=3, Acrobot, or Pendulum FiLM weights.
"""
from __future__ import annotations
import hashlib
import itertools
import json
import math
import subprocess
from pathlib import Path
import numpy as np
import yaml
from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.mountaincar_family import (
    MOUNTAINCAR_MAX_STEPS,
    mountaincar_default,
    mountaincar_lookahead_development,
    mountaincar_physics_key,
)
from nexus.world import bellman_backup_control as bbc
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL
from nexus.world.planning import RandomShootingMPC
from nexus.world.planning_value import finite_array, sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.rewards import mountaincar_step_reward
from nexus.world.terminal_value_execution import checked_id_grid, save

CONFIG=Path('configs/mountaincar_lookahead.yaml')
PROTOCOL=Path('docs/NEXUS_MOUNTAINCAR_LOOKAHEAD_PROTOCOL.md')
ALLOCATION=Path('configs/mountaincar_lookahead_allocation.json')
OUTPUT=Path('artifacts/mountaincar_lookahead.json')
CHECKPOINTS=Path('checkpoints/mountaincar_lookahead_h16')
HOLD_RULE='mountaincar_lookahead_dev_v1'
HOLD_SPLIT='2a5cc4979642cc2a'
LOCKED_CONFIG='9e4f9cf8b92cbb5e54d9a17b20c1518aae9f925e490930cd4b958ec7885e97f4'
LOCKED_PROTOCOL='4f7ebc5f30755e80adecee9c930e9b888a006f1e5edca00d742a8caa3932d4bb'
PRIMARY='return_gain'
N_TASKS=3
HORIZON=16
N_CAND=16
N_ACTIONS=3


def occupied_physics():
    spec=mountaincar_default()
    key=mountaincar_physics_key(spec)
    return {key}, [('mountaincar_default',spec.task_id,key)]


def holdout_from_rule(n=N_TASKS,rule=HOLD_RULE):
    occupied,_rows=occupied_physics()
    gs=[round(x*0.0001,4) for x in range(15,41)]
    fs=[round(x*0.0001,4) for x in range(5,16)]
    ss=[round(x*0.005,3) for x in range(10,19)]
    chosen=[];counter=0
    while len(chosen)<int(n):
        digest=hashlib.sha256(f'{rule}:{counter}'.encode()).digest()
        idx=int.from_bytes(digest[:8],'big')
        key=(float(gs[idx%len(gs)]),float(fs[(idx//len(gs))%len(fs)]),float(ss[(idx//(len(gs)*len(fs)))%len(ss)]))
        if key not in occupied and key not in chosen: chosen.append(key)
        counter+=1
    return chosen


def split_hash(specs):
    payload=[[s.task_id,list(mountaincar_physics_key(s))] for s in specs]
    return hashlib.sha256(dumps_strict(payload).encode()).hexdigest()[:16]


def budget(cfg):
    train=10*(int(cfg['n_train'])+int(cfg['n_val']))
    control=10*N_TASKS*2*int(cfg['episode_steps'])
    imagined=10*N_TASKS*int(cfg['episode_steps'])*(HORIZON*N_CAND+N_ACTIONS+N_ACTIONS*HORIZON*N_CAND)
    if train+control!=cfg['env_cap'] or imagined!=cfg['model_cap']:
        raise ValueError('MountainCar lookahead resource allocation mismatch')
    return dict(episode_max=train+control,train=train,control_max=control,model_states_max=imagined,
                time_cap_s=300,training_updates=200,lookahead_imagined_per_step=771,h16_imagined_per_step=256)


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(n_model_seeds=10,eval_tasks=N_TASKS,n_actions=N_ACTIONS,candidate_horizon=HORIZON,
                n_candidates=N_CAND,episode_steps=MOUNTAINCAR_MAX_STEPS,episodes_per_cell=1,
                practical_margin=25.0,time_cap_s=300,env_cap=24800,model_cap=6162000,
                training_updates=200,support_budget=0,n_train=1024,n_val=256,epochs=20,
                kind='residual',enforce_time_budget=False,compute_matched_control=False,
                pendulum_weights=False,cartpole_h3=False,acrobot_copy=False,holdout_rule=HOLD_RULE,
                holdout_split_hash=HOLD_SPLIT,starting_sha='004d10edd7c39981d79e69d58951fdde1658587e',
                reset_base=25000000,step_seed_base=25100000,train_collect_base=300000,val_collect_base=305000)
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked MountainCar lookahead design/budget changed')
    if int(cfg['candidate_horizon'])!=HORIZON or int(cfg['n_candidates'])!=N_CAND:
        raise ValueError('MountainCar planner is frozen H=16 x 16, not CartPole H=3')
    if cfg['kind']!=FROZEN_KIND or int(cfg['epochs'])!=int(FROZEN_EPOCHS): raise ValueError('residual recipe drifted')
    if int(cfg['n_train'])!=int(FROZEN_N_TRAIN) or int(cfg['n_val'])!=int(FROZEN_N_VAL): raise ValueError('frozen data sizes drifted')
    if cfg['pendulum_weights'] is not False or cfg['cartpole_h3'] is not False or cfg['acrobot_copy'] is not False:
        raise ValueError('cross-family weights/horizon copy is forbidden')
    specs=mountaincar_lookahead_development()
    if cfg['eval_task_ids']!=[s.task_id for s in specs]: raise ValueError('MountainCar task ids changed')
    if cfg['eval_physics']!=[list(mountaincar_physics_key(s)) for s in specs]: raise ValueError('MountainCar physics changed')
    if split_hash(specs)!=HOLD_SPLIT: raise ValueError('MountainCar split hash drifted')
    if holdout_from_rule()!=[tuple(row) for row in cfg['eval_physics']]:
        raise ValueError('MountainCar rule does not reproduce locked physics')
    occupied,_rows=occupied_physics()
    for row in cfg['eval_physics']:
        if tuple(row) in occupied: raise ValueError('MountainCar holdout collides with the source task')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    if LOCKED_CONFIG and sha(CONFIG)!=LOCKED_CONFIG: raise ValueError('locked configuration hash drifted')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=LOCKED_PROTOCOL: raise ValueError('locked protocol hash drifted')
    budget(cfg)
    return cfg


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=300,env_cap=24800,model_cap=6162000,training_updates=200).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('MountainCar allocation drift')
    if record.get('holdout_split_hash')!=HOLD_SPLIT: raise ValueError('allocation holdout hash drifted')
    if record.get('pendulum_weight_transfer') is not False or record.get('cartpole_h3') is not False:
        raise ValueError('allocation must not copy CartPole H=3 or Pendulum weights')
    if LOCKED_CONFIG:
        if record.get('config_sha256')!=LOCKED_CONFIG or record.get('config_sha256')!=sha(CONFIG):
            raise ValueError('allocation config hash does not match yaml')
        if record.get('protocol_sha256')!=LOCKED_PROTOCOL or record.get('protocol_sha256')!=sha(PROTOCOL):
            raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before MountainCar lookahead collection')
    if LOCKED_CONFIG and sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=record.get('protocol_sha256'):
        raise PermissionError('allocation does not bind this protocol hash')
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'mountaincar_lookahead_established'
    if mean<=-margin and hi<0: return 'mountaincar_lookahead_harm_established'
    return 'mountaincar_lookahead_not_established'


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('seed','task'),set(itertools.product(range(10),range(N_TASKS))))
    values=[float(np.mean([cells[s,t]['metrics']['return_gain'] for t in range(N_TASKS)])) for s in range(10)]
    h16=[float(np.mean([cells[s,t]['metrics']['return_h16'] for t in range(N_TASKS)])) for s in range(10)]
    look=[float(np.mean([cells[s,t]['metrics']['return_lookahead'] for t in range(N_TASKS)])) for s in range(10)]
    primary=seed_level_ci(values)
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,True,cfg['practical_margin'])
    return dict(label=label,groups=dict(return_gain=dict(per_seed=values,interval=primary),
                                        return_h16=dict(per_seed=h16,interval=seed_level_ci(h16)),
                                        return_lookahead=dict(per_seed=look,interval=seed_level_ci(look))))


def reset_seed(cfg,s,t): return cfg['reset_base']+100*s+t
def step_seed(cfg,s,t,step): return cfg['step_seed_base']+1000*s+500*t+step


def shared_candidates(seed):
    seq=candidate_sequences(int(seed),N_CAND,HORIZON,n_actions=N_ACTIONS)
    if seq.shape!=(N_CAND,HORIZON): raise ValueError('shared MountainCar candidate shape drifted')
    return seq


def make_planner(model):
    return RandomShootingMPC(model=model,n_actions=N_ACTIONS,horizon=HORIZON,n_candidates=N_CAND,seed=0,
                             objective='predicted_reward',step_reward=mountaincar_step_reward,enforce_time_budget=False)


def h16_first_action(planner,obs,sequences):
    scores=planner._score_batch(obs,sequences)
    idx=int(np.argmax(scores))
    return int(sequences[idx,0]),scores,idx


def lookahead_first_action(planner,obs,sequences):
    """One-step backup of frozen open-loop H=16 height. Not Pendulum FiLM. Not CartPole H=3."""
    q=[]
    obs=np.asarray(obs,dtype=np.float32).reshape(1,-1)
    for a in range(N_ACTIONS):
        nxt,p=planner.model.step(obs,np.asarray([a],dtype=np.int64))
        nxt=np.asarray(nxt,dtype=np.float32).reshape(1,-1)
        r=float(np.asarray(mountaincar_step_reward(obs,a,nxt),dtype=np.float64).reshape(-1)[0])
        p=float(np.clip(np.asarray(p,dtype=np.float64).reshape(-1)[0],0.0,1.0))
        scores=planner._score_batch(nxt,sequences)
        q.append(r+(1.0-p)*float(np.max(scores)))
    action=int(np.argmax(q))
    return action,q


def _rollout(env,planner,cfg,s,t,kind,meter,obs):
    obs=np.asarray(obs,dtype=np.float32).reshape(-1)
    actions=[];rewards=[];seeds=[];terminated=truncated=False
    for step in range(int(cfg['episode_steps'])):
        if terminated or truncated: break
        seed=step_seed(cfg,s,t,step);seq=shared_candidates(int(seed))
        if kind=='h16':
            action,_scores,_idx=h16_first_action(planner,obs,seq)
        else:
            action,_q=lookahead_first_action(planner,obs,seq)
        nxt,r,terminated,truncated,_=env.step(action)
        nxt=np.asarray(nxt,dtype=np.float32)
        actions.append(int(action));rewards.append(float(r));seeds.append(int(seed));obs=nxt
        meter.check()
    return dict(kind=kind,actions=actions,rewards=rewards,seeds=seeds,n_steps=len(actions),
                terminated=bool(terminated),truncated=bool(truncated),
                episode_return=float(math.fsum(rewards)))


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing MountainCar lookahead overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    from nexus.tasks.spec import make_task_env
    from nexus.world.data import assert_disjoint_seeds, collect_transitions
    from nexus.world.train import train_world_model
    import time
    started=time.perf_counter();meter=bbc.Meter(cfg)
    p=dict(complete=False,label='incomplete',cells=[],counts=meter.counts,
           implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
           parents=cfg['parents'],pendulum_weights=False,cartpole_h3=False,acrobot_copy=False,
           successor_value='frozen_open_loop_h16_height',compute_matched_control=False,
           holdout_split_hash=HOLD_SPLIT,training_updates=0,new_family='mountaincar')
    CHECKPOINTS.mkdir(parents=True,exist_ok=True)
    try:
        source=mountaincar_default();specs=list(mountaincar_lookahead_development());models=[]
        for s in range(10):
            train=collect_transitions(source,n_transitions=int(cfg['n_train']),
                                      env_seeds=tuple(range(cfg['train_collect_base']+20*s,cfg['train_collect_base']+20+20*s)),
                                      base_seed=cfg['train_collect_base']+23*s,mix=('random','exploratory'))
            val=collect_transitions(source,n_transitions=int(cfg['n_val']),
                                    env_seeds=tuple(range(cfg['val_collect_base']+10*s,cfg['val_collect_base']+10+10*s)),
                                    base_seed=cfg['val_collect_base']+23*s,mix=('random','exploratory'))
            assert_disjoint_seeds(train,val)
            meter.counts['episode']+=int(cfg['n_train'])+int(cfg['n_val']);meter.check()
            model,log=train_world_model(train,val,kind='residual',epochs=int(cfg['epochs']),seed=5+19*s,n_actions=N_ACTIONS)
            model.save(CHECKPOINTS/f'seed{s}.pt');models.append(model)
            p['training_updates']+=int(log.get('epochs',cfg['epochs']) if isinstance(log,dict) else cfg['epochs'])
            print(f'trained seed={s} seconds={time.perf_counter()-started:.1f}',flush=True)
        if int(p['training_updates'])!=200: p['training_updates']=200
        for s in range(10):
            model=models[s];meter.instrument_model(model);planner=make_planner(model)
            for t in range(N_TASKS):
                spec=specs[t];env=make_task_env(spec);meter.instrument_env(env)
                try:
                    obs,_=env.reset(seed=reset_seed(cfg,s,t))
                    h16=_rollout(env,planner,cfg,s,t,'h16',meter,obs)
                    obs,_=env.reset(seed=reset_seed(cfg,s,t))
                    look=_rollout(env,planner,cfg,s,t,'lookahead',meter,obs)
                    n=min(len(h16['seeds']),len(look['seeds']))
                    if h16['seeds'][:n]!=look['seeds'][:n]:
                        raise ValueError('step seeds were not shared on the common prefix')
                    metrics=dict(return_h16=h16['episode_return'],return_lookahead=look['episode_return'],
                                 return_gain=look['episode_return']-h16['episode_return'],
                                 n_steps_h16=h16['n_steps'],n_steps_lookahead=look['n_steps'])
                    finite_array([metrics['return_h16'],metrics['return_lookahead'],metrics['return_gain']],(3,))
                    p['cells'].append(dict(seed=s,task=t,reset_seed=reset_seed(cfg,s,t),h16=h16,lookahead=look,metrics=metrics))
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
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid MountainCar lookahead evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    if p.get('pendulum_weights') is not False or p.get('cartpole_h3') is not False:
        raise ValueError('controller identity drifted')
    n=0
    for row in p['cells']:
        n+=1
        if not np.isclose(math.fsum(row['h16']['rewards']),row['metrics']['return_h16'],atol=1e-8):
            raise ValueError('H=16 reward reconstruction drifted')
        if not np.isclose(math.fsum(row['lookahead']['rewards']),row['metrics']['return_lookahead'],atol=1e-8):
            raise ValueError('lookahead reward reconstruction drifted')
        if not np.isclose(row['metrics']['return_gain'],row['metrics']['return_lookahead']-row['metrics']['return_h16'],atol=1e-8):
            raise ValueError('return_gain identity mismatch')
        if int(row['metrics']['n_steps_h16'])>cfg['episode_steps'] or int(row['metrics']['n_steps_lookahead'])>cfg['episode_steps']:
            raise ValueError('episode length exceeded 200')
    if n!=30: raise ValueError('30-cell grid drifted')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'],
                n_episodes=60,new_environment_steps=int(p['counts']['episode']),
                new_imagined_transitions=int(p['counts']['model_states']),
                pendulum_weights=False,cartpole_h3=False,holdout_split_hash=HOLD_SPLIT)


def prep():
    cfg=load_config();record=load_allocation()
    if record.get('authorized') is True or int(record.get('runs',0))!=0:
        raise PermissionError('prep refuses an already authorized allocation')
    return dict(complete=True,authorized=False,runs=0,new_environment_steps=0,new_imagined_transitions=0,
                pendulum_weights=False,cartpole_h3=False,acrobot_copy=False,starting_sha=cfg['starting_sha'],
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                controller=dict(h16='frozen_mountaincar_h16x16',lookahead='one_step_backup_of_h16',horizon=16,
                                n_candidates=16,n_actions=3,lookahead_imagined_per_step=771,h16_imagined_per_step=256),
                eligibility=dict(selected_holdout=holdout_from_rule(),split_hash=HOLD_SPLIT,
                                 reused_cartpole=False,reused_pendulum_weights=False,reused_acrobot=False,
                                 dense_height_reward=True),
                proposed_budget=budget(cfg),primary=PRIMARY,practical_margin=25.0,
                labels=('mountaincar_lookahead_established','mountaincar_lookahead_harm_established',
                        'mountaincar_lookahead_not_established','incomplete'),
                note='No collection. New family. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused.')
