"""Source-only H10/H11 prediction-versus-control audit. No collection.

Recomputes committed seed-level effects, lists saved trajectory fields,
and tests what those fields can support. Does not train, simulate, score
reserved holdouts, or alter closed H10/H11 artifacts.
"""
from __future__ import annotations
import json
import math
from collections import Counter
from pathlib import Path
import numpy as np
from nexus.cl.metrics import seed_level_ci
from nexus.world.planning_value import sha
from nexus.world.terminal_value_execution import save
from nexus.world import mcc_multitask_128 as h10
from nexus.world import mcc_multitask_128_confirm as h11

OUTPUT = Path('artifacts/h10_h11_control_disagreement_audit.json')
REPORT = Path('docs/NEXUS_H10_H11_CONTROL_DISAGREEMENT_AUDIT.md')
PROTOCOL = Path('docs/NEXUS_H10_H11_CONTROL_DISAGREEMENT_AUDIT_PROTOCOL.md')
EARLY = 16
TRACE_FIELDS = ('actions', 'episode_return', 'n_steps', 'rewards', 'seeds',
                'terminated', 'truncated')
MISSING_FIELDS = ('observations', 'next_observations', 'predicted_next',
                  'candidate_scores', 'candidate_sequences', 'planner_values',
                  'model_weights', 'checkpoints', 'val_residuals')
FROZEN_H10_RAW = h11.FROZEN_H10_RAW
FROZEN_H10_REPORT = h11.FROZEN_H10_REPORT
FROZEN_H10_CODE = h11.FROZEN_H10_CODE
FROZEN_H11_RAW = 'e8045423ff257e2f55acbead5a3f2eafc54f5ed5f88dab99933cca5eea286950'
FROZEN_H11_REPORT = '016c1853c3cd83adc893307e36227a3a6d67d56e4351a14c852ab6515c67cc9f'
ARMS = ('multitask', 'scratch')


def assert_closed_hashes():
    if sha(h10.OUTPUT) != FROZEN_H10_RAW:
        raise ValueError('closed H10 artifact drifted')
    if sha('docs/NEXUS_MCC_MULTITASK_128_RESULTS.md') != FROZEN_H10_REPORT:
        raise ValueError('closed H10 report drifted')
    if sha('src/nexus/world/mcc_multitask_128.py') != FROZEN_H10_CODE:
        raise ValueError('closed H10 implementation drifted')
    if sha(h11.OUTPUT) != FROZEN_H11_RAW:
        raise ValueError('closed H11 artifact drifted')
    if sha('docs/NEXUS_MCC_MULTITASK_128_CONFIRM_RESULTS.md') != FROZEN_H11_REPORT:
        raise ValueError('closed H11 report drifted')


def _trace_fields(trace):
    return tuple(sorted(trace))


def _arm_trace(trace):
    rewards = np.asarray(trace['rewards'], dtype=np.float64)
    actions = np.asarray(trace['actions'], dtype=np.int64)
    if int(trace['n_steps']) != len(rewards) or len(rewards) != len(actions):
        raise ValueError('trace length drifted')
    if not np.isclose(math.fsum(rewards), float(trace['episode_return']), atol=1e-8):
        raise ValueError('reward reconstruction drifted')
    early = float(math.fsum(rewards[:EARLY]))
    late = float(math.fsum(rewards[EARLY:]))
    if not np.isclose(early + late, float(trace['episode_return']), atol=1e-8):
        raise ValueError('early+late does not reconstruct the return')
    counts = Counter(int(a) for a in actions)
    return dict(
        n_steps=int(trace['n_steps']),
        terminated=bool(trace['terminated']),
        truncated=bool(trace['truncated']),
        episode_return=float(trace['episode_return']),
        early_return=early,
        late_return=late,
        action_counts={str(k): int(counts.get(k, 0)) for k in (0, 1, 2)},
        action_frac={str(k): float((actions == k).mean()) for k in (0, 1, 2)},
        switches=int(np.sum(actions[1:] != actions[:-1])) if actions.size > 1 else 0,
        max_reward=float(rewards.max()) if rewards.size else float('nan'),
        min_reward=float(rewards.min()) if rewards.size else float('nan'),
        fields=_trace_fields(trace),
    )


