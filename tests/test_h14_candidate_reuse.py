"""Source-only H14 candidate-reuse design tests. No MountainCar env."""
from __future__ import annotations
import inspect
from pathlib import Path
import numpy as np
import pytest
from nexus.world import h14_candidate_reuse as m
from nexus.world import xenv_transfer as rung1
from nexus.world.h12_h13_recede_disagreement_audit import _spearman


class ToyScorer:
    def __init__(self, scores):
        self.scores = np.asarray(scores, dtype=np.float64)
        self.seen = []

    def score(self, obs, sequences):
        self.seen.append((np.asarray(obs).copy(), np.asarray(sequences).copy()))
        return self.scores


def test_first_library_is_shared_across_modes_and_has_no_arm_term():
    lib = 76000000
    redraw = 76100000
    a = m.recede_candidates('fixed', lib, redraw, 0, 1, 0)
    b = m.recede_candidates('redraw', lib, redraw, 0, 1, 0)
    assert np.array_equal(a, b)
    assert np.array_equal(a, m.assert_shared_first_library(lib, 0, 1))
    assert 'arm' not in inspect.signature(m.recede_candidates).parameters
    assert 'actual' not in inspect.signature(m.score_library).parameters
    assert 'realized' not in inspect.signature(m.score_library).parameters


def test_fixed_reuses_library_and_redraw_changes_after_step_zero():
    lib = 76000000
    redraw = 76100000
    first = m.recede_candidates('fixed', lib, redraw, 2, 3, 0)
    for step in range(1, 16):
        assert np.array_equal(m.recede_candidates('fixed', lib, redraw, 2, 3, step), first)
        fresh = m.recede_candidates('redraw', lib, redraw, 2, 3, step)
        assert not np.array_equal(fresh, first)
        other_state = m.recede_candidates('redraw', lib, redraw, 2, 2, step)
        assert not np.array_equal(fresh, other_state)
    with pytest.raises(ValueError, match='step 0'):
        m.redraw_step_seed(redraw, 0, 0, 0)


def test_ties_use_first_index_and_did_sign():
    seq = np.zeros((16, 16), dtype=np.int64)
    seq[0, 0] = 2
    seq[1, 0] = 0
    scores = np.zeros(16)
    scores[0] = 1.0
    scores[1] = 1.0
    idx, action = m.selected_first_action(seq, scores)
    assert idx == 0 and action == 2
    means = {('multitask', 'fixed'): 1.0, ('scratch', 'fixed'): 0.0,
             ('multitask', 'redraw'): 0.0, ('scratch', 'redraw'): 1.0}
    assert m.difference_in_differences(means) == 2.0
    assert m.classify_primary(0.2, 0.1, 0.3, 10) == 'h14_fixed_library_helps_multitask_relative'
    assert m.classify_primary(-0.2, -0.3, -0.1, 10) == 'h14_redraw_helps_multitask_relative'
    assert m.classify_primary(0.2, -0.1, 0.3, 10) == 'h14_resampling_effect_not_established'
    assert m.classify_primary(0.2, 0.1, 0.3, 9) == 'incomplete'


def test_missing_duplicate_and_nonfinite_cells():
    good = [dict(state_index=k, returns={'multitask': {'fixed': 1.0, 'redraw': 0.0},
                                         'scratch': {'fixed': 0.0, 'redraw': 0.5}})
            for k in range(4)]
    cells = [dict(seed=s, states=good) for s in range(10)]
    out = m.summarize(cells)
    assert out['label'] == 'h14_fixed_library_helps_multitask_relative'
    with pytest.raises(ValueError, match='incomplete or duplicated seed grid'):
        m.summarize(cells + [cells[0]])
    with pytest.raises(ValueError, match='incomplete or duplicated seed grid'):
        m.summarize(cells[:9])
    bad_state = list(good)
    bad_state[3] = dict(good[3], state_index=0)
    with pytest.raises(ValueError, match='state'):
        m.mean_seed_returns(bad_state)
    nan_state = list(good)
    nan_state[0] = dict(good[0], returns={'multitask': {'fixed': float('nan'), 'redraw': 0.0},
                                          'scratch': {'fixed': 0.0, 'redraw': 0.0}})
    with pytest.raises(ValueError, match='nonfinite'):
        m.mean_seed_returns(nan_state)


def test_meters_cannot_exceed_caps_and_planning_is_blind():
    meter = rung1.Meter(dict(time_cap_s=30, env_cap=1, model_cap=1))
    meter.env_step()
    with pytest.raises(RuntimeError, match='env-step cap reached'):
        meter.env_step()
    class OneStep:
        def step(self, obs, action):
            return np.zeros_like(obs), 0.0
    model = OneStep()
    imagined = rung1.Meter(dict(time_cap_s=30, env_cap=10, model_cap=1))
    imagined.instrument(model)
    model.step(np.zeros(2), 0)
    with pytest.raises(RuntimeError, match='imagined cap reached'):
        model.step(np.zeros(2), 0)
    scorer = ToyScorer(np.arange(16, dtype=np.float64))
    seq = m.recede_candidates('fixed', 76000000, 76100000, 0, 0, 0)
    scores = m.score_library(scorer, np.array([0.1, 0.0]), seq)
    assert scores.shape == (16,)
    assert len(scorer.seen) == 1


