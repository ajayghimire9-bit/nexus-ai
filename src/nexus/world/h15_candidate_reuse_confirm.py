"""H15 same-design confirmation lock. Source-only. No collection.

Freezes the H14 controller, DiD primary, redraw stride, and budget.
Only the holdout rule and 77M seed block change. H14 stays closed.
"""
from __future__ import annotations
import hashlib
import importlib
import json
import re
from pathlib import Path
import numpy as np
import yaml
from nexus.cl.metrics import seed_level_ci
from nexus.world.planning_value import sha
from nexus.world import h14_candidate_reuse as h14
from nexus.world import mcc_multitask_128 as h10

CONFIG = Path('configs/mcc_candidate_reuse_confirm.yaml')
PROTOCOL = Path('docs/NEXUS_H15_CANDIDATE_REUSE_CONFIRM_PROTOCOL.md')
ALLOCATION = Path('configs/mcc_candidate_reuse_confirm_allocation.json')
HOLD_RULE = 'mcc_candidate_reuse_confirm_v1'
CLOSED_H14 = h14.LOCKED_TARGET
LOCKED_TARGET = (0.004, 0.0021, 0.05)
N_SEEDS = h14.N_SEEDS
N_STATES = h14.N_STATES
HORIZON = h14.HORIZON
N_CAND = h14.N_CAND
N_ACTIONS = h14.N_ACTIONS
ARMS = h14.ARMS
MODES = h14.MODES
PRIMARY_BUDGET = h14.PRIMARY_BUDGET
REGISTRIES = h14.REGISTRIES
OTHER_BRANCH_BLOCKS = h14.OTHER_BRANCH_BLOCKS + (76_000_000,)
SEED_MARGIN = h14.SEED_MARGIN
LOCKED_CONFIG = 'bc263e69e3a57ae3bcb4c27616f0c4736deaf123dab6c0c3cb49311b3804c193'
LOCKED_PROTOCOL = '4e5f7a5d0f55c6f183d1c78046597a99f5dfd8f788546a1d91c8270dad0116af'
FROZEN_H14_CONFIG = 'df155e89b8a4810bdbf04cfc121e93de7c9900235a440057dd66f7128459f81a'
FROZEN_H14_PROTOCOL = '1005e12568f3457f32638f9c7a08b0c29c7090785bf1085d097054224a012c1b'
FROZEN_H14_RAW = '7e4a74ba0a8f21f735b41cc1fbceb4d5c005f68718159c0a2077caa27934959e'
FROZEN_H14_REPORT = 'b59b62ca71f4c7e9829f03eb62dd7de0628bcc665ba00b9b2d18983cad301dc5'
FROZEN_H14_CODE = 'dd997185e4672fda6b7b575fbee6b86f06814a9987ff85d67f350344bfb9e15e'
FROZEN_H14_RUNNER = '9f3573d459c6ae6688cff26fb02dc64720edff6641ead33999adfbcc2b3334f7'
FROZEN_H14_FIELDS = (
    'n_model_seeds', 'source_family', 'target_family', 'target_budget',
    'n_source_physics', 'source_train', 'target_train', 'target_val',
    'pretrain_epochs', 'train_epochs', 'train_lr', 'term_weight', 'batch_size',
    'hidden', 'horizon', 'n_candidates', 'n_actions', 'n_states',
    'episode_steps', 'restore_method', 'closed_loop_horizon',
    'share_step0_scores', 'include_shared_open_loop',
    'h10_negative_seeds_used', 'full_episode_primary', 'closed_loop_is_primary',
    'practical_margin', 'time_cap_s', 'env_cap', 'model_cap',
    'cross_family_weights', 'new_architecture_family', 'retune_from_closed_splits',
    'claims_learning_to_learn', 'is_agi',
)


def source_physics_keys():
    return h14.source_physics_keys()


def occupied_physics():
    occupied = set(h14.occupied_physics())
    occupied.add(CLOSED_H14)
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


def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if not all(np.isfinite(v) for v in (mean, lo, hi)):
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'h15_fixed_library_helps_multitask_relative'
    if mean < 0 and hi < 0:
        return 'h15_redraw_helps_multitask_relative'
    return 'h15_resampling_effect_not_established'


