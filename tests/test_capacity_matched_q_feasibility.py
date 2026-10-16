"""Recorded offline feasibility. No new environment collection."""
import json
from nexus.world import capacity_matched_q as m


def test_feasibility_artifact_is_offline_and_unauthorized():
    p=json.loads(m.FEASIBILITY.read_text())
    assert p['complete'] is True
    assert p['new_environment_steps']==0 and p['new_imagined_transitions']==0
    assert p['authorized'] is False
    assert p['n_weights']==81 and p['polynomial_coordinates']==77
    hist=p['historical_source_decoder0']
    assert hist['n_unique_labels']==24 and hist['feature_rank']==50
    assert hist['state_independent_action_ranking'] is True
    assert p['development_outcomes_used'] is False
    assert p['confirmation_used'] is False
    assert p['linear_q_weights_used'] is False
    assert p['config_sha256']==m.sha(m.CONFIG)
    assert p['protocol_sha256']==m.sha(m.PROTOCOL)
