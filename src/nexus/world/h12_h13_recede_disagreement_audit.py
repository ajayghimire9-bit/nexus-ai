"""Source-only H12/H13 ranking-versus-recede audit. No collection.

Recomputes committed seed-level ranking and recede statistics from saved
artifacts. Does not train, step a simulator, or alter closed H12/H13 files.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import numpy as np
from nexus.cl.metrics import seed_level_ci
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences
from nexus.world.terminal_value_execution import save
from nexus.world import mcc_planning_ranking as h12
from nexus.world import mcc_planning_ranking_confirm as h13

OUTPUT = Path('artifacts/h12_h13_recede_disagreement_audit.json')
REPORT = Path('docs/NEXUS_H12_H13_CONTROL_DISAGREEMENT_AUDIT.md')
ARMS = ('multitask', 'scratch')
N_SEEDS = 10
N_STATES = 4
N_CAND = 16
HORIZON = 16
FROZEN_H12_RAW = h13.FROZEN_H12_RAW
FROZEN_H12_REPORT = h13.FROZEN_H12_REPORT
FROZEN_H12_CODE = h13.FROZEN_H12_CODE
FROZEN_H12_CONFIG = h13.FROZEN_H12_CONFIG
FROZEN_H12_PROTOCOL = h13.FROZEN_H12_PROTOCOL
FROZEN_H13_RAW = 'e1083da8fecccffa140b2051744c9c3bd8c0398ffa8fd5a9ebc36c2a079afdc8'
FROZEN_H13_REPORT = '18d34d5624956690534256414f419ee28f41019435ac6b05456338420669e67f'
FROZEN_H13_CODE = 'fb98d762d0c7cbca76d10ebf6238efbc3ce233155a123be627bba1b1ba13532f'
MISSING_RECEDE = ('closed_loop_actions', 'closed_loop_rewards', 'closed_loop_observations',
                  'closed_loop_scores', 'later_state_rankings', 'predicted_next',
                  'model_weights', 'checkpoints')
SAVED_STATE = ('actual', 'obs0', 'ranked', 'state_index', 'state_seed', 'traces')


def assert_closed_hashes():
    if sha(h12.OUTPUT) != FROZEN_H12_RAW:
        raise ValueError('closed H12 artifact drifted')
    if sha('docs/NEXUS_MCC_PLANNING_RANKING_RESULTS.md') != FROZEN_H12_REPORT:
        raise ValueError('closed H12 report drifted')
    if sha(h12.CONFIG) != FROZEN_H12_CONFIG or sha(h12.PROTOCOL) != FROZEN_H12_PROTOCOL:
        raise ValueError('closed H12 config/protocol drifted')
    if sha('src/nexus/world/mcc_planning_ranking.py') != FROZEN_H12_CODE:
        raise ValueError('closed H12 implementation drifted')
    if sha(h13.OUTPUT) != FROZEN_H13_RAW:
        raise ValueError('closed H13 artifact drifted')
    if sha('docs/NEXUS_MCC_PLANNING_RANKING_CONFIRM_RESULTS.md') != FROZEN_H13_REPORT:
        raise ValueError('closed H13 report drifted')
    if sha('src/nexus/world/mcc_planning_ranking_confirm.py') != FROZEN_H13_CODE:
        raise ValueError('closed H13 implementation drifted')


def _spearman(xs, ys):
    a = np.asarray(xs, dtype=np.float64).reshape(-1)
    b = np.asarray(ys, dtype=np.float64).reshape(-1)
    if a.size != b.size or a.size < 2:
        raise ValueError('spearman needs paired finite vectors')
    ra = a.argsort(kind='mergesort').argsort().astype(np.float64)
    rb = b.argsort(kind='mergesort').argsort().astype(np.float64)
    if float(ra.std()) == 0.0 or float(rb.std()) == 0.0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def _corr(xs, ys):
    a = np.asarray(xs, dtype=np.float64)
    b = np.asarray(ys, dtype=np.float64)
    if a.size < 2 or float(a.std()) == 0.0 or float(b.std()) == 0.0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def reconstruct_state(state, seed, candidate_base):
    if tuple(sorted(state)) != tuple(sorted(SAVED_STATE)):
        raise ValueError('ranking state fields drifted')
    k = int(state['state_index'])
    expected_seed = int(candidate_base['state_reset_base']) + 10 * int(seed) + k
    if int(state['state_seed']) != expected_seed:
        raise ValueError('state_seed does not match the locked formula')
    sequences = candidate_sequences(
        int(candidate_base['candidate_base']) + 10 * int(seed) + k,
        N_CAND, HORIZON, n_actions=3)
    actual = np.asarray(state['actual'], dtype=np.float64)
    traces = state['traces']
    if actual.shape != (N_CAND,) or len(traces) != N_CAND:
        raise ValueError('shared ground-truth grid drifted')
    rebuilt = np.asarray([math.fsum(row) for row in traces], dtype=np.float64)
    if rebuilt.shape != actual.shape or not np.allclose(actual, rebuilt, atol=1e-8):
        raise ValueError('open-loop traces do not reconstruct realized returns')
    if not np.isfinite(actual).all():
        raise ValueError('nonfinite realized returns')
    obs0 = np.asarray(state['obs0'], dtype=np.float64)
    if obs0.shape != (2,) or not np.isfinite(obs0).all():
        raise ValueError('obs0 is missing or nonfinite')
    arms = {}
    for arm in ARMS:
        row = state['ranked'][arm]
        pred = np.asarray(row['predicted'], dtype=np.float64)
        if pred.shape != (N_CAND,) or not np.isfinite(pred).all():
            raise ValueError('nonfinite or misaligned predicted scores')
        selected = int(np.argmax(pred))
        if selected != int(row['selected']):
            raise ValueError('selected index is not argmax of predicted scores')
        if int(sequences[selected, 0]) != int(row['first_action']):
            raise ValueError('saved first action does not match the reconstructed candidate')
        seq_reg = h12.sequence_regret(pred, actual)
        fa_reg = h12.first_action_regret(pred, actual, sequences)
        if not np.isclose(seq_reg, float(row['sequence_regret']), atol=1e-12):
            raise ValueError('sequence regret reconstruction drifted')
        if not np.isclose(fa_reg, float(row['first_action_regret']), atol=1e-12):
            raise ValueError('first-action regret reconstruction drifted')
        pred_v = h12.first_action_values(pred, sequences)
        a_hat = max(pred_v, key=pred_v.get)
        selected_return = float(actual[selected])
        best_return = float(np.max(actual))
        recede = float(row['closed_loop_return'])
        if not np.isfinite(recede):
            raise ValueError('nonfinite recede return')
        arms[arm] = dict(
            selected=selected,
            first_action=int(row['first_action']),
            first_action_matches_v=bool(a_hat == int(row['first_action'])),
            sequence_regret=seq_reg,
            first_action_regret=fa_reg,
            selected_return=selected_return,
            best_return=best_return,
            recede=recede,
            recede_minus_selected=recede - selected_return,
            recede_minus_best=recede - best_return,
            spearman=_spearman(pred, actual),
            top1=bool(selected == int(np.argmax(actual))),
            selected_abserr=float(abs(pred[selected] - actual[selected])),
            mean_abserr=float(np.mean(np.abs(pred - actual))),
        )
    return dict(state_index=k, state_seed=int(state['state_seed']), obs0=obs0.tolist(),
                actual=actual.tolist(), arms=arms)


def study_payload(payload, *, candidate_base, label, physics):
    if payload.get('complete') is not True:
        raise ValueError('incomplete ranking artifact')
    if payload.get('closed_loop_is_primary') is not False or payload.get('full_episode_primary') is not False:
        raise ValueError('secondary recede was elevated to a primary')
    if payload.get('primary_metric') != 'scratch_minus_multitask_sequence_regret':
        raise ValueError('primary metric drifted')
    if list(payload.get('target_physics')) != list(physics):
        raise ValueError('artifact physics drifted')
    rows = {int(c['seed']): c for c in payload['cells']}
    if set(rows) != set(range(N_SEEDS)):
        raise ValueError('incomplete or duplicated seed grid')
    seed_rows = []
    state_pairs = []
    for seed in range(N_SEEDS):
        cell = rows[seed]
        states = cell['states']
        if len(states) != N_STATES or {int(s['state_index']) for s in states} != set(range(N_STATES)):
            raise ValueError('incomplete or duplicated state grid')
        reconstructed = [reconstruct_state(st, seed, candidate_base) for st in states]
        seq = {arm: float(np.mean([st['arms'][arm]['sequence_regret'] for st in reconstructed]))
               for arm in ARMS}
        fa = {arm: float(np.mean([st['arms'][arm]['first_action_regret'] for st in reconstructed]))
              for arm in ARMS}
        recede = {arm: float(np.mean([st['arms'][arm]['recede'] for st in reconstructed]))
                  for arm in ARMS}
        selected = {arm: float(np.mean([st['arms'][arm]['selected_return'] for st in reconstructed]))
                    for arm in ARMS}
        bonus = {arm: float(np.mean([st['arms'][arm]['recede_minus_selected'] for st in reconstructed]))
                 for arm in ARMS}
        if not np.allclose([seq[arm] for arm in ARMS],
                           [float(cell['sequence_regret'][arm]) for arm in ARMS], atol=1e-12):
            raise ValueError('seed sequence-regret mean drifted')
        if not np.allclose([fa[arm] for arm in ARMS],
                           [float(cell['first_action_regret'][arm]) for arm in ARMS], atol=1e-12):
            raise ValueError('seed first-action-regret mean drifted')
        if not np.allclose([recede[arm] for arm in ARMS],
                           [float(cell['closed_loop_return'][arm]) for arm in ARMS], atol=1e-12):
            raise ValueError('seed recede mean drifted')
        seq_delta = seq['scratch'] - seq['multitask']
        recede_delta = recede['multitask'] - recede['scratch']
        selected_delta = selected['multitask'] - selected['scratch']
        if not np.isclose(seq_delta, selected_delta, atol=1e-12):
            raise ValueError('shared-ground-truth identity failed')
        seed_rows.append(dict(
            seed=seed, sequence_delta=seq_delta, first_action_delta=fa['scratch'] - fa['multitask'],
            recede_delta=recede_delta, selected_delta=selected_delta,
            recede_bonus=bonus, sequence_regret=seq, first_action_regret=fa,
            recede=recede, selected_return=selected))
        for st in reconstructed:
            state_pairs.append(dict(
                seed=seed, state_index=st['state_index'],
                sequence_delta=st['arms']['scratch']['sequence_regret']
                - st['arms']['multitask']['sequence_regret'],
                recede_delta=st['arms']['multitask']['recede'] - st['arms']['scratch']['recede'],
                same_first_action=st['arms']['multitask']['first_action']
                == st['arms']['scratch']['first_action'],
                first_action={arm: st['arms'][arm]['first_action'] for arm in ARMS},
                recede_minus_selected={arm: st['arms'][arm]['recede_minus_selected'] for arm in ARMS},
                spearman={arm: st['arms'][arm]['spearman'] for arm in ARMS},
                top1={arm: st['arms'][arm]['top1'] for arm in ARMS},
                selected_abserr={arm: st['arms'][arm]['selected_abserr'] for arm in ARMS},
                mean_abserr={arm: st['arms'][arm]['mean_abserr'] for arm in ARMS},
                first_action_matches_v={arm: st['arms'][arm]['first_action_matches_v'] for arm in ARMS},
            ))
    seq_ci = seed_level_ci([r['sequence_delta'] for r in seed_rows])
    fa_ci = seed_level_ci([r['first_action_delta'] for r in seed_rows])
    recede_ci = seed_level_ci([r['recede_delta'] for r in seed_rows])
    saved = payload['groups']['primary']['interval']
    if not np.isclose(seq_ci['mean'], saved['mean'], atol=1e-12):
        raise ValueError('recomputed primary mean drifted')
    if not np.isclose(seq_ci['lo'], saved['lo'], atol=1e-12) or not np.isclose(seq_ci['hi'], saved['hi'], atol=1e-12):
        raise ValueError('recomputed primary interval drifted')
    if payload['label'] != label:
        raise ValueError('saved label drifted')
    return dict(
        label=label,
        physics=list(physics),
        primary=seq_ci,
        first_action=fa_ci,
        recede=recede_ci,
        selected_open_loop=seed_level_ci([r['selected_delta'] for r in seed_rows]),
        recede_bonus={arm: seed_level_ci([r['recede_bonus'][arm] for r in seed_rows]) for arm in ARMS},
        n_positive_sequence=int(sum(r['sequence_delta'] > 0 for r in seed_rows)),
        n_positive_first_action=int(sum(r['first_action_delta'] > 0 for r in seed_rows)),
        n_positive_recede=int(sum(r['recede_delta'] > 0 for r in seed_rows)),
        corr_sequence_vs_recede_seed=_corr([r['sequence_delta'] for r in seed_rows],
                                           [r['recede_delta'] for r in seed_rows]),
        corr_sequence_vs_recede_state=_corr([r['sequence_delta'] for r in state_pairs],
                                            [r['recede_delta'] for r in state_pairs]),
        same_first_action_rate=float(np.mean([r['same_first_action'] for r in state_pairs])),
        first_action_matches_v_rate={arm: float(np.mean([r['first_action_matches_v'][arm] for r in state_pairs]))
                                     for arm in ARMS},
        spearman={arm: float(np.mean([r['spearman'][arm] for r in state_pairs])) for arm in ARMS},
        top1={arm: float(np.mean([r['top1'][arm] for r in state_pairs])) for arm in ARMS},
        selected_abserr={arm: float(np.mean([r['selected_abserr'][arm] for r in state_pairs])) for arm in ARMS},
        mean_abserr={arm: float(np.mean([r['mean_abserr'][arm] for r in state_pairs])) for arm in ARMS},
        state_sign_agree=int(sum((r['sequence_delta'] > 0) == (r['recede_delta'] > 0) for r in state_pairs)),
        n_states=len(state_pairs),
        seed_rows=seed_rows,
        missing_recede_fields=list(MISSING_RECEDE),
        closed_loop_is_primary=False,
    )


def analyze():
    assert_closed_hashes()
    h12_p = json.loads(h12.OUTPUT.read_text())
    h13_p = json.loads(h13.OUTPUT.read_text())
    h12_s = study_payload(h12_p, candidate_base=dict(
        state_reset_base=74100000, candidate_base=74200000),
        label='mcc_planning_ranking_multitask_better', physics=[0.0027, 0.0015, 0.075])
    h13_s = study_payload(h13_p, candidate_base=dict(
        state_reset_base=75100000, candidate_base=75200000),
        label='mcc_planning_ranking_confirm_multitask_better', physics=[0.0039, 0.002, 0.075])
    return dict(
        complete=True,
        new_environment_interactions=0,
        new_imagined_transitions=0,
        trained=False,
        authorized=False,
        claims_learning_to_learn=False,
        is_agi=False,
        closed_loop_is_primary=False,
        statistical_unit='independent_model_seed',
        h12=h12_s,
        h13=h13_s,
        testable_with_saved_artifacts=dict(
            reset_state_ranking=True,
            first_action_vs_sequence_at_obs0=True,
            shared_open_loop_identity=True,
            recede_scalar_return=True,
            recede_bonus_vs_commitment=True,
            later_state_ranking=False,
            recede_actions_or_occupancy=False,
            multi_step_residuals=False,
        ),
        mechanisms=dict(
            A_later_state_decay='unresolved_insufficient_later_states',
            B_compounding_prediction_error='unresolved_no_recede_residuals',
            C_sequence_vs_feedback_action='partial_obs0_first_action_matches_V',
            D_recede_option_value_or_exploitation='compatible_not_distinguished',
        ),
        strongest_supported_claim=(
            'H12 and H13 establish better same-state ranking, not better recede control.'
        ),
    )


def run():
    result = analyze()
    save(OUTPUT, result)
    return result
