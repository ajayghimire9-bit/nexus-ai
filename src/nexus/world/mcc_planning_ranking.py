"""Same-state MCC planning-ranking diagnostic. Preparation only.

Tests whether H10-recipe multitask ranks shared H=16 candidates better
than scratch on matched reset states. Pendulum already has a student-versus
zero ranking audit; this MCC multitask-versus-scratch grid has not been run.
Collection is unauthorized.
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
from nexus.world import mcc_multitask_128 as h10
from nexus.world import mcc_multitask_128_confirm as h11

CONFIG = Path('configs/mcc_planning_ranking.yaml')
PROTOCOL = Path('docs/NEXUS_MCC_PLANNING_RANKING_PROTOCOL.md')
ALLOCATION = Path('configs/mcc_planning_ranking_allocation.json')
OUTPUT = Path('artifacts/mcc_planning_ranking.json')
HOLD_RULE = 'mcc_planning_ranking_v1'
CLOSED_H11 = (0.0022, 0.0016, 0.07)
N_SEEDS = 10
N_STATES = 4
HORIZON = 16
N_CAND = 16
N_ACTIONS = 3
N_ARMS = 2
PRIMARY_BUDGET = 128
LOCKED_CONFIG = '17a48088591e8c9316f5b6bffd7cefac48ea2daf158cac98555204b47546feb6'
LOCKED_PROTOCOL = '6acea6f51bdc8ec0ce0f72ce08996f38a333e2e68f854b8fb6c77e218a57148b'
REGISTRIES = h11.REGISTRIES
OTHER_BRANCH_BLOCKS = h11.OTHER_BRANCH_BLOCKS + (73_000_000,)
SEED_MARGIN = h11.SEED_MARGIN
ARMS = ('multitask', 'scratch')
FROZEN_TRAIN_FIELDS = (
    'n_model_seeds', 'source_family', 'target_family', 'target_budget',
    'n_source_physics', 'source_train', 'target_train', 'target_val',
    'pretrain_epochs', 'train_epochs', 'train_lr', 'term_weight', 'batch_size',
    'hidden', 'horizon', 'n_candidates', 'n_actions',
    'cross_family_weights', 'new_architecture_family', 'retune_from_closed_splits',
    'claims_learning_to_learn', 'is_agi',
)


def source_specs():
    return h10.source_specs()


def source_physics_keys():
    return h10.source_physics_keys()


def occupied_physics():
    occupied = set(h11.occupied_physics())
    occupied.add(h11.CLOSED_H10)
    occupied.add(CLOSED_H11)
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
    return _mcc('mcc_planning_rank_t0', 'mcc_planning_ranking',
        f'Same-state ranking diagnostic target {key}.',
        gravity=key[0], power=key[1], max_speed=key[2])


def sequence_regret(predicted, actual):
    """Nonnegative: best realized candidate return minus selected realized return."""
    pred = np.asarray(predicted, dtype=np.float64).reshape(-1)
    real = np.asarray(actual, dtype=np.float64).reshape(-1)
    if pred.shape != real.shape or pred.size == 0:
        raise ValueError('predicted and realized candidate returns must align')
    if not np.isfinite(pred).all() or not np.isfinite(real).all():
        raise ValueError('nonfinite candidate returns')
    selected = int(np.argmax(pred))
    regret = float(np.max(real) - real[selected])
    if regret < -1e-12:
        raise ValueError('sequence regret became negative')
    return float(max(regret, 0.0))


def first_action_values(scores, sequences):
    seq = np.asarray(sequences, dtype=np.int64)
    val = np.asarray(scores, dtype=np.float64).reshape(-1)
    if seq.ndim != 2 or seq.shape[0] != val.size:
        raise ValueError('first-action values need paired sequences')
    out = {}
    for action in range(N_ACTIONS):
        mask = seq[:, 0] == action
        if np.any(mask):
            out[int(action)] = float(np.max(val[mask]))
    if not out:
        raise ValueError('no first actions in the candidate set')
    return out


def first_action_regret(predicted, actual, sequences):
    """Nonnegative: best realized first-action value minus selected first-action value."""
    pred_v = first_action_values(predicted, sequences)
    real_v = first_action_values(actual, sequences)
    chosen = max(pred_v, key=pred_v.get)
    if chosen not in real_v:
        raise ValueError('selected first action missing from realized set')
    best = max(real_v.values())
    regret = float(best - real_v[chosen])
    if regret < -1e-12:
        raise ValueError('first-action regret became negative')
    return float(max(regret, 0.0))


def restore_is_reset_seed(method):
    """Ground-truth candidates are restored only by env.reset(seed=state_seed)."""
    return method == 'reset_same_seed'


def budget(cfg):
    source = int(cfg['n_source_physics']) * int(cfg['source_train']) * N_SEEDS
    target = (int(cfg['target_train']) + int(cfg['target_val'])) * N_SEEDS
    gt = N_SEEDS * int(cfg['n_states']) * N_CAND * HORIZON
    closed = N_SEEDS * N_ARMS * int(cfg['n_states']) * HORIZON
    imagined_score = N_SEEDS * N_ARMS * int(cfg['n_states']) * N_CAND * HORIZON
    imagined_recede = N_SEEDS * N_ARMS * int(cfg['n_states']) * HORIZON * N_CAND * HORIZON
    if source + target + gt + closed != cfg['env_cap']:
        raise ValueError('ranking env-step allocation mismatch')
    if imagined_score + imagined_recede != cfg['model_cap']:
        raise ValueError('ranking imagined allocation mismatch')
    if int(cfg['target_train']) != PRIMARY_BUDGET:
        raise ValueError('ranking target budget drifted')
    if int(cfg['n_states']) != N_STATES:
        raise ValueError('ranking state grid drifted')
    return dict(source_collection=source, target_pool=target, ground_truth_open_loop=gt,
                closed_loop_recede=closed, imagined_score=imagined_score,
                imagined_recede=imagined_recede, time_cap_s=cfg['time_cap_s'])


def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'mcc_planning_ranking_multitask_better'
    if mean < 0 and hi < 0:
        return 'mcc_planning_ranking_scratch_better'
    return 'mcc_planning_ranking_not_established'


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    h10_cfg = yaml.safe_load(h10.CONFIG.read_text())
    locked = dict(starting_sha='95dbebc962e53c12f271fe8ed02fe61c2ac55fc5',
        n_model_seeds=10, source_family='mountaincar_continuous',
        target_family='mountaincar_continuous', holdout_rule=HOLD_RULE,
        target_budget=PRIMARY_BUDGET, n_source_physics=3,
        source_train=512, target_train=128, target_val=32,
        pretrain_epochs=15, train_epochs=20, train_lr=.001, term_weight=.25,
        batch_size=128, hidden=[64, 64], horizon=HORIZON, n_candidates=N_CAND,
        n_actions=N_ACTIONS, n_states=N_STATES, episode_steps=16,
        restore_method='reset_same_seed', closed_loop_horizon=HORIZON,
        h10_negative_seeds_used=False, full_episode_primary=False,
        practical_margin=0.0, time_cap_s=300, env_cap=28480, model_cap=348160,
        reset_base=74000000, state_reset_base=74100000, candidate_base=74200000,
        collect_source_base=74300000, collect_target_base=74400000,
        closed_loop_step_base=74500000,
        cross_family_weights=False, new_architecture_family=False,
        retune_from_closed_splits=False, claims_learning_to_learn=False, is_agi=False)
    for key, value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError('locked ranking design/budget changed')
    for key in FROZEN_TRAIN_FIELDS:
        if cfg[key] != h10_cfg[key]:
            raise ValueError(f'ranking training recipe drifted from H10: {key}')
    if cfg['source_physics'] != h10_cfg['source_physics']:
        raise ValueError('ranking source physics drifted from H10')
    if cfg['h10_negative_seeds_used'] is not False:
        raise ValueError('H11 seeds 4/5 must not select physics or candidates')
    if not restore_is_reset_seed(cfg['restore_method']):
        raise ValueError('restore method drifted')
    if holdout_from_rule() != [tuple(cfg['target_physics'][0])]:
        raise ValueError('ranking rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('ranking target collides with occupied physics')
    if tuple(cfg['target_physics'][0]) in {h11.CLOSED_H10, CLOSED_H11}:
        raise ValueError('ranking must not reuse H10 or H11 holdouts')
    spec = target_spec(tuple(cfg['target_physics'][0]))
    if spec.family != 'mountaincar_continuous' or spec.n_actions != N_ACTIONS:
        raise ValueError('ranking target is not MountainCarContinuous')
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
    used = {cfg['state_reset_base'] + 10 * s + k for s in range(N_SEEDS) for k in range(N_STATES)}
    used |= {cfg['candidate_base'] + 10 * s + k for s in range(N_SEEDS) for k in range(N_STATES)}
    used |= {cfg['collect_source_base'] + 120 * s + i for s in range(N_SEEDS) for i in range(120)}
    used |= {cfg['collect_target_base'] + 40 * s + i for s in range(N_SEEDS) for i in range(40)}
    used |= {cfg['closed_loop_step_base'] + 1000 * s + 100 * arm + k
             for s in range(N_SEEDS) for arm in range(N_ARMS) for k in range(HORIZON)}
    used |= {cfg['reset_base'] + s for s in range(N_SEEDS)}
    if used & blocked:
        raise ValueError('ranking seeds collide with a closed experiment')
    if min(used) < cfg['reset_base']:
        raise ValueError('seed block drifted below the locked base')
    for base_id in OTHER_BRANCH_BLOCKS:
        if any(base_id <= u < base_id + 300000 for u in used):
            raise ValueError('ranking seeds collide with another live branch block')


def summarize(cells, cfg):
    rows = {int(c['seed']): c for c in cells}
    if set(rows) != set(range(N_SEEDS)):
        raise ValueError('incomplete ranking seed grid')
    diffs = [float(rows[s]['sequence_regret']['scratch']) - float(rows[s]['sequence_regret']['multitask'])
             for s in range(N_SEEDS)]
    primary = seed_level_ci(diffs)
    label = classify_primary(primary['mean'], primary['lo'], primary['hi'], N_SEEDS, True)
    fa = seed_level_ci([float(rows[s]['first_action_regret']['scratch'])
                        - float(rows[s]['first_action_regret']['multitask'])
                        for s in range(N_SEEDS)])
    return dict(label=label, groups=dict(primary=dict(per_seed=diffs, interval=primary,
        budget=PRIMARY_BUDGET, metric='scratch_minus_multitask_sequence_regret'),
        first_action_regret_gain=fa))


def execute():
    cfg = load_config(); require_allocation(cfg)
    raise PermissionError('ranking collection is not authorized on this prep branch')


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
        n_states=N_STATES, n_candidates=N_CAND, horizon=HORIZON,
        restore_method=cfg['restore_method'],
        proposed_budget=budget(cfg), arms=list(ARMS),
        labels=('mcc_planning_ranking_multitask_better',
                'mcc_planning_ranking_scratch_better',
                'mcc_planning_ranking_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False, full_episode_primary=False,
        note='No collection. Small same-state grid. H10/H11 holdouts closed.')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=300, env_cap=28480, model_cap=348160).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('ranking allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before ranking collection')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s']) < cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')