def summarize(cells):
    rows = {int(c['seed']): c for c in cells}
    if len(cells) != N_SEEDS or set(rows) != set(range(N_SEEDS)) or len(rows) != len(cells):
        raise ValueError('incomplete or duplicated seed grid')
    diffs = []
    for seed in range(N_SEEDS):
        means = h14.mean_seed_returns(rows[seed]['states'])
        diffs.append(h14.difference_in_differences(means))
    interval = seed_level_ci(diffs)
    return dict(label=classify_primary(interval['mean'], interval['lo'], interval['hi'], N_SEEDS, True),
                groups=dict(primary=dict(per_seed=diffs, interval=interval,
                    metric='fixed_minus_redraw_relative_multitask_advantage',
                    budget=PRIMARY_BUDGET)))


def budget(*, include_shared_open_loop=True, share_step0_scores=False):
    return h14.budget(include_shared_open_loop=include_shared_open_loop,
                      share_step0_scores=share_step0_scores)


def seed_streams(cfg):
    return h14.seed_streams(cfg)


def redraw_alias_count(cfg):
    """Locked H14 stride: unique redraw seeds versus intended (s,k,t) slots."""
    intended = N_SEEDS * N_STATES * (HORIZON - 1)
    unique = len(seed_streams(cfg)[0]['redraw'])
    return dict(intended=intended, unique=unique, aliased=intended - unique)


