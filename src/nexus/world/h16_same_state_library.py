"""H16 same-state library protocol lock. Source-only. No collection.

Locks the common-later-state L0-versus-redraw ranking contrast, unused
MCC physics, 78M seed streams, reset-plus-prefix restoration contract,
and 84,000 / 81,920 caps. Does not train, construct MountainCar, or
authorize an experiment.
"""
from __future__ import annotations
import hashlib
import importlib
import inspect
import json
import re
from pathlib import Path
import numpy as np
import yaml
from nexus.cl.metrics import seed_level_ci
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world import h14_candidate_reuse as h14
from nexus.world import h15_candidate_reuse_confirm as h15
from nexus.world import mcc_multitask_128 as h10
from nexus.world import h16_same_state_library_feasibility as feas

CONFIG = Path('configs/mcc_same_state_library.yaml')
PROTOCOL = Path('docs/NEXUS_H16_SAME_STATE_LIBRARY_PROTOCOL.md')
ALLOCATION = Path('configs/mcc_same_state_library_allocation.json')
PROVENANCE = Path('artifacts/h16_same_state_library_provenance.json')
HOLD_RULE = 'mcc_same_state_library_v1'
CLOSED_H14 = h14.LOCKED_TARGET
CLOSED_H15 = h15.LOCKED_TARGET
LOCKED_TARGET = (0.0015, 0.0014, 0.055)
HOLD_COUNTER = 0
HOLD_INDEX = 16634735916735444846
N_SEEDS = 10
N_STATES = 4
LATER_TIMES = (8, 12)
N_TIMES = 2
LIBS = ('l0', 'redraw')
ARMS = h14.ARMS
HORIZON = 16
N_CAND = 16
N_ACTIONS = 3
PRIMARY_BUDGET = 128
PROPOSED_ENV_CAP = 84_000
PROPOSED_MODEL_CAP = 81_920
PROPOSED_TIME_CAP_S = 300
RESTORE_METHOD = 'reset_plus_action_prefix'
REGISTRIES = h15.REGISTRIES
OTHER_BRANCH_BLOCKS = h15.OTHER_BRANCH_BLOCKS + (76_000_000, 77_000_000)
SEED_MARGIN = h15.SEED_MARGIN
LOCKED_CONFIG = 'e71b0053331afa39db5b368510c8524d23e454fb490a2bde57e72ac39f32834c'
LOCKED_PROTOCOL = 'f757e8a8e1f08d0b5abeb7cffa84071a79e1c5e93ded89b6817fe25e8f7fcea7'
FROZEN_H10_FIELDS = h14.FROZEN_TRAIN_FIELDS
GRAVITIES = [round(x * 0.0001, 4) for x in range(15, 41)]
POWERS = [round(x * 0.0001, 4) for x in range(8, 23)]
SPEEDS = [round(x * 0.005, 3) for x in range(10, 19)]
REQUIRED_WRAPPERS = (
    'MountainCarDenseRewardWrapper',
    'DiscreteTorqueWrapper',
    'ContinuousMountainCarGravityPatch',
    'TimeLimit',
)
FORBIDDEN_WRAPPERS = ('ObservationNoiseWrapper', 'ActionDelayWrapper')
RESTORATION = dict(
    method=RESTORE_METHOD,
    direct_state_mutation=False,
    empirical_status='runner_time_gate_not_verified_at_lock',
    reset_observation='float32_array_equal',
    raw_state='float32_array_equal',
    later_observation='float32_array_equal',
    later_raw_state='float32_array_equal',
    prefix_actions='exact_int',
    prefix_rewards='exact_float_to_reference',
    terminated_truncated='exact_false_through_t12_and_candidates',
    elapsed_steps='exact_int_equals_prefix_length',
    published_reward_check='inherited_h12_reward_atol_1e-5',
    time_limit_steps=200,
)


def source_physics_keys():
    return h15.source_physics_keys()


def occupied_physics():
    occupied = set(h15.occupied_physics())
    occupied.add(CLOSED_H14)
    occupied.add(CLOSED_H15)
    occupied.update(source_physics_keys())
    return occupied


