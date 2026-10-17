"""Source-only H10/H11 audit guards. No environment collection."""
from __future__ import annotations
import json
from pathlib import Path
from nexus.world import h10_h11_control_disagreement_audit as m
from nexus.world import mcc_multitask_128 as h10
from nexus.world import mcc_multitask_128_confirm as h11
from nexus.world.planning_value import sha


def test_closed_hashes_and_recomputed_primaries_match():
    m.assert_closed_hashes()
    result = m.analyze()
    assert result['new_environment_interactions'] == 0
    assert result['trained'] is False
    assert result['not_a_harm_claim'] is True
    assert result['claims_learning_to_learn'] is False
    assert result['is_agi'] is False
    h10_p = json.loads(h10.OUTPUT.read_text())
    h11_p = json.loads(h11.OUTPUT.read_text())
    assert result['h10']['primary']['mean'] == h10_p['groups']['primary']['interval']['mean']
    assert result['h11']['primary']['mean'] == h11_p['groups']['primary']['interval']['mean']
    assert result['h10']['n_positive'] == 10
    assert result['h11']['n_positive'] == 8
    assert result['h11_negative_seeds'] == [4, 5]
    assert result['h11_negative_still_better_mae'] is True
    assert result['h10']['all_200_steps'] and result['h11']['all_200_steps']
    assert result['h10']['any_terminated'] is False
    assert 'observations' in result['h11']['missing_fields']
    assert result['testable_with_saved_artifacts']['action_ranking'] is False
    assert result['testable_with_saved_artifacts']['reward_phase_split'] is True
    assert sha(h10.OUTPUT) == m.FROZEN_H10_RAW
    assert sha(h11.OUTPUT) == m.FROZEN_H11_RAW


def test_early_plus_late_reconstructs_every_saved_return():
    result = m.analyze()
    for study in (result['h10'], result['h11']):
        for row in study['rows']:
            for arm in m.ARMS:
                tr = row['traces'][arm]
                total = tr['early_return'] + tr['late_return']
                assert abs(total - tr['episode_return']) < 1e-8
                assert set(tr['fields']) == set(m.TRACE_FIELDS)


def test_audit_module_does_not_collect_or_train():
    src = Path(m.__file__).read_text(encoding='utf-8')
    assert 'collect_transitions' not in src
    assert 'train_world_model' not in src
    assert 'make_task_env' not in src
    result = m.analyze()
    assert result['not_a_harm_claim'] is True
