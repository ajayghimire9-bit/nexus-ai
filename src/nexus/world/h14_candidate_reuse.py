"""H14 candidate-reuse protocol lock. Source-only. No collection.

Locks shared-library versus redraw recede, the difference-in-differences
primary, unused MCC physics, 76M seed streams, and pre-operation caps.
Does not train, step a simulator, or authorize an experiment.
"""
from __future__ import annotations
import hashlib
import importlib
import json
import re
import time
from pathlib import Path
import numpy as np
import yaml
from nexus.cl.metrics import seed_level_ci
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world import mcc_multitask_128 as h10
from nexus.world import mcc_planning_ranking as h12
from nexus.world import mcc_planning_ranking_confirm as h13

CONFIG = Path('configs/mcc_candidate_reuse.yaml')
PROTOCOL = Path('docs/NEXUS_H14_CANDIDATE_REUSE_PROTOCOL.md')
ALLOCATION = Path('configs/mcc_candidate_reuse_allocation.json')
OUTPUT = Path('artifacts/h14_candidate_reuse_feasibility.json')
HOLD_RULE = 'mcc_candidate_reuse_v1'
CLOSED_H10 = (0.0032, 0.0022, 0.06)
CLOSED_H11 = (0.0022, 0.0016, 0.07)
CLOSED_H12 = (0.0027, 0.0015, 0.075)
CLOSED_H13 = (0.0039, 0.002, 0.075)
LOCKED_TARGET = (0.0023, 0.0019, 0.065)
N_SEEDS = 10
N_STATES = 4
N_ARMS = 2
N_MODES = 2
HORIZON = 16
N_CAND = 16
N_ACTIONS = 3
ARMS = ('multitask', 'scratch')
MODES = ('fixed', 'redraw')
PRIMARY_BUDGET = 128
PROPOSED_TIME_CAP_S = 300
PROPOSED_ENV_CAP = 29760
PROPOSED_MODEL_CAP = 655360
RESET_ATOL = 1e-6
REGISTRIES = h13.REGISTRIES
OTHER_BRANCH_BLOCKS = h13.OTHER_BRANCH_BLOCKS + (75_000_000,)
SEED_MARGIN = h13.SEED_MARGIN
LOCKED_CONFIG = 'df155e89b8a4810bdbf04cfc121e93de7c9900235a440057dd66f7128459f81a'
LOCKED_PROTOCOL = '1005e12568f3457f32638f9c7a08b0c29c7090785bf1085d097054224a012c1b'
FROZEN_H12_CODE = '2cc7342ca747f4a667f14171353dad36a89907ac38bb475a94a7a862ef85d817'
FROZEN_H13_CODE = 'fb98d762d0c7cbca76d10ebf6238efbc3ce233155a123be627bba1b1ba13532f'
FROZEN_H10_CODE = '79a26fed3d0b4a852cd8194492ae67977af41965a56effc01d7441b006dfc701'
FROZEN_TRAIN_FIELDS = (
    'n_model_seeds', 'source_family', 'target_family', 'target_budget',
    'n_source_physics', 'source_train', 'target_train', 'target_val',
    'pretrain_epochs', 'train_epochs', 'train_lr', 'term_weight', 'batch_size',
    'hidden', 'horizon', 'n_candidates', 'n_actions',
    'cross_family_weights', 'new_architecture_family', 'retune_from_closed_splits',
    'claims_learning_to_learn', 'is_agi',
)
TRACE_FIELDS = (
    'seed', 'state_index', 'mode', 'arm', 'state_seed', 'reset_observation',
    'step', 'candidate_seed', 'library_fingerprint', 'observation',
    'predicted_scores', 'selected_index', 'executed_action', 'next_observation',
    'realized_reward', 'terminated', 'truncated', 'env_steps',
    'imagined_transitions',
)
SECONDARIES = (
    'multitask_minus_scratch_fixed',
    'multitask_minus_scratch_redraw',
    'open_loop_selected_return',
    'open_loop_sequence_regret',
    'initial_candidate_ranking',
    'later_state_action_disagreement',
    'predicted_score_behavior',
    'executed_transition_one_step_residual',
)


def source_physics_keys():
    return h13.source_physics_keys()


