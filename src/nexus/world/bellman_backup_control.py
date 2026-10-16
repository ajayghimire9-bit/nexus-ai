"""Parameter-free Bellman backup versus frozen H=16. Collection unauthorized."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import yaml
from nexus.world import late_episode_decision_trajectory as late
from nexus.world import receding_long_term_value_audit as audit
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.tasks.pendulum_family import pendulum_context_development,pendulum_physics_key

CONFIG=Path('configs/bellman_backup_control.yaml')
PROTOCOL=Path('docs/NEXUS_BELLMAN_BACKUP_CONTROL_PROTOCOL.md')
ALLOCATION=Path('configs/bellman_backup_control_allocation.json')
OUTPUT=Path('artifacts/bellman_backup_control.json')
PRIMARY='return_gain'


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),eval_tasks=3,visitors=2,
                candidate_horizon=16,n_candidates=16,n_actions=3,episode_steps=200,phase=0,
                practical_margin=25.0,time_cap_s=180,env_cap=24000,model_cap=12324000,
                training_updates=0,reset_base=13000000,step_seed_base=13100000,
                paired_shared_candidates=True,new_network=False,three_action_counterfactuals=False,
                starting_sha='580dfb0d3e0df1c03d561339577f0a2da8f6e893')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked Bellman design/budget changed')
    specs=pendulum_context_development()
    if cfg['eval_task_ids']!=[s.task_id for s in specs]: raise ValueError('development physics changed')
    if cfg['eval_physics']!=[list(pendulum_physics_key(s)) for s in specs]: raise ValueError('development physics values changed')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    budget(cfg);check_seeds(cfg)
    return cfg


def reset_seed(cfg,d,t): return cfg['reset_base']+100*d+t
def step_seed(cfg,d,t,step): return cfg['step_seed_base']+1000*d+200*t+step


def seed_groups(cfg):
    resets={reset_seed(cfg,d,t) for d in range(10) for t in range(3)}
    steps={step_seed(cfg,d,t,s) for d in range(10) for t in range(3) for s in range(200)}
    return [resets,steps]


def check_seeds(cfg):
    groups=seed_groups(cfg)
    if [len(g) for g in groups]!=[30,6000]: raise ValueError('duplicate Bellman seeds')
    used=set().union(*groups)
    blocked=set().union(*late.seed_groups(late.load_config()))
    if used & blocked: raise ValueError('Bellman seeds collide with late-episode/H=8 paired seeds')
    if min(used)<13000000: raise ValueError('seed block drifted below 13000000')


def budget(cfg):
    counts=audit.budget()
    if counts['episode']!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:
        raise ValueError('Bellman resource allocation mismatch')
    if int(cfg['training_updates'])!=0: raise ValueError('training is not part of this protocol')
    return counts


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=180,env_cap=24000,model_cap=12324000,training_updates=0).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('Bellman allocation drift')
    if record.get('config_sha256')!=sha(CONFIG): raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256')!=sha(PROTOCOL): raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before Bellman collection')
    if sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'bellman_backup_improves_episode_return'
    if mean<=-margin and hi<0: return 'bellman_backup_hurts_episode_return'
    return 'bellman_backup_not_established'


def shared_candidates(seed):
    seq=candidate_sequences(int(seed),16,16)
    if seq.shape!=(16,16): raise ValueError('shared candidate shape drifted')
    return seq
