"""Within-family MCC residual-scale adaptation (not a shared-trunk xenv rung).

Same residual world model, same 128 target transitions, same target RMS,
same H=16 planner. Treatment is a frozen 2-d residual scale from source
mcc_default |s'−s| versus unit scale. No cross-family weights.
Not learning-to-learn.
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
from nexus.tasks.mountaincar_continuous_family import mcc_default, mcc_physics_key
from nexus.world.data import collect_transitions
from nexus.world.dynamics import WorldModel
from nexus.world.planning_value import sha
from nexus.world.terminal_value_execution import save
from nexus.world import mcc_native_rms as rms_rung
from nexus.world import xenv_transfer as rung1

CONFIG = Path('configs/mcc_residual_scale.yaml')
PROTOCOL = Path('docs/NEXUS_MCC_RESIDUAL_SCALE_PROTOCOL.md')
ALLOCATION = Path('configs/mcc_residual_scale_allocation.json')
OUTPUT = Path('artifacts/mcc_residual_scale.json')
HOLD_RULE = 'mcc_residual_scale_v1'
PRIMARY_BUDGET = 128
CLOSED_NATIVE_RMS = (0.0029, 0.0022, 0.055)
LOCKED_CONFIG = 'c0159fccf9ee6fc91053994651950d93bc311c964e5c601adbd5335e4efcbb83'
LOCKED_PROTOCOL = '2a62404277663817cbb7adb5dd11a87b584c5cea7190d3c43d2ca568b5ed359f'
N_SEEDS = 10
HORIZON = 16
N_CAND = 16
N_ACTIONS = 3
SCALE_DIM = 2
SCALE_EPS = 1e-6
REGISTRIES = rung1.REGISTRIES
OTHER_BRANCH_BLOCKS = rung1.OTHER_BRANCH_BLOCKS + (
    63000000, 63500000, 64000000, 65000000, 66000000, 67000000, 68000000, 69000000, 70000000)
SEED_MARGIN = 110000
ARMS = ('source_scale', 'unit_scale')


def occupied_physics():
    occupied = set(rms_rung.occupied_physics())
    occupied.add(CLOSED_NATIVE_RMS)
    occupied.add(mcc_physics_key(mcc_default()))
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
    return _mcc('mcc_residual_scale_t0', 'mcc_residual_scale',
        f'Within-family residual-scale target gravity/power/speed {key}.',
        gravity=key[0], power=key[1], max_speed=key[2])


def residual_scale(ds, rms):
    """2-d mean |s'−s| in the provided RMS-normalized coordinates."""
    obs = np.asarray(rms.normalize(ds.obs), dtype=np.float64)
    nxt = np.asarray(rms.normalize(ds.next_obs), dtype=np.float64)
    if obs.shape[-1] != SCALE_DIM:
        raise ValueError('residual-scale dim drifted')
    scale = np.mean(np.abs(nxt - obs), axis=0)
    return np.maximum(scale, SCALE_EPS)


def unit_scale():
    return np.ones(SCALE_DIM, dtype=np.float64)


class ScaledResidualModel:
    """WorldModel whose residual is trained and decoded in units of `scale`."""

    def __init__(self, wm: WorldModel, scale: np.ndarray) -> None:
        self.wm = wm
        self.scale = np.asarray(scale, dtype=np.float64).reshape(SCALE_DIM)

    def step(self, obs, action):
        self.wm.net.eval()
        o = np.asarray(obs, dtype=np.float32).reshape(-1, self.wm.net.obs_dim)
        a = np.asarray(action, dtype=np.int64).reshape(-1)
        if a.size == 1 and o.shape[0] > 1:
            a = np.full(o.shape[0], int(a.flat[0]), dtype=np.int64)
        with torch.no_grad():
            obs_n = torch.as_tensor(self.wm.normalize(o))
            pred, logit = self.wm.net(obs_n, torch.as_tensor(a))
            scale = torch.as_tensor(self.scale, dtype=pred.dtype)
            next_n = obs_n + pred * scale
            p = torch.sigmoid(logit)
        return self.wm.unnormalize(next_n.cpu().numpy()).reshape(o.shape), p.cpu().numpy().reshape(-1)


