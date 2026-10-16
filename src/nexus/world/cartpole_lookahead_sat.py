"""Lookahead versus frozen CartPole H=3 on the unsaturated saturation holdout.

Uses the same six-task split `a69833ab38a34ab4`. Does not drop ceilinged tasks.
Does not retune H=3. Closed confirmation tuples are not reused.
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
from nexus.tasks.cartpole_family import (
    cartpole_h3_saturation,
    cartpole_lookahead_development,
    cartpole_lookahead_hard,
    cartpole_physics_key,
)
from nexus.world import bellman_backup_control as bbc
from nexus.world import cartpole_h3_saturation as sat
from nexus.world import cartpole_lookahead as base
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

CONFIG=Path('configs/cartpole_lookahead_sat.yaml')
PROTOCOL=Path('docs/NEXUS_CARTPOLE_LOOKAHEAD_SAT_PROTOCOL.md')
ALLOCATION=Path('configs/cartpole_lookahead_sat_allocation.json')
OUTPUT=Path('artifacts/cartpole_lookahead_sat.json')
CHECKPOINTS=Path('checkpoints/cartpole_lookahead_sat')
HOLD_RULE='cartpole_h3_saturation_v1'
HOLD_SPLIT='a69833ab38a34ab4'
LOCKED_CONFIG='7fe2a70eaf88953f2203f9f70de586d69991e16741864075fcdfbe7148547dbe'
LOCKED_PROTOCOL='3c82cdd477082ea3898ac346e4d193eda5506e6aab947f259d76fe954d75dac8'
PRIMARY='return_gain'
N_TASKS=6


def budget(cfg):
    train=10*(int(cfg['n_train'])+int(cfg['n_val']))
    control=10*N_TASKS*2*int(cfg['max_episode_steps'])
    imagined=10*N_TASKS*int(cfg['max_episode_steps'])*(16*3+2+2*16*3)
    if train+control!=cfg['env_cap'] or imagined!=cfg['model_cap']:
        raise ValueError('saturation-holdout lookahead resource allocation mismatch')
    return dict(episode_max=train+control,train=train,control_max=control,model_states_max=imagined,
                time_cap_s=300,training_updates=200,lookahead_imagined_per_step=98,h3_imagined_per_step=48)


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(n_model_seeds=10,eval_tasks=N_TASKS,n_actions=2,candidate_horizon=3,n_candidates=16,
                max_episode_steps=500,episodes_per_cell=1,practical_margin=25.0,time_cap_s=300,
                env_cap=72800,model_cap=4380000,training_updates=200,support_budget=0,n_train=1024,
                n_val=256,epochs=20,kind='residual',objective='both',enforce_time_budget=False,
                compute_matched_control=False,pendulum_weights=False,student_zero_context=False,
                drop_ceilinged_tasks=False,holdout_rule=HOLD_RULE,holdout_split_hash=HOLD_SPLIT,
                starting_sha='18ed8e424daf5351f84c8f5763730c644ea54574',
                reset_base=21000000,step_seed_base=21100000,train_collect_base=190000,val_collect_base=195000)
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked sat-holdout lookahead design/budget changed')
    if int(cfg['candidate_horizon'])!=int(FROZEN_PRIMARY_HORIZON): raise ValueError('CartPole horizon is frozen H=3')
    if int(cfg['n_candidates'])!=int(FROZEN_CANDIDATES[3]): raise ValueError('candidate count drifted')
    if cfg['kind']!=FROZEN_KIND or int(cfg['epochs'])!=int(FROZEN_EPOCHS): raise ValueError('frozen residual recipe drifted')
    if int(cfg['n_train'])!=int(FROZEN_N_TRAIN) or int(cfg['n_val'])!=int(FROZEN_N_VAL): raise ValueError('frozen data sizes drifted')
    if cfg['objective']!=FROZEN_OBJECTIVE: raise ValueError('frozen CartPole objective drifted')
    if cfg['drop_ceilinged_tasks'] is not False: raise ValueError('ceilinged tasks must not be dropped')
    specs=cartpole_h3_saturation()
    if cfg['eval_task_ids']!=[s.task_id for s in specs]: raise ValueError('sat-holdout task ids changed')
    if cfg['eval_physics']!=[list(cartpole_physics_key(s)) for s in specs]: raise ValueError('sat-holdout physics changed')
    if sat.split_hash(specs)!=HOLD_SPLIT: raise ValueError('sat-holdout split hash drifted')
    if sat.holdout_from_rule()!=[tuple(row) for row in cfg['eval_physics']]:
        raise ValueError('sat-holdout is not the locked saturation split')
    if len(cfg['eval_physics'])!=N_TASKS: raise ValueError('sat-holdout dropped tasks')
    closed={cartpole_physics_key(s) for s in v073_confirmation_targets()}
    closed |={cartpole_physics_key(s) for s in cartpole_lookahead_development()}
    closed |={cartpole_physics_key(s) for s in cartpole_lookahead_hard()}
    for row in cfg['eval_physics']:
        if tuple(row) in closed: raise ValueError('sat-holdout collides with a closed confirmation or ceilinged lookahead split')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    if LOCKED_CONFIG and sha(CONFIG)!=LOCKED_CONFIG: raise ValueError('locked configuration hash drifted')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=LOCKED_PROTOCOL: raise ValueError('locked protocol hash drifted')
    budget(cfg)
    return cfg


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=300,env_cap=72800,model_cap=4380000,training_updates=200).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('sat-holdout allocation drift')
    if record.get('holdout_split_hash')!=HOLD_SPLIT: raise ValueError('allocation holdout hash drifted')
    if record.get('drop_ceilinged_tasks') is not False: raise ValueError('allocation must keep all six tasks')
    if LOCKED_CONFIG:
        if record.get('config_sha256')!=LOCKED_CONFIG or record.get('config_sha256')!=sha(CONFIG):
            raise ValueError('allocation config hash does not match yaml')
        if record.get('protocol_sha256')!=LOCKED_PROTOCOL or record.get('protocol_sha256')!=sha(PROTOCOL):
            raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before sat-holdout lookahead collection')
    if LOCKED_CONFIG and sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')
    if LOCKED_PROTOCOL and sha(PROTOCOL)!=record.get('protocol_sha256'):
        raise PermissionError('allocation does not bind this protocol hash')
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s'])<cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'cartpole_sat_lookahead_established'
    if mean<=-margin and hi<0: return 'cartpole_sat_lookahead_harm_established'
    return 'cartpole_sat_lookahead_not_established'


def summarize(rows,cfg):
    cells=checked_id_grid(rows,('seed','task'),set(itertools.product(range(10),range(N_TASKS))))
    values=[float(np.mean([cells[s,t]['metrics']['return_gain'] for t in range(N_TASKS)])) for s in range(10)]
    h3=[float(np.mean([cells[s,t]['metrics']['return_h3'] for t in range(N_TASKS)])) for s in range(10)]
    look=[float(np.mean([cells[s,t]['metrics']['return_lookahead'] for t in range(N_TASKS)])) for s in range(10)]
    primary=seed_level_ci(values)
    label=classify_primary(primary['mean'],primary['lo'],primary['hi'],10,True,cfg['practical_margin'])
    return dict(label=label,groups=dict(return_gain=dict(per_seed=values,interval=primary),
                                        return_h3=dict(per_seed=h3,interval=seed_level_ci(h3)),
                                        return_lookahead=dict(per_seed=look,interval=seed_level_ci(look))))


def execute():
    cfg=load_config();require_allocation(cfg)
    if OUTPUT.exists():raise RuntimeError('refusing sat-holdout lookahead overwrite')
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
           parents=cfg['parents'],pendulum_weights=False,retuned_h3=False,drop_ceilinged_tasks=False,
           successor_value='frozen_open_loop_h3_score',compute_matched_control=False,
           holdout_split_hash=HOLD_SPLIT,training_updates=0)
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
        p['complete']=len(p['cells'])==60
        p['n_episodes']=120
    except Exception as exc:
        p['failure']=dict(type=type(exc).__name__,message=str(exc));print('INCOMPLETE',p['failure'],flush=True)
        p['complete']=False;p['label']='incomplete'
    p['wall_clock_s']=time.perf_counter()-started;save(OUTPUT,p);return p


def audit_results():
    cfg=load_config();p=json.loads(OUTPUT.read_text())
    if p.get('complete') is not True:raise RuntimeError('incomplete/invalid sat-holdout lookahead evaluation')
    rebuilt=summarize(p['cells'],cfg)
    if p['label']!=rebuilt['label']:raise ValueError('saved label differs')
    if p.get('pendulum_weights') is not False or p.get('retuned_h3') is not False or p.get('drop_ceilinged_tasks') is not False:
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
    if n!=60: raise ValueError('60-cell grid drifted')
    return dict(audit_passed=True,label=p['label'],raw_sha256=sha(OUTPUT),groups=p['groups'],
                n_episodes=120,new_environment_steps=int(p['counts']['episode']),
                new_imagined_transitions=int(p['counts']['model_states']),
                pendulum_weights=False,retuned_h3=False,drop_ceilinged_tasks=False,holdout_split_hash=HOLD_SPLIT)


def prep():
    cfg=load_config();record=load_allocation()
    if record.get('authorized') is True or int(record.get('runs',0))!=0:
        raise PermissionError('prep refuses an already authorized allocation')
    return dict(complete=True,authorized=False,runs=0,new_environment_steps=0,new_imagined_transitions=0,
                pendulum_weights=False,retuned_h3=False,drop_ceilinged_tasks=False,starting_sha=cfg['starting_sha'],
                config_sha256=sha(CONFIG),protocol_sha256=sha(PROTOCOL),allocation_sha256=sha(ALLOCATION),
                controller=dict(h3='frozen_cartpole_h3x16',lookahead='one_step_backup_of_h3',horizon=3,
                                n_candidates=16,n_actions=2,lookahead_imagined_per_step=98,h3_imagined_per_step=48),
                eligibility=dict(selected_holdout=sat.holdout_from_rule(),split_hash=HOLD_SPLIT,
                                 reused_v073_confirmation=False,dropped_ceilinged_tasks=False,n_tasks=N_TASKS),
                proposed_budget=budget(cfg),primary=PRIMARY,practical_margin=25.0,
                labels=('cartpole_sat_lookahead_established','cartpole_sat_lookahead_harm_established',
                        'cartpole_sat_lookahead_not_established','incomplete'),
                note='No collection. Same six-task saturation holdout. H=3 was not retuned. Ceilinged tasks were not dropped.')
