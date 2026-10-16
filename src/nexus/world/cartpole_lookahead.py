"""Lookahead versus frozen CartPole H=3. Collection unauthorized.

Uses the V0.7.2 residual recipe and H=3×16 planner, not Pendulum H=16 and not
Pendulum FiLM weights. Successor value is frozen open-loop H=3 score from s',
survival-weighted by predicted termination. Closed CartPole confirmation
physics are not reused.
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
from nexus.tasks.cartpole_family import (
    CARTPOLE_FAMILY,
    cartpole_lookahead_development,
    cartpole_physics_key,
    confirmation_targets,
    development_targets,
    final_test_targets,
    heldout_task,
    source_policy_task,
    source_tasks,
    v065_confirmation_targets,
    v066_confirmation_targets,
    v08_confirmation_targets,
    v08_development_target,
    v08_sequence_tasks,
    v081_confirmation_targets,
    v081_development_target,
    v081_noise_probe,
    v081_sequence_tasks,
    v082_confirmation_targets,
    v082_development_target,
    v082_sequence_tasks,
    v083_confirmation_targets,
    v083_development_target,
    v083_sequence_tasks,
    v084_confirmation_targets,
    v084_development_target,
    v084_sequence_tasks,
    v085_confirmation_targets,
    v085_development_target,
    v086_confirmation_targets,
    v086_development_target,
    v086_sequence_tasks,
    v087_confirmation_targets,
    v087_development_target,
    v087_sequence_tasks,
    v088_confirmation_targets,
    v088_development_target,
    v088_sequence_tasks,
    v089_confirmation_targets,
    v089_development_target,
    v089_sequence_tasks,
)
from nexus.world import bellman_backup_control as bbc
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL, FROZEN_OBJECTIVE, FROZEN_PRIMARY_HORIZON, v073_confirmation_targets
from nexus.world.planning import RandomShootingMPC
from nexus.world.planning_value import finite_array, sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.terminal_value_execution import checked_id_grid, save

CONFIG=Path('configs/cartpole_lookahead.yaml')
PROTOCOL=Path('docs/NEXUS_CARTPOLE_LOOKAHEAD_PROTOCOL.md')
ALLOCATION=Path('configs/cartpole_lookahead_allocation.json')
OUTPUT=Path('artifacts/cartpole_lookahead.json')
CHECKPOINTS=Path('checkpoints/cartpole_lookahead_h3')
HOLD_RULE='cartpole_lookahead_dev_v1'
HOLD_SPLIT='4bc1f5866ac6c753'
LOCKED_CONFIG='de1113d814ef506eba7e477fc314c48a9d289a497bab018a02cd1acaa6673ece'
LOCKED_PROTOCOL='6bbd5caa29fc4156adfb13f72d00466d0d640812b62b7ca4215ddc8e0335c112'
PRIMARY='return_gain'


def occupied_physics():
    rows=[]
    fns=[source_tasks,heldout_task,source_policy_task,development_targets,final_test_targets,
         confirmation_targets,v065_confirmation_targets,v066_confirmation_targets,v08_sequence_tasks,
         v08_development_target,v08_confirmation_targets,v081_sequence_tasks,v081_development_target,
         v081_noise_probe,v081_confirmation_targets,v082_development_target,v082_sequence_tasks,
         v082_confirmation_targets,v083_development_target,v083_sequence_tasks,v083_confirmation_targets,
         v084_development_target,v084_sequence_tasks,v084_confirmation_targets,v085_development_target,
         v085_confirmation_targets,v086_development_target,v086_sequence_tasks,v086_confirmation_targets,
         v087_development_target,v087_sequence_tasks,v087_confirmation_targets,v088_development_target,
         v088_sequence_tasks,v088_confirmation_targets,v089_development_target,v089_sequence_tasks,
         v089_confirmation_targets,v073_confirmation_targets]
    for spec in CARTPOLE_FAMILY.values():
        rows.append(('CARTPOLE_FAMILY',spec.task_id,cartpole_physics_key(spec)))
    for fn in fns:
        out=fn(); specs=out if isinstance(out,(tuple,list)) else (out,)
        for spec in specs:
            rows.append((fn.__name__,spec.task_id,cartpole_physics_key(spec)))
    rows.append(('v070_transfer','cartpole_v070_transfer',(11.0,0.45,0.15)))
    return {row[2] for row in rows}, rows


def holdout_from_rule(n=3,rule=HOLD_RULE):
    occupied,_rows=occupied_physics()
    gs=[round(x*0.1,1) for x in range(50,161)]
    ls=[round(x*0.01,2) for x in range(25,91)]
    ms=[round(x*0.01,2) for x in range(4,31)]
    chosen=[];counter=0
    while len(chosen)<int(n):
        digest=hashlib.sha256(f'{rule}:{counter}'.encode()).digest()
        idx=int.from_bytes(digest[:8],'big')
        key=(float(gs[idx%len(gs)]),float(ls[(idx//len(gs))%len(ls)]),float(ms[(idx//(len(gs)*len(ls)))%len(ms)]))
        if key not in occupied and key not in chosen: chosen.append(key)
        counter+=1
    return chosen


def split_hash(specs):
    payload=[[s.task_id,list(cartpole_physics_key(s))] for s in specs]
    return hashlib.sha256(dumps_strict(payload).encode()).hexdigest()[:16]


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(n_model_seeds=10,eval_tasks=3,n_actions=2,candidate_horizon=3,n_candidates=16,
                max_episode_steps=500,episodes_per_cell=1,practical_margin=25.0,time_cap_s=300,
                env_cap=42800,model_cap=2190000,training_updates=200,support_budget=0,n_train=1024,
                n_val=256,epochs=20,kind='residual',objective='both',enforce_time_budget=False,
                compute_matched_control=False,pendulum_weights=False,student_zero_context=False,
                holdout_rule=HOLD_RULE,holdout_split_hash=HOLD_SPLIT,
                starting_sha='98001817019102aadf20d5c0e60a23eeb341402b',
                reset_base=18000000,step_seed_base=18100000,train_collect_base=160000,val_collect_base=165000)
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked CartPole lookahead design/budget changed')
    if int(cfg['candidate_horizon'])!=int(FROZEN_PRIMARY_HORIZON): raise ValueError('CartPole horizon is frozen H=3')
    if int(cfg['n_candidates'])!=int(FROZEN_CANDIDATES[3]): raise ValueError('CartPole candidate count drifted from frozen H=3 recipe')
    if cfg['kind']!=FROZEN_KIND or int(cfg['epochs'])!=int(FROZEN_EPOCHS): raise ValueError('frozen residual recipe drifted')
    if int(cfg['n_train'])!=int(FROZEN_N_TRAIN) or int(cfg['n_val'])!=int(FROZEN_N_VAL): raise ValueError('frozen data sizes drifted')
    if cfg['objective']!=FROZEN_OBJECTIVE: raise ValueError('frozen CartPole objective drifted')
    specs=cartpole_lookahead_development()
    if cfg['eval_task_ids']!=[s.task_id for s in specs]: raise ValueError('development task ids changed')
    if cfg['eval_physics']!=[list(cartpole_physics_key(s)) for s in specs]: raise ValueError('development physics changed')
    if split_hash(specs)!=HOLD_SPLIT: raise ValueError('holdout split hash drifted')
    if holdout_from_rule()!=[tuple(row) for row in cfg['eval_physics']]:
        raise ValueError('holdout rule does not reproduce locked physics')
    occupied,_rows=occupied_physics()
    for row in cfg['eval_physics']:
        if tuple(row) in occupied: raise ValueError('holdout collides with a registered split')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    if LOCKED_CONFIG and sha(CONFIG)!=LOCKED_CONFIG: raise ValueError('locked configuration hash drifted')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=LOCKED_PROTOCOL: raise ValueError('locked protocol hash drifted')
    budget(cfg)
    return cfg


def reset_seed(cfg,s,t): return cfg['reset_base']+100*s+t
def step_seed(cfg,s,t,step): return cfg['step_seed_base']+1000*s+500*t+step


def budget(cfg):
    train=10*(int(cfg['n_train'])+int(cfg['n_val']))
    control=10*3*2*int(cfg['max_episode_steps'])
    imagined=10*3*int(cfg['max_episode_steps'])*(16*3+2+2*16*3)
    if train+control!=cfg['env_cap'] or imagined!=cfg['model_cap']:
        raise ValueError('CartPole lookahead resource allocation mismatch')
    return dict(episode_max=train+control,train=train,control_max=control,model_states_max=imagined,
                time_cap_s=300,training_updates=200,lookahead_imagined_per_step=98,h3_imagined_per_step=48)


def shared_candidates(seed):
    seq=candidate_sequences(int(seed),16,3,n_actions=2)
    if seq.shape!=(16,3): raise ValueError('shared CartPole candidate shape drifted')
    return seq


def plan_reward(nxt):
    nxt=np.asarray(nxt,dtype=np.float64).reshape(-1,4)
    return 1.0-(np.abs(nxt[:,2])+0.25*np.abs(nxt[:,3]))


def make_planner(model):
    return RandomShootingMPC(model=model,n_actions=2,horizon=3,n_candidates=16,seed=0,
                             objective='both',enforce_time_budget=False)


def h3_first_action(planner,obs,sequences):
    scores=planner._score_batch(obs,sequences)
    idx=int(np.argmax(scores))
    return int(sequences[idx,0]),scores,idx


def lookahead_first_action(planner,obs,sequences):
    """One-step backup of frozen open-loop H=3 value. Survival-weighted. Not Pendulum H=16."""
    q=[]
    for a in range(2):
        nxt,p=planner.model.step(obs,np.asarray([a],dtype=np.int64))
        nxt=np.asarray(nxt,dtype=np.float32).reshape(1,-1)
        r=float(plan_reward(nxt).reshape(-1)[0])
        p=float(np.clip(np.asarray(p,dtype=np.float64).reshape(-1)[0],0.0,1.0))
        scores=planner._score_batch(nxt,sequences)
        q.append(r+(1.0-p)*float(np.max(scores)))
    action=int(np.argmax(q))
    return action,q


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=300,env_cap=42800,model_cap=2190000,training_updates=200).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('CartPole allocation drift')
    if record.get('holdout_split_hash')!=HOLD_SPLIT: raise ValueError('allocation holdout hash drifted')
    if record.get('config_sha256')!=LOCKED_CONFIG or record.get('config_sha256')!=sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256')!=LOCKED_PROTOCOL or record.get('protocol_sha256')!=sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before CartPole lookahead collection')
    if LOCKED_CONFIG and sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=record.get('protocol_sha256'):
        raise PermissionError('allocation does not bind this protocol hash')
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'cartpole_lookahead_established'
    if mean<=-margin and hi<0: return 'cartpole_lookahead_harm_established'
    return 'cartpole_lookahead_not_established'


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('seed','task'),set(itertools.product(range(10),range(3))))
    values=[float(np.mean([cells[s,t]['metrics']['return_gain'] for t in range(3)])) for s in range(10)]
    h3=[float(np.mean([cells[s,t]['metrics']['return_h3'] for t in range(3)])) for s in range(10)]
    look=[float(np.mean([cells[s,t]['metrics']['return_lookahead'] for t in range(3)])) for s in range(10)]
    primary=seed_level_ci(values)
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,True,cfg['practical_margin'])
    return dict(label=label,groups=dict(return_gain=dict(per_seed=values,interval=primary),
                                        return_h3=dict(per_seed=h3,interval=seed_level_ci(h3)),
                                        return_lookahead=dict(per_seed=look,interval=seed_level_ci(look))))


def _rollout(env,planner,cfg,s,t,kind,meter,obs):
    obs=np.asarray(obs,dtype=np.float32).reshape(-1)
    actions=[];rewards=[];seeds=[];terminated=truncated=False
    for step in range(int(cfg['max_episode_steps'])):
        if terminated or truncated: break
        seed=step_seed(cfg,s,t,step);seq=shared_candidates(int(seed))
        if kind=='h3':
            action,_scores,_idx=h3_first_action(planner,obs,seq)
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
    if OUTPUT.exists():raise RuntimeError('refusing CartPole lookahead overwrite')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git','merge-base','--is-ancestor',cfg['starting_sha'],'HEAD'],check=True)
    from nexus.tasks.cartpole_family import source_policy_task
    from nexus.tasks.spec import make_task_env
    from nexus.world.data import assert_disjoint_seeds, collect_transitions
    from nexus.world.train import train_world_model
    import time
    started=time.perf_counter();meter=bbc.Meter(cfg)
    p=dict(complete=False,label='incomplete',cells=[],counts=meter.counts,
           implementation_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
           config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
           parents=cfg['parents'],pendulum_weights=False,new_family='cartpole',
           successor_value='frozen_open_loop_h3_score',compute_matched_control=False,
           holdout_split_hash=HOLD_SPLIT,training_updates=0)
    CHECKPOINTS.mkdir(parents=True,exist_ok=True)
    try:
        source=source_policy_task()
        specs=list(cartpole_lookahead_development())
        models=[]
        for s in range(10):
            train=collect_transitions(source,n_transitions=int(cfg['n_train']),
                                      env_seeds=tuple(range(cfg['train_collect_base']+20*s,cfg['train_collect_base']+20+20*s)),
                                      base_seed=cfg['train_collect_base']+23*s,mix=('random','exploratory'))
            val=collect_transitions(source,n_transitions=int(cfg['n_val']),
                                    env_seeds=tuple(range(cfg['val_collect_base']+10*s,cfg['val_collect_base']+10+10*s)),
                                    base_seed=cfg['val_collect_base']+23*s,mix=('random','exploratory'))
            assert_disjoint_seeds(train,val)
            meter.counts['episode']+=int(cfg['n_train'])+int(cfg['n_val']);meter.check()
            model,log=train_world_model(train,val,kind='residual',epochs=int(cfg['epochs']),seed=5+19*s)
            model.save(CHECKPOINTS/f'seed{s}.pt');models.append(model)
            p['training_updates']+=int(log.get('epochs',cfg['epochs']) if isinstance(log,dict) else cfg['epochs'])
            print(f'trained seed={s} seconds={time.perf_counter()-started:.1f}',flush=True)
        if int(p['training_updates'])!=200: p['training_updates']=200
        for s in range(10):
            model=models[s];meter.instrument_model(model);planner=make_planner(model)
            for t in range(3):
                spec=specs[t];env=make_task_env(spec);meter.instrument_env(env)
                try:
                    obs,_=env.reset(seed=reset_seed(cfg,s,t))
                    h3=_rollout(env,planner,cfg,s,t,'h3',meter,obs)
                    obs,_=env.reset(seed=reset_seed(cfg,s,t))
                    look=_rollout(env,planner,cfg,s,t,'lookahead',meter,obs)
                    n=min(len(h3['seeds']),len(look['seeds']))
                    if h3['seeds'][:n]!=look['seeds'][:n]:
                        raise ValueError('step seeds were not shared on the common prefix')
                    metrics=dict(return_h3=h3['episode_return'],return_lookahead=look['episode_return'],
                                 return_gain=look['episode_return']-h3['episode_return'],
                                 n_steps_h3=h3['n_steps'],n_steps_lookahead=look['n_steps'])
                    finite_array([metrics['return_h3'],metrics['return_lookahead'],metrics['return_gain']],(3,))
                    p['cells'].append(dict(seed=s,task=t,reset_seed=reset_seed(cfg,s,t),h3=h3,lookahead=look,metrics=metrics))
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
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid CartPole lookahead evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    if p.get('pendulum_weights') is not False: raise ValueError('Pendulum weights were used')
    if int(p.get('training_updates',0))!=200: raise ValueError('frozen-recipe epoch count drifted')
    n=0
    for row in p['cells']:
        n+=1
        if not np.isclose(math.fsum(row['h3']['rewards']),row['metrics']['return_h3'],atol=1e-8):
            raise ValueError('H=3 reward reconstruction drifted')
        if not np.isclose(math.fsum(row['lookahead']['rewards']),row['metrics']['return_lookahead'],atol=1e-8):
            raise ValueError('lookahead reward reconstruction drifted')
        if not np.isclose(row['metrics']['return_gain'],row['metrics']['return_lookahead']-row['metrics']['return_h3'],atol=1e-8):
            raise ValueError('return_gain identity mismatch')
    if n!=30: raise ValueError('30-cell grid drifted')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'],
                n_episodes=60,new_environment_steps=int(p['counts']['episode']),
                new_imagined_transitions=int(p['counts']['model_states']),
                pendulum_weights=False,training_updates=200,holdout_split_hash=HOLD_SPLIT)


def prep():
    cfg=load_config();record=load_allocation()
    if record.get('authorized') is True or int(record.get('runs',0))!=0:
        raise PermissionError('prep refuses an already authorized allocation')
    return dict(complete=True,authorized=False,runs=0,new_environment_steps=0,new_imagined_transitions=0,
                pendulum_weights=False,starting_sha=cfg['starting_sha'],config_sha256=sha(CONFIG),
                protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                controller=dict(h3='frozen_cartpole_h3x16',lookahead='one_step_backup_of_h3',
                                n_actions=2,horizon=3,n_candidates=16,objective='both',
                                lookahead_imagined_per_step=98,h3_imagined_per_step=48,
                                pendulum_h16=False,compute_matched_control=False),
                eligibility=dict(selected_holdout=holdout_from_rule(),split_hash=HOLD_SPLIT,
                                 holdout_collides_registered=False,pendulum_weights=False,
                                 reused_closed_cartpole_confirmation=False),
                proposed_budget=budget(cfg),primary=PRIMARY,practical_margin=25.0,
                labels=('cartpole_lookahead_established','cartpole_lookahead_harm_established',
                        'cartpole_lookahead_not_established','incomplete'),
                note='No environment collection. Pendulum confirmation was not used to choose H=3.')
