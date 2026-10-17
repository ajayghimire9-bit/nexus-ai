"""H16 same-state library feasibility. Source-only. No collection.

Designs a common-later-state L0-versus-redraw ranking contrast that
removes controller occupancy from the immediate library comparison.
Does not train, construct MountainCar, select holdout physics, lock a
protocol, or authorize an experiment.
"""
from __future__ import annotations
import inspect
import json
from pathlib import Path
import numpy as np
from nexus.cl.metrics import seed_level_ci
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world import h14_candidate_reuse as h14
from nexus.world import h15_candidate_reuse_confirm as h15

OUTPUT = Path('artifacts/h16_same_state_library_feasibility.json')
H14_RAW = Path('artifacts/h14_candidate_reuse.json')
H15_RAW = Path('artifacts/h15_candidate_reuse_confirm.json')
H14_RAW_SHA = h15.FROZEN_H14_RAW
H15_RAW_SHA = '440671d592c888e16f5c43d90de701c83bcae6887b9e0b83d1eb71b4312c7a15'
N_SEEDS = 10
N_STATES = 4
LATER_TIMES = (8, 12)
N_TIMES = len(LATER_TIMES)
N_LIBS = 2
LIBS = ('l0', 'redraw')
ARMS = h14.ARMS
N_ARMS = 2
HORIZON = 16
N_CAND = 16
N_ACTIONS = 3
N_SOURCE = 3
SOURCE_TRAIN = 512
TARGET_TRAIN = 128
TARGET_VAL = 32
RESET_ATOL = h14.RESET_ATOL
STANDING_ENV_CEILING = 100_000
PROPOSED_TIME_CAP_S = 300
PROPOSED_SEED_BLOCK = 78_000_000
RESTORE_METHOD = 'reset_plus_action_prefix'
PREFIX_POLICY = 'seeded_independent_integers'


def assert_parent_hashes():
    if sha(H14_RAW) != H14_RAW_SHA:
        raise ValueError('H14 raw artifact drifted')
    if sha(H15_RAW) != H15_RAW_SHA:
        raise ValueError('H15 raw artifact drifted')
    if sha(h14.CONFIG) != h14.LOCKED_CONFIG or sha(h14.PROTOCOL) != h14.LOCKED_PROTOCOL:
        raise ValueError('H14 lock drifted')
    if sha(h15.CONFIG) != h15.LOCKED_CONFIG or sha(h15.PROTOCOL) != h15.LOCKED_PROTOCOL:
        raise ValueError('H15 lock drifted')


def closed_mcc_physics():
    """Known occupied MCC keys. Does not select a new holdout."""
    keys = set(h15.occupied_physics())
    keys.add(tuple(h15.LOCKED_TARGET))
    return frozenset(keys)


def prefix_actions(prefix_base, seed, state_index, length):
    """Model-independent prefix. Same for both arms and both libraries."""
    rng = np.random.default_rng(int(prefix_base) + 10 * int(seed) + int(state_index))
    return rng.integers(0, N_ACTIONS, size=int(length), dtype=np.int64)


def l0_seed(library_base, seed, state_index):
    return int(library_base) + 10 * int(seed) + int(state_index)


def redraw_seed(redraw_base, seed, state_index, later_t):
    if int(later_t) not in LATER_TIMES:
        raise ValueError('redraw time is not a proposed later-state time')
    return int(redraw_base) + 1000 * int(seed) + 10 * int(state_index) + int(later_t)


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
    if values.shape != (N_CAND,) or not np.isfinite(values).all():
        raise ValueError('selected return needs 16 finite candidate returns')
    scores = np.asarray(scores, dtype=np.float64).reshape(-1)
    if scores.shape != (N_CAND,) or not np.isfinite(scores).all():
        raise ValueError('nonfinite or misaligned scores')
    return float(values[selected_index(scores)])


def within_library_regret(realized, scores):
    return oracle_return(realized) - selected_return(realized, scores)


def first_action_regret(sequences, realized, scores):
    """Loss relative to the best sequence that shares the selected first action."""
    seq = np.asarray(sequences, dtype=np.int64)
    values = np.asarray(realized, dtype=np.float64).reshape(-1)
    idx = selected_index(scores)
    first = int(seq[idx, 0])
    mask = seq[:, 0] == first
    return oracle_return(values) - float(values[mask].max())


