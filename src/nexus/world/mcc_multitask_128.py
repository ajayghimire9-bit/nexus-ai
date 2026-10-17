"""Within-family MCC multitask pretrain versus scratch at 128.

The cited established lever is multitask pretraining across physics
variants within a family. That lever has not been measured for an MCC
residual world model at the 128-transition H=16 budget. This screen
does that on unused physics. Both arms use the same target RMS; the
contrast is pretrained weights versus random init. Closed xenv,
source-RMS, and residual-scale holdouts stay closed.
"""
from __future__ import annotations
import hashlib
import importlib
import json
import math
import re
import subprocess
import time
from pathlib import Path
import numpy as np
import torch
from torch import nn
import yaml
from nexus.cl.metrics import seed_level_ci
from nexus.tasks.mountaincar_continuous_family import (
    mcc_default,
    mcc_lookahead_development,
    mcc_physics_key,
)
from nexus.world.data import collect_transitions, concat_datasets
from nexus.world.dynamics import WorldModel
from nexus.world.planning_value import sha
from nexus.world.terminal_value_execution import save
from nexus.world.train import train_world_model
from nexus.world import mcc_residual_scale as scale_rung
from nexus.world import xenv_transfer as rung1

CONFIG = Path('configs/mcc_multitask_128.yaml')
PROTOCOL = Path('docs/NEXUS_MCC_MULTITASK_128_PROTOCOL.md')
ALLOCATION = Path('configs/mcc_multitask_128_allocation.json')
OUTPUT = Path('artifacts/mcc_multitask_128.json')
HOLD_RULE = 'mcc_multitask_128_v1'
PRIMARY_BUDGET = 128
N_SOURCE_PHYSICS = 3
CLOSED_INTERFACE = ((0.0029, 0.0022, 0.055), (0.0021, 0.0018, 0.055))
LOCKED_CONFIG = 'eaa07dc035afe9f21be7f0dc9d4f99c3dc0f0d7f7c179ccf395485dd32745ae7'
LOCKED_PROTOCOL = 'e3da47f78e25ef27f8296b4d6713d848dfad73709f9d044360ad5dd179c2cdcd'
N_SEEDS = 10
HORIZON = 16
N_CAND = 16
N_ACTIONS = 3
REGISTRIES = rung1.REGISTRIES
OTHER_BRANCH_BLOCKS = rung1.OTHER_BRANCH_BLOCKS + (
    63000000, 63500000, 64000000, 65000000, 66000000, 67000000, 68000000,
    69000000, 70000000, 71000000)
SEED_MARGIN = 110000
ARMS = ('multitask', 'scratch')


def source_specs():
    return (mcc_default(),) + tuple(mcc_lookahead_development()[:2])


def source_physics_keys():
    return tuple(mcc_physics_key(spec) for spec in source_specs())


def occupied_physics():
    occupied = set(scale_rung.occupied_physics())
    occupied.update(CLOSED_INTERFACE)
    occupied.update(source_physics_keys())
    return occupied


