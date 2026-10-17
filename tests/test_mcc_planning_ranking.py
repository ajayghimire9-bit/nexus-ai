"""Source-only ranking-prep guards. No environment collection."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pytest
from nexus.world import mcc_planning_ranking as m
from nexus.world import mcc_multitask_128 as h10
from nexus.world import mcc_multitask_128_confirm as h11
from nexus.world.planning_value import sha


def test_holdout_is_unused_and_not_chosen_from_h11_negative_seeds():
    cfg = m.load_config()
    hold = m.holdout_from_rule()
    assert hold == [(0.0027, 0.0015, 0.075)]
    assert hold[0] not in m.occupied_physics()
    assert hold[0] != h11.CLOSED_H10
    assert hold[0] != m.CLOSED_H11
    assert cfg['h10_negative_seeds_used'] is False
    assert cfg['full_episode_primary'] is False
    assert cfg['restore_method'] == 'reset_same_seed'
    assert cfg['n_states'] == 4 and cfg['n_candidates'] == 16
    assert cfg['source_physics'] == h10.load_config()['source_physics']
    assert cfg['pretrain_epochs'] == 15 and cfg['target_train'] == 128
    m.check_seeds(cfg)


def test_regret_is_nonnegative_and_separates_first_action():
    pred = np.array([1.0, 3.0, 0.5, 2.0])
    real = np.array([4.0, 1.0, 5.0, 0.0])
    seq = np.array([[0, 1], [1, 1], [2, 0], [1, 2]])
    assert m.sequence_regret(pred, real) == 4.0
    assert m.first_action_regret(pred, real, seq) == 4.0
    with pytest.raises(ValueError):
        m.sequence_regret([1.0], [1.0, 2.0])
    assert m.classify_primary(1.0, 0.1, 2.0, 10) == 'mcc_planning_ranking_multitask_better'
    assert m.classify_primary(-1.0, -2.0, -0.1, 10) == 'mcc_planning_ranking_scratch_better'
    assert m.classify_primary(1.0, -0.1, 2.0, 10) == 'mcc_planning_ranking_not_established'


def test_budget_counts_shared_ground_truth_and_blocks_collection():
    cfg = m.load_config()
    counts = m.budget(cfg)
    assert counts['ground_truth_open_loop'] == 10240
    assert counts['closed_loop_recede'] == 1280
    assert counts['source_collection'] + counts['target_pool'] == 16960
    assert cfg['env_cap'] == 28480 and cfg['model_cap'] == 348160
    assert cfg['time_cap_s'] == 300
    record = m.load_allocation()
    assert record['authorized'] is False and record['runs'] == 0
    assert record['config_sha256'] == sha(m.CONFIG) == m.LOCKED_CONFIG
    assert m.prep()['new_environment_steps'] == 0
    with pytest.raises(PermissionError, match='fresh human approval'):
        m.require_allocation(cfg)
    with pytest.raises(PermissionError):
        m.execute()
    src = Path(m.__file__).read_text(encoding='utf-8')
    assert 'collect_transitions' not in src
    assert 'make_task_env' not in src
