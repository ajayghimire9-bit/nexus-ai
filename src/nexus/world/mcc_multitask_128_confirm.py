"""Same-design confirmation of H10 on unused MCC physics. No collection here.

Freezes the H10 residual recipe, three source physics, target-RMS treatment,
128-transition budget, matched scratch, and H=16 planner. Only the holdout
and seed block change. Closed H10 data are not rewritten.
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
import yaml
from nexus.cl.metrics import seed_level_ci
from nexus.world.data import collect_transitions, concat_datasets
from nexus.world.planning_value import sha
from nexus.world.terminal_value_execution import save
from nexus.world.train import train_world_model
from nexus.world import mcc_multitask_128 as base
from nexus.world import xenv_transfer as rung1

CONFIG = Path('configs/mcc_multitask_128_confirm.yaml')
PROTOCOL = Path('docs/NEXUS_MCC_MULTITASK_128_CONFIRM_PROTOCOL.md')
ALLOCATION = Path('configs/mcc_multitask_128_confirm_allocation.json')
OUTPUT = Path('artifacts/mcc_multitask_128_confirm.json')
HOLD_RULE = 'mcc_multitask_128_confirm_v1'
CLOSED_H10 = (0.0032, 0.0022, 0.06)
FROZEN_H10_CODE = '79a26fed3d0b4a852cd8194492ae67977af41965a56effc01d7441b006dfc701'
FROZEN_H10_CONFIG = 'eaa07dc035afe9f21be7f0dc9d4f99c3dc0f0d7f7c179ccf395485dd32745ae7'
FROZEN_H10_PROTOCOL = 'e3da47f78e25ef27f8296b4d6713d848dfad73709f9d044360ad5dd179c2cdcd'
FROZEN_H10_RAW = 'caca746457eb72e89c95b6f8b9cd82c7cf06cff68713ff1d9ad8a98519e4d274'
FROZEN_H10_REPORT = '9c8f0274ed3778f4197319e74217427a1432d05658b21c59676652eb4143d480'
LOCKED_CONFIG = '82720142eac6cc2251303590a44abc6ba878b2ca3e1d128fb9874532a0dc47fe'
LOCKED_PROTOCOL = '4c6507dde8171f5acac1b618506666856cfcf21f0bfc156c0ca91d9cc7d82b7b'
PRIMARY_BUDGET = base.PRIMARY_BUDGET
N_SOURCE_PHYSICS = base.N_SOURCE_PHYSICS
N_SEEDS = base.N_SEEDS
HORIZON = base.HORIZON
N_CAND = base.N_CAND
N_ACTIONS = base.N_ACTIONS
REGISTRIES = base.REGISTRIES
OTHER_BRANCH_BLOCKS = base.OTHER_BRANCH_BLOCKS + (72_000_000,)
SEED_MARGIN = base.SEED_MARGIN
ARMS = base.ARMS
FROZEN_H10_FIELDS = (
    'n_model_seeds', 'source_family', 'target_family', 'target_budget',
    'n_source_physics', 'source_train', 'target_train', 'target_val',
    'pretrain_epochs', 'train_epochs', 'train_lr', 'term_weight', 'batch_size',
    'hidden', 'horizon', 'n_candidates', 'n_actions', 'episode_steps',
    'practical_margin', 'time_cap_s', 'env_cap', 'model_cap',
    'cross_family_weights', 'new_architecture_family', 'retune_from_closed_splits',
    'claims_learning_to_learn', 'is_agi',
)


def source_specs():
    return base.source_specs()


def source_physics_keys():
    return base.source_physics_keys()


def occupied_physics():
    occupied = set(base.occupied_physics())
    occupied.add(CLOSED_H10)
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
    return _mcc('mcc_multitask_128_cf0', 'mcc_multitask_128_confirm',
        f'Within-family multitask-128 confirmation target {key}.',
        gravity=key[0], power=key[1], max_speed=key[2])


def assert_h10_frozen():
    if sha('src/nexus/world/mcc_multitask_128.py') != FROZEN_H10_CODE:
        raise ValueError('H10 implementation drifted')
    if sha(base.CONFIG) != FROZEN_H10_CONFIG:
        raise ValueError('H10 configuration drifted')
    if sha(base.PROTOCOL) != FROZEN_H10_PROTOCOL:
        raise ValueError('H10 protocol drifted')
    if sha(base.OUTPUT) != FROZEN_H10_RAW:
        raise ValueError('closed H10 artifact drifted')
    if sha('docs/NEXUS_MCC_MULTITASK_128_RESULTS.md') != FROZEN_H10_REPORT:
        raise ValueError('closed H10 report drifted')
    if base.holdout_from_rule() != [CLOSED_H10]:
        raise ValueError('H10 holdout drifted')
    if base.source_physics_keys() != source_physics_keys():
        raise ValueError('confirmation source physics drifted from H10')


def load_config():
    assert_h10_frozen()
    cfg = yaml.safe_load(CONFIG.read_text())
    h10 = yaml.safe_load(base.CONFIG.read_text())
    locked = dict(starting_sha='5f8cda330194786dfe450292ba34a01e7b42540c',
        n_model_seeds=10, source_family='mountaincar_continuous',
        target_family='mountaincar_continuous', holdout_rule=HOLD_RULE,
        target_budget=PRIMARY_BUDGET, n_source_physics=N_SOURCE_PHYSICS,
        source_train=512, target_train=128, target_val=32,
        pretrain_epochs=15, train_epochs=20, train_lr=.001, term_weight=.25,
        batch_size=128, hidden=[64, 64], horizon=HORIZON, n_candidates=N_CAND,
        n_actions=N_ACTIONS, episode_steps=200, practical_margin=0.0,
        time_cap_s=600, env_cap=20960, model_cap=1024000,
        reset_base=73000000, step_seed_base=73100000,
        collect_source_base=73200000, collect_target_base=73300000,
        cross_family_weights=False, new_architecture_family=False,
        retune_from_closed_splits=False, claims_learning_to_learn=False, is_agi=False)
    for key, value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError('locked multitask-128 confirmation design/budget changed')
    for key in FROZEN_H10_FIELDS:
        if cfg[key] != h10[key]:
            raise ValueError(f'confirmation hyperparameter drifted from H10: {key}')
    if cfg['source_physics'] != h10['source_physics']:
        raise ValueError('confirmation source physics drifted from H10')
    if [list(k) for k in source_physics_keys()] != cfg['source_physics']:
        raise ValueError('locked source physics drifted')
    if holdout_from_rule() != [tuple(cfg['target_physics'][0])]:
        raise ValueError('confirmation rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('confirmation target collides with occupied MountainCarContinuous physics')
    if tuple(cfg['target_physics'][0]) == CLOSED_H10:
        raise ValueError('confirmation must not reuse the H10 holdout')
    spec = target_spec(tuple(cfg['target_physics'][0]))
    if spec.family != 'mountaincar_continuous' or spec.n_actions != N_ACTIONS:
        raise ValueError('confirmation target is not MountainCarContinuous')
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
        raise ValueError('confirmation seeds collide with a closed experiment')
    if min(used) < cfg['reset_base']:
        raise ValueError('seed block drifted below the locked base')
    for base_id in OTHER_BRANCH_BLOCKS:
        if any(base_id <= u < base_id + 300000 for u in used):
            raise ValueError('confirmation seeds collide with another live branch block')
    h10 = yaml.safe_load(base.CONFIG.read_text())
    h10_used = {h10['reset_base'] + 100 * s + slot for s in range(N_SEEDS) for slot in range(2)}
    h10_used |= {h10['step_seed_base'] + 1000 * s + 100 * slot + k for s in range(N_SEEDS)
                 for slot in range(2) for k in range(200)}
    h10_used |= {h10['collect_source_base'] + 120 * s + i for s in range(N_SEEDS) for i in range(120)}
    h10_used |= {h10['collect_target_base'] + 40 * s + i for s in range(N_SEEDS) for i in range(40)}
    if used & h10_used:
        raise ValueError('confirmation seeds overlap the closed H10 block')


def budget(cfg):
    return base.budget(cfg)


def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'mcc_multitask_128_confirm_beats_scratch'
    if mean < 0 and hi < 0:
        return 'mcc_multitask_128_confirm_harm_established'
    return 'mcc_multitask_128_confirm_not_established'


def summarize(cells, cfg):
    rows = {int(c['seed']): c for c in cells}
    if set(rows) != set(range(N_SEEDS)):
        raise ValueError('incomplete confirmation seed grid')
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
        raise RuntimeError('refusing confirmation overwrite')
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
        'src/nexus/world/mcc_multitask_128_confirm.py',
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
                raise ValueError('confirmation source split drifted')
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
                raise ValueError('confirmation target prefix length drifted')
            target_rms = rung1.fit_rms(train.obs)
            multi, _pre = train_world_model(source_train, source_val, kind='residual',
                epochs=int(cfg['pretrain_epochs']), lr=cfg['train_lr'],
                seed=5 + 19 * s, n_actions=spec.n_actions, hidden=(64, 64),
                obs_rms=source_rms, freeze_rms=True)
            multi.copy_rms(target_rms)
            base.continue_train(multi, train, val, epochs=int(cfg['train_epochs']),
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
                raise ValueError('nonfinite confirmation return')
            p['cells'].append(cell)
            print(f'seed={s} seconds={time.perf_counter()-started:.1f}', flush=True)
        p.update(summarize(p['cells'], cfg))
        if meter.env_steps != cfg['env_cap'] or meter.model_states != cfg['model_cap']:
            raise ValueError('confirmation totals inconsistent with the locked budget')
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
        raise RuntimeError('incomplete/invalid confirmation evaluation')
    rebuilt = summarize(p['cells'], cfg)
    if p['label'] != rebuilt['label']:
        raise ValueError('saved label differs')
    if p.get('claims_learning_to_learn') is not False or p.get('is_agi') is not False:
        raise ValueError('forbidden claim flags drifted')
    if p.get('cross_family_weights') is not False:
        raise ValueError('confirmation must not share cross-family weights')
    n_traces = 0
    for row in p['cells']:
        for arm, trace in row['traces'].items():
            n_traces += 1
            if not np.isclose(math.fsum(trace['rewards']), trace['episode_return'], atol=1e-8):
                raise ValueError('confirmation reward reconstruction drifted')
            if not np.isclose(trace['episode_return'], row['returns'][arm], atol=1e-8):
                raise ValueError('confirmation trace/return mismatch')
            if int(trace['n_steps']) > cfg['episode_steps']:
                raise ValueError('confirmation episode length exceeded 200')
    if n_traces != 20:
        raise ValueError('confirmation 20-trace grid drifted')
    if int(p['counts']['env_steps']) != cfg['env_cap'] or int(p['counts']['model_states']) != cfg['model_cap']:
        raise ValueError('confirmation execution totals drifted')
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
        labels=('mcc_multitask_128_confirm_beats_scratch',
                'mcc_multitask_128_confirm_harm_established',
                'mcc_multitask_128_confirm_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False, cross_family_weights=False,
        note='No collection. H10 holdout and artifact remain closed.')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=600, env_cap=20960, model_cap=1024000).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('confirmation allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before confirmation collection')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s']) < cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')
