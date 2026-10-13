"""Direct latent-context diagnostic. Network weights stay frozen. Only z is optimized.

Source prediction only. No MPC. No confirmation physics. Not learning-to-learn.
The frozen-trunk encoder result is unchanged.
"""

from __future__ import annotations

import copy
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
from nexus.tasks.pendulum_family import pendulum_context_train
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_diagnosis import ROLLOUT_STARTS, complete_episodes
from nexus.world.context_optimization import _episode_prediction, _sha256
from nexus.world.context_pilot import _collect, _svg, prefix_hash
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, concat_datasets
from nexus.world.frozen_dynamics import (
    load_context_checkpoint,
    load_mlp_checkpoint,
    planned_env_seeds,
    records_from_cells,
    slim_cell,
    source_split_seeds,
)
from nexus.world.frozen_dynamics import load_frozen_config
from nexus.world.result_checks import schema_completeness
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/direct_latent_context_diagnostic.yaml")
PRIOR_SELECTION = Path("artifacts/frozen_dynamics_selection.json")
PRIOR_AUDIT = Path("artifacts/frozen_dynamics_audit.json")
METRICS = ("mae", "rmse", "angvel_mae")
HORIZONS = ("3", "8", "16")
FIXED_LABELS = ("zero", "global", "encoder", "mlp_reference", "constant_external")
AUDIT_LABELS = ("zero", "global", "task", "wrong", "encoder", "mlp_reference", "constant_external")


def load_latent_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("direct-latent config must be a mapping")
    required = {
        "protocol_id": "direct_latent_context_diagnostic_v1",
        "starting_sha": "5cc3a6611ffd0c6d4839d813c2521181e248a6e8",
        "prior_frozen_selection": "artifacts/frozen_dynamics_selection.json",
        "prior_frozen_audit": "artifacts/frozen_dynamics_audit.json",
        "confirmation_unlocked": False,
        "control_sweep": False,
        "n_seeds": 3,
        "n_source_tasks": 8,
        "support_budget": 128,
        "context_dim": 8,
        "global_updates": 300,
        "global_lr": 0.01,
        "learning_rates": [0.01, 0.1],
        "task_updates": [0, 16, 64, 256],
        "max_task_updates": 256,
        "source_per_task": 400,
        "query_episodes": 4,
        "query_transitions": 800,
        "angular_velocity_index": 2,
        "horizons": [3, 8, 16],
        "rollout_starts": [0, 32, 64, 96, 128, 160],
        "time_limit_s": 3600,
        "donor": "source_task_(i+1)_mod_n",
        "screen_angvel_improvement": 0.05,
        "screen_min_positive_seeds": 2,
        "screen_max_worsening": 0.05,
        "audit_support_env0": 48000,
        "audit_query_env0": 52000,
        "audit_support_base": 240000,
        "audit_query_base": 241000,
        "parent_history_updates": 1000,
        "mlp_reference_updates": 1000,
    }
    for key, expected in required.items():
        if cfg.get(key) != expected:
            raise ValueError(f"config {key}={cfg.get(key)!r} does not match the locked setting {expected!r}")
    hypothesis = (
        "With all network weights fixed, a latent vector optimized from a task's support transitions "
        "improves held-out query angular-velocity MAE over zero context, a global task-independent vector, "
        "and a vector optimized from wrong-task support."
    )
    if cfg.get("is_agi") is not False or cfg.get("h_latent") != hypothesis:
        raise ValueError("hypothesis must be stated exactly and this run is not AGI")
    if list(cfg["rollout_starts"]) != list(ROLLOUT_STARTS):
        raise ValueError("rollout starts drifted from the shared evaluator")
    if int(cfg["max_task_updates"]) != max(int(u) for u in cfg["task_updates"]):
        raise ValueError("the task grid must stop at its declared maximum")
    return cfg


def task_ids_from_config(cfg: dict[str, Any]) -> list[str]:
    return [spec.task_id for spec in pendulum_context_train()[: int(cfg["n_source_tasks"])]]


def rule_label(lr: float, updates: int) -> str:
    return f"direct_lr{float(lr):.2f}_u{int(updates)}"


def selection_schema_from_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Planned development grid. Seed and task ids come from the locked config."""
    labels: list[str] = []
    conditions: dict[str, list[str]] = {}
    for lr in cfg["learning_rates"]:
        for updates in cfg["task_updates"]:
            label = rule_label(float(lr), int(updates))
            labels.append(label)
            conditions[label] = ["task", "wrong"]
    for name in FIXED_LABELS:
        labels.append(name)
        conditions[name] = [name]
    return {
        "seed_ids": list(range(int(cfg["n_seeds"]))),
        "task_ids": task_ids_from_config(cfg),
        "labels": labels,
        "conditions_by_label": conditions,
        "metrics": list(METRICS),
        "horizons": list(HORIZONS),
        "per_dim": 3,
    }


def audit_schema_from_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Planned audit grid. Produced rows cannot shrink this set."""
    return {
        "seed_ids": list(range(int(cfg["n_seeds"]))),
        "task_ids": task_ids_from_config(cfg),
        "labels": list(AUDIT_LABELS),
        "conditions_by_label": {label: [label] for label in AUDIT_LABELS},
        "metrics": list(METRICS),
        "horizons": list(HORIZONS),
        "per_dim": 3,
    }


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


def paired_constant_minus_mlp(audit_path: str | Path = PRIOR_AUDIT) -> dict[str, Any]:
    """Paired constant-model minus MLP angular-velocity MAE from the frozen-dynamics audit.

    The contrast is one difference per model seed. Overlap of the two separate intervals
    is not the test.
    """
    payload = json.loads(Path(audit_path).read_text())
    rows = payload["per_seed_metrics"]
    deltas = [float(row["angvel_constant"]) - float(row["angvel_mlp"]) for row in rows]
    out = dict(seed_level_ci(deltas))
    out["per_seed"] = deltas
    out["contrast"] = "constant_external_minus_mlp"
    out["source"] = str(audit_path)
    return out


