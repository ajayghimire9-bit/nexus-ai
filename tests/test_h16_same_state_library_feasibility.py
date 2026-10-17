"""Source-only H16 same-state library feasibility tests. No MountainCar env."""
from __future__ import annotations
import inspect
from pathlib import Path
import numpy as np
import pytest
from nexus.world import h16_same_state_library_feasibility as m


def test_parent_hashes_and_no_holdout_selection():
    m.assert_parent_hashes()
    report = m.feasibility_report()
    assert report['authorized'] is False
    assert report['locked'] is False
    assert report['trained'] is False
    assert report['new_environment_steps'] == 0
    assert report['new_imagined_transitions'] == 0
    assert report['holdout_physics_selected'] is False
    assert report['protocol_ready_to_lock'] is False
    assert [0.0023, 0.0019, 0.065] in report['closed_mcc_physics']
    assert [0.004, 0.0021, 0.05] in report['closed_mcc_physics']
    src = Path(m.__file__).read_text(encoding='utf-8')
    assert 'from nexus.tasks.spec import make_task_env' not in src
    assert 'from nexus.world.data import collect_transitions' not in src
    assert 'import gymnasium' not in src
    assert 'from nexus.world.train import train_world_model' not in src


def test_shared_common_state_and_reset_plus_prefix():
    prefix = m.prefix_actions(1, 0, 0, 8)
    first = m.reconstruct_later_state(m.MockLaterEnv(), 11, prefix)
    second = m.reconstruct_later_state(m.MockLaterEnv(), 11, prefix)
    m.assert_same_later_state(first, second)
    other = m.reconstruct_later_state(m.MockLaterEnv(), 12, prefix)
    with pytest.raises(RuntimeError, match='later observation'):
        m.assert_same_later_state(first, other)


def test_library_identity_and_candidate_returns():
    l0_id, l0 = m.library_for('l0', 100, 200, 1, 2, 8)
    l0_again, l0_b = m.library_for('l0', 100, 200, 1, 2, 12)
    assert l0_id == l0_again == m.l0_seed(100, 1, 2)
    assert np.array_equal(l0, l0_b)
    red8_id, red8 = m.library_for('redraw', 100, 200, 1, 2, 8)
    red12_id, red12 = m.library_for('redraw', 100, 200, 1, 2, 12)
    assert red8_id != red12_id
    assert not np.array_equal(red8, red12)
    assert not np.array_equal(l0, red8)
    assert m.library_fingerprint(l0) != m.library_fingerprint(red8)
    assert m.redraw_unique() == dict(intended=80, unique=80, colliding_groups=0)
    env = m.MockLaterEnv()
    start, values = m.realize_candidates(env, 3, m.prefix_actions(1, 0, 1, 8), l0)
    assert start['obs'].shape == (2,)
    assert values.shape == (16,)
    assert np.isfinite(values).all()
    again = m.realize_candidates(m.MockLaterEnv(), 3, m.prefix_actions(1, 0, 1, 8), l0)[1]
    assert np.allclose(values, again)


def test_oracle_regret_and_primary_algebra():
    realized = np.linspace(-2.0, -0.5, 16)
    scores_mt = realized.copy()
    scores_sc = -realized
    assert m.oracle_return(realized) == pytest.approx(-0.5)
    assert m.selected_return(realized, scores_mt) == pytest.approx(-0.5)
    assert m.within_library_regret(realized, scores_mt) == pytest.approx(0.0)
    assert m.within_library_regret(realized, scores_sc) == pytest.approx(1.5)
    gap = m.oracle_cancels_in_arm_gap(realized, scores_mt, scores_sc)
    shifted = realized + 4.0
    assert m.oracle_cancels_in_arm_gap(shifted, scores_mt, scores_sc) == pytest.approx(gap)
    assert m.same_state_did(-1.0, -1.4, -1.5, -1.3) == pytest.approx(0.6)
    seq = np.zeros((16, 16), dtype=np.int64)
    seq[:, 0] = 2
    seq[15, 0] = 0
    scores = np.zeros(16)
    scores[0] = 1.0
    assert m.first_action_regret(seq, realized, scores) == pytest.approx(
        m.oracle_return(realized) - float(realized[:15].max()))
    assert 'realized' not in inspect.signature(m.score_library).parameters


def test_missing_duplicate_nonfinite_and_early_stop():
    cells = m.synthetic_complete_grid()
    out = m.mean_seed_cells(cells)
    assert out['interval']['n'] == 10
    assert out['interval']['df'] == 9
    assert out['label'] == 'h16_l0_helps_multitask_relative_same_state'
    with pytest.raises(ValueError, match='incomplete or duplicated seed'):
        m.mean_seed_cells(cells + [cells[0]])
    with pytest.raises(ValueError, match='incomplete or duplicated seed'):
        m.mean_seed_cells(cells[:9])
    bad = list(cells)
    bad[0] = dict(cells[0], later_states=cells[0]['later_states'][:-1])
    with pytest.raises(ValueError, match='later-state'):
        m.mean_seed_cells(bad)
    nan = list(cells)
    row = dict(cells[0]['later_states'][0], s_mt_l0=float('nan'))
    nan[0] = dict(cells[0], later_states=[row] + cells[0]['later_states'][1:])
    with pytest.raises(ValueError, match='nonfinite'):
        m.mean_seed_cells(nan)
    with pytest.raises(RuntimeError, match='prefix ended'):
        m.reconstruct_later_state(m.MockLaterEnv(terminate_after=3), 1, [0] * 8)
    with pytest.raises(RuntimeError, match='candidate ended'):
        m.realize_candidates(m.MockLaterEnv(terminate_after=10), 1, [0] * 8,
                             np.zeros((16, 16), dtype=np.int64))
    assert m.classify_primary(0.2, -0.1, 0.3, 10) == 'h16_same_state_library_effect_not_established'
    assert m.classify_primary(0.2, 0.1, 0.3, 9) == 'incomplete'


def test_hard_budget_and_exact_cost_accounting():
    counts = m.assert_budget_fits_ceiling()
    assert counts['source_collection'] == 15360
    assert counts['target_pool'] == 1600
    assert counts['reference_prefix'] == 480
    assert counts['prefix_replay'] == 25600
    assert counts['shared_candidate_realizations'] == 40960
    assert counts['env_total'] == 84000
    assert counts['imagined_total'] == 81920
    assert counts['margin_to_ceiling'] == 16000
    meter = m.HardBudget(env_cap=8, imagined_cap=4)
    env = m.MockLaterEnv()
    m.reconstruct_later_state(env, 1, [0, 1], meter=meter)
    with pytest.raises(RuntimeError, match='env-step cap'):
        m.reconstruct_later_state(m.MockLaterEnv(), 1, [0] * 8, meter=meter)
    meter.reserve_imagined(4)
    with pytest.raises(RuntimeError, match='imagined cap'):
        meter.reserve_imagined(1)
    class Toy:
        def score(self, obs, sequences):
            return np.arange(16, dtype=np.float64)
    scores = m.score_library(Toy(), np.zeros(2), np.zeros((16, 16), dtype=np.int64))
    assert scores.shape == (16,)