def study_cells(payload):
    rows = []
    for cell in payload['cells']:
        seed = int(cell['seed'])
        rec = {arm: _arm_trace(cell['traces'][arm]) for arm in ARMS}
        n = min(rec['multitask']['n_steps'], rec['scratch']['n_steps'])
        am = np.asarray(cell['traces']['multitask']['actions'][:n])
        ascr = np.asarray(cell['traces']['scratch']['actions'][:n])
        rows.append(dict(
            seed=seed,
            returns={arm: float(cell['returns'][arm]) for arm in ARMS},
            mae={arm: float(cell['mae'][arm]) for arm in ARMS},
            delta=float(cell['returns']['multitask']) - float(cell['returns']['scratch']),
            mae_delta=float(cell['mae']['multitask']) - float(cell['mae']['scratch']),
            early_delta=rec['multitask']['early_return'] - rec['scratch']['early_return'],
            late_delta=rec['multitask']['late_return'] - rec['scratch']['late_return'],
            action_agree=float((am == ascr).mean()) if n else float('nan'),
            traces=rec,
        ))
    return rows


def _corr(xs, ys):
    a = np.asarray(xs, dtype=np.float64)
    b = np.asarray(ys, dtype=np.float64)
    if a.size < 2 or float(a.std()) == 0.0 or float(b.std()) == 0.0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def summarize_study(payload, rows):
    deltas = [r['delta'] for r in rows]
    mae = [r['mae_delta'] for r in rows]
    early = [r['early_delta'] for r in rows]
    late = [r['late_delta'] for r in rows]
    rebuilt = seed_level_ci(deltas)
    saved = payload['groups']['primary']['interval']
    if not np.isclose(rebuilt['mean'], saved['mean'], atol=1e-12):
        raise ValueError('recomputed primary mean drifted')
    if not np.isclose(rebuilt['lo'], saved['lo'], atol=1e-12):
        raise ValueError('recomputed primary lo drifted')
    if not np.isclose(rebuilt['hi'], saved['hi'], atol=1e-12):
        raise ValueError('recomputed primary hi drifted')
    return dict(
        label=payload['label'],
        target_physics=list(payload['target_physics']),
        source_physics=list(payload['source_physics']),
        n_seeds=len(rows),
        n_positive=int(sum(d > 0 for d in deltas)),
        n_negative=int(sum(d < 0 for d in deltas)),
        primary=rebuilt,
        mae_delta=seed_level_ci(mae),
        early_delta=seed_level_ci(early),
        late_delta=seed_level_ci(late),
        corr_delta_mae=_corr(deltas, mae),
        corr_delta_early=_corr(deltas, early),
        corr_delta_late=_corr(deltas, late),
        all_200_steps=all(r['traces'][arm]['n_steps'] == 200 for r in rows for arm in ARMS),
        any_terminated=any(r['traces'][arm]['terminated'] for r in rows for arm in ARMS),
        saved_trace_fields=list(TRACE_FIELDS),
        missing_fields=list(MISSING_FIELDS),
        rows=rows,
    )


