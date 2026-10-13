"""Frozen-dynamics context diagnostic. Source prediction only.

The shared trunk, prediction heads, and normalization stay at the 3000-update
checkpoint. Only the history encoder and FiLM, or a constant vector and FiLM,
receive further Adam updates. No MPC. No confirmation physics. Not learning-to-learn.
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
from nexus.world.context_diagnosis import complete_episodes
from nexus.world.context_model import (
    MAX_CONTEXT,
    ContextWorldModel,
    make_context_schedule,
    split_support_query,
    support_take,
)
from nexus.world.context_optimization import (
    CHECKPOINT_DIR as PRIOR_CHECKPOINT_DIR,
    _context_bundle,
    _episode_prediction,
    _sha256,
    choose_checkpoint,
)
from nexus.world.context_pilot import _collect, _svg, prefix_hash
from nexus.world.data import TransitionDataset, assert_disjoint_seeds
from nexus.world.dynamics import WorldModel
from nexus.world.protocol import V089C_TRAIN_SEED
from nexus.world.result_checks import schema_completeness
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/frozen_dynamics_context_diagnostic.yaml")
CHECKPOINT_DIR = Path("artifacts/frozen_dynamics_checkpoints")
PRIOR_SELECTION = Path("artifacts/context_optimization_selection.json")
METRICS = ("mae", "rmse", "angvel_mae")
HORIZONS = ("3", "8", "16")
AUDIT_LABELS = ("history_selected", "starting", "constant_selected", "mlp_reference")
EPISODE_CAP = 200


def load_frozen_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("frozen-dynamics config must be a mapping")
    required = {
        "protocol_id": "frozen_dynamics_context_diagnostic_v1",
        "starting_sha": "eecdd7b813601613c176b0005d053dc53604ea61",
        "prior_optimization_sha": "6fbf78d865e328ca137a8be8fdd55f6d6e781018",
        "prior_selection_artifact": "artifacts/context_optimization_selection.json",
        "prior_context_updates": 3000,
        "mlp_reference_updates": 1000,
        "confirmation_unlocked": False,
        "control_sweep": False,
        "additional_updates": [0, 300, 1000],
        "total_additional_updates": 1000,
        "n_seeds": 3,
        "n_source_tasks": 8,
        "context_dim": 8,
        "encoder_hidden": 32,
        "trunk_hidden": [48, 48],
        "mlp_hidden": [64, 64],
        "lr": 0.001,
        "batch": 64,
        "empty_prob": 0.2,
        "support_policy": "fixed_128",
        "support_budget": 128,
        "angular_velocity_index": 2,
        "horizons": [3, 8, 16],
        "rollout_starts": [0, 32, 64, 96, 128, 160],
        "source_per_task": 400,
        "time_limit_s": 3600,
        "donor": "source_task_(i+1)_mod_n",
        "screen_angvel_improvement": 0.05,
        "screen_min_positive_seeds": 2,
        "screen_max_worsening": 0.05,
        "audit_support_env0": 36000,
        "audit_query_env0": 40000,
        "audit_support_base": 230000,
        "audit_query_base": 231000,
        "init_seed_offset": 8000,
        "prior_audit_support_env0": 20000,
        "prior_audit_query_env0": 24000,
    }
    for key, expected in required.items():
        if cfg.get(key) != expected:
            raise ValueError(f"config {key}={cfg.get(key)!r} does not match the locked setting {expected!r}")
    hypothesis = (
        "With shared dynamics fixed, training a history encoder and FiLM produces lower held-out "
        "source prediction error with real context than with zero context, wrong-task context, and "
        "a trainable constant-context control."
    )
    if cfg.get("is_agi") is not False or cfg.get("h_frozen") != hypothesis:
        raise ValueError("hypothesis must be stated exactly and this run is not AGI")
    return cfg


def planned_env_seeds(n_transitions: int, env0: int, *, episode_cap: int = EPISODE_CAP) -> set[int]:
    """Env seeds `collect_transitions` assigns when every episode lasts `episode_cap` or the remainder."""
    n = int(n_transitions)
    n_env = max(2, min(8, max(1, n // 32)))
    seeds: set[int] = set()
    remaining = n
    episode_id = 0
    while remaining > 0:
        seeds.add(int(env0) + (episode_id % n_env) + 1000 * (episode_id // n_env))
        remaining -= min(int(episode_cap), remaining)
        episode_id += 1
    return seeds


def source_split_seeds(cfg: dict[str, Any]) -> dict[str, set[int]]:
    """Collect-seed sets that the fresh audit is not allowed to touch."""
    n_tasks = int(cfg["n_source_tasks"])
    n_seeds = int(cfg["n_seeds"])
    per_task = int(cfg["source_per_task"])
    groups: dict[str, set[int]] = {
        "train": set(),
        "val": set(),
        "selection_support": set(),
        "selection_query": set(),
        "diagnosis_prefix": set(),
        "prior_audit_support": set(),
        "prior_audit_query": set(),
    }
    for s in range(n_seeds):
        for i in range(n_tasks):
            groups["train"] |= planned_env_seeds(per_task, 1000 + 100 * s + 10 * i)
            groups["val"] |= planned_env_seeds(32, 3000 + 50 * s + 10 * i)
            groups["diagnosis_prefix"] |= planned_env_seeds(1024, 5000 + 50 * s + 10 * i)
    for i in range(n_tasks):
        groups["selection_support"] |= planned_env_seeds(128, 8000 + 10 * i)
        groups["selection_query"] |= planned_env_seeds(400, 14000 + 10 * i)
        groups["prior_audit_support"] |= planned_env_seeds(128, int(cfg["prior_audit_support_env0"]) + 10 * i)
        groups["prior_audit_query"] |= planned_env_seeds(400, int(cfg["prior_audit_query_env0"]) + 10 * i)
    return groups


def fresh_audit_seeds(cfg: dict[str, Any], *, n_tasks: int | None = None) -> dict[str, set[int]]:
    n = int(cfg["n_source_tasks"] if n_tasks is None else n_tasks)
    support: set[int] = set()
    query: set[int] = set()
    for i in range(n):
        support |= planned_env_seeds(128, int(cfg["audit_support_env0"]) + 10 * i)
        query |= planned_env_seeds(400, int(cfg["audit_query_env0"]) + 10 * i)
    return {"audit_support": support, "audit_query": query}


def assert_source_splits_disjoint(cfg: dict[str, Any], *, n_tasks: int | None = None) -> None:
    groups = source_split_seeds(cfg)
    fresh = fresh_audit_seeds(cfg, n_tasks=n_tasks)
    named = {**groups, **fresh}
    keys = list(named)
    for i, left in enumerate(keys):
        for right in keys[i + 1 :]:
            overlap = named[left] & named[right]
            if overlap:
                raise ValueError(f"collect seeds overlap between {left} and {right}: {sorted(overlap)[:8]}")


def freeze_shared_dynamics(model: ContextWorldModel) -> None:
    """Freeze trunk, state head, termination head. Leave encoder and FiLM trainable."""
    for name, param in model.net.named_parameters():
        if name.startswith("film."):
            param.requires_grad_(True)
        elif name.startswith(("trunk.", "state_head.", "term_head.")):
            param.requires_grad_(False)
        else:
            raise RuntimeError(f"unexpected dynamics parameter {name}")
    for param in model.encoder.parameters():
        param.requires_grad_(True)


def _named_frozen(model: ContextWorldModel) -> list[tuple[str, torch.Tensor]]:
    rows = [(f"net.{name}", param.detach()) for name, param in model.net.named_parameters() if not name.startswith("film.")]
    rms = model.obs_rms.state_dict()
    rows.append(("rms.mean", torch.as_tensor(np.asarray(rms["mean"]))))
    rows.append(("rms.var", torch.as_tensor(np.asarray(rms["var"]))))
    rows.append(("rms.count", torch.as_tensor(float(rms["count"]))))
    return rows


def frozen_parameter_digest(model: ContextWorldModel) -> str:
    digest = hashlib.sha256()
    for name, value in _named_frozen(model):
        arr = value.detach().cpu().contiguous().numpy()
        digest.update(name.encode())
        digest.update(str(arr.shape).encode())
        digest.update(str(arr.dtype).encode())
        digest.update(np.ascontiguousarray(arr).tobytes())
    return digest.hexdigest()


def _history_params(model: ContextWorldModel) -> tuple[list[torch.nn.Parameter], list[str]]:
    encoder = list(model.encoder.parameters())
    film = [param for name, param in model.net.named_parameters() if name.startswith("film.")]
    frozen = [param for name, param in model.net.named_parameters() if not name.startswith("film.")]
    names = [f"encoder.{name}" for name, _param in model.encoder.named_parameters()]
    names += [f"net.{name}" for name, _param in model.net.named_parameters() if name.startswith("film.")]
    if not encoder or not film:
        raise RuntimeError("history training requires an encoder and FiLM")
    if any(not param.requires_grad for param in encoder + film):
        raise RuntimeError("encoder or FiLM is not trainable; clone_frozen() is not a training setup")
    if any(param.requires_grad for param in frozen):
        raise RuntimeError("shared dynamics parameters are still trainable")
    return encoder + film, names


def history_optimizer(model: ContextWorldModel, lr: float = 1e-3) -> torch.optim.Optimizer:
    params, _names = _history_params(model)
    return torch.optim.Adam(params, lr=float(lr))


def constant_optimizer(model: ContextWorldModel, vector: torch.nn.Parameter, lr: float = 1e-3) -> torch.optim.Optimizer:
    if not isinstance(vector, torch.nn.Parameter) or not vector.requires_grad:
        raise RuntimeError("constant context must be a trainable parameter")
    film = [param for name, param in model.net.named_parameters() if name.startswith("film.")]
    frozen = [param for name, param in model.net.named_parameters() if not name.startswith("film.")]
    encoder = list(model.encoder.parameters())
    if any(param.requires_grad for param in encoder):
        raise RuntimeError("constant adaptation must not train the history encoder")
    if any(not param.requires_grad for param in film):
        raise RuntimeError("constant adaptation must train FiLM")
    if any(param.requires_grad for param in frozen):
        raise RuntimeError("shared dynamics parameters are still trainable")
    params = [vector, *film]
    if any(param is encoder_param for param in params for encoder_param in encoder):
        raise RuntimeError("encoder parameter leaked into the constant optimizer")
    return torch.optim.Adam(params, lr=float(lr))


def trainable_names(model: ContextWorldModel, vector: torch.nn.Parameter | None = None) -> list[str]:
    names = [f"encoder.{name}" for name, param in model.encoder.named_parameters() if param.requires_grad]
    names += [f"net.{name}" for name, param in model.net.named_parameters() if param.requires_grad]
    if vector is not None and vector.requires_grad:
        names.append("constant_vector")
    return names


def mean_training_support_context(model: ContextWorldModel, tasks: list[TransitionDataset], seed: int) -> torch.Tensor:
    """Mean of per-task support encodings. Uses its own RNG, not the query schedule."""
    rng = np.random.default_rng(int(seed))
    probe = model.clone_trainable()
    vectors = []
    for ds in tasks:
        support, _query = split_support_query(ds, rng)
        k = min(MAX_CONTEXT, len(support))
        sl = support.slice(np.arange(k))
        vectors.append(probe.encode(sl.obs, sl.action, sl.next_obs, differentiable=False).detach().clone())
        probe.clear_context()
    if not vectors:
        raise RuntimeError("no source-training tasks for the constant-context initialization")
    return torch.stack(vectors, dim=0).mean(dim=0)


def _grad_norm(params: list[torch.nn.Parameter]) -> float:
    total = 0.0
    for param in params:
        if param.grad is not None:
            total += float(param.grad.detach().norm().item())
    return total


def _consume_row(model: ContextWorldModel, tasks: list[TransitionDataset], row: dict[str, Any]) -> tuple[TransitionDataset, np.ndarray]:
    ds = tasks[int(row["task_index"])]
    query = ds.slice(np.asarray(row["query_index"], dtype=np.int64))
    take = support_take(row, "fixed")
    if take.size:
        support = ds.slice(take)
        if set(np.unique(support.episode_id).tolist()) & set(np.unique(query.episode_id).tolist()):
            raise RuntimeError("support and query episodes overlap")
    return query, take


def run_history_updates(
    model: ContextWorldModel,
    opt: torch.optim.Optimizer,
    tasks: list[TransitionDataset],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Adam steps on encoder and FiLM only. The caller must already have frozen the trunk and heads."""
    params, _names = _history_params(model)
    opt_ids = {id(param) for param in opt.param_groups[0]["params"]}
    if opt_ids != {id(param) for param in params}:
        raise RuntimeError("history optimizer parameters are not exactly the encoder and FiLM")
    encoder_params = list(model.encoder.parameters())
    film_params = [param for name, param in model.net.named_parameters() if name.startswith("film.")]
    frozen_before = frozen_parameter_digest(model)
    grad_encoder: list[float] = []
    grad_film: list[float] = []
    state_losses: list[float] = []
    term_losses: list[float] = []
    query_indices: list[list[int]] = []
    n_query = 0
    n_support = 0
    n_nonempty = 0
    for row in rows:
        query, take = _consume_row(model, tasks, row)
        query_indices.append(np.asarray(row["query_index"], dtype=np.int64).tolist())
        model.net.train()
        if take.size == 0:
            z = torch.zeros(model.context_dim())
        else:
            support = tasks[int(row["task_index"])].slice(take)
            z = model.encode(support.obs, support.action, support.next_obs, differentiable=True)
            n_support += int(take.size)
            n_nonempty += 1
        state, term_loss, loss = model.query_terms(query.obs, query.action, query.next_obs, query.terminated, z)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        grad_encoder.append(_grad_norm(encoder_params))
        grad_film.append(_grad_norm(film_params))
        for name, param in model.net.named_parameters():
            if not name.startswith("film.") and param.grad is not None:
                raise RuntimeError(f"frozen parameter {name} received a gradient")
        nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        n_query += len(query)
        state_losses.append(float(state.detach().item()))
        term_losses.append(float(term_loss.detach().item()))
    if frozen_parameter_digest(model) != frozen_before:
        raise RuntimeError("frozen dynamics or normalization changed during history updates")
    if n_nonempty and max(grad_encoder) <= 0.0:
        raise RuntimeError("history encoder received no gradient on nonempty updates")
    if n_nonempty and max(grad_film) <= 0.0:
        raise RuntimeError("FiLM received no gradient on nonempty history updates")
    model.clear_context()
    model.encoder.eval()
    model.net.eval()
    return {
        "optimizer_updates": len(rows),
        "query_examples": int(n_query),
        "support_examples": int(n_support),
        "support_encodes": int(n_nonempty),
        "nonempty_updates": int(n_nonempty),
        "query_indices": query_indices,
        "mean_encoder_grad_norm": float(np.mean(grad_encoder)) if grad_encoder else 0.0,
        "mean_film_grad_norm": float(np.mean(grad_film)) if grad_film else 0.0,
        "max_encoder_grad_norm": float(max(grad_encoder)) if grad_encoder else 0.0,
        "max_film_grad_norm": float(max(grad_film)) if grad_film else 0.0,
        "mean_state_loss": float(np.mean(state_losses)) if state_losses else 0.0,
        "mean_term_loss": float(np.mean(term_losses)) if term_losses else 0.0,
        "frozen_sha256": frozen_before,
    }


