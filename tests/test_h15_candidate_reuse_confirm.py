"""Source-only H15 same-design confirmation lock tests. No MountainCar env."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
import yaml
from nexus.world import h14_candidate_reuse as h14
from nexus.world import h15_candidate_reuse_confirm as m


def test_holdout_rule_is_independent_and_excludes_closed_physics():
    first = m.holdout_from_rule()
    second = m.holdout_from_rule()
    assert first == second == [m.LOCKED_TARGET] == [(0.004, 0.0021, 0.05)]
    occupied = m.occupied_physics()
    assert m.LOCKED_TARGET not in occupied
    assert m.CLOSED_H14 in occupied
    for closed in (h14.CLOSED_H10, h14.CLOSED_H11, h14.CLOSED_H12, h14.CLOSED_H13, m.CLOSED_H14):
        assert closed in occupied
        assert closed != m.LOCKED_TARGET
    for source in m.source_physics_keys():
        assert source in occupied
    gs = [round(x * 0.0001, 4) for x in range(15, 41)]
    ps = [round(x * 0.0001, 4) for x in range(8, 23)]
    ss = [round(x * 0.005, 3) for x in range(10, 19)]
    digest = hashlib.sha256(f'{m.HOLD_RULE}:0'.encode()).digest()
    idx = int.from_bytes(digest[:8], 'big')
    recomputed = (float(gs[idx % len(gs)]), float(ps[(idx // len(gs)) % len(ps)]),
                  float(ss[(idx // (len(gs) * len(ps))) % len(ss)]))
    assert recomputed == m.LOCKED_TARGET
    assert m.HOLD_RULE == 'mcc_candidate_reuse_confirm_v1'


def test_h15_seeds_are_disjoint_from_h14_and_preserve_redraw_aliasing():
    cfg = m.load_config()
    parent = yaml.safe_load(h14.CONFIG.read_text())
    streams, used = m.seed_streams(cfg)
    _parent, h14_used = h14.seed_streams(parent)
    names = list(streams)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            assert not (streams[left] & streams[right])
    assert used & h14_used == set()
    assert min(used) >= 77_000_000
    assert max(h14_used) < 77_000_000
    aliases = m.redraw_alias_count(cfg)
    assert aliases == dict(intended=600, unique=450, aliased=150)
    assert aliases == m.redraw_alias_count(parent)
    assert h14.redraw_step_seed(cfg['redraw_base'], 0, 0, 11) == (
        h14.redraw_step_seed(cfg['redraw_base'], 0, 1, 1))


def test_design_is_frozen_to_h14_except_holdout_and_seeds():
    cfg = m.load_config()
    parent = yaml.safe_load(h14.CONFIG.read_text())
    for key in m.FROZEN_H14_FIELDS:
        assert cfg[key] == parent[key]
    assert cfg['source_physics'] == parent['source_physics']
    assert tuple(cfg['target_physics'][0]) != h14.LOCKED_TARGET
    assert cfg['reset_base'] == 77_000_000
    assert parent['reset_base'] == 76_000_000
    counts = m.budget(include_shared_open_loop=True, share_step0_scores=False)
    assert counts['source_collection'] == 15360
    assert counts['target_pool'] == 1600
    assert counts['recede_control'] == 2560
    assert counts['shared_open_loop'] == 10240
    assert counts['env_total'] == 29760
    assert counts['imagined_total'] == 655360
    src = Path(m.__file__).read_text(encoding='utf-8')
    assert 'collect_transitions' not in src
    assert 'make_task_env' not in src
    assert 'train_world_model' not in src


def test_h15_labels_match_h14_decision_and_never_pool_h14():
    assert m.classify_primary(0.178, 0.009, 0.348, 10) == (
        'h15_fixed_library_helps_multitask_relative')
    assert m.classify_primary(-0.2, -0.3, -0.1, 10) == (
        'h15_redraw_helps_multitask_relative')
    assert m.classify_primary(0.178, -0.001, 0.348, 10) == (
        'h15_resampling_effect_not_established')
    assert m.classify_primary(0.0, -0.1, 0.1, 10) == (
        'h15_resampling_effect_not_established')
    assert m.classify_primary(0.178, 0.009, 0.348, 9) == 'incomplete'
    assert m.classify_primary(float('nan'), 0.1, 0.3, 10) == 'incomplete'
    good = [dict(state_index=k, returns={'multitask': {'fixed': 1.0, 'redraw': 0.0},
                                         'scratch': {'fixed': 0.0, 'redraw': 0.5}})
            for k in range(4)]
    cells = [dict(seed=s, states=good) for s in range(10)]
    out = m.summarize(cells)
    assert out['label'] == 'h15_fixed_library_helps_multitask_relative'
    assert 'h14' not in out['label']


def test_authorized_one_run_record_is_loadable_and_not_consumed():
    rec = m.load_allocation()
    if rec.get('authorized') is not True:
        pytest.skip('one-run allocation not yet flipped')
    if rec.get('consumed') is True:
        pytest.skip('one-run allocation already consumed')
    cfg = m.load_config()
    assert rec['runs'] == 1
    assert rec['consumed'] is False
    assert rec['closed'] is False
    assert rec['config_sha256'] == m.LOCKED_CONFIG
    assert rec['protocol_sha256'] == m.LOCKED_PROTOCOL
    m.require_allocation(cfg)
    usage = json.loads(Path(rec['one_run_usage_record']).read_text())
    assert usage['consumed'] is False
    assert float(usage['remaining_session_allowance_s']) >= cfg['time_cap_s']


def test_locked_prep_refuses_execution_and_does_not_reuse_h14_allocation():
    if m.load_allocation().get('authorized') is True:
        pytest.skip('one-run allocation already flipped')
    cfg = m.load_config()
    assert tuple(cfg['target_physics'][0]) == m.LOCKED_TARGET
    report = m.prep()
    assert report['authorized'] is False
    assert report['runs'] == 0
    assert report['runner_implemented'] is False
    assert report['new_environment_steps'] == 0
    assert report['new_imagined_transitions'] == 0
    assert report['locked'] is True
    with pytest.raises(PermissionError, match='fresh human approval'):
        m.execute()
    allocation = m.load_allocation()
    assert allocation['authorized'] is False
    assert allocation['runs'] == 0
    assert allocation['config_sha256'] == m.LOCKED_CONFIG
    assert Path(m.ALLOCATION).resolve() != Path(h14.ALLOCATION).resolve()
    h14_allocation = h14.load_allocation()
    assert h14_allocation.get('authorized') is True
    assert int(h14_allocation.get('runs', 0)) == 1
