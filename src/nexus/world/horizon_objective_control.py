"""Nested H=8 scoring versus archived H=16 receding. Collection unauthorized."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import yaml
from nexus.world import late_episode_decision_trajectory as late
from nexus.world.planning import RandomShootingMPC
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.rewards import pendulum_step_reward
from nexus.world.long_continuation import paired_interval

CONFIG=Path('configs/horizon_objective_control.yaml')
PROTOCOL=Path('docs/NEXUS_HORIZON_OBJECTIVE_CONTROL_PROTOCOL.md')
ALLOCATION=Path('configs/horizon_objective_control_allocation.json')
OUTPUT=Path('artifacts/horizon_objective_control.json')
PRIMARY='return_gain'
SCORE_H=8
CAND_H=16


def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(decoders=list(range(10)),students=list(range(5)),eval_tasks=3,visitors=2,
                candidate_horizon=CAND_H,score_horizon=SCORE_H,n_candidates=16,n_actions=3,
                episode_steps=200,phase=0,practical_margin=25.0,time_cap_s=90,env_cap=12000,
                model_cap=1536000,reset_base=11000000,step_seed_base=11100000,
                paired_late_episode_seeds=True,reuse_archived_h16_returns=True,
                three_action_counterfactuals=False,matched_state_first_action_forks=False,
                starting_sha='a9ada15ac3ae758b75187074aaae98eab089d2a9')
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:raise ValueError('locked H=8 design/budget changed')
    late_cfg=late.load_config()
    if cfg['reset_base']!=late_cfg['reset_base'] or cfg['step_seed_base']!=late_cfg['step_seed_base']:
        raise ValueError('H=8 seeds must pair with the archived H=16 traces')
    if cfg['eval_task_ids']!=late_cfg['eval_task_ids'] or cfg['eval_physics']!=late_cfg['eval_physics']:
        raise ValueError('development physics drifted')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest:raise ValueError('closed parent changed')
    budget(cfg)
    return cfg


def budget(cfg):
    counts=dict(episode=10*3*2*200,model_states=10*3*2*200*16*SCORE_H)
    if counts['episode']!=cfg['env_cap'] or counts['model_states']!=cfg['model_cap']:
        raise ValueError('H=8 resource allocation mismatch')
    return counts


def nested_candidates(seed):
    seq=candidate_sequences(int(seed),16,CAND_H)
    prefix=seq[:,:SCORE_H]
    if prefix.shape!=(16,SCORE_H): raise ValueError('nested prefix shape drifted')
    return seq,prefix


def score_prefix(model,obs,prefix):
    prefix=np.asarray(prefix,dtype=np.int64)
    if prefix.shape!=(16,SCORE_H): raise ValueError('H=8 prefix is not 16x8')
    planner=RandomShootingMPC(model=model,n_actions=3,horizon=SCORE_H,n_candidates=16,seed=0,
                              objective='predicted_reward',step_reward=pendulum_step_reward,
                              enforce_time_budget=False)
    scores=np.asarray(planner._score_batch(np.asarray(obs,dtype=np.float32),prefix),dtype=np.float64)
    if scores.shape!=(16,): raise RuntimeError('planner dropped a candidate')
    return scores


def archived_h16_returns():
    payload=json.loads(late.OUTPUT.read_text())
    if payload.get('complete') is not True: raise ValueError('archived H=16 capture is incomplete')
    out={}
    for cell in payload['cells']:
        out[(int(cell['decoder']),int(cell['task']))]=dict(
            student=float(cell['metrics']['return_student']),zero=float(cell['metrics']['return_zero']))
    if len(out)!=30: raise ValueError('archived H=16 grid drifted')
    return out


def classify_primary(mean,lo,hi,n,complete=True,margin=25.0):
    if not complete or int(n)!=10: return 'incomplete'
    if mean>=margin and lo>0: return 'shorter_horizon_improves_episode_return'
    if mean<=-margin and hi<0: return 'shorter_horizon_hurts_episode_return'
    return 'shorter_horizon_not_established'


def load_allocation():
    record=json.loads(ALLOCATION.read_text())
    for key,value in dict(time_cap_s=90,env_cap=12000,model_cap=1536000).items():
        if type(record.get(key)) is not type(value) or record[key]!=value:raise ValueError('H=8 allocation drift')
    return record


def require_allocation(cfg):
    record=load_allocation()
    if record.get('authorized') is not True or int(record.get('runs',0))!=1:
        raise PermissionError('fresh human approval required before H=8 collection')
    if sha(CONFIG)!=record.get('config_sha256'):
        raise PermissionError('allocation does not bind this configuration hash')


def decoder_gain(h8_rows,archived):
    values=[]
    for d in range(10):
        xs=[]
        for t in range(3):
            arch=archived[(d,t)]; row=h8_rows[(d,t)]
            xs.append(0.5*((row['student']-arch['student'])+(row['zero']-arch['zero'])))
        values.append(float(sum(xs)/3.0))
    return paired_interval(values)