def occupied_physics():
    occupied = set(h13.occupied_physics())
    occupied.update((CLOSED_H10, CLOSED_H11, CLOSED_H12, CLOSED_H13))
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


def shared_library_seed(library_base, seed, state_index):
    """State-specific first matrix. No arm term. Shared by both modes at step 0."""
    return int(library_base) + 10 * int(seed) + int(state_index)


def redraw_step_seed(redraw_base, seed, state_index, step):
    """Later redraws. State-specific. No arm term. Step 0 is forbidden."""
    if int(step) <= 0:
        raise ValueError('redraw step 0 must reuse the shared first library')
    return int(redraw_base) + 1000 * int(seed) + 10 * int(state_index) + int(step)


def recede_candidates(mode, library_base, redraw_base, seed, state_index, step):
    """Return the candidate matrix for one recede decision.

    Planners receive only this matrix and the current observation. Realized
    counterfactual returns are not arguments.
    """
    if mode not in MODES:
        raise ValueError('unknown recede mode')
    if int(step) == 0 or mode == 'fixed':
        seed_id = shared_library_seed(library_base, seed, state_index)
    else:
        seed_id = redraw_step_seed(redraw_base, seed, state_index, step)
    seq = candidate_sequences(seed_id, N_CAND, HORIZON, n_actions=N_ACTIONS)
    if seq.shape != (N_CAND, HORIZON):
        raise ValueError('candidate shape drifted')
    return seq


def library_fingerprint(sequences):
    arr = np.asarray(sequences, dtype=np.int64)
    if arr.shape != (N_CAND, HORIZON):
        raise ValueError('candidate shape drifted')
    return hashlib.sha256(arr.tobytes()).hexdigest()


def score_library(model, obs, sequences):
    """Imagined scores. Realized returns are not an argument."""
    sequences = np.asarray(sequences, dtype=np.int64)
    if sequences.shape != (N_CAND, HORIZON):
        raise ValueError('candidate shape drifted')
    scores = np.asarray(model.score(obs, sequences), dtype=np.float64).reshape(-1)
    if scores.shape != (N_CAND,) or not np.isfinite(scores).all():
        raise ValueError('nonfinite or misaligned scores')
    return scores


def selected_first_action(sequences, scores):
    """First-index argmax. Same rule as H12 ranking."""
    idx = int(np.argmax(np.asarray(scores, dtype=np.float64).reshape(-1)))
    return idx, int(np.asarray(sequences, dtype=np.int64)[idx, 0])


def difference_in_differences(seed_means):
    """D_s = (mt_fixed - sc_fixed) - (mt_redraw - sc_redraw)."""
    required = {(arm, mode) for arm in ARMS for mode in MODES}
    if set(seed_means) != required:
        raise ValueError('missing arm/mode mean')
    return float((seed_means[('multitask', 'fixed')] - seed_means[('scratch', 'fixed')])
                 - (seed_means[('multitask', 'redraw')] - seed_means[('scratch', 'redraw')]))


def mean_seed_returns(state_returns):
    if len(state_returns) != N_STATES:
        raise ValueError('seed is missing a reset state')
    if {int(row['state_index']) for row in state_returns} != set(range(N_STATES)):
        raise ValueError('incomplete or duplicated state grid')
    if len({int(row['state_index']) for row in state_returns}) != len(state_returns):
        raise ValueError('duplicated state index')
    means = {}
    for arm in ARMS:
        for mode in MODES:
            means[(arm, mode)] = float(np.mean([float(row['returns'][arm][mode]) for row in state_returns]))
            if not np.isfinite(means[(arm, mode)]):
                raise ValueError('nonfinite controller return')
    return means


def summarize(cells):
    rows = {int(c['seed']): c for c in cells}
    if len(cells) != N_SEEDS or set(rows) != set(range(N_SEEDS)) or len(rows) != len(cells):
        raise ValueError('incomplete or duplicated seed grid')
    diffs = []
    for seed in range(N_SEEDS):
        means = mean_seed_returns(rows[seed]['states'])
        diffs.append(difference_in_differences(means))
    interval = seed_level_ci(diffs)
    return dict(label=classify_primary(interval['mean'], interval['lo'], interval['hi'], N_SEEDS, True),
                groups=dict(primary=dict(per_seed=diffs, interval=interval,
                    metric='fixed_minus_redraw_relative_multitask_advantage',
                    budget=PRIMARY_BUDGET)))


