"""Source-only H16 same-state library lock tests. No MountainCar env."""
from __future__ import annotations
import hashlib
import inspect
from pathlib import Path
import numpy as np
import pytest
import yaml
from nexus.world import h14_candidate_reuse as h14
from nexus.world import h15_candidate_reuse_confirm as h15
from nexus.world import h16_same_state_library as m
from nexus.world import h16_same_state_library_feasibility as feas


def test_holdout_rule_is_deterministic_and_excludes_history():
    first = m.holdout_from_rule()
    second = m.holdout_from_rule()
    assert first == second == [m.LOCKED_TARGET] == [(0.0015, 0.0014, 0.055)]
    occupied = m.occupied_physics()
    assert m.LOCKED_TARGET not in occupied
    for closed in (h14.CLOSED_H10, h14.CLOSED_H11, h14.CLOSED_H12, h14.CLOSED_H13,
                   m.CLOSED_H14, m.CLOSED_H15):
        assert closed in occupied
        assert closed != m.LOCKED_TARGET
    for source in m.source_physics_keys():
        assert source in occupied
    digest = hashlib.sha256(f'{m.HOLD_RULE}:{m.HOLD_COUNTER}'.encode()).digest()
    idx = int.from_bytes(digest[:8], 'big')
    recomputed = (
        float(m.GRAVITIES[idx % len(m.GRAVITIES)]),
        float(m.POWERS[(idx // len(m.GRAVITIES)) % len(m.POWERS)]),
        float(m.SPEEDS[(idx // (len(m.GRAVITIES) * len(m.POWERS))) % len(m.SPEEDS)]),
    )
    assert recomputed == m.LOCKED_TARGET
    assert idx == m.HOLD_INDEX
    assert m.HOLD_RULE == 'mcc_same_state_library_v1'
    assert m.holdout_trace()['counter'] == 0


def test_seed_streams_are_disjoint_and_not_h14_alias():
    cfg = m.load_config()
    streams, used = m.seed_streams(cfg)
    names = list(streams)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            assert not (streams[left] & streams[right])
    h14_used = h14.seed_streams(yaml.safe_load(h14.CONFIG.read_text()))[1]
    h15_used = h15.seed_streams(yaml.safe_load(h15.CONFIG.read_text()))[1]
    assert used & h14_used == set()
    assert used & h15_used == set()
    assert min(used) >= 78_000_000
    assert max(h15_used) < 78_000_000
    assert len(streams['redraw']) == 80
    assert m.redraw_seed(cfg['redraw_base'], 0, 0, 12) != m.redraw_seed(
        cfg['redraw_base'], 0, 1, 8)
    assert h14.redraw_step_seed(0, 0, 0, 11) == h14.redraw_step_seed(0, 0, 1, 1)
    l0_id, l0 = m.library_for('l0', cfg['library_base'], cfg['redraw_base'], 1, 2, 8)
    l0_b, l0_again = m.library_for('l0', cfg['library_base'], cfg['redraw_base'], 1, 2, 12)
    assert l0_id == l0_b and np.array_equal(l0, l0_again)
    red8 = m.library_for('redraw', cfg['library_base'], cfg['redraw_base'], 1, 2, 8)[1]
    red12 = m.library_for('redraw', cfg['library_base'], cfg['redraw_base'], 1, 2, 12)[1]
    assert not np.array_equal(l0, red8)
    assert not np.array_equal(red8, red12)
    first = m.prefix_actions(cfg['prefix_base'], 3, 1, 12)
    assert np.array_equal(first, m.prefix_actions(cfg['prefix_base'], 3, 1, 12))
    assert not np.array_equal(first, m.prefix_actions(cfg['prefix_base'], 3, 2, 12))


def test_prefix_reconstruction_and_wrapper_contract():
    ref = dict(prefix_actions=[2, 1, 0, 2, 1, 0, 2, 1],
               reset_obs=np.array([0.1, 0.0], dtype=np.float32),
               reset_state=np.array([0.1, 0.0], dtype=np.float32),
               later_obs=np.array([0.2, 0.01], dtype=np.float32),
               later_state=np.array([0.2, 0.01], dtype=np.float32),
               prefix_rewards=[-0.1] * 8, terminated=False, truncated=False,
               elapsed_steps=8, later_t=8)
    assert m.assert_replay_identity(ref, dict(ref))
    bad = dict(ref, later_obs=np.array([0.3, 0.01], dtype=np.float32))
    with pytest.raises(RuntimeError, match='later_obs'):
        m.assert_replay_identity(ref, bad)
    wrong_prefix = dict(ref, prefix_actions=[0] * 8)
    with pytest.raises(RuntimeError, match='prefix action'):
        m.assert_replay_identity(ref, wrong_prefix)
    raw = dict(ref, later_state=np.array([0.2, 0.02], dtype=np.float32))
    with pytest.raises(RuntimeError, match='later_state'):
        m.assert_replay_identity(ref, raw)
    assert m.wrapper_stack_ok(m.REQUIRED_WRAPPERS)
    assert not m.wrapper_stack_ok(m.REQUIRED_WRAPPERS + m.FORBIDDEN_WRAPPERS)
    assert not m.wrapper_stack_ok(('TimeLimit',))
    assert m.RESTORATION['direct_state_mutation'] is False
    assert m.RESTORATION['empirical_status'] == 'runner_time_gate_not_verified_at_lock'
    with pytest.raises(RuntimeError, match='prefix ended'):
        feas.reconstruct_later_state(feas.MockLaterEnv(terminate_after=3), 1, [0] * 8)
    a = feas.reconstruct_later_state(feas.MockLaterEnv(), 4, [1, 2, 0, 1, 2, 0, 1, 2])
    b = feas.reconstruct_later_state(feas.MockLaterEnv(), 4, [1, 2, 0, 1, 2, 0, 1, 2])
    feas.assert_same_later_state(a, b)


def test_shared_returns_oracle_algebra_and_student_t():
    realized = np.linspace(-2.0, -0.5, 16)
    scores_mt = realized.copy()
    scores_sc = -realized
    gap = m.oracle_cancels_in_arm_gap(realized, scores_mt, scores_sc)
    assert m.oracle_cancels_in_arm_gap(realized + 3.0, scores_mt, scores_sc) == pytest.approx(gap)
    assert m.same_state_did(-1.0, -1.4, -1.5, -1.3) == pytest.approx(0.6)
    assert m.same_state_did(-1.0, -1.4, -1.5, -1.3) == pytest.approx(
        feas.same_state_did(-1.0, -1.4, -1.5, -1.3))
    cells = []
    for seed in range(10):
        later = [dict(state_index=k, later_t=t, s_mt_l0=-1.0 + 0.02 * seed,
                      s_sc_l0=-1.2, s_mt_redraw=-1.3, s_sc_redraw=-1.25)
                 for k in range(4) for t in (8, 12)]
        cells.append(dict(seed=seed, later_states=later))
    out = m.mean_seed_cells(cells)
    assert out['interval']['n'] == 10 and out['interval']['df'] == 9
    assert out['label'] == 'h16_l0_helps_multitask_relative_same_state'
    with pytest.raises(ValueError, match='incomplete or duplicated seed'):
        m.mean_seed_cells(cells[:9])
    with pytest.raises(ValueError, match='incomplete or duplicated seed'):
        m.mean_seed_cells(cells + [cells[0]])
    nan = list(cells)
    row = dict(cells[0]['later_states'][0], s_mt_l0=float('nan'))
    nan[0] = dict(cells[0], later_states=[row] + cells[0]['later_states'][1:])
    with pytest.raises(ValueError, match='nonfinite'):
        m.mean_seed_cells(nan)
    assert m.classify_primary(0.2, -0.1, 0.3, 10) == 'h16_same_state_library_effect_not_established'
    assert m.classify_primary(0.2, 0.1, 0.3, 9) == 'incomplete'
    assert 'realized' not in inspect.signature(m.score_library).parameters


def test_budget_hard_cap_and_unauthorized_execute():
    cfg = m.load_config()
    counts = m.assert_budget(cfg)
    assert counts == m.budget()
    assert counts['env_total'] == 84000
    assert counts['imagined_total'] == 81920
    assert counts['source_collection'] == 15360
    assert counts['target_pool'] == 1600
    assert counts['reference_prefix'] == 480
    assert counts['prefix_replay'] == 25600
    assert counts['shared_candidate_realizations'] == 40960
    meter = feas.HardBudget(env_cap=2, imagined_cap=1)
    meter.reserve_env(2)
    with pytest.raises(RuntimeError, match='env-step cap'):
        meter.reserve_env(1)
    meter.reserve_imagined(1)
    with pytest.raises(RuntimeError, match='imagined cap'):
        meter.reserve_imagined(1)
    record = m.load_allocation()
    assert record['authorized'] is False and record['runs'] == 0
    with pytest.raises(PermissionError, match='fresh human approval'):
        m.execute()
    report = m.prep()
    assert report['authorized'] is False and report['runs'] == 0
    assert report['locked'] is True
    assert report['new_environment_steps'] == 0
    src = Path(m.__file__).read_text(encoding='utf-8')
    assert 'from nexus.tasks.spec import make_task_env' not in src
    assert 'from nexus.world.data import collect_transitions' not in src
    assert 'import gymnasium' not in src
    assert 'from nexus.world.train import train_world_model' not in src
