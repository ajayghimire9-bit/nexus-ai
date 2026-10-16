"""Late-episode trajectory locks. These tests do not collect the registered grid."""
from __future__ import annotations
import inspect
from pathlib import Path
import numpy as np
import pytest
import yaml
from nexus.tasks.pendulum_family import pendulum_context_confirmation, pendulum_context_development, PENDULUM_MAX_STEPS
from nexus.world import late_episode_decision_trajectory as m
from nexus.world import decision_aware_world_model as dawm
from nexus.world import horizon_alignment as horizon
from nexus.world import same_set_planning as same
from nexus.world import receding_policy_consistency as recede
from nexus.world import action_conditioned_q as acq
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import planner_scores, candidate_sequences


def test_archive_lacks_per_step_actions_and_scores():
    missing=m.inventory()
    paths={row['artifact'] for row in missing}
    assert 'return_phase_decomposition.json' in paths
    assert 'horizon_alignment.json' in paths
    assert 'late_control_gap.json' in paths


def test_shared_step_seeds_are_visitor_independent():
    cfg=yaml.safe_load(m.CONFIG.read_text())
    a=m.step_seed(cfg,3,1,64);b=m.step_seed(cfg,3,1,64)
    assert a==b and m.step_seed(cfg,3,1,65)==a+1
    seq=candidate_sequences(a,16,16);again=candidate_sequences(a,16,16)
    assert np.array_equal(seq,again) and seq.shape==(16,16)


def test_same_state_prefix_stops_at_first_mismatch():
    a=[0]*10+[1]*190;b=[0]*10+[2]*190
    assert m.first_mismatch(a,b)==10
    student=dict(actions=a,rewards=[0.0]*200,angvel_err=[0.1]*64+[0.4]*136,planned_second=[0]*200)
    zero=dict(actions=b,rewards=[0.0]*200,angvel_err=[0.1]*64+[0.2]*136,planned_second=[0]*200)
    metrics=m.cell_metrics(student,zero)
    assert metrics['n_matched']==10 and metrics['first_mismatch']==10
    assert np.isclose(metrics['growth_diff'],(0.4-0.1)-(0.2-0.1))


def test_labels_do_not_promote_episode_return():
    assert m.classify_primary(0.08,0.01,0.15,10,True,0.05)=='student_late_error_grows_faster'
    assert m.classify_primary(-0.08,-0.15,-0.01,10,True,0.05)=='zero_late_error_grows_faster'
    assert m.classify_primary(0.02,-0.01,0.05,10,True,0.05)=='late_error_growth_not_established'
    assert m.classify_primary(0.2,0.1,0.3,10,False,0.05)=='incomplete'
    assert m.PRIMARY=='growth_diff'


def test_scoring_excludes_returns_and_three_action_forks_are_off():
    names=set(inspect.signature(planner_scores).parameters)
    assert names.isdisjoint({'actual','returns','rewards','regret'})
    cfg=m.load_config();counts=m.budget(cfg)
    assert counts['episode']==12000 and counts['model_states']==3084000
    assert cfg['three_action_counterfactuals'] is False
    assert cfg['matched_state_first_action_forks'] is False
    assert int(cfg['episode_steps'])==PENDULUM_MAX_STEPS==200


def test_budget_seeds_one_run_authorization_and_parents_frozen():
    cfg=m.load_config();record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['authority_commit']=='2f81d4130a954cec67f22ce579c9115b228ffcdd'
    assert record['time_cap_s']==90 and record['training_authorized'] is False
    m.require_allocation(cfg)
    assert m.OUTPUT.exists() is False
    recede_cfg=yaml.safe_load(recede.CONFIG.read_text());same_cfg=yaml.safe_load(same.CONFIG.read_text())
    horizon_cfg=yaml.safe_load(horizon.CONFIG.read_text());dawm_cfg=yaml.safe_load(dawm.CONFIG.read_text())
    blocked=set().union(*acq.seed_groups(yaml.safe_load(acq.CONFIG.read_text())),*recede.seed_groups(recede_cfg),
                         *same.seed_groups(same_cfg),*horizon.seed_groups(horizon_cfg),*dawm.seed_groups(dawm_cfg))
    used=set().union(*m.seed_groups(cfg))
    assert not (used & blocked) and min(used)>=11000000
    confirm={s.task_id for s in pendulum_context_confirmation()}
    assert set(cfg['eval_task_ids']).isdisjoint(confirm)
    assert cfg['eval_task_ids']==[s.task_id for s in pendulum_context_development()]
    assert dawm.load_allocation()['authorized'] is False
    assert sha('artifacts/research_session_first_action_value_usage.json')=='c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462'


def test_offline_audit_zero_new_steps():
    report=m.offline_audit()
    assert report['new_environment_steps']==0 and report['new_imagined_transitions']==0
    assert report['three_action_forks'] is False
    assert report['confirmation_used'] is False
    assert Path('docs/NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_AUDIT.md').is_file()
    assert Path('docs/NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_PROTOCOL.md').is_file()