def same_state_did(s_mt_l0, s_sc_l0, s_mt_redraw, s_sc_redraw):
    """D = (S_mt(L0) - S_sc(L0)) - (S_mt(Lredraw) - S_sc(Lredraw))."""
    return float((s_mt_l0 - s_sc_l0) - (s_mt_redraw - s_sc_redraw))


def oracle_cancels_in_arm_gap(realized, scores_mt, scores_sc):
    """S_mt - S_sc == regret_sc - regret_mt. Oracle cancels."""
    gap = selected_return(realized, scores_mt) - selected_return(realized, scores_sc)
    via_regret = (within_library_regret(realized, scores_sc)
                  - within_library_regret(realized, scores_mt))
    if abs(gap - via_regret) > 1e-12:
        raise ValueError('oracle cancellation failed')
    return float(gap)


def score_library(model, obs, sequences):
    """Imagined scores. Realized returns are not an argument."""
    if 'realized' in inspect.signature(score_library).parameters:
        raise RuntimeError('planner scoring must not accept realized returns')
    sequences = np.asarray(sequences, dtype=np.int64)
    if sequences.shape != (N_CAND, HORIZON):
        raise ValueError('candidate shape drifted')
    scores = np.asarray(model.score(obs, sequences), dtype=np.float64).reshape(-1)
    if scores.shape != (N_CAND,) or not np.isfinite(scores).all():
        raise ValueError('nonfinite or misaligned scores')
    return scores


def budget():
    source = N_SOURCE * SOURCE_TRAIN * N_SEEDS
    target = (TARGET_TRAIN + TARGET_VAL) * N_SEEDS
    n_groups = N_SEEDS * N_STATES
    n_later = n_groups * N_TIMES
    reference_prefix = n_groups * max(LATER_TIMES)
    prefix_replay = n_groups * N_LIBS * N_CAND * int(sum(LATER_TIMES))
    realizations = n_later * N_LIBS * N_CAND * HORIZON
    env_total = source + target + reference_prefix + prefix_replay + realizations
    imagined = n_later * N_LIBS * N_ARMS * N_CAND * HORIZON
    return dict(
        source_collection=source,
        target_pool=target,
        reference_prefix=reference_prefix,
        prefix_replay=prefix_replay,
        shared_candidate_realizations=realizations,
        env_total=env_total,
        imagined_total=imagined,
        standing_env_ceiling=STANDING_ENV_CEILING,
        margin_to_ceiling=STANDING_ENV_CEILING - env_total,
        time_cap_s=PROPOSED_TIME_CAP_S,
        later_times=list(LATER_TIMES),
        restore_method=RESTORE_METHOD,
        prefix_policy=PREFIX_POLICY,
        n_later_states=n_later,
        notes=(
            'Counts every intended simulator action: training collection, '
            'one reference prefix to t=12 per reset group, reset-plus-prefix '
            'replay before every candidate, and 16-step shared realizations. '
            'Resets are not steps. Training forwards are not imagined. '
            'make_planner uncertainty_penalty=0 adds no ensemble inferences. '
            'Direct .state mutation is not counted because it is not registered.'
        ),
    )


def assert_budget_fits_ceiling(counts=None):
    counts = counts or budget()
    if int(counts['env_total']) >= STANDING_ENV_CEILING:
        raise ValueError('proposed env total does not fit the standing ceiling')
    if int(counts['margin_to_ceiling']) < 10_000:
        raise ValueError('safety margin below 10,000 real interactions')
    if int(counts['env_total']) != 84_000:
        raise ValueError('nominal 84,000 env accounting drifted')
    if int(counts['imagined_total']) != 81_920:
        raise ValueError('nominal 81,920 imagined accounting drifted')
    return counts


def redraw_unique():
    """With only t=8 and t=12, the H14-style stride does not alias."""
    seen = {}
    for seed in range(N_SEEDS):
        for state in range(N_STATES):
            for later_t in LATER_TIMES:
                sid = redraw_seed(0, seed, state, later_t)
                seen.setdefault(sid, []).append((seed, state, later_t))
    collisions = {k: v for k, v in seen.items() if len(v) > 1}
    return dict(intended=N_SEEDS * N_STATES * N_TIMES, unique=len(seen),
                colliding_groups=len(collisions))


