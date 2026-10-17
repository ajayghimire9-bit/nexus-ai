"""Source-only H13 ranking-confirmation guards. No environment collection."""
from __future__ import annotations
import pytest
from nexus.world import mcc_planning_ranking as h12
from nexus.world import mcc_planning_ranking_confirm as m
from nexus.world import mcc_multitask_128 as h10
from nexus.world import mcc_multitask_128_confirm as h11
from nexus.world.planning_value import sha


def test_h12_closed_hashes_and_recipe_are_frozen():
    m.assert_h12_frozen()
    assert sha(h12.OUTPUT) == m.FROZEN_H12_RAW
    assert sha('docs/NEXUS_MCC_PLANNING_RANKING_RESULTS.md') == m.FROZEN_H12_REPORT
    assert sha('src/nexus/world/mcc_planning_ranking.py') == m.FROZEN_H12_CODE
    assert sha(h12.CONFIG) == m.FROZEN_H12_CONFIG == h12.LOCKED_CONFIG
    assert sha(h12.PROTOCOL) == m.FROZEN_H12_PROTOCOL == h12.LOCKED_PROTOCOL
    assert h12.holdout_from_rule() == [m.CLOSED_H12]
    cfg = m.load_config()
    parent = h12.load_config()
    for key in m.FROZEN_H12_FIELDS:
        assert cfg[key] == parent[key]
    assert cfg['source_physics'] == parent['source_physics']
    assert cfg['target_train'] == 128 and cfg['n_states'] == 4
    assert cfg['restore_method'] == 'reset_same_seed'
    assert cfg['h10_negative_seeds_used'] is False
    assert cfg['full_episode_primary'] is False


def test_confirmation_holdout_and_seeds_are_disjoint_from_h12():
    cfg = m.load_config()
    hold = m.holdout_from_rule()
    assert hold == [(0.0039, 0.002, 0.075)]
    assert hold[0] != m.CLOSED_H12
    assert hold[0] != h11.CLOSED_H10
    assert hold[0] != h12.CLOSED_H11
    assert hold[0] not in m.occupied_physics()
    assert hold[0] not in h10.source_physics_keys()
    assert m.CLOSED_H12 in m.occupied_physics()
    spec = m.target_spec(hold[0])
    assert spec.family == 'mountaincar_continuous' and spec.n_actions == 3
    assert cfg['reset_base'] == 75000000
    assert cfg['cross_family_weights'] is False
    m.check_seeds(cfg)
    assert m.classify_primary(1.0, 0.1, 2.0, 10) == 'mcc_planning_ranking_confirm_multitask_better'
    assert m.classify_primary(-1.0, -2.0, -0.1, 10) == 'mcc_planning_ranking_confirm_scratch_better'
    assert m.classify_primary(1.0, -0.1, 2.0, 10) == 'mcc_planning_ranking_confirm_not_established'
    assert m.classify_primary(1.0, 0.1, 2.0, 9) == 'incomplete'


def test_budget_and_unauthorized_allocation_block_collection():
    cfg = m.load_config()
    counts = m.budget(cfg)
    assert counts['ground_truth_open_loop'] == 10240
    assert counts['closed_loop_recede'] == 1280
    assert cfg['env_cap'] == 28480 and cfg['model_cap'] == 348160
    assert cfg['time_cap_s'] == 300
    record = m.load_allocation()
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    assert record['protocol_sha256'] == sha(m.PROTOCOL) == m.LOCKED_PROTOCOL
    if record.get('authorized') is True:
        assert record['runs'] == 1
        m.require_allocation(cfg)
        with pytest.raises(PermissionError, match='already authorized'):
            m.prep()
    else:
        assert record['runs'] == 0
        assert m.prep()['authorized'] is False
        assert m.prep()['new_environment_steps'] == 0
        with pytest.raises(PermissionError, match='fresh human approval'):
            m.require_allocation(cfg)
        with pytest.raises(PermissionError):
            m.execute()
    cells = [dict(seed=s, sequence_regret=dict(scratch=1.0, multitask=0.0),
                  first_action_regret=dict(scratch=0.0, multitask=0.0))
             for s in range(10)]
    out = m.summarize(cells, cfg)
    assert out['groups']['primary']['metric'] == 'scratch_minus_multitask_sequence_regret'
    assert out['label'] == 'mcc_planning_ranking_confirm_multitask_better'
