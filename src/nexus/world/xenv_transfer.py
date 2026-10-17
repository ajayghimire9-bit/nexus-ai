"""Cross-environment shared-trunk world-model transfer pilot.

First rung of the cross-environment adaptation direction: does one shared
64->64 tanh layer, pretrained jointly on three other environments, improve
MountainCarContinuous world-model adaptation on new physics at matched target
data versus the identical architecture trained on the target only? Same
residual-MLP family; no new architecture family. Not learning-to-learn, not AGI.
"""
from __future__ import annotations
import hashlib
import importlib
import itertools
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
from nexus.rl.running_stats import RunningMeanStd
from nexus.tasks.acrobot_family import acrobot_default
from nexus.tasks.cartpole_family import CARTPOLE_FAMILY
from nexus.tasks.mountaincar_continuous_family import (
    mcc_default,
    mcc_lookahead_confirmation,
    mcc_lookahead_development,
    mcc_physics_key,
)
from nexus.tasks.mountaincar_family import mountaincar_default
from nexus.world.data import TransitionDataset, collect_transitions
from nexus.world.planning import RandomShootingMPC
from nexus.world.planning_value import sha
from nexus.world.rewards import mountaincar_step_reward
from nexus.world.terminal_value_execution import save

CONFIG=Path('configs/xenv_transfer_pilot.yaml')
PROTOCOL=Path('docs/NEXUS_XENV_TRANSFER_PILOT_PROTOCOL.md')
ALLOCATION=Path('configs/xenv_transfer_pilot_allocation.json')
OUTPUT=Path('artifacts/xenv_transfer_pilot.json')
HOLD_RULE='mcc_xenv_v1'
LOCKED_CONFIG='531bfe1ab9456dfe93341b324a61ce4c40ff23594534575b141f7496e4fb8a58'
LOCKED_PROTOCOL='4e309b4f61e9afa280a632bec024a230a0328d045893690c12596ba22745127e'
PRIMARY='xenv_minus_scratch'
N_SEEDS=10
HIDDEN=64
HORIZON=16
N_CAND=16
REGISTRIES=("action_conditioned_q","capacity_matched_q","bellman_backup_control",
    "receding_policy_consistency","same_set_planning","horizon_alignment",
    "decision_aware_world_model","late_episode_decision_trajectory",
    "pendulum_compute_matched","lookahead_transfer_confirmation",
    "mountaincar_compute_matched","acrobot_compute_matched",
    "tree_reuse_lookahead","prefix_max_tree_reuse","terminal_value","planning_value")
OTHER_BRANCH_BLOCKS=(61000000,61100000,61200000)


def prior_specs():
    return dict(cartpole=CARTPOLE_FAMILY['cartpole_default'],
                acrobot=acrobot_default(),
                mountaincar=mountaincar_default())


def occupied_physics():
    occupied={mcc_physics_key(mcc_default())}
    occupied|={mcc_physics_key(s) for s in mcc_lookahead_development()}
    occupied|={mcc_physics_key(s) for s in mcc_lookahead_confirmation()}
    return occupied