class HardBudget:
    def __init__(self, env_cap, imagined_cap):
        self.env_cap = int(env_cap)
        self.imagined_cap = int(imagined_cap)
        self.env_steps = 0
        self.imagined = 0

    def reserve_env(self, n=1):
        n = int(n)
        if n < 1:
            raise ValueError('env reservation must be positive')
        if self.env_steps + n > self.env_cap:
            raise RuntimeError('env-step cap would be exceeded')
        self.env_steps += n
        return self.env_steps

    def reserve_imagined(self, n):
        n = int(n)
        if n < 1:
            raise ValueError('imagined batch size must be positive')
        if self.imagined + n > self.imagined_cap:
            raise RuntimeError('imagined cap would be exceeded')
        self.imagined += n
        return self.imagined


class MockLaterEnv:
    """Deterministic toy dynamics. Not MountainCar. No gymnasium."""

    def __init__(self, terminate_after=None):
        self.terminate_after = terminate_after
        self.state = None
        self.obs = None
        self.elapsed = 0

    def reset(self, seed):
        rng = np.random.default_rng(int(seed))
        self.state = rng.normal(size=2).astype(np.float64)
        self.obs = self.state.astype(np.float32)
        self.elapsed = 0
        return self.obs.copy(), {}

    def step(self, action):
        if self.state is None:
            raise RuntimeError('mock env stepped before reset')
        force = float(int(action) - 1)
        self.state = self.state + 0.05 * force + np.array([0.01, -0.01])
        self.obs = self.state.astype(np.float32)
        self.elapsed += 1
        reward = float(-np.linalg.norm(self.state))
        terminated = self.terminate_after is not None and self.elapsed >= int(self.terminate_after)
        return self.obs.copy(), reward, bool(terminated), False, {}


def reconstruct_later_state(env, reset_seed, prefix, meter=None):
    """Reset, apply the stored prefix, never assign .state."""
    obs, _info = env.reset(seed=int(reset_seed))
    recorded = [np.asarray(obs, dtype=np.float32).copy()]
    for action in np.asarray(prefix, dtype=np.int64).reshape(-1):
        if meter is not None:
            meter.reserve_env(1)
        nxt, _reward, terminated, truncated, _info = env.step(int(action))
        if terminated or truncated:
            raise RuntimeError('prefix ended before the later state')
        obs = np.asarray(nxt, dtype=np.float32).reshape(-1)
        recorded.append(obs.copy())
    return dict(obs=obs.copy(), state=None if env.state is None else np.asarray(env.state).copy(),
                path=recorded, elapsed=int(env.elapsed))


def assert_same_later_state(first, second, atol=RESET_ATOL):
    if first['obs'].shape != second['obs'].shape or not np.allclose(
            first['obs'], second['obs'], atol=atol, rtol=0.0):
        raise RuntimeError('later observation identity failed')
    if first['state'] is not None and second['state'] is not None:
        if first['state'].shape != second['state'].shape or not np.allclose(
                first['state'], second['state'], atol=atol, rtol=0.0):
            raise RuntimeError('later raw-state identity failed')
    return first


def realize_candidates(env, reset_seed, prefix, sequences, meter=None):
    """Shared ground-truth returns. Models never see these values."""
    sequences = np.asarray(sequences, dtype=np.int64)
    if sequences.shape != (N_CAND, HORIZON):
        raise ValueError('candidate shape drifted')
    start = reconstruct_later_state(env, reset_seed, prefix, meter=meter)
    values = np.zeros(N_CAND, dtype=np.float64)
    for j, actions in enumerate(sequences):
        restored = reconstruct_later_state(env, reset_seed, prefix, meter=meter)
        assert_same_later_state(start, restored)
        rewards = []
        for action in actions:
            if meter is not None:
                meter.reserve_env(1)
            _nxt, reward, terminated, truncated, _info = env.step(int(action))
            if terminated or truncated:
                raise RuntimeError('candidate ended before the horizon')
            if not np.isfinite(reward):
                raise ValueError('nonfinite reward')
            rewards.append(float(reward))
        if len(rewards) != HORIZON:
            raise RuntimeError('incomplete candidate realization')
        values[j] = float(np.sum(rewards))
    return start, values


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