def latent_seed_groups(cfg: dict[str, Any]) -> dict[str, set[int]]:
    frozen_cfg = load_frozen_config()
    groups = source_split_seeds(frozen_cfg)
    n_tasks = int(frozen_cfg["n_source_tasks"])
    groups["frozen_audit_support"] = set()
    groups["frozen_audit_query"] = set()
    for i in range(n_tasks):
        groups["frozen_audit_support"] |= planned_env_seeds(128, int(frozen_cfg["audit_support_env0"]) + 10 * i)
        groups["frozen_audit_query"] |= planned_env_seeds(400, int(frozen_cfg["audit_query_env0"]) + 10 * i)
    groups["latent_audit_support"] = set()
    groups["latent_audit_query"] = set()
    for i in range(int(cfg["n_source_tasks"])):
        groups["latent_audit_support"] |= planned_env_seeds(int(cfg["support_budget"]), int(cfg["audit_support_env0"]) + 10 * i)
        groups["latent_audit_query"] |= planned_env_seeds(int(cfg["query_transitions"]), int(cfg["audit_query_env0"]) + 10 * i)
    return groups


def assert_latent_splits_disjoint(cfg: dict[str, Any]) -> None:
    named = latent_seed_groups(cfg)
    keys = list(named)
    for i, left in enumerate(keys):
        for right in keys[i + 1 :]:
            overlap = named[left] & named[right]
            if overlap:
                raise ValueError(f"collect seeds overlap between {left} and {right}: {sorted(overlap)[:8]}")


def lock_network(model: Any) -> None:
    for param in list(model.encoder.parameters()) + list(model.net.parameters()):
        param.requires_grad_(False)
    model.encoder.eval()
    model.net.eval()


def frozen_network_digest(model: Any) -> str:
    digest = hashlib.sha256()
    named = [(f"encoder.{name}", param.detach()) for name, param in model.encoder.named_parameters()]
    named += [(f"net.{name}", param.detach()) for name, param in model.net.named_parameters()]
    rms = model.obs_rms.state_dict()
    named.append(("rms.mean", torch.as_tensor(np.asarray(rms["mean"]))))
    named.append(("rms.var", torch.as_tensor(np.asarray(rms["var"]))))
    named.append(("rms.count", torch.as_tensor(float(rms["count"]))))
    for name, value in named:
        arr = value.detach().cpu().contiguous().numpy()
        digest.update(name.encode())
        digest.update(str(arr.shape).encode())
        digest.update(str(arr.dtype).encode())
        digest.update(np.ascontiguousarray(arr).tobytes())
    return digest.hexdigest()


def vector_hash(vector: torch.Tensor) -> str:
    arr = np.ascontiguousarray(vector.detach().cpu().numpy().astype(np.float32))
    return hashlib.sha256(arr.tobytes()).hexdigest()


def donor_index(task_index: int, n_tasks: int) -> int:
    return (int(task_index) + 1) % int(n_tasks)


def support_for(supports: list[TransitionDataset], task_index: int, kind: str) -> TransitionDataset:
    if kind == "task":
        return supports[int(task_index)]
    if kind == "wrong":
        return supports[donor_index(task_index, len(supports))]
    raise ValueError(kind)


def _finite_scalar(value: torch.Tensor) -> bool:
    return bool(torch.isfinite(value.detach()).all().item())


