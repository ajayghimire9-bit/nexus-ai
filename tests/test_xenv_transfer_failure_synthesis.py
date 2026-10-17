"""Offline guards for the seven-rung xenv failure synthesis. No collection."""
from __future__ import annotations
from nexus.world import xenv_transfer_failure_synthesis as m


def test_all_seven_primaries_include_zero_and_are_not_established():
    report = m.analyze()
    assert report['new_environment_steps'] == 0
    assert len(report['rungs']) == 7
    labels = [row['label'] for row in report['rungs']]
    assert labels == [
        'xenv_shared_layer_not_established',
        'xenv_deep_trunk_not_established',
        'xenv_context_code_not_established',
        'xenv_residual_context_not_established',
        'xenv_prior_scale_not_established',
        'xenv_low_budget_not_established',
        'xenv_cartpole_target_not_established',
    ]
    for row in report['rungs']:
        assert row['primary']['lo'] <= 0 <= row['primary']['hi']
        assert row['claims_learning_to_learn'] is False


def test_shared_layer_is_a_minority_of_rung1_weights():
    counts = m.architecture_inventory()['parameter_counts']
    assert counts['rung1_shared_layer'] == dict(total=7186, shared=4160, family=3026, other=0)
    assert counts['rung2_deep_trunk']['shared'] == 8320
    assert counts['rung3_occupancy_film']['total'] == 8858
    assert counts['rung4_residual_film']['total'] == 8906
    assert m.architecture_inventory()['residual_pad'] == 6


def test_cartpole_ceiling_and_next_direction_are_not_another_xenv_variant():
    report = m.analyze()
    ceiling = report['rungs'][6]['ceiling_at_200']
    assert ceiling['1024']['xenv'] == 9 and ceiling['1024']['scratch'] == 9
    assert ceiling['128']['xenv'] == 0
    nxt = report['next_direction']
    assert nxt['name'] == 'family_native_interface_adaptation'
    banned = ('shared-trunk', 'FiLM trunk', 'another target family', 'low-budget xenv')
    text = nxt['minimal_future_experiment'] + nxt['why_not_another_xenv_variant']
    assert 'No cross-family weights' in nxt['minimal_future_experiment']
    assert all(term not in nxt['name'] for term in banned)
    assert report['bottleneck']['status'] == 'supported_interpretation'
    assert report['bottleneck']['not_a_trained_label'] is True
