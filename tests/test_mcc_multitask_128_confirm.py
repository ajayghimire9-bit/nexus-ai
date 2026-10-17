"""Source-only H11 confirmation guards. No environment collection here."""
from __future__ import annotations
import pytest
from nexus.world import mcc_multitask_128 as h10
from nexus.world import mcc_multitask_128_confirm as m
from nexus.world.planning_value import sha


def test_h10_closed_hashes_and_recipe_are_frozen():
    m.assert_h10_frozen()
    assert sha(h10.OUTPUT) == m.FROZEN_H10_RAW
    assert sha('docs/NEXUS_MCC_MULTITASK_128_RESULTS.md') == m.FROZEN_H10_REPORT
    assert sha('src/nexus/world/mcc_multitask_128.py') == m.FROZEN_H10_CODE
    assert sha(h10.CONFIG) == m.FROZEN_H10_CONFIG == h10.LOCKED_CONFIG
    assert sha(h10.PROTOCOL) == m.FROZEN_H10_PROTOCOL == h10.LOCKED_PROTOCOL
    assert h10.holdout_from_rule() == [m.CLOSED_H10]
    cfg = m.load_config()
    parent = h10.load_config()
    for key in m.FROZEN_H10_FIELDS:
        assert cfg[key] == parent[key]
    assert cfg['source_physics'] == parent['source_physics']
    assert cfg['target_train'] == 128
    assert cfg['pretrain_epochs'] == 15 and cfg['train_epochs'] == 20
    assert cfg['hidden'] == [64, 64] and cfg['horizon'] == 16


def test_confirmation_holdout_and_seeds_are_disjoint_from_h10():
    cfg = m.load_config()
    hold = m.holdout_from_rule()
    assert hold == [(0.0022, 0.0016, 0.07)]
    assert hold[0] != m.CLOSED_H10
    assert hold[0] not in m.occupied_physics()
    assert hold[0] not in h10.source_physics_keys()
    assert (0.0032, 0.0022, 0.06) in m.occupied_physics()
    assert (0.0029, 0.0022, 0.055) in m.occupied_physics()
    assert (0.0021, 0.0018, 0.055) in m.occupied_physics()
    spec = m.target_spec(hold[0])
    assert spec.family == 'mountaincar_continuous' and spec.n_actions == 3
    assert cfg['reset_base'] == 73000000
    assert cfg['cross_family_weights'] is False
    m.check_seeds(cfg)
    assert m.classify_primary(10.0, 1.0, 20.0, 10) == 'mcc_multitask_128_confirm_beats_scratch'
    assert m.classify_primary(10.0, -1.0, 20.0, 10) == 'mcc_multitask_128_confirm_not_established'
    assert m.classify_primary(-10.0, -20.0, -1.0, 10) == 'mcc_multitask_128_confirm_harm_established'


def test_budget_and_unauthorized_allocation_block_collection():
    cfg = m.load_config()
    counts = m.budget(cfg)
    assert counts['source_collection'] == 15360
    assert counts['target_pool'] == 1600
    assert counts['evaluation_episodes'] == 4000
    assert cfg['env_cap'] == 20960 and cfg['model_cap'] == 1024000
    assert cfg['time_cap_s'] == 600
    record = m.load_allocation()
    assert record['authorized'] is False and record['runs'] == 0
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    assert record['protocol_sha256'] == sha(m.PROTOCOL) == m.LOCKED_PROTOCOL
    assert m.prep()['authorized'] is False
    assert m.prep()['new_environment_steps'] == 0
    with pytest.raises(PermissionError, match='fresh human approval'):
        m.require_allocation(cfg)
    cells = [dict(seed=s, returns=dict(multitask=10.0 + s, scratch=0.0),
                  mae=dict(multitask=0.1, scratch=0.1)) for s in range(10)]
    out = m.summarize(cells, cfg)
    assert out['groups']['primary']['budget'] == 128
    assert out['label'] == 'mcc_multitask_128_confirm_beats_scratch'