def holdout_from_rule(n=1,rule=HOLD_RULE):
    occupied=occupied_physics()
    gs=[round(x*0.0001,4) for x in range(15,41)]
    ps=[round(x*0.0001,4) for x in range(8,23)]
    ss=[round(x*0.005,3) for x in range(10,19)]
    chosen=[];counter=0
    while len(chosen)<int(n):
        digest=hashlib.sha256(f'{rule}:{counter}'.encode()).digest()
        idx=int.from_bytes(digest[:8],'big')
        key=(float(gs[idx%len(gs)]),float(ps[(idx//len(gs))%len(ps)]),float(ss[(idx//(len(gs)*len(ps)))%len(ss)]))
        if key not in occupied and key not in chosen: chosen.append(key)
        counter+=1
    return chosen


def target_spec(key):
    from nexus.tasks.mountaincar_continuous_family import _mcc
    return _mcc('mcc_xenv_t0','xenv_pilot',
        f'Cross-environment transfer target gravity/power/speed {key}.',
        gravity=key[0],power=key[1],max_speed=key[2])

def load_config():
    cfg=yaml.safe_load(CONFIG.read_text())
    locked=dict(starting_sha='5263714ab6cb105d0ebb93c84e6c597a23618d35',
        n_model_seeds=10,prior_families=['cartpole','acrobot','mountaincar'],
        target_family='mountaincar_continuous',holdout_rule=HOLD_RULE,
        target_budgets=[128,1024],target_pool_train=1024,target_pool_val=256,
        prior_train=512,prior_val=128,pretrain_epochs=15,pretrain_lr=.001,
        finetune_epochs=20,finetune_lr=.0005,reference_epochs=20,reference_lr=.001,
        term_weight=.25,batch_size=128,horizon=HORIZON,n_candidates=N_CAND,
        n_actions=3,episode_steps=200,practical_margin=0.0,time_cap_s=600,
        env_cap=44000,model_cap=3072000,reset_base=63000000,step_seed_base=63100000,
        collect_prior_base=63200000,collect_target_base=63300000,training_epochs_budget=10,
        retune_from_closed_splits=False,new_architecture_family=False,
        claims_learning_to_learn=False,claims_weight_transfer_across_families=False,
        is_agi=False)
    for key,value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key]!=value:
            raise ValueError('locked cross-environment pilot design/budget changed')
    if holdout_from_rule()!=[tuple(cfg['target_physics'][0])]:
        raise ValueError('xenv rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('xenv target collides with occupied MountainCarContinuous physics')
    for file,digest in cfg['parents'].items():
        if sha(file)!=digest: raise ValueError(f'closed parent changed: {file}')
    if sha(CONFIG)!=LOCKED_CONFIG: raise ValueError('locked configuration hash drifted')
    if sha(PROTOCOL)!=LOCKED_PROTOCOL: raise ValueError('locked protocol hash drifted')
    budget(cfg);check_seeds(cfg)
    return cfg


def check_seeds(cfg):
    blocked=set()
    for name in REGISTRIES:
        module=importlib.import_module(f'nexus.world.{name}')
        other=yaml.safe_load(module.CONFIG.read_text())
        if hasattr(module,'seed_groups'):
            blocked|=set().union(*module.seed_groups(other))
    for path in Path('configs').glob('*.yaml'):
        if path.name==CONFIG.name: continue
        for value in re.findall(r'[a-z_]*base:\s*(\d+)',path.read_text()):
            blocked|={int(value)+i for i in range(64)}
    used={cfg['reset_base']+100*s+slot for s in range(N_SEEDS) for slot in range(6)}
    used|={cfg['step_seed_base']+1000*s+100*slot+k for s in range(N_SEEDS)
           for slot in range(6) for k in range(200)}
    used|={cfg['collect_prior_base']+40*s+i for s in range(N_SEEDS) for i in range(40)}
    used|={cfg['collect_target_base']+40*s+i for s in range(N_SEEDS) for i in range(40)}
    if used & blocked: raise ValueError('xenv pilot seeds collide with a closed experiment')
    if min(used)<cfg['reset_base']: raise ValueError('seed block drifted below the locked base')
    for base in OTHER_BRANCH_BLOCKS:
        if any(base<=u<base+300000 for u in used):
            raise ValueError('xenv pilot seeds collide with another live branch block')


def budget(cfg):
    prior=3*(int(cfg['prior_train'])+int(cfg['prior_val']))*N_SEEDS
    pool=(int(cfg['target_pool_train'])+int(cfg['target_pool_val']))*N_SEEDS
    episodes=6*N_SEEDS*int(cfg['episode_steps'])
    if prior+pool+episodes!=cfg['env_cap']: raise ValueError('xenv env-step allocation mismatch')
    if episodes*HORIZON*N_CAND!=cfg['model_cap']: raise ValueError('xenv imagined allocation mismatch')
    return dict(prior_collection=prior,target_pool=pool,evaluation_episodes=episodes,
                imagined=episodes*HORIZON*N_CAND,time_cap_s=cfg['time_cap_s'])

class XEnvNet(nn.Module):
    """Per-family input/output heads over one shared 64->64 tanh layer."""

    def __init__(self, families: dict[str, tuple[int, int]], seed: int = 0) -> None:
        super().__init__()
        torch.manual_seed(int(seed))
        self.families = {str(k): (int(v[0]), int(v[1])) for k, v in families.items()}
        self.in_heads = nn.ModuleDict()
        self.state_heads = nn.ModuleDict()
        self.term_heads = nn.ModuleDict()
        for name, (obs_dim, n_actions) in self.families.items():
            self.in_heads[name] = nn.Linear(obs_dim + n_actions, HIDDEN)
            self.state_heads[name] = nn.Linear(HIDDEN, obs_dim)
            self.term_heads[name] = nn.Linear(HIDDEN, 1)
        self.shared = nn.Linear(HIDDEN, HIDDEN)
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.zeros_(m.bias)

    def forward(self, name, obs_norm, action):
        name = str(name)
        obs_dim, n_actions = self.families[name]
        a = torch.as_tensor(action, dtype=torch.int64).reshape(-1)
        onehot = torch.nn.functional.one_hot(a, n_actions).to(obs_norm.dtype)
        x = torch.cat([obs_norm, onehot], dim=1)
        h = torch.tanh(self.in_heads[name](x))
        h = torch.tanh(self.shared(h))
        return self.state_heads[name](h), self.term_heads[name](h)


class XEnvModel:
    """Family-scoped view of an XEnvNet; mirrors WorldModel.step semantics."""

    def __init__(self, net, name, obs_dim, n_actions, rms) -> None:
        self.net = net
        self.name = str(name)
        self.obs_dim = int(obs_dim)
        self.n_actions = int(n_actions)
        self.obs_rms = rms

    def normalize(self, obs):
        return self.obs_rms.normalize(np.asarray(obs, dtype=np.float32).reshape(-1, self.obs_dim))

    def unnormalize(self, obs_norm):
        std = np.sqrt(self.obs_rms.var + self.obs_rms.epsilon)
        return (np.asarray(obs_norm, dtype=np.float64) * std + self.obs_rms.mean).astype(np.float32)

    def step(self, obs, action):
        self.net.eval()
        o = np.asarray(obs, dtype=np.float32).reshape(-1, self.obs_dim)
        a = np.asarray(action, dtype=np.int64).reshape(-1)
        if a.size == 1 and o.shape[0] > 1:
            a = np.full(o.shape[0], int(a.flat[0]), dtype=np.int64)
        with torch.no_grad():
            on = torch.as_tensor(self.normalize(o))
            pred, logit = self.net(self.name, on, a)
            pn = on + pred
            p = torch.sigmoid(logit)
        return self.unnormalize(pn.cpu().numpy()).reshape(o.shape), p.cpu().numpy().reshape(-1)


def fit_rms(obs):
    arr = np.asarray(obs, dtype=np.float64)
    rms = RunningMeanStd((int(arr.shape[-1]),))
    rms.update(arr)
    return rms


def _family_tensors(ds, rms):
    obs = torch.as_tensor(rms.normalize(ds.obs), dtype=torch.float32)
    nxt = torch.as_tensor(rms.normalize(ds.next_obs), dtype=torch.float32)
    act = torch.as_tensor(ds.action, dtype=torch.int64)
    term = torch.as_tensor(np.asarray(ds.terminated, dtype=np.float32))
    return obs, nxt, act, term


def _batches(n, batch, rng):
    idx = rng.permutation(n)
    return [idx[i:i + batch] for i in range(0, n, batch)]

def pretrain_shared(net, data, *, epochs, lr, seed, batch_size=128, term_weight=.25):
    """Joint training across the prior families; touches their heads + shared."""
    tensors = {str(name): _family_tensors(ds, rms) for name, (ds, rms) in data.items()}
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


def finetune_target(net, name, train, val, rms, *, epochs, lr, seed, batch_size=128, term_weight=.25):
    """Fine-tune the target family's heads + the shared layer; best-val checkpoint."""
    name = str(name)
    tr = _family_tensors(train, rms)
    va = _family_tensors(val, rms)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    mse = nn.MSELoss(); bce = nn.BCEWithLogitsLoss()
    rng = np.random.default_rng(seed)
    best = 1e18
    best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
    history = []
    for _epoch in range(int(epochs)):
        net.train()
        obs, nxt, act, term = tr
        for idx in _batches(len(obs), batch_size, rng):
            pred, logit = net(name, obs[idx], act[idx])
            loss = mse(pred, nxt[idx] - obs[idx]) + term_weight * bce(logit.reshape(-1), term[idx])
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
        net.eval()
        with torch.no_grad():
            obs, nxt, act, term = va
            pred, logit = net(name, obs, act)
            v = float((mse(pred, nxt - obs) + term_weight * bce(logit.reshape(-1), term)).item())
        history.append(v)
        if v < best:
            best = v
            best_state = {k: t.detach().cpu().clone() for k, t in net.state_dict().items()}
    net.load_state_dict(best_state)
    net.eval()
    return dict(epochs=int(epochs), best_val=best)


def prediction_mae(model, ds):
    pred, _p = model.step(ds.obs, ds.action)
    return float(np.mean(np.abs(np.asarray(pred, dtype=np.float64)
                                 - np.asarray(ds.next_obs, dtype=np.float64))))

class Meter:
    def __init__(self, cfg):
        self.deadline = time.perf_counter() + cfg['time_cap_s']
        self.env_cap = cfg['env_cap']
        self.model_cap = cfg['model_cap']
        self.env_steps = 0
        self.model_states = 0

    def check(self):
        if time.perf_counter() >= self.deadline:
            raise TimeoutError('xenv pilot time cap reached')

    def collect(self, n):
        self.check()
        self.env_steps += int(n)
        if self.env_steps > self.env_cap:
            raise RuntimeError('env-step cap reached')

    def env_step(self):
        self.check()
        self.env_steps += 1
        if self.env_steps > self.env_cap:
            raise RuntimeError('env-step cap reached')

    def instrument(self, model):
        step = model.step

        def guarded(obs, action):
            self.check()
            result = step(obs, action)
            arr = np.asarray(obs)
            self.model_states += int(arr.shape[0]) if arr.ndim > 1 else 1
            if self.model_states > self.model_cap:
                raise RuntimeError('imagined cap reached')
            return result
        model.step = guarded
        return model


def make_planner(model):
    return RandomShootingMPC(model=model, n_actions=3, horizon=HORIZON,
        n_candidates=N_CAND, seed=0, objective='predicted_reward',
        step_reward=mountaincar_step_reward, enforce_time_budget=False)


def shared_candidates(seed):
    from nexus.world.prediction_control_gap import candidate_sequences
    seq = candidate_sequences(int(seed), N_CAND, HORIZON, n_actions=3)
    if seq.shape != (N_CAND, HORIZON):
        raise ValueError('xenv candidate shape drifted')
    return seq


def h16_rollout(env, model, cfg, s, slot, meter):
    """Frozen H=16 x 16 receding control on the target physics; 256 imagined/step."""
    planner = make_planner(meter.instrument(model))
    obs = np.asarray(env.reset(seed=cfg['reset_base'] + 100 * s + slot)[0], dtype=np.float32)
    actions = []; rewards = []; seeds = []; terminated = truncated = False
    for k in range(int(cfg['episode_steps'])):
        if terminated or truncated:
            break
        seed = cfg['step_seed_base'] + 1000 * s + 100 * slot + k
        seq = shared_candidates(seed)
        scores = planner._score_batch(obs, seq)
        idx = int(np.argmax(scores))
        action = int(seq[idx, 0])
        nxt, r, terminated, truncated, _ = env.step(action)
        meter.env_step()
        actions.append(action); rewards.append(float(r)); seeds.append(int(seed))
        obs = np.asarray(nxt, dtype=np.float32)
        meter.check()
    return dict(actions=actions, rewards=rewards, seeds=seeds, n_steps=len(actions),
                terminated=bool(terminated), truncated=bool(truncated),
                episode_return=float(math.fsum(rewards)))

def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'xenv_shared_layer_beats_scratch'
    if mean < 0 and hi < 0:
        return 'xenv_shared_layer_harm_established'
    return 'xenv_shared_layer_not_established'


def summarize(cells, cfg):
    rows = {int(c['seed']): c for c in cells}
    if set(rows) != set(range(N_SEEDS)):
        raise ValueError('incomplete xenv pilot seed grid')
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
        raise RuntimeError('refusing xenv pilot overwrite')
    if subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip():
        raise RuntimeError('commit clean protocol before collection')
    subprocess.run(['git', 'merge-base', '--is-ancestor', cfg['starting_sha'], 'HEAD'], check=True)
    from nexus.tasks.spec import make_task_env
    from nexus.world.train import train_world_model
    torch.set_num_threads(1)
    started = time.perf_counter(); meter = Meter(cfg)
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
        'src/nexus/world/xenv_transfer.py', 'src/nexus/world/train.py',
        'src/nexus/world/dynamics.py', 'src/nexus/world/data.py',
        'src/nexus/world/planning.py')}
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

# __XENV_EXECUTE2__

            cell = dict(seed=s, returns=dict(xenv={}, scratch={}, reference={}),
                        mae=dict(xenv={}, scratch={}, reference={}), traces={})
            for bi, budget in enumerate(cfg['target_budgets']):
                train_b = pool_train.slice(np.arange(int(budget)))
                val_n = max(32, int(budget) // 4)
                val_b = pool_val.slice(np.arange(val_n))
                if len(val_b) != val_n or len(train_b) != int(budget):
                    raise ValueError('xenv prefix length drifted')
                rms = fit_rms(train_b.obs)
                xnet = XEnvNet(families, seed=5 + 19 * s)
                pretrain_shared(xnet, {name: (tr, fit_rms(tr.obs))
                    for name, (tr, _vl) in prior_data.items()},
                    epochs=int(cfg['pretrain_epochs']), lr=cfg['pretrain_lr'], seed=7 + 23 * s)
                finetune_target(xnet, 'mcc', train_b, val_b, rms,
                    epochs=int(cfg['finetune_epochs']), lr=cfg['finetune_lr'], seed=11 + 29 * s)
                xmodel = XEnvModel(xnet, 'mcc', spec.obs_dim, spec.n_actions, rms)
                znet = XEnvNet(families, seed=5 + 19 * s)
                finetune_target(znet, 'mcc', train_b, val_b, rms,
                    epochs=int(cfg['finetune_epochs']), lr=cfg['finetune_lr'], seed=11 + 29 * s)
                zmodel = XEnvModel(znet, 'mcc', spec.obs_dim, spec.n_actions, rms)
                rmodel, _log = train_world_model(train_b, val_b, kind='residual',
                    epochs=int(cfg['reference_epochs']), lr=cfg['reference_lr'],
                    seed=5 + 19 * s, n_actions=spec.n_actions)
                for arm, model, slot in (('xenv', xmodel, 2 * bi), ('scratch', zmodel, 2 * bi + 1),
                                         ('reference', rmodel, 4 + bi)):
                    env = make_task_env(spec)
                    try:
                        trace = h16_rollout(env, model, cfg, s, slot, meter)
                    finally:
                        env.close()
                    cell['returns'][arm][str(budget)] = trace['episode_return']
                    cell['traces'][f'{arm}@{budget}'] = trace
                    cell['mae'][arm][str(budget)] = prediction_mae(model, val_b)
            if any(not np.isfinite(v) for arm in cell['returns'].values() for v in arm.values()):
                raise ValueError('nonfinite xenv return')
            p['cells'].append(cell)
            print(f'seed={s} seconds={time.perf_counter()-started:.1f}', flush=True)
        p.update(summarize(p['cells'], cfg))
        if meter.env_steps != cfg['env_cap'] or meter.model_states != cfg['model_cap']:
            raise ValueError('xenv execution totals inconsistent with the locked budget')
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
        raise RuntimeError('incomplete/invalid xenv pilot evaluation')
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
                raise ValueError('xenv reward reconstruction drifted')
            arm, budget = name.split('@')
            if not np.isclose(trace['episode_return'],
                    row['returns'][arm][str(budget)], atol=1e-8):
                raise ValueError('xenv trace/return mismatch')
            if int(trace['n_steps']) > cfg['episode_steps']:
                raise ValueError('xenv episode length exceeded 200')
    if n_traces != 60:
        raise ValueError('xenv 60-trace grid drifted')
    if int(p['counts']['env_steps']) != cfg['env_cap'] or int(p['counts']['model_states']) != cfg['model_cap']:
        raise ValueError('xenv execution totals drifted')
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
        labels=('xenv_shared_layer_beats_scratch', 'xenv_shared_layer_harm_established',
                'xenv_shared_layer_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False,
        note='No collection. New unused target physics; closed splits untouched.')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=600, env_cap=44000, model_cap=3072000).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('xenv pilot allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before xenv pilot collection')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s']) < cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


