"""Offline Pendulum context-adaptation pilot. Development gate before confirmation. Not AGI."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import (
    pendulum_confirmation_targets,
    pendulum_context_confirmation,
    pendulum_context_development,
    pendulum_context_train,
    pendulum_meta_confirm,
    pendulum_meta_train,
    pendulum_meta_val,
    pendulum_physics_key,
    pendulum_source,
    pendulum_transfer_confirmation,
    pendulum_transfer_development,
    pendulum_transfer_sequence,
)
from nexus.tasks.spec import TaskSpec
from nexus.world.adapt import finetune_world_model
from nexus.world.agent import plan_with_belief
from nexus.world.belief import IdentityBelief
from nexus.world.context_model import (
    CONTEXT_DIM,
    MAX_CONTEXT,
    ContextWorldModel,
    train_context_model,
)
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, collect_transitions, concat_datasets
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_HIDDEN, FROZEN_KIND, FROZEN_PRIMARY_HORIZON
from nexus.world.memory import checkpoint_nbytes
from nexus.world.planning import PENDULUM_PLAN_CANDIDATES, PENDULUM_PLAN_HORIZON
from nexus.world.protocol import (
    V089C_CONFIRM_EVAL_SEED,
    V089C_DEV_EVAL_SEED,
    V089C_PREFIX_SEED,
    V089C_SOURCE_COLLECT_SEED,
    V089C_TRAIN_SEED,
    V089M_CONFIRM_EVAL_SEED,
)
from nexus.rl.running_stats import RunningMeanStd
from nexus.world.train import one_step_errors, train_world_model
from nexus.world.v085 import _git_meta
from nexus.world.v086 import V086_FT_LR
from nexus.world.v089 import _auc

STARTING_SHA = "a9c184c85c2a22317098d0c3637812386f4207e6"
BUDGETS = (0, 16, 32, 64, 128, 256, 512, 1024)
PRIMARY_HI = 256
SOURCE_PER_TASK = 400
SOURCE_EPOCHS = 6
MLP_BATCH = 64
FT_LR = float(V086_FT_LR)
FT_EPOCH_CANDIDATES = (2, 4)
DEV_LIMIT_S = 2 * 60 * 60
CONFIRM_LIMIT_S = 4 * 60 * 60
GRU_EXCLUDED = "Shuffled transition minibatches do not form a coherent GRU trajectory. Excluded; not a recurrent rewrite."
# Primary confirmatory contrast is real-context AUC minus multitask fine-tune.
# The two context controls are prespecified secondary tests with unadjusted CIs.
MULTIPLICITY = "primary_only_confirmatory; secondary_unadjusted; no_bonferroni"


def _split_hash(specs: tuple[TaskSpec, ...] | list[TaskSpec]) -> str:
    payload = [[s.task_id, list(pendulum_physics_key(s))] for s in specs]
    return hashlib.sha256(dumps_strict(payload).encode()).hexdigest()[:16]


def prior_physics_keys() -> set[tuple[float, float, float]]:
    specs: list[TaskSpec] = [
        pendulum_source(),
        pendulum_transfer_development(),
        *pendulum_confirmation_targets(),
        *pendulum_transfer_confirmation(),
        *pendulum_transfer_sequence(),
        *pendulum_meta_train(),
        *pendulum_meta_val(),
        *pendulum_meta_confirm(),
    ]
    return {pendulum_physics_key(s) for s in specs}


def assert_context_physics_disjoint() -> None:
    prior = prior_physics_keys()
    seen: set[tuple[float, float, float]] = set()
    groups = {
        "train": pendulum_context_train(),
        "dev": pendulum_context_development(),
        "confirm": pendulum_context_confirmation(),
    }
    for name, specs in groups.items():
        for spec in specs:
            key = pendulum_physics_key(spec)
            if key in prior or key in seen:
                raise AssertionError(f"physics collision {name} {spec.task_id} {key}")
            seen.add(key)
    if groups["dev"] and groups["confirm"] and _split_hash(groups["dev"]) == _split_hash(groups["confirm"]):
        raise AssertionError("dev and confirm hashes collided")


def prefix_hash(ds: TransitionDataset, budget: int) -> str:
    """Hash the allowed prefix, including outcomes and array metadata.

    Observations, actions, next observations, termination, and truncation are included,
    with shape and dtype. Rows past `budget` do not enter the digest.
    """
    k = max(0, min(int(budget), len(ds)))
    parts: list[bytes] = []
    arrays = {
        "obs": ds.obs[:k],
        "action": ds.action[:k],
        "next_obs": ds.next_obs[:k],
        "terminated": np.asarray(ds.terminated[:k]),
        "truncated": np.asarray(ds.truncated[:k]),
    }
    for name, arr in arrays.items():
        block = np.ascontiguousarray(arr)
        parts.append(f"{name}:{block.shape}:{block.dtype}:".encode())
        parts.append(block.tobytes())
    return hashlib.sha256(b"".join(parts)).hexdigest()[:16]


def norm_auc(budgets: tuple[int, ...] | list[int], values: list[float], hi: int) -> float:
    xs = [int(b) for b in budgets if int(b) <= int(hi)]
    ys = [float(values[i]) for i, b in enumerate(budgets) if int(b) <= int(hi)]
    if len(xs) < 2:
        return float(ys[-1]) if ys else float("nan")
    return float(_auc(xs, ys) / float(hi))


def _collect(spec: TaskSpec, n: int, *, env0: int, base: int) -> TransitionDataset:
    n_env = max(2, min(8, max(1, int(n) // 32)))
    return collect_transitions(
        spec, n_transitions=int(n), env_seeds=tuple(range(int(env0), int(env0) + n_env)), base_seed=int(base), mix=("random",),
    )


def _fit_rms(datasets: list[TransitionDataset]) -> RunningMeanStd:
    obs = np.concatenate([ds.obs for ds in datasets], axis=0)
    rms = RunningMeanStd((obs.shape[-1],))
    rms.update(obs)
    return rms


def _mlp_updates(n: int, epochs: int, batch: int = MLP_BATCH) -> int:
    if n <= 0 or epochs <= 0:
        return 0
    return int(epochs) * int(np.ceil(n / float(batch)))


def _eval(spec: TaskSpec, model: Any, *, seed: int, episodes: int) -> dict[str, Any]:
    z0 = getattr(model, "z", None)
    if z0 is not None:
        z0 = z0.detach().clone()
    n0 = getattr(model, "n_encodes", None)
    row = plan_with_belief(spec, model, IdentityBelief(), seed=int(seed), episodes=int(episodes))
    if z0 is not None and not torch.equal(model.z, z0):
        raise RuntimeError("evaluation or rollout updated context")
    if n0 is not None and int(model.n_encodes) != int(n0):
        raise RuntimeError("evaluation encoded a new context")
    return {
        "mean_return": float(row["mean_return"]),
        "env_interactions": int(row["env_interactions"]),
        "model_states": int(row["model_states"]),
    }


def _ft(mlp: WorldModel, prefix: TransitionDataset, budget: int, *, epochs: int, seed: int) -> tuple[WorldModel, dict[str, Any]]:
    t0 = time.perf_counter()
    k = min(int(budget), len(prefix))
    if k <= 0:
        return mlp.clone(), {"optimizer_updates": 0, "target_train_examples": 0, "wall_s": 0.0, "used_target_val": False}
    train = prefix.slice(np.arange(k))
    empty = prefix.slice(np.zeros(0, dtype=np.int64))
    out, _log = finetune_world_model(mlp, train, empty, epochs=int(epochs), seed=int(seed), lr=FT_LR, select_by_val=False)
    return out, {
        "optimizer_updates": _mlp_updates(k, epochs),
        "target_train_examples": int(k) * int(epochs),
        "wall_s": time.perf_counter() - t0,
        "used_target_val": False,
    }


def _svg(path: Path, budgets: list[int], series: dict[str, list[float]], bands: dict[str, list[tuple[float, float]]] | None = None) -> None:
    width, height, pad = 640, 360, 40
    ys = [v for seq in series.values() for v in seq if np.isfinite(v)]
    if bands:
        ys.extend(v for seq in bands.values() for lo_b, hi_b in seq for v in (lo_b, hi_b) if np.isfinite(v))
    if not ys:
        return
    lo, hi = min(ys), max(ys)
    if hi - lo < 1e-6:
        hi = lo + 1.0
    def x(b: int) -> float:
        return pad + (width - 2 * pad) * (budgets.index(b) / max(len(budgets) - 1, 1))
    def y(v: float) -> float:
        return pad + (height - 2 * pad) * (1.0 - (v - lo) / (hi - lo))
    colors = ["#1f4e79", "#c45911", "#2e7d32", "#6b6b6b", "#8e24aa", "#00838f"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']
    parts.append(f'<rect width="100%" height="100%" fill="white"/>')
    for i, (name, seq) in enumerate(series.items()):
        color = colors[i % len(colors)]
        if bands and name in bands:
            band = bands[name]
            upper = " ".join(f"{x(b):.1f},{y(lo_b):.1f}" for b, (lo_b, _hi_b) in zip(budgets, band) if np.isfinite(lo_b))
            lower = " ".join(f"{x(b):.1f},{y(hi_b):.1f}" for b, (_lo_b, hi_b) in reversed(list(zip(budgets, band))) if np.isfinite(hi_b))
            parts.append(f'<polygon fill="{color}" fill-opacity="0.15" stroke="none" points="{upper} {lower}"/>')
        pts = " ".join(f"{x(b):.1f},{y(v):.1f}" for b, v in zip(budgets, seq))
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/>')
        parts.append(f'<text x="{pad}" y="{18 + 14 * i}" fill="{colors[i % len(colors)]}" font-size="12">{name}</text>')
    parts.append("</svg>")
    path.write_text("".join(parts))


def _train_pair(
    tasks: list[TransitionDataset],
    val: TransitionDataset,
    *,
    seed: int,
    epochs: int,
    updates: int | None,
    include_random: bool,
) -> dict[str, Any]:
    t_prep = time.perf_counter()
    rms = _fit_rms(tasks)
    prep_wall = time.perf_counter() - t_prep
    pooled = concat_datasets(*tasks, task_id="context_source_pool")
    t_mlp = time.perf_counter()
    mlp, slog = train_world_model(
        pooled, val, kind=FROZEN_KIND, epochs=epochs, batch_size=MLP_BATCH,
        seed=V089C_TRAIN_SEED + int(seed), hidden=FROZEN_HIDDEN, n_actions=3, obs_rms=rms,
    )
    mlp_wall = time.perf_counter() - t_mlp
    n_updates = _mlp_updates(len(pooled), epochs)
    ctx = ContextWorldModel.create(3, 3, seed=V089C_TRAIN_SEED + 17 * int(seed))
    ctx.copy_rms(rms)
    t_ctx = time.perf_counter()
    ctx_log = train_context_model(ctx, tasks, updates=int(n_updates if updates is None else updates), seed=V089C_TRAIN_SEED + 31 * int(seed))
    ctx_wall = time.perf_counter() - t_ctx
    rand_log = None
    rand = None
    if include_random:
        rand = ContextWorldModel.create(3, 3, seed=V089C_TRAIN_SEED + 41 * int(seed), random_encoder=True)
        rand.copy_rms(rms)
        rand_log = train_context_model(rand, tasks, updates=int(n_updates if updates is None else updates), seed=V089C_TRAIN_SEED + 43 * int(seed))
    return {
        "mlp": mlp,
        "ctx": ctx,
        "rand": rand,
        "rms_mean": np.asarray(rms.mean).tolist(),
        "mlp_updates": n_updates,
        "mlp_examples": int(len(pooled) * epochs),
        "mlp_wall_s": mlp_wall,
        "prep_wall_s": prep_wall,
        "ctx_log": ctx_log,
        "ctx_wall_s": ctx_wall,
        "rand_log": rand_log,
        "mlp_val": slog["best_val"],
        "nbytes_mlp": checkpoint_nbytes(mlp),
        "nbytes_ctx": int(sum(p.numel() * p.element_size() for p in list(ctx.encoder.parameters()) + list(ctx.net.parameters()))),
        "params_mlp": sum(int(p.numel()) for p in mlp.net.parameters()),
        "params_ctx": ctx.n_parameters(),
        "params_ctx_trainable": ctx.trainable_parameters(),
    }


def _select_ft_epochs(mlp: WorldModel, prefix: TransitionDataset, spec: TaskSpec, *, seed: int) -> dict[str, Any]:
    rows = []
    for ep in FT_EPOCH_CANDIDATES:
        model, meta = _ft(mlp, prefix, 64, epochs=ep, seed=seed)
        ev = _eval(spec, model, seed=V089C_DEV_EVAL_SEED, episodes=1)
        rows.append({"epochs": ep, "return": ev["mean_return"], **meta})
    best = max(rows, key=lambda r: r["return"])
    return {"candidates": rows, "selected_epochs": int(best["epochs"]), "rule": "dev_task0_budget64_one_episode_max_return"}


def _curves_for_seed(
    *,
    models: dict[str, Any],
    tasks: tuple[TaskSpec, ...],
    prefixes: dict[str, TransitionDataset],
    donor: TransitionDataset,
    budgets: tuple[int, ...],
    episodes: int,
    eval_seed: int,
    ft_epochs: int,
    methods: tuple[str, ...],
    seed_i: int,
    deadline: float,
) -> dict[str, Any]:
    per_task: dict[str, Any] = {}
    for spec in tasks:
        if time.perf_counter() > deadline:
            return {"incomplete": True, "per_task": per_task}
        prefix = prefixes[spec.task_id]
        hashes = {str(b): prefix_hash(prefix, b) for b in budgets}
        curves: dict[str, list[float]] = {m: [] for m in methods}
        resources: dict[str, Any] = {}
        pred: dict[str, Any] = {}
        ctx: ContextWorldModel = models["ctx"]
        rand: ContextWorldModel | None = models.get("rand")
        frozen_cache: dict[str, dict[str, Any]] = {}
        for b in budgets:
            if time.perf_counter() > deadline:
                return {"incomplete": True, "per_task": per_task}
            built: dict[str, Any] = {}
            res_b: dict[str, Any] = {}
            if "mlp_frozen" in methods:
                built["mlp_frozen"] = models["mlp"]
                res_b["mlp_frozen"] = {"optimizer_updates": 0, "target_train_examples": 0, "wall_s": 0.0}
            if "mlp_ft" in methods:
                if b == 0:
                    built["mlp_ft"] = models["mlp"]
                    res_b["mlp_ft"] = {"optimizer_updates": 0, "target_train_examples": 0, "wall_s": 0.0, "used_target_val": False}
                else:
                    built["mlp_ft"], res_b["mlp_ft"] = _ft(models["mlp"], prefix, b, epochs=ft_epochs, seed=V089C_TRAIN_SEED + 1000 * seed_i + b)
            if "ctx_real" in methods:
                m = ctx.clone_frozen()
                m.set_context_from_dataset(prefix, budget=b)
                built["ctx_real"] = m
                res_b["ctx_real"] = {"context_rows": min(b, MAX_CONTEXT, len(prefix)), "weight_updates": 0}
            if "ctx_zero" in methods:
                m = ctx.clone_frozen()
                m.clear_context()
                built["ctx_zero"] = m
                res_b["ctx_zero"] = {"context_rows": 0, "weight_updates": 0}
            if "ctx_wrong" in methods:
                m = ctx.clone_frozen()
                if b <= 0:
                    m.clear_context()
                else:
                    m.set_context_from_dataset(donor, budget=b)
                built["ctx_wrong"] = m
                res_b["ctx_wrong"] = {"donor_task": donor.task_id, "context_rows": 0 if b <= 0 else min(b, MAX_CONTEXT, len(donor))}
            if "ctx_rand" in methods and rand is not None:
                m = rand.clone_frozen()
                m.set_context_from_dataset(prefix, budget=b)
                built["ctx_rand"] = m
                res_b["ctx_rand"] = {"context_rows": min(b, MAX_CONTEXT, len(prefix)), "encoder_trained": False}
            for name, model in built.items():
                cached = name in ("mlp_frozen", "ctx_zero") and name in frozen_cache
                if cached:
                    ev = frozen_cache[name]
                    executed_env = 0
                    executed_imagined = 0
                else:
                    ev = _eval(spec, model, seed=eval_seed, episodes=episodes)
                    executed_env = int(ev["env_interactions"])
                    executed_imagined = int(ev["model_states"])
                    if name in ("mlp_frozen", "ctx_zero"):
                        frozen_cache[name] = ev
                curves[name].append(float(ev["mean_return"]))
                res_b[name] = {
                    **res_b.get(name, {}),
                    "eval_env": int(ev["env_interactions"]),
                    "eval_env_executed": executed_env,
                    "imagined_states": int(ev["model_states"]),
                    "imagined_executed": executed_imagined,
                    "cached": cached,
                }
            if b == min(PRIMARY_HI, max(budgets)):
                pred = {}
                if "ctx_real" in built and b > 0:
                    pred["ctx_real_prefix_mae"] = float(one_step_errors(built["ctx_real"], prefix.slice(np.arange(min(b, len(prefix)))))["mae"])
                if "mlp_ft" in built and b > 0:
                    pred["mlp_ft_prefix_mae"] = float(one_step_errors(built["mlp_ft"], prefix.slice(np.arange(min(b, len(prefix)))))["mae"])
            resources[str(b)] = res_b
        z_real = ctx.clone_frozen()
        z_real.set_context_from_dataset(prefix, budget=min(PRIMARY_HI, len(prefix)))
        z_wrong = ctx.clone_frozen()
        z_wrong.set_context_from_dataset(donor, budget=min(PRIMARY_HI, len(donor)))
        sens = {
            "z_real_norm": float(torch.linalg.vector_norm(z_real.z).item()),
            "z_real_minus_zero": float(torch.linalg.vector_norm(z_real.z).item()),
            "z_real_minus_wrong": float(torch.linalg.vector_norm(z_real.z - z_wrong.z).item()),
        }
        auc = {m: {"primary": norm_auc(budgets, curves[m], PRIMARY_HI), "full": norm_auc(budgets, curves[m], int(budgets[-1]))} for m in methods}
        per_task[spec.task_id] = {
            "params": dict(spec.params),
            "prefix_hashes": hashes,
            "curve": {m: curves[m] for m in methods},
            "auc": auc,
            "prediction_in_prefix": pred,
            "sensitivity": sens,
            "resources": resources,
            "finite": all(np.isfinite(curves[m]).all() for m in methods),
        }
    return {"incomplete": False, "per_task": per_task}


def _mean_auc(block: dict[str, Any], method: str, which: str = "primary") -> float:
    vals = [float(block["per_task"][tid]["auc"][method][which]) for tid in block["per_task"]]
    return float(np.mean(vals)) if vals else float("nan")


def development_gate(per_seed: list[dict[str, Any]]) -> dict[str, Any]:
    def col(a: str, b: str) -> list[float]:
        return [_mean_auc(s["curves"], a) - _mean_auc(s["curves"], b) for s in per_seed if s["curves"]["per_task"]]

    rz, rw, rf = col("ctx_real", "ctx_zero"), col("ctx_real", "ctx_wrong"), col("ctx_real", "mlp_ft")
    enc = [float(s["train"]["ctx_log"]["encoder_l2_delta"]) for s in per_seed]
    finite = all(s["curves"]["incomplete"] is False and all(t["finite"] for t in s["curves"]["per_task"].values()) for s in per_seed)
    passed = bool(finite and float(np.mean(rz)) > 0 and float(np.mean(rw)) > 0 and float(np.mean(rf)) > 0 and float(np.mean(enc)) > 0)
    return {
        "pass": passed,
        "rule": "dev point means: real-zero>0, real-wrong>0, real-ft>0, encoder_l2_delta>0, all finite. Not a significance test.",
        "real_minus_zero": float(np.mean(rz)) if rz else None,
        "real_minus_wrong": float(np.mean(rw)) if rw else None,
        "real_minus_ft": float(np.mean(rf)) if rf else None,
        "encoder_l2_delta": float(np.mean(enc)) if enc else None,
        "finite": finite,
    }


def run_context_adaptation(
    *,
    phase: str = "dev",
    quick: bool = False,
    ft_epochs: int | None = None,
    artifact_path: str | Path | None = None,
    plot_path: str | Path | None = None,
    dev_artifact: dict[str, Any] | None = None,
    dev_artifact_path: str | Path | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    assert_context_physics_disjoint()
    if phase not in ("dev", "confirm", "smoke"):
        raise ValueError(phase)
    if phase == "confirm":
        from nexus.world.confirm_guard import assert_confirmation_allowed, load_dev_artifact

        evidence = dev_artifact if dev_artifact is not None else load_dev_artifact(dev_artifact_path)
        assert_confirmation_allowed(evidence)
        if ft_epochs is None and not quick:
            ft_epochs = int(evidence["protocol"]["ft_epochs"])
    dev_specs = pendulum_context_development()
    confirm_specs = pendulum_context_confirmation() if phase == "confirm" else ()
    source_specs = pendulum_context_train()
    budgets = BUDGETS
    n_seeds = 2 if phase == "dev" else (10 if phase == "confirm" else 1)
    episodes = 2 if phase == "dev" else (5 if phase == "confirm" else 1)
    epochs = SOURCE_EPOCHS
    per_task_n = SOURCE_PER_TASK
    prefix_n = 1024
    updates = None
    if quick or phase == "smoke":
        n_seeds, episodes, epochs, per_task_n, prefix_n = 1, 1, 1, 220, 32
        budgets = (0, 16)
        updates = 2
        source_specs = source_specs[:2]
        dev_specs = dev_specs[:1]
        if phase == "confirm":
            confirm_specs = confirm_specs[:1]
    deadline = t0 + (CONFIRM_LIMIT_S if phase == "confirm" else DEV_LIMIT_S)
    methods = ("mlp_frozen", "mlp_ft", "ctx_real", "ctx_zero", "ctx_wrong")
    if phase != "confirm":
        methods = methods + ("ctx_rand",)
    eval_seed = V089C_CONFIRM_EVAL_SEED if phase == "confirm" else V089C_DEV_EVAL_SEED
    specs = confirm_specs if phase == "confirm" else dev_specs
    if phase == "confirm" and ft_epochs is None and not quick:
        raise RuntimeError("confirmation requires the development-selected fine-tune epoch count")
    ft_epochs_selected = 4 if ft_epochs is None else int(ft_epochs)
    ft_search = None
    per_seed: list[dict[str, Any]] = []
    incomplete = False
    for s in range(n_seeds):
        if time.perf_counter() > deadline:
            incomplete = True
            break
        tasks = [
            _collect(spec, per_task_n, env0=1000 + 100 * s + 10 * i, base=V089C_SOURCE_COLLECT_SEED + 50 * s + 9 * i)
            for i, spec in enumerate(source_specs)
        ]
        val_parts = [
            _collect(spec, 32 if not (quick or phase == "smoke") else 16, env0=3000 + 50 * s + 10 * i, base=V089C_SOURCE_COLLECT_SEED + 800 + 20 * s + i)
            for i, spec in enumerate(source_specs)
        ]
        assert_disjoint_seeds(*tasks, *val_parts)
        val = concat_datasets(*val_parts, task_id="context_source_val")
        trained = _train_pair(tasks, val, seed=s, epochs=epochs, updates=updates, include_random=phase != "confirm")
        if phase == "dev" and s == 0 and not quick:
            pref0 = _collect(dev_specs[0], prefix_n, env0=4900, base=V089C_PREFIX_SEED)
            ft_search = _select_ft_epochs(trained["mlp"], pref0, dev_specs[0], seed=s)
            ft_epochs_selected = int(ft_search["selected_epochs"])
        prefixes = {
            spec.task_id: _collect(spec, prefix_n, env0=5000 + 50 * s + 10 * i, base=V089C_PREFIX_SEED + 100 * s + i)
            for i, spec in enumerate(specs)
        }
        block = _curves_for_seed(
            models=trained, tasks=specs, prefixes=prefixes, donor=tasks[0], budgets=budgets, episodes=episodes,
            eval_seed=eval_seed, ft_epochs=1 if phase == "smoke" else ft_epochs_selected, methods=methods, seed_i=s, deadline=deadline,
        )
        if block["incomplete"]:
            incomplete = True
        per_seed.append(
            {
                "model_seed": s,
                "train": {
                    "source_env": int(sum(t.env_interactions for t in tasks)),
                    "source_val_env": int(val.env_interactions),
                    "mlp_updates": trained["mlp_updates"],
                    "mlp_examples": trained["mlp_examples"],
                    "mlp_wall_s": trained["mlp_wall_s"],
                    "ctx_log": trained["ctx_log"],
                    "ctx_wall_s": trained["ctx_wall_s"],
                    "rand_log": trained["rand_log"],
                    "params_mlp": trained["params_mlp"],
                    "params_ctx": trained["params_ctx"],
                    "nbytes_mlp": trained["nbytes_mlp"],
                    "nbytes_ctx": trained["nbytes_ctx"],
                    "rms_frozen_from_source": True,
                },
                "curves": block,
            }
        )
        print(f"context_adapt phase={phase} seed={s}", flush=True)
        if incomplete:
            break
    gate = development_gate(per_seed) if phase == "dev" and per_seed and not quick else {"pass": False, "reason": "not a full development run" if phase != "dev" else "empty"}
    if phase == "dev" and quick:
        gate = {"pass": False, "reason": "smoke is not a development gate"}

    def pack(method: str, which: str = "primary") -> dict[str, Any] | None:
        xs = [_mean_auc(s["curves"], method, which) for s in per_seed if s["curves"]["per_task"]]
        return seed_level_ci(xs) if len(xs) >= 2 else ({"n": len(xs), "mean": float(np.mean(xs))} if xs else None)

    methods_present = [m for m in methods if per_seed and m in next(iter(per_seed[0]["curves"]["per_task"].values()), {}).get("auc", {})]
    summary_auc = {m: pack(m) for m in methods_present}
    deltas = {}
    if "ctx_real" in methods_present:
        for other in ("mlp_ft", "mlp_frozen", "ctx_zero", "ctx_wrong", "ctx_rand"):
            if other in methods_present:
                xs = [_mean_auc(s["curves"], "ctx_real") - _mean_auc(s["curves"], other) for s in per_seed if s["curves"]["per_task"]]
                deltas[f"real_minus_{other}"] = seed_level_ci(xs) if len(xs) >= 2 else ({"n": len(xs), "mean": float(np.mean(xs))} if xs else None)
    from nexus.world.confirm_guard import provenance_fields

    payload = {
        "protocol": {
            "code_version": "context_adaptation_pilot",
            "starting_sha": STARTING_SHA,
            "phase": phase,
            "conditioning": "film",
            "context_dim": CONTEXT_DIM,
            "max_context": MAX_CONTEXT,
            "gru_excluded": GRU_EXCLUDED,
            "budgets": list(budgets),
            "primary_metric": "trapz_return_auc_0_to_256_divided_by_256",
            "primary_comparison": "ctx_real_minus_mlp_ft",
            "secondary_comparisons": ["ctx_real_minus_ctx_zero", "ctx_real_minus_ctx_wrong"],
            "multiplicity": MULTIPLICITY,
            "ft_lr": FT_LR,
            "ft_epochs": ft_epochs_selected,
            "ft_target_validation": False,
            "source_epochs": epochs,
            "n_model_seeds": n_seeds,
            "eval_episodes": episodes,
            "eval_seed": eval_seed,
            "prior_confirm_eval_unused": V089M_CONFIRM_EVAL_SEED,
            "horizon": PENDULUM_PLAN_HORIZON,
            "candidates": PENDULUM_PLAN_CANDIDATES,
            "cartpole_horizon": FROZEN_PRIMARY_HORIZON,
            "train_hash": _split_hash(source_specs),
            "dev_hash": _split_hash(pendulum_context_development()),
            "confirm_hash": _split_hash(pendulum_context_confirmation()),
            "confirm_evaluated": phase == "confirm",
            "reptile_note": "Previous Reptile loss is a negative result for that run, not a disproof of Reptile.",
            "is_agi": False,
            **provenance_fields(),
            "quick": quick or phase == "smoke",
            "git": _git_meta(),
        },
        "ft_search": ft_search,
        "gate": gate,
        "summary_primary_auc": summary_auc,
        "deltas_primary_auc": deltas,
        "per_seed": per_seed,
        "incomplete": incomplete,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
    }
    if plot_path is not None and per_seed and per_seed[0]["curves"]["per_task"]:
        series = {}
        bands = {}
        for m in methods_present:
            acc = []
            band = []
            for b_i, _b in enumerate(budgets):
                seed_means = []
                for s in per_seed:
                    vals = [task["curve"][m][b_i] for task in s["curves"]["per_task"].values() if len(task["curve"][m]) > b_i]
                    if vals:
                        seed_means.append(float(np.mean(vals)))
                acc.append(float(np.mean(seed_means)) if seed_means else float("nan"))
                band.append((float(np.min(seed_means)), float(np.max(seed_means))) if seed_means else (float("nan"), float("nan")))
            series[m] = acc
            bands[m] = band
        _svg(Path(plot_path), list(budgets), series, bands)
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
