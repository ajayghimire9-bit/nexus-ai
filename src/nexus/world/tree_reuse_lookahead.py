"""Tree-reuse lookahead versus frozen H=16 on MountainCar development models.

One H=16 tree from s is cached; successor value is nearest remaining open-loop
height. No fitted critic. Confirmation physics unused. Collection unauthorized.
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
from nexus.world import lookahead_generalization_synthesis as synth
from nexus.world import mountaincar_lookahead as base
from nexus.world import mountaincar_lookahead_confirm as confirm
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL
from nexus.world.planning_value import finite_array, sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.rewards import mountaincar_step_reward
from nexus.world.terminal_value_execution import checked_id_grid, save

CONFIG=Path('configs/tree_reuse_lookahead.yaml')
PROTOCOL=Path('docs/NEXUS_TREE_REUSE_LOOKAHEAD_PROTOCOL.md')
ALLOCATION=Path('configs/tree_reuse_lookahead_allocation.json')
OUTPUT=Path('artifacts/tree_reuse_lookahead.json')
CHECKPOINTS=Path('checkpoints/mountaincar_lookahead_h16')
HOLD_RULE='mountaincar_lookahead_dev_v1'
HOLD_SPLIT='2a5cc4979642cc2a'
LOCKED_CONFIG='5d85db5bbab131f1bcb7f9a51b96aef4254753e14325713be34e5af5afc40451'
LOCKED_PROTOCOL='fdaf615cef38209afcaf3a199c8094a41df2ad798a8920ffd957142d5c0b5500'
PRIMARY='return_gain'
N_TASKS=3
HORIZON=16
N_CAND=16
N_ACTIONS=3
H16_IMAGINED=N_CAND*HORIZON
TREE_REUSE_IMAGINED=H16_IMAGINED+N_ACTIONS
LOOKAHEAD_IMAGINED=N_ACTIONS+N_ACTIONS*HORIZON*N_CAND


def budget(cfg):
    control=10*N_TASKS*3*int(cfg['episode_steps'])
    imagined=10*N_TASKS*int(cfg['episode_steps'])*(H16_IMAGINED+TREE_REUSE_IMAGINED+LOOKAHEAD_IMAGINED)
    if int(cfg['training_updates'])!=0: raise ValueError('tree-reuse protocol does not retrain')
    if control!=cfg['env_cap'] or imagined!=cfg['model_cap']:
        raise ValueError('tree-reuse resource allocation mismatch')
    if imagined!=7716000: raise ValueError('locked imagined budget drifted')
    return dict(episode_max=control,train=0,control_max=control,model_states_max=imagined,
                time_cap_s=180,training_updates=0,lookahead_imagined_per_step=LOOKAHEAD_IMAGINED,
                tree_reuse_imagined_per_step=TREE_REUSE_IMAGINED,h16_imagined_per_step=H16_IMAGINED)


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(n_model_seeds=10,eval_tasks=N_TASKS,n_actions=N_ACTIONS,candidate_horizon=HORIZON,
                n_candidates=N_CAND,episode_steps=MOUNTAINCAR_MAX_STEPS,episodes_per_cell=1,
                practical_margin=25.0,time_cap_s=180,env_cap=18000,model_cap=7716000,
                training_updates=0,support_budget=0,n_train=1024,n_val=256,epochs=20,kind='residual',
                enforce_time_budget=False,tree_reuse_control=True,reuse_development_checkpoints=True,
                distance_tau='inf',pendulum_weights=False,cartpole_h3=False,acrobot_copy=False,
                mountaincar_continuous=False,fitted_critic=False,retune_from_confirmation=False,
                holdout_rule=HOLD_RULE,holdout_split_hash=HOLD_SPLIT,
                starting_sha='57cff66fd5f8f0451fc45bcf9771a9d0bcdcf3d2',
                reset_base=29000000,step_seed_base=29100000,
                checkpoint_dir='checkpoints/mountaincar_lookahead_h16',
                closed_confirmation_split_hash='bf4b4412f4f683dd')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:
            raise ValueError('locked tree-reuse design/budget changed')
    if int(cfg['candidate_horizon'])!=HORIZON or int(cfg['n_candidates'])!=N_CAND:
        raise ValueError('H=16 successor is frozen at 16 candidates')
    if cfg['kind']!=FROZEN_KIND or int(cfg['epochs'])!=int(FROZEN_EPOCHS): raise ValueError('residual recipe drifted')
    if int(cfg['n_train'])!=int(FROZEN_N_TRAIN) or int(cfg['n_val'])!=int(FROZEN_N_VAL): raise ValueError('frozen data sizes drifted')
    if cfg['pendulum_weights'] is not False or cfg['cartpole_h3'] is not False or cfg['acrobot_copy'] is not False:
        raise ValueError('cross-family weights/horizon copy is forbidden')
    if cfg['mountaincar_continuous'] is not False: raise ValueError('MountainCarContinuous is not this experiment')
    if cfg['fitted_critic'] is not False: raise ValueError('tree-reuse must not fit a critic')
    if cfg['retune_from_confirmation'] is not False:
        raise ValueError('confirmation outcomes must not retune this controller')
    specs=mountaincar_lookahead_development()
    if cfg['eval_task_ids']!=[s.task_id for s in specs]: raise ValueError('development task ids changed')
    if cfg['eval_physics']!=[list(mountaincar_physics_key(s)) for s in specs]: raise ValueError('development physics changed')
    if base.split_hash(specs)!=HOLD_SPLIT: raise ValueError('development split hash drifted')
    closed_confirm={mountaincar_physics_key(s) for s in mountaincar_lookahead_confirmation()}
    if any(tuple(row) in closed_confirm for row in cfg['eval_physics']):
        raise ValueError('tree-reuse eval collides with confirmation physics')
    if confirm.HOLD_SPLIT!=cfg['closed_confirmation_split_hash']:
        raise ValueError('closed confirmation hash drifted')
    if len(cfg['checkpoint_sha256'])!=10: raise ValueError('need ten frozen development checkpoints')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    if LOCKED_CONFIG and sha(CONFIG)!=LOCKED_CONFIG: raise ValueError('locked configuration hash drifted')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=LOCKED_PROTOCOL: raise ValueError('locked protocol hash drifted')
    if sha(synth.SYNTHESIS)!=synth.LOCKED_SYNTHESIS: raise ValueError('synthesis document drifted')
    budget(cfg)
    return cfg


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=180,env_cap=18000,model_cap=7716000,training_updates=0).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:
            raise ValueError('tree-reuse allocation drift')
    if record.get('holdout_split_hash')!=HOLD_SPLIT: raise ValueError('allocation holdout hash drifted')
    if record.get('retune_from_confirmation') is not False:
        raise ValueError('allocation must not retune from confirmation')
    if record.get('reuse_development_checkpoints') is not True:
        raise ValueError('allocation must reuse frozen development checkpoints')
    if record.get('fitted_critic') is not False:
        raise ValueError('allocation must not fit a critic')
    if LOCKED_CONFIG:
        if record.get('config_sha256')!=LOCKED_CONFIG or record.get('config_sha256')!=sha(CONFIG):
            raise ValueError('allocation config hash does not match yaml')
        if record.get('protocol_sha256')!=LOCKED_PROTOCOL or record.get('protocol_sha256')!=sha(PROTOCOL):
            raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before tree-reuse collection')
    if LOCKED_CONFIG and sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=record.get('protocol_sha256'):
        raise PermissionError('allocation does not bind this protocol hash')
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'tree_reuse_lookahead_established'
    if mean<=-margin and hi<0: return 'tree_reuse_lookahead_harm_established'
    return 'tree_reuse_lookahead_not_established'


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('seed','task'),set(itertools.product(range(10),range(N_TASKS))))
    values=[float(np.mean([cells[s,t]['metrics']['return_gain'] for t in range(N_TASKS)])) for s in range(10)]
    h16=[float(np.mean([cells[s,t]['metrics']['return_h16'] for t in range(N_TASKS)])) for s in range(10)]
    reuse=[float(np.mean([cells[s,t]['metrics']['return_tree_reuse'] for t in range(N_TASKS)])) for s in range(10)]
    look=[float(np.mean([cells[s,t]['metrics']['return_lookahead'] for t in range(N_TASKS)])) for s in range(10)]
    primary=seed_level_ci(values)
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,True,cfg['practical_margin'])
    return dict(label=label,groups=dict(return_gain=dict(per_seed=values,interval=primary),
                                        return_h16=dict(per_seed=h16,interval=seed_level_ci(h16)),
                                        return_tree_reuse=dict(per_seed=reuse,interval=seed_level_ci(reuse)),
                                        return_lookahead=dict(per_seed=look,interval=seed_level_ci(look))))


def reset_seed(cfg,s,t): return cfg['reset_base']+100*s+t
def step_seed(cfg,s,t,step): return cfg['step_seed_base']+1000*s+500*t+step


def seed_groups(cfg):
    resets={reset_seed(cfg,s,t) for s in range(10) for t in range(N_TASKS)}
    steps={step_seed(cfg,s,t,step) for s in range(10) for t in range(N_TASKS) for step in range(int(cfg['episode_steps']))}
    return resets,steps


def shared_candidates(seed):
    seq=candidate_sequences(int(seed),N_CAND,HORIZON,n_actions=N_ACTIONS)
    if seq.shape!=(N_CAND,HORIZON): raise ValueError('shared tree-reuse candidate shape drifted')
    return seq


def _begin(model,n):
    begin=getattr(model,'begin_rollout',None) or getattr(getattr(model,'model',None),'begin_rollout',None)
    if begin is None:
        begin=getattr(getattr(model,'wm',None),'begin_rollout',None)
    if begin is not None:
        begin(n)


def unroll_open_loop_tree(planner,obs,sequences):
    """H=16 tree from obs. Remaining value is survival-weighted open-loop height."""
    seqs=np.asarray(sequences)
    n,h=seqs.shape
    obs=np.asarray(obs,dtype=np.float32).reshape(-1)
    s=np.repeat(obs.reshape(1,-1),n,axis=0)
    alive=np.ones(n,dtype=np.float64)
    rewards=np.zeros((n,h),dtype=np.float64)
    states=np.zeros((n,h+1,obs.shape[0]),dtype=np.float32)
    states[:,0]=s
    model=planner.model
    _begin(model,n)
    reward_fn=planner.step_reward if planner.step_reward is not None else mountaincar_step_reward
    for t in range(h):
        nxt,p=model.step(s,seqs[:,t])
        p=np.clip(np.asarray(p,dtype=np.float64).reshape(n),0.0,1.0)
        r=np.asarray(reward_fn(s,seqs[:,t],nxt),dtype=np.float64).reshape(n)
        rewards[:,t]=alive*r
        alive=alive*(1.0-p)
        s=np.asarray(nxt,dtype=np.float32)
        states[:,t+1]=s
    remaining=np.cumsum(rewards[:,::-1],axis=1)[:,::-1]
    cache_states=np.concatenate([states[:,:h].reshape(n*h,-1),states[:,h]],axis=0)
    cache_values=np.concatenate([remaining.reshape(-1),np.zeros(n,dtype=np.float64)])
    scores=remaining[:,0]
    return scores,cache_states,cache_values


def nearest_remaining(cache_states,cache_values,query):
    q=np.asarray(query,dtype=np.float32).reshape(1,-1)
    delta=cache_states-q
    dist=np.sqrt(np.sum(delta*delta,axis=1))
    idx=int(np.argmin(dist))
    return float(cache_values[idx]),float(dist[idx]),idx


def tree_reuse_first_action(planner,obs,sequences):
    """One-step backup of nearest cached H=16 remaining value. Not a fitted Q."""
    obs=np.asarray(obs,dtype=np.float32).reshape(-1)
    _scores,cache_states,cache_values=unroll_open_loop_tree(planner,obs,sequences)
    q=[];nn=[]
    cur=obs.reshape(1,-1)
    for a in range(N_ACTIONS):
        nxt,p=planner.model.step(cur,np.asarray([a],dtype=np.int64))
        nxt=np.asarray(nxt,dtype=np.float32).reshape(1,-1)
        r=float(np.asarray(mountaincar_step_reward(cur,a,nxt),dtype=np.float64).reshape(-1)[0])
        p=float(np.clip(np.asarray(p,dtype=np.float64).reshape(-1)[0],0.0,1.0))
        value,dist,_idx=nearest_remaining(cache_states,cache_values,nxt)
        q.append(r+(1.0-p)*value)
        nn.append(dist)
    action=int(np.argmax(q))
    return action,q,float(np.mean(nn))


def _rollout(env,planner,cfg,s,t,kind,meter,obs):
    obs=np.asarray(obs,dtype=np.float32).reshape(-1)
    actions=[];rewards=[];seeds=[];nns=[];terminated=truncated=False
    for step in range(int(cfg['episode_steps'])):
        if terminated or truncated: break
        seed=step_seed(cfg,s,t,step);seq=shared_candidates(int(seed))
        if kind=='h16':
            action,_scores,_idx=base.h16_first_action(planner,obs,seq)
        elif kind=='tree_reuse':
            action,_q,nn=tree_reuse_first_action(planner,obs,seq);nns.append(nn)
        else:
            action,_q=base.lookahead_first_action(planner,obs,seq)
        nxt,r,terminated,truncated,_=env.step(action)
        nxt=np.asarray(nxt,dtype=np.float32)
        actions.append(int(action));rewards.append(float(r));seeds.append(int(seed));obs=nxt
        meter.check()
    return dict(kind=kind,actions=actions,rewards=rewards,seeds=seeds,n_steps=len(actions),
                nearest_distance=float(np.mean(nns)) if nns else None,
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
    if OUTPUT.exists():raise RuntimeError('refusing tree-reuse overwrite')
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
           mountaincar_continuous=False,fitted_critic=False,
           successor_value='nearest_cached_open_loop_h16_remaining',tree_reuse_control=True,
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
                    reuse=_rollout(env,planner,cfg,s,t,'tree_reuse',meter,obs)
                    obs,_=env.reset(seed=reset_seed(cfg,s,t))
                    look=_rollout(env,planner,cfg,s,t,'lookahead',meter,obs)
                    n=min(len(h16['seeds']),len(reuse['seeds']),len(look['seeds']))
                    if h16['seeds'][:n]!=reuse['seeds'][:n] or h16['seeds'][:n]!=look['seeds'][:n]:
                        raise ValueError('step seeds were not shared on the common prefix')
                    metrics=dict(return_h16=h16['episode_return'],return_tree_reuse=reuse['episode_return'],
                                 return_lookahead=look['episode_return'],
                                 return_gain=reuse['episode_return']-h16['episode_return'],
                                 n_steps_h16=h16['n_steps'],n_steps_tree_reuse=reuse['n_steps'],
                                 n_steps_lookahead=look['n_steps'],
                                 nearest_distance=reuse['nearest_distance'])
                    finite_array([metrics['return_h16'],metrics['return_tree_reuse'],
                                  metrics['return_lookahead'],metrics['return_gain']],(4,))
                    p['cells'].append(dict(seed=s,task=t,reset_seed=reset_seed(cfg,s,t),
                                           h16=h16,tree_reuse=reuse,lookahead=look,metrics=metrics))
                finally:
                    env.close()
                print(f'seed={s} task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['counts']=dict(meter.counts)
        if int(p['counts']['episode'])>cfg['env_cap']:raise ValueError('env step count exceeded cap')
        if int(p['counts']['model_states'])>cfg['model_cap']:raise ValueError('imagined count exceeded cap')
        summary=summarize(p['cells'],cfg);p.update(summary);meter.check()
        p['complete']=len(p['cells'])==30
        p['n_episodes']=90
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
        p['complete']=False;p['label']='incomplete'
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def audit_results():
    cfg=load_config();p=json.loads(OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid tree-reuse evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    if p.get('fitted_critic') is not False: raise ValueError('fitted critic flag drifted')
    if p.get('retune_from_confirmation') is not False: raise ValueError('confirmation retune flag drifted')
    n=0
    for row in p['cells']:
        n+=1
        if not np.isclose(math.fsum(row['h16']['rewards']),row['metrics']['return_h16'],atol=1e-8):
            raise ValueError('H=16 reward reconstruction drifted')
        if not np.isclose(math.fsum(row['tree_reuse']['rewards']),row['metrics']['return_tree_reuse'],atol=1e-8):
            raise ValueError('tree-reuse reward reconstruction drifted')
        if not np.isclose(row['metrics']['return_gain'],row['metrics']['return_tree_reuse']-row['metrics']['return_h16'],atol=1e-8):
            raise ValueError('return_gain identity mismatch')
        if int(row['metrics']['n_steps_h16'])>cfg['episode_steps'] or int(row['metrics']['n_steps_tree_reuse'])>cfg['episode_steps']:
            raise ValueError('episode length exceeded 200')
    if n!=30: raise ValueError('30-cell grid drifted')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'],
                n_episodes=90,new_environment_steps=int(p['counts']['episode']),
                new_imagined_transitions=int(p['counts']['model_states']),
                pendulum_weights=False,cartpole_h3=False,fitted_critic=False,
                retune_from_confirmation=False,holdout_split_hash=HOLD_SPLIT)


def prep():
    cfg=load_config();record=load_allocation()
    if record.get('authorized') is True or int(record.get('runs',0))!=0:
        raise PermissionError('prep refuses an already authorized allocation')
    ours=set().union(*seed_groups(cfg))
    if min(ours)<29000000: raise ValueError('tree-reuse seeds drifted below 29000000')
    load_frozen_models(cfg)
    synth.load_cited()
    return dict(complete=True,authorized=False,runs=0,new_environment_steps=0,new_imagined_transitions=0,
                pendulum_weights=False,cartpole_h3=False,fitted_critic=False,confirmation_outcomes_read=False,
                starting_sha=cfg['starting_sha'],config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),
                allocation_sha256=sha(ALLOCATION),
                controller=dict(h16='frozen_mountaincar_h16x16',tree_reuse='nearest_cached_open_loop_remaining',
                                lookahead='one_step_backup_of_h16x16',horizon=16,n_candidates=16,n_actions=3,
                                h16_imagined_per_step=H16_IMAGINED,tree_reuse_imagined_per_step=TREE_REUSE_IMAGINED,
                                lookahead_imagined_per_step=LOOKAHEAD_IMAGINED,distance_tau='inf'),
                eligibility=dict(selected_holdout=base.holdout_from_rule(),split_hash=HOLD_SPLIT,
                                 reused_confirmation_physics=False,reused_development_episode_seeds=False,
                                 reused_cartpole=False,reused_pendulum_weights=False,dense_height_reward=True),
                proposed_budget=budget(cfg),primary=PRIMARY,practical_margin=25.0,
                labels=('tree_reuse_lookahead_established','tree_reuse_lookahead_harm_established',
                        'tree_reuse_lookahead_not_established','incomplete'))
