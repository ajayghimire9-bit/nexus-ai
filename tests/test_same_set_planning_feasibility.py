"""Recorded same-set feasibility and retrospective audit. No new environment collection."""
import json
from nexus.world import same_set_planning as m
from nexus.world.planning_value import sha


def test_feasibility_and_retrospective_are_offline_and_unauthorized():
    p=json.loads(m.FEASIBILITY.read_text());audit=json.loads(m.AUDIT.read_text())
    assert p['complete'] is True and audit['complete'] is True
    assert p['new_environment_steps']==0 and p['new_imagined_transitions']==0
    assert audit['new_environment_steps']==0 and audit['new_imagined_transitions']==0
    assert p['authorized'] is False and p['score_correction_closed'] is True
    assert p['confirmation_used'] is False and audit['confirmation_used'] is False
    assert p['primary']=='gain_same_fresh'
    assert p['proposed_budget']['same']==960
    assert p['equal_recede_imagined'] is True
    assert p['h16_is_production_controller'] is True
    assert audit['retrospective'] is True and audit['cannot_upgrade_locked_label'] is True
    assert audit['locked_primary_label']=='replan_consistency_not_established'
    assert audit['n_cells']==160
    assert audit['scientific_status']=='credible_retrospective_confounded_by_horizon_mismatch'
    assert audit['fairness']['imagined_ratio_fresh_over_same']==2.0
    assert audit['fairness']['fresh_plans_past_evaluation_window'] is True
    assert audit['parent_sha256']==sha(m.PARENT)
    assert p['checkpoints']==dict(verified=120,missing=0,mismatched=0)
    assert p['config_sha256']==sha(m.CONFIG)
    assert p['protocol_sha256']==sha(m.PROTOCOL)
