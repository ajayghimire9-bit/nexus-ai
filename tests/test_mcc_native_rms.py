"""Offline native-RMS guards. No environment collection here."""
from __future__ import annotations
import pytest
from nexus.world import mcc_native_rms as m
from nexus.world.planning_value import sha


def test_holdout_is_unused_mcc_and_not_an_xenv_variant():
    cfg = m.load_config()
    assert cfg['source_family'] == cfg['target_family'] == 'mountaincar_continuous'
    assert cfg['cross_family_weights'] is False
    assert cfg['target_train'] == 128 and cfg['env_cap'] == 10720
    assert cfg['reset_base'] == 70000000
    hold = m.holdout_from_rule()
    assert hold == [(0.0029, 0.0022, 0.055)]
    assert (0.0016, 0.0011, 0.08) in m.occupied_physics()
    assert (0.0025, 0.0015, 0.07) in m.occupied_physics()
    spec = m.target_spec(hold[0])
    assert spec.family == 'mountaincar_continuous' and spec.n_actions == 3
    m.check_seeds(cfg)
    assert m.classify_primary(10.0, 1.0, 20.0, 10) == 'mcc_native_rms_beats_scratch'
    assert m.classify_primary(10.0, -1.0, 20.0, 10) == 'mcc_native_rms_not_established'


def test_summarize_is_source_minus_scratch_at_128():
    cfg = m.load_config()
    cells = [dict(seed=s, returns=dict(source_rms=10.0 + s, scratch_rms=0.0),
                  mae=dict(source_rms=0.1, scratch_rms=0.1)) for s in range(10)]
    out = m.summarize(cells, cfg)
    assert out['groups']['primary']['budget'] == 128
    assert all(d > 0 for d in out['groups']['primary']['per_seed'])
    assert out['label'] == 'mcc_native_rms_beats_scratch'


def test_allocation_unauthorized():
    cfg = m.load_config()
    record = m.load_allocation()
    assert record['authorized'] is False and record['runs'] == 0
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    with pytest.raises(PermissionError):
        m.require_allocation(cfg)
    report = m.prep()
    assert report['target_physics'] == [0.0029, 0.0022, 0.055]
    assert report['new_environment_steps'] == 0
    assert report['cross_family_weights'] is False