def synthetic_complete_grid():
    """Deterministic mock cells. Not experimental outcomes."""
    cells = []
    for seed in range(N_SEEDS):
        later = []
        for state_index in range(N_STATES):
            for later_t in LATER_TIMES:
                later.append(dict(
                    state_index=state_index, later_t=later_t,
                    s_mt_l0=-1.0 + 0.02 * seed, s_sc_l0=-1.2,
                    s_mt_redraw=-1.3, s_sc_redraw=-1.25,
                ))
        cells.append(dict(seed=seed, later_states=later))
    return cells


def restoration_assessment():
    return dict(
        proposed_method=RESTORE_METHOD,
        direct_state_mutation='rejected_unless_separately_validated',
        source_supports_determinism=(
            'H14/H15 already require reset(seed) observation and raw-state '
            'identity at t=0. MCC dense-height wrapper forces goal '
            'terminated=False. TimeLimit is 200; prefix 12 plus horizon 16 '
            'cannot truncate. Inner MCC physics is a deterministic map of '
            '(position, velocity, action).'
        ),
        empirical_status='not_verified_this_task_no_simulator',
        blocking_for_execution=(
            'A future runner must fail closed if reset-plus-prefix misses '
            'the recorded later observation or raw state. This feasibility '
            'task cannot guarantee gymnasium float identity without a real env.'
        ),
        time_limit_note=(
            'Mutating .state without reset would desynchronize TimeLimit '
            'elapsed_steps. For 16-step candidates that mismatch cannot '
            'truncate, but it remains unregistered and is rejected.'
        ),
        lock_readiness='conditional',
    )


def identifiability():
    return dict(
        library_opportunity='O(x,L); secondary only',
        model_ranking_error='Regret_a(x,L) and D_same; proposed primary',
        closed_loop_occupancy='controlled by shared model-independent prefixes; not measured as a controller occupancy',
        h14_h15_causal_attribution='not identified',
        positive_d_means=(
            'At sampled common later states, multitask-minus-scratch selected '
            'return is larger under L0 than under redraw.'
        ),
        positive_d_does_not_mean=(
            'H14/H15 trajectory cause, compounding error, general control, '
            'cross-family transfer, learning-to-learn, or AGI.'
        ),
    )


def feasibility_report():
    assert_parent_hashes()
    counts = assert_budget_fits_ceiling()
    return dict(
        complete=True,
        authorized=False,
        locked=False,
        trained=False,
        new_environment_steps=0,
        new_imagined_transitions=0,
        holdout_physics_selected=False,
        parent_audit='c157eb65910b5bb45bd20b40148fb8020e7a5d69',
        parent_h15_results='644a9f05781d543f03d41fc6e553b0da25be0ad4',
        question=(
            'At the same later simulator state, does reused L0 change the '
            'relative selected-return quality of multitask versus scratch '
            'compared with a freshly drawn library?'
        ),
        question_class='mechanistic',
        later_times_motivated_by_prior_results=True,
        later_times=list(LATER_TIMES),
        restore_method=RESTORE_METHOD,
        prefix_policy=PREFIX_POLICY,
        proposed_primary='same_state_fixed_minus_redraw_relative_multitask_advantage',
        labels=(
            'h16_l0_helps_multitask_relative_same_state',
            'h16_redraw_helps_multitask_relative_same_state',
            'h16_same_state_library_effect_not_established',
            'incomplete',
        ),
        budget=counts,
        redraw_aliasing=redraw_unique(),
        closed_mcc_physics=[list(k) for k in sorted(closed_mcc_physics())],
        restoration=restoration_assessment(),
        identifiability=identifiability(),
        protocol_ready_to_lock=False,
        claims_learning_to_learn=False,
        is_agi=False,
        session_ledger=dict(used_s=303.777, remaining_s=3296.223, unchanged=True),
        note=(
            'Feasibility only. Nested reset states and later times are not '
            'extra model-training replications. No H16 execution.'
        ),
    )


def save_feasibility():
    report = feasibility_report()
    OUTPUT.write_text(json.dumps(report, indent=2, default=float))
    return report
