"""Offline CartPole-target guards. No environment collection here."""
from __future__ import annotations
import pytest
from nexus.world import xenv_cartpole_target as m
from nexus.world.planning_value import sha


def test_holdout_is_unused_cartpole_and_priors_exclude_cartpole():
    cfg = m.load_config()
    assert cfg['target_family'] == 'cartpole' and cfg['n_actions'] == 2
    assert cfg['prior_families'] == ['acrobot', 'mountaincar', 'mountaincar_continuous']
    assert cfg['prior_train'] == 512 and cfg['env_cap'] == 44000
    assert cfg['reset_base'] == 69000000
    hold = m.holdout_from_rule()
    assert hold == [(6.5, 0.57, 0.28)]
    assert (9.8, 0.5, 0.1) in m.occupied_physics()
    spec = m.target_spec(hold[0])
    assert spec.task_id == 'cartpole_xenv_t0' and spec.n_actions == 2
    priors = m.prior_specs()
    assert set(priors) == {'acrobot', 'mountaincar', 'mcc'}
    assert 'cartpole' not in priors
    m.check_seeds(cfg)
    assert m.classify_primary(10.0, 1.0, 20.0, 10) == 'xenv_cartpole_target_beats_scratch'
    assert m.classify_primary(10.0, -1.0, 20.0, 10) == 'xenv_cartpole_target_not_established'


def test_summarize_uses_mean_over_budgets():
    cfg = m.load_config()
    cells = []
    for s in range(10):
        cells.append(dict(seed=s, returns=dict(
            xenv={'128': 10.0 + s, '1024': 10.0 + s},
            scratch={'128': 0.0, '1024': 0.0},
            reference={'128': 0.0, '1024': 0.0}),
            mae=dict(xenv={'128': 0.1, '1024': 0.1},
                     scratch={'128': 0.1, '1024': 0.1},
                     reference={'128': 0.1, '1024': 0.1})))
    out = m.summarize(cells, cfg)
    assert all(d > 0 for d in out['groups']['primary']['per_seed'])
    assert out['label'] == 'xenv_cartpole_target_beats_scratch'


def test_allocation_binds_the_authorized_one_run_record():
    cfg = m.load_config()
    record = m.load_allocation()
    assert record['authorized'] is True and record['runs'] == 1
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    m.require_allocation(cfg)
    with pytest.raises(PermissionError, match='already authorized'):
        m.prep()