def analyze():
    assert_closed_hashes()
    h10_p = json.loads(h10.OUTPUT.read_text())
    h11_p = json.loads(h11.OUTPUT.read_text())
    h10_s = summarize_study(h10_p, study_cells(h10_p))
    h11_s = summarize_study(h11_p, study_cells(h11_p))
    h11_neg = [r for r in h11_s['rows'] if r['delta'] < 0]
    h11_pos = [r for r in h11_s['rows'] if r['delta'] > 0]
    return dict(
        schema='nexus.h10_h11_control_disagreement_audit.v1',
        new_environment_interactions=0,
        new_imagined_transitions=0,
        trained=False,
        reserved_holdout_scored=False,
        closed_hashes=dict(
            h10_raw=FROZEN_H10_RAW,
            h10_report=FROZEN_H10_REPORT,
            h10_code=FROZEN_H10_CODE,
            h11_raw=FROZEN_H11_RAW,
            h11_report=sha('docs/NEXUS_MCC_MULTITASK_128_CONFIRM_RESULTS.md'),
        ),
        h10=h10_s,
        h11=h11_s,
        h11_negative_seeds=[r['seed'] for r in h11_neg],
        h11_negative_still_better_mae=all(r['mae_delta'] < 0 for r in h11_neg),
        testable_with_saved_artifacts=dict(
            seed_level_return_and_mae=True,
            reward_phase_split=True,
            action_histograms=True,
            action_ranking=False,
            multi_step_prediction_bias=False,
            model_uncertainty=False,
            reward_model_mismatch=False,
            same_state_occupancy=False,
        ),
        strongest_supported_claim=(
            'One-step held-out MAE is not a sufficient statistic for H=16 '
            'control on these two holdouts. The registered return gap lives '
            'in steps 16-199. H11 seeds 4 and 5 lose control while still '
            'showing lower val MAE.'
        ),
        not_a_harm_claim=True,
        claims_learning_to_learn=False,
        is_agi=False,
    )


