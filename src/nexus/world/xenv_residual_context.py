"""Cross-environment residual-aware context transfer (rung 4).

A shared one-layer trunk conditioned by a support-inferred FiLM context
that may read the normalized residual s'-s. No family-ID table. Rungs 1-3
are closed not_established. Not learning-to-learn, not AGI.
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
from torch import nn
from nexus.cl.metrics import seed_level_ci
from nexus.world.data import collect_transitions
from nexus.world.planning_value import sha
from nexus.world.terminal_value_execution import save
from nexus.world import xenv_transfer as rung1

CONFIG = Path('configs/xenv_residual_context.yaml')
PROTOCOL = Path('docs/NEXUS_XENV_RESIDUAL_CONTEXT_PROTOCOL.md')
ALLOCATION = Path('configs/xenv_residual_context_allocation.json')
OUTPUT = Path('artifacts/xenv_residual_context.json')
HOLD_RULE = 'mcc_xenv_v5'
RUNG1_TARGET = (0.0025, 0.0015, 0.09)
RUNG2_TARGET = (0.0028, 0.0013, 0.065)
CLINE_V3_TARGET = (0.0034, 0.001, 0.055)
RUNG3_TARGET = (0.0027, 0.0009, 0.05)
LOCKED_CONFIG = 'a8583454fdfb1a87b62d4b067c0e612d7fd03a1a3d213cfc7744ba3d564e5d93'
LOCKED_PROTOCOL = '7f13199ff0f599dbc47d26568845eb3b7fda3ddb5f48430cf85665239942d5fa'
RESIDUAL_PAD = 6
N_SEEDS = 10
HIDDEN = 64
HORIZON = 16
N_CAND = 16
REGISTRIES = rung1.REGISTRIES
OTHER_BRANCH_BLOCKS = rung1.OTHER_BRANCH_BLOCKS + (63000000, 63500000, 64000000, 65000000)
SEED_MARGIN = 110000


def prior_specs():
    return rung1.prior_specs()


def occupied_physics():
    occupied = rung1.occupied_physics()
    occupied.add(RUNG1_TARGET)
    occupied.add(RUNG2_TARGET)
    occupied.add(CLINE_V3_TARGET)
    occupied.add(RUNG3_TARGET)
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
    return _mcc('mcc_xenv5_t0', 'xenv_residual_context',
        f'Cross-environment residual-context target gravity/power/speed {key}.',
        gravity=key[0], power=key[1], max_speed=key[2])


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    locked = dict(starting_sha='c129c62cfb848be173ee77ffe2623f2d2dd9d586',
        n_model_seeds=10, prior_families=['cartpole', 'acrobot', 'mountaincar'],
        target_family='mountaincar_continuous', holdout_rule=HOLD_RULE,
        target_budgets=[128, 1024], target_pool_train=1024, target_pool_val=256,
        prior_train=512, prior_val=128, context_dim=8, context_support=64,
        residual_pad=6, pretrain_epochs=15, pretrain_lr=.001,
        finetune_epochs=20, finetune_lr=.0005, reference_epochs=20, reference_lr=.001,
        term_weight=.25, batch_size=128, horizon=HORIZON, n_candidates=N_CAND,
        n_actions=3, episode_steps=200, practical_margin=0.0, time_cap_s=600,
        env_cap=44000, model_cap=3072000, reset_base=66000000, step_seed_base=66100000,
        collect_prior_base=66200000, collect_target_base=66300000, training_epochs_budget=10,
        retune_from_closed_splits=False, new_architecture_family=False,
        claims_learning_to_learn=False, claims_weight_transfer_across_families=False,
        is_agi=False)
    for key, value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError('locked residual-context design/budget changed')
    if holdout_from_rule() != [tuple(cfg['target_physics'][0])]:
        raise ValueError('residual-context rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('residual-context target collides with occupied MountainCarContinuous physics')
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
            base = int(value)
            blocked |= {base + i for i in range(SEED_MARGIN)}
    used = {cfg['reset_base'] + 100 * s + slot for s in range(N_SEEDS) for slot in range(6)}
    used |= {cfg['step_seed_base'] + 1000 * s + 100 * slot + k for s in range(N_SEEDS)
             for slot in range(6) for k in range(200)}
    used |= {cfg['collect_prior_base'] + 40 * s + i for s in range(N_SEEDS) for i in range(40)}
    used |= {cfg['collect_target_base'] + 40 * s + i for s in range(N_SEEDS) for i in range(40)}
    if used & blocked:
            raise ValueError('residual-context seeds collide with a closed experiment')
    if min(used) < cfg['reset_base']:
        raise ValueError('seed block drifted below the locked base')
    for base in OTHER_BRANCH_BLOCKS:
        if any(base <= u < base + 300000 for u in used):
            raise ValueError('residual-context seeds collide with another live branch block')


def budget(cfg):
    counts = rung1.budget(cfg)
    if counts['prior_collection'] + counts['target_pool'] + counts['evaluation_episodes'] != cfg['env_cap']:
        raise ValueError('residual-context env-step allocation mismatch')
    if counts['imagined'] != cfg['model_cap']:
        raise ValueError('residual-context imagined allocation mismatch')
    return counts


class XEnvResidualContextNet(nn.Module):
    """Per-family projections over one shared layer with residual-aware FiLM.

    Context is inferred from (obs, action, residual). Residual is zero-padded
    to RESIDUAL_PAD so the shared encoder has a fixed input size.
    """

    def __init__(self, families: dict[str, tuple[int, int]], context_dim: int = 8,
                 seed: int = 0) -> None:
        super().__init__()
        torch.manual_seed(int(seed))
        self.families = {str(k): (int(v[0]), int(v[1])) for k, v in families.items()}
        self.context_dim = int(context_dim)
        self.in_proj = nn.ModuleDict()
        self.state_heads = nn.ModuleDict()
        self.term_heads = nn.ModuleDict()
        for name, (obs_dim, n_actions) in self.families.items():
            self.in_proj[name] = nn.Linear(obs_dim + n_actions, HIDDEN)
            self.state_heads[name] = nn.Linear(HIDDEN, obs_dim)
            self.term_heads[name] = nn.Linear(HIDDEN, 1)
        self.shared = nn.Linear(HIDDEN, HIDDEN)
        self.ctx_enc = nn.Sequential(nn.Linear(HIDDEN + RESIDUAL_PAD, self.context_dim), nn.Tanh())
        self.film = nn.Linear(self.context_dim, 2 * HIDDEN)
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.zeros_(m.bias)
        nn.init.zeros_(self.film.weight)
        nn.init.zeros_(self.film.bias)
        self.contexts: dict[str, torch.Tensor] = {}

    def embed(self, name, obs_norm, action):
        name = str(name)
        obs_dim, n_actions = self.families[name]
        a = torch.as_tensor(action, dtype=torch.int64).reshape(-1)
        onehot = torch.nn.functional.one_hot(a, n_actions).to(obs_norm.dtype)
        x = torch.cat([obs_norm, onehot], dim=1)
        return torch.tanh(self.in_proj[name](x))

    def infer_context(self, name, support_obs, support_action, support_next):
        """Encode each support transition with residual, then mean-pool."""
        obs = torch.as_tensor(np.asarray(support_obs), dtype=torch.float32)
        nxt = torch.as_tensor(np.asarray(support_next), dtype=torch.float32)
        resid = nxt - obs
        pad = torch.zeros(resid.shape[0], RESIDUAL_PAD, dtype=obs.dtype)
        dim = int(resid.shape[1])
        if dim > RESIDUAL_PAD:
            raise ValueError('residual wider than locked pad')
        pad[:, :dim] = resid
        h = self.embed(name, obs, support_action)
        return self.ctx_enc(torch.cat([h, pad], dim=1)).mean(dim=0, keepdim=True)

    def frozen_context(self, name, support_obs, support_action, support_next):
        """Adaptation-time inference: detached; no target gradient to the encoder."""
        with torch.no_grad():
            z = self.infer_context(name, support_obs, support_action, support_next)
        return z.detach()

    def set_context(self, name, z):
        self.contexts[str(name)] = torch.as_tensor(z, dtype=torch.float32).reshape(-1, self.context_dim)

    def forward(self, name, obs_norm, action):
        name = str(name)
        h = torch.tanh(self.shared(self.embed(name, obs_norm, action)))
        z = self.contexts.get(name)
        if z is None:
            raise KeyError(f'context not set for family {name}')
        gamma, beta = self.film(z).chunk(2, dim=-1)
        h = h * (1.0 + gamma) + beta
        return self.state_heads[name](h), self.term_heads[name](h)

    def n_parameters(self) -> int:
        return sum(int(p.numel()) for p in self.parameters())


def support_arrays(ds, n):
    """Train-prefix (obs, action, next_obs) only; never val or evaluation."""
    return (np.asarray(ds.obs[:int(n)]), np.asarray(ds.action[:int(n)]),
            np.asarray(ds.next_obs[:int(n)]))


def pretrain_contextual(net, data, support_n, *, epochs, lr, seed,
                         batch_size=128, term_weight=.25):
    """Joint source pretraining; contexts recomputed each batch from support.

    Recomputing per batch keeps a live graph for the encoder (avoids
    second-backward through a spent context) and trains FiLM through
    conditioning.
    """
    tensors = {str(name): rung1._family_tensors(ds, rms) for name, (ds, rms) in data.items()}
    supports = {str(name): (rms.normalize(np.asarray(ds.obs[:int(support_n)])),
                            np.asarray(ds.action[:int(support_n)]),
                            rms.normalize(np.asarray(ds.next_obs[:int(support_n)])))
                for name, (ds, rms) in data.items()}
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    mse = nn.MSELoss(); bce = nn.BCEWithLogitsLoss()
    rng = np.random.default_rng(seed)
    history = []
    for _epoch in range(int(epochs)):
        net.train()
        perms = {name: rng.permutation(len(obs)) for name, (obs, _n, _a, _t) in tensors.items()}
        span = min(len(p) for p in perms.values())
        for i in range(0, span, batch_size):
            loss = 0.
            for name, (obs, nxt, act, term) in tensors.items():
                net.set_context(name, net.infer_context(name, *supports[name]))
                idx = perms[name][i:i + batch_size]
                pred, logit = net(name, obs[idx], act[idx])
                loss = loss + mse(pred, nxt[idx] - obs[idx]) + term_weight * bce(logit.reshape(-1), term[idx])
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
        history.append(float(loss.item()))
    net.eval()
    return dict(epochs=int(epochs), final_loss=history[-1] if history else None)


def context_diagnostics(net, source_supports, target_support):
    """Nearest-source ratio: identification would collapse the target onto a source."""
    names = list(source_supports)
    zs = [net.frozen_context(n, *source_supports[n]).reshape(-1).cpu().numpy() for n in names]
    zt = net.frozen_context('mcc', *target_support).reshape(-1).cpu().numpy()
    inter = [float(np.linalg.norm(zs[i] - zs[j])) for i in range(len(zs))
             for j in range(i + 1, len(zs))]
    nearest = [float(np.linalg.norm(zt - z)) for z in zs]
    mean_inter = float(np.mean(inter)) if inter else 0.0
    return dict(target_norm=float(np.linalg.norm(zt)),
                nearest_source_distance=float(np.min(nearest)) if nearest else None,
                mean_inter_source_distance=mean_inter,
                nearest_source_ratio=(float(np.min(nearest)) / mean_inter) if mean_inter > 0 else None)


def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'xenv_residual_context_beats_scratch'
    if mean < 0 and hi < 0:
        return 'xenv_residual_context_harm_established'
    return 'xenv_residual_context_not_established'


def summarize(cells, cfg):
    rows = {int(c['seed']): c for c in cells}
    if set(rows) != set(range(N_SEEDS)):
        raise ValueError('incomplete residual-context seed grid')
    for s in range(N_SEEDS):
        c = rows[s]
        for arm in ('xenv', 'scratch', 'reference'):
            for b in cfg['target_budgets']:
                if str(b) not in c['returns'][arm]:
                    raise ValueError(f'missing return: seed={s} arm={arm} budget={b}')
        if c['parameters']['xenv'] != c['parameters']['scratch']:
            raise ValueError('arm parameter counts differ')
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
    ratios = [r for s in range(N_SEEDS) for r in
              [rows[s]['context_diagnostics'][str(b)].get('nearest_source_ratio')
               for b in cfg['target_budgets']] if r is not None]
    return dict(label=label, groups=dict(primary=dict(per_seed=diffs, interval=primary),
        per_budget_return_gain=per_budget, reference_return=reference, mae_gain=mae_gain,
        context_diagnostics=dict(nearest_source_ratio_mean=(float(np.mean(ratios)) if ratios else None),
                                  n_reported=len(ratios))))


def execute():
    cfg = load_config(); require_allocation(cfg)
    if OUTPUT.exists():
        raise RuntimeError('refusing residual-context overwrite')
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
        context_dim=int(cfg['context_dim']), context_support=int(cfg['context_support']),
        new_environment_interactions=cfg['env_cap'], imagined_transitions=cfg['model_cap'],
        training_epochs_budget=cfg['training_epochs_budget'], is_agi=False,
        claims_learning_to_learn=False, claims_weight_transfer_across_families=False)
    p['code_hashes'] = {f: sha(f) for f in (
        'src/nexus/world/xenv_residual_context.py', 'src/nexus/world/xenv_transfer.py',
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
                        mae=dict(xenv={}, scratch={}, reference={}), traces={},
                        context_diagnostics={}, parameters={})
            for bi, budget_n in enumerate(cfg['target_budgets']):
                train_b = pool_train.slice(np.arange(int(budget_n)))
                val_n = max(32, int(budget_n) // 4)
                val_b = pool_val.slice(np.arange(val_n))
                if len(val_b) != val_n or len(train_b) != int(budget_n):
                    raise ValueError('residual-context prefix length drifted')
                rms = rung1.fit_rms(train_b.obs)
                sobs, sact, snxt = support_arrays(train_b, min(cfg['context_support'], len(train_b)))
                support = (rms.normalize(sobs), sact, rms.normalize(snxt))
                src_supports = {name: (rung1.fit_rms(tr.obs).normalize(
                    np.asarray(tr.obs[:cfg['context_support']])),
                    np.asarray(tr.action[:cfg['context_support']]),
                    rung1.fit_rms(tr.obs).normalize(np.asarray(tr.next_obs[:cfg['context_support']])))
                    for name, (tr, _vl) in prior_data.items()}
                xnet = XEnvResidualContextNet(families, context_dim=int(cfg['context_dim']), seed=5 + 19 * s)
                pretrain_contextual(xnet, {name: (tr, rung1.fit_rms(tr.obs))
                    for name, (tr, _vl) in prior_data.items()}, cfg['context_support'],
                    epochs=int(cfg['pretrain_epochs']), lr=cfg['pretrain_lr'], seed=7 + 23 * s)
                xnet.set_context('mcc', xnet.frozen_context('mcc', *support))
                rung1.finetune_target(xnet, 'mcc', train_b, val_b, rms,
                    epochs=int(cfg['finetune_epochs']), lr=cfg['finetune_lr'], seed=11 + 29 * s)
                xmodel = rung1.XEnvModel(xnet, 'mcc', spec.obs_dim, spec.n_actions, rms)
                znet = XEnvResidualContextNet(families, context_dim=int(cfg['context_dim']), seed=5 + 19 * s)
                znet.set_context('mcc', znet.frozen_context('mcc', *support))
                rung1.finetune_target(znet, 'mcc', train_b, val_b, rms,
                    epochs=int(cfg['finetune_epochs']), lr=cfg['finetune_lr'], seed=11 + 29 * s)
                zmodel = rung1.XEnvModel(znet, 'mcc', spec.obs_dim, spec.n_actions, rms)
                rmodel, _log = train_world_model(train_b, val_b, kind='residual',
                    epochs=int(cfg['reference_epochs']), lr=cfg['reference_lr'],
                    seed=5 + 19 * s, n_actions=spec.n_actions)
                cell['parameters'] = dict(xenv=xnet.n_parameters(), scratch=znet.n_parameters())
                cell['context_diagnostics'][str(budget_n)] = context_diagnostics(xnet, src_supports, support)
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
                raise ValueError('nonfinite residual-context return')
            p['cells'].append(cell)
            print(f'seed={s} seconds={time.perf_counter()-started:.1f}', flush=True)
        p.update(summarize(p['cells'], cfg))
        if meter.env_steps != cfg['env_cap'] or meter.model_states != cfg['model_cap']:
            raise ValueError('residual-context totals inconsistent with the locked budget')
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
        raise RuntimeError('incomplete/invalid residual-context evaluation')
    rebuilt = summarize(p['cells'], cfg)
    if p['label'] != rebuilt['label']:
        raise ValueError('saved label differs')
    if p.get('claims_learning_to_learn') is not False or p.get('is_agi') is not False:
        raise ValueError('forbidden claim flags drifted')
    if int(p.get('context_dim')) != int(cfg['context_dim']):
        raise ValueError('context dimension drifted')
    n_traces = 0
    for row in p['cells']:
        if row['parameters']['xenv'] != row['parameters']['scratch']:
            raise ValueError('arm parameter counts differ in the recorded grid')
        for name, trace in row['traces'].items():
            n_traces += 1
            if not np.isclose(math.fsum(trace['rewards']), trace['episode_return'], atol=1e-8):
                raise ValueError('residual-context reward reconstruction drifted')
            arm, budget_n = name.split('@')
            if not np.isclose(trace['episode_return'],
                    row['returns'][arm][str(budget_n)], atol=1e-8):
                raise ValueError('residual-context trace/return mismatch')
            if int(trace['n_steps']) > cfg['episode_steps']:
                raise ValueError('residual-context episode length exceeded 200')
        for b in cfg['target_budgets']:
            if 'nearest_source_ratio' not in row['context_diagnostics'][str(b)]:
                raise ValueError('missing context diagnostic')
    if n_traces != 60:
        raise ValueError('residual-context 60-trace grid drifted')
    if int(p['counts']['env_steps']) != cfg['env_cap'] or int(p['counts']['model_states']) != cfg['model_cap']:
        raise ValueError('residual-context execution totals drifted')
    return dict(audit_passed=True, label=p['label'], raw_sha256=sha(OUTPUT),
        groups=p['groups'], n_traces=n_traces,
        new_environment_steps=int(p['counts']['env_steps']),
        new_imagined_transitions=int(p['counts']['model_states']),
        target_physics=p['target_physics'], context_dim=p['context_dim'], is_agi=False,
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
        context_dim=int(cfg['context_dim']), context_support=int(cfg['context_support']),
        proposed_budget=budget(cfg), arms=['xenv', 'scratch', 'reference'],
        labels=('xenv_residual_context_beats_scratch', 'xenv_residual_context_harm_established',
                'xenv_residual_context_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False,
        note='No collection. New unused target physics; rungs 1-3 untouched.')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=600, env_cap=44000, model_cap=3072000).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('residual-context allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before residual-context collection')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s']) < cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')
