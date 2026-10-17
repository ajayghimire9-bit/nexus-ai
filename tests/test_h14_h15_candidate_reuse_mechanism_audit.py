"""Source-only H14/H15 mechanism-audit tests. No MountainCar env."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pytest
from nexus.world.planning_value import sha
from nexus.world import h14_candidate_reuse as h14
from nexus.world import h15_candidate_reuse_confirm as h15
from nexus.world import h14_h15_candidate_reuse_mechanism_audit as m


def test_raw_hashes_and_registered_primaries_rebuild():
    assert sha(m.H14_RAW) == m.H14_RAW_SHA
    assert sha(m.H15_RAW) == m.H15_RAW_SHA
    report = m.audit()
    assert report['new_environment_steps'] == 0
    assert report['new_imagined_transitions'] == 0
    assert report['trained'] is False
    h14r = report['h14']
    h15r = report['h15']
    assert h14r['label'] == 'h14_fixed_library_helps_multitask_relative'
    assert h15r['label'] == 'h15_fixed_library_helps_multitask_relative'
    assert h14r['n_positive'] == 6
    assert h15r['n_positive'] == 10
    saved14 = m.load_artifact(m.H14_RAW)['groups']['primary']['interval']
    saved15 = m.load_artifact(m.H15_RAW)['groups']['primary']['interval']
    assert abs(h14r['interval']['mean'] - saved14['mean']) < 1e-12
    assert abs(h15r['interval']['mean'] - saved15['mean']) < 1e-12
    assert h14r['interval']['df'] == h15r['interval']['df'] == 9
    assert h14r['counts']['env_steps'] == h15r['counts']['env_steps'] == 29760


def test_step_rewards_and_candidate_seeds_match_saved_cells():
    report = m.audit()
    assert report['h14']['t0_action_match'] == {'multitask': 1.0, 'scratch': 1.0}
    assert report['h15']['t0_action_match'] == {'multitask': 1.0, 'scratch': 1.0}
    payload = m.load_artifact(m.H15_RAW)
    state = payload['cells'][0]['states'][1]
    rebuilt = m.reward_sum(state, 'multitask', 'fixed')
    assert rebuilt == pytest.approx(state['returns']['multitask']['fixed'])
    seed = payload['cells'][0]['seed']
    cfg = h15.load_config()
    row = m.traces(state, 'multitask', 'fixed')[0]
    assert row['candidate_seed'] == h14.shared_library_seed(cfg['library_base'], seed, state['state_index'])
    later = m.traces(state, 'multitask', 'redraw')[3]
    assert later['candidate_seed'] == h14.redraw_step_seed(cfg['redraw_base'], seed, state['state_index'], 3)


def test_aliasing_and_action_divergence_grouping():
    h14_alias = m.alias_map(h14.load_config()['redraw_base'])
    h15_alias = m.alias_map(h15.load_config()['redraw_base'])
    assert h14_alias == h15_alias == dict(
        intended=600, unique=450, aliased=150, colliding_groups=150, within_state_unique=True)
    report = m.audit()
    assert report['h14']['first_divergence_never']['multitask'] == 0
    assert report['h15']['first_divergence_never']['multitask'] == 0
    assert report['h14']['action_disagreement_by_step']['multitask'][0] == 0.0
    assert report['h15']['action_disagreement_by_step']['scratch'][0] == 0.0
    assert m.first_divergence(
        [{'executed_action': 1}] * 16, [{'executed_action': 1}] * 16) is None
    assert m.first_divergence(
        [{'executed_action': 1}, {'executed_action': 2}],
        [{'executed_action': 1}, {'executed_action': 0}]) == 1


def test_missing_fields_nonfinite_and_incomplete_fail_closed():
    payload = m.load_artifact(m.H14_RAW)
    bad = json_clone(payload)
    del bad['cells'][0]['states'][0]['controllers']['scratch']
    with pytest.raises((KeyError, ValueError)):
        m.validate_cells(bad)
    short = json_clone(payload)
    short['cells'][0]['states'][0]['controllers']['multitask']['fixed']['traces'] = (
        short['cells'][0]['states'][0]['controllers']['multitask']['fixed']['traces'][:8])
    with pytest.raises(ValueError, match='incomplete controller'):
        m.validate_cells(short)
    nan = json_clone(payload)
    nan['cells'][0]['states'][0]['controllers']['multitask']['fixed']['traces'][3]['realized_reward'] = float('nan')
    with pytest.raises(ValueError, match='nonfinite'):
        m.validate_cells(nan)
    assert m.EVIDENCE['unchosen_later_realized_returns'] == 'missing'
    assert m.EVIDENCE['full_predicted_next_state'] == 'missing'
    assert m.EVIDENCE['model_checkpoints'] == 'missing'
    assert m.EVIDENCE['chosen_one_step_residual'] == 'available'


def test_audit_module_has_no_collection_or_training_calls():
    src = Path(m.__file__).read_text(encoding='utf-8')
    assert 'from nexus.world.data import collect_transitions' not in src
    assert 'from nexus.tasks.spec import make_task_env' not in src
    assert 'from nexus.world.train import train_world_model' not in src
    assert 'gymnasium' not in src
    scores = np.arange(16, dtype=np.float64)
    assert m.spearman(scores, scores) == pytest.approx(1.0)
    assert m.spearman(scores, -scores) == pytest.approx(-1.0)


def json_clone(payload):
    import json
    return json.loads(json.dumps(payload))
