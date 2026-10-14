from __future__ import annotations

import copy

import pytest
import torch
import yaml

from nexus.world.latent_control import (
    assert_control_seeds,
    assert_protocol_frozen,
    control_gate,
    load_control_config,
    recommend_control,
    verify_student_checkpoints,
)


def test_config_locks_the_planner_and_the_return_margin() -> None:
    cfg = load_control_config()
    assert cfg["horizon"] == 16
    assert cfg["n_candidates"] == 16
    assert cfg["episodes"] == 4
    assert cfg["minimum_effect"] == 25
    assert cfg["enforce_time_budget"] is False
    assert cfg["confirm_task_ids"] == [f"pendulum_lat_cf{i}" for i in range(4)]
    assert_protocol_frozen("docs/NEXUS_LATENT_CONTROL.md", cfg)
    assert_control_seeds(cfg)


def test_drifted_margin_is_rejected(tmp_path) -> None:
    cfg = load_control_config()
    drifted = copy.deepcopy(cfg)
    drifted["minimum_effect"] = 1
    path = tmp_path / "drift.yaml"
    path.write_text(yaml.safe_dump(drifted))
    with pytest.raises(ValueError, match="drifted"):
        load_control_config(path)


def test_missing_protocol_does_not_plan(monkeypatch, tmp_path) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("control started before the protocol check")

    monkeypatch.setattr("nexus.world.latent_control.run_episodes", boom)
    monkeypatch.setattr("nexus.world.latent_generalization._collect", boom)
    from nexus.world.latent_control import run_latent_control

    with pytest.raises(RuntimeError, match="protocol document"):
        run_latent_control(protocol_path=tmp_path / "missing.md")


def test_a_bad_checkpoint_hash_is_not_replaced(tmp_path) -> None:
    cfg = load_control_config()
    path = tmp_path / "encoder.pt"
    torch.save({"w": torch.zeros(584)}, path)
    artifact = {"checkpoints": [{
        "decoder": 0, "student": 0, "kind": "broad", "epoch": 200,
        "path": str(path), "sha256": "0" * 64, "n_parameters": 584,
    }]}
    # The count check is reached only after fifteen files. A single wrong hash fails closed.
    artifact["checkpoints"] = [
        {"decoder": d, "student": s, "kind": kind, "epoch": 200, "path": str(path), "sha256": "0" * 64, "n_parameters": 584}
        for kind in ("broad", "baseline")
        for d in range(3)
        for s in range(5)
    ]
    with pytest.raises(RuntimeError, match="hash mismatch"):
        verify_student_checkpoints(artifact, cfg)
    assert path.is_file()


def test_return_gate_treats_a_crossing_interval_as_inconclusive() -> None:
    passed, report = control_gate([40, 40, 40], [30, 30, 30], 25)
    assert passed is True
    assert report["zero"]["interval"]["df"] == 2
    small, _ = control_gate([10, 10, 10], [30, 30, 30], 25)
    assert small is False
    assert recommend_control(True, [40, 40, 40], [30, 30, 30], [50, 50, 50], 25) == "independent_control_confirmation"
    assert recommend_control(False, [40, 40, -20], [30, 30, 30], [50, 50, 50], 25) == "inconclusive"
    assert recommend_control(False, [10, 10, 10], [12, 12, 12], [5, 5, 5], 25) == "below_minimum_effect"
    assert recommend_control(False, [-30, -30, -30], [-20, -20, -20], [40, 40, 40], 25) == "latent_mismatch"
    assert recommend_control(False, [-30, -30, -30], [-20, -20, -20], [-10, -10, -10], 25) == "planning_mechanism"
    assert recommend_control(False, [40, 40, 40], [-30, -30, -30], [5, 5, 5], 25) == "prediction_control_gap"
