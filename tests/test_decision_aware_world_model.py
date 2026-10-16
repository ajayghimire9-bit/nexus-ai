"""Decision-aware locks. These tests do not collect the registered grid."""
from __future__ import annotations
import inspect
import json
from pathlib import Path
import numpy as np
import pytest
import yaml
from nexus.tasks.pendulum_family import pendulum_context_confirmation, pendulum_context_development
from nexus.world import decision_aware_world_model as m
from nexus.world import horizon_alignment as horizon
from nexus.world import same_set_planning as same
from nexus.world import receding_policy_consistency as recede
from nexus.world import action_conditioned_q as acq
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import planner_scores, candidate_sequences


def test_near_best_split_and_contrast_identity():
    actual=np.array([-1.0]+[-10.0]*15)
    scores=np.array([-2.0]+[-10.0]*15)
    mask=m.near_best_mask(actual,1.0)
    assert int(mask.sum())==1 and int((~mask).sum())==15
    row=m.score_error_contrast(scores,actual,1.0)
    assert row['n_near']==1 and row['n_dominated']==15
    assert np.isclose(row['near_mae'],1.0) and np.isclose(row['dominated_mae'],0.0)
    assert np.isclose(row['contrast'],1.0)
    with pytest.raises(ValueError,match='split empty'):
        m.score_error_contrast(np.zeros(16),np.zeros(16),1.0)


def test_paired_decoder_aggregation_not_student_replication():
    rows=[]
    for d in range(10):
        for t in range(3):
            metrics={k:float(d)+0.01*t for k in m.FIELDS}
            metrics['episode_student']=-500.0-d;metrics['episode_zero']=-520.0-d
            metrics['episode_gain']=metrics['episode_student']-metrics['episode_zero']
            rows.append(dict(decoder=d,task=t,metrics=metrics,n_near=1,n_dominated=15,
                             n_steps_student=200,n_steps_zero=200))
    cfg=dict(practical_margin=1.0)
    summary=m.summarize(rows,cfg)
    assert summary['groups']['student_contrast']['interval']['n']==10
    assert len(summary['groups']['student_contrast']['per_decoder'])==10


def test_labels_do_not_promote_episode_return():
    assert m.classify_primary(1.2,0.1,2.0,10,True,1.0)=='decision_relevant_error_concentrated'
    assert m.classify_primary(-1.2,-2.0,-0.1,10,True,1.0)=='ordinary_error_larger'
    assert m.classify_primary(0.5,-0.2,1.2,10,True,1.0)=='decision_relevant_error_not_established'
    assert m.classify_primary(2.0,1.5,2.5,9,True,1.0)=='incomplete'
    assert m.classify_primary(2.0,1.5,2.5,10,False,1.0)=='incomplete'
    assert m.PRIMARY=='student_contrast'


def test_scoring_api_cannot_take_simulator_returns():
    assert m.scores_exclude_returns()
    names=set(inspect.signature(planner_scores).parameters)
    assert names.isdisjoint({'actual','returns','rewards','regret','prefix'})


def test_first_action_regret_uses_measured_set_only():
    seq=np.zeros((16,16),dtype=np.int64);seq[0,0]=1;seq[1,0]=2
    actual=np.arange(16,dtype=np.float64)
    scores=np.zeros(16);scores[0]=10.0
    row=m.first_action_regret(scores,actual,seq)
    assert row['chosen']==1 and row['n_actions']==3
    assert np.isclose(row['regret'],float(actual.max()-actual[0]))


def test_budget_seeds_unauthorized_collection_and_parents_frozen():
    cfg=m.load_config();counts=m.budget(cfg)
    assert counts['prefix']+counts['episode']==19680
    assert counts['model_states']==3164160
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    assert record['time_cap_s']==90 and record['env_cap']==19680 and record['model_cap']==3164160
    assert record['training_authorized'] is False
    assert record['previous_exhausted_session_sha256']=='c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462'
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.require_allocation(cfg)
    assert m.OUTPUT.exists() is False
    recede_cfg=yaml.safe_load(recede.CONFIG.read_text());same_cfg=yaml.safe_load(same.CONFIG.read_text())
    horizon_cfg=yaml.safe_load(horizon.CONFIG.read_text())
    blocked=set().union(*acq.seed_groups(yaml.safe_load(acq.CONFIG.read_text())),*recede.seed_groups(recede_cfg),
                         *same.seed_groups(same_cfg),*horizon.seed_groups(horizon_cfg))
    used=set().union(*m.seed_groups(cfg))
    assert not (used & blocked) and min(used)>=10000000
    confirm={s.task_id for s in pendulum_context_confirmation()}
    assert set(cfg['eval_task_ids']).isdisjoint(confirm)
    assert cfg['eval_task_ids']==[s.task_id for s in pendulum_context_development()]
    exhausted=json.loads(Path('artifacts/research_session_first_action_value_usage.json').read_text())
    assert sha('artifacts/research_session_first_action_value_usage.json')==record['previous_exhausted_session_sha256']
    assert float(exhausted['remaining_session_allowance_s'])<90


def test_offline_source_audit_zero_new_steps_and_no_leakage_into_scores():
    report=m.offline_audit()
    assert report['new_environment_steps']==0 and report['new_imagined_transitions']==0
    assert report['authorized'] is False and report['h1_established_on_source'] is False
    assert report['decision_aware_training_justified'] is False
    assert report['confirmation_used'] is False
    source=report['source_planning_value']
    assert source['n_cells']==80 and source['retuned'] is False and source['causal'] is False
    ci=source['student_contrast']['interval']
    assert ci['n']==10 and ci['lo']<0<ci['hi']
    assert source['student_rank16']['interval']['mean']>0.8
    assert report['source_first_action']['has_model_scores'] is False
    assert report['prediction_control_gap']['per_candidate_arrays_stored'] is False
    assert any(row['path']=='artifacts/planning_value.json' for row in report['inventory'])
    seq=candidate_sequences(0,16,16)
    assert seq.shape==(16,16)


def test_cell_metrics_average_students_inside_decoder_task():
    seq=candidate_sequences(3,16,16)
    actual=np.linspace(-20.0,-1.0,16)
    scores={str(s):actual.copy() for s in range(5)};scores['zero']=actual.copy()
    scores['0'][0]-=2.0
    angvel={k:np.zeros(16) for k in m.NAMES}
    metrics=m.cell_metrics(scores,actual,seq,angvel,-500.0,-520.0,1.0)
    assert metrics['episode_gain']==20.0
    assert metrics['student_contrast']!=metrics['zero_contrast']
    assert set(metrics)==set(m.FIELDS)
