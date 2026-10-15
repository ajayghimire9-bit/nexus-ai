"""Decompose fresh-physics student-minus-zero return into steps 0–15 and 16–199.

The controllers, horizon, and candidate count stay fixed. This does not fit a
model and it does not treat the closed episode returns as a new sample.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import PENDULUM_MAX_STEPS, pendulum_physics_key
from nexus.tasks.spec import make_task_env
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_pilot import prefix_hash
from nexus.world.control_replication import (
    _collect_named,
    _confirmation_artifact,
    assert_fresh_physics,
    load_replication_config,
)
from nexus.world.latent_generalization import decoder_digest, load_generalization_config
from nexus.world.planning import mpc_for_model
from nexus.world.prediction_control_gap import (
    assert_diagnostic_output_path,
    diagnostic_seed_groups,
    load_prediction_config,
    verify_provenance,
)
from nexus.world.receding_horizon import (
    _context_snapshot,
    _models_for_task,
    _same_context,
    horizon_seed_groups,
    load_horizon_config,
)
from nexus.world.rewards import pendulum_step_reward
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/return_phase_decomposition.yaml")
PROTOCOL_PATH = Path("docs/NEXUS_RETURN_PHASE_DECOMPOSITION.md")
EARLY_STEPS = 16
IDENTITY_ATOL = 1e-8
SHARE_MIN_ABS = 1.0

LABELS = (
    "incomplete",
    "absolute_only",
    "primarily_early",
    "primarily_late",
    "both_phases",
    "unseparated",
)


def _locked_config() -> dict[str, Any]:
    replication = load_replication_config()
    gap = load_prediction_config()
    horizon = load_horizon_config()
    evidence = hashlib.sha256(Path("artifacts/nexus_evidence_manifest.json").read_bytes()).hexdigest()
    return {
        "protocol_id": "return_phase_decomposition_v1",
        "starting_sha": "cf2d468c878175c6172b25b6975c5cd90f5968d4",
        "evidence_manifest_sha256": evidence,
        "episodes_per_task": 4,
        "max_steps": int(PENDULUM_MAX_STEPS),
        "early_steps": EARLY_STEPS,
        "horizon": 16,
        "n_candidates": 16,
        "n_actions": 3,
        "n_student_seeds": int(replication["n_student_seeds"]),
        "target_decoders": 10,
        "student_kind": "broad",
        "support_budget": int(replication["support_budget"]),
        "primary_split": "fresh",
        "eval_env0": 400000,
        "planner_seed_base": 410000,
        "task_stride": 100,
        "share_min_abs": SHARE_MIN_ABS,
        "identity_atol": format(IDENTITY_ATOL, ".0e"),
        "time_limit_s": 1800,
        "fresh_split_hash": str(replication["fresh_split_hash"]),
        "fresh_task_ids": list(replication["fresh_task_ids"]),
        "fresh_physics": replication["fresh_physics"],
        "fresh_support_env0": int(replication["fresh_support_env0"]),
        "fresh_support_base": int(replication["fresh_support_base"]),
        "fresh_support_hashes": list(horizon["fresh_support_hashes"]),
        "control_artifact_sha256": str(gap["control_artifact_sha256"]),
        "manifest_sha256": str(gap["manifest_sha256"]),
        "prediction_artifact_sha256": hashlib.sha256(Path("artifacts/prediction_control_gap.json").read_bytes()).hexdigest(),
        "closed_returns_remeasured": False,
        "control_claim": False,
        "is_agi": False,
        "is_learning_to_learn": False,
    }


def load_phase_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    loaded = yaml.safe_load(Path(path).read_text())
    locked = _locked_config()
    if loaded != locked:
        raise RuntimeError("return-phase config drifted from the locked protocol")
    return loaded


def assert_protocol_frozen(protocol_path: str | Path, cfg: dict[str, Any]) -> None:
    text = Path(protocol_path).read_text()
    start = text.find("<!-- protocol-lock")
    end = text.find("-->", start)
    if start < 0 or end < 0:
        raise RuntimeError("return-phase protocol lock is missing")
    locked: dict[str, str] = {}
    for line in text[start:end].splitlines():
        if ":" not in line or line.strip().startswith("<!--"):
            continue
        key, value = line.split(":", 1)
        locked[key.strip()] = value.strip()
    expected = {
        "episodes_per_task": str(int(cfg["episodes_per_task"])),
        "max_steps": str(int(cfg["max_steps"])),
        "early_steps": str(int(cfg["early_steps"])),
        "horizon": str(int(cfg["horizon"])),
        "n_candidates": str(int(cfg["n_candidates"])),
        "n_actions": str(int(cfg["n_actions"])),
        "n_student_seeds": str(int(cfg["n_student_seeds"])),
        "target_decoders": str(int(cfg["target_decoders"])),
        "student_kind": str(cfg["student_kind"]),
        "support_budget": str(int(cfg["support_budget"])),
        "primary_split": str(cfg["primary_split"]),
        "eval_env0": str(int(cfg["eval_env0"])),
        "planner_seed_base": str(int(cfg["planner_seed_base"])),
        "task_stride": str(int(cfg["task_stride"])),
        "share_min_abs": str(int(cfg["share_min_abs"])) if float(cfg["share_min_abs"]) == int(cfg["share_min_abs"]) else str(cfg["share_min_abs"]),
        "identity_atol": str(cfg["identity_atol"]),
        "time_limit_s": str(int(cfg["time_limit_s"])),
        "fresh_split_hash": str(cfg["fresh_split_hash"]),
        "fresh_support_hashes": ",".join(cfg["fresh_support_hashes"]),
        "control_artifact_sha256": str(cfg["control_artifact_sha256"]),
        "manifest_sha256": str(cfg["manifest_sha256"]),
        "prediction_artifact_sha256": str(cfg["prediction_artifact_sha256"]),
        "evidence_manifest_sha256": str(cfg["evidence_manifest_sha256"]),
        "starting_sha": str(cfg["starting_sha"]),
        "closed_returns_remeasured": "false",
        "control_claim": "false",
        "is_agi": "false",
        "is_learning_to_learn": "false",
    }
    for key, value in expected.items():
        if locked.get(key) != value:
            raise RuntimeError(f"protocol lock drifted for {key}: document={locked.get(key)!r} config={value!r}")


def episode_env_seed(env0: int, task: int, episode: int, stride: int = 100) -> int:
    return int(env0) + int(stride) * int(task) + int(episode)


def episode_planner_seed(base: int, task: int, episode: int, stride: int = 100) -> int:
    return int(base) + int(stride) * int(task) + int(episode)


def phase_seed_groups(cfg: dict[str, Any]) -> dict[str, set[int]]:
    env: set[int] = set()
    planner: set[int] = set()
    for task in range(len(cfg["fresh_task_ids"])):
        for episode in range(int(cfg["episodes_per_task"])):
            env.add(episode_env_seed(int(cfg["eval_env0"]), task, episode, int(cfg["task_stride"])))
            planner.add(episode_planner_seed(int(cfg["planner_seed_base"]), task, episode, int(cfg["task_stride"])))
    return {"eval_env": env, "planner_rng": planner}


def assert_phase_seeds(cfg: dict[str, Any]) -> None:
    occupied, gap_groups = diagnostic_seed_groups(load_prediction_config())
    blocked: set[int] = set()
    for seeds in list(occupied.values()) + list(gap_groups.values()):
        blocked |= set(seeds)
    for seeds in horizon_seed_groups(load_horizon_config()).values():
        blocked |= set(seeds)
    groups = phase_seed_groups(cfg)
    if groups["eval_env"] & groups["planner_rng"]:
        raise ValueError("evaluation resets and planner seeds overlap")
    expected = len(cfg["fresh_task_ids"]) * int(cfg["episodes_per_task"])
    if len(groups["eval_env"]) != expected or len(groups["planner_rng"]) != expected:
        raise ValueError("phase seeds are not unique")
    for name, seeds in groups.items():
        overlap = seeds & blocked
        if overlap:
            raise ValueError(f"{name} reuses a closed seed: {sorted(overlap)[:8]}")
        blocked |= seeds


def phase_deltas(student_rewards: np.ndarray, zero_rewards: np.ndarray, *, early_steps: int = EARLY_STEPS) -> dict[str, float]:
    """Student seeds are averaged first. Early is steps 0–15 and late is steps 16–199."""
    student = np.asarray(student_rewards, dtype=np.float64)
    zero = np.asarray(zero_rewards, dtype=np.float64)
    if student.ndim == 1:
        student = student.reshape(1, -1)
    if student.shape[1] != int(PENDULUM_MAX_STEPS) or zero.shape != (int(PENDULUM_MAX_STEPS),):
        raise ValueError("reward traces must cover 200 environment steps")
    if int(early_steps) != EARLY_STEPS:
        raise ValueError("the early window is locked at 16 steps")
    delta = student.mean(axis=0) - zero
    early = float(delta[:EARLY_STEPS].sum())
    late = float(delta[EARLY_STEPS:].sum())
    total = float(delta.sum())
    if abs((early + late) - total) > IDENTITY_ATOL:
        raise RuntimeError("early plus late does not equal the total return difference")
    return {"early": early, "late": late, "total": total}


def _excludes_zero(interval: dict[str, Any]) -> bool:
    return int(interval["n"]) == 10 and float(interval["lo"]) * float(interval["hi"]) > 0


def phase_percentages(early: list[float], late: list[float], total: list[float], *, min_abs: float = SHARE_MIN_ABS) -> dict[str, Any]:
    """Percentages require a ten-decoder total whose interval excludes 0 and whose denominators are not tiny."""
    if len(early) != len(late) or len(late) != len(total):
        raise ValueError("phase vectors must have the same decoder count")
    interval = seed_level_ci([float(value) for value in total])
    stable = _excludes_zero(interval) and all(abs(float(value)) >= float(min_abs) for value in total)
    if not stable:
        return {
            "reported": False,
            "reason": "the total difference does not have a stable nonzero denominator",
            "total_interval": interval,
        }
    early_share = [float(left) / float(right) for left, right in zip(early, total)]
    late_share = [float(left) / float(right) for left, right in zip(late, total)]
    return {
        "reported": True,
        "early_share": seed_level_ci(early_share),
        "late_share": seed_level_ci(late_share),
        "total_interval": interval,
    }


def describe_contribution(early: list[float], late: list[float], total: list[float]) -> dict[str, Any]:
    if len(total) != 10:
        return {"label": "incomplete", "percentages_reported": False, "early": None, "late": None, "total": None, "percentages": {"reported": False}}
    early_iv = seed_level_ci([float(value) for value in early])
    late_iv = seed_level_ci([float(value) for value in late])
    total_iv = seed_level_ci([float(value) for value in total])
    percentages = phase_percentages(early, late, total)
    label = "absolute_only"
    if percentages["reported"]:
        early_on = _excludes_zero(early_iv)
        late_on = _excludes_zero(late_iv)
        early_share = float(percentages["early_share"]["mean"])
        late_share = float(percentages["late_share"]["mean"])
        if early_on and not late_on and early_share > 0.5:
            label = "primarily_early"
        elif late_on and not early_on and late_share > 0.5:
            label = "primarily_late"
        elif early_on and late_on and float(early_iv["mean"]) * float(total_iv["mean"]) > 0 and float(late_iv["mean"]) * float(total_iv["mean"]) > 0:
            label = "both_phases"
        else:
            label = "unseparated"
    return {
        "label": label,
        "percentages_reported": bool(percentages["reported"]),
        "early": early_iv,
        "late": late_iv,
        "total": total_iv,
        "percentages": percentages,
    }


def require_complete(n_rows: int, expected: int) -> None:
    if int(n_rows) != int(expected):
        raise RuntimeError(f"return decomposition has {n_rows} paired episodes, not {expected}")


def _reward_ok(obs: np.ndarray, action: int, nxt: np.ndarray, reward: float) -> None:
    published = float(np.asarray(pendulum_step_reward(obs, int(action), nxt), dtype=np.float64).reshape(-1)[0])
    if abs(float(reward) - published) > 1e-5:
        raise RuntimeError("environment reward does not match the published pendulum cost")


def rollout_controller(env: Any, model: Any, *, reset_seed: int, planner_seed: int, max_steps: int) -> dict[str, Any]:
    planner = mpc_for_model(model, seed=int(planner_seed), enforce_time_budget=False)
    if int(planner.horizon) != 16 or int(planner.n_candidates) != 16 or planner.enforce_time_budget:
        raise RuntimeError("planner recipe is not the locked H=16 controller")
    planner.reset_episode(int(planner_seed))
    snapshot = _context_snapshot(model)
    obs, _info = env.reset(seed=int(reset_seed))
    rewards: list[float] = []
    observations: list[np.ndarray] = []
    for step in range(int(max_steps)):
        current = np.asarray(obs, dtype=np.float32).reshape(-1)
        observations.append(current.copy())
        action, info = planner.act(current)
        if int(info["n_scored"]) != 16:
            raise RuntimeError("a controller scored fewer than 16 candidate sequences")
        nxt, reward, terminated, truncated, _info = env.step(int(action))
        nxt_arr = np.asarray(nxt, dtype=np.float32).reshape(-1)
        _reward_ok(current, int(action), nxt_arr, float(reward))
        rewards.append(float(reward))
        obs = nxt
        if (terminated or truncated) and step < int(max_steps) - 1:
            raise RuntimeError("episode ended before 200 steps")
    _same_context(model, snapshot)
    if len(rewards) != int(max_steps):
        raise RuntimeError("episode did not record every reward")
    return {
        "rewards": np.asarray(rewards, dtype=np.float64),
        "observations": np.stack(observations),
        "model_states": int(max_steps) * 16 * 16,
    }


def _ancestor_or_raise(sha: str) -> None:
    probe = subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], check=False)
    if probe.returncode != 0:
        raise RuntimeError(f"HEAD does not contain the verified base {sha}")


def _fresh_supports(rep: dict[str, Any], cfg: dict[str, Any]) -> tuple[list[Any], list[Any], int]:
    forbidden = set(load_generalization_config()["forbidden_task_ids"])
    specs = list(assert_fresh_physics(rep))
    supports = []
    budget = int(cfg["support_budget"])
    for index, spec in enumerate(specs):
        support = _collect_named(
            spec,
            budget,
            int(cfg["fresh_support_env0"]) + 10 * index,
            int(cfg["fresh_support_base"]) + index,
            forbidden,
        )
        digest = prefix_hash(support, budget)
        if digest != cfg["fresh_support_hashes"][index]:
            raise RuntimeError(f"fresh support for {spec.task_id} does not match the closed context")
        supports.append(support)
    return specs, supports, budget * len(specs)


def _decoder_means(rows: list[dict[str, Any]], key: str) -> list[float]:
    grouped: dict[int, list[float]] = {}
    for row in rows:
        grouped.setdefault(int(row["decoder"]), []).append(float(row[key]))
    if len(grouped) != 10:
        raise RuntimeError("phase summary does not have ten decoders")
    return [float(np.mean(grouped[decoder])) for decoder in sorted(grouped)]


def _task_table(rows: list[dict[str, Any]], tasks: list[str]) -> list[dict[str, Any]]:
    table = []
    for task in tasks:
        chosen = [row for row in rows if row["task"] == task]
        early = _decoder_means(chosen, "early")
        late = _decoder_means(chosen, "late")
        total = _decoder_means(chosen, "total")
        summary = describe_contribution(early, late, total)
        table.append({
            "task": task,
            "early": summary["early"],
            "late": summary["late"],
            "total": summary["total"],
            "percentages_reported": summary["percentages_reported"],
            "percentages": summary["percentages"] if summary["percentages_reported"] else {"reported": False},
            "per_decoder_total": total,
        })
    return table


def _write_plot(path: Path, summary: dict[str, Any], tasks: list[dict[str, Any]]) -> None:
    width, height = 720, 320
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="36" y="28" font-family="sans-serif" font-size="15">Fresh return difference by phase</text>',
        f'<text x="36" y="48" font-family="sans-serif" font-size="11" fill="#444">{summary["label"]}. Early is steps 0-15. This is not a general control claim.</text>',
    ]
    values = []
    for row in tasks:
        values.append(float(row["early"]["mean"]))
        values.append(float(row["late"]["mean"]))
    limit = max([abs(value) for value in values] + [1.0])
    for index, row in enumerate(tasks):
        cx = 90 + index * 160
        for offset, key, color in ((-16, "early", "#1f4b99"), (8, "late", "#9a3412")):
            value = float(row[key]["mean"])
            height_px = abs(value) / limit * 180
            y = 220 - height_px if value >= 0 else 220
            parts.append(f'<rect x="{cx + offset}" y="{y:.1f}" width="22" height="{max(height_px, 1):.1f}" fill="{color}"/>')
        parts.append(f'<text x="{cx - 16}" y="250" font-family="sans-serif" font-size="11">{row["task"].replace("pendulum_ctrl_", "")}</text>')
    parts.append('<text x="36" y="290" font-family="sans-serif" font-size="11" fill="#1f4b99">early</text>')
    parts.append('<text x="90" y="290" font-family="sans-serif" font-size="11" fill="#9a3412">late</text>')
    parts.append("</svg>")
    path.write_text("".join(parts))


def run_return_phase(
    out_path: str | Path = "artifacts/return_phase_decomposition.json",
    plot_path: str | Path = "artifacts/return_phase_decomposition.svg",
) -> dict[str, Any]:
    cfg = load_phase_config()
    assert_protocol_frozen(PROTOCOL_PATH, cfg)
    assert_phase_seeds(cfg)
    _ancestor_or_raise(str(cfg["starting_sha"]))
    head = _git_meta()
    source_status = inspect_source_tree(str(head.get("revision") or ""))
    if source_status.get("source_dirty") or source_status.get("source_changed"):
        raise RuntimeError("return-phase source is dirty; commit the protocol before collecting returns")
    started = time.perf_counter()
    deadline = started + float(cfg["time_limit_s"])
    gap = load_prediction_config()
    if hashlib.sha256(Path("artifacts/prediction_control_gap.json").read_bytes()).hexdigest() != cfg["prediction_artifact_sha256"]:
        raise RuntimeError("prediction-control artifact hash mismatch")
    if str(gap["control_artifact_sha256"]) != str(cfg["control_artifact_sha256"]) or str(gap["manifest_sha256"]) != str(cfg["manifest_sha256"]):
        raise RuntimeError("closed control provenance drifted")
    provenance = verify_provenance(gap)
    rep = load_replication_config()
    confirmation = _confirmation_artifact(rep)
    specs, supports, support_steps = _fresh_supports(rep, cfg)
    fingerprints = {int(row["seed"]): row["decoder_digest"] for row in provenance["decoder_fingerprints"]}
    rows: list[dict[str, Any]] = []
    totals = {"env_steps": int(support_steps), "model_states": 0, "support_steps": int(support_steps)}
    finished: list[int] = []
    timed_out = False
    identity_max = 0.0
    seeds = list(range(int(cfg["target_decoders"])))
    for seed in seeds:
        if time.perf_counter() > deadline:
            timed_out = True
            break
        digest = fingerprints[int(seed)]
        for task_index, spec in enumerate(specs):
            if time.perf_counter() > deadline:
                timed_out = True
                break
            models = _models_for_task(int(seed), rep, cfg, confirmation, supports[task_index], digest)
            env = make_task_env(spec)
            try:
                for episode in range(int(cfg["episodes_per_task"])):
                    reset_seed = episode_env_seed(int(cfg["eval_env0"]), task_index, episode, int(cfg["task_stride"]))
                    planner_seed = episode_planner_seed(int(cfg["planner_seed_base"]), task_index, episode, int(cfg["task_stride"]))
                    student_rewards = []
                    student_obs = []
                    for student in range(int(cfg["n_student_seeds"])):
                        rolled = rollout_controller(
                            env, models[student], reset_seed=reset_seed, planner_seed=planner_seed, max_steps=int(cfg["max_steps"]),
                        )
                        student_rewards.append(rolled["rewards"])
                        student_obs.append(rolled["observations"])
                        totals["env_steps"] += int(cfg["max_steps"])
                        totals["model_states"] += int(rolled["model_states"])
                    zero = rollout_controller(
                        env, models["zero"], reset_seed=reset_seed, planner_seed=planner_seed, max_steps=int(cfg["max_steps"]),
                    )
                    totals["env_steps"] += int(cfg["max_steps"])
                    totals["model_states"] += int(zero["model_states"])
                    stacked_obs = np.stack(student_obs)
                    if not np.array_equal(stacked_obs[:, 0], np.repeat(zero["observations"][:1], int(cfg["n_student_seeds"]), axis=0)):
                        raise RuntimeError("paired resets did not share the initial observation")
                    deltas = phase_deltas(np.stack(student_rewards), zero["rewards"])
                    gap_abs = abs((deltas["early"] + deltas["late"]) - deltas["total"])
                    identity_max = max(identity_max, gap_abs)
                    mean_obs = stacked_obs.mean(axis=0)
                    distance = np.linalg.norm(mean_obs - zero["observations"], axis=1)
                    rows.append({
                        "decoder": int(seed),
                        "task": spec.task_id,
                        "physics": [float(value) for value in pendulum_physics_key(spec)],
                        "episode": int(episode),
                        "env_seed": int(reset_seed),
                        "planner_seed": int(planner_seed),
                        "student_rewards": np.stack(student_rewards).tolist(),
                        "zero_rewards": zero["rewards"].tolist(),
                        "early": deltas["early"],
                        "late": deltas["late"],
                        "total": deltas["total"],
                        "obs_l2_mean": float(np.mean(distance)),
                        "obs_l2_at_0": float(distance[0]),
                        "obs_l2_at_16": float(distance[16]),
                        "obs_l2_at_199": float(distance[199]),
                    })
            finally:
                env.close()
            if decoder_digest(models["zero"]) != digest:
                raise RuntimeError(f"evaluation changed decoder {seed}")
            print(f"phase scored decoder {seed} {spec.task_id}", flush=True)
        else:
            finished.append(int(seed))
            continue
        break
    expected = int(cfg["target_decoders"]) * len(cfg["fresh_task_ids"]) * int(cfg["episodes_per_task"])
    complete = (not timed_out) and finished == seeds and len(rows) == expected
    summary: dict[str, Any] = {"label": "incomplete", "percentages_reported": False}
    tasks: list[dict[str, Any]] = []
    divergence = None
    if complete:
        require_complete(len(rows), expected)
        if identity_max > IDENTITY_ATOL:
            raise RuntimeError("reward identity failed on a paired episode")
        summary = describe_contribution(_decoder_means(rows, "early"), _decoder_means(rows, "late"), _decoder_means(rows, "total"))
        tasks = _task_table(rows, list(cfg["fresh_task_ids"]))
        divergence = {
            "obs_l2_mean": seed_level_ci(_decoder_means(rows, "obs_l2_mean")),
            "obs_l2_at_16": seed_level_ci(_decoder_means(rows, "obs_l2_at_16")),
            "obs_l2_at_199": seed_level_ci(_decoder_means(rows, "obs_l2_at_199")),
            "limitation": "Trajectories diverge after the first action difference. Distance is descriptive.",
        }
    destination = assert_diagnostic_output_path(out_path)
    figure = assert_diagnostic_output_path(plot_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if complete:
        _write_plot(figure, summary, tasks)
    payload = {
        "protocol_id": cfg["protocol_id"],
        "starting_sha": cfg["starting_sha"],
        "implementation_sha": head.get("revision"),
        "source_dirty": False,
        "diagnostic_complete": bool(complete),
        "timed_out": bool(timed_out),
        "primary_label": summary["label"],
        "percentages_reported": bool(summary.get("percentages_reported")),
        "summary": summary,
        "by_task": tasks,
        "divergence": divergence,
        "identity_max_abs": float(identity_max),
        "identity_ok": bool(complete and identity_max <= IDENTITY_ATOL),
        "finished_decoders": finished,
        "independent_decoder_count": len(finished),
        "paired_episodes": rows,
        "env_steps": totals,
        "wall_clock_s": float(time.perf_counter() - started),
        "time_limit_s": int(cfg["time_limit_s"]),
        "closed_returns_remeasured": False,
        "control_claim": False,
        "control_improvement": False,
        "is_agi": False,
        "is_learning_to_learn": False,
        "provenance_verified": bool(provenance.get("verified")),
        "checkpoints_written": False,
        "notes": {
            "early_steps": "0-15",
            "late_steps": "16-199",
            "students_averaged_inside_decoder": True,
            "paired_reset_and_planner_seed": True,
            "trajectory_divergence_is_a_limitation": True,
            "closed_episode_gap_is_an_input": True,
            "percentage_requires_stable_nonzero_total": True,
        },
    }
    destination.write_text(dumps_strict(payload))
    print(
        f"phase label {summary['label']} complete={complete} percentages={summary.get('percentages_reported')}",
        flush=True,
    )
    return payload
