"""Lookahead versus frozen CartPole H=3 on harder unused physics.

Does not retune H=3. Hard region is the published V0.7.3 off-ceiling corner.
Closed confirmation tuples and the ceilinged development draw are not reused.
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
from nexus.tasks.cartpole_family import cartpole_lookahead_development, cartpole_lookahead_hard, cartpole_physics_key
from nexus.world import bellman_backup_control as bbc
from nexus.world import cartpole_lookahead as base
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL, FROZEN_OBJECTIVE, FROZEN_PRIMARY_HORIZON, v073_confirmation_targets
from nexus.world.planning_value import finite_array, sha
from nexus.world.terminal_value_execution import checked_id_grid, save

CONFIG=Path('configs/cartpole_lookahead_hard.yaml')
PROTOCOL=Path('docs/NEXUS_CARTPOLE_LOOKAHEAD_HARD_PROTOCOL.md')
ALLOCATION=Path('configs/cartpole_lookahead_hard_allocation.json')
OUTPUT=Path('artifacts/cartpole_lookahead_hard.json')
CHECKPOINTS=Path('checkpoints/cartpole_lookahead_hard_h3')
HOLD_RULE='cartpole_lookahead_hard_v1'
HOLD_SPLIT='9a60e48299b738ef'
LOCKED_CONFIG='0515452c75a45d94d610a21ddea91727c499b00a4aeae3d72f56f322a65f954c'
LOCKED_PROTOCOL='c2bb743a003544ee1ef6a310ea4c77633fa6f9b42db428a5cfe4a0b40cb26f6e'
PRIMARY='return_gain'
HARD_G=(12.0,16.0)
HARD_L=(0.25,0.45)
HARD_M=(0.15,0.30)


def occupied_physics():
    occupied,rows=base.occupied_physics()
    for spec in cartpole_lookahead_development():
        key=cartpole_physics_key(spec)
        occupied.add(key);rows.append(('cartpole_lookahead_development',spec.task_id,key))
    return occupied,rows


def holdout_from_rule(n=3,rule=HOLD_RULE):
    occupied,_rows=occupied_physics()
    gs=[round(x*0.1,1) for x in range(120,161)]
    ls=[round(x*0.01,2) for x in range(25,46)]
    ms=[round(x*0.01,2) for x in range(15,31)]
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
                starting_sha='82d85519f97533e2969834e09dd80c9333a0e3a6',
                reset_base=19000000,step_seed_base=19100000,train_collect_base=170000,val_collect_base=175000)
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked hard CartPole design/budget changed')
    region=cfg['hard_region']
    if [float(x) for x in region['gravity']]!=list(HARD_G) or [float(x) for x in region['length']]!=list(HARD_L):
        raise ValueError('hard region drifted')
    if [float(x) for x in region['masspole']]!=list(HARD_M): raise ValueError('hard mass region drifted')
    if int(cfg['candidate_horizon'])!=int(FROZEN_PRIMARY_HORIZON): raise ValueError('CartPole horizon is frozen H=3')
    if int(cfg['n_candidates'])!=int(FROZEN_CANDIDATES[3]): raise ValueError('candidate count drifted')
    if cfg['kind']!=FROZEN_KIND or int(cfg['epochs'])!=int(FROZEN_EPOCHS): raise ValueError('frozen residual recipe drifted')
    if int(cfg['n_train'])!=int(FROZEN_N_TRAIN) or int(cfg['n_val'])!=int(FROZEN_N_VAL): raise ValueError('frozen data sizes drifted')
    if cfg['objective']!=FROZEN_OBJECTIVE: raise ValueError('frozen CartPole objective drifted')
    specs=cartpole_lookahead_hard()
    if cfg['eval_task_ids']!=[s.task_id for s in specs]: raise ValueError('hard task ids changed')
    if cfg['eval_physics']!=[list(cartpole_physics_key(s)) for s in specs]: raise ValueError('hard physics changed')
    if split_hash(specs)!=HOLD_SPLIT: raise ValueError('hard split hash drifted')
    if holdout_from_rule()!=[tuple(row) for row in cfg['eval_physics']]:
        raise ValueError('hard rule does not reproduce locked physics')
    occupied,_rows=occupied_physics()
    closed={cartpole_physics_key(s) for s in v073_confirmation_targets()}
    closed |= {cartpole_physics_key(s) for s in cartpole_lookahead_development()}
    for row in cfg['eval_physics']:
        key=tuple(row)
        if key in occupied or key in closed: raise ValueError('hard holdout collides with a registered or closed split')
        g,l,m=key
        if not (HARD_G[0]<=g<=HARD_G[1] and HARD_L[0]<=l<=HARD_L[1] and HARD_M[0]<=m<=HARD_M[1]):
            raise ValueError('hard holdout left the published off-ceiling region')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    if LOCKED_CONFIG and sha(CONFIG)!=LOCKED_CONFIG: raise ValueError('locked configuration hash drifted')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=LOCKED_PROTOCOL: raise ValueError('locked protocol hash drifted')
    base.budget(cfg)
    return cfg


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=300,env_cap=42800,model_cap=2190000,training_updates=200).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('hard allocation drift')
    if record.get('holdout_split_hash')!=HOLD_SPLIT: raise ValueError('allocation holdout hash drifted')
    if LOCKED_CONFIG:
        if record.get('config_sha256')!=LOCKED_CONFIG or record.get('config_sha256')!=sha(CONFIG):
            raise ValueError('allocation config hash does not match yaml')
        if record.get('protocol_sha256')!=LOCKED_PROTOCOL or record.get('protocol_sha256')!=sha(PROTOCOL):
            raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before hard CartPole lookahead collection')
    if LOCKED_CONFIG and sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=record.get('protocol_sha256'):
        raise PermissionError('allocation does not bind this protocol hash')
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'cartpole_hard_lookahead_established'
    if mean<=-margin and hi<0: return 'cartpole_hard_lookahead_harm_established'
    return 'cartpole_hard_lookahead_not_established'


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


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing hard CartPole lookahead overwrite')
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
           parents=cfg['parents'],pendulum_weights=False,retuned_h3=False,
           successor_value='frozen_open_loop_h3_score',compute_matched_control=False,
           holdout_split_hash=HOLD_SPLIT,training_updates=0,hard_region=cfg['hard_region'])
    CHECKPOINTS.mkdir(parents=True,exist_ok=True)
    try:
        source=source_policy_task();specs=list(cartpole_lookahead_hard());models=[]
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
            model=models[s];meter.instrument_model(model);planner=base.make_planner(model)
            for t in range(3):
                spec=specs[t];env=make_task_env(spec);meter.instrument_env(env)
                try:
                    obs,_=env.reset(seed=base.reset_seed(cfg,s,t))
                    h3=base._rollout(env,planner,cfg,s,t,'h3',meter,obs)
                    obs,_=env.reset(seed=base.reset_seed(cfg,s,t))
                    look=base._rollout(env,planner,cfg,s,t,'lookahead',meter,obs)
                    n=min(len(h3['seeds']),len(look['seeds']))
                    if h3['seeds'][:n]!=look['seeds'][:n]:
                        raise ValueError('step seeds were not shared on the common prefix')
                    metrics=dict(return_h3=h3['episode_return'],return_lookahead=look['episode_return'],
                                 return_gain=look['episode_return']-h3['episode_return'],
                                 n_steps_h3=h3['n_steps'],n_steps_lookahead=look['n_steps'])
                    finite_array([metrics['return_h3'],metrics['return_lookahead'],metrics['return_gain']],(3,))
                    p['cells'].append(dict(seed=s,task=t,reset_seed=base.reset_seed(cfg,s,t),h3=h3,lookahead=look,metrics=metrics))
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
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid hard CartPole lookahead evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    if p.get('pendulum_weights') is not False or p.get('retuned_h3') is not False:
        raise ValueError('controller identity drifted')
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
                pendulum_weights=False,retuned_h3=False,holdout_split_hash=HOLD_SPLIT)


def prep():
    cfg=load_config();record=load_allocation()
    if record.get('authorized') is True or int(record.get('runs',0))!=0:
        raise PermissionError('prep refuses an already authorized allocation')
    return dict(complete=True,authorized=False,runs=0,new_environment_steps=0,new_imagined_transitions=0,
                pendulum_weights=False,retuned_h3=False,starting_sha=cfg['starting_sha'],
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                controller=dict(h3='frozen_cartpole_h3x16',lookahead='one_step_backup_of_h3',horizon=3,
                                n_candidates=16,n_actions=2,lookahead_imagined_per_step=98,h3_imagined_per_step=48),
                eligibility=dict(selected_holdout=holdout_from_rule(),split_hash=HOLD_SPLIT,
                                 reused_v073_confirmation=False,reused_ceilinged_development=False,
                                 hard_region=cfg['hard_region']),
                proposed_budget=base.budget(cfg),primary=PRIMARY,practical_margin=25.0,
                labels=('cartpole_hard_lookahead_established','cartpole_hard_lookahead_harm_established',
                        'cartpole_hard_lookahead_not_established','incomplete'),
                note='No collection. H=3 was not retuned. V0.7.3 confirmation tuples were not reused.')
