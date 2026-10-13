"""Unseen-physics confirmation of the locked direct-latent rule.

The decoder stays frozen. Only a support-fit latent may change. This is prediction
on the reserved confirmation physics, not control and not learning-to-learn.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import pendulum_context_confirmation, pendulum_physics_key
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_diagnosis import ROLLOUT_STARTS, complete_episodes
from nexus.world.context_optimization import _sha256
from nexus.world.context_pilot import _collect, prefix_hash
from nexus.world.context_pilot import _split_hash
from nexus.world.data import assert_disjoint_seeds
from nexus.world.direct_latent import (
    assert_support_query_separated,
    encoder_context,
    fit_from_support,
    frozen_network_digest,
    latent_screen,
    load_latent_config,
    latent_seed_groups,
    lock_network,
    score_with_z,
    score_with_z_mlp,
    support_for,
    vector_hash,
)
from nexus.world.direct_latent import _mean_cell
from nexus.world.frozen_dynamics import load_context_checkpoint, load_mlp_checkpoint, planned_env_seeds, records_from_cells
from nexus.world.result_checks import schema_completeness
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/direct_latent_confirmation.yaml")
PROTOCOL_PATH = Path("docs/NEXUS_DIRECT_LATENT_CONFIRMATION.md")
CONFIRM_LR = 0.1
CONFIRM_UPDATES = 256
SAME_DECODER = ("task", "zero", "global", "wrong", "encoder")
EXTERNAL = ("mlp_reference",)
LABELS = SAME_DECODER + EXTERNAL


def load_confirmation_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("confirmation config must be a mapping")
    expected = _locked_config()
    if cfg != expected:
        missing = sorted(set(expected) - set(cfg))
        extra = sorted(set(cfg) - set(expected))
        drifted = sorted(key for key in expected if key in cfg and cfg[key] != expected[key])
        raise ValueError(f"confirmation config drifted; missing={missing} extra={extra} drifted={drifted}")
    if list(cfg["rollout_starts"]) != list(ROLLOUT_STARTS):
        raise ValueError("rollout starts drifted")
    if float(cfg["learning_rate"]) != CONFIRM_LR or int(cfg["updates"]) != CONFIRM_UPDATES:
        raise ValueError("optimizer hyperparameters drifted from the locked rule")
    return cfg


def _locked_config() -> dict[str, Any]:
    return {
        "protocol_id": "direct_latent_confirmation_v1",
        "starting_sha": "f3ab5e6914d7c399be4235fdf4ffc628c78c952f",
        "prior_selection": "artifacts/direct_latent_selection.json",
        "prior_audit": "artifacts/direct_latent_audit.json",
        "prior_frozen_selection": "artifacts/frozen_dynamics_selection.json",
        "prior_frozen_audit": "artifacts/frozen_dynamics_audit.json",
        "confirm_hash": "87b83c41be34aa1a",
        "is_agi": False,
        "control_sweep": False,
        "replication_unit": "model_training_seed",
        "h_confirm": (
            "With all network weights fixed, the locked support-only latent rule lowers held-out "
            "query angular-velocity MAE on the reserved confirmation physics relative to zero context, "
            "the global vector, and a vector fit on the cyclic donor task's support."
        ),
        "n_seeds": 3,
        "n_tasks": 4,
        "task_ids": ["pendulum_ctx_c0", "pendulum_ctx_c1", "pendulum_ctx_c2", "pendulum_ctx_c3"],
        "physics": [[4.8, 1.0, 1.0], [15.2, 1.0, 1.0], [10.0, 0.35, 1.0], [11.8, 1.6, 0.75]],
        "support_budget": 128,
        "query_episodes": 4,
        "query_transitions": 800,
        "learning_rate": 0.1,
        "updates": 256,
        "angular_velocity_index": 2,
        "horizons": [3, 8, 16],
        "rollout_starts": [0, 32, 64, 96, 128, 160],
        "donor": "confirmation_task_(i+1)_mod_n",
        "screen_angvel_improvement": 0.05,
        "screen_min_positive_seeds": 2,
        "screen_max_worsening": 0.05,
        "support_env0": 64000,
        "query_env0": 68000,
        "support_base": 250000,
        "query_base": 251000,
        "time_limit_s": 3600,
        "same_decoder_conditions": ["task", "zero", "global", "wrong", "encoder"],
        "external_conditions": ["mlp_reference"],
        "parent_checkpoints": [
            {
                "seed": 0,
                "path": "artifacts/frozen_dynamics_checkpoints/seed0_history_u1000.pt",
                "sha256": "83e90a9b187cdffe5e39d794ce86abf65ef891fde011daf8e55b7eee1f348959",
                "frozen_network_sha256": "71d44b7880f145c99bc99f6b8e24921134e5b90f58dbf8c78f56d942daf80636",
                "global_vector_sha256": "d40d71a3e5c0e62ef158e08ec82617f10a8f6fcfeaac436744c9e9958b31f8ba",
            },
            {
                "seed": 1,
                "path": "artifacts/frozen_dynamics_checkpoints/seed1_history_u1000.pt",
                "sha256": "cd5400070a69238ce8e35ca036c57448b18664f7ce1e8600ac5a3aab2983ef3e",
                "frozen_network_sha256": "4bcdc147a80171bf6123b1bc9079f1174614e750a2337a75f9d3ef79942a3104",
                "global_vector_sha256": "4705c19a62e0547267705e1b10aeb4f06c1a62058ab077534b24a8f2cc4fdb33",
            },
            {
                "seed": 2,
                "path": "artifacts/frozen_dynamics_checkpoints/seed2_history_u1000.pt",
                "sha256": "254b097c5dbd3df02c463913c60392928aaed0584c6c29245e060ed25113b6fd",
                "frozen_network_sha256": "13090d27d02476584c39284cc045f19d9b727c33721e22186be25a055bc064ac",
                "global_vector_sha256": "9910f28a645a7a4d8a714cf0523f6c8a9c7b58b7dd71103e96a511583be31218",
            },
        ],
        "mlp_checkpoints": [
            {"seed": 0, "path": "artifacts/context_optimization_checkpoints/seed0_mlp_u1000.pt", "sha256": "4f4db2ca0ade8d2e19cb37971cf7343959edcdc17befe73e1aa9169e19c21cc2"},
            {"seed": 1, "path": "artifacts/context_optimization_checkpoints/seed1_mlp_u1000.pt", "sha256": "eb72c8c9f41d6e53a123e9f9b9aa86ce0540117e33a97c5617c164ff4456526f"},
            {"seed": 2, "path": "artifacts/context_optimization_checkpoints/seed2_mlp_u1000.pt", "sha256": "58dc9209c1435543b33cb48878785a30705bc9909090510631e40f7e95b466a1"},
        ],
        "prior_artifact_sha256": {
            "artifacts/direct_latent_selection.json": "ef99a31fd1c50ee27e4de35dff6c810397a22ab267622d1b4aa938cf4ffb5c5f",
            "artifacts/direct_latent_audit.json": "9681f5de77d53c8fafba54aa5c0e41eeb60cd39a8e0f4d8308615dcf7476f9dc",
            "artifacts/frozen_dynamics_selection.json": "b8506c2d9670692cfafdfc42fc6cffe2c36565b4219cfc22e39128cf84294f11",
            "artifacts/frozen_dynamics_audit.json": "72a65dee5ecb694b0c2137f05f8d885c200933df11f0f85a5b4cc0986af22ba3",
        },
    }


def confirmation_schema_from_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Planned grid. Produced rows cannot drop a seed, task, or condition."""
    labels = list(LABELS)
    return {
        "seed_ids": list(range(int(cfg["n_seeds"]))),
        "task_ids": list(cfg["task_ids"]),
        "labels": labels,
        "conditions_by_label": {label: [label] for label in labels},
        "metrics": ["mae", "rmse", "angvel_mae"],
        "horizons": ["3", "8", "16"],
        "per_dim": 3,
    }


