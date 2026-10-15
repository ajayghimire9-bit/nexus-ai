"""State cloning, live-score replay, context locking, and the registered decision tree."""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pytest
import torch

from nexus.tasks.pendulum_family import pendulum_latent_confirmation
from nexus.tasks.spec import make_task_env
from nexus.world.planning import mpc_for_model
from nexus.world.prediction_control_gap import assert_diagnostic_output_path, assert_existing_hash, reliable_improvement
from nexus.world.receding_horizon import (
    REQUIRED_ROWS,
    assert_horizon_seeds,
    assert_protocol_frozen,
    chunked_scores,
    continuation_step_seed,
    decide,
    decoder_values,
    diagnostic_candidate_seed,
    load_horizon_config,
    reproduce_live_scores,
    restore_state,
    rollout_actions,
    true_state,
    verify_horizon_provenance,
)
from nexus.world.rewards import pendulum_step_reward


class _Net:
    obs_dim = 3
    n_actions = 3


class _Model:
    def __init__(self) -> None:
        self.net = _Net()
        self.z = torch.zeros(8)
        self.seen: list[np.ndarray] = []

    def context_dim(self) -> int:
        return 8

    def begin_rollout(self, n: int) -> None:
        del n

    def step(self, obs: np.ndarray, action: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        self.seen.append(np.asarray(action).reshape(-1).copy())
        state = np.asarray(obs, dtype=np.float32)
        if state.ndim == 1:
            state = state.reshape(1, -1)
        n = np.asarray(action).reshape(-1).shape[0]
        if state.shape[0] == 1 and n > 1:
            state = np.repeat(state, n, axis=0)
        return state.copy(), np.zeros(state.shape[0], dtype=np.float32)


def test_protocol_seeds_and_equal_budgets() -> None:
    cfg = load_horizon_config()
    assert_protocol_frozen("docs/NEXUS_RECEDING_HORIZON_DIAGNOSTIC.md", cfg)
    assert_horizon_seeds(cfg)
    assert cfg["continuation_policy"] == "zero_context_replan"
    assert cfg["episodes_per_task"] == 1
    assert REQUIRED_ROWS(cfg) == 640
    assert "action" not in inspect.signature(continuation_step_seed).parameters
    assert continuation_step_seed(280000, 0, 1, 2, 3, 4) != continuation_step_seed(280000, 0, 1, 2, 3, 5)


def test_reset_and_cloned_state_repeat_the_reward() -> None:
    spec = pendulum_latent_confirmation()[0]
    env = make_task_env(spec)
    obs, _info = env.reset(seed=170000)
    state = true_state(env)
    for _step in range(200):
        env.step(1)
    restored = restore_state(env, state)
    assert np.allclose(restored, np.asarray(obs, dtype=np.float32))
    actions = np.asarray([0, 2, 1, 2], dtype=np.int64)
    first = rollout_actions(env, state, actions)
    second = rollout_actions(env, state, actions)
    assert first["return"] == pytest.approx(second["return"])
    assert np.allclose(first["rewards"], second["rewards"])
    manual = []
    current = restored
    fresh = make_task_env(spec)
    fresh.reset(seed=1)
    fresh.unwrapped.state = state.copy()
    for action in actions:
        nxt, reward, _term, _trunc, _info = fresh.step(int(action))
        manual.append(float(np.asarray(pendulum_step_reward(current, int(action), nxt)).reshape(-1)[0]))
        current = np.asarray(nxt, dtype=np.float32)
    assert first["return"] == pytest.approx(float(np.sum(manual)))
    env.close()
    fresh.close()


def test_live_scores_replay_and_context_stays_fixed() -> None:
    model = _Model()
    obs = np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
    planner = mpc_for_model(model, seed=176000, enforce_time_budget=False)
    planner.reset_episode(176000)
    action, info = planner.act(obs)
    sequences = np.asarray(planner.last_seqs)
    assert reproduce_live_scores(model, obs, sequences, np.asarray(info["candidate_scores"]), int(action))
    assert torch.equal(model.z, torch.zeros(8))
    again = mpc_for_model(model, seed=176000, enforce_time_budget=False)
    again.reset_episode(176000)
    again.act(obs)
    assert np.array_equal(again.last_seqs, sequences)
    carried = mpc_for_model(model, seed=176000, enforce_time_budget=False)
    carried.act(obs)
    carried.act(obs)
    restarted = mpc_for_model(model, seed=176000, enforce_time_budget=False)
    restarted.reset_episode(176000)
    assert not np.array_equal(carried.last_seqs, restarted.last_seqs)
    from nexus.world.prediction_control_gap import candidate_sequences

    seqs = candidate_sequences(diagnostic_candidate_seed(210000, 0, 0, 0, 0))
    left_model, right_model = _Model(), _Model()
    left = chunked_scores(left_model, obs, seqs)
    right = chunked_scores(right_model, obs, seqs)
    assert np.allclose(left, right)
    assert np.array_equal(np.concatenate(left_model.seen), np.concatenate(right_model.seen))
    assert list(inspect.signature(chunked_scores).parameters) == ["model", "obs", "sequences"]


def test_students_and_incomplete_grids_do_not_inflate_the_decoder_count() -> None:
    rows = []
    for decoder in (0, 1):
        for _index in range(4):
            rows.append({"decoder": decoder, "split": "fresh", "visitor": "student", "regret_improvement": float(decoder + 1)})
    values = decoder_values(rows, "fresh", "regret_improvement", expected=4)
    assert values == [1.0, 2.0]
    report = reliable_improvement(values)
    assert report["interval"]["n"] == 2
    assert report["pass"] is False
    with pytest.raises(RuntimeError, match="not 32"):
        decoder_values(rows, "fresh", "regret_improvement", expected=32)


def test_decision_tree_prioritises_reproduction_then_visited_states() -> None:
    common = dict(open_loop_better=True, action_regret_better=True, full_episode_better=False)
    assert decide(reproduction_ok=False, one_shot_better=False, one_shot_worse=True, continuation_better=False, continuation_worse=True, **common) == "planner_implementation"
    assert decide(reproduction_ok=True, one_shot_better=False, one_shot_worse=True, continuation_better=True, continuation_worse=False, **common) == "visited_state_shift"
    assert decide(reproduction_ok=True, one_shot_better=True, one_shot_worse=False, continuation_better=False, continuation_worse=True, **common) == "replanning_or_compounding"
    assert decide(
        reproduction_ok=True, one_shot_better=True, one_shot_worse=False, continuation_better=True, continuation_worse=False,
        open_loop_better=True, action_regret_better=True, full_episode_better=False,
    ) == "unresolved_long_horizon"
    assert decide(
        reproduction_ok=True, one_shot_better=True, one_shot_worse=False, continuation_better=True, continuation_worse=False,
        open_loop_better=True, action_regret_better=True, full_episode_better=True,
    ) == "local_agrees_with_closed_return"
    assert decide(
        reproduction_ok=True, one_shot_better=False, one_shot_worse=False, continuation_better=False, continuation_worse=False,
        open_loop_better=False, action_regret_better=False, full_episode_better=False,
    ) == "inconclusive"
    with pytest.raises(RuntimeError, match="contradict"):
        decide(
            reproduction_ok=True, one_shot_better=True, one_shot_worse=True, continuation_better=False, continuation_worse=False,
            open_loop_better=False, action_regret_better=False, full_episode_better=False,
        )


def test_hash_mismatch_does_not_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "decoder.pt"
    target.write_bytes(b"closed")
    with pytest.raises(RuntimeError, match="refusing to replace"):
        assert_existing_hash(target, "0" * 64)
    assert target.read_bytes() == b"closed"
    with pytest.raises(RuntimeError, match="does not write checkpoints"):
        assert_diagnostic_output_path(tmp_path / "gap.pt")


def test_closed_artifacts_and_checkpoints_match() -> None:
    report = verify_horizon_provenance(load_horizon_config())
    assert report["verified"] is True
    assert report["checkpoints_written"] is False
    assert len(report["decoder_fingerprints"]) == 10
