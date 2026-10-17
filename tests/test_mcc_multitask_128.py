"""Offline multitask-128 guards. No environment collection here."""
from __future__ import annotations
import pytest
from nexus.world import mcc_multitask_128 as m
from nexus.world.planning_value import sha


def test_holdout_is_unused_mcc_and_not_an_interface_transplant():
    cfg = m.load_config()
    assert cfg['source_family'] == cfg['target_family'] == 'mountaincar_continuous'
    assert cfg['cross_family_weights'] is False
    assert cfg['n_source_physics'] == 3 and cfg['target_train'] == 128
    assert cfg['env_cap'] == 20960 and cfg['reset_base'] == 72000000
    hold = m.holdout_from_rule()
    assert hold == [(0.0032, 0.0022, 0.06)]
    assert (0.0029, 0.0022, 0.055) in m.occupied_physics()
    assert (0.0021, 0.0018, 0.055) in m.occupied_physics()
    assert (0.0025, 0.0015, 0.07) in m.occupied_physics()
    assert m.source_physics_keys() == (
        (0.0025, 0.0015, 0.07),
        (0.0038, 0.0019, 0.085),
        (0.0024, 0.0019, 0.09),
    )
    spec = m.target_spec(hold[0])
    assert spec.family == 'mountaincar_continuous' and spec.n_actions == 3
    m.check_seeds(cfg)
    assert m.classify_primary(10.0, 1.0, 20.0, 10) == 'mcc_multitask_128_beats_scratch'
    assert m.classify_primary(10.0, -1.0, 20.0, 10) == 'mcc_multitask_128_not_established'
    assert m.classify_primary(-10.0, -20.0, -1.0, 10) == 'mcc_multitask_128_harm_established'


def test_summarize_is_multitask_minus_scratch_at_128():
    cfg = m.load_config()
    cells = [dict(seed=s, returns=dict(multitask=10.0 + s, scratch=0.0),
                  mae=dict(multitask=0.1, scratch=0.1)) for s in range(10)]
    out = m.summarize(cells, cfg)
    assert out['groups']['primary']['budget'] == 128
    assert all(d > 0 for d in out['groups']['primary']['per_seed'])
    assert out['label'] == 'mcc_multitask_128_beats_scratch'


def test_allocation_state_matches_the_committed_record():
    cfg = m.load_config()
    record = m.load_allocation()
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    if record.get('authorized') is True:
        assert record['runs'] == 1
        m.require_allocation(cfg)
        with pytest.raises(PermissionError, match='already authorized'):
            m.prep()
    else:
        assert record['runs'] == 0
        assert m.prep()['authorized'] is False