def train_scaled_residual(train, val, *, scale, rms, epochs, lr, seed, n_actions,
                          batch_size=128, term_weight=.25):
    wm = WorldModel.create(int(train.obs.shape[-1]), int(n_actions), kind='residual',
                           hidden=(64, 64), seed=int(seed), arch='mlp')
    wm.copy_rms(rms)
    scale_t = torch.as_tensor(np.asarray(scale, dtype=np.float64), dtype=torch.float32)
    if scale_t.numel() != SCALE_DIM:
        raise ValueError('locked residual scale is not 2-d')
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
            target = (nxt - obs) / scale_t
            loss = mse(pred, target) + term_weight * bce(logit.reshape(-1), term.reshape(-1))
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(wm.net.parameters(), 1.0)
            opt.step()
        wm.net.eval()
        with torch.no_grad():
            obs, nxt, act, term = tensors(val)
            pred, logit = wm.net(obs, act)
            v = float((mse(pred, (nxt - obs) / scale_t)
                       + term_weight * bce(logit.reshape(-1), term.reshape(-1))).item())
        if v < best:
            best = v
            best_state = {k: t.detach().cpu().clone() for k, t in wm.net.state_dict().items()}
    wm.net.load_state_dict(best_state)
    wm.net.eval()
    return ScaledResidualModel(wm, scale), dict(best_val=best, scale=np.asarray(scale).tolist())


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    locked = dict(starting_sha='d8e6402f294d8de37eb898d27c3c6f1cc89f8733',
        n_model_seeds=10, source_family='mountaincar_continuous',
        target_family='mountaincar_continuous', holdout_rule=HOLD_RULE,
        target_budget=PRIMARY_BUDGET, source_train=512, target_train=128, target_val=32,
        scale_dim=SCALE_DIM, train_epochs=20, train_lr=.001, term_weight=.25, batch_size=128,
        hidden=[64, 64], horizon=HORIZON, n_candidates=N_CAND, n_actions=N_ACTIONS,
        episode_steps=200, practical_margin=0.0, time_cap_s=600,
        env_cap=10720, model_cap=1024000, reset_base=71000000, step_seed_base=71100000,
        collect_source_base=71200000, collect_target_base=71300000,
        cross_family_weights=False, new_architecture_family=False,
        retune_from_closed_splits=False, claims_learning_to_learn=False, is_agi=False)
    for key, value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError('locked residual-scale design/budget changed')
    if holdout_from_rule() != [tuple(cfg['target_physics'][0])]:
        raise ValueError('residual-scale rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('residual-scale target collides with occupied MountainCarContinuous physics')
    spec = target_spec(tuple(cfg['target_physics'][0]))
    if spec.family != 'mountaincar_continuous' or spec.n_actions != N_ACTIONS:
        raise ValueError('residual-scale target is not MountainCarContinuous')
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
    used |= {cfg['collect_source_base'] + 40 * s + i for s in range(N_SEEDS) for i in range(40)}
    used |= {cfg['collect_target_base'] + 40 * s + i for s in range(N_SEEDS) for i in range(40)}
    if used & blocked:
        raise ValueError('residual-scale seeds collide with a closed experiment')
    if min(used) < cfg['reset_base']:
        raise ValueError('seed block drifted below the locked base')
    for base in OTHER_BRANCH_BLOCKS:
        if any(base <= u < base + 300000 for u in used):
            raise ValueError('residual-scale seeds collide with another live branch block')


def budget(cfg):
    source = int(cfg['source_train']) * N_SEEDS
    target = (int(cfg['target_train']) + int(cfg['target_val'])) * N_SEEDS
    evaluation = 2 * N_SEEDS * int(cfg['episode_steps'])
    imagined = evaluation * HORIZON * N_CAND
    if source + target + evaluation != cfg['env_cap']:
        raise ValueError('residual-scale env-step allocation mismatch')
    if imagined != cfg['model_cap']:
        raise ValueError('residual-scale imagined allocation mismatch')
    if int(cfg['scale_dim']) != SCALE_DIM:
        raise ValueError('residual-scale dim drifted')
    return dict(source_collection=source, target_pool=target, evaluation_episodes=evaluation,
                imagined=imagined, time_cap_s=cfg['time_cap_s'])


def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'mcc_residual_scale_beats_unit'
    if mean < 0 and hi < 0:
        return 'mcc_residual_scale_harm_established'
    return 'mcc_residual_scale_not_established'


def summarize(cells, cfg):
    rows = {int(c['seed']): c for c in cells}
    if set(rows) != set(range(N_SEEDS)):
        raise ValueError('incomplete residual-scale seed grid')
    diffs = [float(rows[s]['returns']['source_scale']) - float(rows[s]['returns']['unit_scale'])
             for s in range(N_SEEDS)]
    primary = seed_level_ci(diffs)
    label = classify_primary(primary['mean'], primary['lo'], primary['hi'], N_SEEDS, True)
    mae = seed_level_ci([float(rows[s]['mae']['source_scale']) - float(rows[s]['mae']['unit_scale'])
                         for s in range(N_SEEDS)])
    returns = {arm: seed_level_ci([float(rows[s]['returns'][arm]) for s in range(N_SEEDS)])
               for arm in ARMS}
    return dict(label=label, groups=dict(primary=dict(per_seed=diffs, interval=primary,
        budget=PRIMARY_BUDGET), mae_gain=mae, arm_return=returns))


def execute():
    cfg = load_config(); require_allocation(cfg)
    if OUTPUT.exists():
        raise RuntimeError('refusing residual-scale overwrite')
    if subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip():
        raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git', 'merge-base', '--is-ancestor', cfg['starting_sha'], 'HEAD'], check=True)
    from nexus.tasks.spec import make_task_env
    torch.set_num_threads(1)
    started = time.perf_counter(); meter = rung1.Meter(cfg)
    key = holdout_from_rule()[0]
    spec = target_spec(key)
    source_spec = mcc_default()
    p = dict(complete=False, label='incomplete', cells=[], parents=cfg['parents'],
        implementation_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        config_sha256=sha(CONFIG), protocol_sha256=sha(PROTOCOL), allocation_sha256=sha(ALLOCATION),
        source_dirty=False, target_physics=list(key), holdout_rule=HOLD_RULE,
        new_environment_interactions=cfg['env_cap'], imagined_transitions=cfg['model_cap'],
        cross_family_weights=False, is_agi=False, claims_learning_to_learn=False)
    p['code_hashes'] = {f: sha(f) for f in (
        'src/nexus/world/mcc_residual_scale.py', 'src/nexus/world/train.py',
        'src/nexus/world/dynamics.py', 'src/nexus/world/data.py',
        'src/nexus/world/planning.py', 'src/nexus/world/xenv_transfer.py')}
    try:
        for s in range(N_SEEDS):
            meter.check()
            B = cfg['collect_source_base'] + 40 * s
            source = collect_transitions(source_spec, n_transitions=int(cfg['source_train']),
                env_seeds=tuple(range(B, B + 6)), base_seed=B + 6, mix=('random', 'exploratory'))
            meter.collect(int(cfg['source_train']))
            B2 = cfg['collect_target_base'] + 40 * s
            train = collect_transitions(spec, n_transitions=int(cfg['target_train']),
                env_seeds=tuple(range(B2, B2 + 6)), base_seed=B2 + 6,
                mix=('random', 'exploratory'))
            val = collect_transitions(spec, n_transitions=int(cfg['target_val']),
                env_seeds=(B2 + 8, B2 + 9), base_seed=B2 + 10,
                mix=('random', 'exploratory'))
            meter.collect(int(cfg['target_train']) + int(cfg['target_val']))
            if len(train) != int(cfg['target_train']) or len(val) != int(cfg['target_val']):
                raise ValueError('residual-scale prefix length drifted')
            rms = rung1.fit_rms(train.obs)
            src_scale = residual_scale(source, rms)
            ones = unit_scale()
            cell = dict(seed=s, returns={}, mae={}, traces={},
                        scale=dict(source=src_scale.tolist(), unit=ones.tolist()))
            for arm, scale, slot in (('source_scale', src_scale, 0), ('unit_scale', ones, 1)):
                model, _log = train_scaled_residual(train, val, scale=scale, rms=rms,
                    epochs=int(cfg['train_epochs']), lr=cfg['train_lr'],
                    seed=5 + 19 * s, n_actions=spec.n_actions)
                env = make_task_env(spec)
                try:
                    trace = rung1.h16_rollout(env, model, cfg, s, slot, meter)
                finally:
                    env.close()
                cell['returns'][arm] = trace['episode_return']
                cell['traces'][arm] = trace
                cell['mae'][arm] = rung1.prediction_mae(model, val)
            if any(not np.isfinite(v) for v in cell['returns'].values()):
                raise ValueError('nonfinite residual-scale return')
            p['cells'].append(cell)
            print(f'seed={s} seconds={time.perf_counter()-started:.1f}', flush=True)
        p.update(summarize(p['cells'], cfg))
        if meter.env_steps != cfg['env_cap'] or meter.model_states != cfg['model_cap']:
            raise ValueError('residual-scale totals inconsistent with the locked budget')
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
        raise RuntimeError('incomplete/invalid residual-scale evaluation')
    rebuilt = summarize(p['cells'], cfg)
    if p['label'] != rebuilt['label']:
        raise ValueError('saved label differs')
    if p.get('claims_learning_to_learn') is not False or p.get('is_agi') is not False:
        raise ValueError('forbidden claim flags drifted')
    if p.get('cross_family_weights') is not False:
        raise ValueError('residual-scale must not share cross-family weights')
    n_traces = 0
    for row in p['cells']:
        if len(row['scale']['source']) != SCALE_DIM:
            raise ValueError('saved source scale dim drifted')
        for arm, trace in row['traces'].items():
            n_traces += 1
            if not np.isclose(math.fsum(trace['rewards']), trace['episode_return'], atol=1e-8):
                raise ValueError('residual-scale reward reconstruction drifted')
            if not np.isclose(trace['episode_return'], row['returns'][arm], atol=1e-8):
                raise ValueError('residual-scale trace/return mismatch')
            if int(trace['n_steps']) > cfg['episode_steps']:
                raise ValueError('residual-scale episode length exceeded 200')
    if n_traces != 20:
        raise ValueError('residual-scale 20-trace grid drifted')
    if int(p['counts']['env_steps']) != cfg['env_cap'] or int(p['counts']['model_states']) != cfg['model_cap']:
        raise ValueError('residual-scale execution totals drifted')
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
        proposed_budget=budget(cfg), arms=list(ARMS),
        labels=('mcc_residual_scale_beats_unit', 'mcc_residual_scale_harm_established',
                'mcc_residual_scale_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False, cross_family_weights=False,
        note='No collection. Native-RMS and xenv holdouts untouched. No shared trunk.')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=600, env_cap=10720, model_cap=1024000).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('residual-scale allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before residual-scale collection')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s']) < cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')