def run_constant_updates(
    model: ContextWorldModel,
    vector: torch.nn.Parameter,
    opt: torch.optim.Optimizer,
    tasks: list[TransitionDataset],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Same query rows as history adaptation. Nonempty steps use one shared vector; empty steps use zero."""
    if any(param.requires_grad for param in model.encoder.parameters()):
        raise RuntimeError("constant updates must keep the encoder frozen")
    film_params = [param for name, param in model.net.named_parameters() if name.startswith("film.")]
    opt_ids = {id(param) for param in opt.param_groups[0]["params"]}
    if opt_ids != {id(vector), *[id(param) for param in film_params]}:
        raise RuntimeError("constant optimizer parameters are not exactly the vector and FiLM")
    frozen_before = frozen_parameter_digest(model)
    encoder_before = torch.cat([param.detach().flatten().clone() for param in model.encoder.parameters()])
    grad_vector: list[float] = []
    grad_film: list[float] = []
    state_losses: list[float] = []
    term_losses: list[float] = []
    query_indices: list[list[int]] = []
    n_query = 0
    n_support_skipped = 0
    n_nonempty = 0
    for row in rows:
        query, take = _consume_row(model, tasks, row)
        query_indices.append(np.asarray(row["query_index"], dtype=np.int64).tolist())
        model.net.train()
        if take.size == 0:
            z = torch.zeros(model.context_dim())
        else:
            z = vector
            n_support_skipped += int(take.size)
            n_nonempty += 1
        state, term_loss, loss = model.query_terms(query.obs, query.action, query.next_obs, query.terminated, z)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        for param in model.encoder.parameters():
            if param.grad is not None:
                raise RuntimeError("history encoder received a gradient during constant adaptation")
        grad_vector.append(float(vector.grad.detach().norm().item()) if vector.grad is not None else 0.0)
        grad_film.append(_grad_norm(film_params))
        nn.utils.clip_grad_norm_(opt.param_groups[0]["params"], 1.0)
        opt.step()
        n_query += len(query)
        state_losses.append(float(state.detach().item()))
        term_losses.append(float(term_loss.detach().item()))
    encoder_after = torch.cat([param.detach().flatten() for param in model.encoder.parameters()])
    if not torch.equal(encoder_before, encoder_after):
        raise RuntimeError("history encoder weights changed during constant adaptation")
    if frozen_parameter_digest(model) != frozen_before:
        raise RuntimeError("frozen dynamics or normalization changed during constant updates")
    if n_nonempty and max(grad_vector) <= 0.0:
        raise RuntimeError("constant vector received no gradient on nonempty updates")
    if n_nonempty and max(grad_film) <= 0.0:
        raise RuntimeError("FiLM received no gradient on nonempty constant updates")
    model.clear_context()
    model.encoder.eval()
    model.net.eval()
    return {
        "optimizer_updates": len(rows),
        "query_examples": int(n_query),
        "support_examples": 0,
        "support_rows_not_encoded": int(n_support_skipped),
        "support_encodes": 0,
        "nonempty_updates": int(n_nonempty),
        "query_indices": query_indices,
        "mean_vector_grad_norm": float(np.mean(grad_vector)) if grad_vector else 0.0,
        "mean_film_grad_norm": float(np.mean(grad_film)) if grad_film else 0.0,
        "max_vector_grad_norm": float(max(grad_vector)) if grad_vector else 0.0,
        "max_film_grad_norm": float(max(grad_film)) if grad_film else 0.0,
        "mean_state_loss": float(np.mean(state_losses)) if state_losses else 0.0,
        "mean_term_loss": float(np.mean(term_losses)) if term_losses else 0.0,
        "frozen_sha256": frozen_before,
    }


def selection_schema(seed_ids: list[int], task_ids: list[str], updates: list[int]) -> dict[str, Any]:
    labels = [f"history_u{int(step)}" for step in updates] + [f"constant_u{int(step)}" for step in updates]
    conditions = {f"history_u{int(step)}": ["real", "zero", "wrong"] for step in updates}
    conditions.update({f"constant_u{int(step)}": ["constant"] for step in updates})
    return {
        "seed_ids": [int(s) for s in seed_ids],
        "task_ids": list(task_ids),
        "labels": labels,
        "conditions_by_label": conditions,
        "metrics": list(METRICS),
        "horizons": list(HORIZONS),
        "per_dim": 3,
    }


def audit_schema(seed_ids: list[int], task_ids: list[str]) -> dict[str, Any]:
    conditions = {
        "history_selected": ["real", "zero", "wrong"],
        "starting": ["real", "zero", "wrong"],
        "constant_selected": ["constant"],
        "mlp_reference": ["mlp"],
    }
    return {
        "seed_ids": [int(s) for s in seed_ids],
        "task_ids": list(task_ids),
        "labels": list(AUDIT_LABELS),
        "conditions_by_label": conditions,
        "metrics": list(METRICS),
        "horizons": list(HORIZONS),
        "per_dim": 3,
    }


def context_audit_entries(history_updates: int, constant_updates: int) -> list[dict[str, Any]]:
    """Context audit models. The MLP update count is intentionally absent."""
    return [
        {"label": "history_selected", "updates": int(history_updates), "kind": "history"},
        {"label": "starting", "updates": 0, "kind": "history"},
        {"label": "constant_selected", "updates": int(constant_updates), "kind": "constant"},
    ]


def mlp_audit_entries(mlp_updates: int = 1000) -> list[dict[str, Any]]:
    return [{"label": "mlp_reference", "updates": int(mlp_updates), "kind": "mlp"}]


def slim_cell(prediction: dict[str, Any], horizons: list[int]) -> dict[str, Any]:
    return {
        "mae": float(prediction["mae"]),
        "rmse": float(prediction["rmse"]),
        "angvel_mae": float(prediction["angvel_mae"]),
        "mae_per_dim": [float(x) for x in prediction["mae_per_dim"]],
        "rollout_mae": {str(h): float(prediction["rollout_mae"][str(h)]) for h in horizons},
    }


def records_from_cells(per_seed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for seed in per_seed:
        for task_id, task in seed["tasks"].items():
            for label, conditions in task["labels"].items():
                for condition, cell in conditions.items():
                    records.append({"seed": int(seed["model_seed"]), "task": str(task_id), "label": str(label), "condition": str(condition), **cell})
    return records


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


def _load_prior_selection() -> dict[str, Any]:
    if not PRIOR_SELECTION.is_file():
        raise RuntimeError(f"missing prior selection artifact {PRIOR_SELECTION}")
    return json.loads(PRIOR_SELECTION.read_text())


def reproduce_prior_checkpoint(seed: int, kind: str, updates: int, expected: str) -> Path:
    """Retrain one recorded optimization checkpoint and keep it only if the file hash matches.

    A hash mismatch deletes the new file. Newly trained weights are not substituted.
    """
    from nexus.world.context_model import context_optimizer, run_context_updates
    from nexus.world.context_pilot import _fit_rms
    from nexus.world.data import concat_datasets
    from nexus.world.train import train_mlp_updates

    path = PRIOR_CHECKPOINT_DIR / f"seed{int(seed)}_{kind}_u{int(updates)}.pt"
    specs = pendulum_context_train()[:8]
    tasks = [
        _collect(spec, 400, env0=1000 + 100 * int(seed) + 10 * i, base=191_000 + 50 * int(seed) + 9 * i)
        for i, spec in enumerate(specs)
    ]
    rms = _fit_rms(tasks)
    if kind == "context":
        model = ContextWorldModel.create(3, 3, seed=V089C_TRAIN_SEED + 17 * int(seed))
        model.copy_rms(rms)
        opt = context_optimizer(model, lr=1e-3)
        schedule = make_context_schedule(tasks, updates=3000, seed=V089C_TRAIN_SEED + 31 * int(seed), batch=64, empty_prob=0.2)
        run_context_updates(model, opt, tasks, schedule, support_mode="fixed")
        payload = {
            "encoder": {k: v.detach().cpu().clone() for k, v in model.encoder.state_dict().items()},
            "net": {k: v.detach().cpu().clone() for k, v in model.net.state_dict().items()},
            "obs_rms": rms.state_dict(),
        }
    elif kind == "mlp":
        pooled = concat_datasets(*tasks, task_id="context_source_pool")
        _live, _opt, snaps, _hist = train_mlp_updates(
            pooled, updates=3000, snapshot_at=(300, 1000, 3000), seed=V089C_TRAIN_SEED + int(seed),
            batch_size=64, lr=1e-3, hidden=(64, 64), obs_rms=rms,
        )
        payload = {"net": snaps[int(updates)], "obs_rms": rms.state_dict()}
    else:
        raise RuntimeError(f"cannot reproduce checkpoint kind {kind}")
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    if _sha256(path) != expected:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"reproduced {path} does not match the recorded hash; refusing to substitute new weights")
    return path


def require_prior_checkpoint(seed: int, kind: str, updates: int, expected: str) -> Path:
    path = PRIOR_CHECKPOINT_DIR / f"seed{seed}_{kind}_u{updates}.pt"
    if not path.is_file():
        return reproduce_prior_checkpoint(seed, kind, updates, expected)
    got = _sha256(path)
    if got != expected:
        raise RuntimeError(f"checkpoint hash mismatch for {path}: {got} != {expected}")
    return path


def load_context_checkpoint(path: Path) -> ContextWorldModel:
    blob = torch.load(path, map_location="cpu", weights_only=False)
    model = ContextWorldModel.create(3, 3, seed=0)
    model.encoder.load_state_dict(blob["encoder"])
    model.net.load_state_dict(blob["net"])
    model.obs_rms.load_state_dict(blob["obs_rms"])
    model.clear_context()
    return model


def load_mlp_checkpoint(path: Path, hidden: tuple[int, ...]) -> WorldModel:
    blob = torch.load(path, map_location="cpu", weights_only=False)
    model = WorldModel.create(3, 3, kind="residual", hidden=tuple(hidden), seed=0, arch="mlp")
    model.net.load_state_dict(blob["net"])
    model.obs_rms.load_state_dict(blob["obs_rms"])
    model.net.eval()
    return model


def _save_torch(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    return _sha256(path)


def _flat(params: list[torch.nn.Parameter]) -> torch.Tensor:
    return torch.cat([param.detach().flatten().cpu() for param in params])


def _score_history(model: ContextWorldModel, support: TransitionDataset, donor: TransitionDataset, query: TransitionDataset, budget: int, horizons: list[int], angvel_index: int) -> dict[str, dict[str, Any]]:
    bundle = _context_bundle(model, support, donor, query, budget, horizons, angvel_index)
    return {name: slim_cell(bundle[name], horizons) for name in ("real", "zero", "wrong")}


def _score_constant(model: ContextWorldModel, vector: torch.Tensor, query: TransitionDataset, horizons: list[int], angvel_index: int) -> dict[str, Any]:
    probe = model.clone_frozen()
    probe.z = vector.detach().clone()
    return slim_cell(_episode_prediction(probe, query, horizons, angvel_index), horizons)


def _score_mlp(model: WorldModel, query: TransitionDataset, horizons: list[int], angvel_index: int) -> dict[str, Any]:
    return slim_cell(_episode_prediction(model, query, horizons, angvel_index), horizons)


def build_selected_checkpoints(
    *,
    history_updates: int,
    constant_updates: int,
    mlp_updates: int,
    seeds: list[int],
    checkpoint_sha256: dict[str, str],
) -> dict[str, Any]:
    """Audit allow-list. Unselected history checkpoints are not included, even at the MLP update count."""
    entries = context_audit_entries(history_updates, constant_updates) + mlp_audit_entries(mlp_updates)
    selected: dict[str, Any] = {}
    for entry in entries:
        paths: dict[str, str] = {}
        hashes: dict[str, str] = {}
        for seed in seeds:
            if entry["kind"] == "mlp":
                path = PRIOR_CHECKPOINT_DIR / f"seed{seed}_mlp_u{int(entry['updates'])}.pt"
            elif entry["kind"] == "constant":
                path = CHECKPOINT_DIR / f"seed{seed}_constant_u{int(entry['updates'])}.pt"
            else:
                path = CHECKPOINT_DIR / f"seed{seed}_history_u{int(entry['updates'])}.pt"
            key = str(path)
            if key not in checkpoint_sha256:
                raise RuntimeError(f"selected checkpoint {key} has no recorded hash")
            paths[str(seed)] = key
            hashes[str(seed)] = checkpoint_sha256[key]
        selected[entry["label"]] = {"updates": int(entry["updates"]), "kind": entry["kind"], "paths": paths, "sha256": hashes}
    if set(selected) != set(AUDIT_LABELS):
        raise RuntimeError("audit selection is not exactly the four allowed models")
    return selected


def assert_frozen_audit_allowed(selection_path: str | Path, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(selection_path)
    if not path.is_file():
        raise RuntimeError("source audit is blocked until a selection manifest is saved")
    payload = json.loads(path.read_text())
    record = payload.get("selection_record")
    if not isinstance(record, dict) or record.get("selection_recorded") is not True:
        raise RuntimeError("source audit is blocked until checkpoint selection is recorded")
    if payload.get("smoke") is True or record.get("smoke") is True or record.get("incomplete") is True:
        raise RuntimeError("source audit is blocked for a smoke or incomplete selection")
    selected = record.get("selected_checkpoints")
    if not isinstance(selected, dict) or set(selected) != set(AUDIT_LABELS):
        raise RuntimeError("source audit is blocked until the four selected checkpoints and their hashes are saved")
    for label, entry in selected.items():
        if "updates" not in entry or "paths" not in entry or "sha256" not in entry:
            raise RuntimeError(f"source audit is blocked because {label} is missing a checkpoint id or hash")
        for seed, digest in entry["sha256"].items():
            file_path = Path(entry["paths"][seed])
            if not file_path.is_file() or _sha256(file_path) != digest:
                raise RuntimeError(f"source audit is blocked because {label} seed {seed} hash does not match the saved file")
    locked = cfg if cfg is not None else load_frozen_config()
    task_ids = [spec.task_id for spec in pendulum_context_train()[: int(locked["n_source_tasks"])]]
    schema = selection_schema(list(range(int(locked["n_seeds"]))), task_ids, [int(u) for u in locked["additional_updates"]])
    report = _apply_schema(list(payload.get("raw_records") or []), schema)
    if not report["declared_complete"]:
        raise RuntimeError("source audit is blocked because the saved selection cells are incomplete")
    if record.get("frozen_hashes_unchanged") is not True:
        raise RuntimeError("source audit is blocked because frozen parameters were not certified unchanged")
    return payload


def frozen_screen(per_seed: list[dict[str, float]], *, improvement: float = 0.05, min_positive_seeds: int = 2, max_worsening: float = 0.05, frozen_ok: bool = True, complete: bool = True) -> dict[str, Any]:
    """Development screen on a fresh source audit. Not a proof of generalization."""
    if len(per_seed) < 1:
        return {"pass": False, "reason": "no audit seeds"}

    def mean(key: str) -> float:
        return float(np.mean([row[key] for row in per_seed]))

    real = mean("angvel_real")
    zero = mean("angvel_zero")
    wrong = mean("angvel_wrong")
    constant = mean("angvel_constant")
    start = mean("angvel_start")
    positive = 0
    for row in per_seed:
        if (row["angvel_zero"] - row["angvel_real"]) > 0 and (row["angvel_wrong"] - row["angvel_real"]) > 0 and (row["angvel_constant"] - row["angvel_real"]) > 0:
            positive += 1
    beats_zero_wrong = real <= (1.0 - improvement) * zero and real <= (1.0 - improvement) * wrong
    beats_constant = real <= (1.0 - improvement) * constant
    harm_ok = mean("mae_real") <= (1.0 + max_worsening) * mean("mae_zero") and mean("h16_real") <= (1.0 + max_worsening) * mean("h16_zero")
    start_ok = real <= start
    passed = bool(beats_zero_wrong and beats_constant and positive >= min_positive_seeds and harm_ok and start_ok and frozen_ok and complete)
    return {
        "pass": passed,
        "angvel_real": real,
        "angvel_zero": zero,
        "angvel_wrong": wrong,
        "angvel_constant": constant,
        "angvel_start": start,
        "angvel_mlp": mean("angvel_mlp") if "angvel_mlp" in per_seed[0] else None,
        "positive_seeds": positive,
        "beats_zero_and_wrong": bool(beats_zero_wrong),
        "beats_constant": bool(beats_constant),
        "harm_ok": bool(harm_ok),
        "start_ok": bool(start_ok),
        "frozen_ok": bool(frozen_ok),
        "complete": bool(complete),
        "generic_recalibration": bool(beats_zero_wrong and not beats_constant),
        "thresholds": {"improvement": improvement, "min_positive_seeds": min_positive_seeds, "max_worsening": max_worsening},
    }


def classify_frozen(history_updates: int | None, screen: dict[str, Any]) -> dict[str, Any]:
    real = screen.get("angvel_real")
    mlp = screen.get("angvel_mlp")
    behind_mlp = bool(real is not None and mlp is not None and float(real) > float(mlp))
    if history_updates is None:
        label = "incomplete"
    elif int(history_updates) == 0:
        label = "checkpoint_0_selected"
    elif screen.get("generic_recalibration"):
        label = "generic_recalibration"
    elif screen.get("pass"):
        label = "task_specific"
    else:
        label = "absent"
    training_claimed = bool(screen.get("pass") and history_updates not in (None, 0) and label == "task_specific")
    return {
        "label": label,
        "history_useful": bool(screen.get("pass") and label == "task_specific"),
        "additional_training_helped": training_claimed,
        "generic_recalibration": label == "generic_recalibration",
        "behind_mlp": behind_mlp,
        "note": "Checkpoint 0 means additional frozen-trunk training is not claimed to have helped." if label == "checkpoint_0_selected" else "",
    }


def _mean_condition(tasks: dict[str, Any], label: str, condition: str, key: str) -> float:
    values = []
    for task in tasks.values():
        cell = task["labels"][label][condition]
        if key == "h16":
            values.append(float(cell["rollout_mae"]["16"]))
        else:
            values.append(float(cell[key]))
    return float(np.mean(values)) if values else float("nan")


def _interval_rows(per_seed: list[dict[str, Any]], history_label: str, constant_label: str) -> list[dict[str, float]]:
    rows = []
    for seed in per_seed:
        tasks = seed["tasks"]
        rows.append(
            {
                "angvel_real": _mean_condition(tasks, history_label, "real", "angvel_mae"),
                "angvel_zero": _mean_condition(tasks, history_label, "zero", "angvel_mae"),
                "angvel_wrong": _mean_condition(tasks, history_label, "wrong", "angvel_mae"),
                "angvel_constant": _mean_condition(tasks, constant_label, "constant", "angvel_mae"),
                "angvel_start": _mean_condition(tasks, "starting", "real", "angvel_mae"),
                "angvel_mlp": _mean_condition(tasks, "mlp_reference", "mlp", "angvel_mae"),
                "mae_real": _mean_condition(tasks, history_label, "real", "mae"),
                "mae_zero": _mean_condition(tasks, history_label, "zero", "mae"),
                "h16_real": _mean_condition(tasks, history_label, "real", "h16"),
                "h16_zero": _mean_condition(tasks, history_label, "zero", "h16"),
            }
        )
    return rows


def _intervals(rows: list[dict[str, float]]) -> dict[str, Any]:
    keys = (
        "angvel_real",
        "angvel_zero",
        "angvel_wrong",
        "angvel_constant",
        "angvel_start",
        "angvel_mlp",
        "mae_real",
        "mae_zero",
        "h16_real",
        "h16_zero",
    )
    out: dict[str, Any] = {}
    for key in keys:
        values = [float(row[key]) for row in rows]
        out[key] = seed_level_ci(values) if len(values) >= 2 else {"n": len(values), "mean": float(np.mean(values)) if values else None}
    if rows:
        for name, left, right in (
            ("angvel_zero_minus_real", "angvel_zero", "angvel_real"),
            ("angvel_wrong_minus_real", "angvel_wrong", "angvel_real"),
            ("angvel_constant_minus_real", "angvel_constant", "angvel_real"),
            ("angvel_start_minus_real", "angvel_start", "angvel_real"),
        ):
            deltas = [row[left] - row[right] for row in rows]
            out[name] = seed_level_ci(deltas) if len(deltas) >= 2 else {"n": len(deltas), "mean": float(np.mean(deltas))}
    return out


def _dataset_seeds(ds: TransitionDataset) -> set[int]:
    return {int(s) for s in np.unique(ds.seed)}


def run_frozen_dynamics(
    *,
    smoke: bool = False,
    config_path: str | Path = CONFIG_PATH,
    selection_path: str | Path | None = None,
    audit_path: str | Path | None = None,
    plot_path: str | Path | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cfg = load_frozen_config(config_path)
    updates = [int(u) for u in cfg["additional_updates"]]
    total = int(cfg["total_additional_updates"])
    n_seeds = int(cfg["n_seeds"])
    n_tasks = int(cfg["n_source_tasks"])
    per_task = int(cfg["source_per_task"])
    if smoke:
        updates = [0, 2, 4]
        total = 4
        n_seeds = 1
        n_tasks = 2
        per_task = 220
    assert_source_splits_disjoint(cfg, n_tasks=n_tasks if not smoke else None)
    deadline = t0 + float(cfg["time_limit_s"])
    horizons = [int(h) for h in cfg["horizons"]]
    budget = int(cfg["support_budget"]) if not smoke else 32
    angvel_index = int(cfg["angular_velocity_index"])
    specs = pendulum_context_train()[:n_tasks]
    task_ids = [spec.task_id for spec in specs]
    prior = _load_prior_selection()
    prior_hashes = prior["checkpoint_sha256"]
    incomplete = False

    def timed_out() -> bool:
        return time.perf_counter() > deadline

    resources = {
        "source_train_env": 0,
        "selection_support_env": 0,
        "selection_query_env": 0,
        "audit_support_env": 0,
        "audit_query_env": 0,
        "history_wall_s": 0.0,
        "constant_wall_s": 0.0,
        "history_support_examples": 0,
        "history_query_examples": 0,
        "constant_support_encodes": 0,
        "constant_query_examples": 0,
        "audit_collected": False,
    }
    data_hashes: dict[str, Any] = {}

    def grab(spec: Any, n: int, env0: int, base: int, bucket: str) -> TransitionDataset:
        ds = _collect(spec, n, env0=env0, base=base)
        got = _dataset_seeds(ds)
        expected = planned_env_seeds(n, env0)
        if got != expected:
            raise RuntimeError(f"collect seeds for env0={env0} n={n} were {sorted(got)} not {sorted(expected)}")
        resources[bucket] += int(ds.env_interactions)
        return ds

    selection_support = [grab(spec, 128 if not smoke else 32, 8000 + 10 * i, 196_000 + i, "selection_support_env") for i, spec in enumerate(specs)]
    selection_query = [
        complete_episodes(grab(spec, 400 if not smoke else 220, 14000 + 10 * i, 197_000 + i, "selection_query_env"), 16)
        for i, spec in enumerate(specs)
    ]
    data_hashes["selection_support"] = [prefix_hash(ds, len(ds)) for ds in selection_support]
    data_hashes["selection_query"] = [prefix_hash(ds, len(ds)) for ds in selection_query]
    if not smoke:
        if data_hashes["selection_support"] != prior["data_hashes"]["selection_support"][:n_tasks]:
            raise RuntimeError("selection support does not match the inspected optimization split")
        if data_hashes["selection_query"] != prior["data_hashes"]["selection_query"][:n_tasks]:
            raise RuntimeError("selection query does not match the inspected optimization split")

    per_seed: list[dict[str, Any]] = []
    checkpoint_files: dict[str, str] = {}
    for seed in range(n_seeds):
        if timed_out():
            incomplete = True
            break
        context_key = f"artifacts/context_optimization_checkpoints/seed{seed}_context_u{int(cfg['prior_context_updates'])}.pt"
        mlp_key = f"artifacts/context_optimization_checkpoints/seed{seed}_mlp_u{int(cfg['mlp_reference_updates'])}.pt"
        context_path = require_prior_checkpoint(seed, "context", int(cfg["prior_context_updates"]), prior_hashes[context_key])
        mlp_path = require_prior_checkpoint(seed, "mlp", int(cfg["mlp_reference_updates"]), prior_hashes[mlp_key])
        checkpoint_files[str(mlp_path)] = prior_hashes[mlp_key]
        tasks = [
            grab(spec, per_task, 1000 + 100 * seed + 10 * i, 191_000 + 50 * seed + 9 * i, "source_train_env")
            for i, spec in enumerate(specs)
        ]
        data_hashes[f"seed{seed}_train"] = [prefix_hash(ds, len(ds)) for ds in tasks]
        if not smoke and data_hashes[f"seed{seed}_train"] != prior["data_hashes"][f"seed{seed}_train"]:
            raise RuntimeError(f"source training hash mismatch for seed {seed}")
        assert_disjoint_seeds(*tasks, *selection_support, *selection_query)
        starting = load_context_checkpoint(context_path)
        frozen_digest = frozen_parameter_digest(starting)
        history = starting.clone_trainable()
        constant_model = starting.clone_trainable()
        freeze_shared_dynamics(history)
        init_vector = mean_training_support_context(starting, tasks, V089C_TRAIN_SEED + int(cfg["init_seed_offset"]) + int(seed))
        vector = nn.Parameter(init_vector.clone())
        freeze_shared_dynamics(constant_model)
        for param in constant_model.encoder.parameters():
            param.requires_grad_(False)
        if not torch.equal(history.net.film.weight.detach(), constant_model.net.film.weight.detach()):
            raise RuntimeError("history and constant models did not start from the same FiLM weights")
        history_names = trainable_names(history)
        constant_names = trainable_names(constant_model, vector)
        if not any(name.startswith("encoder.") for name in history_names) or not any(name.startswith("net.film.") for name in history_names):
            raise RuntimeError(f"history trainable set is wrong: {history_names}")
        if any(name.startswith("encoder.") for name in constant_names) or "constant_vector" not in constant_names:
            raise RuntimeError(f"constant trainable set is wrong: {constant_names}")
        schedule = make_context_schedule(
            tasks,
            updates=total,
            seed=V089C_TRAIN_SEED + 31 * int(seed),
            batch=int(cfg["batch"]),
            empty_prob=float(cfg["empty_prob"]),
        )
        history_opt = history_optimizer(history, lr=float(cfg["lr"]))
        constant_opt = constant_optimizer(constant_model, vector, lr=float(cfg["lr"]))
        encoder_start = _flat(list(history.encoder.parameters()))
        film_start = _flat([param for name, param in history.net.named_parameters() if name.startswith("film.")])
        vector_start = vector.detach().clone()
        history_snaps: dict[int, dict[str, Any]] = {}
        constant_snaps: dict[int, dict[str, Any]] = {}
        history_logs: dict[str, Any] = {}
        constant_logs: dict[str, Any] = {}
        cursor = 0
        t_hist = time.perf_counter()
        t_const = 0.0
        for target in updates:
            if target > cursor:
                h_log = run_history_updates(history, history_opt, tasks, schedule[cursor:target])
                t1 = time.perf_counter()
                c_log = run_constant_updates(constant_model, vector, constant_opt, tasks, schedule[cursor:target])
                t_const += time.perf_counter() - t1
                if h_log["query_indices"] != c_log["query_indices"]:
                    raise RuntimeError("history and constant adaptation consumed different query minibatches")
                resources["history_support_examples"] += int(h_log["support_examples"])
                resources["history_query_examples"] += int(h_log["query_examples"])
                resources["constant_query_examples"] += int(c_log["query_examples"])
                history_logs[str(target)] = {k: v for k, v in h_log.items() if k != "query_indices"}
                constant_logs[str(target)] = {k: v for k, v in c_log.items() if k != "query_indices"}
            else:
                history_logs[str(target)] = {"optimizer_updates": 0, "support_examples": 0, "query_examples": 0, "support_encodes": 0}
                constant_logs[str(target)] = {"optimizer_updates": 0, "support_examples": 0, "query_examples": 0, "support_encodes": 0}
            if frozen_parameter_digest(history) != frozen_digest or frozen_parameter_digest(constant_model) != frozen_digest:
                raise RuntimeError("frozen parameters diverged from the starting checkpoint")
            history_snaps[target] = {
                "encoder": {k: v.detach().cpu().clone() for k, v in history.encoder.state_dict().items()},
                "net": {k: v.detach().cpu().clone() for k, v in history.net.state_dict().items()},
                "optimizer": copy.deepcopy(history_opt.state_dict()),
            }
            constant_snaps[target] = {
                "encoder": {k: v.detach().cpu().clone() for k, v in constant_model.encoder.state_dict().items()},
                "net": {k: v.detach().cpu().clone() for k, v in constant_model.net.state_dict().items()},
                "vector": vector.detach().cpu().clone(),
                "optimizer": copy.deepcopy(constant_opt.state_dict()),
            }
            history_logs[str(target)]["encoder_l2_from_start"] = float(torch.linalg.vector_norm(_flat(list(history.encoder.parameters())) - encoder_start).item())
            history_logs[str(target)]["film_l2_from_start"] = float(
                torch.linalg.vector_norm(_flat([param for name, param in history.net.named_parameters() if name.startswith("film.")]) - film_start).item()
            )
            constant_logs[str(target)]["vector_l2_from_start"] = float(torch.linalg.vector_norm(vector.detach() - vector_start).item())
            constant_logs[str(target)]["film_l2_from_start"] = float(
                torch.linalg.vector_norm(_flat([param for name, param in constant_model.net.named_parameters() if name.startswith("film.")]) - film_start).item()
            )
            cursor = target
        resources["history_wall_s"] += time.perf_counter() - t_hist - t_const
        resources["constant_wall_s"] += t_const
        for step, snap in history_snaps.items():
            path = CHECKPOINT_DIR / f"seed{seed}_history_u{step}.pt"
            checkpoint_files[str(path)] = _save_torch(
                path,
                {"encoder": snap["encoder"], "net": snap["net"], "obs_rms": history.obs_rms.state_dict(), "frozen_sha256": frozen_digest, "updates": int(step), "kind": "history"},
            )
            opt_path = CHECKPOINT_DIR / f"seed{seed}_history_opt_u{step}.pt"
            checkpoint_files[str(opt_path)] = _save_torch(opt_path, {"optimizer": snap["optimizer"]})
        for step, snap in constant_snaps.items():
            path = CHECKPOINT_DIR / f"seed{seed}_constant_u{step}.pt"
            checkpoint_files[str(path)] = _save_torch(
                path,
                {
                    "encoder": snap["encoder"],
                    "net": snap["net"],
                    "obs_rms": constant_model.obs_rms.state_dict(),
                    "constant_vector": snap["vector"],
                    "frozen_sha256": frozen_digest,
                    "updates": int(step),
                    "kind": "constant",
                },
            )
            opt_path = CHECKPOINT_DIR / f"seed{seed}_constant_opt_u{step}.pt"
            checkpoint_files[str(opt_path)] = _save_torch(opt_path, {"optimizer": snap["optimizer"]})

        def history_at(step: int) -> ContextWorldModel:
            model = ContextWorldModel.create(3, 3, seed=0)
            model.encoder.load_state_dict(history_snaps[step]["encoder"])
            model.net.load_state_dict(history_snaps[step]["net"])
            model.copy_rms(history.obs_rms)
            return model.clone_frozen()

        def constant_at(step: int) -> tuple[ContextWorldModel, torch.Tensor]:
            model = ContextWorldModel.create(3, 3, seed=0)
            model.encoder.load_state_dict(constant_snaps[step]["encoder"])
            model.net.load_state_dict(constant_snaps[step]["net"])
            model.copy_rms(constant_model.obs_rms)
            return model.clone_frozen(), constant_snaps[step]["vector"].clone()

        donors = [selection_support[(i + 1) % len(selection_support)] for i in range(len(specs))]
        task_rows: dict[str, Any] = {}
        for i, spec in enumerate(specs):
            labels: dict[str, Any] = {}
            for step in updates:
                if timed_out():
                    incomplete = True
                    break
                labels[f"history_u{step}"] = _score_history(history_at(step), selection_support[i], donors[i], selection_query[i], budget, horizons, angvel_index)
                held, held_vector = constant_at(step)
                labels[f"constant_u{step}"] = {"constant": _score_constant(held, held_vector, selection_query[i], horizons, angvel_index)}
            task_rows[spec.task_id] = {"params": dict(spec.params), "donor_task": specs[(i + 1) % len(specs)].task_id, "labels": labels}
        per_seed.append(
            {
                "model_seed": seed,
                "tasks": task_rows,
                "history_logs": history_logs,
                "constant_logs": constant_logs,
                "frozen_sha256": frozen_digest,
                "prior_context_sha256": prior_hashes[context_key],
                "prior_mlp_sha256": prior_hashes[mlp_key],
                "trainable_history": history_names,
                "trainable_constant": constant_names,
                "n_trainable_history": int(
                    sum(param.numel() for param in history.encoder.parameters())
                    + sum(param.numel() for name, param in history.net.named_parameters() if name.startswith("film."))
                ),
                "n_trainable_constant": int(vector.numel() + sum(param.numel() for name, param in constant_model.net.named_parameters() if name.startswith("film."))),
                "n_frozen": int(sum(param.numel() for name, param in history.net.named_parameters() if not name.startswith("film."))),
                "n_context": int(history.n_parameters()),
            }
        )
        print(f"frozen_dynamics seed={seed} smoke={smoke}", flush=True)
        if incomplete:
            break

    schema = selection_schema([seed["model_seed"] for seed in per_seed], task_ids, updates) if per_seed else selection_schema([], [], updates)
    raw_records = records_from_cells(per_seed)
    completeness = _apply_schema(raw_records, schema) if per_seed and not incomplete else {"declared_complete": False, "failures": ["smoke or incomplete or missing selection"], "n_expected": 0, "n_records": 0}
    history_scores: dict[int, float] = {}
    constant_scores: dict[int, float] = {}
    if completeness["declared_complete"]:
        for step in updates:
            history_scores[step] = float(np.mean([_mean_condition(seed["tasks"], f"history_u{step}", "real", "angvel_mae") for seed in per_seed]))
            constant_scores[step] = float(np.mean([_mean_condition(seed["tasks"], f"constant_u{step}", "constant", "angvel_mae") for seed in per_seed]))
    history_chosen = choose_checkpoint(history_scores) if history_scores and all(np.isfinite(list(history_scores.values()))) else None
    constant_chosen = choose_checkpoint(constant_scores) if constant_scores and all(np.isfinite(list(constant_scores.values()))) else None
    head = _git_meta()
    sha = str(head.get("revision") or "")
    source_status = inspect_source_tree(sha) if sha else {"source_dirty": True}
    frozen_ok = bool(per_seed) and all(seed["frozen_sha256"] for seed in per_seed) and not incomplete
    selected_checkpoints = None
    if history_chosen is not None and constant_chosen is not None and not smoke and not incomplete and completeness["declared_complete"]:
        seeds = [int(seed["model_seed"]) for seed in per_seed]
        selected_checkpoints = build_selected_checkpoints(
            history_updates=int(history_chosen),
            constant_updates=int(constant_chosen),
            mlp_updates=int(cfg["mlp_reference_updates"]),
            seeds=seeds,
            checkpoint_sha256=checkpoint_files,
        )
    selection_record = {
        "selection_recorded": bool(selected_checkpoints) and frozen_ok and not smoke,
        "history_updates": history_chosen,
        "constant_updates": constant_chosen,
        "history_rule": "lowest mean selection-set real-context angular-velocity MAE across seeds; ties prefer fewer updates; checkpoint 0 is eligible",
        "constant_rule": "same angular-velocity criterion on the constant-context predictions, chosen independently of the history checkpoint",
        "history_scores_angvel_mae": {str(k): v for k, v in history_scores.items()},
        "constant_scores_angvel_mae": {str(k): v for k, v in constant_scores.items()},
        "selected_checkpoints": selected_checkpoints,
        "frozen_hashes_unchanged": bool(frozen_ok and not smoke),
        "mlp_reference_updates": int(cfg["mlp_reference_updates"]),
        "smoke": bool(smoke),
        "incomplete": bool(incomplete) or bool(smoke),
    }
    selection_payload = {
        "protocol": _protocol(cfg, smoke, sha, source_status, updates, total, n_seeds),
        "selection_record": selection_record,
        "schema": schema,
        "raw_records": raw_records,
        "completeness": completeness,
        "data_hashes": data_hashes,
        "checkpoint_sha256": checkpoint_files,
        "checkpoint_dir": str(CHECKPOINT_DIR),
        "registered_audit_seeds": {
            "support_env0": int(cfg["audit_support_env0"]),
            "query_env0": int(cfg["audit_query_env0"]),
            "support_base": int(cfg["audit_support_base"]),
            "query_base": int(cfg["audit_query_base"]),
            "note": "Registered before training. Predictions on these episodes are not computed until this selection file is saved.",
        },
        "resources": dict(resources),
        "per_seed": [{k: v for k, v in seed.items() if k != "tasks"} | {"task_ids": list(seed["tasks"])} for seed in per_seed],
        "summary": _selection_summary(per_seed, updates),
        "parameter_counts": {
            "history_trainable": None if not per_seed else per_seed[0]["n_trainable_history"],
            "constant_trainable": None if not per_seed else per_seed[0]["n_trainable_constant"],
            "frozen": None if not per_seed else per_seed[0]["n_frozen"],
            "context_total": None if not per_seed else per_seed[0]["n_context"],
        },
        "wall_clock_s": time.perf_counter() - t0,
        "audit_evaluated": False,
        "confirm_evaluated": False,
        "control_evaluated": False,
        "is_agi": False,
        "smoke": bool(smoke),
    }
    if not selection_record["selection_recorded"]:
        selection_record["selected_checkpoints"] = None
        selection_payload["selection_record"] = selection_record
    if selection_path is not None:
        Path(selection_path).parent.mkdir(parents=True, exist_ok=True)
        Path(selection_path).write_text(dumps_strict(selection_payload))
    if plot_path is not None and per_seed and not incomplete:
        _plot(Path(plot_path), per_seed, updates)

    audit_payload = None
    if selection_record["selection_recorded"] and selection_path is not None and not timed_out():
        saved = assert_frozen_audit_allowed(selection_path, cfg)
        audit_payload = _run_audit(
            saved,
            cfg,
            specs,
            selection_support,
            selection_query,
            horizons,
            budget,
            angvel_index,
            resources,
            grab,
        )
        audit_payload["wall_clock_s"] = time.perf_counter() - t0
        if audit_path is not None:
            Path(audit_path).write_text(dumps_strict(audit_payload))
    elif audit_path is not None:
        Path(audit_path).parent.mkdir(parents=True, exist_ok=True)
        Path(audit_path).write_text(dumps_strict({
            "audit_evaluated": False,
            "reason": "selection was not recorded",
            "selection_record": {k: v for k, v in selection_record.items() if k != "selected_checkpoints"},
            "declared_complete": False,
            "confirm_evaluated": False,
            "control_evaluated": False,
        }))
    selection_payload["wall_clock_s"] = time.perf_counter() - t0
    return {"selection": selection_payload, "audit": audit_payload}


def _run_audit(
    saved: dict[str, Any],
    cfg: dict[str, Any],
    specs: tuple[Any, ...],
    selection_support: list[TransitionDataset],
    selection_query: list[TransitionDataset],
    horizons: list[int],
    budget: int,
    angvel_index: int,
    resources: dict[str, Any],
    grab: Any,
) -> dict[str, Any]:
    """Score only the four saved audit labels. Context and MLP are loaded on separate plans."""
    selected = saved["selection_record"]["selected_checkpoints"]
    context_plan = context_audit_entries(int(selected["history_selected"]["updates"]), int(selected["constant_selected"]["updates"]))
    mlp_plan = mlp_audit_entries(int(selected["mlp_reference"]["updates"]))
    allowed_paths = {path for entry in selected.values() for path in entry["paths"].values()}
    planned_paths = set()
    for entry in context_plan:
        planned_paths.update(selected[entry["label"]]["paths"].values())
    for entry in mlp_plan:
        planned_paths.update(selected[entry["label"]]["paths"].values())
    if planned_paths != allowed_paths:
        raise RuntimeError("audit plans do not match the saved checkpoint allow-list")
    audit_support = [grab(spec, 128, int(cfg["audit_support_env0"]) + 10 * i, int(cfg["audit_support_base"]) + i, "audit_support_env") for i, spec in enumerate(specs)]
    audit_query = [
        complete_episodes(grab(spec, 400, int(cfg["audit_query_env0"]) + 10 * i, int(cfg["audit_query_base"]) + i, "audit_query_env"), 16)
        for i, spec in enumerate(specs)
    ]
    resources["audit_collected"] = True
    assert_disjoint_seeds(*audit_support, *audit_query, *selection_support, *selection_query)
    donors = [audit_support[(i + 1) % len(audit_support)] for i in range(len(specs))]
    per_seed = []
    loaded: list[str] = []
    for seed_id in range(len(saved["per_seed"])):
        labels_by_task: dict[str, dict[str, Any]] = {spec.task_id: {"labels": {}} for spec in specs}
        for entry in context_plan:
            info = selected[entry["label"]]
            path = Path(info["paths"][str(seed_id)])
            loaded.append(str(path))
            if entry["kind"] == "constant":
                blob = torch.load(path, map_location="cpu", weights_only=False)
                model = load_context_checkpoint(path)
                vector = torch.as_tensor(blob["constant_vector"]).float()
                for i, spec in enumerate(specs):
                    labels_by_task[spec.task_id]["labels"][entry["label"]] = {"constant": _score_constant(model, vector, audit_query[i], horizons, angvel_index)}
            else:
                model = load_context_checkpoint(path).clone_frozen()
                for i, spec in enumerate(specs):
                    labels_by_task[spec.task_id]["labels"][entry["label"]] = _score_history(model, audit_support[i], donors[i], audit_query[i], budget, horizons, angvel_index)
        for entry in mlp_plan:
            info = selected[entry["label"]]
            path = Path(info["paths"][str(seed_id)])
            loaded.append(str(path))
            mlp = load_mlp_checkpoint(path, tuple(cfg["mlp_hidden"]))
            for i, spec in enumerate(specs):
                labels_by_task[spec.task_id]["labels"][entry["label"]] = {"mlp": _score_mlp(mlp, audit_query[i], horizons, angvel_index)}
        per_seed.append({"model_seed": seed_id, "tasks": {task_id: {"labels": body["labels"]} for task_id, body in labels_by_task.items()}})
    if any("history_u1000" in path and int(selected["history_selected"]["updates"]) != 1000 for path in loaded):
        raise RuntimeError("audit loaded an unselected history checkpoint")
    task_ids = [spec.task_id for spec in specs]
    schema = audit_schema([seed["model_seed"] for seed in per_seed], task_ids)
    raw_records = records_from_cells(per_seed)
    completeness = _apply_schema(raw_records, schema)
    rows = _interval_rows(per_seed, "history_selected", "constant_selected")
    screen = frozen_screen(
        rows,
        improvement=float(cfg["screen_angvel_improvement"]),
        min_positive_seeds=int(cfg["screen_min_positive_seeds"]),
        max_worsening=float(cfg["screen_max_worsening"]),
        frozen_ok=True,
        complete=bool(completeness["declared_complete"]),
    )
    history_updates = int(selected["history_selected"]["updates"])
    return {
        "protocol": saved["protocol"],
        "selection_record": saved["selection_record"],
        "loaded_checkpoints": loaded,
        "context_audit_plan": context_plan,
        "mlp_audit_plan": mlp_plan,
        "data_hashes": {
            "audit_support": [prefix_hash(ds, len(ds)) for ds in audit_support],
            "audit_query": [prefix_hash(ds, len(ds)) for ds in audit_query],
        },
        "schema": schema,
        "raw_records": raw_records,
        "per_seed_metrics": rows,
        "summary": _intervals(rows),
        "screen": screen,
        "classification": classify_frozen(history_updates, screen),
        "completeness": completeness,
        "declared_complete": bool(completeness["declared_complete"]),
        "resources": resources,
        "confirm_evaluated": False,
        "control_evaluated": False,
        "is_agi": False,
        "audit_evaluated": True,
    }


def _selection_summary(per_seed: list[dict[str, Any]], updates: list[int]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for step in updates:
        block: dict[str, Any] = {}
        for label, condition in (
            (f"history_u{step}", "real"),
            (f"history_u{step}", "zero"),
            (f"history_u{step}", "wrong"),
            (f"constant_u{step}", "constant"),
        ):
            angvel = [_mean_condition(seed["tasks"], label, condition, "angvel_mae") for seed in per_seed if seed["tasks"]]
            mae = [_mean_condition(seed["tasks"], label, condition, "mae") for seed in per_seed if seed["tasks"]]
            block[f"{label}.{condition}"] = {
                "angvel_mae": seed_level_ci(angvel) if len(angvel) >= 2 else {"n": len(angvel), "mean": float(np.mean(angvel)) if angvel else None},
                "mae": seed_level_ci(mae) if len(mae) >= 2 else {"n": len(mae), "mean": float(np.mean(mae)) if mae else None},
            }
        out[str(step)] = block
    return {"selection_set": out, "interval": "exploratory_student_t_across_training_seeds_df_2"}


def _protocol(cfg: dict[str, Any], smoke: bool, sha: str, source_status: dict[str, Any], updates: list[int], total: int, n_seeds: int) -> dict[str, Any]:
    return {
        "code_version": "frozen_dynamics_context_diagnostic",
        "config": cfg,
        "executed_updates": updates,
        "executed_total_updates": total,
        "executed_seeds": n_seeds,
        "smoke": bool(smoke),
        "implementation_sha": sha if not source_status.get("source_dirty") else None,
        "source_dirty": bool(source_status.get("source_dirty", True)),
        "git": _git_meta(),
        "confirm_evaluated": False,
        "control_evaluated": False,
        "is_agi": False,
        "h_frozen": cfg.get("h_frozen"),
        "prior_result": "3000 joint updates improved shared dynamics and failed the context-usefulness screen. That result is unchanged.",
    }


def _plot(path: Path, per_seed: list[dict[str, Any]], updates: list[int]) -> None:
    series: dict[str, list[float]] = {}
    bands: dict[str, list[tuple[float, float]]] = {}
    specs_ = (
        ("history_real", "history_u{step}", "real"),
        ("history_zero", "history_u{step}", "zero"),
        ("history_wrong", "history_u{step}", "wrong"),
        ("constant", "constant_u{step}", "constant"),
    )
    for name, label_fmt, condition in specs_:
        acc = []
        band = []
        for step in updates:
            values = [_mean_condition(seed["tasks"], label_fmt.format(step=step), condition, "angvel_mae") for seed in per_seed if seed["tasks"]]
            acc.append(float(np.mean(values)) if values else float("nan"))
            band.append((float(np.min(values)), float(np.max(values))) if values else (float("nan"), float("nan")))
        series[name] = acc
        bands[name] = band
    _svg(path, updates, series, bands)
