"""Does the existing encoder infer a useful latent on physics it was not trained on?

The student is the 584-parameter mean-pooling encoder. The decoder and the teacher
rule stay frozen. Development query error chooses the checkpoint. Validation physics
are scored after that choice. Neither reserved confirmation split is collected.
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
from torch import nn

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import (
    pendulum_amortized_confirmation,
    pendulum_context_confirmation,
    pendulum_context_development,
    pendulum_context_train,
    pendulum_latent_train,
    pendulum_latent_validation,
    pendulum_physics_key,
)
from nexus.world.amortized_latent import decoder_digest
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_diagnosis import ROLLOUT_STARTS, complete_episodes
from nexus.world.context_model import CONTEXT_DIM, ENCODER_HIDDEN
from nexus.world.context_optimization import _sha256
from nexus.world.context_pilot import _collect, _split_hash, _svg, prefix_hash
from nexus.world.data import TransitionDataset
from nexus.world.direct_latent import (
    assert_support_query_separated,
    encoder_context,
    fit_from_support,
    lock_network,
    score_with_z,
    vector_hash,
)
from nexus.world.encoder_representability import representability_seed_groups
from nexus.world.frozen_dynamics import load_context_checkpoint, planned_env_seeds, records_from_cells
from nexus.world.result_checks import schema_completeness
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/latent_generalization.yaml")
PROTOCOL_PATH = Path("docs/NEXUS_LATENT_GENERALIZATION.md")
TEACHER_LR = 0.1
TEACHER_UPDATES = 256
STUDENT_LR = 0.01
FIXED_LABELS = ("zero", "global", "encoder", "teacher")


def load_generalization_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("generalization config must be a mapping")
    expected = _locked_config()
    if cfg != expected:
        missing = sorted(set(expected) - set(cfg))
        extra = sorted(set(cfg) - set(expected))
        drifted = sorted(key for key in expected if key in cfg and cfg[key] != expected[key])
        raise ValueError(f"generalization config drifted; missing={missing} extra={extra} drifted={drifted}")
    if float(cfg["student_learning_rate"]) != STUDENT_LR:
        raise ValueError("student learning rate drifted")
    if float(cfg["teacher_learning_rate"]) != TEACHER_LR or int(cfg["teacher_updates"]) != TEACHER_UPDATES:
        raise ValueError("teacher rule drifted")
    if int(cfg["encoder_hidden"]) != ENCODER_HIDDEN or int(cfg["context_dim"]) != CONTEXT_DIM or int(cfg["n_parameters"]) != 584:
        raise ValueError("encoder capacity drifted")
    if list(cfg["rollout_starts"]) != list(ROLLOUT_STARTS):
        raise ValueError("rollout starts drifted")
    return cfg


def _locked_config() -> dict[str, Any]:
    train_rows = [(g, m, l) for g in (7.3, 8.7, 13.2) for m in (0.65, 1.05) for l in (0.78, 1.22)]
    return {
        "protocol_id": "latent_encoder_generalization_v1",
        "starting_sha": "cc0341c3df6a3fc6e0127b068258c5f805280450",
        "teacher_artifact": "artifacts/amortized_latent_dev.json",
        "teacher_artifact_sha256": "cd120f53ffdd1efbaaff8b632faad01b251e3b4e4afccd201af28c267ac1162f",
        "prior_selection": "artifacts/direct_latent_selection.json",
        "prior_selection_sha256": "ef99a31fd1c50ee27e4de35dff6c810397a22ab267622d1b4aa938cf4ffb5c5f",
        "forbidden_confirm_hash": "87b83c41be34aa1a",
        "amort_confirm_hash": "d1fa621351d286cf",
        "train_split_hash": "a3e558f2eeea1298",
        "val_split_hash": "601715664052382b",
        "dev_split_hash": "e3d6d6dd1a08cf4f",
        "is_agi": False,
        "is_learning_to_learn": False,
        "control_sweep": False,
        "confirmation_evaluated": False,
        "h_generalize": (
            "The existing 584-parameter encoder, trained at learning rate 0.01 on a broader grid of "
            "support-specific teacher codes, lowers held-out development angular-velocity error below "
            "zero context and below the frozen encoder."
        ),
        "n_decoder_seeds": 3,
        "n_student_seeds": 5,
        "n_train_supports": 2,
        "support_budget": 128,
        "query_episodes": 4,
        "query_transitions": 800,
        "epochs": [40, 100, 200],
        "student_learning_rate": 0.01,
        "teacher_learning_rate": 0.1,
        "teacher_updates": 256,
        "encoder_hidden": 32,
        "context_dim": 8,
        "n_parameters": 584,
        "angular_velocity_index": 2,
        "horizons": [3, 8, 16],
        "rollout_starts": [0, 32, 64, 96, 128, 160],
        "mean_fit_l2": 0.25,
        "history_fail_l2": 0.5,
        "teacher_pair_l2": 0.5,
        "recovery_min_relative": 0.05,
        "broad_h0_env0": 96000,
        "broad_h0_base": 262000,
        "broad_h1_env0": 97000,
        "broad_h1_base": 263000,
        "history_env0": 98000,
        "history_base": 264000,
        "val_support_env0": 99000,
        "val_support_base": 265000,
        "val_query_env0": 100000,
        "val_query_base": 266000,
        "dev_support_env0": 74000,
        "dev_support_base": 256000,
        "dev_query_env0": 76000,
        "dev_query_base": 257000,
        "baseline_support_env0": 72000,
        "baseline_support_base": 255000,
        "time_limit_s": 1800,
        "train_physics": [list(row) for row in train_rows],
        "val_physics": [[8.2, 0.95, 1.08], [11.6, 1.12, 0.92], [9.8, 0.58, 1.18], [12.7, 1.42, 1.08]],
        "train_task_ids": [f"pendulum_lat_tr{i}" for i in range(12)],
        "val_task_ids": [f"pendulum_lat_va{i}" for i in range(4)],
        "dev_task_ids": [f"pendulum_ctx_dev{i}" for i in range(3)],
        "baseline_task_ids": [f"pendulum_ctx_tr{i}" for i in range(8)],
        "dev_support_hashes": ["f9da7cd596004681", "a384f4090a0be298", "a6b676ab2d289b90"],
        "dev_query_hashes": ["cdb2c816fa4b235e", "0e8f4b2d167c2ab6", "1f954f66b08b219d"],
        "forbidden_task_ids": [f"pendulum_ctx_c{i}" for i in range(4)] + [f"pendulum_amort_c{i}" for i in range(4)],
        "parent_checkpoints": [
            {"seed": 0, "path": "artifacts/frozen_dynamics_checkpoints/seed0_history_u1000.pt", "sha256": "83e90a9b187cdffe5e39d794ce86abf65ef891fde011daf8e55b7eee1f348959", "global_vector_sha256": "d40d71a3e5c0e62ef158e08ec82617f10a8f6fcfeaac436744c9e9958b31f8ba"},
            {"seed": 1, "path": "artifacts/frozen_dynamics_checkpoints/seed1_history_u1000.pt", "sha256": "cd5400070a69238ce8e35ca036c57448b18664f7ce1e8600ac5a3aab2983ef3e", "global_vector_sha256": "4705c19a62e0547267705e1b10aeb4f06c1a62058ab077534b24a8f2cc4fdb33"},
            {"seed": 2, "path": "artifacts/frozen_dynamics_checkpoints/seed2_history_u1000.pt", "sha256": "254b097c5dbd3df02c463913c60392928aaed0584c6c29245e060ed25113b6fd", "global_vector_sha256": "9910f28a645a7a4d8a714cf0523f6c8a9c7b58b7dd71103e96a511583be31218"},
        ],
    }


def broad_label(epoch: int) -> str:
    return f"broad_e{int(epoch)}"


def baseline_label(epoch: int) -> str:
    return f"baseline_e{int(epoch)}"


def combined_seed(decoder: int, student: int, n_student: int) -> int:
    return int(decoder) * int(n_student) + int(student)


def assert_protocol_frozen(protocol_path: str | Path, cfg: dict[str, Any]) -> None:
    path = Path(protocol_path)
    if not path.is_file():
        raise RuntimeError("generalization is blocked until the protocol document is saved")
    text = path.read_text()
    start = text.find("<!-- protocol-lock")
    end = text.find("-->", start)
    if start < 0 or end < 0:
        raise RuntimeError("generalization is blocked because the protocol lock block is missing")
    locked: dict[str, str] = {}
    for line in text[start:end].splitlines():
        if ":" not in line or line.strip().startswith("<!--"):
            continue
        key, value = line.split(":", 1)
        locked[key.strip()] = value.strip()
    required = {
        "train_split_hash": str(cfg["train_split_hash"]),
        "val_split_hash": str(cfg["val_split_hash"]),
        "dev_split_hash": str(cfg["dev_split_hash"]),
        "forbidden_confirm_hash": str(cfg["forbidden_confirm_hash"]),
        "amort_confirm_hash": str(cfg["amort_confirm_hash"]),
        "teacher_lr": f"{float(cfg['teacher_learning_rate']):.1f}",
        "teacher_updates": str(int(cfg["teacher_updates"])),
        "student_lr": f"{float(cfg['student_learning_rate']):.2f}",
        "epochs": ",".join(str(int(v)) for v in cfg["epochs"]),
        "n_student_seeds": str(int(cfg["n_student_seeds"])),
        "n_train_supports": str(int(cfg["n_train_supports"])),
        "support_budget": str(int(cfg["support_budget"])),
        "mean_fit_l2": f"{float(cfg['mean_fit_l2']):.2f}",
        "history_fail_l2": f"{float(cfg['history_fail_l2']):.1f}",
        "n_parameters": str(int(cfg["n_parameters"])),
        "broad_h0_env0": str(int(cfg["broad_h0_env0"])),
        "dev_support_env0": str(int(cfg["dev_support_env0"])),
        "dev_query_env0": str(int(cfg["dev_query_env0"])),
    }
    for key, value in required.items():
        if locked.get(key) != value:
            raise RuntimeError(f"generalization is blocked because protocol {key}={locked.get(key)!r} is not {value!r}")


def assert_physics(cfg: dict[str, Any]) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
    train = pendulum_latent_train()
    val = pendulum_latent_validation()
    dev = pendulum_context_development()
    if _split_hash(train) != cfg["train_split_hash"] or [s.task_id for s in train] != list(cfg["train_task_ids"]):
        raise RuntimeError("broad training physics drifted")
    if _split_hash(val) != cfg["val_split_hash"] or [s.task_id for s in val] != list(cfg["val_task_ids"]):
        raise RuntimeError("validation physics drifted")
    if _split_hash(dev) != cfg["dev_split_hash"] or [s.task_id for s in dev] != list(cfg["dev_task_ids"]):
        raise RuntimeError("development physics drifted")
    if [list(pendulum_physics_key(s)) for s in train] != cfg["train_physics"]:
        raise RuntimeError("training physics values drifted")
    if [list(pendulum_physics_key(s)) for s in val] != cfg["val_physics"]:
        raise RuntimeError("validation physics values drifted")
    if _split_hash(pendulum_context_confirmation()) != cfg["forbidden_confirm_hash"]:
        raise RuntimeError("the direct-latent confirmation split changed")
    if _split_hash(pendulum_amortized_confirmation()) != cfg["amort_confirm_hash"]:
        raise RuntimeError("the amortized confirmation split changed")
    forbidden_ids = set(cfg["forbidden_task_ids"])
    used = [s for s in (*train, *val, *dev, *pendulum_context_train())]
    if forbidden_ids & {s.task_id for s in used}:
        raise RuntimeError("a reserved confirmation task entered the generalization split")
    keys = [pendulum_physics_key(s) for s in used]
    keys += [pendulum_physics_key(s) for s in (*pendulum_context_confirmation(), *pendulum_amortized_confirmation())]
    if len(keys) != len(set(keys)):
        raise RuntimeError("generalization physics are not disjoint from each other or from the reserved splits")
    return train, val, dev


def generalization_seed_groups(cfg: dict[str, Any]) -> dict[str, set[int]]:
    groups = representability_seed_groups(load_representability_cfg())
    spec = {
        "gen_broad_h0": (int(cfg["support_budget"]), int(cfg["broad_h0_env0"]), len(cfg["train_task_ids"])),
        "gen_broad_h1": (int(cfg["support_budget"]), int(cfg["broad_h1_env0"]), len(cfg["train_task_ids"])),
        "gen_history": (int(cfg["support_budget"]), int(cfg["history_env0"]), len(cfg["train_task_ids"])),
        "gen_val_support": (int(cfg["support_budget"]), int(cfg["val_support_env0"]), len(cfg["val_task_ids"])),
        "gen_val_query": (int(cfg["query_transitions"]), int(cfg["val_query_env0"]), len(cfg["val_task_ids"])),
    }
    for name, (n, env0, n_tasks) in spec.items():
        seeds: set[int] = set()
        for i in range(n_tasks):
            seeds |= planned_env_seeds(n, env0 + 10 * i)
        groups[name] = seeds
    return groups


def load_representability_cfg() -> dict[str, Any]:
    from nexus.world.encoder_representability import load_representability_config

    return load_representability_config()


def assert_seeds_disjoint(cfg: dict[str, Any]) -> None:
    named = generalization_seed_groups(cfg)
    keys = list(named)
    for i, left in enumerate(keys):
        for right in keys[i + 1 :]:
            overlap = named[left] & named[right]
            if overlap:
                raise ValueError(f"collect seeds overlap between {left} and {right}: {sorted(overlap)[:8]}")


def assert_checkpoint_hashes(cfg: dict[str, Any]) -> None:
    for row in cfg["parent_checkpoints"]:
        if _sha256(Path(row["path"])) != row["sha256"]:
            raise RuntimeError(f"checkpoint hash mismatch for {row['path']}")
    artifact = Path(cfg["teacher_artifact"])
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != cfg["teacher_artifact_sha256"]:
        raise RuntimeError("saved teacher artifact hash mismatch")
    selection = Path(cfg["prior_selection"])
    if hashlib.sha256(selection.read_bytes()).hexdigest() != cfg["prior_selection_sha256"]:
        raise RuntimeError("global-vector artifact hash mismatch")


def dev_schema(cfg: dict[str, Any]) -> dict[str, Any]:
    labels = [broad_label(epoch) for epoch in cfg["epochs"]]
    labels += [baseline_label(epoch) for epoch in cfg["epochs"]]
    labels += list(FIXED_LABELS)
    n_student = int(cfg["n_student_seeds"])
    return {
        "seed_ids": [combined_seed(d, s, n_student) for d in range(int(cfg["n_decoder_seeds"])) for s in range(n_student)],
        "task_ids": list(cfg["dev_task_ids"]),
        "labels": labels,
        "conditions_by_label": {label: [label] for label in labels},
        "metrics": ["mae", "rmse", "angvel_mae"],
        "horizons": ["3", "8", "16"],
        "per_dim": 3,
    }


def choose_epoch(dev_means: dict[int, float]) -> int:
    """Lowest development angular-velocity error. Ties prefer the earlier checkpoint."""
    if not dev_means:
        raise ValueError("no development checkpoint scores")
    ranked = sorted((float(value), int(epoch)) for epoch, value in dev_means.items())
    return int(ranked[0][1])


def development_gate(student: float, zero: float, encoder: float) -> bool:
    return bool(np.isfinite(student) and np.isfinite(zero) and np.isfinite(encoder) and student < zero and student < encoder)


def recommend(gate: bool, val_gate: bool, train_l2: float, history_l2: float, teacher_pair_median: float, cfg: dict[str, Any]) -> str:
    if gate and val_gate:
        return "new_confirmation"
    if gate and not val_gate:
        return "hold_confirmation"
    if not np.isfinite(train_l2) or float(train_l2) > float(cfg["mean_fit_l2"]):
        if np.isfinite(teacher_pair_median) and float(teacher_pair_median) > float(cfg["teacher_pair_l2"]):
            return "label_variability"
        return "training_budget"
    if not np.isfinite(history_l2) or float(history_l2) > float(cfg["history_fail_l2"]):
        return "attention_pool"
    return "more_source_tasks"


def assert_pair_binding(support_hash: str, teacher_support_hash: str) -> None:
    if support_hash != teacher_support_hash:
        raise RuntimeError("refusing to train on a teacher fitted to a different support history")


def _apply(records: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
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


def _mean_angvel(records: list[dict[str, Any]], label: str, seed_ids: list[int] | None = None) -> float:
    values = [float(row["angvel_mae"]) for row in records if row["label"] == label and (seed_ids is None or int(row["seed"]) in seed_ids)]
    return float(np.mean(values)) if values else float("nan")


def _student_seed_means(records: list[dict[str, Any]], label: str, cfg: dict[str, Any], task_ids: list[str] | None = None) -> list[float]:
    n_student = int(cfg["n_student_seeds"])
    out = []
    for student in range(n_student):
        ids = [combined_seed(decoder, student, n_student) for decoder in range(int(cfg["n_decoder_seeds"]))]
        values = [
            float(row["angvel_mae"])
            for row in records
            if row["label"] == label and int(row["seed"]) in ids and (task_ids is None or row["task"] in task_ids)
        ]
        out.append(float(np.mean(values)) if values else float("nan"))
    return out


def _paired(records: list[dict[str, Any]], student_label: str, control: str, cfg: dict[str, Any]) -> dict[str, Any]:
    n_student = int(cfg["n_student_seeds"])
    deltas = []
    for student in range(n_student):
        ids = [combined_seed(decoder, student, n_student) for decoder in range(int(cfg["n_decoder_seeds"]))]
        deltas.append(_mean_angvel(records, control, ids) - _mean_angvel(records, student_label, ids))
    return {"per_seed": deltas, "interval": seed_level_ci(deltas), "sign": "control_minus_student"}


def _metric_summary(records: list[dict[str, Any]], label: str) -> dict[str, Any]:
    rows = [row for row in records if row["label"] == label]
    if not rows:
        return {}
    dims = np.mean(np.asarray([row["mae_per_dim"] for row in rows], dtype=np.float64), axis=0)
    distances = [row["latent_l2"] for row in rows if row.get("latent_l2") is not None]
    return {
        "mae": float(np.mean([row["mae"] for row in rows])),
        "angvel_mae": float(np.mean([row["angvel_mae"] for row in rows])),
        "cos_mae": float(dims[0]),
        "sin_mae": float(dims[1]),
        "rollout_mae": {h: float(np.mean([row["rollout_mae"][h] for row in rows])) for h in ("3", "8", "16")},
        "latent_l2": None if not distances else float(np.mean(distances)),
    }


def _collect_checked(spec: Any, n: int, env0: int, base: int, forbidden: set[str]) -> TransitionDataset:
    if spec.task_id in forbidden:
        raise RuntimeError(f"refusing to collect reserved task {spec.task_id}")
    ds = _collect(spec, n, env0=env0, base=base)
    if {int(seed) for seed in np.unique(ds.seed)} != planned_env_seeds(n, env0):
        raise RuntimeError(f"collect seeds drifted for {spec.task_id}")
    return ds


def _fit_teacher(model: Any, support: TransitionDataset, global_z: torch.Tensor) -> torch.Tensor:
    fitted = fit_from_support(model, support, global_z, lr=TEACHER_LR, updates=TEACHER_UPDATES, snapshot_at=(TEACHER_UPDATES,))
    return fitted["snapshots"][TEACHER_UPDATES]


def _support_loss(model: Any, ds: TransitionDataset, vector: torch.Tensor) -> float:
    with torch.no_grad():
        value = model.query_loss(ds.obs, ds.action, ds.next_obs, ds.terminated, vector.detach())
    return float(value.item())


def _infer(model: Any, state: dict[str, torch.Tensor], support: TransitionDataset, budget: int) -> torch.Tensor:
    probe = model.clone_frozen()
    probe.encoder.load_state_dict(state)
    return encoder_context(probe, support.slice(np.arange(min(int(budget), len(support)))), budget)


def _cell(model: Any, vector: torch.Tensor, query: TransitionDataset, teacher_z: torch.Tensor, horizons: list[int], angvel_index: int) -> dict[str, Any]:
    cell = score_with_z(model, vector, query, horizons, angvel_index)
    cell["latent_l2"] = float(torch.linalg.vector_norm(vector.detach() - teacher_z.detach()).item())
    return cell


def _pair_distances(model: Any, supports: list[TransitionDataset], teachers: list[torch.Tensor], state: dict[str, torch.Tensor], budget: int) -> list[float]:
    out = []
    with torch.no_grad():
        for support, teacher in zip(supports, teachers):
            z = _infer(model, state, support, budget)
            out.append(float(torch.linalg.vector_norm(z - teacher).item()))
    return out


def train_pairs(
    model: Any,
    supports: list[TransitionDataset],
    teachers: list[torch.Tensor],
    *,
    epochs: int,
    checkpoints: list[int],
    lr: float,
    seed: int,
    init_state: dict[str, torch.Tensor],
    decoder_before: str,
    budget: int,
) -> tuple[dict[int, dict[str, torch.Tensor]], dict[int, dict[str, float]], float]:
    if int(model.encoder.hidden) != ENCODER_HIDDEN or int(model.encoder.z_dim) != CONTEXT_DIM:
        raise RuntimeError("refusing to train an encoder whose capacity differs from the existing history encoder")
    if int(sum(param.numel() for param in model.encoder.parameters())) != 584:
        raise RuntimeError("encoder parameter count is not 584")
    model.encoder.load_state_dict(init_state)
    for param in model.encoder.parameters():
        param.requires_grad_(True)
    for param in model.net.parameters():
        param.requires_grad_(False)
    opt = torch.optim.Adam(model.encoder.parameters(), lr=float(lr))
    rng = torch.Generator()
    rng.manual_seed(int(seed))
    wanted = {int(step) for step in checkpoints}
    snapshots: dict[int, dict[str, torch.Tensor]] = {}
    train_l2: dict[int, dict[str, float]] = {}
    last_grad = 0.0
    n_pairs = len(supports)
    for epoch in range(1, int(epochs) + 1):
        order = torch.randperm(n_pairs, generator=rng).tolist()
        for index in order:
            opt.zero_grad(set_to_none=True)
            z = model.encode(supports[index].obs, supports[index].action, supports[index].next_obs, differentiable=True)
            loss = nn.functional.mse_loss(z, teachers[index].detach())
            if not torch.isfinite(loss.detach()):
                raise RuntimeError("generalization training produced a nonfinite loss; refusing to continue")
            loss.backward()
            grads = []
            for param in model.encoder.parameters():
                if param.grad is None or not torch.isfinite(param.grad).all():
                    raise RuntimeError("encoder gradient was missing or nonfinite")
                grads.append(param.grad.detach().reshape(-1))
            for name, param in model.net.named_parameters():
                if param.grad is not None:
                    raise RuntimeError(f"decoder parameter {name} received a gradient")
            last_grad = float(torch.cat(grads).norm().item())
            opt.step()
        if decoder_digest(model) != decoder_before:
            raise RuntimeError("student training changed the decoder or normalization")
        if epoch in wanted:
            state = {key: value.detach().cpu().clone() for key, value in model.encoder.state_dict().items()}
            dists = _pair_distances(model, supports, teachers, state, budget)
            snapshots[epoch] = state
            train_l2[epoch] = {"mean": float(np.mean(dists)), "max": float(np.max(dists))}
    if set(snapshots) != wanted:
        raise RuntimeError("training missed a locked checkpoint")
    return snapshots, train_l2, last_grad


def _saved_vectors(payload: dict[str, Any], split: str, decoder: int, tasks: list[str]) -> list[torch.Tensor]:
    rows = [row for row in payload["teachers"] if row["split"] == split and int(row["decoder"]) == decoder]
    by_task = {row["task"]: row for row in rows}
    if [task for task in tasks if task not in by_task]:
        raise RuntimeError(f"saved {split} teachers are incomplete for decoder {decoder}")
    vectors = []
    for task in tasks:
        row = by_task[task]
        vector = torch.tensor(row["vector"], dtype=torch.float32)
        if vector_hash(vector) != row["vector_sha256"]:
            raise RuntimeError(f"saved {split} vector hash mismatch for {task}")
        vectors.append(vector)
    return vectors


def run_latent_generalization(
    *,
    protocol_path: str | Path = PROTOCOL_PATH,
    out_path: str | Path = "artifacts/latent_generalization_dev.json",
    plot_path: str | Path = "artifacts/latent_generalization_dev.svg",
    sink: dict[str, Any] | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cfg = load_generalization_config()
    assert_protocol_frozen(protocol_path, cfg)
    assert_checkpoint_hashes(cfg)
    assert_seeds_disjoint(cfg)
    train_specs, val_specs, dev_specs = assert_physics(cfg)
    baseline_specs = pendulum_context_train()
    if [spec.task_id for spec in baseline_specs] != list(cfg["baseline_task_ids"]):
        raise RuntimeError("baseline tasks drifted")
    forbidden = set(cfg["forbidden_task_ids"])
    budget = int(cfg["support_budget"])
    saved = json.loads(Path(cfg["teacher_artifact"]).read_text())
    selection = json.loads(Path(cfg["prior_selection"]).read_text())["selection_record"]
    if float(selection["chosen_lr"]) != TEACHER_LR or int(selection["chosen_updates"]) != TEACHER_UPDATES:
        raise RuntimeError("the stored teacher rule does not match the locked procedure")
    horizons = [int(h) for h in cfg["horizons"]]
    angvel_index = int(cfg["angular_velocity_index"])
    epochs = [int(v) for v in cfg["epochs"]]

    def grab(spec: Any, n: int, env0: int, base: int) -> TransitionDataset:
        return _collect_checked(spec, n, env0, base, forbidden)

    baseline_supports = [grab(spec, budget, int(cfg["baseline_support_env0"]) + 10 * i, int(cfg["baseline_support_base"]) + i) for i, spec in enumerate(baseline_specs)]
    for i, spec in enumerate(baseline_specs):
        saved_hash = next(row["support_hash"] for row in saved["teachers"] if row["split"] == "meta" and int(row["decoder"]) == 0 and row["task"] == spec.task_id)
        assert_pair_binding(prefix_hash(baseline_supports[i], budget), saved_hash)
    broad_supports = []
    for support_index, (env0_key, base_key) in enumerate((("broad_h0_env0", "broad_h0_base"), ("broad_h1_env0", "broad_h1_base"))):
        broad_supports.append([
            grab(spec, budget, int(cfg[env0_key]) + 10 * i, int(cfg[base_key]) + i)
            for i, spec in enumerate(train_specs)
        ])
    history_supports = [grab(spec, budget, int(cfg["history_env0"]) + 10 * i, int(cfg["history_base"]) + i) for i, spec in enumerate(train_specs)]
    val_supports = [grab(spec, budget, int(cfg["val_support_env0"]) + 10 * i, int(cfg["val_support_base"]) + i) for i, spec in enumerate(val_specs)]
    val_queries = []
    for i, spec in enumerate(val_specs):
        raw = grab(spec, int(cfg["query_transitions"]), int(cfg["val_query_env0"]) + 10 * i, int(cfg["val_query_base"]) + i)
        done = complete_episodes(raw, 16)
        if len(np.unique(done.episode_id)) != int(cfg["query_episodes"]):
            raise RuntimeError(f"{spec.task_id} did not yield the locked validation episode count")
        val_queries.append(done)
    assert_support_query_separated(*zip(val_supports, val_queries))
    dev_supports = [grab(spec, budget, int(cfg["dev_support_env0"]) + 10 * i, int(cfg["dev_support_base"]) + i) for i, spec in enumerate(dev_specs)]
    dev_queries = []
    for i, spec in enumerate(dev_specs):
        raw = grab(spec, int(cfg["query_transitions"]), int(cfg["dev_query_env0"]) + 10 * i, int(cfg["dev_query_base"]) + i)
        done = complete_episodes(raw, 16)
        if len(np.unique(done.episode_id)) != int(cfg["query_episodes"]):
            raise RuntimeError(f"{spec.task_id} did not yield the locked development episode count")
        if prefix_hash(dev_supports[i], budget) != cfg["dev_support_hashes"][i]:
            raise RuntimeError(f"development support is not the locked query set for {spec.task_id}")
        if prefix_hash(done, len(done)) != cfg["dev_query_hashes"][i]:
            raise RuntimeError(f"development query is not the locked query set for {spec.task_id}")
        dev_queries.append(done)
    assert_support_query_separated(*zip(dev_supports, dev_queries))
    resources = {
        "baseline_support_env": int(sum(ds.env_interactions for ds in baseline_supports)),
        "broad_support_env": int(sum(ds.env_interactions for group in broad_supports for ds in group)),
        "history_support_env": int(sum(ds.env_interactions for ds in history_supports)),
        "val_support_env": int(sum(ds.env_interactions for ds in val_supports)),
        "val_query_env": int(sum(ds.env_interactions for ds in val_queries)),
        "dev_support_env": int(sum(ds.env_interactions for ds in dev_supports)),
        "dev_query_env": int(sum(ds.env_interactions for ds in dev_queries)),
        "teacher_optimizer_steps": 0,
        "student_optimizer_steps": 0,
    }
    deadline = t0 + float(cfg["time_limit_s"])
    runs: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    decoder_digests: list[str] = []
    raw_records: list[dict[str, Any]] = []
    teacher_seconds = []
    infer_seconds = []
    snapshots: dict[int, dict[int, dict[tuple[str, int], dict[str, torch.Tensor]]]] = {}
    held_history: dict[int, list[torch.Tensor]] = {}
    held_val: dict[int, list[torch.Tensor]] = {}
    held_global: dict[int, torch.Tensor] = {}
    for decoder in range(int(cfg["n_decoder_seeds"])):
        if time.perf_counter() > deadline:
            raise RuntimeError("generalization exceeded the time cap")
        parent = cfg["parent_checkpoints"][decoder]
        model = load_context_checkpoint(Path(parent["path"]))
        lock_network(model)
        digest = decoder_digest(model)
        decoder_digests.append(digest)
        init_state = {key: value.detach().cpu().clone() for key, value in model.encoder.state_dict().items()}
        global_z = torch.tensor(selection["global_vectors"][str(decoder)], dtype=torch.float32)
        if vector_hash(global_z) != parent["global_vector_sha256"]:
            raise RuntimeError(f"global vector hash mismatch for decoder {decoder}")
        baseline_teachers = _saved_vectors(saved, "meta", decoder, list(cfg["baseline_task_ids"]))
        dev_teachers = _saved_vectors(saved, "dev", decoder, list(cfg["dev_task_ids"]))
        for i, spec in enumerate(dev_specs):
            row = next(item for item in saved["teachers"] if item["split"] == "dev" and int(item["decoder"]) == decoder and item["task"] == spec.task_id)
            assert_pair_binding(prefix_hash(dev_supports[i], budget), row["support_hash"])
        t_fit = time.perf_counter()
        broad_teachers = []
        for support_index, group in enumerate(broad_supports):
            fitted = []
            for task_index, support in enumerate(group):
                vector = _fit_teacher(model, support, global_z)
                if decoder_digest(model) != digest:
                    raise RuntimeError("broad teacher fit changed the decoder")
                support_hash = prefix_hash(support, budget)
                fitted.append(vector)
                pair_rows.append({
                    "decoder": decoder, "task": train_specs[task_index].task_id, "support_index": support_index,
                    "support_hash": support_hash, "vector_sha256": vector_hash(vector), "role": "train",
                    "vector": [float(v) for v in vector.tolist()],
                })
                resources["teacher_optimizer_steps"] += TEACHER_UPDATES
            broad_teachers.append(fitted)
        for task_index in range(len(train_specs)):
            left = broad_teachers[0][task_index]
            right = broad_teachers[1][task_index]
            l2 = float(torch.linalg.vector_norm(left - right).item())
            loss_left_on_right = _support_loss(model, broad_supports[1][task_index], left)
            loss_right_on_right = _support_loss(model, broad_supports[1][task_index], right)
            loss_right_on_left = _support_loss(model, broad_supports[0][task_index], right)
            loss_left_on_left = _support_loss(model, broad_supports[0][task_index], left)
            pair_rows.append({
                "decoder": decoder, "task": train_specs[task_index].task_id, "role": "teacher_pair",
                "l2": l2,
                "gap_left": abs(loss_right_on_left - loss_left_on_left) / max(abs(loss_left_on_left), 1e-8),
                "gap_right": abs(loss_left_on_right - loss_right_on_right) / max(abs(loss_right_on_right), 1e-8),
            })
        history_teachers = []
        for task_index, support in enumerate(history_supports):
            vector = _fit_teacher(model, support, global_z)
            history_teachers.append(vector)
            resources["teacher_optimizer_steps"] += TEACHER_UPDATES
            pair_rows.append({
                "decoder": decoder, "task": train_specs[task_index].task_id, "role": "history",
                "support_hash": prefix_hash(support, budget), "vector_sha256": vector_hash(vector),
                "vector": [float(v) for v in vector.tolist()],
            })
        held_history[decoder] = history_teachers
        val_teachers = []
        for support in val_supports:
            vector = _fit_teacher(model, support, global_z)
            val_teachers.append(vector)
            resources["teacher_optimizer_steps"] += TEACHER_UPDATES
        held_val[decoder] = val_teachers
        held_global[decoder] = global_z.detach().clone()
        if decoder_digest(model) != digest:
            raise RuntimeError("teacher fits changed the decoder")
        teacher_seconds.append(time.perf_counter() - t_fit)
        flat_supports = [ds for group in broad_supports for ds in group]
        flat_teachers = [vector for group in broad_teachers for vector in group]
        for support_index, group in enumerate(broad_supports):
            for task_index, support in enumerate(group):
                stored = next(row["support_hash"] for row in pair_rows if row["role"] == "train" and int(row["decoder"]) == decoder and row["task"] == train_specs[task_index].task_id and int(row["support_index"]) == support_index)
                assert_pair_binding(prefix_hash(support, budget), stored)
        snapshots[decoder] = {}
        fixed: dict[str, dict[str, Any]] = {}
        for task_index, spec in enumerate(dev_specs):
            query = dev_queries[task_index]
            labels = {
                "zero": {"zero": _cell(model, torch.zeros(model.context_dim()), query, dev_teachers[task_index], horizons, angvel_index)},
                "global": {"global": _cell(model, global_z, query, dev_teachers[task_index], horizons, angvel_index)},
                "teacher": {"teacher": _cell(model, dev_teachers[task_index], query, dev_teachers[task_index], horizons, angvel_index)},
            }
            t_inf = time.perf_counter()
            z_enc = _infer(model, init_state, dev_supports[task_index], budget)
            infer_seconds.append(time.perf_counter() - t_inf)
            labels["encoder"] = {"encoder": _cell(model, z_enc, query, dev_teachers[task_index], horizons, angvel_index)}
            fixed[spec.task_id] = labels
        for student in range(int(cfg["n_student_seeds"])):
            seed = 30_000 + decoder * 100 + student
            broad_snaps, broad_l2, _grad = train_pairs(
                model, flat_supports, flat_teachers, epochs=max(epochs), checkpoints=epochs, lr=STUDENT_LR,
                seed=seed, init_state=init_state, decoder_before=digest, budget=budget,
            )
            resources["student_optimizer_steps"] += max(epochs) * len(flat_supports)
            base_snaps, base_l2, _grad = train_pairs(
                model, baseline_supports, baseline_teachers, epochs=max(epochs), checkpoints=epochs, lr=STUDENT_LR,
                seed=seed, init_state=init_state, decoder_before=digest, budget=budget,
            )
            resources["student_optimizer_steps"] += max(epochs) * len(baseline_supports)
            snapshots[decoder][student] = {}
            for epoch in epochs:
                snapshots[decoder][student][("broad", epoch)] = broad_snaps[epoch]
                snapshots[decoder][student][("baseline", epoch)] = base_snaps[epoch]
            seed_id = combined_seed(decoder, student, int(cfg["n_student_seeds"]))
            task_rows = {}
            for task_index, spec in enumerate(dev_specs):
                labels = {name: payload for name, payload in fixed[spec.task_id].items()}
                for epoch in epochs:
                    for kind, state, label in (
                        ("broad", broad_snaps[epoch], broad_label(epoch)),
                        ("baseline", base_snaps[epoch], baseline_label(epoch)),
                    ):
                        t_inf = time.perf_counter()
                        z_s = _infer(model, state, dev_supports[task_index], budget)
                        infer_seconds.append(time.perf_counter() - t_inf)
                        labels[label] = {label: _cell(model, z_s, dev_queries[task_index], dev_teachers[task_index], horizons, angvel_index)}
                task_rows[spec.task_id] = {"labels": labels}
            block = {
                "model_seed": seed_id, "tasks": task_rows, "decoder_seed": decoder, "student_seed": student,
                "broad_train_l2": broad_l2, "baseline_train_l2": base_l2,
            }
            runs.append(block)
            raw_records.extend(records_from_cells([block]))
            print(f"generalization decoder={decoder} student={student}", flush=True)
    schema = dev_schema(cfg)
    completeness = _apply(raw_records, schema)
    dev_means = {}
    if completeness["declared_complete"]:
        for epoch in epochs:
            dev_means[epoch] = _mean_angvel(raw_records, broad_label(epoch))
    chosen = choose_epoch(dev_means) if dev_means else None
    chosen_label = None if chosen is None else broad_label(chosen)
    zero_mean = _mean_angvel(raw_records, "zero")
    encoder_mean = _mean_angvel(raw_records, "encoder")
    student_mean = float("nan") if chosen_label is None else dev_means[chosen]
    gate = bool(chosen is not None and completeness["declared_complete"] and development_gate(student_mean, zero_mean, encoder_mean))
    head = _git_meta()
    sha = str(head.get("revision") or "")
    source_status = inspect_source_tree(sha) if sha else {"source_dirty": True}
    clean = not bool(source_status.get("source_dirty", True))
    student_means = [] if chosen_label is None else _student_seed_means(raw_records, chosen_label, cfg)
    contrasts = {}
    summaries = {}
    if chosen_label is not None and completeness["declared_complete"]:
        for name in ("zero", "encoder", "global", "teacher", baseline_label(chosen)):
            contrasts[name] = _paired(raw_records, chosen_label, name, cfg)
        for name in (chosen_label, baseline_label(chosen), *FIXED_LABELS):
            summaries[name] = _metric_summary(raw_records, name)
    history_l2 = float("nan")
    train_l2 = float("nan")
    teacher_pair_median = float("nan")
    val_records: list[dict[str, Any]] = []
    val_gate = False
    if chosen is not None and completeness["declared_complete"]:
        train_values = [float(block["broad_train_l2"][chosen]["mean"]) for block in runs]
        train_l2 = float(np.mean(train_values))
        pair_l2 = [float(row["l2"]) for row in pair_rows if row["role"] == "teacher_pair"]
        teacher_pair_median = float(np.median(pair_l2)) if pair_l2 else float("nan")
        history_values = []
        for decoder in range(int(cfg["n_decoder_seeds"])):
            model = load_context_checkpoint(Path(cfg["parent_checkpoints"][decoder]["path"]))
            for student in range(int(cfg["n_student_seeds"])):
                state = snapshots[decoder][student][("broad", chosen)]
                history_values.extend(_pair_distances(model, history_supports, held_history[decoder], state, budget))
        history_l2 = float(np.mean(history_values))
        val_records = _score_heldout(
            cfg, snapshots, val_specs, val_supports, val_queries, held_val, held_global, chosen, horizons, angvel_index, budget,
        )
    payload = {
        "protocol_id": cfg["protocol_id"],
        "hypothesis": cfg["h_generalize"],
        "implementation_sha": sha if clean else None,
        "source_dirty": not clean,
        "git": head,
        "decision_recorded": bool(clean and completeness["declared_complete"] and chosen is not None),
        "gate_pass": bool(gate and clean),
        "chosen_epoch": chosen,
        "dev_checkpoint_angvel": {str(epoch): value for epoch, value in dev_means.items()},
        "means": {
            "student": student_mean,
            "zero": zero_mean,
            "encoder": encoder_mean,
            "global": _mean_angvel(raw_records, "global"),
            "teacher": _mean_angvel(raw_records, "teacher"),
            "baseline": float("nan") if chosen is None else _mean_angvel(raw_records, baseline_label(chosen)),
        },
        "student_seed_angvel": student_means,
        "student_seed_interval": seed_level_ci(student_means) if len(student_means) >= 2 else None,
        "paired_control_minus_student": contrasts,
        "metric_summary": summaries,
        "train_latent_l2": train_l2,
        "history_latent_l2": history_l2,
        "teacher_pair_median_l2": teacher_pair_median,
        "per_decoder": _per_decoder(raw_records, chosen_label, cfg) if chosen_label is not None else [],
        "schema": schema,
        "raw_records": raw_records,
        "completeness": completeness,
        "declared_complete": bool(completeness["declared_complete"]),
        "pair_rows": [{key: value for key, value in row.items() if key != "vector"} for row in pair_rows],
        "encoder_parameter_count": 584,
        "resources": resources,
        "teacher_fit_seconds_per_decoder": teacher_seconds,
        "student_infer_seconds_mean": float(np.mean(infer_seconds)) if infer_seconds else None,
        "confirmation_evaluated": False,
        "control_evaluated": False,
        "is_agi": False,
        "is_learning_to_learn": False,
        "replication_unit": "student seed after averaging the three frozen decoders and the development tasks",
        "n_student_seeds_note": "Five student seeds share three frozen decoders. They are not three independent world models.",
        "wall_clock_s": time.perf_counter() - t0,
    }
    if val_records:
        val_student = _mean_angvel(val_records, broad_label(chosen))
        val_zero = _mean_angvel(val_records, "zero")
        val_encoder = _mean_angvel(val_records, "encoder")
        val_gate = development_gate(val_student, val_zero, val_encoder)
        payload["validation"] = {
            "means": {
                "student": val_student,
                "zero": val_zero,
                "encoder": val_encoder,
                "global": _mean_angvel(val_records, "global"),
                "teacher": _mean_angvel(val_records, "teacher"),
                "baseline": _mean_angvel(val_records, baseline_label(chosen)),
            },
            "metric_summary": {name: _metric_summary(val_records, name) for name in (broad_label(chosen), baseline_label(chosen), *FIXED_LABELS)},
            "raw_records": val_records,
            "gate_pass": val_gate,
            "used_for_checkpoint_selection": False,
        }
    payload["val_gate_pass"] = bool(val_gate)
    payload["recommendation"] = recommend(bool(gate and clean), bool(val_gate and clean), train_l2, history_l2, teacher_pair_median, cfg) if payload["decision_recorded"] else None
    payload["wall_clock_s"] = time.perf_counter() - t0
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    if chosen is not None and dev_means:
        series = {"broad": [dev_means[epoch] for epoch in epochs], "baseline": [_mean_angvel(raw_records, baseline_label(epoch)) for epoch in epochs]}
        for name in ("zero", "encoder", "global", "teacher"):
            series[name] = [_mean_angvel(raw_records, name) for _epoch in epochs]
        Path(plot_path).parent.mkdir(parents=True, exist_ok=True)
        _svg(Path(plot_path), epochs, series)
        payload["plot"] = str(plot_path)
    Path(out_path).write_text(dumps_strict(payload))
    if sink is not None:
        sink["snapshots"] = snapshots
        sink["decoder_digests"] = list(decoder_digests)
    return payload


def _per_decoder(records: list[dict[str, Any]], label: str, cfg: dict[str, Any]) -> list[dict[str, float]]:
    n_student = int(cfg["n_student_seeds"])
    rows = []
    for decoder in range(int(cfg["n_decoder_seeds"])):
        ids = [combined_seed(decoder, student, n_student) for student in range(n_student)]
        one = ids[:1]
        rows.append({
            "decoder": decoder,
            "student": _mean_angvel(records, label, ids),
            "baseline": _mean_angvel(records, baseline_label(int(label.removeprefix("broad_e"))), ids),
            "zero": _mean_angvel(records, "zero", one),
            "encoder": _mean_angvel(records, "encoder", one),
            "global": _mean_angvel(records, "global", one),
            "teacher": _mean_angvel(records, "teacher", one),
        })
    return rows


def _score_heldout(
    cfg: dict[str, Any],
    snapshots: dict[int, dict[int, dict[tuple[str, int], dict[str, torch.Tensor]]]],
    specs: tuple[Any, ...],
    supports: list[TransitionDataset],
    queries: list[TransitionDataset],
    teachers_by_decoder: dict[int, list[torch.Tensor]],
    globals_by_decoder: dict[int, torch.Tensor],
    epoch: int,
    horizons: list[int],
    angvel_index: int,
    budget: int,
) -> list[dict[str, Any]]:
    """Score the checkpoint already chosen on development. This does not choose a new one."""
    per_seed = []
    for decoder in range(int(cfg["n_decoder_seeds"])):
        model = load_context_checkpoint(Path(cfg["parent_checkpoints"][decoder]["path"]))
        lock_network(model)
        init_state = {key: value.detach().cpu().clone() for key, value in model.encoder.state_dict().items()}
        teachers = teachers_by_decoder[decoder]
        global_z = globals_by_decoder[decoder]
        fixed = {}
        for task_index, spec in enumerate(specs):
            query = queries[task_index]
            fixed[spec.task_id] = {
                "zero": {"zero": _cell(model, torch.zeros(model.context_dim()), query, teachers[task_index], horizons, angvel_index)},
                "global": {"global": _cell(model, global_z, query, teachers[task_index], horizons, angvel_index)},
                "teacher": {"teacher": _cell(model, teachers[task_index], query, teachers[task_index], horizons, angvel_index)},
                "encoder": {"encoder": _cell(model, _infer(model, init_state, supports[task_index], budget), query, teachers[task_index], horizons, angvel_index)},
            }
        for student in range(int(cfg["n_student_seeds"])):
            task_rows = {}
            for task_index, spec in enumerate(specs):
                labels = {name: payload for name, payload in fixed[spec.task_id].items()}
                for kind, label in (("broad", broad_label(epoch)), ("baseline", baseline_label(epoch))):
                    z_s = _infer(model, snapshots[decoder][student][(kind, epoch)], supports[task_index], budget)
                    labels[label] = {label: _cell(model, z_s, queries[task_index], teachers[task_index], horizons, angvel_index)}
                task_rows[spec.task_id] = {"labels": labels}
            per_seed.append({"model_seed": combined_seed(decoder, student, int(cfg["n_student_seeds"])), "tasks": task_rows})
    return records_from_cells(per_seed)
