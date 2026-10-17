"""Cross-environment 2x prior-data scale (rung 5).

Same XEnvNet as rung 1; twice the source transitions per family. Rungs 1-4
are closed not_established. No FiLM. Not learning-to-learn, not AGI.
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
from nexus.world.data import collect_transitions
from nexus.world.planning_value import sha
from nexus.world.terminal_value_execution import save
from nexus.world import xenv_transfer as rung1

CONFIG = Path('configs/xenv_prior_scale.yaml')
PROTOCOL = Path('docs/NEXUS_XENV_PRIOR_SCALE_PROTOCOL.md')
ALLOCATION = Path('configs/xenv_prior_scale_allocation.json')
OUTPUT = Path('artifacts/xenv_prior_scale.json')
HOLD_RULE = 'mcc_xenv_v6'
CLOSED_TARGETS = (
    (0.0025, 0.0015, 0.09),
    (0.0028, 0.0013, 0.065),
    (0.0034, 0.001, 0.055),
    (0.0027, 0.0009, 0.05),
    (0.0019, 0.0013, 0.065),
)
LOCKED_CONFIG = '9a20c78c0e9b2ef02fb95c0262d5f51f5ef7cf4ba2d3a906f06cbf2f4c6b6fd6'
LOCKED_PROTOCOL = '85c49070bf08083704143d12fb5406b639615cdecee68c73f4f6473abbdafa3b'
N_SEEDS = 10
HORIZON = 16
N_CAND = 16
REGISTRIES = rung1.REGISTRIES
OTHER_BRANCH_BLOCKS = rung1.OTHER_BRANCH_BLOCKS + (63000000, 63500000, 64000000, 65000000, 66000000)
SEED_MARGIN = 110000


def prior_specs():
    return rung1.prior_specs()


def occupied_physics():
    occupied = rung1.occupied_physics()
    occupied.update(CLOSED_TARGETS)
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
    return _mcc('mcc_xenv6_t0', 'xenv_prior_scale',
        f'Cross-environment 2x-prior target gravity/power/speed {key}.',
        gravity=key[0], power=key[1], max_speed=key[2])


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    locked = dict(starting_sha='81e02153b7781dc0fdb45bcbe608b011ba17ca4f',
        n_model_seeds=10, prior_families=['cartpole', 'acrobot', 'mountaincar'],
        target_family='mountaincar_continuous', holdout_rule=HOLD_RULE,
        target_budgets=[128, 1024], target_pool_train=1024, target_pool_val=256,
        prior_train=1024, prior_val=256, pretrain_epochs=15, pretrain_lr=.001,
        finetune_epochs=20, finetune_lr=.0005, reference_epochs=20, reference_lr=.001,
        term_weight=.25, batch_size=128, horizon=HORIZON, n_candidates=N_CAND,
        n_actions=3, episode_steps=200, practical_margin=0.0, time_cap_s=600,
        env_cap=63200, model_cap=3072000, reset_base=67000000, step_seed_base=67100000,
        collect_prior_base=67200000, collect_target_base=67300000, training_epochs_budget=10,
        retune_from_closed_splits=False, new_architecture_family=False,
        claims_learning_to_learn=False, claims_weight_transfer_across_families=False,
        is_agi=False)
    for key, value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError('locked prior-scale design/budget changed')
    if holdout_from_rule() != [tuple(cfg['target_physics'][0])]:
        raise ValueError('prior-scale rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('prior-scale target collides with occupied MountainCarContinuous physics')
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
    used = {cfg['reset_base'] + 100 * s + slot for s in range(N_SEEDS) for slot in range(6)}
    used |= {cfg['step_seed_base'] + 1000 * s + 100 * slot + k for s in range(N_SEEDS)
             for slot in range(6) for k in range(200)}
    used |= {cfg['collect_prior_base'] + 40 * s + i for s in range(N_SEEDS) for i in range(40)}
    used |= {cfg['collect_target_base'] + 40 * s + i for s in range(N_SEEDS) for i in range(40)}
    if used & blocked:
        raise ValueError('prior-scale seeds collide with a closed experiment')
    if min(used) < cfg['reset_base']:
        raise ValueError('seed block drifted below the locked base')
    for base in OTHER_BRANCH_BLOCKS:
        if any(base <= u < base + 300000 for u in used):
            raise ValueError('prior-scale seeds collide with another live branch block')


def budget(cfg):
    counts = rung1.budget(cfg)
    if counts['prior_collection'] + counts['target_pool'] + counts['evaluation_episodes'] != cfg['env_cap']:
        raise ValueError('prior-scale env-step allocation mismatch')
    if counts['imagined'] != cfg['model_cap']:
        raise ValueError('prior-scale imagined allocation mismatch')
    return counts


def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'xenv_prior_scale_beats_scratch'
    if mean < 0 and hi < 0:
        return 'xenv_prior_scale_harm_established'
    return 'xenv_prior_scale_not_established'


def summarize(cells, cfg):
    rows = {int(c['seed']): c for c in cells}
    if set(rows) != set(range(N_SEEDS)):
        raise ValueError('incomplete prior-scale seed grid')
    for s in range(N_SEEDS):
        c = rows[s]
        for arm in ('xenv', 'scratch', 'reference'):
            for b in cfg['target_budgets']:
                if str(b) not in c['returns'][arm]:
                    raise ValueError(f'missing return: seed={s} arm={arm} budget={b}')
    diffs = []
    for s in range(N_SEEDS):
        c = rows[s]
        x = float(np.mean([c['returns']['xenv'][str(b)] for b in cfg['target_budgets']]))
        z = float(np.mean([c['returns']['scratch'][str(b)] for b in cfg['target_budgets']]))
        diffs.append(x - z)
    primary = seed_level_ci(diffs)
    label = classify_primary(primary['mean'], primary['lo'], primary['hi'], N_SEEDS, True)
    per_budget = {str(b): seed_level_ci([rows[s]['returns']['xenv'][str(b)]
        - rows[s]['returns']['scratch'][str(b)] for s in range(N_SEEDS)])
        for b in cfg['target_budgets']}
    reference = {str(b): seed_level_ci([rows[s]['returns']['reference'][str(b)]
        for s in range(N_SEEDS)]) for b in cfg['target_budgets']}
    mae_gain = {str(b): seed_level_ci([rows[s]['mae']['xenv'][str(b)]
        - rows[s]['mae']['scratch'][str(b)] for s in range(N_SEEDS)])
        for b in cfg['target_budgets']}
    return dict(label=label, groups=dict(primary=dict(per_seed=diffs, interval=primary),
        per_budget_return_gain=per_budget, reference_return=reference, mae_gain=mae_gain))


def execute():
    cfg = load_config(); require_allocation(cfg)
    if OUTPUT.exists():
        raise RuntimeError('refusing prior-scale overwrite')
    if subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip():
        raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git', 'merge-base', '--is-ancestor', cfg['starting_sha'], 'HEAD'], check=True)
    from nexus.tasks.spec import make_task_env
    from nexus.world.train import train_world_model
    torch.set_num_threads(1)
    started = time.perf_counter(); meter = rung1.Meter(cfg)
    key = holdout_from_rule()[0]
    spec = target_spec(key)
    priors = prior_specs()
    families = {name: (pspec.obs_dim, pspec.n_actions) for name, pspec in priors.items()}
    families['mcc'] = (spec.obs_dim, spec.n_actions)
    p = dict(complete=False, label='incomplete', cells=[], parents=cfg['parents'],
        implementation_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        config_sha256=sha(CONFIG), protocol_sha256=sha(PROTOCOL), allocation_sha256=sha(ALLOCATION),
        source_dirty=False, target_physics=list(key), holdout_rule=HOLD_RULE,
        new_environment_interactions=cfg['env_cap'], imagined_transitions=cfg['model_cap'],
        training_epochs_budget=cfg['training_epochs_budget'], is_agi=False,
        claims_learning_to_learn=False, claims_weight_transfer_across_families=False)
    p['code_hashes'] = {f: sha(f) for f in (
        'src/nexus/world/xenv_prior_scale.py', 'src/nexus/world/xenv_transfer.py',
        'src/nexus/world/train.py', 'src/nexus/world/dynamics.py',
        'src/nexus/world/data.py', 'src/nexus/world/planning.py')}
    try:
        for s in range(N_SEEDS):
            meter.check()
            B = cfg['collect_prior_base'] + 40 * s
            prior_data = {}
            for j, (name, pspec) in enumerate(priors.items()):
                tr = collect_transitions(pspec, n_transitions=int(cfg['prior_train']),
                    env_seeds=tuple(range(B + 6 * j, B + 6 * j + 6)),
                    base_seed=B + 18 + j, mix=('random', 'exploratory'))
                vl = collect_transitions(pspec, n_transitions=int(cfg['prior_val']),
                    env_seeds=(B + 21 + 3 * j, B + 22 + 3 * j),
                    base_seed=B + 30 + j, mix=('random', 'exploratory'))
                prior_data[name] = (tr, vl)
                meter.collect(int(cfg['prior_train']) + int(cfg['prior_val']))
            B2 = cfg['collect_target_base'] + 40 * s
            pool_train = collect_transitions(spec, n_transitions=int(cfg['target_pool_train']),
                env_seeds=tuple(range(B2, B2 + 6)), base_seed=B2 + 6,
                mix=('random', 'exploratory'))
            pool_val = collect_transitions(spec, n_transitions=int(cfg['target_pool_val']),
                env_seeds=(B2 + 8, B2 + 9), base_seed=B2 + 10,
                mix=('random', 'exploratory'))
            meter.collect(int(cfg['target_pool_train']) + int(cfg['target_pool_val']))
            cell = dict(seed=s, returns=dict(xenv={}, scratch={}, reference={}),
                        mae=dict(xenv={}, scratch={}, reference={}), traces={})
            for bi, budget_n in enumerate(cfg['target_budgets']):
                train_b = pool_train.slice(np.arange(int(budget_n)))
                val_n = max(32, int(budget_n) // 4)
                val_b = pool_val.slice(np.arange(val_n))
                if len(val_b) != val_n or len(train_b) != int(budget_n):
                    raise ValueError('prior-scale prefix length drifted')
                rms = rung1.fit_rms(train_b.obs)
                xnet = rung1.XEnvNet(families, seed=5 + 19 * s)
                rung1.pretrain_shared(xnet, {name: (tr, rung1.fit_rms(tr.obs))
                    for name, (tr, _vl) in prior_data.items()},
                    epochs=int(cfg['pretrain_epochs']), lr=cfg['pretrain_lr'], seed=7 + 23 * s)
                rung1.finetune_target(xnet, 'mcc', train_b, val_b, rms,
                    epochs=int(cfg['finetune_epochs']), lr=cfg['finetune_lr'], seed=11 + 29 * s)
                xmodel = rung1.XEnvModel(xnet, 'mcc', spec.obs_dim, spec.n_actions, rms)
                znet = rung1.XEnvNet(families, seed=5 + 19 * s)
                rung1.finetune_target(znet, 'mcc', train_b, val_b, rms,
                    epochs=int(cfg['finetune_epochs']), lr=cfg['finetune_lr'], seed=11 + 29 * s)
                zmodel = rung1.XEnvModel(znet, 'mcc', spec.obs_dim, spec.n_actions, rms)
                rmodel, _log = train_world_model(train_b, val_b, kind='residual',
                    epochs=int(cfg['reference_epochs']), lr=cfg['reference_lr'],
                    seed=5 + 19 * s, n_actions=spec.n_actions)
                for arm, model, slot in (('xenv', xmodel, 2 * bi), ('scratch', zmodel, 2 * bi + 1),
                                         ('reference', rmodel, 4 + bi)):
                    env = make_task_env(spec)
                    try:
                        trace = rung1.h16_rollout(env, model, cfg, s, slot, meter)
                    finally:
                        env.close()
                    cell['returns'][arm][str(budget_n)] = trace['episode_return']
                    cell['traces'][f'{arm}@{budget_n}'] = trace
                    cell['mae'][arm][str(budget_n)] = rung1.prediction_mae(model, val_b)
            if any(not np.isfinite(v) for arm in cell['returns'].values() for v in arm.values()):
                raise ValueError('nonfinite prior-scale return')
            p['cells'].append(cell)
            print(f'seed={s} seconds={time.perf_counter()-started:.1f}', flush=True)
        p.update(summarize(p['cells'], cfg))
        if meter.env_steps != cfg['env_cap'] or meter.model_states != cfg['model_cap']:
            raise ValueError('prior-scale totals inconsistent with the locked budget')
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
        raise RuntimeError('incomplete/invalid prior-scale evaluation')
    rebuilt = summarize(p['cells'], cfg)
    if p['label'] != rebuilt['label']:
        raise ValueError('saved label differs')
    if p.get('claims_learning_to_learn') is not False or p.get('is_agi') is not False:
        raise ValueError('forbidden claim flags drifted')
    n_traces = 0
    for row in p['cells']:
        for name, trace in row['traces'].items():
            n_traces += 1
            if not np.isclose(math.fsum(trace['rewards']), trace['episode_return'], atol=1e-8):
                raise ValueError('prior-scale reward reconstruction drifted')
            arm, budget_n = name.split('@')
            if not np.isclose(trace['episode_return'],
                    row['returns'][arm][str(budget_n)], atol=1e-8):
                raise ValueError('prior-scale trace/return mismatch')
            if int(trace['n_steps']) > cfg['episode_steps']:
                raise ValueError('prior-scale episode length exceeded 200')
    if n_traces != 60:
        raise ValueError('prior-scale 60-trace grid drifted')
    if int(p['counts']['env_steps']) != cfg['env_cap'] or int(p['counts']['model_states']) != cfg['model_cap']:
        raise ValueError('prior-scale execution totals drifted')
    return dict(audit_passed=True, label=p['label'], raw_sha256=sha(OUTPUT),
        groups=p['groups'], n_traces=n_traces,
        new_environment_steps=int(p['counts']['env_steps']),
        new_imagined_transitions=int(p['counts']['model_states']),
        target_physics=p['target_physics'], is_agi=False,
        claims_learning_to_learn=False)


def prep():
    cfg = load_config()
    record = load_allocation()
    if record.get('authorized') is True or int(record.get('runs', 0)) != 0:
        raise PermissionError('prep refuses an already authorized allocation')
    return dict(complete=True, authorized=False, runs=0, new_environment_steps=0,
        new_imagined_transitions=0, config_sha256=sha(CONFIG),
        protocol_sha256=sha(PROTOCOL), allocation_sha256=sha(ALLOCATION),
        target_physics=list(holdout_from_rule()[0]), holdout_rule=HOLD_RULE,
        proposed_budget=budget(cfg), arms=['xenv', 'scratch', 'reference'],
        labels=('xenv_prior_scale_beats_scratch', 'xenv_prior_scale_harm_established',
                'xenv_prior_scale_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False,
        note='No collection. 2x prior data on closed rung-1 architecture; rungs 1-4 untouched.')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=600, env_cap=63200, model_cap=3072000).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('prior-scale allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before prior-scale collection')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s']) < cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')