def holdout_from_rule(n=1, rule=HOLD_RULE):
    occupied = occupied_physics()
    gs = [round(x * 0.0001, 4) for x in range(15, 41)]
    ps = [round(x * 0.0001, 4) for x in range(8, 23)]
    ss = [round(x * 0.005, 3) for x in range(10, 19)]
    chosen = []; counter = 0
    while len(chosen) < int(n):
        digest = hashlib.sha256(f'{rule}:{counter}'.encode()).digest()
        idx = int.from_bytes(digest[:8], 'big')
        key = (float(gs[idx % len(gs)]), float(ps[(idx // len(gs)) % len(ps)]),
               float(ss[(idx // (len(gs) * len(ps))) % len(ss)]))
        if key not in occupied and key not in chosen:
            chosen.append(key)
        counter += 1
    return chosen


def target_spec(key):
    from nexus.tasks.mountaincar_continuous_family import _mcc
    return _mcc('mcc_multitask_128_t0', 'mcc_multitask_128',
        f'Within-family multitask-128 target gravity/power/speed {key}.',
        gravity=key[0], power=key[1], max_speed=key[2])


def continue_train(wm, train, val, *, epochs, lr, seed, batch_size=128, term_weight=.25):
    """Best-val residual training that keeps existing weights and RMS."""
    opt = torch.optim.Adam(wm.net.parameters(), lr=lr)
    mse = nn.MSELoss(); bce = nn.BCEWithLogitsLoss()
    rng = np.random.default_rng(seed)
    best = 1e18
    best_state = {k: v.detach().cpu().clone() for k, v in wm.net.state_dict().items()}

    def tensors(ds, idx=None):
        sl = slice(None) if idx is None else idx
        obs = torch.as_tensor(wm.normalize(ds.obs[sl]), dtype=torch.float32)
        nxt = torch.as_tensor(wm.normalize(ds.next_obs[sl]), dtype=torch.float32)
        act = torch.as_tensor(ds.action[sl], dtype=torch.int64)
        term = torch.as_tensor(np.asarray(ds.terminated[sl], dtype=np.float32))
        return obs, nxt, act, term

    for _epoch in range(int(epochs)):
        wm.net.train()
        for idx in rung1._batches(len(train), batch_size, rng):
            obs, nxt, act, term = tensors(train, idx)
            pred, logit = wm.net(obs, act)
            loss = mse(pred, nxt - obs) + term_weight * bce(logit.reshape(-1), term.reshape(-1))
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(wm.net.parameters(), 1.0)
            opt.step()
        wm.net.eval()
        with torch.no_grad():
            obs, nxt, act, term = tensors(val)
            pred, logit = wm.net(obs, act)
            v = float((mse(pred, nxt - obs)
                       + term_weight * bce(logit.reshape(-1), term.reshape(-1))).item())
        if v < best:
            best = v
            best_state = {k: t.detach().cpu().clone() for k, t in wm.net.state_dict().items()}
    wm.net.load_state_dict(best_state)
    wm.net.eval()
    return dict(best_val=best)


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    locked = dict(starting_sha='954beb19f03a1a6054843593088270c00fba4caa',
        n_model_seeds=10, source_family='mountaincar_continuous',
        target_family='mountaincar_continuous', holdout_rule=HOLD_RULE,
        target_budget=PRIMARY_BUDGET, n_source_physics=N_SOURCE_PHYSICS,
        source_train=512, target_train=128, target_val=32,
        pretrain_epochs=15, train_epochs=20, train_lr=.001, term_weight=.25,
        batch_size=128, hidden=[64, 64], horizon=HORIZON, n_candidates=N_CAND,
        n_actions=N_ACTIONS, episode_steps=200, practical_margin=0.0,
        time_cap_s=600, env_cap=20960, model_cap=1024000,
        reset_base=72000000, step_seed_base=72100000,
        collect_source_base=72200000, collect_target_base=72300000,
        cross_family_weights=False, new_architecture_family=False,
        retune_from_closed_splits=False, claims_learning_to_learn=False, is_agi=False)
    for key, value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError('locked multitask-128 design/budget changed')
    if [list(k) for k in source_physics_keys()] != cfg['source_physics']:
        raise ValueError('locked source physics drifted')
    if holdout_from_rule() != [tuple(cfg['target_physics'][0])]:
        raise ValueError('multitask-128 rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('multitask-128 target collides with occupied MountainCarContinuous physics')
    spec = target_spec(tuple(cfg['target_physics'][0]))
    if spec.family != 'mountaincar_continuous' or spec.n_actions != N_ACTIONS:
        raise ValueError('multitask-128 target is not MountainCarContinuous')
    for file, digest in cfg['parents'].items():
        if sha(file) != digest:
            raise ValueError(f'closed parent changed: {file}')
    if sha(CONFIG) != LOCKED_CONFIG:
        raise ValueError('locked configuration hash drifted')
    if sha(PROTOCOL) != LOCKED_PROTOCOL:
        raise ValueError('locked protocol hash drifted')
    budget(cfg); check_seeds(cfg)
    return cfg


def check_seeds(cfg):
    blocked = set()
    for name in REGISTRIES:
        module = importlib.import_module(f'nexus.world.{name}')
        other = yaml.safe_load(module.CONFIG.read_text())
        if hasattr(module, 'seed_groups'):
            blocked |= set().union(*module.seed_groups(other))
    for path in Path('configs').glob('*.yaml'):
        if path.name == CONFIG.name:
            continue
        for value in re.findall(r'[a-z_]*base:\s*(\d+)', path.read_text()):
            blocked |= {int(value) + i for i in range(SEED_MARGIN)}
    used = {cfg['reset_base'] + 100 * s + slot for s in range(N_SEEDS) for slot in range(2)}
    used |= {cfg['step_seed_base'] + 1000 * s + 100 * slot + k for s in range(N_SEEDS)
             for slot in range(2) for k in range(200)}
    used |= {cfg['collect_source_base'] + 120 * s + i for s in range(N_SEEDS) for i in range(120)}
    used |= {cfg['collect_target_base'] + 40 * s + i for s in range(N_SEEDS) for i in range(40)}
    if used & blocked:
        raise ValueError('multitask-128 seeds collide with a closed experiment')
    if min(used) < cfg['reset_base']:
        raise ValueError('seed block drifted below the locked base')
    for base in OTHER_BRANCH_BLOCKS:
        if any(base <= u < base + 300000 for u in used):
            raise ValueError('multitask-128 seeds collide with another live branch block')


def budget(cfg):
    source = int(cfg['n_source_physics']) * int(cfg['source_train']) * N_SEEDS
    target = (int(cfg['target_train']) + int(cfg['target_val'])) * N_SEEDS
    evaluation = 2 * N_SEEDS * int(cfg['episode_steps'])
    imagined = evaluation * HORIZON * N_CAND
    if source + target + evaluation != cfg['env_cap']:
        raise ValueError('multitask-128 env-step allocation mismatch')
    if imagined != cfg['model_cap']:
        raise ValueError('multitask-128 imagined allocation mismatch')
    if int(cfg['target_train']) != PRIMARY_BUDGET:
        raise ValueError('multitask-128 primary budget drifted')
    if int(cfg['n_source_physics']) != N_SOURCE_PHYSICS:
        raise ValueError('multitask-128 source-physics count drifted')
    return dict(source_collection=source, target_pool=target, evaluation_episodes=evaluation,
                imagined=imagined, time_cap_s=cfg['time_cap_s'])


def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'mcc_multitask_128_beats_scratch'
    if mean < 0 and hi < 0:
        return 'mcc_multitask_128_harm_established'
    return 'mcc_multitask_128_not_established'


def summarize(cells, cfg):
    rows = {int(c['seed']): c for c in cells}
    if set(rows) != set(range(N_SEEDS)):
        raise ValueError('incomplete multitask-128 seed grid')
    diffs = [float(rows[s]['returns']['multitask']) - float(rows[s]['returns']['scratch'])
             for s in range(N_SEEDS)]
    primary = seed_level_ci(diffs)
    label = classify_primary(primary['mean'], primary['lo'], primary['hi'], N_SEEDS, True)
    mae = seed_level_ci([float(rows[s]['mae']['multitask']) - float(rows[s]['mae']['scratch'])
                         for s in range(N_SEEDS)])
    returns = {arm: seed_level_ci([float(rows[s]['returns'][arm]) for s in range(N_SEEDS)])
               for arm in ARMS}
    return dict(label=label, groups=dict(primary=dict(per_seed=diffs, interval=primary,
        budget=PRIMARY_BUDGET), mae_gain=mae, arm_return=returns))


def execute():
    cfg = load_config(); require_allocation(cfg)
    if OUTPUT.exists():
        raise RuntimeError('refusing multitask-128 overwrite')
    if subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip():
        raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git', 'merge-base', '--is-ancestor', cfg['starting_sha'], 'HEAD'], check=True)
    from nexus.tasks.spec import make_task_env
    torch.set_num_threads(1)
    started = time.perf_counter(); meter = rung1.Meter(cfg)
    key = holdout_from_rule()[0]
    spec = target_spec(key)
    priors = source_specs()
    p = dict(complete=False, label='incomplete', cells=[], parents=cfg['parents'],
        implementation_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        config_sha256=sha(CONFIG), protocol_sha256=sha(PROTOCOL), allocation_sha256=sha(ALLOCATION),
        source_dirty=False, target_physics=list(key), holdout_rule=HOLD_RULE,
        source_physics=[list(k) for k in source_physics_keys()],
        new_environment_interactions=cfg['env_cap'], imagined_transitions=cfg['model_cap'],
        cross_family_weights=False, is_agi=False, claims_learning_to_learn=False)
    p['code_hashes'] = {f: sha(f) for f in (
        'src/nexus/world/mcc_multitask_128.py', 'src/nexus/world/train.py',
        'src/nexus/world/dynamics.py', 'src/nexus/world/data.py',
        'src/nexus/world/planning.py', 'src/nexus/world/xenv_transfer.py')}
    try:
        for s in range(N_SEEDS):
            meter.check()
            parts = []
            for i, prior in enumerate(priors):
                B = cfg['collect_source_base'] + 120 * s + 40 * i
                ds = collect_transitions(prior, n_transitions=int(cfg['source_train']),
                    env_seeds=tuple(range(B, B + 6)), base_seed=B + 6,
                    mix=('random', 'exploratory'))
                meter.collect(int(cfg['source_train']))
                parts.append(ds)
            source = concat_datasets(*parts, task_id='mcc_multitask_source')
            source_train = source.slice(np.arange(len(source) - 32, dtype=np.int64))
            source_val = source.slice(np.arange(len(source) - 32, len(source), dtype=np.int64))
            if len(source_train) != 1504 or len(source_val) != 32:
                raise ValueError('multitask-128 source split drifted')
            source_rms = rung1.fit_rms(source_train.obs)
            B2 = cfg['collect_target_base'] + 40 * s
            train = collect_transitions(spec, n_transitions=int(cfg['target_train']),
                env_seeds=tuple(range(B2, B2 + 6)), base_seed=B2 + 6,
                mix=('random', 'exploratory'))
            val = collect_transitions(spec, n_transitions=int(cfg['target_val']),
                env_seeds=(B2 + 8, B2 + 9), base_seed=B2 + 10,
                mix=('random', 'exploratory'))
            meter.collect(int(cfg['target_train']) + int(cfg['target_val']))
            if len(train) != int(cfg['target_train']) or len(val) != int(cfg['target_val']):
                raise ValueError('multitask-128 target prefix length drifted')
            target_rms = rung1.fit_rms(train.obs)
            multi, _pre = train_world_model(source_train, source_val, kind='residual',
                epochs=int(cfg['pretrain_epochs']), lr=cfg['train_lr'],
                seed=5 + 19 * s, n_actions=spec.n_actions, hidden=(64, 64),
                obs_rms=source_rms, freeze_rms=True)
            multi.copy_rms(target_rms)
            continue_train(multi, train, val, epochs=int(cfg['train_epochs']),
                lr=cfg['train_lr'], seed=7 + 19 * s)
            scratch, _log = train_world_model(train, val, kind='residual',
                epochs=int(cfg['train_epochs']), lr=cfg['train_lr'],
                seed=5 + 19 * s, n_actions=spec.n_actions, hidden=(64, 64),
                obs_rms=target_rms, freeze_rms=True)
            cell = dict(seed=s, returns={}, mae={}, traces={})
            for arm, model, slot in (('multitask', multi, 0), ('scratch', scratch, 1)):
                env = make_task_env(spec)
                try:
                    trace = rung1.h16_rollout(env, model, cfg, s, slot, meter)
                finally:
                    env.close()
                cell['returns'][arm] = trace['episode_return']
                cell['traces'][arm] = trace
                cell['mae'][arm] = rung1.prediction_mae(model, val)
            if any(not np.isfinite(v) for v in cell['returns'].values()):
                raise ValueError('nonfinite multitask-128 return')
            p['cells'].append(cell)
            print(f'seed={s} seconds={time.perf_counter()-started:.1f}', flush=True)
        p.update(summarize(p['cells'], cfg))
        if meter.env_steps != cfg['env_cap'] or meter.model_states != cfg['model_cap']:
            raise ValueError('multitask-128 totals inconsistent with the locked budget')
        meter.check(); p['complete'] = True
    except Exception as exc:
        p['label'] = 'incomplete'
        p['failure'] = dict(type=type(exc).__name__, message=str(exc))
        print('INCOMPLETE', p['failure'], flush=True)
    p['wall_clock_s'] = time.perf_counter() - started
    p['counts'] = dict(env_steps=meter.env_steps, model_states=meter.model_states)
    save(OUTPUT, p)
    return p


def audit_results():
    cfg = load_config(); p = json.loads(OUTPUT.read_text())
    if p.get('complete') is not True:
        raise RuntimeError('incomplete/invalid multitask-128 evaluation')
    rebuilt = summarize(p['cells'], cfg)
    if p['label'] != rebuilt['label']:
        raise ValueError('saved label differs')
    if p.get('claims_learning_to_learn') is not False or p.get('is_agi') is not False:
        raise ValueError('forbidden claim flags drifted')
    if p.get('cross_family_weights') is not False:
        raise ValueError('multitask-128 must not share cross-family weights')
    n_traces = 0
    for row in p['cells']:
        for arm, trace in row['traces'].items():
            n_traces += 1
            if not np.isclose(math.fsum(trace['rewards']), trace['episode_return'], atol=1e-8):
                raise ValueError('multitask-128 reward reconstruction drifted')
            if not np.isclose(trace['episode_return'], row['returns'][arm], atol=1e-8):
                raise ValueError('multitask-128 trace/return mismatch')
            if int(trace['n_steps']) > cfg['episode_steps']:
                raise ValueError('multitask-128 episode length exceeded 200')
    if n_traces != 20:
        raise ValueError('multitask-128 20-trace grid drifted')
    if int(p['counts']['env_steps']) != cfg['env_cap'] or int(p['counts']['model_states']) != cfg['model_cap']:
        raise ValueError('multitask-128 execution totals drifted')
    return dict(audit_passed=True, label=p['label'], raw_sha256=sha(OUTPUT),
        groups=p['groups'], n_traces=n_traces,
        new_environment_steps=int(p['counts']['env_steps']),
        new_imagined_transitions=int(p['counts']['model_states']),
        target_physics=p['target_physics'], is_agi=False,
        claims_learning_to_learn=False, cross_family_weights=False)


def prep():
    cfg = load_config()
    record = load_allocation()
    if record.get('authorized') is True or int(record.get('runs', 0)) != 0:
        raise PermissionError('prep refuses an already authorized allocation')
    return dict(complete=True, authorized=False, runs=0, new_environment_steps=0,
        new_imagined_transitions=0, config_sha256=sha(CONFIG),
        protocol_sha256=sha(PROTOCOL), allocation_sha256=sha(ALLOCATION),
        target_physics=list(holdout_from_rule()[0]), holdout_rule=HOLD_RULE,
        source_physics=[list(k) for k in source_physics_keys()],
        proposed_budget=budget(cfg), arms=list(ARMS),
        labels=('mcc_multitask_128_beats_scratch', 'mcc_multitask_128_harm_established',
                'mcc_multitask_128_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False, cross_family_weights=False,
        note='No collection. Interface-transplant and xenv holdouts untouched.')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=600, env_cap=20960, model_cap=1024000).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('multitask-128 allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before multitask-128 collection')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s']) < cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')
