"""Amortized latent inference. The teacher rule stays locked. The decoder stays frozen.

The student is the existing history encoder. Development tasks select the objective.
The previously evaluated confirmation physics are not used to fit or select it.
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
    pendulum_physics_key,
)
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_diagnosis import ROLLOUT_STARTS, complete_episodes
from nexus.world.context_model import CONTEXT_DIM, ENCODER_HIDDEN
from nexus.world.context_optimization import _sha256
from nexus.world.context_pilot import _collect, _split_hash, _svg, prefix_hash
from nexus.world.data import TransitionDataset, assert_disjoint_seeds
from nexus.world.direct_latent import (
    assert_support_query_separated,
    encoder_context,
    fit_from_support,
    latent_seed_groups,
    load_latent_config,
    lock_network,
    score_with_z,
    score_with_z_mlp,
    support_for,
    vector_hash,
)
from nexus.world.direct_latent_confirmation import confirmation_seed_groups, load_confirmation_config
from nexus.world.frozen_dynamics import load_context_checkpoint, load_mlp_checkpoint, planned_env_seeds, records_from_cells
from nexus.world.result_checks import schema_completeness
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/amortized_latent_inference.yaml")
PROTOCOL_PATH = Path("docs/NEXUS_AMORTIZED_LATENT_INFERENCE.md")
TEACHER_LR = 0.1
TEACHER_UPDATES = 256
FIXED_LABELS = ("zero", "global", "teacher", "wrong", "mlp_reference")


def load_amortized_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("amortized config must be a mapping")
    expected = _locked_config()
    if cfg != expected:
        missing = sorted(set(expected) - set(cfg))
        extra = sorted(set(cfg) - set(expected))
        drifted = sorted(key for key in expected if key in cfg and cfg[key] != expected[key])
        raise ValueError(f"amortized config drifted; missing={missing} extra={extra} drifted={drifted}")
    if list(cfg["rollout_starts"]) != list(ROLLOUT_STARTS):
        raise ValueError("rollout starts drifted")
    if float(cfg["teacher_learning_rate"]) != TEACHER_LR or int(cfg["teacher_updates"]) != TEACHER_UPDATES:
        raise ValueError("teacher hyperparameters drifted")
    if 0 not in [int(v) for v in cfg["lambdas"]]:
        raise ValueError("the distillation-only baseline is missing")
    if int(cfg["encoder_hidden"]) != ENCODER_HIDDEN or int(cfg["context_dim"]) != CONTEXT_DIM:
        raise ValueError("student capacity drifted")
    return cfg


def _locked_config() -> dict[str, Any]:
    return {
        "protocol_id": "amortized_latent_inference_v1",
        "starting_sha": "13acf89787f8262c43107193ea2b331a4bec3e26",
        "prior_selection": "artifacts/direct_latent_selection.json",
        "prior_audit": "artifacts/direct_latent_audit.json",
        "prior_confirmation": "artifacts/direct_latent_confirmation.json",
        "prior_frozen_selection": "artifacts/frozen_dynamics_selection.json",
        "prior_frozen_audit": "artifacts/frozen_dynamics_audit.json",
        "forbidden_confirm_hash": "87b83c41be34aa1a",
        "amort_confirm_hash": "d1fa621351d286cf",
        "is_agi": False,
        "is_learning_to_learn": False,
        "control_sweep": False,
        "h_amortized": (
            "A student with the existing history-encoder capacity, trained to match support-fit teacher latents, "
            "lowers held-out query angular-velocity MAE below zero context and below the original frozen encoder."
        ),
        "n_decoder_seeds": 3,
        "n_student_seeds": 10,
        "teacher_learning_rate": 0.1,
        "teacher_updates": 256,
        "student_learning_rate": 0.001,
        "lambdas": [0, 10, 100, 1000],
        "epochs": [40, 120, 400],
        "budgets": [16, 32, 64, 128],
        "support_budget": 128,
        "query_episodes": 4,
        "query_transitions": 800,
        "encoder_hidden": 32,
        "context_dim": 8,
        "angular_velocity_index": 2,
        "horizons": [3, 8, 16],
        "rollout_starts": [0, 32, 64, 96, 128, 160],
        "donor": "evaluation_task_(i+1)_mod_n",
        "recovery_min_relative": 0.05,
        "meta_support_env0": 72000,
        "meta_support_base": 255000,
        "dev_support_env0": 74000,
        "dev_support_base": 256000,
        "dev_query_env0": 76000,
        "dev_query_base": 257000,
        "confirm_support_env0": 82000,
        "confirm_support_base": 258000,
        "confirm_query_env0": 84000,
        "confirm_query_base": 259000,
        "time_limit_s": 3600,
        "meta_task_ids": [f"pendulum_ctx_tr{i}" for i in range(8)],
        "dev_task_ids": [f"pendulum_ctx_dev{i}" for i in range(3)],
        "confirm_task_ids": [f"pendulum_amort_c{i}" for i in range(4)],
        "confirm_physics": [[16.4, 1.0, 1.0], [10.0, 2.6, 1.0], [10.0, 1.0, 0.5], [7.0, 1.45, 1.4]],
        "forbidden_task_ids": [f"pendulum_ctx_c{i}" for i in range(4)],
        "parent_checkpoints": [
            {"seed": 0, "path": "artifacts/frozen_dynamics_checkpoints/seed0_history_u1000.pt", "sha256": "83e90a9b187cdffe5e39d794ce86abf65ef891fde011daf8e55b7eee1f348959", "frozen_network_sha256": "71d44b7880f145c99bc99f6b8e24921134e5b90f58dbf8c78f56d942daf80636", "global_vector_sha256": "d40d71a3e5c0e62ef158e08ec82617f10a8f6fcfeaac436744c9e9958b31f8ba"},
            {"seed": 1, "path": "artifacts/frozen_dynamics_checkpoints/seed1_history_u1000.pt", "sha256": "cd5400070a69238ce8e35ca036c57448b18664f7ce1e8600ac5a3aab2983ef3e", "frozen_network_sha256": "4bcdc147a80171bf6123b1bc9079f1174614e750a2337a75f9d3ef79942a3104", "global_vector_sha256": "4705c19a62e0547267705e1b10aeb4f06c1a62058ab077534b24a8f2cc4fdb33"},
            {"seed": 2, "path": "artifacts/frozen_dynamics_checkpoints/seed2_history_u1000.pt", "sha256": "254b097c5dbd3df02c463913c60392928aaed0584c6c29245e060ed25113b6fd", "frozen_network_sha256": "13090d27d02476584c39284cc045f19d9b727c33721e22186be25a055bc064ac", "global_vector_sha256": "9910f28a645a7a4d8a714cf0523f6c8a9c7b58b7dd71103e96a511583be31218"},
        ],
        "mlp_checkpoints": [
            {"seed": 0, "path": "artifacts/context_optimization_checkpoints/seed0_mlp_u1000.pt", "sha256": "4f4db2ca0ade8d2e19cb37971cf7343959edcdc17befe73e1aa9169e19c21cc2"},
            {"seed": 1, "path": "artifacts/context_optimization_checkpoints/seed1_mlp_u1000.pt", "sha256": "eb72c8c9f41d6e53a123e9f9b9aa86ce0540117e33a97c5617c164ff4456526f"},
            {"seed": 2, "path": "artifacts/context_optimization_checkpoints/seed2_mlp_u1000.pt", "sha256": "58dc9209c1435543b33cb48878785a30705bc9909090510631e40f7e95b466a1"},
        ],
        "prior_artifact_sha256": {
            "artifacts/direct_latent_selection.json": "ef99a31fd1c50ee27e4de35dff6c810397a22ab267622d1b4aa938cf4ffb5c5f",
            "artifacts/direct_latent_audit.json": "9681f5de77d53c8fafba54aa5c0e41eeb60cd39a8e0f4d8308615dcf7476f9dc",
            "artifacts/direct_latent_confirmation.json": "1de5b1ebfa33caafe602f55d709490d71a25d07122a3198019a0aca5e73bb67f",
            "artifacts/frozen_dynamics_selection.json": "b8506c2d9670692cfafdfc42fc6cffe2c36565b4219cfc22e39128cf84294f11",
            "artifacts/frozen_dynamics_audit.json": "72a65dee5ecb694b0c2137f05f8d885c200933df11f0f85a5b4cc0986af22ba3",
        },
    }


def student_label(lam: int, epoch: int, budget: int) -> str:
    return f"student_l{int(lam)}_e{int(epoch)}_b{int(budget)}"


def encoder_label(budget: int) -> str:
    return f"encoder_b{int(budget)}"


def parse_student_label(label: str) -> tuple[int, int, int]:
    body = label.removeprefix("student_")
    lam_s, epoch_s, budget_s = body.split("_")
    return int(lam_s[1:]), int(epoch_s[1:]), int(budget_s[1:])


def combined_seed(decoder: int, student: int, n_student: int) -> int:
    return int(decoder) * int(n_student) + int(student)


def dev_schema_from_config(cfg: dict[str, Any]) -> dict[str, Any]:
    labels = [student_label(lam, epoch, budget) for lam in cfg["lambdas"] for epoch in cfg["epochs"] for budget in cfg["budgets"]]
    labels += [encoder_label(budget) for budget in cfg["budgets"]]
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


def assert_protocol_frozen(protocol_path: str | Path, cfg: dict[str, Any]) -> None:
    path = Path(protocol_path)
    if not path.is_file():
        raise RuntimeError("amortized inference is blocked until the protocol document is saved")
    text = path.read_text()
    start = text.find("<!-- protocol-lock")
    end = text.find("-->", start)
    if start < 0 or end < 0:
        raise RuntimeError("amortized inference is blocked because the protocol lock block is missing")
    locked: dict[str, str] = {}
    for line in text[start:end].splitlines():
        if ":" not in line or line.strip().startswith("<!--"):
            continue
        key, value = line.split(":", 1)
        locked[key.strip()] = value.strip()
    required = {
        "forbidden_confirm_hash": str(cfg["forbidden_confirm_hash"]),
        "amort_confirm_hash": str(cfg["amort_confirm_hash"]),
        "teacher_lr": f"{float(cfg['teacher_learning_rate']):.1f}",
        "teacher_updates": str(int(cfg["teacher_updates"])),
        "student_lr": f"{float(cfg['student_learning_rate']):.3f}",
        "lambdas": ",".join(str(int(v)) for v in cfg["lambdas"]),
        "epochs": ",".join(str(int(v)) for v in cfg["epochs"]),
        "budgets": ",".join(str(int(v)) for v in cfg["budgets"]),
        "n_student_seeds": str(int(cfg["n_student_seeds"])),
        "meta_support_env0": str(int(cfg["meta_support_env0"])),
        "dev_support_env0": str(int(cfg["dev_support_env0"])),
        "dev_query_env0": str(int(cfg["dev_query_env0"])),
        "confirm_support_env0": str(int(cfg["confirm_support_env0"])),
        "confirm_query_env0": str(int(cfg["confirm_query_env0"])),
    }
    for key, value in required.items():
        if locked.get(key) != value:
            raise RuntimeError(f"amortized inference is blocked because protocol {key}={locked.get(key)!r} is not {value!r}")


def assert_splits(cfg: dict[str, Any]) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
    meta = pendulum_context_train()
    dev = pendulum_context_development()
    confirm = pendulum_amortized_confirmation()
    old = pendulum_context_confirmation()
    if _split_hash(old) != cfg["forbidden_confirm_hash"]:
        raise RuntimeError("the previously evaluated confirmation split changed")
    if _split_hash(confirm) != cfg["amort_confirm_hash"]:
        raise RuntimeError("the new confirmation split hash does not match the protocol")
    if [s.task_id for s in meta] != list(cfg["meta_task_ids"]):
        raise RuntimeError("meta-training tasks drifted")
    if [s.task_id for s in dev] != list(cfg["dev_task_ids"]):
        raise RuntimeError("development tasks drifted")
    if [s.task_id for s in confirm] != list(cfg["confirm_task_ids"]):
        raise RuntimeError("amortized confirmation tasks drifted")
    if [list(pendulum_physics_key(s)) for s in confirm] != cfg["confirm_physics"]:
        raise RuntimeError("amortized confirmation physics drifted")
    forbidden = set(cfg["forbidden_task_ids"])
    used = {s.task_id for s in (*meta, *dev, *confirm)}
    if used & forbidden:
        raise RuntimeError("a previously evaluated confirmation task entered the student split")
    keys = [pendulum_physics_key(s) for s in (*meta, *dev, *old, *confirm)]
    if len(keys) != len(set(keys)):
        raise RuntimeError("student physics splits are not disjoint")
    return meta, dev, confirm


def assert_prior_artifacts_unchanged(cfg: dict[str, Any]) -> None:
    for path, expected in cfg["prior_artifact_sha256"].items():
        file = Path(path)
        if not file.is_file():
            raise RuntimeError(f"prior artifact is missing: {path}")
        if hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"prior artifact changed: {path}")


def assert_checkpoint_hashes(cfg: dict[str, Any]) -> None:
    for row in list(cfg["parent_checkpoints"]) + list(cfg["mlp_checkpoints"]):
        path = Path(row["path"])
        if _sha256(path) != row["sha256"]:
            raise RuntimeError(f"checkpoint hash mismatch for {path}")


def amortized_seed_groups(cfg: dict[str, Any]) -> dict[str, set[int]]:
    groups = confirmation_seed_groups(load_confirmation_config())
    groups.update(latent_seed_groups(load_latent_config()))
    # confirmation_seed_groups already includes the latent groups; repeating keys is harmless.
    spec = {
        "amort_meta_support": (int(cfg["support_budget"]), int(cfg["meta_support_env0"]), len(cfg["meta_task_ids"])),
        "amort_dev_support": (int(cfg["support_budget"]), int(cfg["dev_support_env0"]), len(cfg["dev_task_ids"])),
        "amort_dev_query": (int(cfg["query_transitions"]), int(cfg["dev_query_env0"]), len(cfg["dev_task_ids"])),
        "amort_confirm_support": (int(cfg["support_budget"]), int(cfg["confirm_support_env0"]), len(cfg["confirm_task_ids"])),
        "amort_confirm_query": (int(cfg["query_transitions"]), int(cfg["confirm_query_env0"]), len(cfg["confirm_task_ids"])),
    }
    for name, (n, env0, n_tasks) in spec.items():
        seeds: set[int] = set()
        for i in range(n_tasks):
            seeds |= planned_env_seeds(n, env0 + 10 * i)
        groups[name] = seeds
    return groups


def assert_amortized_seeds_disjoint(cfg: dict[str, Any]) -> None:
    named = amortized_seed_groups(cfg)
    keys = list(named)
    for i, left in enumerate(keys):
        for right in keys[i + 1 :]:
            overlap = named[left] & named[right]
            if overlap:
                raise ValueError(f"collect seeds overlap between {left} and {right}: {sorted(overlap)[:8]}")


def decoder_digest(model: Any) -> str:
    digest = hashlib.sha256()
    named = [(f"net.{name}", param.detach()) for name, param in model.net.named_parameters()]
    rms = model.obs_rms.state_dict()
    named.append(("rms.mean", torch.as_tensor(np.asarray(rms["mean"]))))
    named.append(("rms.var", torch.as_tensor(np.asarray(rms["var"]))))
    named.append(("rms.count", torch.as_tensor(float(rms["count"]))))
    for name, value in named:
        arr = np.ascontiguousarray(value.detach().cpu().numpy())
        digest.update(name.encode())
        digest.update(arr.tobytes())
    return digest.hexdigest()


def encoder_parameter_count(model: Any) -> int:
    return int(sum(param.numel() for param in model.encoder.parameters()))


def _window(ds: TransitionDataset, start: int, budget: int) -> TransitionDataset:
    stop = int(start) + int(budget)
    if stop > len(ds):
        raise RuntimeError("support window leaves the collected support")
    return ds.slice(np.arange(int(start), stop))


def _prefix(ds: TransitionDataset, budget: int) -> TransitionDataset:
    return _window(ds, 0, budget)


def student_objective(model: Any, support: TransitionDataset, teacher_z: torch.Tensor, lam: float) -> tuple[torch.Tensor, torch.Tensor]:
    """Distillation plus an optional support prediction term. Query rows are not an argument."""
    z = model.encode(support.obs, support.action, support.next_obs, differentiable=True)
    distill = nn.functional.mse_loss(z, teacher_z.detach())
    if float(lam) == 0.0:
        return distill, z
    _state, _term, pred = model.query_terms(support.obs, support.action, support.next_obs, support.terminated, z)
    return distill + float(lam) * pred, z


def train_student(
    model: Any,
    supports: list[TransitionDataset],
    teachers: list[torch.Tensor],
    *,
    lam: float,
    epochs: int,
    checkpoints: list[int],
    budgets: list[int],
    student_lr: float,
    seed: int,
    init_state: dict[str, torch.Tensor],
    decoder_before: str,
) -> dict[int, dict[str, torch.Tensor]]:
    """Train the existing encoder. Decoder parameters stay frozen. Checkpoints share one optimizer."""
    model.encoder.load_state_dict(init_state)
    for param in model.encoder.parameters():
        param.requires_grad_(True)
    for param in model.net.parameters():
        param.requires_grad_(False)
    opt = torch.optim.Adam(model.encoder.parameters(), lr=float(student_lr))
    rng = torch.Generator()
    rng.manual_seed(int(seed))
    snapshots: dict[int, dict[str, torch.Tensor]] = {}
    wanted = {int(step) for step in checkpoints}
    n_tasks = len(supports)
    for epoch in range(1, int(epochs) + 1):
        order = torch.randperm(n_tasks, generator=rng).tolist()
        opt.zero_grad(set_to_none=True)
        total = None
        for task_index in order:
            budget = int(budgets[int(torch.randint(0, len(budgets), (1,), generator=rng).item())])
            start_max = len(supports[task_index]) - budget
            start = 0 if start_max <= 0 else int(torch.randint(0, start_max + 1, (1,), generator=rng).item())
            window = _window(supports[task_index], start, budget)
            loss, _z = student_objective(model, window, teachers[task_index], lam)
            total = loss if total is None else total + loss
        if total is None or not torch.isfinite(total.detach()):
            raise RuntimeError("student training produced a nonfinite loss; refusing to change the objective")
        total.backward()
        for name, param in model.net.named_parameters():
            if param.grad is not None:
                raise RuntimeError(f"decoder parameter {name} received a student gradient")
        opt.step()
        if decoder_digest(model) != decoder_before:
            raise RuntimeError("student training changed the decoder or normalization")
        if epoch in wanted:
            snapshots[epoch] = {key: value.detach().cpu().clone() for key, value in model.encoder.state_dict().items()}
    return snapshots


def choose_student(scores: dict[str, float]) -> tuple[int, int, int]:
    """Lowest development angular-velocity MAE. Ties prefer fewer transitions, then lower λ, then fewer epochs."""
    if not scores:
        raise ValueError("no student scores")
    ranked = []
    for label, value in scores.items():
        lam, epoch, budget = parse_student_label(label)
        ranked.append((float(value), int(budget), int(lam), int(epoch)))
    ranked.sort()
    _value, budget, lam, epoch = ranked[0]
    return int(lam), int(epoch), int(budget)


def development_gate(student: float, zero: float, encoder: float) -> bool:
    return bool(np.isfinite(student) and np.isfinite(zero) and np.isfinite(encoder) and student < zero and student < encoder)


def recovery_fraction(global_error: float, student_error: float, teacher_error: float, *, min_relative: float = 0.05) -> float | None:
    denom = float(global_error) - float(teacher_error)
    if not np.isfinite(denom) or denom < float(min_relative) * float(global_error):
        return None
    return (float(global_error) - float(student_error)) / denom


def assert_dev_allows_confirmation(payload: dict[str, Any], cfg: dict[str, Any]) -> None:
    if payload.get("selection_recorded") is not True or payload.get("gate_pass") is not True:
        raise RuntimeError("confirmation is blocked because the development gate did not pass")
    if payload.get("source_dirty") is not False:
        raise RuntimeError("confirmation is blocked because the development run was dirty")
    for key in ("chosen_lambda", "chosen_epoch", "chosen_budget"):
        if key not in payload:
            raise RuntimeError(f"confirmation is blocked because {key} was not locked")
    schema = dev_schema_from_config(cfg)
    report = schema_completeness(
        list(payload.get("raw_records") or []),
        seed_ids=list(schema["seed_ids"]),
        task_ids=list(schema["task_ids"]),
        labels=list(schema["labels"]),
        conditions_by_label={k: list(v) for k, v in schema["conditions_by_label"].items()},
        metrics=tuple(schema["metrics"]),
        horizons=tuple(schema["horizons"]),
        per_dim=3,
    )
    if not report["declared_complete"]:
        raise RuntimeError("confirmation is blocked because the development grid is incomplete")


def _apply(records: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
    return schema_completeness(
        records,
        seed_ids=list(schema["seed_ids"]),
        task_ids=list(schema["task_ids"]),
        labels=list(schema["labels"]),
        conditions_by_label={k: list(v) for k, v in schema["conditions_by_label"].items()},
        metrics=tuple(schema["metrics"]),
        horizons=tuple(schema["horizons"]),
        per_dim=int(schema["per_dim"]),
    )


def _mean_angvel(records: list[dict[str, Any]], label: str, seed_ids: list[int] | None = None) -> float:
    values = [float(row["angvel_mae"]) for row in records if row["label"] == label and (seed_ids is None or int(row["seed"]) in seed_ids)]
    return float(np.mean(values)) if values else float("nan")


def _student_seed_means(records: list[dict[str, Any]], label: str, cfg: dict[str, Any]) -> list[float]:
    n_student = int(cfg["n_student_seeds"])
    out = []
    for student in range(n_student):
        ids = [combined_seed(decoder, student, n_student) for decoder in range(int(cfg["n_decoder_seeds"]))]
        out.append(_mean_angvel(records, label, ids))
    return out


def _paired_control_minus_student(records: list[dict[str, Any]], student_label_name: str, control: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Positive means the student has lower angular-velocity error than the control.

    Each student seed is one number, after averaging the frozen decoders and the tasks.
    The interval is student-training variability on these decoders, not ten world models.
    """
    n_student = int(cfg["n_student_seeds"])
    deltas = []
    for student in range(n_student):
        ids = [combined_seed(decoder, student, n_student) for decoder in range(int(cfg["n_decoder_seeds"]))]
        deltas.append(_mean_angvel(records, control, ids) - _mean_angvel(records, student_label_name, ids))
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