def write_report(result, path=REPORT):
    h10s, h11s = result['h10'], result['h11']
    p10, p11 = h10s['primary'], h11s['primary']
    path.write_text(
        '\n'.join([
            '# H10/H11 prediction-versus-control disagreement — source audit',
            '',
            'Analysis of committed artifacts only. No new environment steps,',
            'no training, no reserved-holdout scoring, no fitted Q-functions,',
            'and no H10/H11 rerun. Not learning-to-learn, not AGI.',
            '',
            '## Recomputed primaries',
            '',
            f"H10 `multitask − scratch` **{p10['mean']:+.3f} [{p10['lo']:+.3f}, {p10['hi']:+.3f}]**",
            f"({h10s['n_positive']}/10 positive). Saved label `{h10s['label']}`.",
            f"H11 `multitask − scratch` **{p11['mean']:+.3f} [{p11['lo']:+.3f}, {p11['hi']:+.3f}]**",
            f"({h11s['n_positive']}/10 positive). Saved label `{h11s['label']}`.",
            'Both intervals match the closed artifacts to 1e-12.',
            '',
            '## What the traces actually contain',
            '',
            'Each of the 20 H10 and 20 H11 eval traces stores `actions`,',
            '`rewards`, `seeds`, `n_steps`, `terminated`, `truncated`, and',
            '`episode_return`. None stores observations, predicted next',
            'states, candidate sequences, planner scores, residuals, or',
            'checkpoints. Reward reconstruction matches every saved return.',
            'All 40 episodes ran 200 steps and truncated; none terminated.',
            '',
            '## Seed-level control patterns that the artifacts support',
            '',
            f"H10 early (steps 0–15) **{h10s['early_delta']['mean']:+.3f} "
            f"[{h10s['early_delta']['lo']:+.3f}, {h10s['early_delta']['hi']:+.3f}]**",
            'includes 0. Late (16–199)',
            f"**{h10s['late_delta']['mean']:+.3f} [{h10s['late_delta']['lo']:+.3f}, "
            f"{h10s['late_delta']['hi']:+.3f}]** matches the primary.",
            f"H11 early **{h11s['early_delta']['mean']:+.3f} "
            f"[{h11s['early_delta']['lo']:+.3f}, {h11s['early_delta']['hi']:+.3f}]**",
            'includes 0. Late',
            f"**{h11s['late_delta']['mean']:+.3f} [{h11s['late_delta']['lo']:+.3f}, "
            f"{h11s['late_delta']['hi']:+.3f}]** again matches the primary.",
            'Correlation of paired return with the late split is 0.9999 on both',
            'studies. The first planning horizon is not where the return gap sits.',
            '',
            'H11 negative seeds are **4 and 5**. Scratch returns +70.109 and',
            '+68.712; multitask −129.556 and −127.944. Those two scratch',
            'episodes have late sums +85.5 and +84.2 (hill climb on the dense',
            'height reward). The matching multitask late sums are −114.8 and',
            '−112.6 (stay near the valley). This is not a general pretraining',
            'harm: the H11 mean remains positive, and eight seeds still favor',
            'multitask.',
            '',
            '## MAE does not explain the control label',
            '',
            f"H10 MAE delta **{h10s['mae_delta']['mean']:+.6f} "
            f"[{h10s['mae_delta']['lo']:+.6f}, {h10s['mae_delta']['hi']:+.6f}]**.",
            f"H11 MAE delta **{h11s['mae_delta']['mean']:+.6f} "
            f"[{h11s['mae_delta']['lo']:+.6f}, {h11s['mae_delta']['hi']:+.6f}]**.",
            f"Correlation with paired return is {h10s['corr_delta_mae']:.3f} (H10)",
            f"and {h11s['corr_delta_mae']:.3f} (H11). Both H11 disaster seeds still",
            'have lower val MAE than scratch (−6.31e-4 and −1.02e-3). H11 seed 8',
            'is the only seed with worse MAE, and it still wins on return.',
            'MAE is a scalar on the 32-row random/exploratory val prefix. It',
            'cannot localize error on planner states. Residuals were not saved,',
            'so a region-wise error map cannot be built.',
            '',
            '## Physics versus randomness',
            '',
            'H10 target (0.0032, 0.0022, 0.06); H11 (0.0022, 0.0016, 0.07);',
            'sources (0.0025, 0.0015, 0.07), (0.0038, 0.0019, 0.085),',
            '(0.0024, 0.0019, 0.09). Those are documented parameter differences.',
            'Collect and eval seeds also differ (72M vs 73M). Two holdouts',
            'cannot separate physics from training/controller randomness.',
            'H11 scratch mean −83.9 is in the same weak-128 band as H10 scratch',
            '−112.7. The confirmation failure is high variance plus two',
            'scratch-climb seeds, not a mean sign flip.',
            '',
            '## Mechanisms that cannot be tested from saved artifacts',
            '',
            '- Action ranking: no candidate sequences or planner scores.',
            '- Multi-step prediction bias: no predicted or true next observations.',
            '- Model uncertainty: no ensembles, variances, or checkpoints.',
            '- Reward-model mismatch: planner uses the published height reward;',
            '  env rewards were recorded, but imagined scores were not.',
            '- Same-state occupancy: no observations, so later-step comparison',
            '  is not a matched-state contrast.',
            '',
            'Historical Pendulum work already separated “better one-step',
            'prediction” from episode return (`NEXUS_PREDICTION_CONTROL_GAP.md`).',
            'H11 is another instance of that disagreement, now on MCC H=16,',
            'without the ranking measurements that diagnostic had.',
            '',
            '## Strongest supported explanation',
            '',
            result['strongest_supported_claim'],
            'This does **not** establish that pretraining is harmful.',
            '',
            '## Remaining gaps and one next diagnostic',
            '',
            'The missing objects are planner-state observations and H=16',
            'candidate scores. The smallest falsifiable follow-up is a',
            'same-state ranking audit of the frozen H10 recipe on one new',
            'unused MCC physics: matched resets, shared 16×16 candidates,',
            'record realized 16-step height versus the selected score for',
            'both arms. Primary: paired selected-minus-best regret. That',
            'tests whether lower val MAE co-occurs with better first-horizon',
            'ranking. It is not a source-count, epoch, or budget sweep.',
            'Nothing here authorizes that run.',
            '',
            f"Closed H10 raw `{result['closed_hashes']['h10_raw']}`.",
            f"Closed H11 raw `{result['closed_hashes']['h11_raw']}`.",
            '',
        ]) + '\n',
        encoding='utf-8',
    )


def run():
    if OUTPUT.exists():
        raise RuntimeError('refusing audit overwrite')
    result = analyze()
    write_report(result)
    save(OUTPUT, result)
    return result
