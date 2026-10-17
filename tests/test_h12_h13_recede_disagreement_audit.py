"""Source-only H12/H13 recede-disagreement audit guards. No collection."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.world import h12_h13_recede_disagreement_audit as m
from nexus.world import mcc_planning_ranking as h12
from nexus.world import mcc_planning_ranking_confirm as h13
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences


def test_closed_hashes_and_recomputed_primaries_match():
    m.assert_closed_hashes()
    result = m.analyze()
    assert result['new_environment_interactions'] == 0
    assert result['new_imagined_transitions'] == 0
    assert result['trained'] is False
    assert result['authorized'] is False
    assert result['closed_loop_is_primary'] is False
    assert result['claims_learning_to_learn'] is False
    assert result['is_agi'] is False
    h12_p = json.loads(h12.OUTPUT.read_text())
    h13_p = json.loads(h13.OUTPUT.read_text())
    assert result['h12']['primary']['mean'] == h12_p['groups']['primary']['interval']['mean']
    assert result['h13']['primary']['mean'] == h13_p['groups']['primary']['interval']['mean']
    assert result['h12']['n_positive_sequence'] == 10
    assert result['h13']['n_positive_sequence'] == 10
    assert result['h12']['n_positive_recede'] == 5
    assert result['h13']['n_positive_recede'] == 2
    assert result['h12']['label'] == 'mcc_planning_ranking_multitask_better'
    assert result['h13']['label'] == 'mcc_planning_ranking_confirm_multitask_better'
    assert result['testable_with_saved_artifacts']['reset_state_ranking'] is True
    assert result['testable_with_saved_artifacts']['later_state_ranking'] is False
    assert result['h12']['closed_loop_is_primary'] is False
    assert sha(h12.OUTPUT) == m.FROZEN_H12_RAW
    assert sha(h13.OUTPUT) == m.FROZEN_H13_RAW


def test_shared_ground_truth_identity_and_candidate_alignment():
    result = m.analyze()
    for study in (result['h12'], result['h13']):
        for row in study['seed_rows']:
            assert abs(row['sequence_delta'] - row['selected_delta']) < 1e-12
        assert study['first_action_matches_v_rate']['multitask'] == 1.0
        assert study['first_action_matches_v_rate']['scratch'] == 1.0
        assert study['n_states'] == 40
    seq = candidate_sequences(74200000, 16, 16, n_actions=3)
    cell = json.loads(h12.OUTPUT.read_text())['cells'][0]['states'][0]
    assert int(cell['state_seed']) == 74100000
    assert int(seq[int(cell['ranked']['multitask']['selected']), 0]) == int(
        cell['ranked']['multitask']['first_action'])


def test_reconstruct_state_ties_missing_and_nonfinite():
    seed = 0
    base = dict(state_reset_base=74100000, candidate_base=74200000)
    sequences = candidate_sequences(74200000, 16, 16, n_actions=3)
    actual = np.linspace(-1.0, 1.0, 16)
    pred = np.zeros(16)
    pred[0] = 1.0
    pred[1] = 1.0
    traces = [[float(actual[i]) / 16.0] * 16 for i in range(16)]
    ranked = {
        'multitask': dict(predicted=pred.tolist(), selected=0, first_action=int(sequences[0, 0]),
                          sequence_regret=h12.sequence_regret(pred, actual),
                          first_action_regret=h12.first_action_regret(pred, actual, sequences),
                          closed_loop_return=-15.0),
        'scratch': dict(predicted=pred.tolist(), selected=0, first_action=int(sequences[0, 0]),
                        sequence_regret=h12.sequence_regret(pred, actual),
                        first_action_regret=h12.first_action_regret(pred, actual, sequences),
                        closed_loop_return=-15.0),
    }
    state = dict(state_index=0, state_seed=74100000, obs0=[0.1, 0.0],
                 actual=actual.tolist(), traces=traces, ranked=ranked)
    out = m.reconstruct_state(state, seed, base)
    assert out['arms']['multitask']['selected'] == 0
    bad = dict(state)
    bad['ranked'] = dict(ranked)
    bad['ranked']['multitask'] = dict(ranked['multitask'], predicted=[float('nan')] * 16)
    with pytest.raises(ValueError, match='nonfinite'):
        m.reconstruct_state(bad, seed, base)
    missing = dict(state)
    missing.pop('obs0')
    with pytest.raises(ValueError, match='fields drifted'):
        m.reconstruct_state(missing, seed, base)


def test_incomplete_seed_grid_and_secondary_not_primary():
    payload = json.loads(h12.OUTPUT.read_text())
    short = dict(payload, cells=payload['cells'][:9])
    with pytest.raises(ValueError, match='incomplete or duplicated seed grid'):
        m.study_payload(short, candidate_base=dict(state_reset_base=74100000, candidate_base=74200000),
                        label=payload['label'], physics=payload['target_physics'])
    elevated = dict(payload, closed_loop_is_primary=True)
    with pytest.raises(ValueError, match='elevated to a primary'):
        m.study_payload(elevated, candidate_base=dict(state_reset_base=74100000, candidate_base=74200000),
                        label=payload['label'], physics=payload['target_physics'])


def test_audit_module_does_not_collect_or_train():
    src = Path(m.__file__).read_text(encoding='utf-8')
    assert 'collect_transitions' not in src
    assert 'train_world_model' not in src
    assert 'make_task_env' not in src
    result = m.analyze()
    assert result['new_environment_interactions'] == 0
    assert 'closed_loop_actions' in result['h13']['missing_recede_fields']
