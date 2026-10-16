"""Recorded horizon-alignment feasibility. No registered-grid collection."""
import json
from nexus.world import horizon_alignment as m
from nexus.world.planning_value import sha


def test_feasibility_is_offline_unauthorized_and_records_timelimit():
    p=json.loads(m.FEASIBILITY.read_text());audit=json.loads(m.AUDIT.read_text())
    assert p['complete'] is True and p['authorized'] is False
    assert p['new_environment_steps']==0 and p['new_imagined_transitions']==0
    assert audit['new_environment_steps']==0 and audit['authorized'] is False
    assert p['time_limit']['max_episode_steps']==200
    assert p['time_limit']['true_terminal_state'] is False
    assert p['time_limit']['planner_clips_elapsed_time'] is False
    assert p['primary']=='gain_full' and p['practical_margin_full']==25.0
    assert p['proposed_budget']['full_fixed']==12000
    assert p['retrospective']['artificial_cutoff'] is True
    assert p['retrospective']['parent_label']=='same_set_advantage_not_established'
    assert p['checkpoints']==dict(verified=120,missing=0,mismatched=0)
    assert p['config_sha256']==sha(m.CONFIG)
    assert p['protocol_sha256']==sha(m.PROTOCOL)
    assert p['score_correction_closed'] is True and p['confirmation_used'] is False
