"""H14 candidate-reuse design helpers. Source-only. No collection.

Defines shared-library versus redraw recede seeds, the predeclared
difference-in-differences primary, and exact resource formulas.
Does not train, step a simulator, or authorize an experiment.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
from nexus.cl.metrics import seed_level_ci
from nexus.world.prediction_control_gap import candidate_sequences

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
HOLD_RULE = 'mcc_candidate_reuse_v1_draft'
OUTPUT = Path('artifacts/h14_candidate_reuse_feasibility.json')


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


def assert_shared_first_library(library_base, seed, state_index):
    fixed0 = recede_candidates('fixed', library_base, 0, seed, state_index, 0)
    redraw0 = recede_candidates('redraw', library_base, 0, seed, state_index, 0)
    if not np.array_equal(fixed0, redraw0):
        raise ValueError('first-step libraries differ across modes')
    return fixed0
