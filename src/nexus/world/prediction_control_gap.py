"""Same-state diagnostic for the prediction-to-control gap. Not a new controller.

The ten-decoder H=16 returns stay closed. This module scores one shared set of
candidate sequences with the saved zero-context and student-context models, then
compares those scores with simulator returns from the same reset. It does not
train, does not edit checkpoints, and does not change the planner.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import pendulum_latent_confirmation, pendulum_physics_key
from nexus.tasks.spec import make_task_env
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_optimization import _sha256
from nexus.world.context_pilot import prefix_hash
from nexus.world.control_replication import (
    MANIFEST_PATH,
    NEW_SEEDS,
    ORIGINAL_SEEDS,
    TARGET_DECODERS,
    _collect_named,
    _confirmation_artifact,
    _decoder_file,
    _fresh_decoder,
    _global_vector,
    _install_encoder,
    _pearson,
    _spearman,
    _student_rows,
    assert_fresh_physics,
    assert_writable_checkpoint,
    load_replication_config,
    replication_seed_groups,
)
from nexus.world.frozen_dynamics import planned_env_seeds
from nexus.world.latent_generalization import assert_checkpoint_hashes, decoder_digest, load_generalization_config
from nexus.world.latent_control import verify_student_checkpoints
from nexus.world.planning import mpc_for_model
from nexus.world.rewards import pendulum_step_reward
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/prediction_control_gap.yaml")
PROTOCOL_PATH = Path("docs/NEXUS_PREDICTION_CONTROL_GAP.md")
SELECTION_ATOL = 1e-8
REQUIRED_DECODERS = 10
CONTEXT_DIM = 8

RECOMMENDATIONS = {
    "objective_misaligned": (
        "The present prediction objective is insufficiently aligned with planning decisions on these physics. "
        "A later experiment should measure and improve action-ranking accuracy on held-out physics. "
        "Do not change the architecture in this study."
    ),
    "receding_horizon": (
        "Candidate action ranking improved while the closed full-episode return did not, and the H=16 reward "
        "forecast did not reliably improve. A later experiment should measure receding-horizon sensitivity and "
        "distribution shift. Do not change the architecture in this study."
    ),
    "evaluation_variance": (
        "Action ranking and the H=16 reward forecast both improved. Audit evaluation variance and the planning "
        "implementation before any architecture change. Do not change the architecture in this study."
    ),
    "planning_metrics_agree": (
        "Action ranking and the H=16 reward forecast improved on a split whose closed full-episode return also "
        "favored the student. That agreement is a contrast with the fresh split, not a new control claim. "
        "Do not change the architecture in this study."
    ),
    "inconclusive": (
        "The decoder-level intervals do not separate the pre-registered branches. "
        "Do not change the architecture on this sample."
    ),
    "incomplete": "The diagnostic grid did not finish inside the locked budget. No mechanism conclusion is available.",
    "blocked_dirty_tree": "The source tree was dirty, so this run does not record a mechanism conclusion.",
}


def load_prediction_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("prediction-control config must be a mapping")
    expected = _locked_config()
    if cfg != expected:
        missing = sorted(set(expected) - set(cfg))
        extra = sorted(set(cfg) - set(expected))
        drifted = sorted(key for key in expected if key in cfg and cfg[key] != expected[key])
        raise ValueError(f"prediction-control config drifted; missing={missing} extra={extra} drifted={drifted}")
    if int(cfg["target_decoders"]) != REQUIRED_DECODERS or int(cfg["horizon"]) != 16 or int(cfg["n_candidates"]) != 16:
        raise ValueError("planner budget drifted")
    if cfg["primary_split"] != "fresh" or cfg["ranking_metric"] != "regret":
        raise ValueError("primary comparison drifted")
    if bool(cfg["full_episode_remeasured"]) or bool(cfg["fresh_full_episode_student_better"]):
        raise ValueError("closed control facts drifted")
    if int(cfg["states_per_physics"]) > int(cfg["seed_stride"]):
        raise ValueError("state seeds would overlap the next physics block")
    return cfg


def _locked_config() -> dict[str, Any]:
    rep = load_replication_config()
    if int(rep["previous_control_eval_env0"]) != 110000 or int(rep["replication_eval_env0"]) != 120000:
        raise ValueError("closed control episode seeds drifted")
    if int(rep["fresh_eval_env0"]) != 126000 or int(rep["fresh_support_env0"]) != 124000:
        raise ValueError("closed fresh seeds drifted")
    if int(rep["confirm_support_env0"]) != 102000 or int(rep["support_budget"]) != 128:
        raise ValueError("closed confirmation support drifted")
    if int(rep["n_parameters"]) != 584 or int(rep["n_decoder_parameters"]) != 3748:
        raise ValueError("model size drifted")
    return {
        "protocol_id": "prediction_control_gap_v1",
        "starting_sha": "af32a0398375b72d534417b6459638fedac41297",
        "manifest_sha256": "265cd1822ec73bab8eac6fd792438c3c9fe7834ae5af307b8c33104bf919d06b",
        "control_artifact": "artifacts/control_replication.json",
        "control_artifact_sha256": "35c75320e1c243eaa1914cf6e726e9849d246910ebfc79f6ac0f390c86daf0e9",
        "is_agi": False,
        "is_learning_to_learn": False,
        "control_claim": False,
        "full_episode_remeasured": False,
        "fresh_full_episode_student_better": False,
        "replication_full_episode_student_better": True,
        "primary_split": "fresh",
        "target_decoders": TARGET_DECODERS,
        "original_seeds": list(ORIGINAL_SEEDS),
        "new_seeds": list(NEW_SEEDS),
        "n_student_seeds": int(rep["n_student_seeds"]),
        "student_kind": "broad",
        "n_parameters": int(rep["n_parameters"]),
        "n_decoder_parameters": int(rep["n_decoder_parameters"]),
        "horizon": 16,
        "n_candidates": 16,
        "n_actions": 3,
        "states_per_physics": 16,
        "recorded_transitions": 128,
        "seed_stride": 20,
        "support_budget": int(rep["support_budget"]),
        "replication_state_env0": 140000,
        "fresh_state_env0": 142000,
        "replication_recorded_env0": 144000,
        "fresh_recorded_env0": 146000,
        "candidate_rng_base": 151000,
        "recorded_action_base": 147000,
        "time_limit_s": 1800,
        "selection_atol": format(SELECTION_ATOL, ".0e"),
        "ranking_metric": "regret",
        "prediction_metric": "candidate_one_step_angvel",
        "reward_metric": "absolute_planner_score_error",
        "primary_unit": "decoder",
        "confirm_split_hash": rep["confirm_split_hash"],
        "fresh_split_hash": rep["fresh_split_hash"],
        "replication_task_ids": list(rep["replication_task_ids"]),
        "fresh_task_ids": list(rep["fresh_task_ids"]),
        "replication_physics": [list(row) for row in rep["replication_physics"]],
        "fresh_physics": [list(row) for row in rep["fresh_physics"]],
        "confirm_support_env0": int(rep["confirm_support_env0"]),
        "confirm_support_base": int(rep["confirm_support_base"]),
        "fresh_support_env0": int(rep["fresh_support_env0"]),
        "fresh_support_base": int(rep["fresh_support_base"]),
        "closed_previous_control_eval_env0": int(rep["previous_control_eval_env0"]),
        "closed_replication_eval_env0": int(rep["replication_eval_env0"]),
        "closed_fresh_eval_env0": int(rep["fresh_eval_env0"]),
        "closed_fresh_support_env0": int(rep["fresh_support_env0"]),
    }


def assert_protocol_frozen(protocol_path: str | Path, cfg: dict[str, Any]) -> None:
    path = Path(protocol_path)
    if not path.is_file():
        raise RuntimeError("diagnostic is blocked until the protocol document is saved")
    text = path.read_text()
    start = text.find("<!-- protocol-lock")
    end = text.find("-->", start)
    if start < 0 or end < 0:
        raise RuntimeError("diagnostic is blocked because the protocol lock block is missing")
    locked: dict[str, str] = {}
    for line in text[start:end].splitlines():
        if ":" not in line or line.strip().startswith("<!--"):
            continue
        key, value = line.split(":", 1)
        locked[key.strip()] = value.strip()
    expected = {
        "states_per_physics": str(int(cfg["states_per_physics"])),
        "recorded_transitions": str(int(cfg["recorded_transitions"])),
        "horizon": str(int(cfg["horizon"])),
        "n_candidates": str(int(cfg["n_candidates"])),
        "n_actions": str(int(cfg["n_actions"])),
        "target_decoders": str(int(cfg["target_decoders"])),
        "n_student_seeds": str(int(cfg["n_student_seeds"])),
        "primary_split": str(cfg["primary_split"]),
        "seed_stride": str(int(cfg["seed_stride"])),
        "replication_state_env0": str(int(cfg["replication_state_env0"])),
        "fresh_state_env0": str(int(cfg["fresh_state_env0"])),
        "replication_recorded_env0": str(int(cfg["replication_recorded_env0"])),
        "fresh_recorded_env0": str(int(cfg["fresh_recorded_env0"])),
        "candidate_rng_base": str(int(cfg["candidate_rng_base"])),
        "recorded_action_base": str(int(cfg["recorded_action_base"])),
        "time_limit_s": str(int(cfg["time_limit_s"])),
        "starting_sha": str(cfg["starting_sha"]),
        "manifest_sha256": str(cfg["manifest_sha256"]),
        "control_artifact_sha256": str(cfg["control_artifact_sha256"]),
        "confirm_split_hash": str(cfg["confirm_split_hash"]),
        "fresh_split_hash": str(cfg["fresh_split_hash"]),
        "ranking_metric": str(cfg["ranking_metric"]),
        "prediction_metric": str(cfg["prediction_metric"]),
        "reward_metric": str(cfg["reward_metric"]),
        "selection_atol": str(cfg["selection_atol"]),
        "full_episode_remeasured": "false",
        "fresh_full_episode_student_better": "false",
        "replication_full_episode_student_better": "true",
        "support_budget": str(int(cfg["support_budget"])),
        "closed_previous_control_eval_env0": str(int(cfg["closed_previous_control_eval_env0"])),
        "closed_replication_eval_env0": str(int(cfg["closed_replication_eval_env0"])),
        "closed_fresh_eval_env0": str(int(cfg["closed_fresh_eval_env0"])),
        "closed_fresh_support_env0": str(int(cfg["closed_fresh_support_env0"])),
    }
    for key, value in expected.items():
        if locked.get(key) != value:
            raise RuntimeError(f"protocol lock drifted for {key}: document={locked.get(key)!r} config={value!r}")


def state_seed(env0: int, task_index: int, state_index: int, stride: int = 20) -> int:
    return int(env0) + int(stride) * int(task_index) + int(state_index)


def candidate_seed(base: int, split_index: int, task_index: int, state_index: int) -> int:
    return int(base) + int(split_index) * 10000 + int(task_index) * 100 + int(state_index)


def candidate_sequences(seed: int, n_candidates: int = 16, horizon: int = 16, n_actions: int = 3) -> np.ndarray:
    rng = np.random.default_rng(int(seed))
    return rng.integers(0, int(n_actions), size=(int(n_candidates), int(horizon)), dtype=np.int64)


def collector_seed_span(n_transitions: int, env0: int) -> set[int]:
    """Seeds passed to the collector, including the unused slots in its env range."""
    n_env = max(2, min(8, max(1, int(n_transitions) // 32)))
    return set(range(int(env0), int(env0) + n_env)) | planned_env_seeds(int(n_transitions), int(env0))


def diagnostic_seed_groups(cfg: dict[str, Any]) -> tuple[dict[str, set[int]], dict[str, set[int]]]:
    occupied = replication_seed_groups(load_replication_config())
    groups: dict[str, set[int]] = {}
    n_tasks = len(cfg["replication_task_ids"])
    if n_tasks != len(cfg["fresh_task_ids"]):
        raise ValueError("physics splits do not have equal task counts")
    stride = int(cfg["seed_stride"])
    for name, env0 in (
        ("replication_state", int(cfg["replication_state_env0"])),
        ("fresh_state", int(cfg["fresh_state_env0"])),
    ):
        groups[name] = {
            state_seed(env0, task, index, stride)
            for task in range(n_tasks)
            for index in range(int(cfg["states_per_physics"]))
        }
    for name, env0 in (
        ("replication_recorded", int(cfg["replication_recorded_env0"])),
        ("fresh_recorded", int(cfg["fresh_recorded_env0"])),
    ):
        seeds: set[int] = set()
        for task in range(n_tasks):
            seeds |= collector_seed_span(int(cfg["recorded_transitions"]), int(env0) + stride * task)
        groups[name] = seeds
    groups["candidate_rng"] = {
        candidate_seed(int(cfg["candidate_rng_base"]), split, task, index)
        for split in range(2)
        for task in range(n_tasks)
        for index in range(int(cfg["states_per_physics"]))
    }
    return occupied, groups


def assert_diagnostic_seeds(cfg: dict[str, Any]) -> None:
    occupied, groups = diagnostic_seed_groups(cfg)
    blocked: set[int] = set()
    for seeds in occupied.values():
        blocked |= seeds
    fresh = list(groups)
    for name in fresh:
        overlap = groups[name] & blocked
        if overlap:
            raise ValueError(f"{name} reuses a closed seed: {sorted(overlap)[:8]}")
        blocked |= groups[name]
    if len(groups["replication_state"]) != len(groups["fresh_state"]):
        raise ValueError("state budgets are not equal across splits")
    if len(groups["replication_recorded"]) != len(groups["fresh_recorded"]):
        raise ValueError("recorded budgets are not equal across splits")
    per_physics = int(cfg["states_per_physics"])
    n_tasks = len(cfg["replication_task_ids"])
    if len(groups["replication_state"]) != per_physics * n_tasks:
        raise ValueError("state seeds are not unique")


def assert_diagnostic_output_path(path: str | Path) -> Path:
    target = assert_writable_checkpoint(path)
    if target.suffix == ".pt":
        raise RuntimeError("this diagnostic does not write checkpoints")
    return target


def assert_existing_hash(path: str | Path, expected: str) -> None:
    """Reject a hash miss. The file is left untouched."""
    target = Path(path)
    before = target.read_bytes() if target.is_file() else None
    try:
        if not target.is_file():
            raise FileNotFoundError(target)
        got = _sha256(target)
        if got != expected:
            raise RuntimeError(f"checkpoint hash mismatch for {target}; refusing to replace it")
    finally:
        if before is not None and target.is_file() and target.read_bytes() != before:
            raise RuntimeError(f"hash check rewrote {target}")


def verify_provenance(cfg: dict[str, Any]) -> dict[str, Any]:
    """Check the closed checkpoints and stop. This does not train or score actions."""
    rep = load_replication_config()
    artifact_path = Path(cfg["control_artifact"])
    artifact_sha = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    if artifact_sha != cfg["control_artifact_sha256"]:
        raise RuntimeError("closed control artifact hash mismatch")
    artifact = __import__("json").loads(artifact_path.read_text())
    manifest_bytes = MANIFEST_PATH.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != cfg["manifest_sha256"]:
        raise RuntimeError("checkpoint manifest hash mismatch")
    manifest = __import__("json").loads(manifest_bytes)
    if manifest != artifact.get("checkpoint_manifest"):
        raise RuntimeError("manifest does not match the closed replication artifact")
    assert_checkpoint_hashes(load_generalization_config())
    confirmation = _confirmation_artifact(rep)
    verify_student_checkpoints(
        confirmation,
        {"n_decoder_seeds": 3, "n_student_seeds": int(cfg["n_student_seeds"]), "n_parameters": int(cfg["n_parameters"])},
    )
    selection = __import__("json").loads(Path(load_generalization_config()["prior_selection"]).read_text())["selection_record"]
    expected_digests = list(confirmation["reproduction"]["decoder_digests"])
    if len(expected_digests) != len(ORIGINAL_SEEDS):
        raise RuntimeError("original decoder fingerprints are incomplete")
    fingerprints = []
    for seed in list(ORIGINAL_SEEDS) + list(NEW_SEEDS):
        path = _decoder_file(int(seed), rep)
        _student_rows(int(seed), "broad", rep, confirmation)
        _student_rows(int(seed), "baseline", rep, confirmation)
        _global_vector(int(seed), rep, selection)
        model, digest = _fresh_decoder(path, rep)
        if int(model.context_dim()) != CONTEXT_DIM:
            raise RuntimeError("context dimension drifted")
        if int(seed) in ORIGINAL_SEEDS and digest != expected_digests[int(seed)]:
            raise RuntimeError(f"frozen decoder fingerprint mismatch for seed {seed}")
        if decoder_digest(model) != digest:
            raise RuntimeError("loading a decoder changed its fingerprint")
        fingerprints.append({"seed": int(seed), "decoder_digest": digest, "path": path})
        del model
    return {
        "verified": True,
        "decoder_fingerprints": fingerprints,
        "manifest_sha256": cfg["manifest_sha256"],
        "control_artifact_sha256": artifact_sha,
        "global_vectors_checked": True,
        "baseline_students_checked": True,
        "checkpoints_written": False,
    }


def rollout_sequence(spec: Any, reset_seed: int, actions: np.ndarray | list[int]) -> dict[str, Any]:
    """Replay one action sequence from a registered reset. The model is not called."""
    env = make_task_env(spec)
    try:
        obs, _info = env.reset(seed=int(reset_seed))
        obs = np.asarray(obs, dtype=np.float32).reshape(-1)
        obs0 = obs.copy()
        rewards: list[float] = []
        published: list[float] = []
        nxts: list[np.ndarray] = []
        for action in np.asarray(actions, dtype=np.int64).reshape(-1):
            nxt, reward, terminated, truncated, _info = env.step(int(action))
            nxt_arr = np.asarray(nxt, dtype=np.float32).reshape(-1)
            published_reward = float(np.asarray(pendulum_step_reward(obs, int(action), nxt_arr), dtype=np.float64).reshape(-1)[0])
            if abs(float(reward) - published_reward) > 1e-5:
                raise RuntimeError("environment reward does not match the published pendulum cost")
            rewards.append(float(reward))
            published.append(published_reward)
            nxts.append(nxt_arr.copy())
            obs = nxt_arr
            if terminated or truncated:
                break
        if len(rewards) != int(np.asarray(actions).reshape(-1).size):
            raise RuntimeError("rollout ended before the candidate horizon")
        return {
            "obs0": obs0,
            "rewards": np.asarray(rewards, dtype=np.float64),
            "published": np.asarray(published, dtype=np.float64),
            "next_obs": np.stack(nxts, axis=0),
            "return": float(np.sum(rewards)),
        }
    finally:
        env.close()


def planner_scores(model: Any, obs: np.ndarray, sequences: np.ndarray) -> np.ndarray:
    """Score a shared candidate set with the existing planner objective.

    The simulator return is not an argument. Hidden physics parameters are not arguments.
    """
    sequences = np.asarray(sequences, dtype=np.int64)
    if sequences.ndim != 2:
        raise ValueError("candidate sequences must be a matrix")
    planner = mpc_for_model(model, seed=0, enforce_time_budget=False)
    if int(planner.horizon) != int(sequences.shape[1]) or int(planner.n_candidates) != int(sequences.shape[0]):
        raise ValueError("candidate set does not match the locked planner budget")
    if int(planner.n_actions) != 3 or planner.step_reward is not pendulum_step_reward:
        raise ValueError("planner reward drifted")
    before = model.z.detach().clone() if getattr(model, "z", None) is not None else None
    scores = np.asarray(planner._score_batch(np.asarray(obs, dtype=np.float32), sequences), dtype=np.float64)
    if before is not None and not torch.equal(model.z.detach(), before):
        raise RuntimeError("scoring changed the context vector")
    if scores.shape != (sequences.shape[0],):
        raise RuntimeError("planner dropped a candidate")
    return scores


def decision_metrics(predicted: np.ndarray, actual: np.ndarray, sequences: np.ndarray, *, atol: float = SELECTION_ATOL) -> dict[str, Any]:
    predicted = np.asarray(predicted, dtype=np.float64).reshape(-1)
    actual = np.asarray(actual, dtype=np.float64).reshape(-1)
    sequences = np.asarray(sequences, dtype=np.int64)
    if predicted.shape != actual.shape or predicted.shape[0] != sequences.shape[0]:
        raise ValueError("candidate scores, returns, and sequences are not paired")
    if not np.isfinite(predicted).all() or not np.isfinite(actual).all():
        raise RuntimeError("candidate scores or returns are not finite")
    selected = int(np.argmax(predicted))
    best = float(np.max(actual))
    chosen = float(actual[selected])
    return {
        "selected": selected,
        "first_action": int(sequences[selected, 0]),
        "regret": float(best - chosen),
        "correct": bool(chosen >= best - float(atol)),
        "spearman": float(_spearman(predicted.tolist(), actual.tolist())),
        "reward_mae": float(np.mean(np.abs(predicted - actual))),
    }


def trajectory_prediction_errors(model: Any, obs0: np.ndarray, sequences: np.ndarray, actual_next: np.ndarray) -> dict[str, float]:
    sequences = np.asarray(sequences, dtype=np.int64)
    actual_next = np.asarray(actual_next, dtype=np.float32)
    n, horizon = sequences.shape
    if actual_next.shape != (n, horizon, 3):
        raise ValueError("actual trajectory is not paired with the candidate set")
    imagined = np.repeat(np.asarray(obs0, dtype=np.float32).reshape(1, -1), n, axis=0)
    teacher = imagined.copy()
    open_ang: list[np.ndarray] = []
    one_ang: list[np.ndarray] = []
    open_state: list[np.ndarray] = []
    one_state: list[np.ndarray] = []
    for step_index in range(horizon):
        nxt_open, _p_open = model.step(imagined, sequences[:, step_index])
        nxt_one, _p_one = model.step(teacher, sequences[:, step_index])
        real = actual_next[:, step_index]
        open_ang.append(np.abs(nxt_open[:, 2] - real[:, 2]))
        one_ang.append(np.abs(nxt_one[:, 2] - real[:, 2]))
        open_state.append(np.mean(np.abs(nxt_open - real), axis=1))
        one_state.append(np.mean(np.abs(nxt_one - real), axis=1))
        imagined = np.asarray(nxt_open, dtype=np.float32)
        teacher = real
    return {
        "open_loop_angvel": float(np.mean(np.concatenate(open_ang))),
        "one_step_angvel": float(np.mean(np.concatenate(one_ang))),
        "open_loop_state": float(np.mean(np.concatenate(open_state))),
        "one_step_state": float(np.mean(np.concatenate(one_state))),
    }


def dataset_one_step(model: Any, dataset: Any) -> dict[str, float]:
    pred, _p = model.step(dataset.obs, dataset.action)
    real = np.asarray(dataset.next_obs, dtype=np.float32)
    pred = np.asarray(pred, dtype=np.float32)
    if pred.shape != real.shape:
        raise RuntimeError("one-step prediction is not paired with the recorded transition")
    return {
        "one_step_angvel": float(np.mean(np.abs(pred[:, 2] - real[:, 2]))),
        "one_step_state": float(np.mean(np.abs(pred - real))),
    }


def average_student_metric(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        raise RuntimeError("student aggregate is empty")
    return float(np.mean([float(row[key]) for row in rows]))


def split_decoder_values(rows: list[dict[str, Any]], split: str, key: str, *, tasks: int) -> list[float]:
    grouped: dict[int, list[float]] = {}
    for row in rows:
        if row["split"] != split:
            continue
        grouped.setdefault(int(row["decoder"]), []).append(float(row[key]))
    values = []
    for decoder in sorted(grouped):
        if len(grouped[decoder]) != int(tasks):
            raise RuntimeError(f"decoder {decoder} does not have {tasks} {split} tasks")
        values.append(float(np.mean(grouped[decoder])))
    return values


def task_decoder_values(rows: list[dict[str, Any]], split: str, task: str, key: str) -> list[float]:
    found = [(int(row["decoder"]), float(row[key])) for row in rows if row["split"] == split and row["task"] == task]
    found.sort(key=lambda item: item[0])
    return [value for _decoder, value in found]


def reliable_improvement(values: list[float], *, required_n: int = REQUIRED_DECODERS) -> dict[str, Any]:
    interval = seed_level_ci([float(value) for value in values])
    mean = interval.get("mean")
    lo = interval.get("lo")
    passed = (
        int(interval.get("n") or 0) == int(required_n)
        and mean is not None
        and lo is not None
        and float(mean) > 0.0
        and float(lo) > 0.0
    )
    return {
        "per_decoder": [float(value) for value in values],
        "interval": interval,
        "pass": bool(passed),
        "required_n": int(required_n),
    }


def decide(
    *,
    state_better: bool,
    ranking_better: bool,
    ranking_worse: bool,
    reward_better: bool,
    full_episode_better: bool,
) -> str:
    """Pre-registered branch. More specific planning-metric agreement is tested before the horizon branch."""
    if ranking_better and ranking_worse:
        raise RuntimeError("ranking flags contradict")
    if state_better and ranking_worse:
        return "objective_misaligned"
    if ranking_better and reward_better:
        return "evaluation_variance" if not full_episode_better else "planning_metrics_agree"
    if ranking_better and not full_episode_better:
        return "receding_horizon"
    return "inconclusive"


def gap_sentence(*, state_better: bool, ranking_better: bool, ranking_worse: bool, reward_better: bool) -> str:
    prediction = (
        "Student one-step angular-velocity error is lower."
        if state_better
        else "Student one-step angular-velocity error is not reliably lower."
    )
    if ranking_worse:
        ranking = "Student regret on the shared candidates is higher."
    elif ranking_better:
        ranking = "Student regret on the shared candidates is lower."
    else:
        ranking = "The regret interval does not separate the student from zero context."
    reward = (
        "The absolute H=16 reward-forecast error is lower."
        if reward_better
        else "The absolute H=16 reward-forecast error is not reliably lower."
    )
    return f"{prediction} {ranking} {reward}"


def _mean_rows(rows: list[dict[str, Any]], key: str) -> float:
    return float(np.mean([float(row[key]) for row in rows]))


def _score_context(model: Any, states: list[dict[str, Any]], zero_actions: list[int] | None) -> dict[str, Any]:
    metrics = []
    errors = []
    actions = []
    disagreements = []
    for index, state in enumerate(states):
        scores = planner_scores(model, state["obs"], state["sequences"])
        row = decision_metrics(scores, state["returns"], state["sequences"])
        metrics.append(row)
        errors.append(trajectory_prediction_errors(model, state["obs"], state["sequences"], state["next_obs"]))
        actions.append(int(row["first_action"]))
        if zero_actions is not None:
            disagreements.append(float(int(row["first_action"]) != int(zero_actions[index])))
    return {
        "regret": _mean_rows(metrics, "regret"),
        "correct": _mean_rows(metrics, "correct"),
        "spearman": _mean_rows(metrics, "spearman"),
        "reward_mae": _mean_rows(metrics, "reward_mae"),
        "one_step_angvel": _mean_rows(errors, "one_step_angvel"),
        "open_loop_angvel": _mean_rows(errors, "open_loop_angvel"),
        "one_step_state": _mean_rows(errors, "one_step_state"),
        "open_loop_state": _mean_rows(errors, "open_loop_state"),
        "first_actions": actions,
        "disagreement": float(np.mean(disagreements)) if disagreements else 0.0,
        "model_states": int(len(states) * states[0]["sequences"].shape[0] * states[0]["sequences"].shape[1] * 3),
    }


def _build_states(spec: Any, env0: int, task_index: int, split_index: int, cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    states = []
    env_steps = 0
    horizon = int(cfg["horizon"])
    for index in range(int(cfg["states_per_physics"])):
        reset = state_seed(env0, task_index, index, int(cfg["seed_stride"]))
        seed = candidate_seed(int(cfg["candidate_rng_base"]), split_index, task_index, index)
        sequences = candidate_sequences(seed, int(cfg["n_candidates"]), horizon, int(cfg["n_actions"]))
        returns = []
        next_obs = []
        obs0 = None
        for sequence in sequences:
            rolled = rollout_sequence(spec, reset, sequence)
            if obs0 is None:
                obs0 = rolled["obs0"]
            elif not np.array_equal(obs0, rolled["obs0"]):
                raise RuntimeError(f"reset {reset} did not reproduce the registered state")
            returns.append(rolled["return"])
            next_obs.append(rolled["next_obs"])
            env_steps += horizon
        states.append({
            "reset_seed": reset,
            "candidate_seed": seed,
            "obs": obs0,
            "sequences": sequences,
            "returns": np.asarray(returns, dtype=np.float64),
            "next_obs": np.stack(next_obs, axis=0),
        })
    return states, env_steps


def _table_hash(states: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for state in states:
        digest.update(np.ascontiguousarray(state["obs"], dtype=np.float32).tobytes())
        digest.update(np.ascontiguousarray(state["sequences"], dtype=np.int64).tobytes())
    return digest.hexdigest()


def _collect_supports(rep: dict[str, Any], cfg: dict[str, Any]) -> tuple[list[Any], list[Any], list[str], int]:
    forbidden = set(load_generalization_config()["forbidden_task_ids"])
    confirmation = _confirmation_artifact(rep)
    budget = int(cfg["support_budget"])
    replication_supports = []
    for index, spec in enumerate(pendulum_latent_confirmation()):
        support = _collect_named(
            spec,
            budget,
            int(cfg["confirm_support_env0"]) + 10 * index,
            int(cfg["confirm_support_base"]) + index,
            forbidden,
        )
        expected = {row["support_hash"] for row in confirmation["teacher_bindings"] if row["task"] == spec.task_id}
        if expected != {prefix_hash(support, budget)}:
            raise RuntimeError(f"support for {spec.task_id} is not the closed confirmation support")
        replication_supports.append(support)
    fresh_supports = []
    fresh_hashes = []
    for index, spec in enumerate(assert_fresh_physics(rep)):
        support = _collect_named(
            spec,
            budget,
            int(cfg["fresh_support_env0"]) + 10 * index,
            int(cfg["fresh_support_base"]) + index,
            forbidden,
        )
        fresh_supports.append(support)
        fresh_hashes.append(prefix_hash(support, budget))
    interactions = budget * (len(replication_supports) + len(fresh_supports))
    return replication_supports, fresh_supports, fresh_hashes, interactions


def _zero_context(model: Any) -> None:
    if int(model.context_dim()) != CONTEXT_DIM:
        raise RuntimeError("context dimension drifted")
    model.z = torch.zeros(CONTEXT_DIM, dtype=torch.float32)


def _task_row(
    *,
    decoder: int,
    split: str,
    spec: Any,
    zero: dict[str, Any],
    students: list[dict[str, Any]],
    zero_recorded: dict[str, float],
    student_recorded: list[dict[str, float]],
    n_states: int,
) -> dict[str, Any]:
    physics = [float(value) for value in pendulum_physics_key(spec)]
    return {
        "decoder": int(decoder),
        "split": split,
        "task": spec.task_id,
        "physics": physics,
        "n_states": int(n_states),
        "n_students": len(students),
        "zero_regret": zero["regret"],
        "student_regret": average_student_metric(students, "regret"),
        "regret_improvement": zero["regret"] - average_student_metric(students, "regret"),
        "zero_correct": zero["correct"],
        "student_correct": average_student_metric(students, "correct"),
        "correct_improvement": average_student_metric(students, "correct") - zero["correct"],
        "zero_spearman": zero["spearman"],
        "student_spearman": average_student_metric(students, "spearman"),
        "spearman_improvement": average_student_metric(students, "spearman") - zero["spearman"],
        "zero_reward_mae": zero["reward_mae"],
        "student_reward_mae": average_student_metric(students, "reward_mae"),
        "reward_improvement": zero["reward_mae"] - average_student_metric(students, "reward_mae"),
        "zero_one_step_angvel": zero["one_step_angvel"],
        "student_one_step_angvel": average_student_metric(students, "one_step_angvel"),
        "angvel_improvement": zero["one_step_angvel"] - average_student_metric(students, "one_step_angvel"),
        "zero_open_loop_angvel": zero["open_loop_angvel"],
        "student_open_loop_angvel": average_student_metric(students, "open_loop_angvel"),
        "open_loop_improvement": zero["open_loop_angvel"] - average_student_metric(students, "open_loop_angvel"),
        "zero_one_step_state": zero["one_step_state"],
        "student_one_step_state": average_student_metric(students, "one_step_state"),
        "state_improvement": zero["one_step_state"] - average_student_metric(students, "one_step_state"),
        "zero_open_loop_state": zero["open_loop_state"],
        "student_open_loop_state": average_student_metric(students, "open_loop_state"),
        "open_loop_state_improvement": zero["open_loop_state"] - average_student_metric(students, "open_loop_state"),
        "zero_recorded_angvel": zero_recorded["one_step_angvel"],
        "student_recorded_angvel": average_student_metric(student_recorded, "one_step_angvel"),
        "recorded_angvel_improvement": zero_recorded["one_step_angvel"] - average_student_metric(student_recorded, "one_step_angvel"),
        "zero_recorded_state": zero_recorded["one_step_state"],
        "student_recorded_state": average_student_metric(student_recorded, "one_step_state"),
        "recorded_state_improvement": zero_recorded["one_step_state"] - average_student_metric(student_recorded, "one_step_state"),
        "action_disagreement": average_student_metric(students, "disagreement"),
    }


def _score_decoder(
    seed: int,
    rep: dict[str, Any],
    cfg: dict[str, Any],
    confirmation: dict[str, Any],
    bundles: dict[str, dict[str, Any]],
    fingerprints: dict[int, str],
) -> tuple[list[dict[str, Any]], int]:
    path = _decoder_file(int(seed), rep)
    broad = _student_rows(int(seed), str(cfg["student_kind"]), rep, confirmation)
    if len(broad) != int(cfg["n_student_seeds"]):
        raise RuntimeError(f"decoder {seed} does not have the locked student count")
    expected_digest = fingerprints[int(seed)]
    rows: list[dict[str, Any]] = []
    model_states = 0
    for split, bundle in bundles.items():
        for task_index, spec in enumerate(bundle["specs"]):
            states = bundle["states"][task_index]
            recorded = bundle["recorded"][task_index]
            zero_model, digest = _fresh_decoder(path, rep)
            if digest != expected_digest:
                raise RuntimeError(f"decoder {seed} fingerprint changed before scoring")
            _zero_context(zero_model)
            zero = _score_context(zero_model, states, None)
            zero_recorded = dataset_one_step(zero_model, recorded)
            if decoder_digest(zero_model) != expected_digest:
                raise RuntimeError(f"scoring changed decoder {seed}")
            model_states += int(zero["model_states"]) + int(len(recorded))
            students = []
            student_recorded = []
            for student in range(int(cfg["n_student_seeds"])):
                probe, probe_digest = _fresh_decoder(path, rep)
                if probe_digest != expected_digest:
                    raise RuntimeError(f"decoder {seed} fingerprint changed while loading a student")
                slot = next(row for row in broad if int(row["student"]) == student)
                _install_encoder(probe, slot["path"], rep, expected_digest)
                probe.set_context_from_dataset(bundle["supports"][task_index], budget=int(cfg["support_budget"]))
                scored = _score_context(probe, states, zero["first_actions"])
                students.append(scored)
                recorded_error = dataset_one_step(probe, recorded)
                student_recorded.append(recorded_error)
                if decoder_digest(probe) != expected_digest:
                    raise RuntimeError(f"student context changed decoder {seed}")
                model_states += int(scored["model_states"]) + int(len(recorded))
            rows.append(_task_row(
                decoder=int(seed),
                split=split,
                spec=spec,
                zero=zero,
                students=students,
                zero_recorded=zero_recorded,
                student_recorded=student_recorded,
                n_states=len(states),
            ))
            print(f"gap scored decoder {seed} {split} {spec.task_id}", flush=True)
    return rows, model_states


def _improvement_bundle(rows: list[dict[str, Any]], split: str, tasks: int) -> dict[str, Any]:
    keys = {
        "angvel_improvement": "candidate_one_step_angvel",
        "state_improvement": "candidate_one_step_state",
        "open_loop_improvement": "candidate_open_loop_angvel",
        "open_loop_state_improvement": "candidate_open_loop_state",
        "recorded_angvel_improvement": "recorded_one_step_angvel",
        "recorded_state_improvement": "recorded_one_step_state",
        "regret_improvement": "regret",
        "reward_improvement": "reward_mae",
        "correct_improvement": "correct_selection",
        "spearman_improvement": "spearman",
    }
    report = {}
    for key, name in keys.items():
        values = split_decoder_values(rows, split, key, tasks=tasks)
        report[name] = reliable_improvement(values)
        if key == "regret_improvement":
            report[name]["sign"] = "zero_regret_minus_student_regret"
        elif key in ("correct_improvement", "spearman_improvement"):
            report[name]["sign"] = "student_minus_zero"
        else:
            report[name]["sign"] = "zero_error_minus_student_error"
    worse_values = [-value for value in report["regret"]["per_decoder"]]
    report["regret_worse"] = reliable_improvement(worse_values)
    report["regret_worse"]["sign"] = "student_regret_minus_zero_regret"
    disagreement = split_decoder_values(rows, split, "action_disagreement", tasks=tasks)
    report["action_disagreement"] = {
        "per_decoder": disagreement,
        "interval": seed_level_ci(disagreement),
        "sign": "fraction_of_states_whose_selected_first_action_differs",
    }
    return report


def _task_intervals(rows: list[dict[str, Any]], split: str, task_ids: list[str], physics: list[list[float]]) -> list[dict[str, Any]]:
    table = []
    for task, values in zip(task_ids, physics):
        entry: dict[str, Any] = {"split": split, "task": task, "physics": values}
        for key, name in (
            ("angvel_improvement", "angvel_improvement"),
            ("regret_improvement", "regret_improvement"),
            ("reward_improvement", "reward_improvement"),
            ("open_loop_improvement", "open_loop_improvement"),
            ("recorded_angvel_improvement", "recorded_angvel_improvement"),
            ("correct_improvement", "correct_improvement"),
            ("action_disagreement", "action_disagreement"),
        ):
            decoder_values = task_decoder_values(rows, split, task, key)
            entry[name] = {"per_decoder": decoder_values, "interval": seed_level_ci(decoder_values)}
        table.append(entry)
    return table


def _patterns(bundle: dict[str, Any], task_table: list[dict[str, Any]]) -> dict[str, Any]:
    signs = [float(row["regret_improvement"]["interval"]["mean"]) for row in task_table]
    finite = [value for value in signs if value == value]
    return {
        "h1_state_better_and_ranking_worse": bool(bundle["candidate_one_step_angvel"]["pass"] and bundle["regret_worse"]["pass"]),
        "h2_recorded_improves_open_loop_does_not": bool(
            bundle["recorded_one_step_angvel"]["pass"] and not bundle["candidate_open_loop_angvel"]["pass"]
        ),
        "h3_one_step_improves_reward_forecast_does_not": bool(
            bundle["candidate_one_step_angvel"]["pass"] and not bundle["reward_mae"]["pass"]
        ),
        "h4_task_regret_signs_differ": bool(any(value > 0.0 for value in finite) and any(value < 0.0 for value in finite)),
        "correlation_is_not_causal": True,
    }


def _ancestor_or_raise(sha: str) -> None:
    probe = subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], check=False)
    if probe.returncode != 0:
        raise RuntimeError(f"HEAD does not contain the verified base {sha}")


def _write_plot(path: Path, task_table: list[dict[str, Any]], decision: str) -> None:
    width = 760
    height = 420
    left = 70
    top = 50
    plot_width = 640
    plot_height = 300
    means = []
    for row in task_table:
        means.append(float(row["regret_improvement"]["interval"]["mean"] or 0.0))
        means.append(float(row["angvel_improvement"]["interval"]["mean"] or 0.0))
    limit = max([abs(value) for value in means] + [1e-6])
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="70" y="28" font-family="sans-serif" font-size="15">Prediction error and decision regret by physics</text>',
        f'<text x="70" y="46" font-family="sans-serif" font-size="11" fill="#444">{decision}</text>',
        f'<line x1="{left}" y1="{top + plot_height / 2}" x2="{left + plot_width}" y2="{top + plot_height / 2}" stroke="#222"/>',
    ]
    n = max(1, len(task_table))
    slot = plot_width / n
    for index, row in enumerate(task_table):
        regret = float(row["regret_improvement"]["interval"]["mean"] or 0.0)
        angvel = float(row["angvel_improvement"]["interval"]["mean"] or 0.0)
        cx = left + slot * index + slot / 2
        for offset, value, color in ((-12, regret, "#1f4b99"), (8, angvel, "#b35c00")):
            height_px = (value / limit) * (plot_height / 2 - 8)
            y = top + plot_height / 2 - max(height_px, 0)
            bar_height = abs(height_px)
            parts.append(
                f'<rect x="{cx + offset}" y="{y}" width="16" height="{bar_height}" fill="{color}"/>'
            )
        parts.append(
            f'<text x="{cx}" y="{top + plot_height + 22}" text-anchor="middle" font-family="sans-serif" font-size="10">{row["task"].replace("pendulum_", "")}</text>'
        )
    parts.append('<text x="70" y="400" font-family="sans-serif" font-size="11" fill="#1f4b99">Blue: regret improvement (zero minus student)</text>')
    parts.append('<text x="430" y="400" font-family="sans-serif" font-size="11" fill="#b35c00">Orange: angular-velocity improvement</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def run_prediction_control_gap(
    out_path: str | Path = "artifacts/prediction_control_gap.json",
    plot_path: str | Path = "artifacts/prediction_control_gap.svg",
) -> dict[str, Any]:
    cfg = load_prediction_config()
    assert_protocol_frozen(PROTOCOL_PATH, cfg)
    assert_diagnostic_seeds(cfg)
    _ancestor_or_raise(str(cfg["starting_sha"]))
    head = _git_meta()
    source_status = inspect_source_tree(str(head.get("revision") or ""))
    if source_status.get("source_dirty") or source_status.get("source_changed"):
        raise RuntimeError("diagnostic source is dirty; commit the protocol before evaluating")
    started = time.perf_counter()
    deadline = started + float(cfg["time_limit_s"])
    provenance = verify_provenance(cfg)
    rep = load_replication_config()
    confirmation = _confirmation_artifact(rep)
    replication_supports, fresh_supports, fresh_support_hashes, support_steps = _collect_supports(rep, cfg)
    forbidden = set(load_generalization_config()["forbidden_task_ids"])
    replication_specs = list(pendulum_latent_confirmation())
    fresh_specs = list(assert_fresh_physics(rep))
    if [spec.task_id for spec in replication_specs] != list(cfg["replication_task_ids"]):
        raise RuntimeError("replication physics drifted")
    if [spec.task_id for spec in fresh_specs] != list(cfg["fresh_task_ids"]):
        raise RuntimeError("fresh physics drifted")
    recorded_steps = 0
    recorded: dict[str, list[Any]] = {"replication": [], "fresh": []}
    for split, specs, env0 in (
        ("replication", replication_specs, int(cfg["replication_recorded_env0"])),
        ("fresh", fresh_specs, int(cfg["fresh_recorded_env0"])),
    ):
        for index, spec in enumerate(specs):
            dataset = _collect_named(
                spec,
                int(cfg["recorded_transitions"]),
                env0 + int(cfg["seed_stride"]) * index,
                int(cfg["recorded_action_base"]) + (0 if split == "replication" else 10) + index,
                forbidden,
            )
            if len(dataset) != int(cfg["recorded_transitions"]):
                raise RuntimeError(f"recorded budget drifted for {spec.task_id}")
            recorded[split].append(dataset)
            recorded_steps += int(cfg["recorded_transitions"])
    state_tables: dict[str, list[list[dict[str, Any]]]] = {"replication": [], "fresh": []}
    candidate_steps = 0
    table_hashes = {}
    for split_index, (split, specs, env0) in enumerate((
        ("replication", replication_specs, int(cfg["replication_state_env0"])),
        ("fresh", fresh_specs, int(cfg["fresh_state_env0"])),
    )):
        flat: list[dict[str, Any]] = []
        for task_index, spec in enumerate(specs):
            states, steps = _build_states(spec, env0, task_index, split_index, cfg)
            state_tables[split].append(states)
            flat.extend(states)
            candidate_steps += steps
        table_hashes[split] = _table_hash(flat)
        print(f"gap registered {split} states {table_hashes[split]}", flush=True)
    bundles = {
        "replication": {
            "specs": replication_specs,
            "supports": replication_supports,
            "recorded": recorded["replication"],
            "states": state_tables["replication"],
        },
        "fresh": {
            "specs": fresh_specs,
            "supports": fresh_supports,
            "recorded": recorded["fresh"],
            "states": state_tables["fresh"],
        },
    }
    fingerprints = {int(row["seed"]): row["decoder_digest"] for row in provenance["decoder_fingerprints"]}
    rows: list[dict[str, Any]] = []
    model_states = 0
    finished: list[int] = []
    timed_out = False
    for seed in list(cfg["original_seeds"]) + list(cfg["new_seeds"]):
        if time.perf_counter() > deadline:
            timed_out = True
            break
        decoder_rows, scored_states = _score_decoder(int(seed), rep, cfg, confirmation, bundles, fingerprints)
        rows.extend(decoder_rows)
        model_states += scored_states
        finished.append(int(seed))
    tasks = len(cfg["replication_task_ids"])
    complete = (
        not timed_out
        and finished == [int(seed) for seed in list(cfg["original_seeds"]) + list(cfg["new_seeds"])]
        and len(rows) == REQUIRED_DECODERS * tasks * 2
    )
    reports = {}
    task_tables = {}
    decisions = {}
    if complete:
        for split, task_ids, physics, episode_better in (
            ("replication", list(cfg["replication_task_ids"]), cfg["replication_physics"], bool(cfg["replication_full_episode_student_better"])),
            ("fresh", list(cfg["fresh_task_ids"]), cfg["fresh_physics"], bool(cfg["fresh_full_episode_student_better"])),
        ):
            bundle = _improvement_bundle(rows, split, tasks)
            table = _task_intervals(rows, split, task_ids, physics)
            reports[split] = bundle
            task_tables[split] = table
            decisions[split] = decide(
                state_better=bool(bundle["candidate_one_step_angvel"]["pass"]),
                ranking_better=bool(bundle["regret"]["pass"]),
                ranking_worse=bool(bundle["regret_worse"]["pass"]),
                reward_better=bool(bundle["reward_mae"]["pass"]),
                full_episode_better=episode_better,
            )
            angvel = [float(value) for value in bundle["candidate_one_step_angvel"]["per_decoder"]]
            regret = [float(value) for value in bundle["regret"]["per_decoder"]]
            bundle["pearson_angvel_improvement_vs_regret_improvement"] = _pearson(angvel, regret)
            bundle["patterns"] = _patterns(bundle, table)
            bundle["gap"] = gap_sentence(
                state_better=bool(bundle["candidate_one_step_angvel"]["pass"]),
                ranking_better=bool(bundle["regret"]["pass"]),
                ranking_worse=bool(bundle["regret_worse"]["pass"]),
                reward_better=bool(bundle["reward_mae"]["pass"]),
            )
            bundle["decoder_sd"] = {
                "angvel_improvement": float(np.std(angvel, ddof=1)),
                "regret_improvement": float(np.std(regret, ddof=1)),
            }
    primary = decisions.get("fresh", "incomplete")
    recommendation = RECOMMENDATIONS[primary]
    destination = assert_diagnostic_output_path(out_path)
    figure = assert_diagnostic_output_path(plot_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if task_tables:
        _write_plot(figure, list(task_tables["replication"]) + list(task_tables["fresh"]), primary)
    payload = {
        "protocol_id": cfg["protocol_id"],
        "starting_sha": cfg["starting_sha"],
        "implementation_sha": head.get("revision"),
        "source_dirty": False,
        "decision_recorded": bool(complete),
        "diagnostic_complete": bool(complete),
        "timed_out": bool(timed_out),
        "primary_split": "fresh",
        "primary_decision": primary,
        "replication_decision": decisions.get("replication"),
        "recommendation": recommendation,
        "control_claim": False,
        "control_improvement": False,
        "full_episode_remeasured": False,
        "is_agi": False,
        "is_learning_to_learn": False,
        "finished_decoders": finished,
        "independent_decoder_count": len(finished),
        "provenance": provenance,
        "fresh_support_hashes": fresh_support_hashes,
        "state_table_hashes": table_hashes,
        "comparisons": reports,
        "per_task": task_tables,
        "task_rows": rows,
        "prediction_versus_decision": {
            split: {
                "one_step_angvel_improvement": reports[split]["candidate_one_step_angvel"],
                "regret_improvement": reports[split]["regret"],
                "reward_forecast_improvement": reports[split]["reward_mae"],
                "sentence": reports[split]["gap"],
            }
            for split in reports
        },
        "env_steps": {
            "support_recollect": int(support_steps),
            "recorded_transitions": int(recorded_steps),
            "candidate_rollouts": int(candidate_steps),
        },
        "model_states": int(model_states),
        "wall_clock_s": float(time.perf_counter() - started),
        "time_limit_s": int(cfg["time_limit_s"]),
        "notes": {
            "planner_score_includes_survival_weighting": True,
            "actual_return_is_the_published_pendulum_sum": True,
            "students_averaged_inside_decoder": True,
            "candidate_trajectories_are_not_independent_replications": True,
            "correlation_is_not_causal": True,
            "hidden_physics_not_model_inputs": True,
            "actual_outcomes_not_model_inputs": True,
        },
    }
    destination.write_text(dumps_strict(payload))
    print(f"gap decision {primary} complete={complete}", flush=True)
    return payload
