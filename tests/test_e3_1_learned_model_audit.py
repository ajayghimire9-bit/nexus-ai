"""Source-only arithmetic/boundary tests: no model loading or environments."""
import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('e3audit',ROOT/'scripts/audit_e3_1_learned_model.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)


def fixture():
    c=a.config();capture=json.loads((ROOT/'artifacts/unified_crossed_reset.json').read_text())
    rows,slices=a.recorded_rows(c,capture)
    target=np.asarray([r['next_obs'] for r in rows])
    pred={'0':dict(next_obs=(target+np.array([0.,0.,1.])).tolist(),termination_probability=[.1]*3200),
          '1':dict(next_obs=target.tolist(),termination_probability=[.2]*3200)}
    return c,rows,slices,pred


def test_identical_canonical_queries_and_known_error():
    c,rows,slices,pred=fixture()
    assert len(rows)==3200 and len(slices)==16
    cells=a.metric_cells(c,rows,slices,pred);summary=a.summarize(c,cells)
    assert len(cells)==32
    assert summary['model0_minus_model1']['angular_velocity_mae']==pytest.approx(1.)
    assert summary['means']['0']['mae']==pytest.approx(1/3)
    assert summary['means']['0']['rmse']==pytest.approx(1/np.sqrt(3))
    assert summary['model0_minus_model1']['termination_brier']==pytest.approx(-.03)
    assert not summary['causal_explanation_established'] and not summary['learning_to_learn_established']


def test_truncation_is_not_positive_termination():
    c,rows,slices,pred=fixture()
    assert sum(r['truncated'] for r in rows)==16
    assert sum(r['terminated'] for r in rows)==0
    assert all(x['positive_terminations']==0 for x in a.metric_cells(c,rows,slices,pred))


@pytest.mark.parametrize('change',['model','visitor','policy','episode','duplicate','nan','bool','missing_metric','slice'])
def test_full_metric_schema_fails_closed(change):
    c,rows,slices,pred=fixture();cells=a.metric_cells(c,rows,slices,pred)
    if change=='model':cells=[r for r in cells if r['candidate_model']!=1]
    if change=='visitor':cells=[r for r in cells if r['visitor_model']!=1]
    if change=='policy':cells=[r for r in cells if r['visitor_policy']!='rank_blend']
    if change=='episode':cells=[r for r in cells if r['episode']!=3]
    if change=='duplicate':cells[-1]=copy.deepcopy(cells[0])
    if change=='nan':cells[0]['angular_velocity_mae']=float('nan')
    if change=='bool':cells[0]['mae']=True
    if change=='missing_metric':cells[0].pop('rmse')
    if change=='slice':cells[0]['start']+=200;cells[0]['stop']+=200
    with pytest.raises((ValueError,KeyError)):a.summarize(c,cells)


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-.01,1.01])
def test_invalid_probability_rejected(bad):
    with pytest.raises(ValueError):a.metrics(np.zeros((1,3)),np.array([bad]),np.zeros((1,3)),np.array([False]))


def test_missing_prediction_model_and_wrong_target_type_rejected():
    c,rows,slices,pred=fixture();pred.pop('1')
    with pytest.raises(ValueError):a.metric_cells(c,rows,slices,pred)
    with pytest.raises(ValueError):a.metrics(np.zeros((1,3)),np.zeros(1),np.zeros((1,3)),np.zeros(1))


def test_evidence_config_must_not_drop_a_closed_study():
    c=a.config();c['evidence_sha256'].pop('artifacts/unified_headroom_audit.json')
    with pytest.raises(ValueError):a.validate_config(c)
    c=a.config();c['real_interaction_cap']=True
    with pytest.raises(ValueError):a.validate_config(c)


def test_checkpoint_hash_guard_uses_bytes_not_a_flag(tmp_path):
    path=tmp_path/'frozen';path.write_bytes(b'original')
    expected=a.h.sha(path);a.h.verify_file(path,expected)
    path.write_bytes(b'altered')
    with pytest.raises(ValueError):a.h.verify_file(path,expected)


def test_source_runner_has_no_environment_or_optimizer_call():
    import ast
    tree=ast.parse((ROOT/'scripts/audit_e3_1_learned_model.py').read_text())
    names={getattr(n.func,'attr',getattr(n.func,'id','')) for n in ast.walk(tree) if isinstance(n,ast.Call)}
    assert not names&{'make_task_env','gym.make','Adam','SGD','backward','train_world_model'}


def test_query_fingerprint_includes_outcomes_flags_and_input_types():
    _,rows,_,_=fixture();arrays=a.query_arrays(rows);before=a.query_hash(arrays)
    changed=copy.deepcopy(rows);changed[0]['next_obs'][0]+=.01
    after=a.query_arrays(changed)
    assert np.array_equal(arrays['obs'],after['obs']) and np.array_equal(arrays['action'],after['action'])
    assert a.query_hash(after)!=before
    arrays['truncated'][0]=not arrays['truncated'][0]
    assert a.query_hash(arrays)!=before


def test_allocation_bound_to_protocol_and_zero_collection():
    allocation=json.loads(a.ALLOCATION.read_text())
    assert allocation['config_sha256']==a.h.sha(a.CONFIG)
    assert allocation['protocol_sha256']==a.h.sha(a.PROTOCOL)
    assert allocation['real_interaction_cap']==0 and allocation['neural_row_cap']==6400
    assert allocation['session_used_before_s']==487.3923076680088