def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if not all(np.isfinite(v) for v in (mean, lo, hi)):
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'h14_fixed_library_helps_multitask_relative'
    if mean < 0 and hi < 0:
        return 'h14_redraw_helps_multitask_relative'
    return 'h14_resampling_effect_not_established'


def budget(*, include_shared_open_loop=True, share_step0_scores=False):
    source = 3 * 512 * N_SEEDS
    target = (128 + 32) * N_SEEDS
    recede = N_SEEDS * N_ARMS * N_MODES * N_STATES * HORIZON
    gt = N_SEEDS * N_STATES * N_CAND * HORIZON if include_shared_open_loop else 0
    env = source + target + recede + gt
    imagined_step = N_CAND * HORIZON
    if share_step0_scores:
        imagined = (N_SEEDS * N_ARMS * N_STATES * imagined_step
                    + N_SEEDS * N_ARMS * N_MODES * N_STATES * (HORIZON - 1) * imagined_step)
    else:
        imagined = N_SEEDS * N_ARMS * N_MODES * N_STATES * HORIZON * imagined_step
    return dict(source_collection=source, target_pool=target, recede_control=recede,
                shared_open_loop=gt, env_total=env, imagined_total=imagined,
                time_cap_s=PROPOSED_TIME_CAP_S, env_cap=PROPOSED_ENV_CAP,
                model_cap=PROPOSED_MODEL_CAP)


def assert_budget(cfg):
    counts = budget(include_shared_open_loop=bool(cfg['include_shared_open_loop']),
                    share_step0_scores=bool(cfg['share_step0_scores']))
    if counts['env_total'] != int(cfg['env_cap']) or counts['imagined_total'] != int(cfg['model_cap']):
        raise ValueError('H14 cap accounting drifted')
    if cfg['share_step0_scores'] is not False:
        raise ValueError('step-zero score caching is forbidden')
    if cfg['include_shared_open_loop'] is not True:
        raise ValueError('shared open-loop L0 evaluation is required')
    if int(cfg['env_cap']) != PROPOSED_ENV_CAP or int(cfg['model_cap']) != PROPOSED_MODEL_CAP:
        raise ValueError('H14 locked caps drifted')
    return counts


def assert_shared_first_library(library_base, seed, state_index):
    fixed0 = recede_candidates('fixed', library_base, 0, seed, state_index, 0)
    redraw0 = recede_candidates('redraw', library_base, 0, seed, state_index, 0)
    if not np.array_equal(fixed0, redraw0):
        raise ValueError('first-step libraries differ across modes')
    return fixed0


def assert_arm_symmetric_library(mode, library_base, redraw_base, seed, state_index, step):
    """Both model arms must see the same matrix; the seed has no arm term."""
    first = recede_candidates(mode, library_base, redraw_base, seed, state_index, step)
    second = recede_candidates(mode, library_base, redraw_base, seed, state_index, step)
    if not np.array_equal(first, second):
        raise ValueError('candidate library is not deterministic')
    return first


def check_reset_identity(obs, recorded, atol=RESET_ATOL):
    current = np.asarray(obs, dtype=np.float32).reshape(-1)
    expected = np.asarray(recorded, dtype=np.float32).reshape(-1)
    if current.shape != expected.shape or not np.allclose(current, expected, atol=atol, rtol=0.0):
        raise RuntimeError('reset identity failed')
    return current


def one_step_residual(predicted_next, realized_next):
    """Compare one already-executed next observation, not a full-horizon score."""
    pred = np.asarray(predicted_next, dtype=np.float64).reshape(-1)
    real = np.asarray(realized_next, dtype=np.float64).reshape(-1)
    if pred.shape != real.shape or pred.size == 0:
        raise ValueError('one-step residual needs aligned next observations')
    if not np.isfinite(pred).all() or not np.isfinite(real).all():
        raise ValueError('nonfinite one-step residual')
    return pred - real


