"""Offline residual-scale guards. No environment collection here."""
from __future__ import annotations
import numpy as np
import pytest
from nexus.world import mcc_residual_scale as m
from nexus.world.planning_value import sha


def test_holdout_is_unused_and_scale_is_2d():
    cfg = m.load_config()
    assert cfg['scale_dim'] == 2 and cfg['cross_family_weights'] is False
    assert cfg['target_train'] == 128 and cfg['reset_base'] == 71000000
    hold = m.holdout_from_rule()
    assert hold == [(0.0021, 0.0018, 0.055)]
    assert (0.0029, 0.0022, 0.055) in m.occupied_physics()
    assert m.target_spec(hold[0]).family == 'mountaincar_continuous'
    assert list(m.unit_scale()) == [1.0, 1.0]
    class D:
        obs = np.zeros((4, 2)); next_obs = np.array([[0.2, 0.4]] * 4)
    class R:
        def normalize(self, x):
            return np.asarray(x, dtype=np.float64)
    assert np.allclose(m.residual_scale(D(), R()), [0.2, 0.4])
    m.check_seeds(cfg)
    assert m.classify_primary(4.0, 1.0, 8.0, 10) == 'mcc_residual_scale_beats_unit'
    assert m.classify_primary(4.0, -1.0, 8.0, 10) == 'mcc_residual_scale_not_established'


def test_summarize_is_source_scale_minus_unit():
    cfg = m.load_config()
    cells = [dict(seed=s, returns=dict(source_scale=5.0 + s, unit_scale=0.0),
                  mae=dict(source_scale=0.1, unit_scale=0.1)) for s in range(10)]
    out = m.summarize(cells, cfg)
    assert out['groups']['primary']['budget'] == 128
    assert out['label'] == 'mcc_residual_scale_beats_unit'


def test_allocation_unauthorized():
    cfg = m.load_config()
    record = m.load_allocation()
    assert record['authorized'] is False and record['runs'] == 0
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    with pytest.raises(PermissionError):
        m.require_allocation(cfg)
    report = m.prep()
    assert report['target_physics'] == [0.0021, 0.0018, 0.055]
    assert report['new_environment_steps'] == 0
