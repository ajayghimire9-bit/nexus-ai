"""Same-state pairing, published reward, and checkpoint integrity. No diagnostic grid."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from nexus.tasks.pendulum_family import pendulum_latent_confirmation
from nexus.world.planning import mpc_for_model
from nexus.world.prediction_control_gap import (
    REQUIRED_DECODERS,
    assert_diagnostic_output_path,
    assert_diagnostic_seeds,
    assert_existing_hash,
    assert_protocol_frozen,
    average_student_metric,
    candidate_seed,
    candidate_sequences,
    decide,
    decision_metrics,
    load_prediction_config,
    planner_scores,
    reliable_improvement,
    rollout_sequence,
    split_decoder_values,
    state_seed,
    trajectory_prediction_errors,
    verify_provenance,
)
from nexus.world.rewards import pendulum_step_reward


class _Net:
    obs_dim = 3
    n_actions = 3


class _Identity:
    def __init__(self) -> None:
        self.net = _Net()

    def begin_rollout(self, n: int) -> None:
        del n

    def step(self, obs: np.ndarray, action: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        del action
        state = np.asarray(obs, dtype=np.float32)
        if state.ndim == 1:
            state = state.reshape(1, -1)
        return state.copy(), np.zeros(state.shape[0], dtype=np.float32)


def test_registered_config_and_protocol_lock() -> None:
    cfg = load_prediction_config()
    assert_protocol_frozen("docs/NEXUS_PREDICTION_CONTROL_GAP.md", cfg)
    assert cfg["primary_split"] == "fresh"
    assert cfg["full_episode_remeasured"] is False
    assert cfg["horizon"] == 16 and cfg["n_candidates"] == 16
    assert_diagnostic_seeds(cfg)


def test_diagnostic_seeds_do_not_collapse_across_physics() -> None:
    assert state_seed(140000, 0, 15) == 140015
    assert state_seed(140000, 1, 0) == 140020
    assert candidate_seed(151000, 1, 3, 15) == 161315
    left = candidate_sequences(151000)
    right = candidate_sequences(151000)
    assert left.shape == (16, 16)
    assert np.array_equal(left, right)
    assert set(np.unique(left)).issubset({0, 1, 2})


def test_reset_replays_the_same_state_and_reward() -> None:
    spec = pendulum_latent_confirmation()[0]
    actions = np.asarray([0, 2, 1, 2], dtype=np.int64)
    first = rollout_sequence(spec, 140000, actions)
    second = rollout_sequence(spec, 140000, actions)
    assert np.array_equal(first["obs0"], second["obs0"])
    assert np.allclose(first["rewards"], second["rewards"])
    assert np.allclose(first["next_obs"], second["next_obs"])
    assert float(np.sum(first["rewards"])) == pytest.approx(float(np.sum(first["published"])), abs=1e-6)


def test_published_reward_matches_the_step_cost() -> None:
    spec = pendulum_latent_confirmation()[0]
    rolled = rollout_sequence(spec, 140000, np.asarray([1, 2, 0], dtype=np.int64))
    manual = []
    obs = rolled["obs0"]
    for action, nxt in zip([1, 2, 0], rolled["next_obs"], strict=True):
        manual.append(float(np.asarray(pendulum_step_reward(obs, action, nxt)).reshape(-1)[0]))
        obs = nxt
    assert np.allclose(rolled["published"], manual)
    assert np.allclose(rolled["rewards"], manual)


def test_shared_candidates_keep_the_planner_objective() -> None:
    import inspect

    assert list(inspect.signature(planner_scores).parameters) == ["model", "obs", "sequences"]
    model = _Identity()
    obs = np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
    sequences = np.ones((16, 16), dtype=np.int64)
    sequences[1] = 2
    scores = planner_scores(model, obs, sequences)
    assert scores.shape == (16,)
    assert scores[0] == pytest.approx(0.0)
    assert scores[1] == pytest.approx(-0.064)
    planner = mpc_for_model(model, seed=0, enforce_time_budget=False)
    chunks = np.concatenate([
        planner._score_batch(obs, sequences[:8]),
        planner._score_batch(obs, sequences[8:]),
    ])
    assert np.allclose(scores, chunks)
    paired = decision_metrics(scores, np.zeros(16), sequences)
    assert paired["selected"] == 0
    swapped = decision_metrics(np.asarray([-2.0, -1.0, 0.0]), np.asarray([0.0, -5.0, -1.0]), np.zeros((3, 2), dtype=np.int64))
    assert swapped["selected"] == 2
    assert swapped["regret"] == pytest.approx(1.0)
    assert swapped["correct"] is False
    with pytest.raises(ValueError, match="not paired"):
        decision_metrics(scores, np.zeros(4), sequences)


def test_open_loop_error_uses_the_same_actions() -> None:
    model = _Identity()
    obs = np.asarray([1.0, 0.0, 0.25], dtype=np.float32)
    sequences = np.zeros((4, 3), dtype=np.int64)
    actual = np.zeros((4, 3, 3), dtype=np.float32)
    actual[:, :, 2] = 0.25
    matched = trajectory_prediction_errors(model, obs, sequences, actual)
    assert matched["open_loop_angvel"] == pytest.approx(0.0)
    assert matched["one_step_angvel"] == pytest.approx(0.0)
    actual[:, :, 2] = 0.0
    shifted = trajectory_prediction_errors(model, obs, sequences, actual)
    assert shifted["open_loop_angvel"] == pytest.approx(0.25)


def test_students_stay_inside_the_decoder() -> None:
    assert average_student_metric([{"regret": 1.0}, {"regret": 3.0}], "regret") == pytest.approx(2.0)
    rows = [
        {"decoder": 0, "split": "fresh", "task": "a", "regret_improvement": 1.0},
        {"decoder": 0, "split": "fresh", "task": "b", "regret_improvement": 3.0},
        {"decoder": 1, "split": "fresh", "task": "a", "regret_improvement": 5.0},
        {"decoder": 1, "split": "fresh", "task": "b", "regret_improvement": 7.0},
    ]
    assert split_decoder_values(rows, "fresh", "regret_improvement", tasks=2) == [2.0, 6.0]
    short = reliable_improvement([2.0, 6.0], required_n=REQUIRED_DECODERS)
    assert short["pass"] is False
    assert short["interval"]["n"] == 2


def test_decision_tree_is_registered_before_outcomes() -> None:
    assert decide(
        state_better=True, ranking_better=False, ranking_worse=True, reward_better=True, full_episode_better=False,
    ) == "objective_misaligned"
    assert decide(
        state_better=True, ranking_better=True, ranking_worse=False, reward_better=True, full_episode_better=False,
    ) == "evaluation_variance"
    assert decide(
        state_better=False, ranking_better=True, ranking_worse=False, reward_better=False, full_episode_better=False,
    ) == "receding_horizon"
    assert decide(
        state_better=True, ranking_better=True, ranking_worse=False, reward_better=True, full_episode_better=True,
    ) == "planning_metrics_agree"
    assert decide(
        state_better=False, ranking_better=False, ranking_worse=False, reward_better=False, full_episode_better=False,
    ) == "inconclusive"
    with pytest.raises(RuntimeError, match="contradict"):
        decide(state_better=True, ranking_better=True, ranking_worse=True, reward_better=False, full_episode_better=False)


def test_hash_mismatch_does_not_overwrite_and_prior_dirs_are_closed(tmp_path: Path) -> None:
    target = tmp_path / "student.pt"
    target.write_bytes(b"closed-weights")
    with pytest.raises(RuntimeError, match="refusing to replace"):
        assert_existing_hash(target, "0" * 64)
    assert target.read_bytes() == b"closed-weights"
    with pytest.raises(RuntimeError, match="refusing to write"):
        assert_diagnostic_output_path(tmp_path / "frozen_dynamics_checkpoints" / "gap.json")
    with pytest.raises(RuntimeError, match="does not write checkpoints"):
        assert_diagnostic_output_path(tmp_path / "gap.pt")


def test_closed_checkpoints_match_the_manifest() -> None:
    report = verify_provenance(load_prediction_config())
    assert report["verified"] is True
    assert report["checkpoints_written"] is False
    assert len(report["decoder_fingerprints"]) == 10
    assert report["global_vectors_checked"] is True