def _fit_teacher(model: Any, support: TransitionDataset, global_z: torch.Tensor) -> dict[str, Any]:
    fitted = fit_from_support(model, support, global_z, lr=TEACHER_LR, updates=TEACHER_UPDATES, snapshot_at=(TEACHER_UPDATES,))
    vector = fitted["snapshots"][TEACHER_UPDATES]
    return {
        "vector": vector,
        "vector_sha256": vector_hash(vector),
        "support_loss_before": fitted["trace"][0]["support_loss"],
        "support_loss_after": fitted["trace"][-1]["support_loss"],
        "mean_grad_norm": float(np.mean([row["grad_norm"] for row in fitted["trace"] if row["grad_norm"] is not None])),
        "nonfinite": len(fitted["nonfinite"]),
        "latent_norm": float(torch.linalg.vector_norm(vector).item()),
    }


def _infer(model: Any, state: dict[str, torch.Tensor], support: TransitionDataset, budget: int) -> torch.Tensor:
    probe = model.clone_frozen()
    probe.encoder.load_state_dict(state)
    return encoder_context(probe, _prefix(support, budget), budget)


def _cell(model: Any, vector: torch.Tensor, query: TransitionDataset, teacher_z: torch.Tensor, horizons: list[int], angvel_index: int) -> dict[str, Any]:
    cell = score_with_z(model, vector, query, horizons, angvel_index)
    cell["latent_l2"] = float(torch.linalg.vector_norm(vector.detach() - teacher_z.detach()).item())
    return cell


