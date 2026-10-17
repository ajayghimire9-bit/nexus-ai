"""Offline 128-primary guards. No environment collection here."""
from __future__ import annotations
import pytest
from nexus.world import xenv_low_budget as m
from nexus.world.planning_value import sha


def test_primary_is_budget_128_and_holdout_is_new():
    cfg = m.load_config()
    assert cfg['primary_budget'] == 128 and cfg['prior_train'] == 1024
    assert cfg['reset_base'] == 68000000 and cfg['env_cap'] == 63200
    hold = m.holdout_from_rule()
    assert hold == [(0.0016, 0.0011, 0.08)]
    assert (0.0022, 0.0019, 0.08) in m.occupied_physics()
    assert m.target_spec(hold[0]).task_id == 'mcc_xenv7_t0'
    m.check_seeds(cfg)
    assert m.classify_primary(10.0, 1.0, 20.0, 10) == 'xenv_low_budget_beats_scratch'
    assert m.classify_primary(10.0, -1.0, 20.0, 10) == 'xenv_low_budget_not_established'


def test_summarize_uses_128_not_the_budget_average():
    cfg = m.load_config()
    cells = []
    for s in range(10):
        cells.append(dict(seed=s, returns=dict(
            xenv={'128': 10.0 + s, '1024': -100.0},
            scratch={'128': 0.0, '1024': 100.0},
            reference={'128': 0.0, '1024': 0.0}),
            mae=dict(xenv={'128': 0.1, '1024': 0.1},
                     scratch={'128': 0.1, '1024': 0.1},
                     reference={'128': 0.1, '1024': 0.1})))
    out = m.summarize(cells, cfg)
    assert out['groups']['primary']['budget'] == 128
    assert all(d > 0 for d in out['groups']['primary']['per_seed'])
    assert out['label'] == 'xenv_low_budget_beats_scratch'
    assert out['groups']['mean_over_budgets']['interval']['mean'] < 0


def test_allocation_unauthorized():
    cfg = m.load_config()
    record = m.load_allocation()
    assert record['authorized'] is False and record['runs'] == 0
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    with pytest.raises(PermissionError):
        m.require_allocation(cfg)
    report = m.prep()
    assert report['target_physics'] == [0.0016, 0.0011, 0.08]
    assert report['new_environment_steps'] == 0