def assert_split_matches(cfg: dict[str, Any]) -> tuple[Any, ...]:
    specs = pendulum_context_confirmation()
    live_hash = _split_hash(specs)
    if live_hash != cfg["confirm_hash"] or live_hash != "87b83c41be34aa1a":
        raise RuntimeError(f"confirmation split hash is {live_hash}, not the reserved hash")
    live_ids = [spec.task_id for spec in specs]
    live_physics = [list(pendulum_physics_key(spec)) for spec in specs]
    if live_ids != list(cfg["task_ids"]) or live_physics != cfg["physics"]:
        raise RuntimeError("confirmation task tuples do not match the locked split")
    if len(specs) != int(cfg["n_tasks"]):
        raise RuntimeError("confirmation task count drifted")
    return specs


def assert_protocol_frozen(protocol_path: str | Path, cfg: dict[str, Any]) -> dict[str, str]:
    path = Path(protocol_path)
    if not path.is_file():
        raise RuntimeError("confirmation is blocked until the protocol document is saved")
    text = path.read_text()
    start = text.find("<!-- protocol-lock")
    end = text.find("-->", start)
    if start < 0 or end < 0:
        raise RuntimeError("confirmation is blocked because the protocol lock block is missing")
    locked: dict[str, str] = {}
    for line in text[start:end].splitlines():
        if ":" not in line or line.strip().startswith("<!--"):
            continue
        key, value = line.split(":", 1)
        locked[key.strip()] = value.strip()
    required = {
        "confirm_hash": str(cfg["confirm_hash"]),
        "support_env0": str(int(cfg["support_env0"])),
        "query_env0": str(int(cfg["query_env0"])),
        "support_base": str(int(cfg["support_base"])),
        "query_base": str(int(cfg["query_base"])),
        "learning_rate": f"{float(cfg['learning_rate']):.1f}",
        "updates": str(int(cfg["updates"])),
        "support_budget": str(int(cfg["support_budget"])),
        "query_episodes": str(int(cfg["query_episodes"])),
        "query_transitions": str(int(cfg["query_transitions"])),
        "donor": str(cfg["donor"]),
        "horizons": "3,8,16",
        "screen_angvel_improvement": f"{float(cfg['screen_angvel_improvement']):.2f}",
        "screen_min_positive_seeds": str(int(cfg["screen_min_positive_seeds"])),
        "screen_max_worsening": f"{float(cfg['screen_max_worsening']):.2f}",
    }
    for key, value in required.items():
        if locked.get(key) != value:
            raise RuntimeError(f"confirmation is blocked because protocol {key}={locked.get(key)!r} is not {value!r}")
    return locked


