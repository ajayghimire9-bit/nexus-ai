"""Replication rules. These tests do not collect control returns."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from nexus.world.control_replication import (
    NEW_SEEDS,
    ORIGINAL_SEEDS,
    TARGET_DECODERS,
    _locked_config,
    _require_hash,
    action_diagnostics,
    assert_fresh_physics,
    assert_protocol_frozen,
    assert_replication_seeds,
    assert_writable_checkpoint,
    cohort,
    decoder_level_deltas,
    episode_seeds,
    load_replication_config,
    recommend_replication,
    replication_gate,
    schedule_seed,
    source_env0,
    student_rng_seed,
    variance_split,
)
from nexus.world.planning import RandomShootingMPC
from nexus.world.rewards import pendulum_step_reward


def test_original_seeds_are_not_counted_as_new() -> None:
    assert ORIGINAL_SEEDS == (0, 1, 2)
    assert NEW_SEEDS == (3, 4, 5, 6, 7, 8, 9)
    assert set(ORIGINAL_SEEDS).isdisjoint(NEW_SEEDS)
    assert len(ORIGINAL_SEEDS) + len(NEW_SEEDS) == TARGET_DECODERS
    assert cohort(0) == "original"
    assert cohort(9) == "new"
    with pytest.raises(ValueError):
        cohort(10)


def test_new_decoder_seeds_continue_the_locked_schedule() -> None:
    assert schedule_seed(0) == 195_000
    assert schedule_seed(3) == 195_000 + 31 * 3
    assert source_env0(0, 0) == 1000
    assert source_env0(3, 0) == 1300
    assert student_rng_seed(2, 4) == 30_204
    assert student_rng_seed(3, 0) == 30_300


def test_registered_config_keeps_the_recipe_and_the_new_sample() -> None:
    cfg = load_replication_config()
    assert cfg == _locked_config()
    assert cfg["student_learning_rate"] == 0.01
    assert cfg["student_epochs"] == 200
    assert cfg["teacher_updates"] == 256
    assert cfg["context_updates"] == 3000
    assert cfg["history_updates"] == 1000
    assert cfg["minimum_effect"] == 25
    assert cfg["horizon"] == 16 and cfg["n_candidates"] == 16
    assert cfg["previous_control_eval_env0"] == 110000
    assert cfg["replication_eval_env0"] == 120000
    assert cfg["fresh_split_hash"] == "053e8efca60fb4ac"
    assert_protocol_frozen("docs/NEXUS_CONTROL_REPLICATION.md", cfg)
    assert_replication_seeds(cfg)
    specs = assert_fresh_physics(cfg)
    assert [spec.task_id for spec in specs] == [f"pendulum_ctrl_rp{i}" for i in range(4)]
    previous = episode_seeds(110000, 4, 4)
    assert episode_seeds(120000, 4, 4).isdisjoint(previous)
    assert episode_seeds(126000, 4, 4).isdisjoint(previous)


def test_student_seeds_are_averaged_inside_the_decoder() -> None:
    records = []
    for decoder in (0, 1):
        for student in range(5):
            records.append(
                {
                    "split": "replication",
                    "decoder": decoder,
                    "student": student,
                    "task": "t",
                    "label": "student",
                    "mean_return": 100.0 + student + 50.0 * decoder,
                }
            )
        records.append(
            {"split": "replication", "decoder": decoder, "student": None, "task": "t", "label": "zero", "mean_return": 0.0}
        )
    deltas = decoder_level_deltas(records, "zero", "replication", [0, 1])
    assert len(deltas) == 2
    assert deltas[0] == pytest.approx(102.0)
    assert deltas[1] == pytest.approx(152.0)


def test_gate_requires_ten_decoders_and_the_locked_margin() -> None:
    clear = [40.0] * 10
    ok, report = replication_gate(clear, clear, 25, 10)
    assert ok
    assert report["zero"]["lower_bound_exceeds_margin"] is True
    assert report["zero"]["interval"]["n"] == 10
    assert replication_gate(clear[:9], clear[:9], 25, 10)[0] is False
    assert replication_gate([10.0] * 10, clear, 25, 10)[0] is False
    spread = [400.0, *([0.0] * 9)]
    failed, spread_report = replication_gate(spread, clear, 25, 10)
    assert failed is False
    assert spread_report["zero"]["interval"]["lo"] <= 0.0
    assert spread_report["zero"]["interval"]["n"] == 10


def test_episode_variance_does_not_inflate_the_decoder_count() -> None:
    records = []
    for decoder, level in ((3, 10.0), (4, 50.0)):
        for task in ("a", "b"):
            returns = [level, level + 5.0, level - 5.0, level]
            records.append(
                {
                    "split": "fresh",
                    "decoder": decoder,
                    "student": 0,
                    "task": task,
                    "label": "student",
                    "mean_return": float(np.mean(returns)),
                    "returns": returns,
                }
            )
            records.append(
                {
                    "split": "fresh",
                    "decoder": decoder,
                    "student": None,
                    "task": task,
                    "label": "zero",
                    "mean_return": 0.0,
                    "returns": [0.0, 0.0, 0.0, 0.0],
                }
            )
    summary = variance_split(records, "fresh", [3, 4])
    assert summary["n_decoders"] == 2
    assert summary["dominates"] == "decoder"


def test_same_state_agreement_is_separate_from_the_path() -> None:
    records = [
        {
            "split": "replication",
            "decoder": 0,
            "student": 0,
            "task": "t",
            "label": "student",
            "first_actions": [1, 0],
            "first_scores": [[0.2, 0.1], [0.0, 0.4]],
            "action_code": "1100",
            "short_horizon_return": -2.0,
        },
        {
            "split": "replication",
            "decoder": 0,
            "student": None,
            "task": "t",
            "label": "zero",
            "first_actions": [1, 1],
            "first_scores": [[0.2, 0.0], [0.4, 0.0]],
            "action_code": "1000",
            "short_horizon_return": -4.0,
        },
    ]
    summary = action_diagnostics(records, "replication", [0])
    assert summary["first_action_agreement"] == pytest.approx(0.5)
    assert summary["path_action_agreement"] == pytest.approx(0.75)
    assert summary["path_agreement_is_same_state"] is False
    assert summary["short_horizon_student_minus_zero"] == pytest.approx(2.0)


def test_incomplete_grid_cannot_become_a_pass() -> None:
    assert recommend_replication(complete=False, replication_pass=True, fresh_pass=True, prediction_pass=True) == "incomplete"
    assert recommend_replication(complete=True, replication_pass=True, fresh_pass=True, prediction_pass=False) == "cross_task_adaptation_efficiency"
    assert recommend_replication(complete=True, replication_pass=True, fresh_pass=False, prediction_pass=True) == "negative_transfer"
    assert recommend_replication(complete=True, replication_pass=False, fresh_pass=False, prediction_pass=True) == "planner_sensitivity"
    assert recommend_replication(complete=True, replication_pass=False, fresh_pass=False, prediction_pass=False) == "uncertain"


def test_hash_mismatch_does_not_overwrite_and_prior_dirs_are_closed(tmp_path: Path) -> None:
    path = tmp_path / "d3_history_u1000.pt"
    path.write_bytes(b"original-bytes")
    with pytest.raises(RuntimeError):
        _require_hash(path, "0" * 64)
    assert path.read_bytes() == b"original-bytes"
    with pytest.raises(RuntimeError):
        assert_writable_checkpoint(Path("artifacts/frozen_dynamics_checkpoints/seed0_history_u1000.pt"))
    with pytest.raises(RuntimeError):
        assert_writable_checkpoint(Path("artifacts/context_optimization_checkpoints/seed0_context_u3000.pt"))
    with pytest.raises(RuntimeError):
        assert_writable_checkpoint(Path("artifacts/latent_generalization_confirmation_checkpoints/d0_s0_broad_e200.pt"))


class _Flat:
    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        array = np.asarray(obs, dtype=np.float32)
        rows = array.reshape(1, -1) if array.ndim == 1 else array
        return rows.copy(), np.zeros(rows.shape[0], dtype=np.float32)


def test_candidate_scores_are_exported_without_dropping_a_candidate() -> None:
    planner = RandomShootingMPC(
        model=_Flat(),
        n_actions=3,
        horizon=16,
        n_candidates=16,
        seed=5,
        objective="predicted_reward",
        step_reward=pendulum_step_reward,
        enforce_time_budget=False,
    )
    action, meta = planner.act(np.array([1.0, 0.0, 0.0], dtype=np.float32))
    assert action in (0, 1, 2)
    assert meta["n_scored"] == 16
    assert len(meta["candidate_scores"]) == 16
    assert meta["best_score"] == max(meta["candidate_scores"])
