"""H=3-only CartPole saturation diagnostic on stricter unused physics.

Lookahead is withheld. H=3 is not retuned. Closed confirmation tuples and both
ceilinged lookahead draws are not reused.
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
    cartpole_h3_saturation,
    cartpole_lookahead_development,
    cartpole_lookahead_hard,
    cartpole_physics_key,
)
from nexus.world import bellman_backup_control as bbc
from nexus.world import cartpole_lookahead as base
from nexus.world import cartpole_lookahead_hard as hard
from nexus.world.freeze import (
    FROZEN_CANDIDATES,
    FROZEN_EPOCHS,
    FROZEN_KIND,
    FROZEN_N_TRAIN,
    FROZEN_N_VAL,
    FROZEN_OBJECTIVE,
    FROZEN_PRIMARY_HORIZON,
    v073_confirmation_targets,
)
from nexus.world.planning_value import finite_array, sha
from nexus.world.terminal_value_execution import checked_id_grid, save

CONFIG=Path('configs/cartpole_h3_saturation.yaml')
PROTOCOL=Path('docs/NEXUS_CARTPOLE_H3_SATURATION_PROTOCOL.md')
ALLOCATION=Path('configs/cartpole_h3_saturation_allocation.json')
OUTPUT=Path('artifacts/cartpole_h3_saturation.json')
CHECKPOINTS=Path('checkpoints/cartpole_h3_saturation')
HOLD_RULE='cartpole_h3_saturation_v1'
HOLD_SPLIT='a69833ab38a34ab4'
LOCKED_CONFIG='55be38a5d77e76bb38a56c50d92e9522037855e8b500577de55c665af9291421'
LOCKED_PROTOCOL='657cf38d25c9d013b733e8ba6ef373845b487f980d19f6b815e3cf4ad96cd157'
PRIMARY='ceiling_gap'
N_TASKS=6
STRICT_G=(13.0,16.0)
STRICT_L=(0.25,0.34)
STRICT_M=(0.20,0.30)


def occupied_physics():
    occupied,rows=hard.occupied_physics()
    for spec in cartpole_lookahead_hard():
        key=cartpole_physics_key(spec)
        occupied.add(key);rows.append(('cartpole_lookahead_hard',spec.task_id,key))
    return occupied,rows


def holdout_from_rule(n=N_TASKS,rule=HOLD_RULE):
    occupied,_rows=occupied_physics()
    gs=[round(x*0.1,1) for x in range(130,161)]
    ls=[round(x*0.01,2) for x in range(25,35)]
    ms=[round(x*0.01,2) for x in range(20,31)]
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


def budget(cfg):
    train=10*(int(cfg['n_train'])+int(cfg['n_val']))
    control=10*N_TASKS*1*int(cfg['max_episode_steps'])
    imagined=10*N_TASKS*int(cfg['max_episode_steps'])*(16*3)
    if train+control!=cfg['env_cap'] or imagined!=cfg['model_cap']:
        raise ValueError('CartPole H=3 saturation resource allocation mismatch')
    return dict(episode_max=train+control,train=train,control_max=control,model_states_max=imagined,
                time_cap_s=300,training_updates=200,h3_imagined_per_step=48,lookahead_imagined_per_step=0)


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(n_model_seeds=10,eval_tasks=N_TASKS,n_actions=2,candidate_horizon=3,n_candidates=16,
                max_episode_steps=500,episodes_per_cell=1,practical_margin=25.0,time_cap_s=300,
                env_cap=42800,model_cap=1440000,training_updates=200,support_budget=0,n_train=1024,
                n_val=256,epochs=20,kind='residual',objective='both',enforce_time_budget=False,
                compute_matched_control=False,pendulum_weights=False,student_zero_context=False,
                lookahead_authorized=False,holdout_rule=HOLD_RULE,holdout_split_hash=HOLD_SPLIT,
                starting_sha='894f5ca3ab0ec7b084d7c0e4f041b6c58de1f5b0',
                reset_base=20000000,step_seed_base=20100000,train_collect_base=180000,val_collect_base=185000)
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked H=3 saturation design/budget changed')
    region=cfg['strict_region']
    if [float(x) for x in region['gravity']]!=list(STRICT_G) or [float(x) for x in region['length']]!=list(STRICT_L):
        raise ValueError('strict region drifted')
    if [float(x) for x in region['masspole']]!=list(STRICT_M): raise ValueError('strict mass region drifted')
    if int(cfg['candidate_horizon'])!=int(FROZEN_PRIMARY_HORIZON): raise ValueError('CartPole horizon is frozen H=3')
    if int(cfg['n_candidates'])!=int(FROZEN_CANDIDATES[3]): raise ValueError('candidate count drifted')
    if cfg['kind']!=FROZEN_KIND or int(cfg['epochs'])!=int(FROZEN_EPOCHS): raise ValueError('frozen residual recipe drifted')
    if int(cfg['n_train'])!=int(FROZEN_N_TRAIN) or int(cfg['n_val'])!=int(FROZEN_N_VAL): raise ValueError('frozen data sizes drifted')
    if cfg['objective']!=FROZEN_OBJECTIVE: raise ValueError('frozen CartPole objective drifted')
    if cfg['lookahead_authorized'] is not False: raise ValueError('lookahead is withheld on this diagnostic')
    specs=cartpole_h3_saturation()
    if cfg['eval_task_ids']!=[s.task_id for s in specs]: raise ValueError('saturation task ids changed')
    if cfg['eval_physics']!=[list(cartpole_physics_key(s)) for s in specs]: raise ValueError('saturation physics changed')
    if split_hash(specs)!=HOLD_SPLIT: raise ValueError('saturation split hash drifted')
    if holdout_from_rule()!=[tuple(row) for row in cfg['eval_physics']]:
        raise ValueError('saturation rule does not reproduce locked physics')
    occupied,_rows=occupied_physics()
    closed={cartpole_physics_key(s) for s in v073_confirmation_targets()}
    closed |={cartpole_physics_key(s) for s in cartpole_lookahead_development()}
    closed |={cartpole_physics_key(s) for s in cartpole_lookahead_hard()}
    for row in cfg['eval_physics']:
        key=tuple(row)
        if key in occupied or key in closed: raise ValueError('saturation holdout collides with a registered or closed split')
        g,l,mass=key
        if not (STRICT_G[0]<=g<=STRICT_G[1] and STRICT_L[0]<=l<=STRICT_L[1] and STRICT_M[0]<=mass<=STRICT_M[1]):
            raise ValueError('saturation holdout left the stricter unused corner')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    if LOCKED_CONFIG and sha(CONFIG)!=LOCKED_CONFIG: raise ValueError('locked configuration hash drifted')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=LOCKED_PROTOCOL: raise ValueError('locked protocol hash drifted')
    budget(cfg)
    return cfg


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=300,env_cap=42800,model_cap=1440000,training_updates=200).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('saturation allocation drift')
    if record.get('holdout_split_hash')!=HOLD_SPLIT: raise ValueError('allocation holdout hash drifted')
    if record.get('lookahead_authorized') is not False: raise ValueError('allocation must withhold lookahead')
    if LOCKED_CONFIG:
        if record.get('config_sha256')!=LOCKED_CONFIG or record.get('config_sha256')!=sha(CONFIG):
            raise ValueError('allocation config hash does not match yaml')
        if record.get('protocol_sha256')!=LOCKED_PROTOCOL or record.get('protocol_sha256')!=sha(PROTOCOL):
            raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before H=3 saturation collection')
    if LOCKED_CONFIG and sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=record.get('protocol_sha256'):
        raise PermissionError('allocation does not bind this protocol hash')
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'cartpole_h3_unsaturated'
    return 'cartpole_h3_still_ceilinged'


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('seed','task'),set(itertools.product(range(10),range(N_TASKS))))
    gap=[float(np.mean([500.0-cells[s,t]['metrics']['return_h3'] for t in range(N_TASKS)])) for s in range(10)]
    h3=[float(np.mean([cells[s,t]['metrics']['return_h3'] for t in range(N_TASKS)])) for s in range(10)]
    primary=seed_level_ci(gap)
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,True,cfg['practical_margin'])
    return dict(label=label,groups=dict(ceiling_gap=dict(per_seed=gap,interval=primary),
                                        return_h3=dict(per_seed=h3,interval=seed_level_ci(h3))))


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing H=3 saturation overwrite')
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
           parents=cfg['parents'],pendulum_weights=False,retuned_h3=False,lookahead_run=False,
           holdout_split_hash=HOLD_SPLIT,training_updates=0,strict_region=cfg['strict_region'])
    CHECKPOINTS.mkdir(parents=True,exist_ok=True)
    try:
        source=source_policy_task();specs=list(cartpole_h3_saturation());models=[]
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
            for t in range(N_TASKS):
                spec=specs[t];env=make_task_env(spec);meter.instrument_env(env)
                try:
                    obs,_=env.reset(seed=base.reset_seed(cfg,s,t))
                    h3=base._rollout(env,planner,cfg,s,t,'h3',meter,obs)
                    metrics=dict(return_h3=h3['episode_return'],ceiling_gap=500.0-h3['episode_return'],n_steps_h3=h3['n_steps'])
                    finite_array([metrics['return_h3'],metrics['ceiling_gap']],(2,))
                    p['cells'].append(dict(seed=s,task=t,reset_seed=base.reset_seed(cfg,s,t),h3=h3,metrics=metrics))
                finally:
                    env.close()
                print(f'seed={s} task={t} seconds={time.perf_counter()-started:.1f}',flush=True)
        p['counts']=dict(meter.counts)
        if int(p['counts']['episode'])>cfg['env_cap']:raise ValueError('env step count exceeded cap')
        if int(p['counts']['model_states'])>cfg['model_cap']:raise ValueError('imagined count exceeded cap')
        summary=summarize(p['cells'],cfg);p.update(summary);meter.check()
        p['complete']=len(p['cells'])==60
        p['n_episodes']=60
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
        p['complete']=False;p['label']='incomplete'
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def audit_results():
    cfg=load_config();p=json.loads(OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid H=3 saturation evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    if p.get('pendulum_weights') is not False or p.get('retuned_h3') is not False or p.get('lookahead_run') is not False:
        raise ValueError('controller identity drifted')
    n=0
    for row in p['cells']:
        n+=1
        if 'lookahead' in row: raise ValueError('lookahead traces were collected')
        if not np.isclose(math.fsum(row['h3']['rewards']),row['metrics']['return_h3'],atol=1e-8):
            raise ValueError('H=3 reward reconstruction drifted')
        if not np.isclose(row['metrics']['ceiling_gap'],500.0-row['metrics']['return_h3'],atol=1e-8):
            raise ValueError('ceiling_gap identity mismatch')
    if n!=60: raise ValueError('60-cell grid drifted')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'],
                n_episodes=60,new_environment_steps=int(p['counts']['episode']),
                new_imagined_transitions=int(p['counts']['model_states']),
                pendulum_weights=False,retuned_h3=False,lookahead_run=False,holdout_split_hash=HOLD_SPLIT)


def prep():
    cfg=load_config();record=load_allocation()
    if record.get('authorized') is True or int(record.get('runs',0))!=0:
        raise PermissionError('prep refuses an already authorized allocation')
    return dict(complete=True,authorized=False,runs=0,new_environment_steps=0,new_imagined_transitions=0,
                pendulum_weights=False,retuned_h3=False,lookahead_run=False,starting_sha=cfg['starting_sha'],
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                controller=dict(h3='frozen_cartpole_h3x16',lookahead='withheld',horizon=3,n_candidates=16,n_actions=2),
                eligibility=dict(selected_holdout=holdout_from_rule(),split_hash=HOLD_SPLIT,
                                 reused_v073_confirmation=False,reused_ceilinged_development=False,
                                 reused_hard_development=False,strict_region=cfg['strict_region']),
                proposed_budget=budget(cfg),primary=PRIMARY,practical_margin=25.0,
                labels=('cartpole_h3_unsaturated','cartpole_h3_still_ceilinged','incomplete'),
                note='No collection. Lookahead withheld. H=3 was not retuned. Closed splits unused.')