def assert_prior_artifacts_unchanged(cfg: dict[str, Any]) -> None:
    for path, expected in cfg["prior_artifact_sha256"].items():
        file = Path(path)
        if not file.is_file():
            raise RuntimeError(f"prior artifact is missing: {path}")
        got = hashlib.sha256(file.read_bytes()).hexdigest()
        if got != expected:
            raise RuntimeError(f"prior artifact changed: {path}")


def assert_checkpoint_hashes(cfg: dict[str, Any]) -> None:
    for row in list(cfg["parent_checkpoints"]) + list(cfg["mlp_checkpoints"]):
        path = Path(row["path"])
        if not path.is_file():
            raise FileNotFoundError(path)
        got = _sha256(path)
        if got != row["sha256"]:
            raise RuntimeError(f"checkpoint hash mismatch for {path}")


def confirmation_seed_groups(cfg: dict[str, Any]) -> dict[str, set[int]]:
    groups = latent_seed_groups(load_latent_config())
    support: set[int] = set()
    query: set[int] = set()
    for i in range(int(cfg["n_tasks"])):
        support |= planned_env_seeds(int(cfg["support_budget"]), int(cfg["support_env0"]) + 10 * i)
        query |= planned_env_seeds(int(cfg["query_transitions"]), int(cfg["query_env0"]) + 10 * i)
    groups["confirmation_support"] = support
    groups["confirmation_query"] = query
    return groups


