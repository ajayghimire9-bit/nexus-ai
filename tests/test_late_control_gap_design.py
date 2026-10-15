"""Locks the late-control design. These tests do not collect environment data."""

from pathlib import Path

import numpy as np
import pytest

from nexus.world.late_control_gap_design import (
    architecture_change,
    assert_design_seeds,
    classify_primary,
    common_continuation_seed,
    distance_of_mean,
    estimated_budget,
    load_design_config,
    mean_of_distances,
)

ROOT = Path(__file__).resolve().parents[1]


def test_distance_of_mean_differs_from_mean_of_distances():
    students = np.array([[1.0, 0.0], [-1.0, 0.0]])
    zero = np.array([0.0, 0.0])
    assert distance_of_mean(students, zero) == pytest.approx(0.0)
    assert mean_of_distances(students, zero) == pytest.approx(1.0)
    shared = np.array([[0.3, -0.4], [0.3, -0.4]])
    assert distance_of_mean(shared, zero) == pytest.approx(mean_of_distances(shared, zero))


def test_mean_observation_need_not_be_a_unit_observation():
    students = np.array([[1.0, 0.0], [-1.0, 0.0]])
    mean = students.mean(axis=0)
    assert np.linalg.norm(mean) == pytest.approx(0.0)


def test_design_seeds_are_disjoint_from_closed_blocks():
    assert_design_seeds(load_design_config())


def test_common_continuation_seed_ignores_the_action():
    cfg = load_design_config()
    first = common_continuation_seed(cfg, task_index=2, phase_index=1, slot=4, step=7)
    again = common_continuation_seed(cfg, 2, 1, 4, 7)
    assert first == again
    assert "action" not in common_continuation_seed.__code__.co_varnames


def test_negative_primary_does_not_authorize_an_architecture_change():
    assert classify_primary(-2.0, -3.0, 0.2, 10, 1.0) == "action_quality_not_separated"
    assert classify_primary(-0.4, -0.9, -0.1, 10, 1.0) == "below_practical_threshold"
    assert classify_primary(-1.5, -2.0, -0.5, 10, 1.0) == "same_state_action_worse"
    assert classify_primary(-1.5, -2.0, -0.5, 9, 1.0) == "incomplete"
    for label in ("incomplete", "action_quality_not_separated", "below_practical_threshold", "same_state_action_worse"):
        assert architecture_change(label) is False


def test_budget_matches_the_locked_grid():
    budget = estimated_budget()
    assert budget["states"] == 960
    assert budget["env_steps"] == 381312
    assert budget["model_states"] == 34488320
    assert budget["live_env_steps"] == 48000
    assert budget["common_continuation_env_steps"] == 46080
    assert budget["policy_continuation_env_steps"] == 40960


def test_protocol_and_module_do_not_execute_the_planner():
    source = (ROOT / "src/nexus/world/late_control_gap_design.py").read_text(encoding="utf-8")
    protocol = (ROOT / "docs/NEXUS_LATE_CONTROL_GAP_DESIGN.md").read_text(encoding="utf-8")
    for banned in ("make_task_env", "mpc_for_model", "rollout_controller"):
        assert banned not in source
    assert "same_state_common_continuation" in protocol
    assert "381,312" in protocol
    assert "does not recommend an architecture change" in protocol
    cfg = load_design_config()
    assert cfg["executed"] is False
    assert cfg["mechanism_identified"] is False
    assert cfg["primary_contrast"] == "same_state_common_continuation"