def test_budget_formulas_and_historical_audit_holes():
    counts = m.budget(include_shared_open_loop=True, share_step0_scores=False)
    assert counts['source_collection'] + counts['target_pool'] == 16960
    assert counts['recede_control'] == 2560
    assert counts['shared_open_loop'] == 10240
    assert counts['env_total'] == 29760
    assert counts['imagined_total'] == 655360
    shared = m.budget(include_shared_open_loop=True, share_step0_scores=True)
    assert shared['imagined_total'] == 634880
    assert m.budget(include_shared_open_loop=False)['env_total'] == 19520
    tied = np.array([1.0, 1.0, 0.0])
    assert _spearman(tied, np.array([10.0, 0.0, 5.0])) != _spearman(tied, np.array([0.0, 10.0, 5.0]))
    src = Path(m.__file__).read_text(encoding='utf-8')
    assert 'collect_transitions' not in src
    assert 'make_task_env' not in src
    assert 'train_world_model' not in src


def test_holdout_rule_is_deterministic_and_excludes_closed_physics():
    first = m.holdout_from_rule()
    second = m.holdout_from_rule()
    assert first == second == [m.LOCKED_TARGET]
    occupied = m.occupied_physics()
    assert m.LOCKED_TARGET not in occupied
    for closed in (m.CLOSED_H10, m.CLOSED_H11, m.CLOSED_H12, m.CLOSED_H13):
        assert closed in occupied
        assert closed != m.LOCKED_TARGET
    for source in m.source_physics_keys():
        assert source in occupied
    assert m.HOLD_RULE == 'mcc_candidate_reuse_v1'


def test_seed_streams_are_disjoint_and_shared_at_step_zero():
    cfg = m.load_config()
    streams, used = m.seed_streams(cfg)
    names = list(streams)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            assert not (streams[left] & streams[right])
    assert min(used) >= cfg['reset_base']
    lib = cfg['library_base']
    redraw = cfg['redraw_base']
    for seed in range(2):
        for state in range(4):
            shared = m.assert_shared_first_library(lib, seed, state)
            mt = m.assert_arm_symmetric_library('fixed', lib, redraw, seed, state, 3)
            sc = m.assert_arm_symmetric_library('redraw', lib, redraw, seed, state, 3)
            assert np.array_equal(m.recede_candidates('fixed', lib, redraw, seed, state, 0), shared)
            assert not np.array_equal(sc, shared)
            assert mt.shape == (16, 16)


def test_did_zero_boundary_and_incomplete_classification():
    assert m.classify_primary(0.0, -0.1, 0.1, 10) == 'h14_resampling_effect_not_established'
    assert m.classify_primary(0.1, 0.0, 0.2, 10) == 'h14_resampling_effect_not_established'
    assert m.classify_primary(-0.1, -0.2, 0.0, 10) == 'h14_resampling_effect_not_established'
    assert m.classify_primary(0.2, 0.1, 0.3, 10, complete=False) == 'incomplete'
    assert m.classify_primary(float('nan'), 0.1, 0.3, 10) == 'incomplete'
    means = {('multitask', 'fixed'): 1.0, ('scratch', 'fixed'): 1.0,
             ('multitask', 'redraw'): 2.0, ('scratch', 'redraw'): 2.0}
    assert m.difference_in_differences(means) == 0.0


def test_reset_identity_and_mandatory_trace_schema():
    obs = np.array([0.1, 0.0], dtype=np.float32)
    assert np.allclose(m.check_reset_identity(obs, obs.copy()), obs)
    with pytest.raises(RuntimeError, match='reset identity'):
        m.check_reset_identity(obs, np.array([0.2, 0.0], dtype=np.float32))
    seq = m.recede_candidates('fixed', 76200000, 76500000, 0, 0, 0)
    scores = np.arange(16, dtype=np.float64)
    idx, action = m.selected_first_action(seq, scores)
    row = m.controller_trace(
        seed=0, state_index=0, mode='fixed', arm='multitask', state_seed=76100000,
        reset_observation=obs.tolist(), step=0, candidate_seed=76200000,
        library_fingerprint=m.library_fingerprint(seq), observation=obs.tolist(),
        predicted_scores=scores, selected_index=idx, executed_action=action,
        next_observation=[0.11, 0.01], realized_reward=-0.1, terminated=False,
        truncated=False, env_steps=1, imagined_transitions=256)
    assert set(row) == set(m.TRACE_FIELDS)
    with pytest.raises(ValueError, match='missing trace'):
        m.controller_trace(seed=0)
    residual = m.one_step_residual([0.2, 0.0], [0.1, 0.0])
    assert residual[0] == pytest.approx(0.1)


def test_preflight_meter_rejects_before_simulator_or_inference():
    meter = m.PreflightMeter(dict(time_cap_s=30, env_cap=1, model_cap=2))
    meter.reserve_env(1)
    with pytest.raises(RuntimeError, match='env-step cap would be exceeded'):
        meter.reserve_env(1)
    with pytest.raises(ValueError, match='positive'):
        meter.reserve_imagined(0)
    class ToyStep:
        def __init__(self):
            self.calls = 0

        def step(self, obs, action):
            self.calls += 1
            return np.zeros_like(obs), 0.0
    model = ToyStep()
    meter.instrument(model)
    model.step(np.zeros((2, 2)), 0)
    assert model.calls == 1
    with pytest.raises(RuntimeError, match='imagined cap would be exceeded'):
        model.step(np.zeros(2), 0)
    assert model.calls == 1


def test_locked_prep_refuses_execution_and_stays_unauthorized():
    cfg = m.load_config()
    assert tuple(cfg['target_physics'][0]) == m.LOCKED_TARGET
    report = m.prep()
    assert report['authorized'] is False
    assert report['runs'] == 0
    assert report['new_environment_steps'] == 0
    assert report['new_imagined_transitions'] == 0
    assert report['locked'] is True
    with pytest.raises(PermissionError, match='fresh human approval'):
        m.execute()
    allocation = m.load_allocation()
    assert allocation['authorized'] is False
    assert allocation['runs'] == 0