def fit_latent(
    model: Any,
    obs: np.ndarray,
    action: np.ndarray,
    nxt: np.ndarray,
    terminated: np.ndarray,
    z_init: torch.Tensor,
    *,
    lr: float,
    updates: int,
    snapshot_at: tuple[int, ...] | list[int],
    opt_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Adam on z only. Full batch. No gradient clipping and no loss change."""
    digest = frozen_network_digest(model)
    z = nn.Parameter(z_init.detach().clone().float())
    opt = torch.optim.Adam([z], lr=float(lr))
    started_fresh = opt_state is None
    if opt_state is not None:
        opt.load_state_dict(copy.deepcopy(opt_state))
    wanted = {int(step) for step in snapshot_at}
    snapshots: dict[int, torch.Tensor] = {}
    optimizer_states: dict[int, dict[str, Any]] = {}
    trace: list[dict[str, Any]] = []
    nonfinite: list[str] = []

    def forward() -> torch.Tensor:
        _state, _term, total = model.query_terms(obs, action, nxt, terminated, z)
        return total

    def mark(step: int, total: torch.Tensor, grad_norm: float | None) -> None:
        finite = _finite_scalar(total) and (grad_norm is None or np.isfinite(grad_norm))
        if not finite:
            nonfinite.append(f"step {step}")
        trace.append(
            {
                "step": int(step),
                "support_loss": float(total.detach().item()) if _finite_scalar(total) else None,
                "grad_norm": None if grad_norm is None else float(grad_norm),
                "latent_norm": float(torch.linalg.vector_norm(z.detach()).item()),
                "nonfinite": not finite,
            }
        )
        if int(step) in wanted:
            snapshots[int(step)] = z.detach().clone()
            optimizer_states[int(step)] = copy.deepcopy(opt.state_dict())

    initial = forward()
    mark(0, initial, None)
    for step in range(1, int(updates) + 1):
        opt.zero_grad(set_to_none=True)
        total = forward()
        if not _finite_scalar(total):
            mark(step, total, None)
            raise RuntimeError("latent optimization produced a nonfinite loss; refusing to clip or restart")
        total.backward()
        for name, param in list(model.encoder.named_parameters()) + list(model.net.named_parameters()):
            if param.grad is not None:
                raise RuntimeError(f"frozen parameter {name} received a gradient")
        if z.grad is None or not _finite_scalar(z.grad):
            mark(step, total.detach(), float("nan"))
            raise RuntimeError("latent optimization produced a nonfinite gradient; refusing to clip or restart")
        grad_norm = float(z.grad.detach().norm().item())
        opt.step()
        after = forward().detach()
        mark(step, after, grad_norm)
        if not _finite_scalar(after):
            raise RuntimeError("latent optimization produced a nonfinite loss after a step; refusing to clip or restart")
    if frozen_network_digest(model) != digest:
        raise RuntimeError("network weights or normalization changed during latent optimization")
    return {
        "snapshots": snapshots,
        "optimizer_states": optimizer_states,
        "trace": trace,
        "nonfinite": nonfinite,
        "started_fresh": started_fresh,
        "final": z.detach().clone(),
        "frozen_network_sha256": digest,
    }


def fit_from_support(
    model: Any,
    support: TransitionDataset,
    z_init: torch.Tensor,
    *,
    lr: float,
    updates: int,
    snapshot_at: tuple[int, ...] | list[int],
    query: TransitionDataset | None = None,
    opt_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Optimize z on support rows only. `query` is accepted so callers cannot sneak it into the loss."""
    del query
    take = support.slice(np.arange(len(support)))
    return fit_latent(
        model,
        take.obs,
        take.action,
        take.next_obs,
        take.terminated,
        z_init,
        lr=lr,
        updates=updates,
        snapshot_at=snapshot_at,
        opt_state=opt_state,
    )


def score_with_z(model: Any, vector: torch.Tensor, query: TransitionDataset, horizons: list[int], angvel_index: int) -> dict[str, Any]:
    probe = model.clone_frozen()
    probe.z = vector.detach().clone().float()
    z0 = probe.z.detach().clone()
    cell = slim_cell(_episode_prediction(probe, query, horizons, angvel_index), horizons)
    if not torch.equal(probe.z, z0):
        raise RuntimeError("evaluation updated z")
    return cell


def encoder_context(model: Any, support: TransitionDataset, budget: int) -> torch.Tensor:
    probe = model.clone_frozen()
    digest = frozen_network_digest(probe)
    probe.set_context_from_dataset(support, budget=int(budget))
    if frozen_network_digest(probe) != digest:
        raise RuntimeError("encoder inference changed network weights")
    return probe.z.detach().clone()


def choose_rule(scores: dict[str, dict[str, float]]) -> tuple[float, int]:
    """Lowest mean query angular-velocity MAE. Ties prefer fewer updates, then the lower learning rate."""
    if not scores:
        raise ValueError("no latent candidate scores")
    ranked = []
    for lr_text, steps in scores.items():
        for update_text, value in steps.items():
            ranked.append((float(value), int(update_text), float(lr_text)))
    ranked.sort()
    _value, updates, lr = ranked[0]
    return float(lr), int(updates)


def latent_screen(
    per_seed: list[dict[str, float]],
    *,
    improvement: float = 0.05,
    min_positive_seeds: int = 2,
    max_worsening: float = 0.05,
    frozen_ok: bool = True,
    complete: bool = True,
) -> dict[str, Any]:
    if len(per_seed) < 1:
        return {"pass": False, "reason": "no audit seeds"}

    def mean(key: str) -> float:
        return float(np.mean([row[key] for row in per_seed]))

    task = mean("angvel_task")
    zero = mean("angvel_zero")
    global_v = mean("angvel_global")
    wrong = mean("angvel_wrong")
    positive = 0
    for row in per_seed:
        if (row["angvel_zero"] - row["angvel_task"]) > 0 and (row["angvel_global"] - row["angvel_task"]) > 0 and (row["angvel_wrong"] - row["angvel_task"]) > 0:
            positive += 1
    beats_zero = task <= (1.0 - improvement) * zero
    beats_global = task <= (1.0 - improvement) * global_v
    beats_wrong = task <= (1.0 - improvement) * wrong
    harm_ok = mean("mae_task") <= (1.0 + max_worsening) * mean("mae_global") and mean("h16_task") <= (1.0 + max_worsening) * mean("h16_global")
    passed = bool(beats_zero and beats_global and beats_wrong and positive >= min_positive_seeds and harm_ok and frozen_ok and complete)
    return {
        "pass": passed,
        "angvel_task": task,
        "angvel_zero": zero,
        "angvel_global": global_v,
        "angvel_wrong": wrong,
        "angvel_encoder": mean("angvel_encoder") if "angvel_encoder" in per_seed[0] else None,
        "angvel_mlp": mean("angvel_mlp") if "angvel_mlp" in per_seed[0] else None,
        "angvel_constant_external": mean("angvel_constant_external") if "angvel_constant_external" in per_seed[0] else None,
        "positive_seeds": positive,
        "beats_zero": bool(beats_zero),
        "beats_global": bool(beats_global),
        "beats_wrong": bool(beats_wrong),
        "harm_ok": bool(harm_ok),
        "frozen_ok": bool(frozen_ok),
        "complete": bool(complete),
        "thresholds": {"improvement": improvement, "min_positive_seeds": min_positive_seeds, "max_worsening": max_worsening},
    }


def classify_latent(chosen_updates: int | None, screen: dict[str, Any], *, support_improved: bool, mean_grad_norm: float | None) -> dict[str, Any]:
    if chosen_updates is None:
        label = "incomplete"
    elif int(chosen_updates) == 0:
        label = "checkpoint_0_selected"
    elif screen.get("pass"):
        label = "task_specific"
    elif not support_improved:
        label = "support_did_not_improve"
    elif not screen.get("beats_global") and not screen.get("beats_wrong") and support_improved:
        label = "support_only" if screen.get("angvel_task", 0) > screen.get("angvel_global", 0) else "generic_recalibration"
    elif screen.get("beats_zero") and screen.get("beats_global") and not screen.get("beats_wrong"):
        label = "no_task_specific_information"
    elif support_improved and not screen.get("beats_global"):
        label = "generic_recalibration" if screen.get("angvel_task", 1) <= screen.get("angvel_global", 0) * 1.05 else "support_only"
    else:
        label = "absent"
    return {
        "label": label,
        "task_specific": label == "task_specific",
        "support_improved": bool(support_improved),
        "mean_grad_norm": mean_grad_norm,
        "additional_task_updates_selected": bool(chosen_updates not in (None, 0) and label == "task_specific"),
        "note": "Checkpoint 0 means task-specific optimization was not selected." if label == "checkpoint_0_selected" else "",
    }


def _mean_cell(tasks: dict[str, Any], label: str, condition: str, key: str) -> float:
    values = []
    for task in tasks.values():
        cell = task["labels"][label][condition]
        values.append(float(cell["rollout_mae"]["16"] if key == "h16" else cell[key]))
    return float(np.mean(values)) if values else float("nan")


def assert_support_query_separated(*pairs: tuple[TransitionDataset, TransitionDataset]) -> None:
    for support, query in pairs:
        overlap = {int(s) for s in np.unique(support.seed)} & {int(s) for s in np.unique(query.seed)}
        if overlap:
            raise ValueError(f"support and query collect seeds overlap: {sorted(overlap)[:8]}")


def assert_latent_audit_allowed(selection_path: str | Path, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(selection_path)
    if not path.is_file():
        raise RuntimeError("source audit is blocked until a selection manifest is saved")
    payload = json.loads(path.read_text())
    record = payload.get("selection_record")
    if not isinstance(record, dict) or record.get("selection_recorded") is not True:
        raise RuntimeError("source audit is blocked until the optimization rule is recorded")
    if payload.get("smoke") is True or record.get("incomplete") is True:
        raise RuntimeError("source audit is blocked for a smoke or incomplete selection")
    for key in ("chosen_lr", "chosen_updates", "global_vector_sha256", "parent_checkpoint_sha256", "frozen_network_sha256"):
        if key not in record:
            raise RuntimeError(f"source audit is blocked because {key} is missing")
    locked = cfg if cfg is not None else load_latent_config()
    schema = selection_schema_from_config(locked)
    report = _apply_schema(list(payload.get("raw_records") or []), schema)
    if not report["declared_complete"]:
        raise RuntimeError("source audit is blocked because the saved development cells are incomplete")
    if record.get("frozen_network_unchanged") is not True:
        raise RuntimeError("source audit is blocked because the network digest was not certified")
    return payload


def _load_prior() -> dict[str, Any]:
    if not PRIOR_SELECTION.is_file():
        raise RuntimeError(f"missing frozen-dynamics selection {PRIOR_SELECTION}")
    return json.loads(PRIOR_SELECTION.read_text())


def _require_hash(path: Path, expected: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    got = _sha256(path)
    if got != expected:
        raise RuntimeError(f"checkpoint hash mismatch for {path}: {got} != {expected}")


def _dataset_seeds(ds: TransitionDataset) -> set[int]:
    return {int(s) for s in np.unique(ds.seed)}


def _trace_summary(trace: list[dict[str, Any]]) -> dict[str, Any]:
    losses = [row["support_loss"] for row in trace if row["support_loss"] is not None]
    grads = [row["grad_norm"] for row in trace if row["grad_norm"] is not None]
    return {
        "support_loss_before": None if not losses else float(losses[0]),
        "support_loss_after": None if not losses else float(losses[-1]),
        "mean_grad_norm": None if not grads else float(np.mean(grads)),
        "max_grad_norm": None if not grads else float(np.max(grads)),
        "latent_norm_after": None if not trace else float(trace[-1]["latent_norm"]),
        "nonfinite_steps": int(sum(1 for row in trace if row["nonfinite"])),
        "optimizer_steps": int(trace[-1]["step"]) if trace else 0,
    }


def run_direct_latent(
    *,
    smoke: bool = False,
    config_path: str | Path = CONFIG_PATH,
    selection_path: str | Path | None = None,
    audit_path: str | Path | None = None,
    plot_path: str | Path | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cfg = load_latent_config(config_path)
    assert_latent_splits_disjoint(cfg)
    learning_rates = [float(v) for v in cfg["learning_rates"]]
    task_updates = [int(v) for v in cfg["task_updates"]]
    total_task_updates = int(cfg["max_task_updates"])
    global_updates = int(cfg["global_updates"])
    global_lr = float(cfg["global_lr"])
    n_seeds = int(cfg["n_seeds"])
    n_tasks = int(cfg["n_source_tasks"])
    per_task = int(cfg["source_per_task"])
    budget = int(cfg["support_budget"])
    query_transitions = int(cfg["query_transitions"])
    query_episodes = int(cfg["query_episodes"])
    if smoke:
        learning_rates = [0.01]
        task_updates = [0, 2]
        total_task_updates = 2
        global_updates = 2
        n_seeds = 1
        n_tasks = 2
        per_task = 220
        budget = 32
        query_transitions = 220
        query_episodes = 1
    deadline = t0 + float(cfg["time_limit_s"])
    horizons = [int(h) for h in cfg["horizons"]]
    angvel_index = int(cfg["angular_velocity_index"])
    specs = pendulum_context_train()[:n_tasks]
    prior = _load_prior()
    selected = prior["selection_record"]["selected_checkpoints"]
    incomplete = False
    resources = {
        "source_train_env": 0,
        "selection_support_env": 0,
        "selection_query_env": 0,
        "audit_support_env": 0,
        "audit_query_env": 0,
        "global_optimizer_steps": 0,
        "task_optimizer_steps": 0,
        "support_examples_processed": 0,
        "global_wall_s": 0.0,
        "task_wall_s": 0.0,
        "audit_collected": False,
    }

    def timed_out() -> bool:
        return time.perf_counter() > deadline

    def grab(spec: Any, n: int, env0: int, base: int, bucket: str) -> TransitionDataset:
        ds = _collect(spec, n, env0=env0, base=base)
        got = _dataset_seeds(ds)
        expected = planned_env_seeds(n, env0)
        if got != expected:
            raise RuntimeError(f"collect seeds for env0={env0} n={n} were {sorted(got)} not {sorted(expected)}")
        resources[bucket] += int(ds.env_interactions)
        return ds

    selection_support = [grab(spec, budget if smoke else 128, 8000 + 10 * i, 196_000 + i, "selection_support_env") for i, spec in enumerate(specs)]
    selection_query = [
        complete_episodes(grab(spec, 220 if smoke else 400, 14000 + 10 * i, 197_000 + i, "selection_query_env"), 16)
        for i, spec in enumerate(specs)
    ]
    data_hashes = {
        "selection_support": [prefix_hash(ds, len(ds)) for ds in selection_support],
        "selection_query": [prefix_hash(ds, len(ds)) for ds in selection_query],
    }
    if not smoke:
        if data_hashes["selection_support"] != prior["data_hashes"]["selection_support"][:n_tasks]:
            raise RuntimeError("selection support does not match the inspected frozen-dynamics split")
        if data_hashes["selection_query"] != prior["data_hashes"]["selection_query"][:n_tasks]:
            raise RuntimeError("selection query does not match the inspected frozen-dynamics split")
    assert_support_query_separated(*zip(selection_support, selection_query))
    per_seed: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    for seed in range(n_seeds):
        if timed_out():
            incomplete = True
            break
        parent = selected["history_selected"]
        mlp_info = selected["mlp_reference"]
        constant_info = selected["constant_selected"]
        parent_path = Path(parent["paths"][str(seed)])
        _require_hash(parent_path, parent["sha256"][str(seed)])
        _require_hash(Path(mlp_info["paths"][str(seed)]), mlp_info["sha256"][str(seed)])
        _require_hash(Path(constant_info["paths"][str(seed)]), constant_info["sha256"][str(seed)])
        model = load_context_checkpoint(parent_path)
        lock_network(model)
        digest = frozen_network_digest(model)
        tasks = [
            grab(spec, per_task, 1000 + 100 * seed + 10 * i, 191_000 + 50 * seed + 9 * i, "source_train_env")
            for i, spec in enumerate(specs)
        ]
        data_hashes[f"seed{seed}_train"] = [prefix_hash(ds, len(ds)) for ds in tasks]
        if not smoke and data_hashes[f"seed{seed}_train"] != prior["data_hashes"][f"seed{seed}_train"]:
            raise RuntimeError(f"source training hash mismatch for seed {seed}")
        assert_disjoint_seeds(*tasks, *selection_support, *selection_query)
        pooled = concat_datasets(*tasks, task_id="latent_source_pool")
        t_global = time.perf_counter()
        global_fit = fit_latent(
            model, pooled.obs, pooled.action, pooled.next_obs, pooled.terminated, torch.zeros(model.context_dim()),
            lr=global_lr, updates=global_updates, snapshot_at=(global_updates,),
        )
        resources["global_wall_s"] += time.perf_counter() - t_global
        resources["global_optimizer_steps"] += global_updates
        resources["support_examples_processed"] += int(global_updates * len(pooled))
        global_z = global_fit["final"]
        if frozen_network_digest(model) != digest:
            raise RuntimeError("global latent fit changed the network")
        trajectories: dict[tuple[str, int, str], dict[str, Any]] = {}
        t_task = time.perf_counter()
        for kind in ("task", "wrong"):
            for lr in learning_rates:
                for task_index in range(n_tasks):
                    support = support_for(selection_support, task_index, kind)
                    if len(support) < budget and not smoke:
                        raise RuntimeError(f"support for task {task_index} is shorter than {budget}")
                    used = support.slice(np.arange(min(budget, len(support))))
                    fitted = fit_from_support(
                        model, used, global_z, lr=lr, updates=total_task_updates, snapshot_at=task_updates, query=selection_query[task_index],
                    )
                    trajectories[(kind, task_index, f"{lr:.2f}")] = fitted
                    resources["task_optimizer_steps"] += total_task_updates
                    resources["support_examples_processed"] += int(total_task_updates * len(used))
                    if frozen_network_digest(model) != digest:
                        raise RuntimeError("task latent fit changed the network")
        resources["task_wall_s"] += time.perf_counter() - t_task
        mlp = load_mlp_checkpoint(Path(mlp_info["paths"][str(seed)]), (64, 64))
        constant_blob = torch.load(constant_info["paths"][str(seed)], map_location="cpu", weights_only=False)
        constant_model = load_context_checkpoint(Path(constant_info["paths"][str(seed)]))
        constant_vector = torch.as_tensor(constant_blob["constant_vector"]).float()
        external_digest = frozen_network_digest(constant_model)
        if external_digest == digest:
            raise RuntimeError("the external constant checkpoint is not a different FiLM pathway")
        task_rows: dict[str, Any] = {}
        for task_index, spec in enumerate(specs):
            labels: dict[str, Any] = {}
            query = selection_query[task_index]
            labels["zero"] = {"zero": score_with_z(model, torch.zeros(model.context_dim()), query, horizons, angvel_index)}
            labels["global"] = {"global": score_with_z(model, global_z, query, horizons, angvel_index)}
            labels["encoder"] = {"encoder": score_with_z(model, encoder_context(model, selection_support[task_index], budget), query, horizons, angvel_index)}
            labels["mlp_reference"] = {"mlp_reference": score_with_z_mlp(mlp, query, horizons, angvel_index)}
            labels["constant_external"] = {"constant_external": score_with_z(constant_model, constant_vector, query, horizons, angvel_index)}
            for lr in learning_rates:
                task_fit = trajectories[("task", task_index, f"{lr:.2f}")]
                wrong_fit = trajectories[("wrong", task_index, f"{lr:.2f}")]
                for step in task_updates:
                    label = rule_label(lr, step)
                    labels[label] = {
                        "task": score_with_z(model, task_fit["snapshots"][step], query, horizons, angvel_index),
                        "wrong": score_with_z(model, wrong_fit["snapshots"][step], query, horizons, angvel_index),
                    }
                    if step == 0 and not torch.allclose(task_fit["snapshots"][0], global_z):
                        raise RuntimeError("checkpoint 0 is not the global vector")
            task_rows[spec.task_id] = {"donor_task": specs[donor_index(task_index, n_tasks)].task_id, "labels": labels}
            for lr in learning_rates:
                curve_rows.append({"model_seed": seed, "task": spec.task_id, "lr": lr, "kind": "task", **_checkpoint_curve(trajectories[("task", task_index, f"{lr:.2f}")], task_updates, labels, lr, "task")})
                curve_rows.append({"model_seed": seed, "task": spec.task_id, "lr": lr, "kind": "wrong", **_checkpoint_curve(trajectories[("wrong", task_index, f"{lr:.2f}")], task_updates, labels, lr, "wrong")})
        per_seed.append(
            {
                "model_seed": seed,
                "tasks": task_rows,
                "frozen_network_sha256": digest,
                "global_vector_sha256": vector_hash(global_z),
                "global_vector": [float(v) for v in global_z.detach().cpu().tolist()],
                "global_trace": _trace_summary(global_fit["trace"]),
                "parent_checkpoint_sha256": parent["sha256"][str(seed)],
                "constant_external_network_sha256": external_digest,
            }
        )
        print(f"direct_latent seed={seed} smoke={smoke}", flush=True)

    schema = selection_schema_from_config(cfg) if not smoke else _executed_selection_schema(cfg, n_seeds, [spec.task_id for spec in specs], learning_rates, task_updates)
    raw_records = records_from_cells(per_seed)
    completeness = _apply_schema(raw_records, schema) if per_seed and not incomplete and not smoke else {
        "declared_complete": False,
        "failures": ["smoke or incomplete or missing selection"],
        "n_expected": schema.get("n_expected", 0) if False else 0,
        "n_records": len(raw_records),
    }
    if not smoke and per_seed and not incomplete:
        completeness = _apply_schema(raw_records, selection_schema_from_config(cfg))
    scores: dict[str, dict[str, float]] = {}
    if completeness.get("declared_complete"):
        for lr in learning_rates:
            scores[f"{lr:.2f}"] = {}
            for step in task_updates:
                label = rule_label(lr, step)
                scores[f"{lr:.2f}"][str(step)] = float(np.mean([_mean_cell(seed["tasks"], label, "task", "angvel_mae") for seed in per_seed]))
    chosen = choose_rule(scores) if scores else None
    head = _git_meta()
    sha = str(head.get("revision") or "")
    source_status = inspect_source_tree(sha) if sha else {"source_dirty": True}
    frozen_ok = bool(per_seed) and len({seed["frozen_network_sha256"] for seed in per_seed}) == len(per_seed)
    selection_record = {
        "selection_recorded": bool(chosen) and bool(completeness.get("declared_complete")) and not smoke and not incomplete and frozen_ok,
        "chosen_lr": None if chosen is None else chosen[0],
        "chosen_updates": None if chosen is None else chosen[1],
        "chosen_rule": "lowest mean development query angular-velocity MAE across seeds and tasks; ties prefer fewer updates, then the lower learning rate",
        "scores_angvel_mae": scores,
        "global_vector_sha256": {str(seed["model_seed"]): seed["global_vector_sha256"] for seed in per_seed},
        "global_vectors": {str(seed["model_seed"]): seed["global_vector"] for seed in per_seed},
        "parent_checkpoint_sha256": {str(seed["model_seed"]): seed["parent_checkpoint_sha256"] for seed in per_seed},
        "frozen_network_sha256": {str(seed["model_seed"]): seed["frozen_network_sha256"] for seed in per_seed},
        "frozen_network_unchanged": bool(per_seed) and not smoke and not incomplete,
        "smoke": bool(smoke),
        "incomplete": bool(incomplete) or bool(smoke),
    }
    selection_payload = {
        "protocol": _protocol(cfg, smoke, sha, source_status, learning_rates, task_updates, n_seeds),
        "selection_record": selection_record,
        "schema": selection_schema_from_config(cfg) if not smoke else schema,
        "raw_records": raw_records,
        "completeness": completeness,
        "curves": curve_rows,
        "data_hashes": data_hashes,
        "prior_paired_constant_minus_mlp": paired_constant_minus_mlp(),
        "resources": dict(resources),
        "per_seed": [{k: v for k, v in seed.items() if k not in ("tasks", "global_vector")} | {"task_ids": list(seed["tasks"])} for seed in per_seed],
        "summary": _selection_summary(per_seed, learning_rates, task_updates),
        "registered_audit_seeds": {
            "support_env0": int(cfg["audit_support_env0"]),
            "query_env0": int(cfg["audit_query_env0"]),
            "support_base": int(cfg["audit_support_base"]),
            "query_base": int(cfg["audit_query_base"]),
            "query_episodes": int(cfg["query_episodes"]),
            "query_transitions": int(cfg["query_transitions"]),
        },
        "wall_clock_s": time.perf_counter() - t0,
        "audit_evaluated": False,
        "confirm_evaluated": False,
        "control_evaluated": False,
        "is_agi": False,
        "smoke": bool(smoke),
    }
    if selection_path is not None:
        Path(selection_path).parent.mkdir(parents=True, exist_ok=True)
        Path(selection_path).write_text(dumps_strict(selection_payload))
    if plot_path is not None and curve_rows:
        _plot_curves(Path(plot_path), curve_rows, task_updates, learning_rates)
    audit_payload = None
    if selection_record["selection_recorded"] and selection_path is not None and not timed_out():
        saved = assert_latent_audit_allowed(selection_path, cfg)
        audit_payload = _run_audit(saved, cfg, specs, selection_support, selection_query, horizons, angvel_index, budget, resources, grab, deadline)
        audit_payload["wall_clock_s"] = time.perf_counter() - t0
        if audit_path is not None:
            Path(audit_path).write_text(dumps_strict(audit_payload))
    elif audit_path is not None:
        Path(audit_path).parent.mkdir(parents=True, exist_ok=True)
        Path(audit_path).write_text(dumps_strict({
            "audit_evaluated": False,
            "reason": "selection was not recorded",
            "declared_complete": False,
            "confirm_evaluated": False,
            "control_evaluated": False,
        }))
    selection_payload["wall_clock_s"] = time.perf_counter() - t0
    return {"selection": selection_payload, "audit": audit_payload}


def score_with_z_mlp(model: Any, query: TransitionDataset, horizons: list[int], angvel_index: int) -> dict[str, Any]:
    return slim_cell(_episode_prediction(model, query, horizons, angvel_index), horizons)


def _checkpoint_curve(fitted: dict[str, Any], updates: list[int], labels: dict[str, Any], lr: float, condition: str) -> dict[str, Any]:
    by_step = {int(row["step"]): row for row in fitted["trace"]}
    query = []
    support = []
    for step in updates:
        label = rule_label(lr, step)
        query.append(float(labels[label][condition]["angvel_mae"]))
        row = by_step.get(int(step))
        support.append(None if row is None else row["support_loss"])
    return {
        "updates": [int(step) for step in updates],
        "query_angvel": query,
        "support_loss": support,
        "summary": _trace_summary(fitted["trace"]),
    }


def _executed_selection_schema(cfg: dict[str, Any], n_seeds: int, task_ids: list[str], learning_rates: list[float], task_updates: list[int]) -> dict[str, Any]:
    labels = []
    conditions: dict[str, list[str]] = {}
    for lr in learning_rates:
        for updates in task_updates:
            label = rule_label(lr, updates)
            labels.append(label)
            conditions[label] = ["task", "wrong"]
    for name in FIXED_LABELS:
        labels.append(name)
        conditions[name] = [name]
    return {
        "seed_ids": list(range(n_seeds)),
        "task_ids": task_ids,
        "labels": labels,
        "conditions_by_label": conditions,
        "metrics": list(METRICS),
        "horizons": list(HORIZONS),
        "per_dim": 3,
    }


def _run_audit(
    saved: dict[str, Any],
    cfg: dict[str, Any],
    specs: tuple[Any, ...],
    selection_support: list[TransitionDataset],
    selection_query: list[TransitionDataset],
    horizons: list[int],
    angvel_index: int,
    budget: int,
    resources: dict[str, Any],
    grab: Any,
    deadline: float,
) -> dict[str, Any]:
    record = saved["selection_record"]
    chosen_lr = float(record["chosen_lr"])
    chosen_updates = int(record["chosen_updates"])
    schema = audit_schema_from_config(cfg)
    if list(schema["seed_ids"]) != list(range(int(cfg["n_seeds"]))):
        raise RuntimeError("audit schema was not built from the locked seed set")
    parent = json.loads(PRIOR_SELECTION.read_text())["selection_record"]["selected_checkpoints"]
    audit_support = [grab(spec, int(cfg["support_budget"]), int(cfg["audit_support_env0"]) + 10 * i, int(cfg["audit_support_base"]) + i, "audit_support_env") for i, spec in enumerate(specs)]
    audit_query = []
    for i, spec in enumerate(specs):
        raw = grab(spec, int(cfg["query_transitions"]), int(cfg["audit_query_env0"]) + 10 * i, int(cfg["audit_query_base"]) + i, "audit_query_env")
        done = complete_episodes(raw, 16)
        n_episodes = len(np.unique(done.episode_id))
        if n_episodes != int(cfg["query_episodes"]):
            raise RuntimeError(f"audit query for {spec.task_id} has {n_episodes} episodes, not {cfg['query_episodes']}")
        audit_query.append(done)
    resources["audit_collected"] = True
    assert_disjoint_seeds(*audit_support, *audit_query, *selection_support, *selection_query)
    assert_support_query_separated(*zip(audit_support, audit_query))
    per_seed = []
    support_before = []
    support_after = []
    grad_norms = []
    for seed in range(int(cfg["n_seeds"])):
        if time.perf_counter() > deadline:
            raise RuntimeError("audit exceeded the time cap before every seed was scored")
        parent_path = Path(parent["history_selected"]["paths"][str(seed)])
        _require_hash(parent_path, record["parent_checkpoint_sha256"][str(seed)])
        model = load_context_checkpoint(parent_path)
        lock_network(model)
        if frozen_network_digest(model) != record["frozen_network_sha256"][str(seed)]:
            raise RuntimeError("loaded network digest does not match the selection manifest")
        global_z = torch.tensor(record["global_vectors"][str(seed)], dtype=torch.float32)
        if vector_hash(global_z) != record["global_vector_sha256"][str(seed)]:
            raise RuntimeError("global vector does not match the recorded hash")
        mlp = load_mlp_checkpoint(Path(parent["mlp_reference"]["paths"][str(seed)]), (64, 64))
        constant_path = Path(parent["constant_selected"]["paths"][str(seed)])
        constant_blob = torch.load(constant_path, map_location="cpu", weights_only=False)
        constant_model = load_context_checkpoint(constant_path)
        constant_vector = torch.as_tensor(constant_blob["constant_vector"]).float()
        labels_by_task: dict[str, Any] = {}
        for task_index, spec in enumerate(specs):
            query = audit_query[task_index]
            real_support = audit_support[task_index].slice(np.arange(min(budget, len(audit_support[task_index]))))
            donor = support_for(audit_support, task_index, "wrong").slice(np.arange(min(budget, len(support_for(audit_support, task_index, "wrong")))))
            task_fit = fit_from_support(model, real_support, global_z, lr=chosen_lr, updates=chosen_updates, snapshot_at=(chosen_updates,), query=query)
            wrong_fit = fit_from_support(model, donor, global_z, lr=chosen_lr, updates=chosen_updates, snapshot_at=(chosen_updates,), query=query)
            if frozen_network_digest(model) != record["frozen_network_sha256"][str(seed)]:
                raise RuntimeError("audit optimization changed the network")
            task_z = global_z if chosen_updates == 0 else task_fit["snapshots"][chosen_updates]
            wrong_z = global_z if chosen_updates == 0 else wrong_fit["snapshots"][chosen_updates]
            summary = _trace_summary(task_fit["trace"])
            support_before.append(summary["support_loss_before"])
            support_after.append(summary["support_loss_after"])
            if summary["mean_grad_norm"] is not None:
                grad_norms.append(summary["mean_grad_norm"])
            resources["task_optimizer_steps"] += chosen_updates * 2
            resources["support_examples_processed"] += chosen_updates * (len(real_support) + len(donor))
            labels_by_task[spec.task_id] = {
                "labels": {
                    "zero": {"zero": score_with_z(model, torch.zeros(model.context_dim()), query, horizons, angvel_index)},
                    "global": {"global": score_with_z(model, global_z, query, horizons, angvel_index)},
                    "task": {"task": score_with_z(model, task_z, query, horizons, angvel_index)},
                    "wrong": {"wrong": score_with_z(model, wrong_z, query, horizons, angvel_index)},
                    "encoder": {"encoder": score_with_z(model, encoder_context(model, real_support, budget), query, horizons, angvel_index)},
                    "mlp_reference": {"mlp_reference": score_with_z_mlp(mlp, query, horizons, angvel_index)},
                    "constant_external": {"constant_external": score_with_z(constant_model, constant_vector, query, horizons, angvel_index)},
                }
            }
        per_seed.append({"model_seed": seed, "tasks": labels_by_task})
    raw_records = records_from_cells(per_seed)
    completeness = _apply_schema(raw_records, schema)
    rows = []
    for seed in per_seed:
        tasks = seed["tasks"]
        rows.append(
            {
                "angvel_task": _mean_cell(tasks, "task", "task", "angvel_mae"),
                "angvel_zero": _mean_cell(tasks, "zero", "zero", "angvel_mae"),
                "angvel_global": _mean_cell(tasks, "global", "global", "angvel_mae"),
                "angvel_wrong": _mean_cell(tasks, "wrong", "wrong", "angvel_mae"),
                "angvel_encoder": _mean_cell(tasks, "encoder", "encoder", "angvel_mae"),
                "angvel_mlp": _mean_cell(tasks, "mlp_reference", "mlp_reference", "angvel_mae"),
                "angvel_constant_external": _mean_cell(tasks, "constant_external", "constant_external", "angvel_mae"),
                "mae_task": _mean_cell(tasks, "task", "task", "mae"),
                "mae_global": _mean_cell(tasks, "global", "global", "mae"),
                "mae_zero": _mean_cell(tasks, "zero", "zero", "mae"),
                "rmse_task": _mean_cell(tasks, "task", "task", "rmse"),
                "h16_task": _mean_cell(tasks, "task", "task", "h16"),
                "h16_global": _mean_cell(tasks, "global", "global", "h16"),
                "h16_zero": _mean_cell(tasks, "zero", "zero", "h16"),
            }
        )
    screen = latent_screen(
        rows,
        improvement=float(cfg["screen_angvel_improvement"]),
        min_positive_seeds=int(cfg["screen_min_positive_seeds"]),
        max_worsening=float(cfg["screen_max_worsening"]),
        frozen_ok=True,
        complete=bool(completeness["declared_complete"]),
    )
    before = float(np.mean(support_before)) if support_before else float("nan")
    after = float(np.mean(support_after)) if support_after else float("nan")
    support_improved = bool(np.isfinite(before) and np.isfinite(after) and after < before)
    mean_grad = float(np.mean(grad_norms)) if grad_norms else None
    contrasts = _paired_contrasts(rows)
    return {
        "protocol": saved["protocol"],
        "selection_record": record,
        "schema": schema,
        "raw_records": raw_records,
        "per_seed_metrics": rows,
        "summary": _intervals(rows),
        "paired_contrasts": contrasts,
        "support_loss_before": before,
        "support_loss_after": after,
        "support_improved": support_improved,
        "mean_grad_norm": mean_grad,
        "screen": screen,
        "classification": classify_latent(chosen_updates, screen, support_improved=support_improved, mean_grad_norm=mean_grad),
        "completeness": completeness,
        "declared_complete": bool(completeness["declared_complete"]),
        "data_hashes": {
            "audit_support": [prefix_hash(ds, len(ds)) for ds in audit_support],
            "audit_query": [prefix_hash(ds, len(ds)) for ds in audit_query],
        },
        "resources": resources,
        "query_episodes_per_task": int(cfg["query_episodes"]),
        "confirm_evaluated": False,
        "control_evaluated": False,
        "is_agi": False,
        "audit_evaluated": True,
    }


def _paired_contrasts(rows: list[dict[str, float]]) -> dict[str, Any]:
    pairs = {
        "zero_minus_task": ("angvel_zero", "angvel_task"),
        "global_minus_task": ("angvel_global", "angvel_task"),
        "wrong_minus_task": ("angvel_wrong", "angvel_task"),
        "encoder_minus_task": ("angvel_encoder", "angvel_task"),
        "mlp_minus_task": ("angvel_mlp", "angvel_task"),
        "constant_external_minus_task": ("angvel_constant_external", "angvel_task"),
    }
    out = {}
    for name, (left, right) in pairs.items():
        deltas = [float(row[left]) - float(row[right]) for row in rows]
        out[name] = seed_level_ci(deltas) if len(deltas) >= 2 else {"n": len(deltas), "mean": float(np.mean(deltas)) if deltas else None, "per_seed": deltas}
        if len(deltas) >= 2:
            out[name] = dict(out[name])
            out[name]["per_seed"] = deltas
    return out


def _intervals(rows: list[dict[str, float]]) -> dict[str, Any]:
    out = {}
    for key in rows[0]:
        values = [float(row[key]) for row in rows]
        out[key] = seed_level_ci(values) if len(values) >= 2 else {"n": len(values), "mean": float(np.mean(values)) if values else None}
    return out


def _selection_summary(per_seed: list[dict[str, Any]], learning_rates: list[float], task_updates: list[int]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not per_seed:
        return out
    for lr in learning_rates:
        for step in task_updates:
            label = rule_label(lr, step)
            block = {}
            for condition in ("task", "wrong"):
                values = [_mean_cell(seed["tasks"], label, condition, "angvel_mae") for seed in per_seed]
                block[condition] = seed_level_ci(values) if len(values) >= 2 else {"n": len(values), "mean": float(np.mean(values)) if values else None}
            out[label] = block
    for name in ("zero", "global", "encoder"):
        values = [_mean_cell(seed["tasks"], name, name, "angvel_mae") for seed in per_seed]
        out[name] = seed_level_ci(values) if len(values) >= 2 else {"n": len(values), "mean": float(np.mean(values)) if values else None}
    return out


def _protocol(cfg: dict[str, Any], smoke: bool, sha: str, source_status: dict[str, Any], learning_rates: list[float], task_updates: list[int], n_seeds: int) -> dict[str, Any]:
    return {
        "code_version": "direct_latent_context_diagnostic",
        "config": cfg,
        "executed_learning_rates": learning_rates,
        "executed_task_updates": task_updates,
        "executed_seeds": n_seeds,
        "smoke": bool(smoke),
        "implementation_sha": sha if not source_status.get("source_dirty") else None,
        "source_dirty": bool(source_status.get("source_dirty", True)),
        "git": _git_meta(),
        "confirm_evaluated": False,
        "control_evaluated": False,
        "is_agi": False,
        "h_latent": cfg.get("h_latent"),
        "prior_result": "Frozen-trunk encoder and FiLM training failed the context screen. That result is unchanged.",
    }


def _plot_curves(path: Path, curve_rows: list[dict[str, Any]], updates: list[int], learning_rates: list[float]) -> None:
    series: dict[str, list[float]] = {}
    for lr in learning_rates:
        for kind in ("task", "wrong"):
            acc = []
            for step_index, _step in enumerate(updates):
                values = []
                for row in curve_rows:
                    if float(row["lr"]) == float(lr) and row["kind"] == kind and row["query_angvel"][step_index] is not None:
                        values.append(float(row["query_angvel"][step_index]))
                acc.append(float(np.mean(values)) if values else float("nan"))
            series[f"{kind}_lr{lr:.2f}"] = acc
    _svg(path, updates, series)
    support_series: dict[str, list[float]] = {}
    for lr in learning_rates:
        for kind in ("task", "wrong"):
            acc = []
            for step_index, _step in enumerate(updates):
                values = [float(row["support_loss"][step_index]) for row in curve_rows if float(row["lr"]) == float(lr) and row["kind"] == kind and row["support_loss"][step_index] is not None]
                acc.append(float(np.mean(values)) if values else float("nan"))
            support_series[f"{kind}_lr{lr:.2f}"] = acc
    _svg(path.with_name(path.stem + "_support" + path.suffix), updates, support_series)
