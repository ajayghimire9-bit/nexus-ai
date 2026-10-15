"""Receding-horizon diagnostic for the prediction-to-control gap. Not a new controller.

Live episodes use the existing H=16 planner. Counterfactuals clone the recorded
simulator state. The continuation after a committed first action is the same
zero-context planner for every branch. Nothing here retrains or edits a checkpoint.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import PENDULUM_MAX_STEPS, pendulum_latent_confirmation, pendulum_physics_key
from nexus.tasks.spec import make_task_env
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_pilot import prefix_hash
from nexus.world.control_replication import (
    NEW_SEEDS,
    ORIGINAL_SEEDS,
    TARGET_DECODERS,
    _collect_named,
    _confirmation_artifact,
    _decoder_file,
    _fresh_decoder,
    _install_encoder,
    _pearson,
    assert_fresh_physics,
    load_replication_config,
)
from nexus.world.latent_generalization import decoder_digest, load_generalization_config
from nexus.world.planning import mpc_for_model
from nexus.world.prediction_control_gap import (
    CONTEXT_DIM,
    assert_diagnostic_output_path,
    candidate_sequences,
    decision_metrics,
    diagnostic_seed_groups,
    load_prediction_config,
    reliable_improvement,
    verify_provenance,
)
from nexus.world.rewards import pendulum_step_reward
from nexus.world.v085 import _git_meta

import yaml

CONFIG_PATH = Path("configs/receding_horizon_diagnostic.yaml")
PROTOCOL_PATH = Path("docs/NEXUS_RECEDING_HORIZON_DIAGNOSTIC.md")
SCORE_ATOL = 1e-5
PHASES = (0, 50, 100, 150)
ZERO_SLOT = 5

RECOMMENDATIONS = {
    "visited_state_shift": (
        "The student's one-shot advantage does not appear on states the controllers visit. "
        "Visited-state distribution shift is the supported diagnostic finding. "
        "Do not change the architecture in this study."
    ),
    "replanning_or_compounding": (
        "The student keeps a one-shot advantage on visited states and loses the matched next-16 continuation. "
        "That is sensitivity to replanning or action compounding. "
        "Do not change the architecture in this study."
    ),
    "planner_implementation": (
        "Replayed scores did not reproduce the recorded live decisions. "
        "The planner implementation has to be understood before any model-quality conclusion. "
        "Do not change the architecture in this study."
    ),
    "unresolved_long_horizon": (
        "The local diagnostics favor the student while the closed full-episode return does not. "
        "The remaining discrepancy is unresolved. A separate controlled long-horizon policy-value study "
        "is the next measurement. Do not change the architecture in this study."
    ),
    "local_agrees_with_closed_return": (
        "The local diagnostics and the closed full-episode return agree on this split. "
        "That is a contrast, not a new control claim. Do not change the architecture in this study."
    ),
    "inconclusive": (
        "The decoder-level intervals do not separate the pre-registered branches. "
        "Do not change the architecture on this sample."
    ),
    "incomplete": "The diagnostic grid did not finish inside the locked budget. No mechanism conclusion is available.",
}


def load_horizon_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("receding-horizon config must be a mapping")
    expected = _locked_config()
    if cfg != expected:
        missing = sorted(set(expected) - set(cfg))
        extra = sorted(set(cfg) - set(expected))
        drifted = sorted(key for key in expected if key in cfg and cfg[key] != expected[key])
        raise ValueError(f"receding-horizon config drifted; missing={missing} extra={extra} drifted={drifted}")
    if int(cfg["horizon"]) != 16 or int(cfg["n_candidates"]) != 16 or int(cfg["chunk_size"]) != 4:
        raise ValueError("planner budget drifted")
    if list(cfg["phases"]) != list(PHASES) or cfg["continuation_policy"] != "zero_context_replan":
        raise ValueError("continuation rule drifted")
    if bool(cfg["full_episode_remeasured"]) or bool(cfg["fresh_full_episode_student_better"]):
        raise ValueError("closed control facts drifted")
    return cfg


def _locked_config() -> dict[str, Any]:
    gap = load_prediction_config()
    rep = load_replication_config()
    return {
        "protocol_id": "receding_horizon_diagnostic_v1",
        "starting_sha": "5260f6474e86e0f1db5e6d7820d4a3feaafe4783",
        "prediction_artifact": "artifacts/prediction_control_gap.json",
        "prediction_artifact_sha256": "f1f36506d3c64086898b6f462f9915a28037784dee52f47bce5c19b91bfe390a",
        "control_artifact_sha256": gap["control_artifact_sha256"],
        "manifest_sha256": gap["manifest_sha256"],
        "fresh_support_hashes": ["aa78f66887b76dcf", "97b370d876c2a569", "bd47719e5850bbf7", "9b97c8539673828c"],
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
        "n_student_seeds": int(gap["n_student_seeds"]),
        "student_kind": "broad",
        "episodes_per_task": 1,
        "horizon": 16,
        "n_candidates": 16,
        "n_actions": 3,
        "chunk_size": 4,
        "max_steps": PENDULUM_MAX_STEPS,
        "phases": list(PHASES),
        "continuation_policy": "zero_context_replan",
        "continuation_context": "zero",
        "score_atol": format(SCORE_ATOL, ".0e"),
        "live_replication_env0": 170000,
        "live_fresh_env0": 174000,
        "live_seed_stride": 10,
        "planner_seed_base": 176000,
        "diagnostic_candidate_base": 210000,
        "continuation_seed_base": 280000,
        "time_limit_s": 1800,
        "primary_unit": "decoder",
        "confirm_split_hash": rep["confirm_split_hash"],
        "fresh_split_hash": rep["fresh_split_hash"],
        "replication_task_ids": list(rep["replication_task_ids"]),
        "fresh_task_ids": list(rep["fresh_task_ids"]),
        "support_budget": int(rep["support_budget"]),
        "confirm_support_env0": int(rep["confirm_support_env0"]),
        "confirm_support_base": int(rep["confirm_support_base"]),
        "fresh_support_env0": int(rep["fresh_support_env0"]),
        "fresh_support_base": int(rep["fresh_support_base"]),
        "closed_previous_control_eval_env0": 110000,
        "closed_replication_eval_env0": 120000,
        "closed_fresh_eval_env0": 126000,
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
        "episodes_per_task": str(int(cfg["episodes_per_task"])),
        "horizon": str(int(cfg["horizon"])),
        "n_candidates": str(int(cfg["n_candidates"])),
        "n_actions": str(int(cfg["n_actions"])),
        "chunk_size": str(int(cfg["chunk_size"])),
        "max_steps": str(int(cfg["max_steps"])),
        "phases": ",".join(str(int(step)) for step in cfg["phases"]),
        "target_decoders": str(int(cfg["target_decoders"])),
        "n_student_seeds": str(int(cfg["n_student_seeds"])),
        "primary_split": str(cfg["primary_split"]),
        "continuation_policy": str(cfg["continuation_policy"]),
        "continuation_context": str(cfg["continuation_context"]),
        "live_replication_env0": str(int(cfg["live_replication_env0"])),
        "live_fresh_env0": str(int(cfg["live_fresh_env0"])),
        "live_seed_stride": str(int(cfg["live_seed_stride"])),
        "planner_seed_base": str(int(cfg["planner_seed_base"])),
        "diagnostic_candidate_base": str(int(cfg["diagnostic_candidate_base"])),
        "continuation_seed_base": str(int(cfg["continuation_seed_base"])),
        "time_limit_s": str(int(cfg["time_limit_s"])),
        "score_atol": str(cfg["score_atol"]),
        "starting_sha": str(cfg["starting_sha"]),
        "prediction_artifact_sha256": str(cfg["prediction_artifact_sha256"]),
        "control_artifact_sha256": str(cfg["control_artifact_sha256"]),
        "manifest_sha256": str(cfg["manifest_sha256"]),
        "fresh_support_hashes": ",".join(cfg["fresh_support_hashes"]),
        "confirm_split_hash": str(cfg["confirm_split_hash"]),
        "fresh_split_hash": str(cfg["fresh_split_hash"]),
        "full_episode_remeasured": "false",
        "fresh_full_episode_student_better": "false",
        "replication_full_episode_student_better": "true",
    }
    for key, value in expected.items():
        if locked.get(key) != value:
            raise RuntimeError(f"protocol lock drifted for {key}: document={locked.get(key)!r} config={value!r}")


def live_reset_seed(env0: int, task_index: int, slot: int, stride: int = 10) -> int:
    return int(env0) + int(stride) * int(task_index) + int(slot)


def episode_planner_seed(base: int, split_index: int, task_index: int, slot: int) -> int:
    return int(base) + int(split_index) * 10000 + int(task_index) * 100 + int(slot)


def diagnostic_candidate_seed(base: int, split_index: int, task_index: int, phase_index: int, slot: int) -> int:
    return int(base) + int(split_index) * 50000 + int(task_index) * 2000 + int(phase_index) * 200 + int(slot) * 20


def continuation_step_seed(base: int, split_index: int, task_index: int, phase_index: int, slot: int, step: int) -> int:
    """Seed for continuation step k. It does not depend on the committed action."""
    return diagnostic_candidate_seed(base, split_index, task_index, phase_index, slot) + int(step)


def horizon_seed_groups(cfg: dict[str, Any]) -> dict[str, set[int]]:
    groups: dict[str, set[int]] = {}
    n_tasks = len(cfg["replication_task_ids"])
    slots = range(int(cfg["n_student_seeds"]) + 1)
    for name, env0 in (
        ("replication_live", int(cfg["live_replication_env0"])),
        ("fresh_live", int(cfg["live_fresh_env0"])),
    ):
        groups[name] = {
            live_reset_seed(env0, task, slot, int(cfg["live_seed_stride"]))
            for task in range(n_tasks)
            for slot in slots
        }
    groups["planner_rng"] = {
        episode_planner_seed(int(cfg["planner_seed_base"]), split, task, slot)
        for split in range(2)
        for task in range(n_tasks)
        for slot in slots
    }
    groups["diagnostic_candidates"] = {
        diagnostic_candidate_seed(int(cfg["diagnostic_candidate_base"]), split, task, phase, slot)
        for split in range(2)
        for task in range(n_tasks)
        for phase in range(len(cfg["phases"]))
        for slot in slots
    }
    groups["continuation_rng"] = {
        continuation_step_seed(int(cfg["continuation_seed_base"]), split, task, phase, slot, step)
        for split in range(2)
        for task in range(n_tasks)
        for phase in range(len(cfg["phases"]))
        for slot in slots
        for step in range(int(cfg["horizon"]))
    }
    return groups


def assert_horizon_seeds(cfg: dict[str, Any]) -> None:
    occupied, gap_groups = diagnostic_seed_groups(load_prediction_config())
    blocked: set[int] = set()
    for seeds in list(occupied.values()) + list(gap_groups.values()):
        blocked |= set(seeds)
    groups = horizon_seed_groups(cfg)
    for name, seeds in groups.items():
        overlap = seeds & blocked
        if overlap:
            raise ValueError(f"{name} reuses a closed seed: {sorted(overlap)[:8]}")
        blocked |= seeds
    if len(groups["replication_live"]) != len(groups["fresh_live"]):
        raise ValueError("live trajectory budgets are not equal")
    n_tasks = len(cfg["replication_task_ids"])
    n_slots = int(cfg["n_student_seeds"]) + 1
    if len(groups["replication_live"]) != n_tasks * n_slots:
        raise ValueError("live reset seeds are not unique")
    if len(groups["continuation_rng"]) != 2 * n_tasks * len(cfg["phases"]) * n_slots * int(cfg["horizon"]):
        raise ValueError("continuation seeds are not unique")


def verify_horizon_provenance(cfg: dict[str, Any]) -> dict[str, Any]:
    artifact = Path(cfg["prediction_artifact"])
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if digest != cfg["prediction_artifact_sha256"]:
        raise RuntimeError("prediction-control artifact hash mismatch")
    payload = __import__("json").loads(artifact.read_text())
    if list(payload.get("fresh_support_hashes") or []) != list(cfg["fresh_support_hashes"]):
        raise RuntimeError("fresh support hashes do not match the closed one-shot diagnostic")
    nested = (payload.get("provenance") or {}).get("control_artifact_sha256")
    control_sha = hashlib.sha256(Path("artifacts/control_replication.json").read_bytes()).hexdigest()
    if nested != cfg["control_artifact_sha256"] or control_sha != cfg["control_artifact_sha256"]:
        raise RuntimeError("closed control artifact identity drifted")
    report = verify_provenance(load_prediction_config())
    report["prediction_artifact_sha256"] = digest
    report["checkpoints_written"] = False
    return report


def _walk_wrappers(env: Any):
    cursor = env
    while cursor is not None:
        yield cursor
        cursor = getattr(cursor, "env", None)


def prepare_clone(env: Any) -> None:
    """Clear the episode time limit so a cloned state can be stepped again."""
    for wrapper in _walk_wrappers(env):
        if hasattr(wrapper, "_elapsed_steps"):
            wrapper._elapsed_steps = 0
        if hasattr(wrapper, "_has_reset"):
            wrapper._has_reset = True


def true_state(env: Any) -> np.ndarray:
    state = np.asarray(env.unwrapped.state, dtype=np.float64).reshape(-1)
    if state.shape != (2,):
        raise RuntimeError("pendulum simulator state is not (theta, angular velocity)")
    return state.copy()


def restore_state(env: Any, state: np.ndarray) -> np.ndarray:
    """Put the simulator back at a recorded state. The model is not involved."""
    prepare_clone(env)
    env.unwrapped.state = np.asarray(state, dtype=np.float64).reshape(2).copy()
    obs = np.asarray(env.unwrapped._get_obs(), dtype=np.float32).reshape(-1)
    if obs.shape != (3,):
        raise RuntimeError("restored observation is not the 3-D pendulum observation")
    return obs


def _reward_ok(obs: np.ndarray, action: int, nxt: np.ndarray, reward: float) -> None:
    published = float(np.asarray(pendulum_step_reward(obs, int(action), nxt), dtype=np.float64).reshape(-1)[0])
    if abs(float(reward) - published) > 1e-5:
        raise RuntimeError("environment reward does not match the published pendulum cost")


def rollout_actions(env: Any, state: np.ndarray, actions: np.ndarray) -> dict[str, Any]:
    obs = restore_state(env, state)
    rewards = []
    nxts = []
    for action in np.asarray(actions, dtype=np.int64).reshape(-1):
        prev = obs
        nxt, reward, terminated, truncated, _info = env.step(int(action))
        nxt_arr = np.asarray(nxt, dtype=np.float32).reshape(-1)
        _reward_ok(prev, int(action), nxt_arr, float(reward))
        rewards.append(float(reward))
        nxts.append(nxt_arr)
        obs = nxt_arr
        if (terminated or truncated) and len(rewards) != int(np.asarray(actions).reshape(-1).size):
            raise RuntimeError("cloned rollout ended before the candidate horizon")
    if len(rewards) != int(np.asarray(actions).reshape(-1).size):
        raise RuntimeError("cloned rollout ended before the candidate horizon")
    return {"return": float(np.sum(rewards)), "rewards": np.asarray(rewards, dtype=np.float64), "next_obs": np.stack(nxts)}


def chunked_scores(model: Any, obs: np.ndarray, sequences: np.ndarray) -> np.ndarray:
    """Score every candidate the way RandomShootingMPC.act does when the time budget is off."""
    sequences = np.asarray(sequences, dtype=np.int64)
    obs = np.asarray(obs, dtype=np.float32).reshape(-1)
    if obs.shape != (3,):
        raise ValueError("planner scoring received a non-observation vector")
    planner = mpc_for_model(model, seed=0, enforce_time_budget=False)
    if int(planner.horizon) != int(sequences.shape[1]) or int(planner.n_candidates) != int(sequences.shape[0]):
        raise ValueError("candidate set does not match the locked planner")
    if int(planner.chunk_size) != 4 or int(planner.n_actions) != 3 or planner.step_reward is not pendulum_step_reward:
        raise ValueError("planner implementation drifted")
    before = model.z.detach().clone() if getattr(model, "z", None) is not None else None
    parts = [planner._score_batch(obs, sequences[i : i + int(planner.chunk_size)]) for i in range(0, sequences.shape[0], int(planner.chunk_size))]
    scores = np.concatenate(parts, axis=0).astype(np.float64)
    if before is not None and not torch.equal(model.z.detach(), before):
        raise RuntimeError("scoring changed the context vector")
    if scores.shape != (sequences.shape[0],):
        raise RuntimeError("planner dropped a candidate")
    return scores


def _context_snapshot(model: Any) -> torch.Tensor:
    if int(model.context_dim()) != CONTEXT_DIM:
        raise RuntimeError("context dimension drifted")
    if model.z is None or tuple(model.z.shape) != (CONTEXT_DIM,):
        raise RuntimeError("context was not installed before scoring")
    return model.z.detach().clone()


def _same_context(model: Any, snapshot: torch.Tensor) -> None:
    if not torch.equal(model.z.detach(), snapshot):
        raise RuntimeError("context changed during evaluation")


def install_zero(model: Any) -> torch.Tensor:
    model.z = torch.zeros(CONTEXT_DIM, dtype=torch.float32)
    return _context_snapshot(model)


def install_student(model: Any, path: str, support: Any, digest: str, rep: dict[str, Any], budget: int) -> torch.Tensor:
    _install_encoder(model, path, rep, digest)
    model.set_context_from_dataset(support, budget=int(budget))
    return _context_snapshot(model)


def reproduce_live_scores(model: Any, obs: np.ndarray, sequences: np.ndarray, stored_scores: np.ndarray, stored_action: int) -> bool:
    replay = chunked_scores(model, obs, sequences)
    stored = np.asarray(stored_scores, dtype=np.float64).reshape(-1)
    if replay.shape != stored.shape:
        return False
    action = int(sequences[int(np.argmax(replay)), 0])
    return bool(action == int(stored_action) and np.allclose(replay, stored, atol=SCORE_ATOL, rtol=SCORE_ATOL))


def run_live_episode(env: Any, model: Any, *, reset_seed: int, planner_seed: int, phases: tuple[int, ...] | list[int], max_steps: int) -> dict[str, Any]:
    planner = mpc_for_model(model, seed=int(planner_seed), enforce_time_budget=False)
    planner.reset_episode(int(planner_seed))
    if int(planner.horizon) != 16 or int(planner.n_candidates) != 16:
        raise RuntimeError("live planner budget drifted")
    obs, _info = env.reset(seed=int(reset_seed))
    obs = np.asarray(obs, dtype=np.float32).reshape(-1)
    phases_set = {int(step) for step in phases}
    captured = []
    rewards = []
    for step_index in range(int(max_steps)):
        state = true_state(env)
        action, info = planner.act(obs)
        sequences = np.asarray(planner.last_seqs, dtype=np.int64)
        scores = np.asarray(info["candidate_scores"], dtype=np.float64)
        if int(info["n_scored"]) != sequences.shape[0] or sequences.shape != (16, 16):
            raise RuntimeError("live planner did not score the full candidate budget")
        selected = int(np.argmax(scores))
        if int(action) != int(sequences[selected, 0]):
            raise RuntimeError("live action does not match the selected candidate")
        reproduced = True
        if step_index in phases_set:
            reproduced = reproduce_live_scores(model, obs, sequences, scores, int(action))
        prev = obs
        nxt, reward, terminated, truncated, _info = env.step(int(action))
        nxt_arr = np.asarray(nxt, dtype=np.float32).reshape(-1)
        _reward_ok(prev, int(action), nxt_arr, float(reward))
        if step_index in phases_set:
            captured.append({
                "step": int(step_index),
                "state": state,
                "obs": prev.copy(),
                "action": int(action),
                "planner_seed": int(planner_seed),
                "selected_index": selected,
                "sequences": sequences.copy(),
                "scores": scores.copy(),
                "immediate_reward": float(reward),
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                "reproduced": bool(reproduced),
            })
        rewards.append(float(reward))
        obs = nxt_arr
        if (terminated or truncated) and step_index < int(max_steps) - 1:
            raise RuntimeError("live episode ended before the registered horizon")
    if len(rewards) != int(max_steps) or len(captured) != len(phases_set):
        raise RuntimeError("live episode did not record every registered phase")
    return {"rewards": rewards, "phases": captured, "return": float(np.sum(rewards))}


def continuation_return(env: Any, model: Any, state: np.ndarray, first_action: int, step_seeds: list[int]) -> float:
    """Committed first action, then zero-context replanning. Not a full-episode value."""
    if len(step_seeds) != 16:
        raise ValueError("continuation seeds must cover the locked horizon")
    snapshot = _context_snapshot(model)
    obs = restore_state(env, state)
    total = 0.0
    prev = obs
    nxt, reward, terminated, truncated, _info = env.step(int(first_action))
    nxt_arr = np.asarray(nxt, dtype=np.float32).reshape(-1)
    _reward_ok(prev, int(first_action), nxt_arr, float(reward))
    total += float(reward)
    obs = nxt_arr
    if terminated or truncated:
        raise RuntimeError("continuation ended on the committed action")
    planner = mpc_for_model(model, seed=int(step_seeds[1]), enforce_time_budget=False)
    for step_index in range(1, 16):
        planner.reset_episode(int(step_seeds[step_index]))
        action, info = planner.act(obs)
        _same_context(model, snapshot)
        if int(info["n_scored"]) != 16:
            raise RuntimeError("continuation planner dropped a candidate")
        prev = obs
        nxt, reward, terminated, truncated, _info = env.step(int(action))
        nxt_arr = np.asarray(nxt, dtype=np.float32).reshape(-1)
        _reward_ok(prev, int(action), nxt_arr, float(reward))
        total += float(reward)
        obs = nxt_arr
        if (terminated or truncated) and step_index < 15:
            raise RuntimeError("continuation ended before 16 rewards")
    _same_context(model, snapshot)
    return float(total)


def evaluate_state(
    env: Any,
    *,
    state: np.ndarray,
    obs: np.ndarray,
    sequences: np.ndarray,
    models: dict[Any, Any],
    zero_model: Any,
    continuation_seeds: list[int],
) -> dict[Any, dict[str, Any]]:
    """Score one shared candidate set, then roll it out. Returns are not model inputs."""
    scored: dict[Any, dict[str, Any]] = {}
    for name, model in models.items():
        scores = chunked_scores(model, obs, sequences)
        scored[name] = {"scores": scores}
    returns = np.asarray([
        rollout_actions(env, state, sequence)["return"] for sequence in sequences
    ], dtype=np.float64)
    continuation = np.asarray([
        continuation_return(env, zero_model, state, action, continuation_seeds) for action in range(3)
    ], dtype=np.float64)
    best_action_return = float(np.max(continuation))
    out: dict[Any, dict[str, Any]] = {}
    for name, row in scored.items():
        metrics = decision_metrics(row["scores"], returns, sequences)
        chosen = int(metrics["first_action"])
        selected = int(metrics["selected"])
        out[name] = {
            "regret": float(metrics["regret"]),
            "correct": float(metrics["correct"]),
            "spearman": float(metrics["spearman"]),
            "reward_mae": float(metrics["reward_mae"]),
            "selected_score_error": float(abs(row["scores"][selected] - returns[selected])),
            "sequence_return": float(returns[selected]),
            "first_action": chosen,
            "continuation_return": float(continuation[chosen]),
            "action_regret": float(best_action_return - continuation[chosen]),
            "score_bias": float(np.mean(row["scores"] - returns)),
        }
    out["continuation"] = continuation
    return out


def decide(
    *,
    reproduction_ok: bool,
    one_shot_better: bool,
    one_shot_worse: bool,
    continuation_better: bool,
    continuation_worse: bool,
    open_loop_better: bool,
    action_regret_better: bool,
    full_episode_better: bool,
) -> str:
    if one_shot_better and one_shot_worse:
        raise RuntimeError("one-shot flags contradict")
    if continuation_better and continuation_worse:
        raise RuntimeError("continuation flags contradict")
    if not reproduction_ok:
        return "planner_implementation"
    if one_shot_worse:
        return "visited_state_shift"
    if one_shot_better and continuation_worse:
        return "replanning_or_compounding"
    if one_shot_better and continuation_better and open_loop_better and action_regret_better:
        return "local_agrees_with_closed_return" if full_episode_better else "unresolved_long_horizon"
    return "inconclusive"


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        raise RuntimeError(f"empty aggregate for {key}")
    return float(np.mean([float(row[key]) for row in rows]))


def decoder_values(rows: list[dict[str, Any]], split: str, key: str, *, expected: int, visitor: str | None = None) -> list[float]:
    grouped: dict[int, list[float]] = {}
    for row in rows:
        if row["split"] != split:
            continue
        if visitor is not None and row["visitor"] != visitor:
            continue
        grouped.setdefault(int(row["decoder"]), []).append(float(row[key]))
    values = []
    for decoder in sorted(grouped):
        if len(grouped[decoder]) != int(expected):
            raise RuntimeError(f"decoder {decoder} has {len(grouped[decoder])} {split} rows, not {expected}")
        values.append(float(np.mean(grouped[decoder])))
    return values


def _ancestor_or_raise(sha: str) -> None:
    probe = subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], check=False)
    if probe.returncode != 0:
        raise RuntimeError(f"HEAD does not contain the verified base {sha}")


def _supports(rep: dict[str, Any], cfg: dict[str, Any]) -> tuple[list[Any], list[Any], int]:
    forbidden = set(load_generalization_config()["forbidden_task_ids"])
    confirmation = _confirmation_artifact(rep)
    budget = int(cfg["support_budget"])
    replication = []
    for index, spec in enumerate(pendulum_latent_confirmation()):
        support = _collect_named(spec, budget, int(cfg["confirm_support_env0"]) + 10 * index, int(cfg["confirm_support_base"]) + index, forbidden)
        expected = {row["support_hash"] for row in confirmation["teacher_bindings"] if row["task"] == spec.task_id}
        if expected != {prefix_hash(support, budget)}:
            raise RuntimeError(f"support for {spec.task_id} is not the closed confirmation support")
        replication.append(support)
    fresh = []
    for index, spec in enumerate(assert_fresh_physics(rep)):
        support = _collect_named(spec, budget, int(cfg["fresh_support_env0"]) + 10 * index, int(cfg["fresh_support_base"]) + index, forbidden)
        digest = prefix_hash(support, budget)
        if digest != cfg["fresh_support_hashes"][index]:
            raise RuntimeError(f"fresh support for {spec.task_id} does not match the one-shot diagnostic")
        fresh.append(support)
    return replication, fresh, budget * (len(replication) + len(fresh))


def _models_for_task(seed: int, rep: dict[str, Any], cfg: dict[str, Any], confirmation: dict[str, Any], support: Any, digest: str) -> dict[Any, Any]:
    path = _decoder_file(int(seed), rep)
    broad = [row for row in _install_rows(seed, rep, cfg, confirmation)]
    zero_model, zero_digest = _fresh_decoder(path, rep)
    if zero_digest != digest:
        raise RuntimeError(f"decoder {seed} fingerprint changed")
    install_zero(zero_model)
    models: dict[Any, Any] = {"zero": zero_model}
    for row in broad:
        probe, probe_digest = _fresh_decoder(path, rep)
        if probe_digest != digest:
            raise RuntimeError(f"decoder {seed} fingerprint changed while loading a student")
        install_student(probe, row["path"], support, digest, rep, int(cfg["support_budget"]))
        models[int(row["student"])] = probe
    return models


def _install_rows(seed: int, rep: dict[str, Any], cfg: dict[str, Any], confirmation: dict[str, Any]) -> list[dict[str, Any]]:
    from nexus.world.control_replication import _student_rows

    rows = _student_rows(int(seed), str(cfg["student_kind"]), rep, confirmation)
    if len(rows) != int(cfg["n_student_seeds"]):
        raise RuntimeError(f"decoder {seed} does not have the locked student count")
    return rows


def _paired_cell(decoder: int, split: str, spec: Any, phase: int, visitor: str, student_rows: list[dict[str, Any]], zero_row: dict[str, Any], live_agreement: float, cross_agreement: float, obs_student: np.ndarray, obs_zero: np.ndarray) -> dict[str, Any]:
    return {
        "decoder": int(decoder),
        "split": split,
        "task": spec.task_id,
        "physics": [float(value) for value in pendulum_physics_key(spec)],
        "phase": int(phase),
        "visitor": visitor,
        "n_students": len(student_rows),
        "student_regret": _mean(student_rows, "regret"),
        "zero_regret": float(zero_row["regret"]),
        "regret_improvement": float(zero_row["regret"]) - _mean(student_rows, "regret"),
        "student_sequence_return": _mean(student_rows, "sequence_return"),
        "zero_sequence_return": float(zero_row["sequence_return"]),
        "sequence_return_improvement": _mean(student_rows, "sequence_return") - float(zero_row["sequence_return"]),
        "student_selected_score_error": _mean(student_rows, "selected_score_error"),
        "zero_selected_score_error": float(zero_row["selected_score_error"]),
        "score_error_improvement": float(zero_row["selected_score_error"]) - _mean(student_rows, "selected_score_error"),
        "student_reward_mae": _mean(student_rows, "reward_mae"),
        "zero_reward_mae": float(zero_row["reward_mae"]),
        "reward_mae_improvement": float(zero_row["reward_mae"]) - _mean(student_rows, "reward_mae"),
        "student_continuation": _mean(student_rows, "continuation_return"),
        "zero_continuation": float(zero_row["continuation_return"]),
        "continuation_improvement": _mean(student_rows, "continuation_return") - float(zero_row["continuation_return"]),
        "student_action_regret": _mean(student_rows, "action_regret"),
        "zero_action_regret": float(zero_row["action_regret"]),
        "action_regret_improvement": float(zero_row["action_regret"]) - _mean(student_rows, "action_regret"),
        "student_correct": _mean(student_rows, "correct"),
        "zero_correct": float(zero_row["correct"]),
        "student_spearman": _mean(student_rows, "spearman"),
        "zero_spearman": float(zero_row["spearman"]),
        "spearman_improvement": _mean(student_rows, "spearman") - float(zero_row["spearman"]),
        "student_score_bias": _mean(student_rows, "score_bias"),
        "zero_score_bias": float(zero_row["score_bias"]),
        "cross_context_agreement": float(cross_agreement),
        "visitor_live_agreement": float(live_agreement),
        "obs_distance": float(np.linalg.norm(np.asarray(obs_student, dtype=np.float64) - np.asarray(obs_zero, dtype=np.float64))),
    }


def _evaluate_decoder(
    seed: int,
    rep: dict[str, Any],
    cfg: dict[str, Any],
    confirmation: dict[str, Any],
    bundles: dict[str, dict[str, Any]],
    fingerprints: dict[int, str],
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    _install_rows(seed, rep, cfg, confirmation)
    digest = fingerprints[int(seed)]
    cells: list[dict[str, Any]] = []
    counts = {"env_steps": 0, "model_states": 0, "reproduced": 0, "checked": 0}
    phases = [int(step) for step in cfg["phases"]]
    for split_index, (split, bundle) in enumerate(bundles.items()):
        env0 = int(cfg["live_replication_env0"] if split == "replication" else cfg["live_fresh_env0"])
        for task_index, spec in enumerate(bundle["specs"]):
            support = bundle["supports"][task_index]
            models = _models_for_task(int(seed), rep, cfg, confirmation, support, digest)
            env = make_task_env(spec)
            try:
                episodes = []
                for slot in range(int(cfg["n_student_seeds"]) + 1):
                    name: Any = "zero" if slot == ZERO_SLOT else slot
                    snapshot = _context_snapshot(models[name])
                    reset_seed = live_reset_seed(env0, task_index, slot, int(cfg["live_seed_stride"]))
                    planner_seed = episode_planner_seed(int(cfg["planner_seed_base"]), split_index, task_index, slot)
                    episode = run_live_episode(
                        env, models[name], reset_seed=reset_seed, planner_seed=planner_seed,
                        phases=phases, max_steps=int(cfg["max_steps"]),
                    )
                    _same_context(models[name], snapshot)
                    counts["env_steps"] += int(cfg["max_steps"])
                    counts["model_states"] += int(cfg["max_steps"]) * 16 * 16
                    for phase in episode["phases"]:
                        counts["checked"] += 1
                        counts["reproduced"] += int(bool(phase["reproduced"]))
                        counts["model_states"] += 16 * 16
                    episodes.append((slot, episode))
                for phase_index, phase in enumerate(phases):
                    student_evals = []
                    student_obs = []
                    student_agreement = []
                    zero_eval = None
                    zero_obs = None
                    zero_live_agreement = None
                    student_live = []
                    for slot, episode in episodes:
                        capture = next(row for row in episode["phases"] if int(row["step"]) == int(phase))
                        sequences = candidate_sequences(
                            diagnostic_candidate_seed(int(cfg["diagnostic_candidate_base"]), split_index, task_index, phase_index, slot),
                            int(cfg["n_candidates"]), int(cfg["horizon"]), int(cfg["n_actions"]),
                        )
                        seeds = [
                            continuation_step_seed(int(cfg["continuation_seed_base"]), split_index, task_index, phase_index, slot, step)
                            for step in range(int(cfg["horizon"]))
                        ]
                        if slot == ZERO_SLOT:
                            named = {student: models[student] for student in range(int(cfg["n_student_seeds"]))}
                            named["zero"] = models["zero"]
                        else:
                            named = {slot: models[slot], "zero": models["zero"]}
                        evaluated = evaluate_state(
                            env, state=capture["state"], obs=capture["obs"], sequences=sequences,
                            models=named, zero_model=models["zero"], continuation_seeds=seeds,
                        )
                        counts["env_steps"] += int(sequences.shape[0]) * int(sequences.shape[1]) + 3 * int(cfg["horizon"])
                        counts["model_states"] += len(named) * int(sequences.size) + 3 * 15 * 16 * 16
                        if slot == ZERO_SLOT:
                            zero_eval = evaluated
                            zero_obs = capture["obs"]
                            zero_live_agreement = float(int(evaluated["zero"]["first_action"]) == int(capture["action"]))
                        else:
                            student_evals.append(evaluated[slot])
                            student_obs.append(capture["obs"])
                            student_live.append(float(int(evaluated[slot]["first_action"]) == int(capture["action"])))
                            student_agreement.append(float(int(evaluated[slot]["first_action"]) == int(evaluated["zero"]["first_action"])))
                            student_evals[-1]["_zero"] = evaluated["zero"]
                    if zero_eval is None or len(student_evals) != int(cfg["n_student_seeds"]):
                        raise RuntimeError("phase capture is incomplete")
                    student_obs_mean = np.mean(np.stack(student_obs, axis=0), axis=0)
                    zero_vector = np.asarray(zero_obs, dtype=np.float64)
                    cells.append(_paired_cell(
                        int(seed), split, spec, phase, "student",
                        student_evals, _mean_zero_on_student(student_evals), float(np.mean(student_live)),
                        float(np.mean(student_agreement)), student_obs_mean, zero_vector,
                    ))
                    zero_student_rows = [zero_eval[student] for student in range(int(cfg["n_student_seeds"]))]
                    zero_agreement = float(np.mean([
                        float(int(zero_eval[student]["first_action"]) == int(zero_eval["zero"]["first_action"]))
                        for student in range(int(cfg["n_student_seeds"]))
                    ]))
                    cells.append(_paired_cell(
                        int(seed), split, spec, phase, "zero",
                        zero_student_rows, zero_eval["zero"], float(zero_live_agreement),
                        zero_agreement, student_obs_mean, zero_vector,
                    ))
            finally:
                env.close()
            if decoder_digest(models["zero"]) != digest:
                raise RuntimeError(f"evaluation changed decoder {seed}")
            print(f"horizon scored decoder {seed} {split} {spec.task_id}", flush=True)
    return cells, counts, {"reproduced": counts["reproduced"], "checked": counts["checked"]}


def _mean_zero_on_student(student_evals: list[dict[str, Any]]) -> dict[str, Any]:
    zeros = [row["_zero"] for row in student_evals]
    keys = [key for key in zeros[0] if key != "first_action"]
    out = {key: float(np.mean([float(row[key]) for row in zeros])) for key in keys}
    out["first_action"] = int(zeros[0]["first_action"])
    # Each student-visited state has its own zero action. Agreement uses the paired row.
    return out


def _bundle(rows: list[dict[str, Any]], split: str, expected: int) -> dict[str, Any]:
    keys = {
        "regret_improvement": "one_shot_regret",
        "sequence_return_improvement": "open_loop_return",
        "score_error_improvement": "selected_score_error",
        "reward_mae_improvement": "candidate_score_mae",
        "continuation_improvement": "continuation_return",
        "action_regret_improvement": "selected_action_regret",
        "spearman_improvement": "spearman",
    }
    report: dict[str, Any] = {}
    for key, name in keys.items():
        values = decoder_values(rows, split, key, expected=expected)
        report[name] = reliable_improvement(values)
        report[name]["per_decoder"] = values
    worse = {
        "one_shot_regret_worse": [-value for value in report["one_shot_regret"]["per_decoder"]],
        "continuation_worse": [-value for value in report["continuation_return"]["per_decoder"]],
        "open_loop_return_worse": [-value for value in report["open_loop_return"]["per_decoder"]],
    }
    for name, values in worse.items():
        report[name] = reliable_improvement(values)
    for visitor, count in (("student", expected // 2), ("zero", expected // 2)):
        report[f"one_shot_regret_{visitor}_visited"] = reliable_improvement(
            decoder_values(rows, split, "regret_improvement", expected=count, visitor=visitor)
        )
    agreement = decoder_values(rows, split, "cross_context_agreement", expected=expected)
    live_agreement = decoder_values(rows, split, "visitor_live_agreement", expected=expected)
    distance = decoder_values(rows, split, "obs_distance", expected=expected)
    report["first_action_agreement"] = {"per_decoder": agreement, "interval": seed_level_ci(agreement)}
    report["live_diagnostic_agreement"] = {"per_decoder": live_agreement, "interval": seed_level_ci(live_agreement)}
    report["visited_observation_distance"] = {"per_decoder": distance, "interval": seed_level_ci(distance), "descriptive": True}
    report["pearson_regret_vs_continuation"] = _pearson(
        report["one_shot_regret"]["per_decoder"], report["continuation_return"]["per_decoder"],
    )
    return report


def _grouped(rows: list[dict[str, Any]], split: str, field: str, values: list[Any], key: str) -> list[dict[str, Any]]:
    table = []
    for value in values:
        chosen = [row for row in rows if row["split"] == split and row[field] == value]
        decoders = sorted({int(row["decoder"]) for row in chosen})
        series = [float(np.mean([float(row[key]) for row in chosen if int(row["decoder"]) == decoder])) for decoder in decoders]
        table.append({field: value, "interval": seed_level_ci(series), "per_decoder": series})
    return table


def _write_plot(path: Path, rows: list[dict[str, Any]], decision: str) -> None:
    fresh = [row for row in rows if row["split"] == "fresh"]
    phases = sorted({int(row["phase"]) for row in fresh})
    width, height = 720, 360
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="40" y="28" font-family="sans-serif" font-size="15">Visited-state regret and next-16 continuation</text>',
        f'<text x="40" y="48" font-family="sans-serif" font-size="11" fill="#444">{decision}. Positive means the student is better. Next-16 is not a full-episode value.</text>',
    ]
    means = []
    for phase in phases:
        chunk = [row for row in fresh if int(row["phase"]) == phase]
        means.append(float(np.mean([row["regret_improvement"] for row in chunk])))
        means.append(float(np.mean([row["continuation_improvement"] for row in chunk])))
    limit = max([abs(value) for value in means] + [1e-6])
    for index, phase in enumerate(phases):
        regret, cont = means[2 * index], means[2 * index + 1]
        cx = 80 + index * 150
        for offset, value, color in ((-18, regret, "#1f4b99"), (6, cont, "#9a3412")):
            height_px = (value / limit) * 110
            y = 200 - max(height_px, 0)
            parts.append(f'<rect x="{cx + offset}" y="{y}" width="16" height="{abs(height_px)}" fill="{color}"/>')
        parts.append(f'<text x="{cx}" y="250" font-family="sans-serif" font-size="11">step {phase}</text>')
    parts.append('<line x1="50" y1="200" x2="680" y2="200" stroke="#222"/>')
    parts.append('<text x="40" y="320" font-family="sans-serif" font-size="11" fill="#1f4b99">Blue: one-shot regret improvement</text>')
    parts.append('<text x="360" y="320" font-family="sans-serif" font-size="11" fill="#9a3412">Red: next-16 continuation improvement</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def run_receding_horizon(
    out_path: str | Path = "artifacts/receding_horizon_diagnostic.json",
    plot_path: str | Path = "artifacts/receding_horizon_diagnostic.svg",
) -> dict[str, Any]:
    cfg = load_horizon_config()
    assert_protocol_frozen(PROTOCOL_PATH, cfg)
    assert_horizon_seeds(cfg)
    _ancestor_or_raise(str(cfg["starting_sha"]))
    head = _git_meta()
    source_status = inspect_source_tree(str(head.get("revision") or ""))
    if source_status.get("source_dirty") or source_status.get("source_changed"):
        raise RuntimeError("diagnostic source is dirty; commit the protocol before evaluating")
    started = time.perf_counter()
    deadline = started + float(cfg["time_limit_s"])
    provenance = verify_horizon_provenance(cfg)
    rep = load_replication_config()
    confirmation = _confirmation_artifact(rep)
    replication_supports, fresh_supports, support_steps = _supports(rep, cfg)
    replication_specs = list(pendulum_latent_confirmation())
    fresh_specs = list(assert_fresh_physics(rep))
    bundles = {
        "replication": {"specs": replication_specs, "supports": replication_supports},
        "fresh": {"specs": fresh_specs, "supports": fresh_supports},
    }
    fingerprints = {int(row["seed"]): row["decoder_digest"] for row in provenance["decoder_fingerprints"]}
    rows: list[dict[str, Any]] = []
    totals = {"env_steps": int(support_steps), "model_states": 0, "reproduced": 0, "checked": 0, "support_steps": int(support_steps)}
    finished: list[int] = []
    timed_out = False
    for seed in list(cfg["original_seeds"]) + list(cfg["new_seeds"]):
        if time.perf_counter() > deadline:
            timed_out = True
            break
        cells, counts, _audit = _evaluate_decoder(int(seed), rep, cfg, confirmation, bundles, fingerprints)
        rows.extend(cells)
        for key in ("env_steps", "model_states", "reproduced", "checked"):
            totals[key] += int(counts[key])
        finished.append(int(seed))
    n_tasks = len(cfg["replication_task_ids"])
    expected = n_tasks * len(cfg["phases"]) * 2
    complete = (
        not timed_out
        and finished == [int(seed) for seed in list(cfg["original_seeds"]) + list(cfg["new_seeds"])]
        and len(rows) == REQUIRED_ROWS(cfg)
    )
    reports = {}
    decisions = {}
    reproduction_ok = bool(complete and totals["checked"] > 0 and totals["reproduced"] == totals["checked"])
    if complete:
        for split, episode_better in (
            ("replication", bool(cfg["replication_full_episode_student_better"])),
            ("fresh", bool(cfg["fresh_full_episode_student_better"])),
        ):
            bundle = _bundle(rows, split, expected)
            reports[split] = bundle
            decisions[split] = decide(
                reproduction_ok=reproduction_ok,
                one_shot_better=bool(bundle["one_shot_regret"]["pass"]),
                one_shot_worse=bool(bundle["one_shot_regret_worse"]["pass"]),
                continuation_better=bool(bundle["continuation_return"]["pass"]),
                continuation_worse=bool(bundle["continuation_worse"]["pass"]),
                open_loop_better=bool(bundle["selected_score_error"]["pass"]),
                action_regret_better=bool(bundle["selected_action_regret"]["pass"]),
                full_episode_better=episode_better,
            )
            bundle["patterns"] = {
                "h1_visited_shift": bool(bundle["one_shot_regret_worse"]["pass"]),
                "h2_replanning": bool(
                    bundle["one_shot_regret"]["pass"] and bundle["continuation_worse"]["pass"] and bundle["open_loop_return"]["pass"]
                ),
                "h3_compounding": bool(
                    bundle["one_shot_regret"]["pass"] and bundle["continuation_worse"]["pass"] and bundle["open_loop_return_worse"]["pass"]
                ),
                "h4_reproduction_failed": not reproduction_ok,
                "correlation_is_not_causal": True,
                "next16_is_not_a_full_episode_value": True,
            }
            bundle["by_phase"] = {
                "regret_improvement": _grouped(rows, split, "phase", list(cfg["phases"]), "regret_improvement"),
                "continuation_improvement": _grouped(rows, split, "phase", list(cfg["phases"]), "continuation_improvement"),
            }
            bundle["by_task"] = {
                "regret_improvement": _grouped(rows, split, "task", list(cfg["replication_task_ids" if split == "replication" else "fresh_task_ids"]), "regret_improvement"),
                "continuation_improvement": _grouped(rows, split, "task", list(cfg["replication_task_ids" if split == "replication" else "fresh_task_ids"]), "continuation_improvement"),
            }
    primary = decisions.get("fresh", "incomplete")
    destination = assert_diagnostic_output_path(out_path)
    figure = assert_diagnostic_output_path(plot_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if complete:
        _write_plot(figure, rows, primary)
    payload = {
        "protocol_id": cfg["protocol_id"],
        "starting_sha": cfg["starting_sha"],
        "implementation_sha": head.get("revision"),
        "source_dirty": False,
        "decision_recorded": bool(complete),
        "diagnostic_complete": bool(complete),
        "timed_out": bool(timed_out),
        "reproduction_ok": bool(reproduction_ok) if complete else False,
        "primary_split": "fresh",
        "primary_decision": primary,
        "replication_decision": decisions.get("replication"),
        "recommendation": RECOMMENDATIONS[primary],
        "control_claim": False,
        "control_improvement": False,
        "full_episode_remeasured": False,
        "is_agi": False,
        "is_learning_to_learn": False,
        "finished_decoders": finished,
        "independent_decoder_count": len(finished),
        "provenance": provenance,
        "comparisons": reports,
        "cells": rows,
        "env_steps": totals,
        "wall_clock_s": float(time.perf_counter() - started),
        "time_limit_s": int(cfg["time_limit_s"]),
        "notes": {
            "continuation_policy": "zero_context_replan",
            "next16_is_not_a_full_episode_value": True,
            "students_averaged_inside_decoder": True,
            "states_are_not_independent_decoder_replications": True,
            "hidden_physics_not_model_inputs": True,
            "true_state_used_only_to_clone_the_simulator": True,
            "actual_outcomes_not_model_inputs": True,
            "correlation_is_not_causal": True,
        },
    }
    destination.write_text(dumps_strict(payload))
    print(f"horizon decision {primary} complete={complete} reproduced={totals['reproduced']}/{totals['checked']}", flush=True)
    return payload


def REQUIRED_ROWS(cfg: dict[str, Any]) -> int:
    return int(cfg["target_decoders"]) * 2 * len(cfg["replication_task_ids"]) * len(cfg["phases"]) * 2