def assert_h14_frozen():
    if sha(h14.CONFIG) != FROZEN_H14_CONFIG:
        raise ValueError('H14 configuration drifted')
    if sha(h14.PROTOCOL) != FROZEN_H14_PROTOCOL:
        raise ValueError('H14 protocol drifted')
    if sha('artifacts/h14_candidate_reuse.json') != FROZEN_H14_RAW:
        raise ValueError('closed H14 artifact drifted')
    if sha('docs/NEXUS_H14_CANDIDATE_REUSE_RESULTS.md') != FROZEN_H14_REPORT:
        raise ValueError('closed H14 report drifted')
    if sha('src/nexus/world/h14_candidate_reuse.py') != FROZEN_H14_CODE:
        raise ValueError('H14 lock implementation drifted')
    if sha('src/nexus/world/h14_candidate_reuse_runner.py') != FROZEN_H14_RUNNER:
        raise ValueError('H14 runner drifted')
    if h14.holdout_from_rule() != [CLOSED_H14]:
        raise ValueError('H14 holdout drifted')
    if h14.source_physics_keys() != source_physics_keys():
        raise ValueError('confirmation source physics drifted from H14')


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    parent = yaml.safe_load(h14.CONFIG.read_text())
    h10_cfg = yaml.safe_load(h10.CONFIG.read_text())
    locked = dict(starting_sha='b05f9f2c9f3a5bd63ce0b55655d888d7f95d57b8',
        n_model_seeds=10, source_family='mountaincar_continuous',
        target_family='mountaincar_continuous', holdout_rule=HOLD_RULE,
        target_budget=PRIMARY_BUDGET, n_source_physics=3,
        source_train=512, target_train=128, target_val=32,
        pretrain_epochs=15, train_epochs=20, train_lr=.001, term_weight=.25,
        batch_size=128, hidden=[64, 64], horizon=HORIZON, n_candidates=N_CAND,
        n_actions=N_ACTIONS, n_states=N_STATES, episode_steps=16,
        restore_method='reset_same_seed', closed_loop_horizon=HORIZON,
        share_step0_scores=False, include_shared_open_loop=True,
        h10_negative_seeds_used=False, full_episode_primary=False,
        closed_loop_is_primary=False, practical_margin=0.0, time_cap_s=300,
        env_cap=29760, model_cap=655360, reset_base=77000000,
        state_reset_base=77100000, library_base=77200000,
        collect_source_base=77300000, collect_target_base=77400000,
        redraw_base=77500000, cross_family_weights=False,
        new_architecture_family=False, retune_from_closed_splits=False,
        claims_learning_to_learn=False, is_agi=False)
    for key, value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError(f'locked H15 design/budget changed: {key}')
    for key in FROZEN_H14_FIELDS:
        if cfg[key] != parent[key]:
            raise ValueError(f'H15 hyperparameter drifted from H14: {key}')
    for key in h14.FROZEN_TRAIN_FIELDS:
        if cfg[key] != h10_cfg[key]:
            raise ValueError(f'H15 training recipe drifted from H10: {key}')
    if cfg['source_physics'] != parent['source_physics']:
        raise ValueError('H15 source physics drifted from H14')
    if holdout_from_rule() != [tuple(cfg['target_physics'][0])]:
        raise ValueError('H15 rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) != LOCKED_TARGET:
        raise ValueError('H15 target physics drifted')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('H15 target collides with occupied physics')
    if tuple(cfg['target_physics'][0]) in {
            h14.CLOSED_H10, h14.CLOSED_H11, h14.CLOSED_H12, h14.CLOSED_H13, CLOSED_H14}:
        raise ValueError('H15 must not reuse H10-H14 holdouts')
    for file, digest in cfg['parents'].items():
        if sha(file) != digest:
            raise ValueError(f'closed parent changed: {file}')
    if sha(CONFIG) != LOCKED_CONFIG:
        raise ValueError('locked configuration hash drifted')
    if sha(PROTOCOL) != LOCKED_PROTOCOL:
        raise ValueError('locked protocol hash drifted')
    assert_h14_frozen()
    h14.assert_budget(cfg)
    check_seeds(cfg)
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
    _streams, used = seed_streams(cfg)
    if used & blocked:
        raise ValueError('H15 seeds collide with a closed experiment')
    if min(used) < cfg['reset_base']:
        raise ValueError('seed block drifted below the locked base')
    for base_id in OTHER_BRANCH_BLOCKS:
        if any(base_id <= u < base_id + 300000 for u in used):
            raise ValueError('H15 seeds collide with another live branch block')
    parent = yaml.safe_load(h14.CONFIG.read_text())
    _parent_streams, h14_used = h14.seed_streams(parent)
    if used & h14_used:
        raise ValueError('H15 seeds overlap the closed H14 block')
    aliases = redraw_alias_count(cfg)
    parent_aliases = redraw_alias_count(parent)
    if aliases['unique'] != parent_aliases['unique'] or aliases['intended'] != parent_aliases['intended']:
        raise ValueError('H15 redraw stride drifted from the locked H14 formula')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=300, env_cap=29760, model_cap=655360).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('H15 allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    authorized = record.get('authorized')
    runs = int(record.get('runs', -1))
    if authorized is False:
        if runs != 0:
            raise ValueError('unauthorized H15 allocation must have runs=0')
    elif authorized is True:
        if runs != 1:
            raise ValueError('authorized H15 allocation must be exactly one run')
        if not record.get('one_run_usage_record'):
            raise ValueError('authorized H15 allocation missing usage record')
    else:
        raise ValueError('H15 allocation authorized flag invalid')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before H15 collection')
    if record.get('consumed') is True or record.get('closed') is True:
        raise PermissionError('H15 one-run allowance already consumed')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if usage.get('consumed') is True:
        raise PermissionError('H15 one-run allowance already consumed')
    if float(usage['remaining_session_allowance_s']) < cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def prep():
    cfg = load_config()
    record = load_allocation()
    if record.get('authorized') is True or int(record.get('runs', 0)) != 0:
        raise PermissionError('prep refuses an already authorized allocation')
    return dict(complete=True, authorized=False, runs=0, locked=True,
        trained=False, runner_implemented=False,
        new_environment_steps=0, new_imagined_transitions=0,
        config_sha256=sha(CONFIG), protocol_sha256=sha(PROTOCOL),
        allocation_sha256=sha(ALLOCATION), target_physics=list(holdout_from_rule()[0]),
        holdout_rule=HOLD_RULE, source_physics=[list(k) for k in source_physics_keys()],
        n_states=N_STATES, n_candidates=N_CAND, horizon=HORIZON,
        restore_method=cfg['restore_method'], proposed_budget=h14.assert_budget(cfg),
        redraw_aliasing=redraw_alias_count(cfg),
        arms=list(ARMS), modes=list(MODES),
        labels=('h15_fixed_library_helps_multitask_relative',
                'h15_redraw_helps_multitask_relative',
                'h15_resampling_effect_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False, full_episode_primary=False,
        closed_loop_is_primary=False, share_step0_scores=False,
        note='Same-design confirmation lock. No collection. H14 stays closed.')


def execute():
    cfg = load_config()
    require_allocation(cfg)
    raise PermissionError('H15 collection is not implemented on this prep branch')