def holdout_from_rule(n=1, rule=HOLD_RULE):
    occupied = occupied_physics()
    chosen = []
    counter = 0
    selected_index = None
    while len(chosen) < int(n):
        digest = hashlib.sha256(f'{rule}:{counter}'.encode()).digest()
        idx = int.from_bytes(digest[:8], 'big')
        key = (float(GRAVITIES[idx % len(GRAVITIES)]),
               float(POWERS[(idx // len(GRAVITIES)) % len(POWERS)]),
               float(SPEEDS[(idx // (len(GRAVITIES) * len(POWERS))) % len(SPEEDS)]))
        if key not in occupied and key not in chosen:
            chosen.append(key)
            if selected_index is None:
                selected_index = idx
        counter += 1
    return chosen


def holdout_trace(rule=HOLD_RULE):
    occupied = occupied_physics()
    digest = hashlib.sha256(f'{rule}:{HOLD_COUNTER}'.encode()).digest()
    idx = int.from_bytes(digest[:8], 'big')
    key = holdout_from_rule(1, rule)[0]
    return dict(rule=rule, counter=HOLD_COUNTER, index=idx, physics=key,
                occupied=sorted(occupied), grid=(len(GRAVITIES), len(POWERS), len(SPEEDS)))


def prefix_actions(prefix_base, seed, state_index, length=max(LATER_TIMES)):
    rng = np.random.default_rng(int(prefix_base) + 10 * int(seed) + int(state_index))
    return rng.integers(0, N_ACTIONS, size=int(length), dtype=np.int64)


def l0_seed(library_base, seed, state_index):
    return int(library_base) + 10 * int(seed) + int(state_index)


def redraw_seed(redraw_base, seed, state_index, later_t):
    if int(later_t) not in LATER_TIMES:
        raise ValueError('redraw time is not a locked later-state time')
    return int(redraw_base) + 10_000 * int(seed) + 100 * int(state_index) + int(later_t)


def library_for(kind, library_base, redraw_base, seed, state_index, later_t):
    if kind == 'l0':
        sid = l0_seed(library_base, seed, state_index)
    elif kind == 'redraw':
        sid = redraw_seed(redraw_base, seed, state_index, later_t)
    else:
        raise ValueError('unknown library kind')
    seq = candidate_sequences(sid, N_CAND, HORIZON, n_actions=N_ACTIONS)
    if seq.shape != (N_CAND, HORIZON):
        raise ValueError('candidate shape drifted')
    return sid, seq


def library_fingerprint(sequences):
    return h14.library_fingerprint(sequences)


def selected_index(scores):
    return int(np.argmax(np.asarray(scores, dtype=np.float64).reshape(-1)))


def oracle_return(realized):
    values = np.asarray(realized, dtype=np.float64).reshape(-1)
    if values.shape != (N_CAND,) or not np.isfinite(values).all():
        raise ValueError('oracle needs 16 finite candidate returns')
    return float(values.max())


def selected_return(realized, scores):
    values = np.asarray(realized, dtype=np.float64).reshape(-1)
    scores = np.asarray(scores, dtype=np.float64).reshape(-1)
    if values.shape != (N_CAND,) or scores.shape != (N_CAND,):
        raise ValueError('selected return needs 16 values')
    if not np.isfinite(values).all() or not np.isfinite(scores).all():
        raise ValueError('nonfinite selected return')
    return float(values[selected_index(scores)])


def within_library_regret(realized, scores):
    return oracle_return(realized) - selected_return(realized, scores)


def same_state_did(s_mt_l0, s_sc_l0, s_mt_redraw, s_sc_redraw):
    return float((s_mt_l0 - s_sc_l0) - (s_mt_redraw - s_sc_redraw))


def oracle_cancels_in_arm_gap(realized, scores_mt, scores_sc):
    gap = selected_return(realized, scores_mt) - selected_return(realized, scores_sc)
    via_regret = (within_library_regret(realized, scores_sc)
                  - within_library_regret(realized, scores_mt))
    if abs(gap - via_regret) > 1e-12:
        raise ValueError('oracle cancellation failed')
    return float(gap)


def score_library(model, obs, sequences):
    if 'realized' in inspect.signature(score_library).parameters:
        raise RuntimeError('planner scoring must not accept realized returns')
    sequences = np.asarray(sequences, dtype=np.int64)
    if sequences.shape != (N_CAND, HORIZON):
        raise ValueError('candidate shape drifted')
    scores = np.asarray(model.score(obs, sequences), dtype=np.float64).reshape(-1)
    if scores.shape != (N_CAND,) or not np.isfinite(scores).all():
        raise ValueError('nonfinite or misaligned scores')
    return scores


def classify_primary(mean, lo, hi, n, complete=True):
    if not complete or int(n) != N_SEEDS:
        return 'incomplete'
    if not all(np.isfinite(v) for v in (mean, lo, hi)):
        return 'incomplete'
    if mean > 0 and lo > 0:
        return 'h16_l0_helps_multitask_relative_same_state'
    if mean < 0 and hi < 0:
        return 'h16_redraw_helps_multitask_relative_same_state'
    return 'h16_same_state_library_effect_not_established'


def mean_seed_cells(cells):
    rows = {int(c['seed']): c for c in cells}
    if len(cells) != N_SEEDS or set(rows) != set(range(N_SEEDS)) or len(rows) != len(cells):
        raise ValueError('incomplete or duplicated seed grid')
    diffs = []
    for seed in range(N_SEEDS):
        nested = rows[seed]['later_states']
        keys = {(int(row['state_index']), int(row['later_t'])) for row in nested}
        expected = {(k, t) for k in range(N_STATES) for t in LATER_TIMES}
        if keys != expected:
            raise ValueError('incomplete or duplicated later-state grid')
        local = []
        for row in nested:
            for key in ('s_mt_l0', 's_sc_l0', 's_mt_redraw', 's_sc_redraw'):
                if not np.isfinite(float(row[key])):
                    raise ValueError('nonfinite selected return')
            local.append(same_state_did(row['s_mt_l0'], row['s_sc_l0'],
                                        row['s_mt_redraw'], row['s_sc_redraw']))
        diffs.append(float(np.mean(local)))
    interval = seed_level_ci(diffs)
    return dict(per_seed=diffs, interval=interval,
                label=classify_primary(interval['mean'], interval['lo'], interval['hi'],
                                       interval['n']))


def budget():
    source = 3 * 512 * N_SEEDS
    target = (128 + 32) * N_SEEDS
    n_groups = N_SEEDS * N_STATES
    n_later = n_groups * N_TIMES
    reference_prefix = n_groups * max(LATER_TIMES)
    prefix_replay = n_groups * 2 * N_CAND * int(sum(LATER_TIMES))
    realizations = n_later * 2 * N_CAND * HORIZON
    env_total = source + target + reference_prefix + prefix_replay + realizations
    imagined = n_later * 2 * 2 * N_CAND * HORIZON
    return dict(source_collection=source, target_pool=target,
                reference_prefix=reference_prefix, prefix_replay=prefix_replay,
                shared_candidate_realizations=realizations, env_total=env_total,
                imagined_total=imagined, time_cap_s=PROPOSED_TIME_CAP_S,
                env_cap=PROPOSED_ENV_CAP, model_cap=PROPOSED_MODEL_CAP)


def assert_budget(cfg):
    counts = budget()
    if counts['env_total'] != PROPOSED_ENV_CAP or counts['imagined_total'] != PROPOSED_MODEL_CAP:
        raise ValueError('H16 locked budget arithmetic drifted')
    if int(cfg['env_cap']) != PROPOSED_ENV_CAP or int(cfg['model_cap']) != PROPOSED_MODEL_CAP:
        raise ValueError('H16 locked caps drifted')
    if counts['env_total'] != feas.budget()['env_total']:
        raise ValueError('H16 lock budget drifted from feasibility')
    if int(cfg['env_cap']) >= feas.STANDING_ENV_CEILING:
        raise ValueError('H16 must not raise the standing interaction ceiling')
    return counts


def seed_streams(cfg):
    streams = {
        'reset': {int(cfg['reset_base']) + s for s in range(N_SEEDS)},
        'state': {int(cfg['state_reset_base']) + 10 * s + k
                  for s in range(N_SEEDS) for k in range(N_STATES)},
        'prefix': {int(cfg['prefix_base']) + 10 * s + k
                   for s in range(N_SEEDS) for k in range(N_STATES)},
        'library': {l0_seed(cfg['library_base'], s, k)
                    for s in range(N_SEEDS) for k in range(N_STATES)},
        'source': {int(cfg['collect_source_base']) + 120 * s + i
                   for s in range(N_SEEDS) for i in range(120)},
        'target': {int(cfg['collect_target_base']) + 40 * s + i
                   for s in range(N_SEEDS) for i in range(40)},
        'redraw': {redraw_seed(cfg['redraw_base'], s, k, t)
                   for s in range(N_SEEDS) for k in range(N_STATES) for t in LATER_TIMES},
        'model_init': {int(cfg['model_init_base']) + 10 * s + i
                       for s in range(N_SEEDS) for i in range(10)},
    }
    used = set()
    for name, group in streams.items():
        if used & group:
            raise ValueError(f'seed stream {name} overlaps another H16 purpose')
        used |= group
    if len(streams['redraw']) != N_SEEDS * N_STATES * N_TIMES:
        raise ValueError('H16 redraw libraries are not unique')
    return streams, used


def wrapper_stack_ok(class_names):
    names = tuple(class_names)
    if any(item in names for item in FORBIDDEN_WRAPPERS):
        return False
    return all(item in names for item in REQUIRED_WRAPPERS)


def assert_replay_identity(reference, replayed):
    """Exact restoration contract. No .state mutation."""
    if reference.get('prefix_actions') != replayed.get('prefix_actions'):
        raise RuntimeError('prefix action identity failed')
    for key in ('reset_obs', 'reset_state', 'later_obs', 'later_state'):
        a = np.asarray(reference[key], dtype=np.float32)
        b = np.asarray(replayed[key], dtype=np.float32)
        if a.shape != b.shape or not np.array_equal(a, b):
            raise RuntimeError(f'{key} identity failed')
    if reference.get('prefix_rewards') != replayed.get('prefix_rewards'):
        raise RuntimeError('prefix reward identity failed')
    if reference.get('terminated') or reference.get('truncated'):
        raise RuntimeError('reference prefix ended early')
    if replayed.get('terminated') or replayed.get('truncated'):
        raise RuntimeError('replay prefix ended early')
    if int(reference['elapsed_steps']) != int(replayed['elapsed_steps']):
        raise RuntimeError('time-limit elapsed_steps identity failed')
    if int(replayed['elapsed_steps']) != int(replayed['later_t']):
        raise RuntimeError('elapsed_steps does not equal prefix length')
    return True


def assert_parents_frozen():
    if sha(h14.CONFIG) != h14.LOCKED_CONFIG or sha(h14.PROTOCOL) != h14.LOCKED_PROTOCOL:
        raise ValueError('H14 lock drifted')
    if sha(h15.CONFIG) != h15.LOCKED_CONFIG or sha(h15.PROTOCOL) != h15.LOCKED_PROTOCOL:
        raise ValueError('H15 lock drifted')
    if sha('artifacts/h14_candidate_reuse.json') != h15.FROZEN_H14_RAW:
        raise ValueError('closed H14 artifact drifted')
    if sha('artifacts/h15_candidate_reuse_confirm.json') != feas.H15_RAW_SHA:
        raise ValueError('closed H15 artifact drifted')
    if h14.holdout_from_rule() != [CLOSED_H14]:
        raise ValueError('H14 holdout drifted')
    if h15.holdout_from_rule() != [CLOSED_H15]:
        raise ValueError('H15 holdout drifted')


def load_config():
    cfg = yaml.safe_load(CONFIG.read_text())
    h10_cfg = yaml.safe_load(h10.CONFIG.read_text())
    locked = dict(starting_sha='929c93c2813db9f9d9e74639f7682439364aecf1',
        n_model_seeds=10, source_family='mountaincar_continuous',
        target_family='mountaincar_continuous', holdout_rule=HOLD_RULE,
        holdout_counter=0, holdout_index=HOLD_INDEX, target_budget=PRIMARY_BUDGET,
        n_source_physics=3, source_train=512, target_train=128, target_val=32,
        pretrain_epochs=15, train_epochs=20, train_lr=0.001, term_weight=0.25,
        batch_size=128, hidden=[64, 64], horizon=HORIZON, n_candidates=N_CAND,
        n_actions=N_ACTIONS, n_states=N_STATES, episode_steps=16,
        later_times=[8, 12], later_times_motivated_by_prior_results=True,
        restore_method=RESTORE_METHOD, prefix_policy='seeded_independent_integers',
        direct_state_mutation=False, share_step0_scores=False,
        closed_loop_horizon=HORIZON, include_shared_open_loop=False,
        h10_negative_seeds_used=False, full_episode_primary=False,
        closed_loop_is_primary=False, same_state_is_primary=True,
        practical_margin=0.0, time_cap_s=300, env_cap=84000, model_cap=81920,
        reset_base=78000000, state_reset_base=78100000, prefix_base=78200000,
        library_base=78300000, collect_source_base=78400000,
        collect_target_base=78500000, redraw_base=78600000,
        model_init_base=78700000, redraw_stride='10000s_plus_100k_plus_t',
        cross_family_weights=False, new_architecture_family=False,
        retune_from_closed_splits=False, claims_learning_to_learn=False,
        is_agi=False)
    for key, value in locked.items():
        if type(cfg.get(key)) is not type(value) or cfg[key] != value:
            raise ValueError(f'locked H16 design/budget changed: {key}')
    for key in FROZEN_H10_FIELDS:
        if cfg[key] != h10_cfg[key]:
            raise ValueError(f'H16 training recipe drifted from H10: {key}')
    if cfg['source_physics'] != yaml.safe_load(h14.CONFIG.read_text())['source_physics']:
        raise ValueError('H16 source physics drifted from H14')
    if holdout_from_rule() != [tuple(cfg['target_physics'][0])]:
        raise ValueError('H16 rule does not reproduce the locked target physics')
    if tuple(cfg['target_physics'][0]) != LOCKED_TARGET:
        raise ValueError('H16 target physics drifted')
    if tuple(cfg['target_physics'][0]) in occupied_physics():
        raise ValueError('H16 target collides with occupied physics')
    trace = holdout_trace()
    if int(trace['index']) != HOLD_INDEX or int(trace['counter']) != HOLD_COUNTER:
        raise ValueError('H16 holdout index or counter drifted')
    for file, digest in cfg['parents'].items():
        if sha(file) != digest:
            raise ValueError(f'closed parent changed: {file}')
    if sha(CONFIG) != LOCKED_CONFIG:
        raise ValueError('locked configuration hash drifted')
    if sha(PROTOCOL) != LOCKED_PROTOCOL:
        raise ValueError('locked protocol hash drifted')
    assert_parents_frozen()
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
    streams, used = seed_streams(cfg)
    if used & blocked:
        raise ValueError('H16 seeds collide with a closed experiment')
    if min(used) < cfg['reset_base']:
        raise ValueError('seed block drifted below the locked base')
    for base_id in OTHER_BRANCH_BLOCKS:
        if any(base_id <= u < base_id + 300000 for u in used):
            raise ValueError('H16 seeds collide with another live branch block')
    h14_used = h14.seed_streams(yaml.safe_load(h14.CONFIG.read_text()))[1]
    h15_used = h15.seed_streams(yaml.safe_load(h15.CONFIG.read_text()))[1]
    if used & h14_used or used & h15_used:
        raise ValueError('H16 seeds overlap a closed H14/H15 block')
    names = list(streams)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            if streams[left] & streams[right]:
                raise ValueError(f'H16 streams {left} and {right} overlap')


def load_allocation():
    record = json.loads(ALLOCATION.read_text())
    for key, value in dict(time_cap_s=300, env_cap=84000, model_cap=81920).items():
        if type(record.get(key)) is not type(value) or record[key] != value:
            raise ValueError('H16 allocation drift')
    if record.get('config_sha256') != LOCKED_CONFIG or record.get('config_sha256') != sha(CONFIG):
        raise ValueError('allocation config hash does not match yaml')
    if record.get('protocol_sha256') != LOCKED_PROTOCOL or record.get('protocol_sha256') != sha(PROTOCOL):
        raise ValueError('allocation protocol hash does not match protocol')
    authorized = record.get('authorized')
    runs = int(record.get('runs', -1))
    if authorized is False:
        if runs != 0:
            raise ValueError('unauthorized H16 allocation must have runs=0')
    elif authorized is True:
        if runs != 1:
            raise ValueError('authorized H16 allocation must be exactly one run')
        if not record.get('one_run_usage_record'):
            raise ValueError('authorized H16 allocation missing usage record')
    else:
        raise ValueError('H16 allocation authorized flag invalid')
    return record


def require_allocation(cfg):
    record = load_allocation()
    if record.get('authorized') is not True or int(record.get('runs', 0)) != 1:
        raise PermissionError('fresh human approval required before H16 collection')
    if record.get('consumed') is True or record.get('closed') is True:
        raise PermissionError('H16 one-run allowance already consumed')
    usage = json.loads(Path(record['one_run_usage_record']).read_text())
    if usage.get('consumed') is True:
        raise PermissionError('H16 one-run allowance already consumed')
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
        holdout_rule=HOLD_RULE, holdout_counter=HOLD_COUNTER, holdout_index=HOLD_INDEX,
        source_physics=[list(k) for k in source_physics_keys()],
        later_times=list(LATER_TIMES),
        restore_method=cfg['restore_method'], restoration=RESTORATION,
        proposed_budget=assert_budget(cfg),
        redraw_unique=len(seed_streams(cfg)[0]['redraw']),
        arms=list(ARMS), libraries=list(LIBS),
        labels=('h16_l0_helps_multitask_relative_same_state',
                'h16_redraw_helps_multitask_relative_same_state',
                'h16_same_state_library_effect_not_established', 'incomplete'),
        claims_learning_to_learn=False, is_agi=False, full_episode_primary=False,
        closed_loop_is_primary=False, same_state_is_primary=True,
        session_ledger=dict(used_s=303.777, remaining_s=3296.223, unchanged=True),
        note='Same-state library lock. No collection. H14/H15 stay closed.')


def execute():
    cfg = load_config()
    require_allocation(cfg)
    raise PermissionError('H16 collection is not implemented on this lock branch')
