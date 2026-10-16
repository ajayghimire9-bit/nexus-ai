"""Recorded source-only feasibility. No new environment collection."""
import json
from nexus.world import action_conditioned_q as m


def test_feasibility_artifact_is_offline_and_selects_action_obs():
    p=json.loads(m.FEASIBILITY.read_text())
    assert p['complete'] is True
    assert p['new_environment_steps']==0 and p['new_imagined_transitions']==0
    assert p['authorized'] is False
    assert p['development_outcomes_used'] is False and p['confirmation_used'] is False
    assert p['synthetic']['action_obs_state_dependent'] is True
    assert p['synthetic']['additive_state_dependent'] is False
    assert p['selected']['family']=='action_obs' and p['selected']['ridge']==0.1
    assert p['selected']['n_weights']==16
    assert p['registered_family']=='action_obs'
    assert p['historical_unique_labels_per_decoder']==24
    assert p['proposed_unique_labels_per_decoder']==48
    assert p['cross_task_source_cv']['additive']['0.1']['action_id']==0.3125
    assert p['config_sha256']==m.sha(m.CONFIG)
    assert p['protocol_sha256']==m.sha(m.PROTOCOL)