def run_amortized_latent(
    *,
    protocol_path: str | Path = PROTOCOL_PATH,
    dev_path: str | Path = "artifacts/amortized_latent_dev.json",
    confirm_path: str | Path = "artifacts/amortized_latent_confirm.json",
    plot_path: str | Path = "artifacts/amortized_latent_dev.svg",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cfg = load_amortized_config()
    assert_protocol_frozen(protocol_path, cfg)
    assert_prior_artifacts_unchanged(cfg)
    assert_checkpoint_hashes(cfg)
    assert_amortized_seeds_disjoint(cfg)
    meta_specs, dev_specs, confirm_specs = assert_splits(cfg)
    selection = json.loads(Path(cfg["prior_selection"]).read_text())["selection_record"]
    if float(selection["chosen_lr"]) != TEACHER_LR or int(selection["chosen_updates"]) != TEACHER_UPDATES:
        raise RuntimeError("the stored teacher rule does not match the locked procedure")
    horizons = [int(h) for h in cfg["horizons"]]
    angvel_index = int(cfg["angular_velocity_index"])
    budget = int(cfg["support_budget"])
    lambdas = [int(v) for v in cfg["lambdas"]]
    epochs = [int(v) for v in cfg["epochs"]]
    budgets = [int(v) for v in cfg["budgets"]]
    deadline = t0 + float(cfg["time_limit_s"])

    def grab(spec: Any, n: int, env0: int, base: int) -> TransitionDataset:
        if spec.task_id in set(cfg["forbidden_task_ids"]):
            raise RuntimeError(f"refusing to collect forbidden confirmation task {spec.task_id}")
        ds = _collect(spec, n, env0=env0, base=base)
        expected = planned_env_seeds(n, env0)
        if {int(s) for s in np.unique(ds.seed)} != expected:
            raise RuntimeError(f"collect seeds drifted for {spec.task_id}")
        return ds

    meta_support = [grab(spec, budget, int(cfg["meta_support_env0"]) + 10 * i, int(cfg["meta_support_base"]) + i) for i, spec in enumerate(meta_specs)]
    dev_support = [grab(spec, budget, int(cfg["dev_support_env0"]) + 10 * i, int(cfg["dev_support_base"]) + i) for i, spec in enumerate(dev_specs)]
    dev_query = []
    for i, spec in enumerate(dev_specs):
        raw = grab(spec, int(cfg["query_transitions"]), int(cfg["dev_query_env0"]) + 10 * i, int(cfg["dev_query_base"]) + i)
        done = complete_episodes(raw, 16)
        if len(np.unique(done.episode_id)) != int(cfg["query_episodes"]):
            raise RuntimeError(f"{spec.task_id} did not yield {cfg['query_episodes']} query episodes")
        dev_query.append(done)
    assert_support_query_separated(*zip(dev_support, dev_query))
    assert_disjoint_seeds(*meta_support, *dev_support, *dev_query)
    resources = {
        "meta_support_env": int(sum(ds.env_interactions for ds in meta_support)),
        "dev_support_env": int(sum(ds.env_interactions for ds in dev_support)),
        "dev_query_env": int(sum(ds.env_interactions for ds in dev_query)),
        "confirm_support_env": 0,
        "confirm_query_env": 0,
        "teacher_optimizer_steps": 0,
        "student_epochs": 0,
    }
    per_decoder: list[dict[str, Any]] = []
    all_snapshots: dict[int, dict[int, dict[tuple[int, int], dict[str, torch.Tensor]]]] = {}
    raw_records: list[dict[str, Any]] = []
    teacher_rows: list[dict[str, Any]] = []
    inference_student_s = []
    inference_teacher_s = []
    for decoder in range(int(cfg["n_decoder_seeds"])):
        if time.perf_counter() > deadline:
            raise RuntimeError("amortized inference exceeded the time cap before development finished")
        parent = cfg["parent_checkpoints"][decoder]
        model = load_context_checkpoint(Path(parent["path"]))
        lock_network(model)
        if decoder_digest(model) == "":
            raise RuntimeError("decoder digest failed")
        digest = decoder_digest(model)
        init_state = {key: value.detach().cpu().clone() for key, value in model.encoder.state_dict().items()}
        if int(model.encoder.hidden) != ENCODER_HIDDEN or int(model.encoder.z_dim) != CONTEXT_DIM:
            raise RuntimeError("refusing to train an encoder whose capacity differs from the existing history encoder")
        global_z = torch.tensor(selection["global_vectors"][str(decoder)], dtype=torch.float32)
        if vector_hash(global_z) != parent["global_vector_sha256"]:
            raise RuntimeError(f"global vector hash mismatch for decoder {decoder}")
        mlp = load_mlp_checkpoint(Path(cfg["mlp_checkpoints"][decoder]["path"]), (64, 64))
        t_teacher = time.perf_counter()
        meta_teachers = []
        for task_index, spec in enumerate(meta_specs):
            fitted = _fit_teacher(model, _prefix(meta_support[task_index], budget), global_z)
            if decoder_digest(model) != digest:
                raise RuntimeError("teacher fit changed the decoder")
            meta_teachers.append(fitted["vector"])
            teacher_rows.append({"split": "meta", "decoder": decoder, "task": spec.task_id, "support_hash": prefix_hash(meta_support[task_index], budget), "checkpoint_sha256": parent["sha256"], **{k: v for k, v in fitted.items() if k != "vector"}, "vector": [float(v) for v in fitted["vector"].tolist()]})
            resources["teacher_optimizer_steps"] += TEACHER_UPDATES
        dev_teachers = []
        dev_wrong = []
        for task_index, spec in enumerate(dev_specs):
            fitted = _fit_teacher(model, _prefix(dev_support[task_index], budget), global_z)
            donor = support_for(dev_support, task_index, "wrong")
            if donor.task_id == spec.task_id:
                raise RuntimeError("wrong-task donor resolved to the same development task")
            wrong = _fit_teacher(model, _prefix(donor, budget), global_z)
            if decoder_digest(model) != digest:
                raise RuntimeError("development teacher fit changed the decoder")
            dev_teachers.append(fitted["vector"])
            dev_wrong.append(wrong["vector"])
            teacher_rows.append({"split": "dev", "decoder": decoder, "task": spec.task_id, "support_hash": prefix_hash(dev_support[task_index], budget), "checkpoint_sha256": parent["sha256"], **{k: v for k, v in fitted.items() if k != "vector"}, "vector": [float(v) for v in fitted["vector"].tolist()]})
            resources["teacher_optimizer_steps"] += TEACHER_UPDATES * 2
        inference_teacher_s.append(time.perf_counter() - t_teacher)
        fixed: dict[str, dict[str, dict[str, Any]]] = {}
        for task_index, spec in enumerate(dev_specs):
            query = dev_query[task_index]
            labels = {
                "zero": {"zero": _cell(model, torch.zeros(model.context_dim()), query, dev_teachers[task_index], horizons, angvel_index)},
                "global": {"global": _cell(model, global_z, query, dev_teachers[task_index], horizons, angvel_index)},
                "teacher": {"teacher": _cell(model, dev_teachers[task_index], query, dev_teachers[task_index], horizons, angvel_index)},
                "wrong": {"wrong": _cell(model, dev_wrong[task_index], query, dev_teachers[task_index], horizons, angvel_index)},
                "mlp_reference": {"mlp_reference": score_with_z_mlp(mlp, query, horizons, angvel_index)},
            }
            labels["mlp_reference"]["mlp_reference"]["latent_l2"] = None
            for k in budgets:
                t_inf = time.perf_counter()
                z_enc = _infer(model, init_state, dev_support[task_index], k)
                inference_student_s.append(time.perf_counter() - t_inf)
                labels[encoder_label(k)] = {encoder_label(k): _cell(model, z_enc, query, dev_teachers[task_index], horizons, angvel_index)}
            fixed[spec.task_id] = labels
        student_snapshots: dict[int, dict[tuple[int, int], dict[str, torch.Tensor]]] = {}
        for student in range(int(cfg["n_student_seeds"])):
            if time.perf_counter() > deadline:
                raise RuntimeError("amortized inference exceeded the time cap during student training")
            print(f"amortized decoder={decoder} student={student}", flush=True)
            student_snapshots[student] = {}
            for lam in lambdas:
                snapshots = train_student(
                    model, meta_support, meta_teachers, lam=lam, epochs=max(epochs), checkpoints=epochs, budgets=budgets,
                    student_lr=float(cfg["student_learning_rate"]), seed=10_000 + decoder * 100 + student,
                    init_state=init_state, decoder_before=digest,
                )
                resources["student_epochs"] += max(epochs)
                for epoch, state in snapshots.items():
                    student_snapshots[student][(lam, epoch)] = state
            seed_id = combined_seed(decoder, student, int(cfg["n_student_seeds"]))
            task_rows: dict[str, Any] = {}
            for task_index, spec in enumerate(dev_specs):
                labels = {name: payload for name, payload in fixed[spec.task_id].items()}
                for lam in lambdas:
                    for epoch in epochs:
                        state = student_snapshots[student][(lam, epoch)]
                        for k in budgets:
                            t_inf = time.perf_counter()
                            z_s = _infer(model, state, dev_support[task_index], k)
                            inference_student_s.append(time.perf_counter() - t_inf)
                            label = student_label(lam, epoch, k)
                            labels[label] = {label: _cell(model, z_s, dev_query[task_index], dev_teachers[task_index], horizons, angvel_index)}
                task_rows[spec.task_id] = {"labels": labels, "donor_task": dev_specs[(task_index + 1) % len(dev_specs)].task_id}
            block = {"model_seed": seed_id, "tasks": task_rows, "decoder_seed": decoder, "student_seed": student, "decoder_sha256": digest}
            per_decoder.append(block)
            raw_records.extend(records_from_cells([block]))
        all_snapshots[decoder] = student_snapshots
        print(f"amortized decoder={decoder}", flush=True)
    schema = dev_schema_from_config(cfg)
    completeness = _apply(raw_records, schema)
    scores = {}
    if completeness["declared_complete"]:
        for lam in lambdas:
            for epoch in epochs:
                for k in budgets:
                    label = student_label(lam, epoch, k)
                    scores[label] = _mean_angvel(raw_records, label)
    chosen = choose_student(scores) if scores else None
    chosen_label = None if chosen is None else student_label(*chosen)
    zero_mean = _mean_angvel(raw_records, "zero")
    encoder_mean = float("nan") if chosen is None else _mean_angvel(raw_records, encoder_label(chosen[2]))
    student_mean = float("nan") if chosen_label is None else scores[chosen_label]
    gate = bool(chosen is not None and completeness["declared_complete"] and development_gate(student_mean, zero_mean, encoder_mean))
    teacher_mean = _mean_angvel(raw_records, "teacher")
    global_mean = _mean_angvel(raw_records, "global")
    recovery = None if not np.isfinite(student_mean) else recovery_fraction(global_mean, student_mean, teacher_mean, min_relative=float(cfg["recovery_min_relative"]))
    head = _git_meta()
    sha = str(head.get("revision") or "")
    source_status = inspect_source_tree(sha) if sha else {"source_dirty": True}
    student_means = [] if chosen_label is None else _student_seed_means(raw_records, chosen_label, cfg)
    contrasts = {}
    summaries = {}
    if chosen_label is not None and completeness["declared_complete"]:
        for name in ("zero", "global", encoder_label(chosen[2]), "teacher", "wrong", "mlp_reference"):
            contrasts[name] = _paired_control_minus_student(raw_records, chosen_label, name, cfg)
        for name in (chosen_label, "zero", "global", encoder_label(chosen[2]), "teacher", "wrong", "mlp_reference"):
            summaries[name] = _metric_summary(raw_records, name)
    payload = {
        "protocol_id": cfg["protocol_id"],
        "hypothesis": cfg["h_amortized"],
        "implementation_sha": sha if not source_status.get("source_dirty") else None,
        "source_dirty": bool(source_status.get("source_dirty", True)),
        "git": head,
        "selection_recorded": bool(chosen is not None and completeness["declared_complete"] and not source_status.get("source_dirty", True)),
        "gate_pass": bool(gate and not source_status.get("source_dirty", True)),
        "chosen_lambda": None if chosen is None else chosen[0],
        "chosen_epoch": None if chosen is None else chosen[1],
        "chosen_budget": None if chosen is None else chosen[2],
        "scores_angvel_mae": scores,
        "means": {"student": student_mean, "zero": zero_mean, "encoder": encoder_mean, "teacher": teacher_mean, "global": global_mean, "wrong": _mean_angvel(raw_records, "wrong"), "mlp_reference": _mean_angvel(raw_records, "mlp_reference")},
        "student_seed_angvel": student_means,
        "student_seed_interval": seed_level_ci(student_means) if len(student_means) >= 2 else None,
        "paired_control_minus_student": contrasts,
        "metric_summary": summaries,
        "recovery_fraction": recovery,
        "recovery_note": "Reported only when the teacher beats the global vector by at least 5% relative. A positive fraction is not a control result.",
        "replication_unit": "student_training_seed after averaging the three frozen decoders and the development tasks",
        "n_student_seeds_note": "Ten student seeds share three frozen decoders. They are not ten independent world models.",
        "schema": schema,
        "raw_records": raw_records,
        "completeness": completeness,
        "declared_complete": bool(completeness["declared_complete"]),
        "teachers": teacher_rows,
        "encoder_parameter_count": encoder_parameter_count(load_context_checkpoint(Path(cfg["parent_checkpoints"][0]["path"]))),
        "resources": resources,
        "teacher_fit_seconds_per_decoder": inference_teacher_s,
        "student_infer_seconds_mean": float(np.mean(inference_student_s)) if inference_student_s else None,
        "data_hashes": {
            "meta_support": [prefix_hash(ds, len(ds)) for ds in meta_support],
            "dev_support": [prefix_hash(ds, len(ds)) for ds in dev_support],
            "dev_query": [prefix_hash(ds, len(ds)) for ds in dev_query],
        },
        "confirm_evaluated": False,
        "control_evaluated": False,
        "is_agi": False,
        "is_learning_to_learn": False,
        "wall_clock_s": time.perf_counter() - t0,
    }
    Path(dev_path).parent.mkdir(parents=True, exist_ok=True)
    if chosen is not None and scores:
        series = {}
        for k in budgets:
            series.setdefault("student", []).append(scores[student_label(chosen[0], chosen[1], k)])
            series.setdefault("encoder", []).append(_mean_angvel(raw_records, encoder_label(k)))
        for name in ("zero", "global", "teacher", "wrong"):
            series[name] = [_mean_angvel(raw_records, name) for _k in budgets]
        Path(plot_path).parent.mkdir(parents=True, exist_ok=True)
        _svg(Path(plot_path), budgets, series)
        payload["plot"] = str(plot_path)
    Path(dev_path).write_text(dumps_strict(payload))
    confirm_payload = None
    if payload["gate_pass"] and payload["selection_recorded"]:
        saved = json.loads(Path(dev_path).read_text())
        assert_dev_allows_confirmation(saved, cfg)
        confirm_payload = _run_confirmation(cfg, saved, confirm_specs, horizons, angvel_index, resources, grab, all_snapshots)
        confirm_payload["wall_clock_s"] = time.perf_counter() - t0
        Path(confirm_path).write_text(dumps_strict(confirm_payload))
        payload["confirm_evaluated"] = True
        payload["resources"] = resources
    payload["wall_clock_s"] = time.perf_counter() - t0
    Path(dev_path).write_text(dumps_strict(payload))
    return {"development": payload, "confirmation": confirm_payload}


def _confirm_schema(cfg: dict[str, Any], lam: int, epoch: int, budget: int) -> dict[str, Any]:
    labels = [student_label(lam, epoch, budget), encoder_label(budget), *FIXED_LABELS]
    n_student = int(cfg["n_student_seeds"])
    return {
        "seed_ids": [combined_seed(d, s, n_student) for d in range(int(cfg["n_decoder_seeds"])) for s in range(n_student)],
        "task_ids": list(cfg["confirm_task_ids"]),
        "labels": labels,
        "conditions_by_label": {label: [label] for label in labels},
        "metrics": ["mae", "rmse", "angvel_mae"],
        "horizons": ["3", "8", "16"],
        "per_dim": 3,
    }


def _run_confirmation(
    cfg: dict[str, Any],
    dev: dict[str, Any],
    specs: tuple[Any, ...],
    horizons: list[int],
    angvel_index: int,
    resources: dict[str, Any],
    grab: Any,
    snapshots: dict[int, dict[int, dict[tuple[int, int], dict[str, torch.Tensor]]]],
) -> dict[str, Any]:
    """Evaluate the locked student on the new physics. No hyperparameter is chosen here."""
    lam = int(dev["chosen_lambda"])
    epoch = int(dev["chosen_epoch"])
    budget_k = int(dev["chosen_budget"])
    support = [grab(spec, int(cfg["support_budget"]), int(cfg["confirm_support_env0"]) + 10 * i, int(cfg["confirm_support_base"]) + i) for i, spec in enumerate(specs)]
    query = []
    for i, spec in enumerate(specs):
        raw = grab(spec, int(cfg["query_transitions"]), int(cfg["confirm_query_env0"]) + 10 * i, int(cfg["confirm_query_base"]) + i)
        done = complete_episodes(raw, 16)
        if len(np.unique(done.episode_id)) != int(cfg["query_episodes"]):
            raise RuntimeError(f"{spec.task_id} confirmation query episode count drifted")
        query.append(done)
    assert_support_query_separated(*zip(support, query))
    resources["confirm_support_env"] = int(sum(ds.env_interactions for ds in support))
    resources["confirm_query_env"] = int(sum(ds.env_interactions for ds in query))
    selection = json.loads(Path(cfg["prior_selection"]).read_text())["selection_record"]
    per_seed = []
    for decoder in range(int(cfg["n_decoder_seeds"])):
        parent = cfg["parent_checkpoints"][decoder]
        model = load_context_checkpoint(Path(parent["path"]))
        lock_network(model)
        digest = decoder_digest(model)
        init_state = {key: value.detach().cpu().clone() for key, value in model.encoder.state_dict().items()}
        global_z = torch.tensor(selection["global_vectors"][str(decoder)], dtype=torch.float32)
        if vector_hash(global_z) != parent["global_vector_sha256"]:
            raise RuntimeError("confirmation global vector hash mismatch")
        teachers = []
        wrongs = []
        for task_index, spec in enumerate(specs):
            fitted = _fit_teacher(model, _prefix(support[task_index], int(cfg["support_budget"])), global_z)
            donor = support_for(support, task_index, "wrong")
            if donor.task_id == spec.task_id:
                raise RuntimeError("confirmation donor resolved to the same task")
            wrong = _fit_teacher(model, _prefix(donor, int(cfg["support_budget"])), global_z)
            if decoder_digest(model) != digest:
                raise RuntimeError("confirmation teacher fit changed the decoder")
            teachers.append(fitted["vector"])
            wrongs.append(wrong["vector"])
            resources["teacher_optimizer_steps"] += TEACHER_UPDATES * 2
        mlp = load_mlp_checkpoint(Path(cfg["mlp_checkpoints"][decoder]["path"]), (64, 64))
        fixed: dict[str, dict[str, Any]] = {}
        for task_index, spec in enumerate(specs):
            fixed[spec.task_id] = {
                "zero": {"zero": _cell(model, torch.zeros(model.context_dim()), query[task_index], teachers[task_index], horizons, angvel_index)},
                "global": {"global": _cell(model, global_z, query[task_index], teachers[task_index], horizons, angvel_index)},
                "teacher": {"teacher": _cell(model, teachers[task_index], query[task_index], teachers[task_index], horizons, angvel_index)},
                "wrong": {"wrong": _cell(model, wrongs[task_index], query[task_index], teachers[task_index], horizons, angvel_index)},
                "mlp_reference": {"mlp_reference": score_with_z_mlp(mlp, query[task_index], horizons, angvel_index)},
                encoder_label(budget_k): {encoder_label(budget_k): _cell(model, _infer(model, init_state, support[task_index], budget_k), query[task_index], teachers[task_index], horizons, angvel_index)},
            }
        for student in range(int(cfg["n_student_seeds"])):
            state = snapshots[decoder][student][(lam, epoch)]
            seed_id = combined_seed(decoder, student, int(cfg["n_student_seeds"]))
            task_rows = {}
            for task_index, spec in enumerate(specs):
                labels = {name: payload for name, payload in fixed[spec.task_id].items()}
                z_s = _infer(model, state, support[task_index], budget_k)
                label = student_label(lam, epoch, budget_k)
                labels[label] = {label: _cell(model, z_s, query[task_index], teachers[task_index], horizons, angvel_index)}
                task_rows[spec.task_id] = {"labels": labels}
            per_seed.append({"model_seed": seed_id, "tasks": task_rows})
    raw = records_from_cells(per_seed)
    schema = _confirm_schema(cfg, lam, epoch, budget_k)
    completeness = _apply(raw, schema)
    label = student_label(lam, epoch, budget_k)
    means = {name: _mean_angvel(raw, name) for name in (label, encoder_label(budget_k), *FIXED_LABELS)}
    student_means = _student_seed_means(raw, label, cfg)
    recovery = recovery_fraction(means["global"], means[label], means["teacher"], min_relative=float(cfg["recovery_min_relative"]))
    contrasts = {}
    summaries = {}
    if completeness["declared_complete"]:
        for name in ("zero", "global", encoder_label(budget_k), "teacher", "wrong", "mlp_reference"):
            contrasts[name] = _paired_control_minus_student(raw, label, name, cfg)
        for name in (label, "zero", "global", encoder_label(budget_k), "teacher", "wrong", "mlp_reference"):
            summaries[name] = _metric_summary(raw, name)
    return {
        "confirm_evaluated": True,
        "control_evaluated": False,
        "is_agi": False,
        "is_learning_to_learn": False,
        "chosen_lambda": lam,
        "chosen_epoch": epoch,
        "chosen_budget": budget_k,
        "schema": schema,
        "raw_records": raw,
        "completeness": completeness,
        "declared_complete": bool(completeness["declared_complete"]),
        "means": means,
        "student_seed_angvel": student_means,
        "student_seed_interval": seed_level_ci(student_means) if len(student_means) >= 2 else None,
        "beats_zero": bool(means[label] < means["zero"]),
        "beats_encoder": bool(means[label] < means[encoder_label(budget_k)]),
        "paired_control_minus_student": contrasts,
        "metric_summary": summaries,
        "recovery_fraction": recovery,
        "resources": resources,
        "data_hashes": {"support": [prefix_hash(ds, len(ds)) for ds in support], "query": [prefix_hash(ds, len(ds)) for ds in query]},
        "replication_unit": "student_training_seed after averaging the three frozen decoders and the confirmation tasks",
    }
