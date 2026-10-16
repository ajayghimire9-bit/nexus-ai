"""Recorded receding-consistency feasibility. No new environment collection."""
import json
from nexus.world import receding_policy_consistency as m
from nexus.world.planning_value import sha


def test_feasibility_artifact_is_offline_and_unauthorized():
    p=json.loads(m.FEASIBILITY.read_text())
    assert p['complete'] is True
    assert p['new_environment_steps']==0 and p['new_imagined_transitions']==0
    assert p['authorized'] is False
    assert p['score_correction_closed'] is True
    assert p['development_outcomes_used_for_tuning'] is False
    assert p['confirmation_used'] is False
    assert p['primary']=='gain_commit_fresh'
    assert p['proposed_budget']['commit']==2560
    assert p['archived_live']['visited_commitment']['confounded'] is True
    assert p['checkpoints']==dict(verified=120,missing=0,mismatched=0)
    assert p['config_sha256']==sha(m.CONFIG)
    assert p['protocol_sha256']==sha(m.PROTOCOL)