def assert_confirmation_seeds_disjoint(cfg: dict[str, Any]) -> None:
    named = confirmation_seed_groups(cfg)
    if not named["confirmation_support"] or not named["confirmation_query"]:
        raise RuntimeError("confirmation seeds were not registered")
    keys = list(named)
    for i, left in enumerate(keys):
        for right in keys[i + 1 :]:
            overlap = named[left] & named[right]
            if overlap:
                raise ValueError(f"collect seeds overlap between {left} and {right}: {sorted(overlap)[:8]}")


def fit_confirmation_latent(model: Any, support: Any, z_init: torch.Tensor, *, query: Any = None) -> dict[str, Any]:
    """Adam at the locked learning rate for the locked update count. Query is ignored."""
    return fit_from_support(
        model,
        support,
        z_init,
        lr=CONFIRM_LR,
        updates=CONFIRM_UPDATES,
        snapshot_at=(CONFIRM_UPDATES,),
        query=query,
    )


def task_level_report(records: list[dict[str, Any]], task_ids: list[str], *, improvement: float = 0.05) -> list[dict[str, Any]]:
    """Per confirmation task. These rows are not model-training replications."""
    out = []
    for task in task_ids:
        cells = [row for row in records if row["task"] == task]
        seeds = sorted({int(row["seed"]) for row in cells})

        def mean(label: str) -> float:
            values = [float(row["angvel_mae"]) for row in cells if row["label"] == label]
            return float(np.mean(values)) if values else float("nan")

        task_v = mean("task")
        controls = {name: mean(name) for name in ("zero", "global", "wrong")}
        misses = [name for name, value in controls.items() if not (task_v <= (1.0 - improvement) * value)]
        cell_misses = []
        for seed in seeds:
            by_label = {row["label"]: float(row["angvel_mae"]) for row in cells if int(row["seed"]) == seed}
            for name in ("zero", "global", "wrong"):
                if name in by_label and by_label.get("task", 1.0) >= by_label[name]:
                    cell_misses.append({"seed": seed, "control": name})
        out.append(
            {
                "task": task,
                "angvel_task": task_v,
                "angvel_zero": controls["zero"],
                "angvel_global": controls["global"],
                "angvel_wrong": controls["wrong"],
                "angvel_encoder": mean("encoder"),
                "angvel_mlp_reference": mean("mlp_reference"),
                "misses_five_percent": misses,
                "seed_cells_without_a_gain": cell_misses,
                "task_point_screen": len(misses) == 0,
            }
        )
    return out


