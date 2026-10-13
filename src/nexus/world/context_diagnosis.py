"""Development diagnosis: fixed-length vs variable-length context training.

Does not evaluate confirmation physics. Does not change trunk size or add a loss.
The 0–128 AUC here is not the original 0–256 confirmatory metric.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import pendulum_context_confirmation, pendulum_context_development, pendulum_context_train
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_model import (
    MAX_CONTEXT,
    ContextWorldModel,
    make_context_schedule,
    train_context_model,
)
from nexus.world.context_pilot import (
    _collect,
    _eval,
    _fit_rms,
    _ft,
    _mlp_updates,
    _split_hash,
    _svg,
    assert_context_physics_disjoint,
    norm_auc,
    prefix_hash,
)
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, concat_datasets
from nexus.world.freeze import FROZEN_HIDDEN, FROZEN_KIND
from nexus.world.memory import checkpoint_nbytes
from nexus.world.protocol import V089C_DEV_EVAL_SEED, V089C_PREFIX_SEED, V089C_SOURCE_COLLECT_SEED, V089C_TRAIN_SEED
from nexus.world.train import one_step_errors, train_world_model
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/context_adaptation_diagnosis.yaml")
DIAG_SUPPORT_ENV = 8_000
DIAG_QUERY_ENV = 14_000
TIME_LIMIT_S = 2 * 60 * 60
NEXT_INTERVENTIONS = (
    "representation_or_optimization",
    "task_distribution_generalization",
    "adopt_variable_support_length",
    "rollout_and_planner_sensitivity",
    "trunk_capacity",
)


def load_diagnosis_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("diagnosis config must be a mapping")
    required = {
        "protocol_id": "context_adaptation_diagnosis_v1",
        "starting_sha": "b86baf4e23e29761ec34e29b2a8d67f3a24ae207",
        "confirmation_unlocked": False,
        "context_dim": 8,
        "encoder_hidden": 32,
        "trunk_hidden": [48, 48],
        "max_context": 128,
        "updates": 300,
        "query_batch": 64,
        "empty_prob": 0.2,
        "variable_lengths": [16, 32, 64, 128],
        "source_per_task": 400,
        "source_epochs": 6,
        "mlp_batch": 64,
        "ft_epochs": 4,
        "ft_lr": 0.0005,
        "ft_target_validation": False,
        "n_seeds": 3,
        "episodes": 3,
        "budgets": [0, 16, 32, 64, 128],
        "primary_hi": 128,
        "primary_metric": "trapz_return_auc_0_to_128_divided_by_128",
        "rollout_horizons": [3, 8, 16],
        "horizon": 16,
        "candidates": 16,
        "eval_seed": 193000,
        "time_limit_s": TIME_LIMIT_S,
        "checkpoint_selection": "mlp_best_source_validation_context_final_update",
        "control_wrong_donor": "source_train_task_0",
        "prediction_donor": "source_task_(i+1)_mod_n__dev_uses_source_0",
        "zero_context_gap": 50,
    }
    for key, expected in required.items():
        if cfg.get(key) != expected:
            raise ValueError(f"config {key}={cfg.get(key)!r} does not match the locked setting {expected!r}")
    if cfg.get("is_agi") is not False:
        raise ValueError("diagnosis is not AGI")
    if not str(cfg.get("h_length") or "").strip() or not str(cfg.get("h_context") or "").strip():
        raise ValueError("diagnostic hypotheses must be stated in the config")
    if int(cfg["eval_seed"]) != int(V089C_DEV_EVAL_SEED):
        raise ValueError("evaluation seed drifted from the context pilot")
    if int(cfg["max_context"]) != int(MAX_CONTEXT):
        raise ValueError("max context drifted")
    return cfg


def complete_episodes(ds: TransitionDataset, min_len: int) -> TransitionDataset:
    chunks = []
    for eid in np.unique(ds.episode_id):
        idx = np.flatnonzero(ds.episode_id == eid)
        last = int(idx[-1])
        if (bool(ds.terminated[last]) or bool(ds.truncated[last])) and int(idx.size) >= int(min_len):
            chunks.append(idx)
    if not chunks:
        raise RuntimeError(f"no complete diagnostic episode in {ds.task_id}")
    return ds.slice(np.concatenate(chunks))


def open_loop_mae(model: Any, ds: TransitionDataset, horizons: tuple[int, ...] | list[int]) -> dict[str, float]:
    """Recorded-action rollout inside complete episodes. Context is not updated."""
    z0 = getattr(model, "z", None)
    if z0 is not None:
        z0 = z0.detach().clone()
    n0 = getattr(model, "n_encodes", None)
    sums = {int(h): [] for h in horizons}
    for eid in np.unique(ds.episode_id):
        idx = np.flatnonzero(ds.episode_id == eid)
        obs = ds.obs[idx]
        act = ds.action[idx]
        nxt = ds.next_obs[idx]
        if obs.shape[0] > 1 and float(np.max(np.abs(nxt[:-1] - obs[1:]))) > 1e-4:
            raise RuntimeError("rollout episode is not contiguous")
        for h in horizons:
            h = int(h)
            if obs.shape[0] <= h:
                continue
            state = obs[0:1]
            for t in range(h):
                state, _p = model.step(state, act[t : t + 1])
            sums[h].append(float(np.mean(np.abs(state.reshape(-1) - obs[h]))))
    if z0 is not None and not torch.equal(model.z, z0):
        raise RuntimeError("open-loop rollout updated context")
    if n0 is not None and int(model.n_encodes) != int(n0):
        raise RuntimeError("open-loop rollout encoded a new context")
    return {str(h): float(np.mean(v)) if v else float("nan") for h, v in sums.items()}


def _predict(model: Any, query: TransitionDataset, horizons: list[int]) -> dict[str, Any]:
    err = one_step_errors(model, query)
    roll = open_loop_mae(model, query, horizons)
    return {
        "mae": err["mae"],
        "rmse": err["rmse"],
        "mae_per_dim": err["mae_per_dim"],
        "rmse_per_dim": err["rmse_per_dim"],
        "n": err["n"],
        "rollout_mae": roll,
    }


def _z_stats(model: ContextWorldModel, real: TransitionDataset, wrong: TransitionDataset, budget: int) -> dict[str, float]:
    probe = model.clone_frozen()
    if budget <= 0:
        probe.clear_context()
        return {"z_norm": 0.0, "z_real_minus_zero": 0.0, "z_real_minus_wrong": 0.0}
    probe.set_context_from_dataset(real, budget=budget)
    zr = probe.z.detach().clone()
    probe.set_context_from_dataset(wrong, budget=budget)
    zw = probe.z.detach().clone()
    return {
        "z_norm": float(torch.linalg.vector_norm(zr).item()),
        "z_real_minus_zero": float(torch.linalg.vector_norm(zr).item()),
        "z_real_minus_wrong": float(torch.linalg.vector_norm(zr - zw).item()),
    }


def interpret_diagnosis(flags: dict[str, bool]) -> dict[str, Any]:
    """Pick one next intervention. Earlier rules win when several patterns are present."""
    order = (
        ("real_context_fails_source_prediction", "representation_or_optimization"),
        ("source_prediction_helps_but_development_does_not", "task_distribution_generalization"),
        ("variable_length_helps_short_histories", "adopt_variable_support_length"),
        ("prediction_improves_but_control_worsens", "rollout_and_planner_sensitivity"),
        ("zero_context_far_below_mlp", "trunk_capacity"),
    )
    fired = [name for name, _choice in order if flags.get(name)]
    choice = next((choice for name, choice in order if flags.get(name)), "insufficient_pattern")
    return {"patterns": fired, "next_intervention": choice, "coexisting": fired[1:] if fired else []}


def _mean(xs: list[float]) -> float:
    vals = [float(x) for x in xs if np.isfinite(x)]
    return float(np.mean(vals)) if vals else float("nan")


def run_context_diagnosis(
    *,
    smoke: bool = False,
    config_path: str | Path = CONFIG_PATH,
    artifact_path: str | Path | None = None,
    plot_prediction: str | Path | None = None,
    plot_control: str | Path | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cfg = load_diagnosis_config(config_path)
    assert_context_physics_disjoint()
    executed = dict(cfg)
    if smoke:
        executed.update(
            {
                "n_seeds": 1,
                "episodes": 1,
                "updates": 2,
                "source_per_task": 220,
                "budgets": [0, 16],
                "smoke": True,
                "n_source_tasks": 2,
                "n_dev_tasks": 1,
            }
        )
    else:
        executed["smoke"] = False
        executed["n_source_tasks"] = 8
        executed["n_dev_tasks"] = 3
    budgets = tuple(int(b) for b in executed["budgets"])
    horizons = [int(h) for h in cfg["rollout_horizons"]]
    hi = int(cfg["primary_hi"])
    deadline = t0 + float(cfg["time_limit_s"])
    source_specs = pendulum_context_train()[: int(executed["n_source_tasks"])]
    dev_specs = pendulum_context_development()[: int(executed["n_dev_tasks"])]
    confirm_hash = _split_hash(pendulum_context_confirmation())
    per_task_n = int(executed["source_per_task"])
    epochs = int(cfg["source_epochs"]) if not smoke else 1
    updates = int(executed["updates"])
    n_seeds = int(executed["n_seeds"])
    episodes = int(executed["episodes"])
    ft_epochs = int(cfg["ft_epochs"]) if not smoke else 1
    diag_support_n = 128 if not smoke else 32
    diag_query_n = 400 if not smoke else 220

    def timed_out() -> bool:
        return time.perf_counter() > deadline

    resources = {
        "source_train_env": 0,
        "source_val_env": 0,
        "diagnostic_support_env": 0,
        "diagnostic_query_env": 0,
        "target_prefix_env": 0,
        "eval_env_executed": 0,
        "imagined_executed": 0,
        "mlp_wall_s": 0.0,
        "ctx_fixed_wall_s": 0.0,
        "ctx_variable_wall_s": 0.0,
    }
    data_hashes: dict[str, Any] = {}
    incomplete = False

    def grab(spec: Any, n: int, env0: int, base: int, bucket: str) -> TransitionDataset:
        ds = _collect(spec, n, env0=env0, base=base)
        resources[bucket] += int(ds.env_interactions)
        return ds

    source_support = [
        grab(spec, diag_support_n, DIAG_SUPPORT_ENV + 10 * i, 196_000 + i, "diagnostic_support_env")
        for i, spec in enumerate(source_specs)
    ]
    source_query = [
        complete_episodes(
            grab(spec, diag_query_n, DIAG_QUERY_ENV + 10 * i, 197_000 + i, "diagnostic_query_env"),
            16,
        )
        for i, spec in enumerate(source_specs)
    ]
    dev_support = [
        grab(spec, diag_support_n, DIAG_SUPPORT_ENV + 400 + 10 * i, 196_500 + i, "diagnostic_support_env")
        for i, spec in enumerate(dev_specs)
    ]
    dev_query = [
        complete_episodes(
            grab(spec, diag_query_n, DIAG_QUERY_ENV + 400 + 10 * i, 197_500 + i, "diagnostic_query_env"),
            16,
        )
        for i, spec in enumerate(dev_specs)
    ]
    data_hashes["diagnostic_support"] = [prefix_hash(ds, len(ds)) for ds in source_support + dev_support]
    data_hashes["diagnostic_query"] = [prefix_hash(ds, len(ds)) for ds in source_query + dev_query]
    assert_disjoint_seeds(*source_support, *source_query, *dev_support, *dev_query)

    per_seed: list[dict[str, Any]] = []
    for s in range(n_seeds):
        if timed_out():
            incomplete = True
            break
        tasks = [
            grab(spec, per_task_n, 1000 + 100 * s + 10 * i, V089C_SOURCE_COLLECT_SEED + 50 * s + 9 * i, "source_train_env")
            for i, spec in enumerate(source_specs)
        ]
        val_parts = [
            grab(spec, 32 if not smoke else 16, 3000 + 50 * s + 10 * i, V089C_SOURCE_COLLECT_SEED + 800 + 20 * s + i, "source_val_env")
            for i, spec in enumerate(source_specs)
        ]
        prefixes = {
            spec.task_id: grab(spec, 1024 if not smoke else 32, 5000 + 50 * s + 10 * i, V089C_PREFIX_SEED + 100 * s + i, "target_prefix_env")
            for i, spec in enumerate(dev_specs)
        }
        assert_disjoint_seeds(*tasks, *val_parts, *prefixes.values(), *source_support, *source_query, *dev_support, *dev_query)
        val = concat_datasets(*val_parts, task_id="context_source_val")
        data_hashes[f"seed{s}_train"] = [prefix_hash(ds, len(ds)) for ds in tasks]
        data_hashes[f"seed{s}_prefix"] = {k: {str(b): prefix_hash(ds, b) for b in budgets} for k, ds in prefixes.items()}
        t_prep = time.perf_counter()
        rms = _fit_rms(tasks)
        prep_wall = time.perf_counter() - t_prep
        pooled = concat_datasets(*tasks, task_id="context_source_pool")
        t_mlp = time.perf_counter()
        mlp, slog = train_world_model(
            pooled, val, kind=FROZEN_KIND, epochs=epochs, batch_size=int(cfg["mlp_batch"]),
            seed=V089C_TRAIN_SEED + int(s), hidden=FROZEN_HIDDEN, n_actions=3, obs_rms=rms,
        )
        mlp_wall = time.perf_counter() - t_mlp
        resources["mlp_wall_s"] += mlp_wall
        final_mlp = mlp.clone()
        final_mlp.net.load_state_dict(mlp.final_state)
        init_seed = V089C_TRAIN_SEED + 17 * int(s)
        base = ContextWorldModel.create(3, 3, seed=init_seed)
        base.copy_rms(rms)
        variable = base.clone_trainable()
        schedule = make_context_schedule(tasks, updates=updates, seed=V089C_TRAIN_SEED + 31 * int(s), batch=int(cfg["query_batch"]), empty_prob=float(cfg["empty_prob"]))
        t_fixed = time.perf_counter()
        fixed_log = train_context_model(base, tasks, updates=updates, seed=0, schedule=schedule, support_mode="fixed", batch=int(cfg["query_batch"]))
        resources["ctx_fixed_wall_s"] += time.perf_counter() - t_fixed
        t_var = time.perf_counter()
        variable_log = train_context_model(variable, tasks, updates=updates, seed=0, schedule=schedule, support_mode="variable", batch=int(cfg["query_batch"]))
        resources["ctx_variable_wall_s"] += time.perf_counter() - t_var
        models = {"fixed": base, "variable": variable}

        def prediction_block(group: str, specs: tuple[Any, ...], supports: list[TransitionDataset], queries: list[TransitionDataset], donors: list[TransitionDataset]) -> dict[str, Any]:
            out: dict[str, Any] = {}
            for i, spec in enumerate(specs):
                if timed_out():
                    raise TimeoutError
                rows: dict[str, Any] = {}
                for b in budgets:
                    conds: dict[str, Any] = {}
                    for mode, model in models.items():
                        real_m = model.clone_frozen()
                        real_m.set_context_from_dataset(supports[i], budget=b)
                        zero_m = model.clone_frozen()
                        zero_m.clear_context()
                        wrong_m = model.clone_frozen()
                        if b <= 0:
                            wrong_m.clear_context()
                        else:
                            wrong_m.set_context_from_dataset(donors[i], budget=b)
                        conds[mode] = {
                            "real": _predict(real_m, queries[i], horizons),
                            "zero": _predict(zero_m, queries[i], horizons),
                            "wrong": _predict(wrong_m, queries[i], horizons),
                            "context": _z_stats(model, supports[i], donors[i], b),
                        }
                    frozen_err = _predict(mlp, queries[i], horizons)
                    if b <= 0:
                        ft_model = mlp
                    else:
                        ft_model, _meta = _ft(mlp, supports[i], b, epochs=ft_epochs, seed=V089C_TRAIN_SEED + 1000 + b)
                    conds["mlp_frozen"] = frozen_err
                    conds["mlp_ft"] = _predict(ft_model, queries[i], horizons)
                    if b == 0:
                        conds["mlp_final_secondary"] = _predict(final_mlp, queries[i], horizons)
                    rows[str(b)] = conds
                out[spec.task_id] = {"params": dict(spec.params), "query_hash": prefix_hash(queries[i], len(queries[i])), "budgets": rows}
            return out

        source_donors = [source_support[(i + 1) % len(source_support)] for i in range(len(source_support))]
        dev_donors = [source_support[0] for _spec in dev_specs]
        try:
            pred_source = prediction_block("source", source_specs, source_support, source_query, source_donors)
            pred_dev = prediction_block("dev", dev_specs, dev_support, dev_query, dev_donors)
        except TimeoutError:
            incomplete = True
            pred_source, pred_dev = {}, {}

        curves: dict[str, Any] = {}
        control_resources: dict[str, Any] = {}
        if not incomplete:
            cache: dict[tuple[str, str], dict[str, Any]] = {}

            def evaluate(spec: Any, model: Any, key: str) -> tuple[dict[str, Any], int, int, bool]:
                if key in cache:
                    return cache[key], 0, 0, True
                ev = _eval(spec, model, seed=int(cfg["eval_seed"]), episodes=episodes)
                cache[key] = ev
                resources["eval_env_executed"] += int(ev["env_interactions"])
                resources["imagined_executed"] += int(ev["model_states"])
                return ev, int(ev["env_interactions"]), int(ev["model_states"]), False

            for spec in dev_specs:
                if timed_out():
                    incomplete = True
                    break
                prefix = prefixes[spec.task_id]
                task_curves: dict[str, list[float]] = {}
                for b in budgets:
                    if timed_out():
                        incomplete = True
                        break
                    built: dict[str, tuple[Any, str]] = {"mlp_frozen": (mlp, f"{spec.task_id}:mlp_frozen")}
                    if b == 0:
                        built["mlp_ft"] = (mlp, f"{spec.task_id}:mlp_frozen")
                        built["mlp_final_secondary"] = (final_mlp, f"{spec.task_id}:mlp_final")
                    else:
                        ft_model, _meta = _ft(mlp, prefix, b, epochs=ft_epochs, seed=V089C_TRAIN_SEED + 3000 * s + b)
                        built["mlp_ft"] = (ft_model, f"{spec.task_id}:mlp_ft:{b}")
                    for mode, model in models.items():
                        zero_m = model.clone_frozen()
                        zero_m.clear_context()
                        built[f"{mode}_zero"] = (zero_m, f"{spec.task_id}:{mode}_zero")
                        if b == 0:
                            built[f"{mode}_real"] = (zero_m, f"{spec.task_id}:{mode}_zero")
                            built[f"{mode}_wrong"] = (zero_m, f"{spec.task_id}:{mode}_zero")
                        else:
                            real_m = model.clone_frozen()
                            real_m.set_context_from_dataset(prefix, budget=b)
                            wrong_m = model.clone_frozen()
                            wrong_m.set_context_from_dataset(tasks[0], budget=b)
                            built[f"{mode}_real"] = (real_m, f"{spec.task_id}:{mode}_real:{b}")
                            built[f"{mode}_wrong"] = (wrong_m, f"{spec.task_id}:{mode}_wrong:{b}")
                    for name, (model, key) in built.items():
                        ev, executed_env, executed_im, cached = evaluate(spec, model, key)
                        task_curves.setdefault(name, []).append(float(ev["mean_return"]))
                        control_resources.setdefault(spec.task_id, {}).setdefault(str(b), {})[name] = {
                            "eval_env_executed": executed_env,
                            "imagined_executed": executed_im,
                            "cached": cached,
                        }
                primary = ("mlp_frozen", "mlp_ft", "fixed_real", "fixed_zero", "fixed_wrong", "variable_real", "variable_zero", "variable_wrong")
                if incomplete or any(len(task_curves.get(name, [])) != len(budgets) for name in primary):
                    incomplete = True
                    break
                curves[spec.task_id] = {
                    "params": dict(spec.params),
                    "curve": task_curves,
                    "auc": {name: norm_auc(budgets, task_curves[name], hi) for name in primary},
                    "budget0": {name: task_curves[name][0] for name in task_curves if task_curves[name]},
                    "mlp_final_secondary_budget0": task_curves.get("mlp_final_secondary", [None])[0],
                }
        per_seed.append(
            {
                "model_seed": s,
                "prep_wall_s": prep_wall,
                "mlp_wall_s": mlp_wall,
                "mlp_updates": _mlp_updates(len(pooled), epochs, int(cfg["mlp_batch"])),
                "fixed_log": fixed_log,
                "variable_log": variable_log,
                "params_mlp": sum(int(p.numel()) for p in mlp.net.parameters()),
                "params_ctx": base.n_parameters(),
                "nbytes_mlp": checkpoint_nbytes(mlp),
                "nbytes_ctx": int(sum(p.numel() * p.element_size() for p in list(base.encoder.parameters()) + list(base.net.parameters()))),
                "checkpoint_asymmetry": "MLP returns the best source-validation weights. Context models return the final update. mlp_final_secondary is the last MLP epoch and is not the primary baseline.",
                "prediction_source": pred_source,
                "prediction_dev": pred_dev,
                "control": curves,
                "control_resources": control_resources,
            }
        )
        print(f"context_diagnosis seed={s} smoke={smoke}", flush=True)
        if incomplete:
            break

    summary = _summarize(per_seed, budgets, hi)
    head = _git_meta()
    sha = str(head.get("revision") or "")
    source_status = inspect_source_tree(sha) if sha else {"source_dirty": True}
    payload = {
        "protocol": {
            "code_version": "context_adaptation_diagnosis",
            "config": cfg,
            "executed": {k: executed[k] for k in executed if k != "config"},
            "smoke": bool(smoke),
            "primary_metric": cfg["primary_metric"],
            "not_the_original_primary": "0-256 AUC from the context-adaptation pilot is unchanged and is not recomputed here.",
            "prior_negative": {"mlp_ft": -453.6, "ctx_real": -755.3, "ctx_zero": -651.9, "ctx_wrong": -725.3},
            "donor_prediction": cfg["prediction_donor"],
            "donor_control": cfg["control_wrong_donor"],
            "confirm_hash": confirm_hash,
            "confirm_evaluated": False,
            "confirmation_unlocked": False,
            "implementation_sha": sha if not source_status.get("source_dirty") else None,
            "source_dirty": bool(source_status.get("source_dirty", True)),
            "git": head,
            "is_agi": False,
            "hypotheses": {"H-length": cfg.get("h_length"), "H-context": cfg.get("h_context")},
        },
        "data_hashes": data_hashes,
        "resources": resources,
        "summary": summary,
        "per_seed": per_seed,
        "incomplete": True if smoke else bool(incomplete),
        "declared_complete": (not smoke) and (not incomplete),
        "smoke": bool(smoke),
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
    }
    if plot_prediction and per_seed and per_seed[0].get("prediction_dev"):
        _prediction_plot(Path(plot_prediction), per_seed, budgets)
    if plot_control and per_seed and per_seed[0].get("control"):
        _control_plot(Path(plot_control), per_seed, budgets)
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload


def _mae(block: dict[str, Any], mode: str, kind: str, budget: str) -> list[float]:
    vals = []
    for task in block.values():
        row = task["budgets"].get(budget, {})
        if mode in ("fixed", "variable"):
            cell = row.get(mode, {}).get(kind, {})
            if "mae" in cell:
                vals.append(float(cell["mae"]))
        elif kind in row and isinstance(row[kind], dict) and "mae" in row[kind]:
            vals.append(float(row[kind]["mae"]))
    return vals


def _summarize(per_seed: list[dict[str, Any]], budgets: tuple[int, ...], hi: int) -> dict[str, Any]:
    def seed_mae(group: str, mode: str, kind: str, budget: int) -> list[float]:
        out = []
        for seed in per_seed:
            block = seed.get("prediction_source" if group == "source" else "prediction_dev") or {}
            vals = _mae(block, mode, kind, str(budget))
            if vals:
                out.append(_mean(vals))
        return out

    prediction = {"source": {}, "development": {}}
    for group, dest in (("source", prediction["source"]), ("development", prediction["development"])):
        for mode in ("fixed", "variable"):
            dest[mode] = {}
            for kind in ("real", "zero", "wrong"):
                dest[mode][kind] = {str(b): seed_level_ci(seed_mae(group, mode, kind, b)) if len(seed_mae(group, mode, kind, b)) >= 2 else {"n": len(seed_mae(group, mode, kind, b)), "mean": _mean(seed_mae(group, mode, kind, b))} for b in budgets}
        for kind in ("mlp_frozen", "mlp_ft", "mlp_final_secondary"):
            dest[kind] = {str(b): {"n": len(seed_mae(group, kind, kind, b)), "mean": _mean(seed_mae(group, kind, kind, b))} for b in budgets}

    def aucs(name: str) -> list[float]:
        vals = []
        for seed in per_seed:
            rows = [task["auc"][name] for task in seed.get("control", {}).values() if name in task.get("auc", {})]
            if rows:
                vals.append(_mean(rows))
        return vals

    names = ("mlp_frozen", "mlp_ft", "fixed_real", "fixed_zero", "fixed_wrong", "variable_real", "variable_zero", "variable_wrong")
    control_auc = {}
    for name in names:
        xs = aucs(name)
        control_auc[name] = seed_level_ci(xs) if len(xs) >= 2 else {"n": len(xs), "mean": _mean(xs)}

    def delta(a: str, b: str) -> dict[str, Any]:
        paired = []
        for seed in per_seed:
            aa = [task["auc"][a] for task in seed.get("control", {}).values() if a in task.get("auc", {}) and b in task.get("auc", {})]
            bb = [task["auc"][b] for task in seed.get("control", {}).values() if a in task.get("auc", {}) and b in task.get("auc", {})]
            if aa and bb:
                paired.append(_mean(aa) - _mean(bb))
        return seed_level_ci(paired) if len(paired) >= 2 else {"n": len(paired), "mean": _mean(paired)}

    deltas = {
        "variable_real_minus_fixed_real": delta("variable_real", "fixed_real"),
        "fixed_real_minus_fixed_zero": delta("fixed_real", "fixed_zero"),
        "fixed_real_minus_fixed_wrong": delta("fixed_real", "fixed_wrong"),
        "variable_real_minus_variable_zero": delta("variable_real", "variable_zero"),
        "variable_real_minus_variable_wrong": delta("variable_real", "variable_wrong"),
        "fixed_real_minus_mlp_ft": delta("fixed_real", "mlp_ft"),
        "variable_real_minus_mlp_ft": delta("variable_real", "mlp_ft"),
    }
    flags = _flags(per_seed, budgets)
    return {
        "prediction_mae": prediction,
        "control_auc_0_128": control_auc,
        "deltas": deltas,
        "flags": flags,
        "interpretation": interpret_diagnosis(flags),
        "interval": "exploratory_student_t_across_training_seeds",
    }


def _flags(per_seed: list[dict[str, Any]], budgets: tuple[int, ...]) -> dict[str, bool]:
    def mae(group: str, mode: str, kind: str, budget: int) -> float:
        vals = []
        for seed in per_seed:
            block = seed.get("prediction_source" if group == "source" else "prediction_dev") or {}
            vals.extend(_mae(block, mode, kind, str(budget)))
        return _mean(vals)

    positive = [b for b in budgets if b > 0]

    def across(group: str, kind: str) -> float:
        return _mean([mae(group, "fixed", kind, b) for b in positive])

    source_real_fails = across("source", "real") >= across("source", "zero") or across("source", "real") >= across("source", "wrong")
    source_helps = across("source", "real") < across("source", "zero") and across("source", "real") < across("source", "wrong")
    dev_fails = across("dev", "real") >= across("dev", "zero") or across("dev", "real") >= across("dev", "wrong")
    short = [b for b in (16, 32) if b in budgets]
    var_helps = False
    if short and per_seed and per_seed[0].get("control"):
        gains = []
        for b in short:
            bi = list(budgets).index(b)
            for seed in per_seed:
                for task in seed.get("control", {}).values():
                    if len(task["curve"].get("variable_real", [])) > bi and len(task["curve"].get("fixed_real", [])) > bi:
                        gains.append(task["curve"]["variable_real"][bi] - task["curve"]["fixed_real"][bi])
        var_helps = bool(gains) and _mean(gains) > 0
    pred_better = bool(positive) and across("dev", "real") < across("dev", "zero")
    control_worse = False
    if per_seed and per_seed[0].get("control"):
        gaps = []
        for seed in per_seed:
            for task in seed.get("control", {}).values():
                if "fixed_real" in task.get("auc", {}) and "fixed_zero" in task.get("auc", {}):
                    gaps.append(task["auc"]["fixed_real"] - task["auc"]["fixed_zero"])
        control_worse = bool(gaps) and _mean(gaps) < 0
    trunk_gap = []
    for seed in per_seed:
        for task in seed.get("control", {}).values():
            if task.get("budget0") and "fixed_zero" in task["budget0"] and "mlp_frozen" in task["budget0"]:
                trunk_gap.append(task["budget0"]["fixed_zero"] - task["budget0"]["mlp_frozen"])
    return {
        "real_context_fails_source_prediction": bool(positive) and source_real_fails,
        "source_prediction_helps_but_development_does_not": bool(positive) and source_helps and dev_fails,
        "variable_length_helps_short_histories": var_helps,
        "prediction_improves_but_control_worsens": bool(positive) and pred_better and control_worse,
        "zero_context_far_below_mlp": bool(trunk_gap) and _mean(trunk_gap) < -50,
    }


def _prediction_plot(path: Path, per_seed: list[dict[str, Any]], budgets: tuple[int, ...]) -> None:
    series: dict[str, list[float]] = {}
    bands: dict[str, list[tuple[float, float]]] = {}
    for label, mode, kind in (
        ("fixed_real", "fixed", "real"),
        ("fixed_zero", "fixed", "zero"),
        ("fixed_wrong", "fixed", "wrong"),
        ("variable_real", "variable", "real"),
        ("mlp_ft", "mlp_ft", "mlp_ft"),
    ):
        acc = []
        band = []
        for b in budgets:
            seed_means = []
            for seed in per_seed:
                vals = _mae(seed.get("prediction_dev") or {}, mode, kind, str(b))
                if vals:
                    seed_means.append(_mean(vals))
            acc.append(_mean(seed_means))
            band.append((float(np.min(seed_means)), float(np.max(seed_means))) if seed_means else (float("nan"), float("nan")))
        series[label] = acc
        bands[label] = band
    _svg(path, list(budgets), series, bands)


def _control_plot(path: Path, per_seed: list[dict[str, Any]], budgets: tuple[int, ...]) -> None:
    series: dict[str, list[float]] = {}
    bands: dict[str, list[tuple[float, float]]] = {}
    for name in ("mlp_frozen", "mlp_ft", "fixed_real", "fixed_zero", "fixed_wrong", "variable_real"):
        acc = []
        band = []
        for i, _b in enumerate(budgets):
            seed_means = []
            for seed in per_seed:
                vals = [task["curve"][name][i] for task in seed.get("control", {}).values() if len(task["curve"].get(name, [])) > i]
                if vals:
                    seed_means.append(_mean(vals))
            acc.append(_mean(seed_means))
            band.append((float(np.min(seed_means)), float(np.max(seed_means))) if seed_means else (float("nan"), float("nan")))
        series[name] = acc
        bands[name] = band
    _svg(path, list(budgets), series, bands)