def controller_trace(**fields):
    missing = [name for name in TRACE_FIELDS if name not in fields]
    if missing:
        raise ValueError(f'missing trace fields: {missing}')
    extra = [name for name in fields if name not in TRACE_FIELDS]
    if extra:
        raise ValueError(f'unknown trace fields: {extra}')
    if fields['mode'] not in MODES or fields['arm'] not in ARMS:
        raise ValueError('trace arm or mode is invalid')
    scores = np.asarray(fields['predicted_scores'], dtype=np.float64).reshape(-1)
    if scores.shape != (N_CAND,) or not np.isfinite(scores).all():
        raise ValueError('predicted scores invalid')
    return {name: fields[name] for name in TRACE_FIELDS}


def seed_streams(cfg):
    streams = {
        'reset': {int(cfg['reset_base']) + s for s in range(N_SEEDS)},
        'state': {int(cfg['state_reset_base']) + 10 * s + k
                  for s in range(N_SEEDS) for k in range(N_STATES)},
        'library': {int(cfg['library_base']) + 10 * s + k
                    for s in range(N_SEEDS) for k in range(N_STATES)},
        'source': {int(cfg['collect_source_base']) + 120 * s + i
                   for s in range(N_SEEDS) for i in range(120)},
        'target': {int(cfg['collect_target_base']) + 40 * s + i
                   for s in range(N_SEEDS) for i in range(40)},
        'redraw': {int(cfg['redraw_base']) + 1000 * s + 10 * k + t
                   for s in range(N_SEEDS) for k in range(N_STATES)
                   for t in range(1, HORIZON)},
    }
    used = set()
    for name, group in streams.items():
        if used & group:
            raise ValueError(f'seed stream {name} overlaps another H14 purpose')
        used |= group
    return streams, used


class PreflightMeter:
    """Reserve before simulator steps and imagined batches.

    Inherited H12 meters increment, then reject if the count exceeds the
    cap, so one extra step or batch can run. This meter rejects if
    used + n would exceed the cap, then adds n, then the caller executes.
    Reserved-but-failed operations stay counted.
    """

    def __init__(self, cfg):
        self.deadline = time.perf_counter() + float(cfg['time_cap_s'])
        self.env_cap = int(cfg['env_cap'])
        self.model_cap = int(cfg['model_cap'])
        self.env_steps = 0
        self.model_states = 0

    def check(self):
        if time.perf_counter() >= self.deadline:
            raise TimeoutError('H14 time cap reached')

    def reserve_env(self, n=1):
        self.check()
        n = int(n)
        if n < 1:
            raise ValueError('env reservation must be positive')
        if self.env_steps + n > self.env_cap:
            raise RuntimeError('env-step cap would be exceeded')
        self.env_steps += n
        return self.env_steps

    def reserve_imagined(self, n):
        self.check()
        n = int(n)
        if n < 1:
            raise ValueError('imagined batch size must be positive')
        if self.model_states + n > self.model_cap:
            raise RuntimeError('imagined cap would be exceeded')
        self.model_states += n
        return self.model_states

    def preflight_collection(self, n):
        return self.reserve_env(n)

    def instrument(self, model):
        step = model.step

        def guarded(obs, action):
            arr = np.asarray(obs)
            n = int(arr.shape[0]) if arr.ndim > 1 else 1
            self.reserve_imagined(n)
            return step(obs, action)

        model.step = guarded
        return model


