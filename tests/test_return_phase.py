"""Reward accounting, paired seeds, and rejection of an incomplete return split."""

from __future__ import annotations

import numpy as np
import pytest

from nexus.tasks.pendulum_family import pendulum_control_replication
from nexus.tasks.spec import make_task_env
from nexus.world.return_phase import (
    EARLY_STEPS,
    assert_phase_seeds,
    assert_protocol_frozen,
    describe_contribution,
    episode_env_seed,
    episode_planner_seed,
    load_phase_config,
    phase_deltas,
    require_complete,
)
from nexus.world.rewards import pendulum_step_reward


def test_protocol_and_new_seeds_stay_disjoint() -> None:
    cfg = load_phase_config()
    assert_protocol_frozen("docs/NEXUS_RETURN_PHASE_DECOMPOSITION.md", cfg)
    assert_phase_seeds(cfg)
    assert cfg["episodes_per_task"] == 4
    assert cfg["primary_split"] == "fresh"
    assert episode_env_seed(400000, 1, 2, 100) == 400102
    assert episode_planner_seed(410000, 1, 2, 100) == 410102
    assert episode_env_seed(400000, 0, 0) == episode_env_seed(400000, 0, 0)


def test_early_plus_late_equals_the_total() -> None:
    student = np.full((5, 200), -1.0)
    zero = np.zeros(200)
    deltas = phase_deltas(student, zero)
    assert deltas["early"] == pytest.approx(-16.0)
    assert deltas["late"] == pytest.approx(-184.0)
    assert deltas["total"] == pytest.approx(deltas["early"] + deltas["late"])
    assert EARLY_STEPS == 16
    mixed = np.arange(200, dtype=np.float64)
    again = phase_deltas(np.stack([mixed, mixed + 2.0]), mixed)
    assert again["total"] == pytest.approx(again["early"] + again["late"])


def test_percentages_need_a_stable_total() -> None:
    early = [10.0] * 10
    late = [0.0] * 10
    total = [10.0] * 10
    early_only = describe_contribution(early, late, total)
    assert early_only["label"] == "primarily_early"
    assert early_only["percentages_reported"] is True
    late_only = describe_contribution(late, early, total)
    assert late_only["label"] == "primarily_late"
    both = describe_contribution([4.0] * 10, [6.0] * 10, total)
    assert both["label"] == "both_phases"
    crossing = [10.0] * 5 + [-10.0] * 5
    quiet = describe_contribution(crossing, crossing, crossing)
    assert quiet["label"] == "absolute_only"
    assert quiet["percentages_reported"] is False
    tiny = [10.0] * 9 + [0.5]
    assert describe_contribution(tiny, [0.0] * 10, tiny)["percentages_reported"] is False
    assert describe_contribution(early[:9], late[:9], total[:9])["label"] == "incomplete"


def test_incomplete_grids_are_rejected() -> None:
    with pytest.raises(RuntimeError, match="not 160"):
        require_complete(159, 160)


def test_published_reward_matches_a_fixed_action_episode() -> None:
    spec = pendulum_control_replication()[0]
    env = make_task_env(spec)
    obs, _info = env.reset(seed=400000)
    rewards = []
    published = []
    for _step in range(200):
        current = np.asarray(obs, dtype=np.float32).reshape(-1)
        nxt, reward, _terminated, _truncated, _info = env.step(1)
        nxt_arr = np.asarray(nxt, dtype=np.float32).reshape(-1)
        rewards.append(float(reward))
        published.append(float(np.asarray(pendulum_step_reward(current, 1, nxt_arr)).reshape(-1)[0]))
        obs = nxt
    env.close()
    assert sum(rewards) == pytest.approx(sum(published), abs=1e-6)
    assert len(rewards) == 200


def test_paired_resets_share_the_initial_observation() -> None:
    spec = pendulum_control_replication()[0]
    first = make_task_env(spec)
    second = make_task_env(spec)
    left, _info = first.reset(seed=400000)
    right, _info = second.reset(seed=400000)
    assert np.array_equal(np.asarray(left), np.asarray(right))
    first.close()
    second.close()
    assert episode_planner_seed(410000, 3, 3) != episode_env_seed(400000, 3, 3)
