"""Preparation helpers only. No experiment is launched by this module.

The configuration is an approval proposal, not a runtime authorization.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import statistics
import subprocess
import time
from pathlib import Path

import numpy as np
import yaml

CONFIG = Path('configs/long_continuation.yaml')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    if cfg['decoders'] != list(range(10)) or cfg['students'] != list(range(5)):
        raise ValueError('independent decoder/student grid changed')
    if (cfg['phases'], cfg['continuation_steps'], cfg['horizon'], cfg['candidates']) != ([50,100],64,16,16):
        raise ValueError('registered phases, continuation or controller changed')
    if len(cfg['tasks']) != 4 or cfg['harvest_steps'] != max(cfg['phases'])+1:
        raise ValueError('harvest grid drift')
    if any(p+cfg['continuation_steps']>cfg['max_episode_steps'] for p in cfg['phases']):
        raise ValueError('continuation crosses original episode boundary')
    for path,key in [('parent_artifact','parent_sha256'),('manifest','manifest_sha256')]:
        if digest(cfg[path]) != cfg[key]:
            raise ValueError(f'closed evidence changed: {path}')
    return cfg


def state_seed(cfg, kind, task, phase_index, slot):
    return cfg[kind+'_seed_base']+task*4096+phase_index*1024+slot*128


def proposed_seeds(cfg):
    # Live conditions deliberately share the initial state and candidate stream.
    groups={k:{cfg[k+'_seed_base']+t*100 for t in range(4)} for k in ('env','planner')}
    for kind in ('candidate','common','policy'):
        width=1 if kind=='candidate' else cfg['continuation_steps']
        groups[kind]={state_seed(cfg,kind,t,p,s)+k for t,p,s,k in
                      itertools.product(range(4),range(2),range(6),range(width))}
    return groups


def assert_unused_seeds(cfg):
    from nexus.world.prediction_control_gap import diagnostic_seed_groups, load_prediction_config
    from nexus.world.receding_horizon import horizon_seed_groups, load_horizon_config
    from nexus.world.return_phase import phase_seed_groups, load_phase_config
    from nexus.world.late_control_gap_design import design_seed_groups
    occupied, diagnostic=diagnostic_seed_groups(load_prediction_config())
    blocked=set()
    for collection in (occupied,diagnostic,horizon_seed_groups(load_horizon_config()),
                       phase_seed_groups(load_phase_config()),design_seed_groups()):
        for seeds in collection.values(): blocked.update(seeds)
    for kind,seeds in proposed_seeds(cfg).items():
        if seeds & blocked: raise ValueError(f'{kind} reuses a closed seed')
        blocked.update(seeds)


def budget(cfg):
    d,t,s,p=len(cfg['decoders']),len(cfg['tasks']),len(cfg['students']),len(cfg['phases'])
    states=d*t*(s+1)*p
    paired_cells=d*t*p*2*s
    # Student visits: 5 pairs, zero visits: 5 students plus one cached zero.
    full_branches=d*t*p*(2*s+s+1)
    live=d*t*(s+1)*cfg['harvest_steps']
    h=cfg['continuation_steps']; plan=cfg['horizon']*cfg['candidates']
    env={'support':t*128,'harvest':live,'common':states*3*h,'full_policy':full_branches*h}
    models={'harvest':live*plan,'live_replay':states*plan,
            'shared_scoring':full_branches*plan,
            'common':states*3*(h-1)*plan,'full_policy':full_branches*h*plan}
    total_models=sum(models.values())
    return {'restored_states':states,'paired_cells':paired_cells,
            'env_by_bucket':env,'env_steps':sum(env.values()),
            'model_by_bucket':models,'model_states':total_models,
            'runtime_estimate_s':557.8021487079986*total_models/34734080,
            'hard_cap_s':cfg['time_cap_s'],'estimate_is_not_measured':True}


def require_budget_approval(approved_config_sha256=None):
    """Fail before importing any simulation path unless a human-approved lock matches.

    Callers must obtain human approval; passing a digest is not permission by itself.
    """
    expected=digest(CONFIG)
    if approved_config_sha256 != expected:
        raise PermissionError(f'simulation budget awaits human approval for config {expected}')
    return expected


def split_rewards(rewards, split=16, horizon=64):
    arr=np.asarray(rewards,dtype=np.float64)
    if arr.shape != (horizon,) or not np.isfinite(arr).all():
        raise ValueError('required complete finite reward trace')
    early=float(arr[:split].sum()); late=float(arr[split:].sum()); total=float(arr.sum())
    if not math.isclose(early+late,total,abs_tol=1e-9,rel_tol=1e-12):
        raise ValueError('reward identity failed')
    return {'early':early,'late':late,'total':total}


def continuation_trace(env, model, state, seeds, *, first_action=None, horizon=64):
    """Reusable rollout primitive; only called after approval by a future driver.

    first_action=None: full policy. Otherwise commit it then replan with the supplied
    model. A zero-context model must be supplied for the common-policy intervention.
    """
    if len(seeds)!=horizon: raise ValueError('continuation RNG length mismatch')
    from nexus.world.receding_horizon import restore_state, _context_snapshot, _same_context, _reward_ok
    from nexus.world.planning import mpc_for_model
    snapshot=_context_snapshot(model)
    if first_action is not None:
        if first_action not in (0,1,2) or bool((snapshot != 0).any()):
            raise ValueError('common continuation requires a valid first action and exact zero context')
    obs=restore_state(env,state)
    rewards=[]; actions=[]
    planner=mpc_for_model(model,seed=seeds[0],enforce_time_budget=False)
    for k,seed in enumerate(seeds):
        if k==0 and first_action is not None:
            action=int(first_action)
        else:
            planner.reset_episode(int(seed))
            action,info=planner.act(obs)
            if info['n_scored']!=16: raise ValueError('candidate budget drift')
        nxt,reward,term,trunc,_=env.step(int(action))
        _reward_ok(obs,action,nxt,reward)
        _same_context(model,snapshot)
        rewards.append(float(reward)); actions.append(int(action)); obs=nxt
        if (term or trunc) and k<horizon-1: raise ValueError('short continuation')
    return {'rewards':rewards,'actions':actions,**split_rewards(rewards,horizon=horizon)}


def paired_interval(values):
    if len(values)!=10 or any(type(v) not in (float,int) or not math.isfinite(v) for v in values):
        raise ValueError('ten finite independent decoder values required')
    mean=statistics.mean(values); se=statistics.stdev(values)/math.sqrt(10)
    return {'n':10,'df':9,'mean':mean,'lo':mean-2.262*se,'hi':mean+2.262*se}


def audit_parent(payload):
    """Recompute raw selected-action contrasts independently of the old aggregator.

    This is an arithmetic/provenance audit, not an independent experiment/reviewer.
    """
    expected=set(itertools.product(range(10),range(4),(16,50,100,150),('student','zero'),range(5)))
    raw={}
    for state in payload['states']:
        d,t,p,slot=(state[k] for k in ('decoder','task','phase','slot'))
        if not state['capture']['reproduced']: raise ValueError('recorded live replay failure')
        ev=state['evaluated']; zero=ev['zero']; common=ev['continuation']
        for student in (range(5) if slot==5 else [slot]):
            a=ev[str(student)]
            primary=common[a['first_action']]-common[zero['first_action']]
            if not math.isclose(primary,a['continuation_return']-zero['continuation_return'],abs_tol=1e-10):
                raise ValueError('selected-action indexing mismatch')
            key=(d,t,p,'zero' if slot==5 else 'student',student)
            if key in raw: raise ValueError('duplicate raw state comparison')
            raw[key]=primary
    if set(raw)!=expected: raise ValueError('raw planned comparison grid incomplete')
    cells={}
    for row in payload['cells']:
        key=tuple(row[k] for k in ('decoder','task','phase','visitor','student'))
        if key in cells: raise ValueError('duplicate aggregate cell')
        if type(row['primary']) not in (int,float) or not math.isfinite(row['primary']):
            raise ValueError('invalid cell')
        cells[key]=row['primary']
    if set(cells)!=expected: raise ValueError('saved comparison grid incomplete')
    for key,value in raw.items():
        if not math.isclose(value,cells[key],abs_tol=1e-10): raise ValueError('raw/cell mismatch')
    values=[sum(raw[(d,t,p,v,s)]/(4*4*2*5) for t,p,v,s in
                itertools.product(range(4),(16,50,100,150),('student','zero'),range(5))) for d in range(10)]
    ci=paired_interval(values)
    reported=payload['comparisons']['primary']['interval']
    if any(not math.isclose(ci[k],reported[k],abs_tol=1e-10) for k in ('mean','lo','hi')):
        raise ValueError('decoder interval mismatch')
    episode_keys=set()
    for episode in payload['episodes']:
        key=tuple(episode[k] for k in ('decoder','task','slot'))
        if key in episode_keys: raise ValueError('duplicate harvested episode')
        episode_keys.add(key)
        if len(episode['rewards'])!=200 or not math.isclose(sum(episode['rewards']),episode['return'],abs_tol=1e-8):
            raise ValueError('live reward accounting mismatch')
    if episode_keys!=set(itertools.product(range(10),range(4),range(6))):
        raise ValueError('harvested episode grid incomplete')
    frozen_keys=[(r['decoder'],r['task']) for r in payload['frozen_checks']]
    if set(frozen_keys)!=set(itertools.product(range(10),range(4))) or len(frozen_keys)!=40:
        raise ValueError('frozen-check grid incomplete')
    if len(payload['frozen_checks'])!=40 or any(r['before']!=r['after'] for r in payload['frozen_checks']):
        raise ValueError('frozen model mismatch')
    return {'audit_passed':True,'primary_recomputed':ci,'per_decoder':values,
            'raw_comparisons':len(raw),'new_environment_steps':0,
            'limitations':['Continuation per-step rewards were not saved in the parent artifact; their sums cannot be independently rederived.',
                          'This audit checks saved evidence and code provenance; it is not external replication.',
                          'Restoring elapsed time to zero is safe for these 16-step Pendulum windows, not arbitrary environments.']}


def prepare():
    started=time.perf_counter()
    cfg=load_config(); assert_unused_seeds(cfg)
    parent=json.loads(Path(cfg['parent_artifact']).read_text())
    audit=audit_parent(parent)
    protocol_bytes=subprocess.check_output(['git','show',parent['implementation_sha']+':docs/NEXUS_LATE_CONTROL_GAP_RESULTS.md'])
    if hashlib.sha256(protocol_bytes).hexdigest()!=parent['protocol_sha256']:
        raise ValueError('execution protocol provenance mismatch')
    return {'status':'awaiting_budget_approval','config_sha256':digest(CONFIG),
            'implementation_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'source_dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
            'parent_sha256':digest(cfg['parent_artifact']),'manifest_sha256':digest(cfg['manifest']),
            'preparation_wall_s':time.perf_counter()-started,
            'proposed_budget':budget(cfg),'parent_audit':audit,'new_environment_steps':0,
            'new_model_training':False,'simulation_executed':False}


RESULT_METRICS = tuple(f'{policy}_{window}' for policy in ('full','common') for window in ('early','late','total'))


def validate_result_grid(rows, cfg):
    """Validate planned cells before aggregation; never infer expected IDs from output."""
    axes=('decoder','task','phase','visitor','student')
    expected=set(itertools.product(cfg['decoders'],range(len(cfg['tasks'])),cfg['phases'],
                                   ('student','zero'),cfg['students']))
    indexed={}
    for row in rows:
        for name in ('decoder','task','phase','student'):
            if type(row.get(name)) is not int:
                raise ValueError(f'{name} must be an integer identifier')
        key=tuple(row.get(k) for k in axes)
        if key not in expected or key in indexed:
            raise ValueError(f'unplanned or duplicate result cell: {key}')
        for metric in RESULT_METRICS:
            value=row.get(metric)
            if type(value) not in (int,float) or not math.isfinite(value):
                raise ValueError(f'missing or invalid result metric: {key} {metric}')
        for policy in ('full','common'):
            if not math.isclose(row[policy+'_early']+row[policy+'_late'],row[policy+'_total'],rel_tol=1e-12,abs_tol=1e-8):
                raise ValueError('paired reward decomposition failed')
        indexed[key]=row
    if set(indexed)!=expected:
        raise ValueError(f'incomplete result grid: {len(indexed)}/{len(expected)}')
    return indexed


def summarize_result_grid(rows, cfg):
    indexed=validate_result_grid(rows,cfg)
    summary={}
    for metric in RESULT_METRICS:
        decoder_values=[]
        for decoder in cfg['decoders']:
            task_values=[]
            for task in range(len(cfg['tasks'])):
                phase_values=[]
                for phase in cfg['phases']:
                    visitors=[]
                    for visitor in ('student','zero'):
                        visitors.append(statistics.mean(indexed[(decoder,task,phase,visitor,s)][metric]
                                                        for s in cfg['students']))
                    phase_values.append(statistics.mean(visitors))
                task_values.append(statistics.mean(phase_values))
            decoder_values.append(float(statistics.mean(task_values)))
        summary[metric]={'per_decoder':decoder_values,'interval':paired_interval(decoder_values)}
    ci=summary['full_late']['interval']
    if ci['lo']<=0<=ci['hi']:
        label='long_policy_tail_unseparated'
    elif ci['hi']<0:
        label='long_policy_tail_worse' if ci['mean']<=-cfg['practical_margin'] else 'long_policy_tail_below_margin'
    else:
        label='long_policy_tail_favors_student'
    return {'complete_metric_grid':True,'primary_label':label,'comparisons':summary,
            'execution_integrity_still_required':True}