def assert_h12_h13_frozen():
    if sha('src/nexus/world/mcc_planning_ranking.py') != FROZEN_H12_CODE:
        raise ValueError('H12 implementation drifted')
    if sha('src/nexus/world/mcc_planning_ranking_confirm.py') != FROZEN_H13_CODE:
        raise ValueError('H13 implementation drifted')
    if sha('src/nexus/world/mcc_multitask_128.py') != FROZEN_H10_CODE:
        raise ValueError('H10 implementation drifted')
    if h12.holdout_from_rule() != [CLOSED_H12]:
        raise ValueError('H12 holdout drifted')
    if h13.holdout_from_rule() != [CLOSED_H13]:
        raise ValueError('H13 holdout drifted')


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    h10_cfg = yaml.safe_load(h10.CONFIG.read_text())
    locked = dict(starting_sha='1949beda85f210521991c82294904ea415a07f39',
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
        env_cap=29760, model_cap=655360, reset_base=76000000,
        state_reset_base=76100000, library_base=76200000,
        collect_source_base=76300000, collect_target_base=76400000,
        redraw_base=76500000, cross_family_weights=False,
        new_architecture_family=False, retune_from_closed_splits=False,
        claims_learning_to_learn=False, is_agi=False)
    for key, value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError(f'locked H14 design/budget changed: {key}')
    for key in FROZEN_TRAIN_FIELDS:
        if cfg[key] != h10_cfg[key]:
            raise ValueError(f'H14 training recipe drifted from H10: {key}')
    if cfg['source_physics'] != h10_cfg['source_physics']:
        raise ValueError('H14 source physics drifted from H10')
    if cfg['h10_negative_seeds_used'] is not False:
        raise ValueError('H11 seeds 4/5 must not select physics or candidates')
    if cfg['restore_method'] != 'reset_same_seed':
        raise ValueError('restore method drifted')
    if holdout_from_rule() != [tuple(cfg['target_physics'][0])]:
        raise ValueError('H14 rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) != LOCKED_TARGET:
        raise ValueError('H14 target physics drifted')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('H14 target collides with occupied physics')
    if tuple(cfg['target_physics'][0]) in {CLOSED_H10, CLOSED_H11, CLOSED_H12, CLOSED_H13}:
        raise ValueError('H14 must not reuse H10-H13 holdouts')
    for file, digest in cfg['parents'].items():
        if sha(file) != digest:
            raise ValueError(f'closed parent changed: {file}')
    if sha(CONFIG) != LOCKED_CONFIG:
        raise ValueError('locked configuration hash drifted')
    if sha(PROTOCOL) != LOCKED_PROTOCOL:
        raise ValueError('locked protocol hash drifted')
    assert_h12_h13_frozen()
    assert_budget(cfg)
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
        raise ValueError('H14 seeds collide with a closed experiment')
    if min(used) < cfg['reset_base']:
        raise ValueError('seed block drifted below the locked base')
    for base_id in OTHER_BRANCH_BLOCKS:
        if any(base_id <= u < base_id + 300000 for u in used):
            raise ValueError('H14 seeds collide with another live branch block')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=300, env_cap=29760, model_cap=655360).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('H14 allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    authorized = record.get('authorized')
    runs = int(record.get('runs', -1))
    if authorized is False:
        if runs != 0:
            raise ValueError('unauthorized H14 allocation must have runs=0')
    elif authorized is True:
        if runs != 1:
            raise ValueError('authorized H14 allocation must be exactly one run')
        if not record.get('one_run_usage_record'):
            raise ValueError('authorized H14 allocation missing usage record')
    else:
        raise ValueError('H14 allocation authorized flag invalid')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before H14 collection')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if float(usage['remaining_session_allowance_s']) < cfg['time_cap_s']:
        raise PermissionError('session allowance exhausted')


def prep():
    cfg = load_config()
    record = load_allocation()
    if record.get('authorized') is True or int(record.get('runs', 0)) != 0:
        raise PermissionError('prep refuses an already authorized allocation')
    return dict(complete=True, authorized=False, runs=0, locked=True,
        trained=False, new_environment_steps=0, new_imagined_transitions=0,
        config_sha256=sha(CONFIG), protocol_sha256=sha(PROTOCOL),
        allocation_sha256=sha(ALLOCATION), target_physics=list(holdout_from_rule()[0]),
        holdout_rule=HOLD_RULE, source_physics=[list(k) for k in source_physics_keys()],
        n_states=N_STATES, n_candidates=N_CAND, horizon=HORIZON,
        restore_method=cfg['restore_method'], proposed_budget=assert_budget(cfg),
        arms=list(ARMS), modes=list(MODES), secondaries=list(SECONDARIES),
        labels=('h14_fixed_library_helps_multitask_relative',
                'h14_redraw_helps_multitask_relative',
                'h14_resampling_effect_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False, full_episode_primary=False,
        closed_loop_is_primary=False, share_step0_scores=False,
        note='Protocol lock only. No collection. H10-H13 stay closed.')


def execute():
    cfg = load_config()
    require_allocation(cfg)
    raise PermissionError('H14 collection is not implemented on this lock branch')