def _apply_schema(records: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
    return schema_completeness(
        records,
        seed_ids=list(schema["seed_ids"]),
        task_ids=list(schema["task_ids"]),
        labels=list(schema["labels"]),
        conditions_by_label={key: list(value) for key, value in schema["conditions_by_label"].items()},
        metrics=tuple(schema["metrics"]),
        horizons=tuple(schema["horizons"]),
        per_dim=int(schema["per_dim"]),
    )


def _dim_mean(tasks: dict[str, Any], label: str, index: int) -> float:
    values = [float(task["labels"][label][label]["mae_per_dim"][index]) for task in tasks.values()]
    return float(np.mean(values)) if values else float("nan")


def _horizon_mean(tasks: dict[str, Any], label: str, horizon: str) -> float:
    values = [float(task["labels"][label][label]["rollout_mae"][horizon]) for task in tasks.values()]
    return float(np.mean(values)) if values else float("nan")


def _seed_rows(per_seed: list[dict[str, Any]]) -> list[dict[str, float]]:
    rows = []
    for seed in per_seed:
        tasks = seed["tasks"]
        row: dict[str, float] = {}
        for label in LABELS:
            row[f"angvel_{label}"] = _mean_cell(tasks, label, label, "angvel_mae")
            row[f"mae_{label}"] = _mean_cell(tasks, label, label, "mae")
            row[f"rmse_{label}"] = _mean_cell(tasks, label, label, "rmse")
            row[f"cos_{label}"] = _dim_mean(tasks, label, 0)
            row[f"sin_{label}"] = _dim_mean(tasks, label, 1)
            for horizon in ("3", "8", "16"):
                row[f"h{horizon}_{label}"] = _horizon_mean(tasks, label, horizon)
        rows.append(row)
    return rows


def _paired(rows: list[dict[str, float]], left: str, right: str) -> dict[str, Any]:
    deltas = [float(row[left]) - float(row[right]) for row in rows]
    out = dict(seed_level_ci(deltas))
    out["per_seed"] = deltas
    out["replication_unit"] = "model_training_seed"
    out["n_is_exploratory"] = True
    return out


def _bars(means: list[float], names: list[str], title: str) -> str:
    width, height, pad = 720, 360, 48
    finite = [value for value in means if np.isfinite(value)]
    hi = max(finite) if finite else 1.0
    hi = hi * 1.15 if hi > 0 else 1.0
    slot = (width - 2 * pad) / max(len(means), 1)
    colors = ["#1f4e79", "#6b6b6b", "#2e7d32", "#c45911", "#8e24aa", "#00838f"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">', '<rect width="100%" height="100%" fill="white"/>']
    parts.append(f'<text x="{pad}" y="24" font-size="14" fill="#222">{title}</text>')
    for i, (name, value) in enumerate(zip(names, means)):
        x = pad + i * slot + 8
        bar_h = 0.0 if not np.isfinite(value) else (height - 80) * (float(value) / hi)
        y = height - 40 - bar_h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{slot - 16:.1f}" height="{bar_h:.1f}" fill="{colors[i % len(colors)]}"/>')
        parts.append(f'<text x="{x:.1f}" y="{height - 22}" font-size="11" fill="#222">{name}</text>')
        if np.isfinite(value):
            parts.append(f'<text x="{x:.1f}" y="{y - 4:.1f}" font-size="11" fill="#222">{value:.3f}</text>')
    parts.append("</svg>")
    return "".join(parts)


def write_confirmation_plots(directory: str | Path, rows: list[dict[str, float]], task_report: list[dict[str, Any]]) -> list[str]:
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    names = ["task", "zero", "global", "wrong", "encoder", "mlp"]
    keys = ["angvel_task", "angvel_zero", "angvel_global", "angvel_wrong", "angvel_encoder", "angvel_mlp_reference"]
    means = [float(np.mean([row[key] for row in rows])) for key in keys]
    angvel_path = folder / "direct_latent_confirmation_angvel.svg"
    angvel_path.write_text(_bars(means, names, "Confirmation angular-velocity MAE"))
    dim_names = ["task cos", "global cos", "task sin", "global sin", "task ang", "global ang"]
    dim_keys = ["cos_task", "cos_global", "sin_task", "sin_global", "angvel_task", "angvel_global"]
    dim_means = [float(np.mean([row[key] for row in rows])) for key in dim_keys]
    dim_path = folder / "direct_latent_confirmation_dims.svg"
    dim_path.write_text(_bars(dim_means, dim_names, "Confirmation per-dimension MAE"))
    task_names = [row["task"].replace("pendulum_ctx_", "") for row in task_report]
    task_means = [float(row["angvel_task"]) for row in task_report]
    task_path = folder / "direct_latent_confirmation_tasks.svg"
    task_path.write_text(_bars(task_means, task_names, "Task latent angular-velocity MAE by confirmation task"))
    return [str(angvel_path), str(dim_path), str(task_path)]


def run_direct_latent_confirmation(
    *,
    protocol_path: str | Path = PROTOCOL_PATH,
    output_path: str | Path = "artifacts/direct_latent_confirmation.json",
    plot_dir: str | Path = "artifacts",
) -> dict[str, Any]:
    """Score the locked rule on the reserved physics. Collection starts only after the protocol check."""
    t0 = time.perf_counter()
    cfg = load_confirmation_config()
    assert_protocol_frozen(protocol_path, cfg)
    assert_prior_artifacts_unchanged(cfg)
    assert_confirmation_seeds_disjoint(cfg)
    assert_checkpoint_hashes(cfg)
    specs = assert_split_matches(cfg)
    selection = json.loads(Path(cfg["prior_selection"]).read_text())
    record = selection["selection_record"]
    if record.get("selection_recorded") is not True or float(record.get("chosen_lr")) != CONFIRM_LR or int(record.get("chosen_updates")) != CONFIRM_UPDATES:
        raise RuntimeError("the source selection did not lock this optimizer rule")
    deadline = t0 + float(cfg["time_limit_s"])
    horizons = [int(h) for h in cfg["horizons"]]
    angvel_index = int(cfg["angular_velocity_index"])
    budget = int(cfg["support_budget"])
    resources = {"support_env": 0, "query_env": 0, "optimizer_steps": 0, "support_examples_processed": 0}
    supports = []
    queries = []
    for i, spec in enumerate(specs):
        support = _collect(spec, budget, env0=int(cfg["support_env0"]) + 10 * i, base=int(cfg["support_base"]) + i)
        query_raw = _collect(spec, int(cfg["query_transitions"]), env0=int(cfg["query_env0"]) + 10 * i, base=int(cfg["query_base"]) + i)
        if {int(s) for s in np.unique(support.seed)} != planned_env_seeds(budget, int(cfg["support_env0"]) + 10 * i):
            raise RuntimeError(f"support seeds drifted for {spec.task_id}")
        if {int(s) for s in np.unique(query_raw.seed)} != planned_env_seeds(int(cfg["query_transitions"]), int(cfg["query_env0"]) + 10 * i):
            raise RuntimeError(f"query seeds drifted for {spec.task_id}")
        query = complete_episodes(query_raw, 16)
        if len(np.unique(query.episode_id)) != int(cfg["query_episodes"]):
            raise RuntimeError(f"{spec.task_id} produced {len(np.unique(query.episode_id))} query episodes")
        resources["support_env"] += int(support.env_interactions)
        resources["query_env"] += int(query_raw.env_interactions)
        supports.append(support)
        queries.append(query)
    assert_support_query_separated(*zip(supports, queries))
    assert_disjoint_seeds(*supports, *queries)
    per_seed: list[dict[str, Any]] = []
    support_before: list[float] = []
    support_after: list[float] = []
    grad_norms: list[float] = []
    nonfinite = 0
    for seed in range(int(cfg["n_seeds"])):
        if time.perf_counter() > deadline:
            raise RuntimeError("confirmation exceeded the time cap")
        parent = cfg["parent_checkpoints"][seed]
        model = load_context_checkpoint(Path(parent["path"]))
        lock_network(model)
        digest = frozen_network_digest(model)
        if digest != parent["frozen_network_sha256"]:
            raise RuntimeError(f"loaded network digest does not match the locked hash for seed {seed}")
        global_z = torch.tensor(record["global_vectors"][str(seed)], dtype=torch.float32)
        if vector_hash(global_z) != parent["global_vector_sha256"]:
            raise RuntimeError(f"global vector hash mismatch for seed {seed}")
        mlp = load_mlp_checkpoint(Path(cfg["mlp_checkpoints"][seed]["path"]), (64, 64))
        labels_by_task: dict[str, Any] = {}
        for task_index, spec in enumerate(specs):
            query = queries[task_index]
            real_support = supports[task_index].slice(np.arange(min(budget, len(supports[task_index]))))
            donor_ds = support_for(supports, task_index, "wrong")
            donor = donor_ds.slice(np.arange(min(budget, len(donor_ds))))
            if donor.task_id == spec.task_id:
                raise RuntimeError("wrong-support donor resolved to the same task")
            task_fit = fit_confirmation_latent(model, real_support, global_z, query=query)
            wrong_fit = fit_confirmation_latent(model, donor, global_z, query=query)
            if frozen_network_digest(model) != digest:
                raise RuntimeError("confirmation optimization changed the network")
            nonfinite += len(task_fit["nonfinite"]) + len(wrong_fit["nonfinite"])
            summary = task_fit["trace"]
            support_before.append(float(summary[0]["support_loss"]))
            support_after.append(float(summary[-1]["support_loss"]))
            grads = [row["grad_norm"] for row in summary if row["grad_norm"] is not None]
            if grads:
                grad_norms.append(float(np.mean(grads)))
            resources["optimizer_steps"] += CONFIRM_UPDATES * 2
            resources["support_examples_processed"] += CONFIRM_UPDATES * (len(real_support) + len(donor))
            task_z = task_fit["snapshots"][CONFIRM_UPDATES]
            wrong_z = wrong_fit["snapshots"][CONFIRM_UPDATES]
            labels_by_task[spec.task_id] = {
                "donor_task": specs[(task_index + 1) % len(specs)].task_id,
                "labels": {
                    "zero": {"zero": score_with_z(model, torch.zeros(model.context_dim()), query, horizons, angvel_index)},
                    "global": {"global": score_with_z(model, global_z, query, horizons, angvel_index)},
                    "task": {"task": score_with_z(model, task_z, query, horizons, angvel_index)},
                    "wrong": {"wrong": score_with_z(model, wrong_z, query, horizons, angvel_index)},
                    "encoder": {"encoder": score_with_z(model, encoder_context(model, real_support, budget), query, horizons, angvel_index)},
                    "mlp_reference": {"mlp_reference": score_with_z_mlp(mlp, query, horizons, angvel_index)},
                },
                "latent_norm_task": float(torch.linalg.vector_norm(task_z).item()),
                "latent_norm_global": float(torch.linalg.vector_norm(global_z).item()),
                "support_loss_before": float(summary[0]["support_loss"]),
                "support_loss_after": float(summary[-1]["support_loss"]),
            }
        per_seed.append(
            {
                "model_seed": seed,
                "tasks": labels_by_task,
                "frozen_network_sha256": digest,
                "parent_checkpoint_sha256": parent["sha256"],
            }
        )
    schema = confirmation_schema_from_config(cfg)
    if schema["task_ids"] != list(cfg["task_ids"]) or schema["seed_ids"] != [0, 1, 2]:
        raise RuntimeError("confirmation schema was not built from the locked grid")
    raw_records = records_from_cells(per_seed)
    completeness = _apply_schema(raw_records, schema)
    rows = _seed_rows(per_seed)
    screen = latent_screen(
        rows,
        improvement=float(cfg["screen_angvel_improvement"]),
        min_positive_seeds=int(cfg["screen_min_positive_seeds"]),
        max_worsening=float(cfg["screen_max_worsening"]),
        frozen_ok=len({seed["frozen_network_sha256"] for seed in per_seed}) == len(per_seed),
        complete=bool(completeness["declared_complete"]) and nonfinite == 0,
    )
    screen["stability_ok"] = nonfinite == 0
    screen["pass"] = bool(screen["pass"] and screen["stability_ok"])
    screen["external_mlp_is_not_a_same_decoder_control"] = True
    tasks = task_level_report(raw_records, list(cfg["task_ids"]), improvement=float(cfg["screen_angvel_improvement"]))
    head = _git_meta()
    sha = str(head.get("revision") or "")
    source_status = inspect_source_tree(sha) if sha else {"source_dirty": True}
    before = float(np.mean(support_before)) if support_before else float("nan")
    after = float(np.mean(support_after)) if support_after else float("nan")
    payload = {
        "protocol_id": cfg["protocol_id"],
        "hypothesis": cfg["h_confirm"],
        "implementation_sha": sha if not source_status.get("source_dirty") else None,
        "source_dirty": bool(source_status.get("source_dirty", True)),
        "git": head,
        "confirm_hash": cfg["confirm_hash"],
        "learning_rate": CONFIRM_LR,
        "updates": CONFIRM_UPDATES,
        "replication_unit": "model_training_seed",
        "n_seeds_exploratory": True,
        "schema": schema,
        "raw_records": raw_records,
        "per_seed_metrics": rows,
        "summary": {key: seed_level_ci([float(row[key]) for row in rows]) for key in rows[0]},
        "paired_contrasts": {
            "zero_minus_task": _paired(rows, "angvel_zero", "angvel_task"),
            "global_minus_task": _paired(rows, "angvel_global", "angvel_task"),
            "wrong_minus_task": _paired(rows, "angvel_wrong", "angvel_task"),
            "encoder_minus_task": _paired(rows, "angvel_encoder", "angvel_task"),
            "mlp_minus_task": _paired(rows, "angvel_mlp_reference", "angvel_task"),
            "task_minus_global_mae": _paired(rows, "mae_task", "mae_global"),
            "task_minus_global_h16": _paired(rows, "h16_task", "h16_global"),
            "task_minus_global_cos": _paired(rows, "cos_task", "cos_global"),
            "task_minus_global_sin": _paired(rows, "sin_task", "sin_global"),
        },
        "task_level": tasks,
        "support_loss_before": before,
        "support_loss_after": after,
        "support_improved": bool(np.isfinite(before) and np.isfinite(after) and after < before),
        "mean_grad_norm": None if not grad_norms else float(np.mean(grad_norms)),
        "max_grad_norm": None if not grad_norms else float(np.max(grad_norms)),
        "nonfinite_steps": int(nonfinite),
        "frozen_network_sha256": {str(seed["model_seed"]): seed["frozen_network_sha256"] for seed in per_seed},
        "screen": screen,
        "classification": _classify(screen, tasks),
        "completeness": completeness,
        "declared_complete": bool(completeness["declared_complete"]),
        "resources": resources,
        "data_hashes": {
            "support": [prefix_hash(ds, len(ds)) for ds in supports],
            "query": [prefix_hash(ds, len(ds)) for ds in queries],
        },
        "plots": write_confirmation_plots(plot_dir, rows, tasks),
        "wall_clock_s": time.perf_counter() - t0,
        "confirm_evaluated": True,
        "control_evaluated": False,
        "is_agi": False,
        "is_learning_to_learn": False,
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(dumps_strict(payload))
    payload["wall_clock_s"] = time.perf_counter() - t0
    return payload


def _classify(screen: dict[str, Any], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    failed_tasks = [row["task"] for row in tasks if not row["task_point_screen"]]
    if screen.get("pass"):
        label = "confirmation_passed"
        next_step = "A small teacher-student fit can ask whether a history encoder can predict this support-optimized latent."
    else:
        label = "confirmation_failed"
        next_step = "Inspect the confirmation tasks that missed the screen before changing the encoder or the architecture. Do not retune this protocol."
    return {
        "label": label,
        "tasks_missing_the_point_screen": failed_tasks,
        "next_step": next_step,
        "claims_not_made": ["universal generalization", "amortized inference", "control improvement", "learning-to-learn", "AGI"],
    }
