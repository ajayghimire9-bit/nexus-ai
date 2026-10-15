"""Design lock for a late-control gap diagnostic. This module does not collect data."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from nexus.world.prediction_control_gap import diagnostic_seed_groups, load_prediction_config
from nexus.world.receding_horizon import horizon_seed_groups, load_horizon_config
from nexus.world.return_phase import load_phase_config, phase_seed_groups

ROOT = Path(__file__).resolve().parents[3]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _locked_config() -> dict[str, Any]:
    phase = load_phase_config()
    horizon = load_horizon_config()
    return {
        "design_only": True,
        "executed": False,
        "primary_split": "fresh",
        "episodes_per_slot": 1,
        "max_steps": 200,
        "late_steps": [16, 50, 100, 150],
        "continuation_steps": 16,
        "horizon": int(horizon["horizon"]),
        "n_candidates": int(horizon["n_candidates"]),
        "n_actions": 3,
        "n_student_seeds": 5,
        "target_decoders": 10,
        "student_kind": "broad",
        "support_budget": 128,
        "eval_env0": 500000,
        "planner_seed_base": 510000,
        "candidate_seed_base": 520000,
        "common_continuation_base": 530000,
        "policy_continuation_base": 540000,
        "task_stride": 100,
        "practical_threshold": 1.0,
        "time_limit_s": 1800,
        "fresh_split_hash": phase["fresh_split_hash"],
        "fresh_support_hashes": list(phase["fresh_support_hashes"]),
        "return_phase_artifact_sha256": _sha256(ROOT / "artifacts/return_phase_decomposition.json"),
        "receding_artifact_sha256": _sha256(ROOT / "artifacts/receding_horizon_diagnostic.json"),
        "prediction_artifact_sha256": _sha256(ROOT / "artifacts/prediction_control_gap.json"),
        "primary_contrast": "same_state_common_continuation",
        "secondary_contrast": "same_state_policy_continuation",
        "statistical_unit": "decoder",
        "architecture_change_authorized": False,
        "mechanism_identified": False,
    }


def load_design_config(path: Path | None = None) -> dict[str, Any]:
    payload = yaml.safe_load((path or ROOT / "configs/late_control_gap_design.yaml").read_text(encoding="utf-8"))
    if payload != _locked_config():
        raise ValueError("late-control design config drifted")
    return payload


def distance_of_mean(student_obs: np.ndarray, zero_obs: np.ndarray) -> np.ndarray:
    """L2 between the mean student observation and zero context.

    This is the quantity stored by the return-phase study.
    """
    mean_obs = np.asarray(student_obs, dtype=np.float64).mean(axis=0)
    return np.linalg.norm(mean_obs - np.asarray(zero_obs, dtype=np.float64), axis=-1)


def mean_of_distances(student_obs: np.ndarray, zero_obs: np.ndarray) -> np.ndarray:
    """Mean across students of each student's L2 distance to zero context."""
    students = np.asarray(student_obs, dtype=np.float64)
    zero = np.asarray(zero_obs, dtype=np.float64)
    return np.linalg.norm(students - zero, axis=-1).mean(axis=0)


def episode_seed(cfg: dict[str, Any], kind: str, task_index: int, slot: int) -> int:
    bases = {"env": "eval_env0", "planner": "planner_seed_base"}
    return int(cfg[bases[kind]]) + int(cfg["task_stride"]) * int(task_index) + int(slot)


def state_seed(cfg: dict[str, Any], kind: str, task_index: int, phase_index: int, slot: int) -> int:
    """State seed. Slot spacing is 20, so continuation steps 0–15 do not collide."""
    bases = {
        "candidate": "candidate_seed_base",
        "common": "common_continuation_base",
        "policy": "policy_continuation_base",
    }
    return int(cfg[bases[kind]]) + int(task_index) * 2000 + int(phase_index) * 200 + int(slot) * 20


def common_continuation_seed(cfg: dict[str, Any], task_index: int, phase_index: int, slot: int, step: int) -> int:
    """Continuation step seed. It does not depend on the committed action."""
    return state_seed(cfg, "common", task_index, phase_index, slot) + int(step)


