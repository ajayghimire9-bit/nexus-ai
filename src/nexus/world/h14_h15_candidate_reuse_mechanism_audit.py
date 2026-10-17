"""Source-only H14/H15 candidate-reuse mechanism audit. No collection.

Reconstructs registered primaries from saved cells and describes
action, occupancy, score, reward, and alias patterns. Does not train,
step a simulator, or authorize a new experiment.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
import numpy as np
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world import h14_candidate_reuse as h14
from nexus.world import h15_candidate_reuse_confirm as h15

H14_RAW = Path('artifacts/h14_candidate_reuse.json')
H15_RAW = Path('artifacts/h15_candidate_reuse_confirm.json')
OUTPUT = Path('artifacts/h14_h15_candidate_reuse_mechanism_audit.json')
H14_RAW_SHA = '7e4a74ba0a8f21f735b41cc1fbceb4d5c005f68718159c0a2077caa27934959e'
H15_RAW_SHA = '440671d592c888e16f5c43d90de701c83bcae6887b9e0b83d1eb71b4312c7a15'
ARMS = h14.ARMS
MODES = h14.MODES
HORIZON = h14.HORIZON
N_SEEDS = h14.N_SEEDS
N_STATES = h14.N_STATES
N_CAND = h14.N_CAND

EVIDENCE = {
    'current_observation': 'available',
    'next_observation': 'available',
    'executed_action': 'available',
    'per_step_reward': 'available',
    'candidate_seed': 'available',
    'candidate_matrix': 'reconstructible_from_seed',
    'predicted_candidate_scores': 'available',
    'selected_index': 'available',
    'library_fingerprint': 'available',
    'chosen_one_step_residual': 'available',
    'full_predicted_next_state': 'missing',
    'unchosen_later_realized_returns': 'missing',
    'reset_l0_open_loop_returns': 'available',
    'model_checkpoints': 'missing',
}


def load_artifact(path):
    return json.loads(Path(path).read_text())


def assert_hashes():
    if sha(H14_RAW) != H14_RAW_SHA:
        raise ValueError('H14 raw artifact drifted')
    if sha(H15_RAW) != H15_RAW_SHA:
        raise ValueError('H15 raw artifact drifted')
    if sha(h14.CONFIG) != h14.LOCKED_CONFIG or sha(h14.PROTOCOL) != h14.LOCKED_PROTOCOL:
        raise ValueError('H14 lock drifted')
    if sha(h15.CONFIG) != h15.LOCKED_CONFIG or sha(h15.PROTOCOL) != h15.LOCKED_PROTOCOL:
        raise ValueError('H15 lock drifted')


def reconstruct_primary(payload, summarize):
    rebuilt = summarize(payload['cells'])
    saved = payload['groups']['primary']['interval']
    if rebuilt['label'] != payload['label']:
        raise ValueError('saved label does not rebuild')
    if rebuilt['groups']['primary']['per_seed'] != payload['groups']['primary']['per_seed']:
        raise ValueError('saved per-seed D drifted')
    for key in ('mean', 'lo', 'hi', 'n', 'df'):
        if abs(float(rebuilt['groups']['primary']['interval'][key]) - float(saved[key])) > 1e-12:
            raise ValueError(f'primary interval drifted: {key}')
    return rebuilt


def traces(state, arm, mode):
    return state['controllers'][arm][mode]['traces']


def reward_sum(state, arm, mode):
    return float(np.sum([float(row['realized_reward']) for row in traces(state, arm, mode)]))


def validate_cells(payload):
    cells = payload['cells']
    if len(cells) != N_SEEDS or {int(c['seed']) for c in cells} != set(range(N_SEEDS)):
        raise ValueError('incomplete or duplicated seed grid')
    for cell in cells:
        states = cell['states']
        if {int(s['state_index']) for s in states} != set(range(N_STATES)):
            raise ValueError('incomplete or duplicated state grid')
        for state in states:
            for arm in ARMS:
                for mode in MODES:
                    rows = traces(state, arm, mode)
                    if len(rows) != HORIZON:
                        raise ValueError('incomplete controller trajectory')
                    if any(not np.isfinite(float(r['realized_reward'])) for r in rows):
                        raise ValueError('nonfinite reward')
                    if any(not np.isfinite(np.asarray(r['predicted_scores'], dtype=np.float64)).all()
                           for r in rows):
                        raise ValueError('nonfinite predicted scores')
                    rebuilt = reward_sum(state, arm, mode)
                    saved = float(state['returns'][arm][mode])
                    if abs(rebuilt - saved) > 1e-9:
                        raise ValueError('step rewards do not reconstruct the saved return')


def first_divergence(fixed_rows, redraw_rows):
    for step in range(HORIZON):
        if int(fixed_rows[step]['executed_action']) != int(redraw_rows[step]['executed_action']):
            return step
    return None


def spearman(a, b):
    xa = np.asarray(a, dtype=np.float64).reshape(-1)
    xb = np.asarray(b, dtype=np.float64).reshape(-1)
    if xa.size != xb.size or xa.size < 2:
        raise ValueError('spearman needs aligned finite vectors')
    ra = np.argsort(np.argsort(xa))
    rb = np.argsort(np.argsort(xb))
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    den = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    return 0.0 if den == 0 else float((ra * rb).sum() / den)


def alias_map(redraw_base):
    intended = []
    for seed in range(N_SEEDS):
        for state in range(N_STATES):
            for step in range(1, HORIZON):
                intended.append((seed, state, step,
                                 h14.redraw_step_seed(redraw_base, seed, state, step)))
    by_seed = {}
    for seed, state, step, sid in intended:
        by_seed.setdefault(int(sid), []).append((seed, state, step))
    collisions = {k: v for k, v in by_seed.items() if len(v) > 1}
    within = []
    for seed in range(N_SEEDS):
        for state in range(N_STATES):
            local = [h14.redraw_step_seed(redraw_base, seed, state, step)
                     for step in range(1, HORIZON)]
            within.append(len(set(local)) == HORIZON - 1)
    return dict(intended=len(intended), unique=len(by_seed),
                aliased=len(intended) - len(by_seed),
                colliding_groups=len(collisions),
                within_state_unique=all(within))


def describe_experiment(payload, *, library_base, redraw_base, summarize):
    validate_cells(payload)
    rebuilt = reconstruct_primary(payload, summarize)
    diffs = rebuilt['groups']['primary']['per_seed']
    t0_match = {arm: [] for arm in ARMS}
    first_div = {arm: [] for arm in ARMS}
    disagree = {arm: np.zeros(HORIZON) for arm in ARMS}
    n_pairs = 0
    obs_l2 = {arm: np.zeros(HORIZON) for arm in ARMS}
    step_reward = {(arm, mode): np.zeros(HORIZON) for arm in ARMS for mode in MODES}
    residual_l2 = {(arm, mode): [] for arm in ARMS for mode in MODES}
    score_range = {(arm, mode): [] for arm in ARMS for mode in MODES}
    top_margin = {(arm, mode): [] for arm in ARMS for mode in MODES}
    switch = {(arm, mode): [] for arm in ARMS for mode in MODES}
    fixed_rank_stability = {arm: [] for arm in ARMS}
    action_hist = {(arm, mode): Counter() for arm in ARMS for mode in MODES}
    seed_obs_l2 = []
    seed_first_div = {arm: [] for arm in ARMS}
    for cell in payload['cells']:
        seed_l2 = []
        seed_div = {arm: [] for arm in ARMS}
        for state in cell['states']:
            n_pairs += 1
            for arm in ARMS:
                fixed = traces(state, arm, 'fixed')
                redraw = traces(state, arm, 'redraw')
                t0_match[arm].append(int(fixed[0]['executed_action']) == int(redraw[0]['executed_action']))
                if fixed[0]['library_fingerprint'] != state['library_fingerprint']:
                    raise ValueError('step-0 fingerprint is not shared L0')
                if redraw[0]['library_fingerprint'] != state['library_fingerprint']:
                    raise ValueError('redraw step-0 fingerprint is not shared L0')
                if fixed[0]['candidate_seed'] != h14.shared_library_seed(library_base, cell['seed'], state['state_index']):
                    raise ValueError('step-0 candidate seed drifted')
                div = first_divergence(fixed, redraw)
                first_div[arm].append(div)
                seed_div[arm].append(div)
                for step in range(HORIZON):
                    if int(fixed[step]['executed_action']) != int(redraw[step]['executed_action']):
                        disagree[arm][step] += 1
                    a = np.asarray(fixed[step]['observation'], dtype=np.float64)
                    b = np.asarray(redraw[step]['observation'], dtype=np.float64)
                    obs_l2[arm][step] += float(np.linalg.norm(a - b))
                    seed_l2.append(float(np.linalg.norm(a - b)))
                seq = candidate_sequences(int(fixed[0]['candidate_seed']), N_CAND, HORIZON, n_actions=3)
                if h14.library_fingerprint(seq) != fixed[0]['library_fingerprint']:
                    raise ValueError('reconstructed L0 fingerprint drifted')
            for arm in ARMS:
                for mode in MODES:
                    rows = traces(state, arm, mode)
                    for step, row in enumerate(rows):
                        step_reward[(arm, mode)][step] += float(row['realized_reward'])
                        scores = np.asarray(row['predicted_scores'], dtype=np.float64)
                        score_range[(arm, mode)].append(float(scores.max() - scores.min()))
                        ordered = np.sort(scores)
                        top_margin[(arm, mode)].append(float(ordered[-1] - ordered[-2]))
                        residual = np.asarray(row['executed_transition_one_step_residual'], dtype=np.float64)
                        residual_l2[(arm, mode)].append(float(np.linalg.norm(residual)))
                        action_hist[(arm, mode)][int(row['executed_action'])] += 1
                    switched = sum(int(rows[t]['selected_index']) != int(rows[t - 1]['selected_index'])
                                   for t in range(1, HORIZON))
                    switch[(arm, mode)].append(switched / (HORIZON - 1))
                    if mode == 'fixed':
                        for t in range(1, HORIZON):
                            if rows[t]['library_fingerprint'] != rows[0]['library_fingerprint']:
                                raise ValueError('fixed library fingerprint drifted')
                            fixed_rank_stability[arm].append(
                                spearman(rows[t - 1]['predicted_scores'], rows[t]['predicted_scores']))
        seed_obs_l2.append(float(np.mean(seed_l2)))
        for arm in ARMS:
            present = [v for v in seed_div[arm] if v is not None]
            seed_first_div[arm].append(float(np.mean(present)) if present else None)
    n = float(n_pairs)
    stepwise_did = []
    for step in range(HORIZON):
        mt = step_reward[('multitask', 'fixed')][step] / n - step_reward[('scratch', 'fixed')][step] / n
        sc = step_reward[('multitask', 'redraw')][step] / n - step_reward[('scratch', 'redraw')][step] / n
        stepwise_did.append(float(mt - sc))
    return dict(
        label=rebuilt['label'],
        interval=rebuilt['groups']['primary']['interval'],
        per_seed=diffs,
        n_positive=int(sum(d > 0 for d in diffs)),
        t0_action_match={arm: float(np.mean(t0_match[arm])) for arm in ARMS},
        first_divergence_mean={arm: float(np.mean([v for v in first_div[arm] if v is not None]))
                               for arm in ARMS},
        first_divergence_never={arm: int(sum(v is None for v in first_div[arm])) for arm in ARMS},
        action_disagreement_by_step={arm: (disagree[arm] / n).tolist() for arm in ARMS},
        obs_l2_by_step={arm: (obs_l2[arm] / n).tolist() for arm in ARMS},
        seed_mean_obs_l2=seed_obs_l2,
        seed_mean_first_div=seed_first_div,
        stepwise_did=stepwise_did,
        stepwise_did_early=float(np.sum(stepwise_did[:4])),
        stepwise_did_late=float(np.sum(stepwise_did[4:])),
        mean_score_range={f'{arm}_{mode}': float(np.mean(score_range[(arm, mode)]))
                          for arm in ARMS for mode in MODES},
        mean_top_margin={f'{arm}_{mode}': float(np.mean(top_margin[(arm, mode)]))
                         for arm in ARMS for mode in MODES},
        mean_switch_rate={f'{arm}_{mode}': float(np.mean(switch[(arm, mode)]))
                          for arm in ARMS for mode in MODES},
        mean_fixed_rank_stability={arm: float(np.mean(fixed_rank_stability[arm])) for arm in ARMS},
        mean_residual_l2={f'{arm}_{mode}': float(np.mean(residual_l2[(arm, mode)]))
                          for arm in ARMS for mode in MODES},
        action_hist={f'{arm}_{mode}': dict(sorted(action_hist[(arm, mode)].items()))
                     for arm in ARMS for mode in MODES},
        aliasing=alias_map(redraw_base),
        counts=dict(env_steps=payload['counts']['env_steps'],
                    imagined=payload['counts']['model_states']),
    )


def audit():
    assert_hashes()
    h14_payload = load_artifact(H14_RAW)
    h15_payload = load_artifact(H15_RAW)
    h14_cfg = h14.load_config()
    h15_cfg = h15.load_config()
    report = dict(
        complete=True,
        authorized=False,
        new_environment_steps=0,
        new_imagined_transitions=0,
        trained=False,
        evidence=EVIDENCE,
        h14=describe_experiment(h14_payload, library_base=h14_cfg['library_base'],
                                redraw_base=h14_cfg['redraw_base'], summarize=h14.summarize),
        h15=describe_experiment(h15_payload, library_base=h15_cfg['library_base'],
                                redraw_base=h15_cfg['redraw_base'], summarize=h15.summarize),
        claims_learning_to_learn=False,
        is_agi=False,
        note='Descriptive source-only audit. Nested states/steps are not extra replications.',
    )
    if report['h14']['label'] != 'h14_fixed_library_helps_multitask_relative':
        raise ValueError('H14 label drifted')
    if report['h15']['label'] != 'h15_fixed_library_helps_multitask_relative':
        raise ValueError('H15 label drifted')
    return report


def save_audit():
    report = audit()
    OUTPUT.write_text(json.dumps(report, indent=2, default=float))
    return report