def design_seed_groups(cfg: dict[str, Any] | None = None) -> dict[str, set[int]]:
    cfg = cfg or load_design_config()
    groups: dict[str, set[int]] = {}
    n_tasks = 4
    n_slots = int(cfg["n_student_seeds"]) + 1
    n_phases = len(cfg["late_steps"])
    groups["env"] = {episode_seed(cfg, "env", task, slot) for task in range(n_tasks) for slot in range(n_slots)}
    groups["planner"] = {episode_seed(cfg, "planner", task, slot) for task in range(n_tasks) for slot in range(n_slots)}
    groups["candidate"] = {state_seed(cfg, "candidate", task, phase, slot) for task in range(n_tasks) for phase in range(n_phases) for slot in range(n_slots)}
    groups["common"] = {
        common_continuation_seed(cfg, task, phase, slot, step)
        for task in range(n_tasks)
        for phase in range(n_phases)
        for slot in range(n_slots)
        for step in range(int(cfg["continuation_steps"]))
    }
    groups["policy"] = {
        state_seed(cfg, "policy", task, phase, slot) + step
        for task in range(n_tasks)
        for phase in range(n_phases)
        for slot in range(n_slots)
        for step in range(int(cfg["continuation_steps"]))
    }
    return groups


def assert_design_seeds(cfg: dict[str, Any] | None = None) -> None:
    cfg = cfg or load_design_config()
    groups = design_seed_groups(cfg)
    occupied: set[int] = set()
    prediction_occupied, prediction_groups = diagnostic_seed_groups(load_prediction_config())
    priors = (prediction_occupied, prediction_groups, horizon_seed_groups(load_horizon_config()), phase_seed_groups(load_phase_config()))
    for prior in priors:
        for values in prior.values():
            occupied.update(values)
    expected = {
        "env": 4 * (int(cfg["n_student_seeds"]) + 1),
        "planner": 4 * (int(cfg["n_student_seeds"]) + 1),
        "candidate": 4 * len(cfg["late_steps"]) * (int(cfg["n_student_seeds"]) + 1),
        "common": 4 * len(cfg["late_steps"]) * (int(cfg["n_student_seeds"]) + 1) * int(cfg["continuation_steps"]),
        "policy": 4 * len(cfg["late_steps"]) * (int(cfg["n_student_seeds"]) + 1) * int(cfg["continuation_steps"]),
    }
    for name, values in groups.items():
        if len(values) != expected[name]:
            raise ValueError(f"{name} seeds are not unique")
        overlap = values & occupied
        if overlap:
            raise ValueError(f"{name} overlaps a closed seed")
        occupied.update(values)
    if groups["env"] & groups["planner"]:
        raise ValueError("env and planner seeds overlap")


def classify_primary(mean: float, lo: float, hi: float, n: int, threshold: float) -> str:
    if int(n) != 10:
        return "incomplete"
    if not (hi < 0.0):
        return "action_quality_not_separated"
    if float(mean) > -float(threshold):
        return "below_practical_threshold"
    return "same_state_action_worse"


def architecture_change(label: str) -> bool:
    return False


def estimated_budget(cfg: dict[str, Any] | None = None) -> dict[str, int]:
    """Interaction count implied by the locked grid. This is not a measurement."""
    cfg = cfg or load_design_config()
    decoders = int(cfg["target_decoders"])
    tasks = 4
    students = int(cfg["n_student_seeds"])
    slots = students + 1
    phases = len(cfg["late_steps"])
    steps = int(cfg["max_steps"])
    horizon = int(cfg["horizon"])
    candidates = int(cfg["n_candidates"])
    actions = int(cfg["n_actions"])
    continuation = int(cfg["continuation_steps"])
    plan = horizon * candidates
    groups = decoders * tasks * phases
    states = groups * slots
    support_env = tasks * int(cfg["support_budget"])
    live_env = decoders * tasks * slots * int(cfg["episodes_per_slot"]) * steps
    open_loop_env = states * plan
    common_env = states * actions * continuation
    policy_env = groups * (students * 2 + (students + 1)) * continuation
    live_model = live_env * plan
    score_model = groups * (students * 2 * plan + (students + 1) * plan)
    common_model = states * actions * (continuation - 1) * plan
    policy_model = groups * (students * 2 + (students + 1)) * continuation * plan
    return {
        "states": states,
        "env_steps": support_env + live_env + open_loop_env + common_env + policy_env,
        "model_states": live_model + score_model + common_model + policy_model,
        "support_env_steps": support_env,
        "live_env_steps": live_env,
        "open_loop_env_steps": open_loop_env,
        "common_continuation_env_steps": common_env,
        "policy_continuation_env_steps": policy_env,
    }
