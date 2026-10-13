"""Bounded source-prediction diagnostic: does more Adam training make context useful?

No MPC. No confirmation physics. Not learning-to-learn.
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

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import pendulum_context_train
from nexus.world.confirm_guard import inspect_source_tree
from nexus.world.context_diagnosis import ROLLOUT_STARTS, complete_episodes, open_loop_mae
from nexus.world.context_model import (
    ContextWorldModel,
    context_optimizer,
    make_context_schedule,
    run_context_updates,
)
from nexus.world.context_pilot import _collect, _fit_rms, _svg, prefix_hash
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, concat_datasets
from nexus.world.dynamics import WorldModel
from nexus.world.protocol import V089C_SOURCE_COLLECT_SEED, V089C_TRAIN_SEED
from nexus.world.result_checks import completeness_report
from nexus.world.train import one_step_errors, train_mlp_updates
from nexus.world.v085 import _git_meta

CONFIG_PATH = Path("configs/context_optimization_diagnostic.yaml")
CHECKPOINT_DIR = Path("artifacts/context_optimization_checkpoints")
ANGVEL_INDEX = 2


def load_optimization_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    if not isinstance(cfg, dict):
        raise ValueError("optimization config must be a mapping")
    required = {
        "protocol_id": "context_optimization_diagnostic_v1",
        "starting_sha": "462b388e24933842297ea9719ed1c9dc5b3902bd",
        "confirmation_unlocked": False,
        "control_sweep": False,
        "updates": [300, 1000, 3000],
        "total_updates": 3000,
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
        "audit_support_env0": 20000,
        "audit_query_env0": 24000,
        "audit_support_base": 210000,
        "audit_query_base": 211000,
    }
    for key, expected in required.items():
        if cfg.get(key) != expected:
            raise ValueError(f"config {key}={cfg.get(key)!r} does not match the locked setting {expected!r}")
    if cfg.get("is_agi") is not False or not str(cfg.get("h_optimization") or "").strip():
        raise ValueError("hypothesis must be stated and this run is not AGI")
    if list(cfg["rollout_starts"]) != list(ROLLOUT_STARTS):
        raise ValueError("rollout starts drifted from the shared evaluator")
    return cfg


def choose_checkpoint(scores: dict[int, float]) -> int:
    """Lowest mean angular-velocity MAE. Exact ties prefer fewer updates."""
    if not scores:
        raise ValueError("no checkpoint scores")
    return sorted(scores, key=lambda u: (float(scores[u]), int(u)))[0]


def assert_audit_allowed(selection_record: dict[str, Any] | None) -> None:
    if not isinstance(selection_record, dict) or selection_record.get("selection_recorded") is not True:
        raise RuntimeError("source audit is blocked until checkpoint selection is recorded")
    if "chosen_updates" not in selection_record:
        raise RuntimeError("source audit is blocked until the chosen checkpoint is recorded")


def optimization_screen(per_seed: list[dict[str, float]], *, improvement: float = 0.05, min_positive_seeds: int = 2, max_worsening: float = 0.05) -> dict[str, Any]:
    """Development screen on independent audit. Not a proof of generalization."""
    if len(per_seed) < 1:
        return {"pass": False, "reason": "no audit seeds"}
    real = float(np.mean([s["angvel_real"] for s in per_seed]))
    zero = float(np.mean([s["angvel_zero"] for s in per_seed]))
    wrong = float(np.mean([s["angvel_wrong"] for s in per_seed]))
    mae_real = float(np.mean([s["mae_real"] for s in per_seed]))
    mae_zero = float(np.mean([s["mae_zero"] for s in per_seed]))
    h_real = float(np.mean([s["h16_real"] for s in per_seed]))
    h_zero = float(np.mean([s["h16_zero"] for s in per_seed]))
    positive = 0
    for s in per_seed:
        if (s["angvel_zero"] - s["angvel_real"]) > 0 and (s["angvel_wrong"] - s["angvel_real"]) > 0:
            positive += 1
    angvel_ok = real <= (1.0 - improvement) * zero and real <= (1.0 - improvement) * wrong
    harm_ok = mae_real <= (1.0 + max_worsening) * mae_zero and h_real <= (1.0 + max_worsening) * h_zero
    return {
        "pass": bool(angvel_ok and positive >= min_positive_seeds and harm_ok),
        "angvel_real": real,
        "angvel_zero": zero,
        "angvel_wrong": wrong,
        "positive_seeds": positive,
        "angvel_ok": bool(angvel_ok),
        "harm_ok": bool(harm_ok),
        "thresholds": {"improvement": improvement, "min_positive_seeds": min_positive_seeds, "max_worsening": max_worsening},
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _episode_prediction(model: Any, query: TransitionDataset, horizons: list[int], angvel_index: int) -> dict[str, Any]:
    z0 = getattr(model, "z", None)
    if z0 is not None:
        z0 = z0.detach().clone()
    n0 = getattr(model, "n_encodes", None)
    episodes = []
    for eid in np.unique(query.episode_id):
        sl = query.slice(np.flatnonzero(query.episode_id == eid))
        err = one_step_errors(model, sl)
        episodes.append(
            {
                "episode_id": int(eid),
                "n": int(err["n"]),
                "mae": float(err["mae"]),
                "rmse": float(err["rmse"]),
                "mae_per_dim": [float(x) for x in err["mae_per_dim"]],
                "angvel_mae": float(err["mae_per_dim"][angvel_index]),
            }
        )
    roll = open_loop_mae(model, query, horizons)
    if z0 is not None and not torch.equal(model.z, z0):
        raise RuntimeError("query evaluation updated context")
    if n0 is not None and int(model.n_encodes) != int(n0):
        raise RuntimeError("query evaluation encoded a new context")

    def avg(key: str) -> float:
        return float(np.mean([row[key] for row in episodes])) if episodes else float("nan")

    dims = np.mean([row["mae_per_dim"] for row in episodes], axis=0) if episodes else np.full(3, np.nan)
    return {
        "episodes": episodes,
        "mae": avg("mae"),
        "rmse": avg("rmse"),
        "mae_per_dim": [float(x) for x in dims],
        "angvel_mae": avg("angvel_mae"),
        "rollout_mae": {h: float(roll[str(h)]) for h in horizons},
        "rollout_counts": {
            "n_episodes": roll["n_episodes"],
            "n_windows": roll["n_windows"],
            **{k: roll[k] for k in roll if str(k).startswith("windows_") or str(k).startswith("episodes_used_")},
        },
    }


def _context_bundle(model: ContextWorldModel, support: TransitionDataset, donor: TransitionDataset, query: TransitionDataset, budget: int, horizons: list[int], angvel_index: int) -> dict[str, Any]:
    out = {}
    specs = {"real": support, "wrong": donor}
    for name, ds in specs.items():
        probe = model.clone_frozen()
        probe.set_context_from_dataset(ds, budget=budget)
        out[name] = _episode_prediction(probe, query, horizons, angvel_index)
    zero = model.clone_frozen()
    zero.clear_context()
    out["zero"] = _episode_prediction(zero, query, horizons, angvel_index)
    return out


def _save_torch(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    return _sha256(path)


def run_context_optimization(
    *,
    smoke: bool = False,
    config_path: str | Path = CONFIG_PATH,
    selection_path: str | Path | None = None,
    audit_path: str | Path | None = None,
    plot_path: str | Path | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cfg = load_optimization_config(config_path)
    checkpoints = [int(u) for u in cfg["updates"]]
    total = int(cfg["total_updates"])
    n_seeds = int(cfg["n_seeds"])
    n_tasks = int(cfg["n_source_tasks"])
    per_task = int(cfg["source_per_task"])
    if smoke:
        checkpoints = [2, 4]
        total = 4
        n_seeds = 1
        n_tasks = 2
        per_task = 220
    deadline = t0 + float(cfg["time_limit_s"])
    horizons = [int(h) for h in cfg["horizons"]]
    budget = int(cfg["support_budget"]) if not smoke else 32
    angvel_index = int(cfg["angular_velocity_index"])
    specs = pendulum_context_train()[:n_tasks]
    incomplete = False

    def timed_out() -> bool:
        return time.perf_counter() > deadline

    resources = {
        "source_train_env": 0,
        "source_val_env": 0,
        "selection_support_env": 0,
        "selection_query_env": 0,
        "audit_support_env": 0,
        "audit_query_env": 0,
        "context_wall_s": 0.0,
        "mlp_wall_s": 0.0,
        "context_support_examples": 0,
        "context_query_examples": 0,
        "mlp_examples": 0,
    }
    data_hashes: dict[str, Any] = {}

    def grab(spec: Any, n: int, env0: int, base: int, bucket: str) -> TransitionDataset:
        ds = _collect(spec, n, env0=env0, base=base)
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
        previous = json.loads(Path("artifacts/context_adaptation_diagnosis.json").read_text())
        prev_support = previous["data_hashes"]["diagnostic_support"][:n_tasks]
        prev_query = previous["data_hashes"]["diagnostic_query"][:n_tasks]
        if data_hashes["selection_support"] != prev_support or data_hashes["selection_query"] != prev_query:
            raise RuntimeError("selection split does not match the recorded diagnostic support/query hashes")
        data_hashes["selection_reused_from"] = "artifacts/context_adaptation_diagnosis.json"

    per_seed: list[dict[str, Any]] = []
    checkpoint_files: dict[str, str] = {}
    for s in range(n_seeds):
        if timed_out():
            incomplete = True
            break
        tasks = [
            grab(spec, per_task, 1000 + 100 * s + 10 * i, V089C_SOURCE_COLLECT_SEED + 50 * s + 9 * i, "source_train_env")
            for i, spec in enumerate(specs)
        ]
        val_parts = [
            grab(spec, 32 if not smoke else 16, 3000 + 50 * s + 10 * i, V089C_SOURCE_COLLECT_SEED + 800 + 20 * s + i, "source_val_env")
            for i, spec in enumerate(specs)
        ]
        assert_disjoint_seeds(*tasks, *val_parts, *selection_support, *selection_query)
        data_hashes[f"seed{s}_train"] = [prefix_hash(ds, len(ds)) for ds in tasks]
        if not smoke:
            prev_train = previous["data_hashes"][f"seed{s}_train"]
            if data_hashes[f"seed{s}_train"] != prev_train:
                raise RuntimeError(f"source training hash mismatch for seed {s}")
        rms = _fit_rms(tasks)
        pooled = concat_datasets(*tasks, task_id="context_source_pool")
        schedule = make_context_schedule(
            tasks, updates=total, seed=V089C_TRAIN_SEED + 31 * int(s), batch=int(cfg["batch"]), empty_prob=float(cfg["empty_prob"])
        )
        reference = make_context_schedule(
            tasks, updates=min(300, total) if not smoke else total, seed=V089C_TRAIN_SEED + 31 * int(s), batch=int(cfg["batch"]), empty_prob=float(cfg["empty_prob"])
        )
        if not smoke:
            for row, ref in zip(schedule[:300], reference):
                if int(row["task_index"]) != int(ref["task_index"]) or row["query_index"].tolist() != ref["query_index"].tolist():
                    raise RuntimeError("the first 300 scheduled updates do not reproduce the fixed-length schedule")
        ctx = ContextWorldModel.create(3, 3, seed=V089C_TRAIN_SEED + 17 * int(s))
        ctx.copy_rms(rms)
        opt = context_optimizer(ctx, lr=float(cfg["lr"]))
        initial = torch.cat([p.detach().flatten().clone() for p in ctx.encoder.parameters()])
        ctx_snaps: dict[int, dict[str, Any]] = {}
        ctx_logs: dict[str, Any] = {}
        cursor = 0
        support_total = 0
        query_total = 0
        t_ctx = time.perf_counter()
        for target in checkpoints:
            log = run_context_updates(ctx, opt, tasks, schedule[cursor:target], support_mode="fixed")
            support_total += int(log["support_examples"])
            query_total += int(log["query_examples"])
            now = torch.cat([p.detach().flatten() for p in ctx.encoder.parameters()])
            ctx_snaps[target] = {
                "encoder": {k: v.detach().cpu().clone() for k, v in ctx.encoder.state_dict().items()},
                "net": {k: v.detach().cpu().clone() for k, v in ctx.net.state_dict().items()},
                "optimizer": copy.deepcopy(opt.state_dict()),
            }
            ctx_logs[str(target)] = {
                **{k: log[k] for k in ("optimizer_updates", "query_examples", "support_examples", "mean_encoder_grad_norm", "mean_state_loss", "mean_term_loss")},
                "cumulative_support_examples": support_total,
                "cumulative_query_examples": query_total,
                "encoder_l2_from_init": float(torch.linalg.vector_norm(now - initial).item()),
            }
            cursor = target
        resources["context_wall_s"] += time.perf_counter() - t_ctx
        resources["context_support_examples"] += support_total
        resources["context_query_examples"] += query_total
        t_mlp = time.perf_counter()
        _mlp_live, _mlp_opt, mlp_snaps, mlp_hist = train_mlp_updates(
            pooled, updates=total, snapshot_at=checkpoints, seed=V089C_TRAIN_SEED + int(s),
            batch_size=int(cfg["batch"]), lr=float(cfg["lr"]), hidden=tuple(cfg["mlp_hidden"]), obs_rms=rms,
        )
        resources["mlp_wall_s"] += time.perf_counter() - t_mlp
        resources["mlp_examples"] += int(total * int(cfg["batch"]))
        for step, snap in ctx_snaps.items():
            path = CHECKPOINT_DIR / f"seed{s}_context_u{step}.pt"
            checkpoint_files[str(path)] = _save_torch(path, {"encoder": snap["encoder"], "net": snap["net"], "obs_rms": rms.state_dict()})
            opt_path = CHECKPOINT_DIR / f"seed{s}_context_opt_u{step}.pt"
            checkpoint_files[str(opt_path)] = _save_torch(opt_path, {"optimizer": snap["optimizer"]})
        for step, snap in mlp_snaps.items():
            path = CHECKPOINT_DIR / f"seed{s}_mlp_u{step}.pt"
            checkpoint_files[str(path)] = _save_torch(path, {"net": snap, "obs_rms": rms.state_dict()})

        def context_at(step: int) -> ContextWorldModel:
            model = ContextWorldModel.create(3, 3, seed=0)
            model.encoder.load_state_dict(ctx_snaps[step]["encoder"])
            model.net.load_state_dict(ctx_snaps[step]["net"])
            model.copy_rms(rms)
            return model.clone_frozen()

        def mlp_at(step: int) -> WorldModel:
            model = WorldModel.create(3, 3, kind="residual", hidden=tuple(cfg["mlp_hidden"]), seed=0, arch="mlp")
            model.net.load_state_dict(mlp_snaps[step])
            model.copy_rms(rms)
            model.net.eval()
            return model

        selection_rows: dict[str, Any] = {}
        donors = [selection_support[(i + 1) % len(selection_support)] for i in range(len(specs))]
        for step in checkpoints:
            if timed_out():
                incomplete = True
                break
            task_rows = {}
            ctx_model = context_at(step)
            mlp_model = mlp_at(step)
            for i, spec in enumerate(specs):
                bundle = _context_bundle(ctx_model, selection_support[i], donors[i], selection_query[i], budget, horizons, angvel_index)
                bundle["mlp"] = _episode_prediction(mlp_model, selection_query[i], horizons, angvel_index)
                task_rows[spec.task_id] = {"params": dict(spec.params), "donor_task": specs[(i + 1) % len(specs)].task_id, "metrics": bundle}
            segment = [row for row in mlp_hist if (checkpoints[checkpoints.index(step) - 1] if step != checkpoints[0] else 0) < row["update"] <= step]
            selection_rows[str(step)] = {
                "tasks": task_rows,
                "mlp_segment_state_loss": float(np.mean([row["state_loss"] for row in segment])) if segment else float("nan"),
                "mlp_segment_term_loss": float(np.mean([row["term_loss"] for row in segment])) if segment else float("nan"),
            }
        per_seed.append(
            {
                "model_seed": s,
                "context_logs": ctx_logs,
                "params_ctx": ctx.n_parameters(),
                "params_mlp": sum(int(p.numel()) for p in _mlp_live.net.parameters()),
                "selection": selection_rows,
                "schedule_prefix_matches_300": True,
            }
        )
        print(f"context_optimization seed={s} smoke={smoke}", flush=True)
        if incomplete:
            break

    scores: dict[int, float] = {}
    mlp_scores: dict[int, float] = {}
    if per_seed and not incomplete and all(str(u) in per_seed[0]["selection"] for u in checkpoints):
        for step in checkpoints:
            ctx_vals = []
            mlp_vals = []
            for seed in per_seed:
                tasks_block = seed["selection"][str(step)]["tasks"]
                ctx_vals.append(float(np.mean([task["metrics"]["real"]["angvel_mae"] for task in tasks_block.values()])))
                mlp_vals.append(float(np.mean([task["metrics"]["mlp"]["angvel_mae"] for task in tasks_block.values()])))
            scores[step] = float(np.mean(ctx_vals))
            mlp_scores[step] = float(np.mean(mlp_vals))
    chosen = choose_checkpoint(scores) if scores and all(np.isfinite(list(scores.values()))) else None
    mlp_chosen = choose_checkpoint(mlp_scores) if mlp_scores and all(np.isfinite(list(mlp_scores.values()))) else None
    head = _git_meta()
    sha = str(head.get("revision") or "")
    source_status = inspect_source_tree(sha) if sha else {"source_dirty": True}
    selection_record = {
        "selection_recorded": chosen is not None and not incomplete and not smoke,
        "chosen_updates": chosen,
        "chosen_rule": "lowest mean selection-set real-context angular-velocity MAE across seeds; ties prefer fewer updates",
        "scores_angvel_mae": {str(k): v for k, v in scores.items()},
        "mlp_own_chosen_updates": mlp_chosen,
        "mlp_own_rule": "same angular-velocity criterion on the MLP update-count snapshots; not a best-validation checkpoint",
        "mlp_scores_angvel_mae": {str(k): v for k, v in mlp_scores.items()},
        "smoke": bool(smoke),
        "incomplete": bool(incomplete) or bool(smoke),
    }
    selection_payload = {
        "protocol": _protocol(cfg, smoke, sha, source_status, checkpoints, total, n_seeds),
        "selection_record": selection_record,
        "data_hashes": data_hashes,
        "checkpoint_sha256": checkpoint_files,
        "checkpoint_dir": str(CHECKPOINT_DIR),
        "resources": dict(resources),
        "per_seed": per_seed,
        "summary": _selection_summary(per_seed, checkpoints),
        "wall_clock_s": time.perf_counter() - t0,
        "audit_evaluated": False,
        "is_agi": False,
    }
    required = {
        "scores": selection_record["scores_angvel_mae"],
        "context_logs": [{k: {"encoder_l2_from_init": v["encoder_l2_from_init"], "mean_state_loss": v["mean_state_loss"]} for k, v in s["context_logs"].items()} for s in per_seed],
    }
    if not smoke and not incomplete and chosen is not None:
        report = completeness_report(required, optional_note="Checkpoint tensors live outside git under artifacts/context_optimization_checkpoints.")
        selection_payload["completeness"] = report
        selection_record["selection_recorded"] = bool(report["declared_complete"])
        selection_payload["selection_record"] = selection_record
    else:
        selection_payload["completeness"] = {"declared_complete": False, "failures": ["smoke or incomplete or missing selection"], "optional_fields_note": ""}
        selection_record["selection_recorded"] = False
        selection_payload["selection_record"] = selection_record
    if selection_path is not None:
        Path(selection_path).parent.mkdir(parents=True, exist_ok=True)
        Path(selection_path).write_text(dumps_strict(selection_payload))
    if plot_path is not None and per_seed:
        _plot(Path(plot_path), per_seed, checkpoints)

    audit_payload: dict[str, Any] | None = None
    if selection_record["selection_recorded"] and not timed_out():
        assert_audit_allowed(selection_record)
        audit_support = [grab(spec, 128, int(cfg["audit_support_env0"]) + 10 * i, int(cfg["audit_support_base"]) + i, "audit_support_env") for i, spec in enumerate(specs)]
        audit_query = [
            complete_episodes(grab(spec, 400, int(cfg["audit_query_env0"]) + 10 * i, int(cfg["audit_query_base"]) + i, "audit_query_env"), 16)
            for i, spec in enumerate(specs)
        ]
        assert_disjoint_seeds(*audit_support, *audit_query, *selection_support, *selection_query)
        # Rebuild frozen models from the saved checkpoints so audit uses the recorded snapshots.
        audit_seeds = []
        for s, seed in enumerate(per_seed):
            del seed
            audit_seeds.append(_audit_seed(s, specs, audit_support, audit_query, checkpoints, chosen, mlp_chosen, cfg, horizons, budget, angvel_index))
        audit_summary = _audit_summary(audit_seeds, chosen)
        screen = optimization_screen(
            audit_summary["per_seed_selected"],
            improvement=float(cfg["screen_angvel_improvement"]),
            min_positive_seeds=int(cfg["screen_min_positive_seeds"]),
            max_worsening=float(cfg["screen_max_worsening"]),
        )
        audit_required = {"per_seed": audit_summary["per_seed_selected"]}
        audit_complete = completeness_report(audit_required)
        audit_payload = {
            "protocol": selection_payload["protocol"],
            "selection_record": selection_record,
            "data_hashes": {
                "audit_support": [prefix_hash(ds, len(ds)) for ds in audit_support],
                "audit_query": [prefix_hash(ds, len(ds)) for ds in audit_query],
            },
            "per_seed": audit_seeds,
            "summary": audit_summary,
            "screen": screen,
            "classification": _classify(chosen, audit_summary, screen),
            "completeness": audit_complete,
            "declared_complete": bool(audit_complete["declared_complete"]) and not smoke,
            "resources": resources,
            "wall_clock_s": time.perf_counter() - t0,
            "confirm_evaluated": False,
            "control_evaluated": False,
            "is_agi": False,
        }
        if audit_path is not None:
            Path(audit_path).write_text(dumps_strict(audit_payload))
    elif audit_path is not None and (incomplete or smoke or chosen is None):
        Path(audit_path).parent.mkdir(parents=True, exist_ok=True)
        Path(audit_path).write_text(dumps_strict({
            "audit_evaluated": False,
            "reason": "selection was not recorded",
            "selection_record": selection_record,
            "declared_complete": False,
            "confirm_evaluated": False,
            "control_evaluated": False,
        }))
    selection_payload["audit_payload"] = None
    selection_payload["wall_clock_s"] = time.perf_counter() - t0
    return {"selection": selection_payload, "audit": audit_payload}


def _audit_seed(s: int, specs: tuple[Any, ...], support: list[TransitionDataset], query: list[TransitionDataset], checkpoints: list[int], chosen: int, mlp_chosen: int | None, cfg: dict[str, Any], horizons: list[int], budget: int, angvel_index: int) -> dict[str, Any]:
    def load_context(step: int) -> ContextWorldModel:
        blob = torch.load(CHECKPOINT_DIR / f"seed{s}_context_u{step}.pt", map_location="cpu", weights_only=False)
        model = ContextWorldModel.create(3, 3, seed=0)
        model.encoder.load_state_dict(blob["encoder"])
        model.net.load_state_dict(blob["net"])
        model.obs_rms.load_state_dict(blob["obs_rms"])
        return model.clone_frozen()

    def load_mlp(step: int) -> WorldModel:
        blob = torch.load(CHECKPOINT_DIR / f"seed{s}_mlp_u{step}.pt", map_location="cpu", weights_only=False)
        model = WorldModel.create(3, 3, kind="residual", hidden=tuple(cfg["mlp_hidden"]), seed=0, arch="mlp")
        model.net.load_state_dict(blob["net"])
        model.obs_rms.load_state_dict(blob["obs_rms"])
        model.net.eval()
        return model

    donors = [support[(i + 1) % len(support)] for i in range(len(specs))]
    rows: dict[str, Any] = {}
    steps = sorted({int(chosen), 300 if 300 in checkpoints else checkpoints[0], int(mlp_chosen) if mlp_chosen is not None else int(chosen)})
    for step in steps:
        task_rows = {}
        ctx_model = load_context(step)
        mlp_model = load_mlp(step)
        for i, spec in enumerate(specs):
            bundle = _context_bundle(ctx_model, support[i], donors[i], query[i], budget, horizons, angvel_index)
            bundle["mlp"] = _episode_prediction(mlp_model, query[i], horizons, angvel_index)
            task_rows[spec.task_id] = {"donor_task": specs[(i + 1) % len(specs)].task_id, "metrics": bundle}
        rows[str(step)] = task_rows
    return {"model_seed": s, "checkpoints": rows}


def _mean_metric(tasks: dict[str, Any], condition: str, key: str) -> float:
    vals = []
    for task in tasks.values():
        cell = task["metrics"][condition]
        if key == "h16":
            vals.append(float(cell["rollout_mae"]["16"]))
        else:
            vals.append(float(cell[key]))
    return float(np.mean(vals)) if vals else float("nan")


def _selection_summary(per_seed: list[dict[str, Any]], checkpoints: list[int]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for step in checkpoints:
        block: dict[str, Any] = {}
        for condition in ("real", "zero", "wrong", "mlp"):
            seed_angvel = []
            seed_mae = []
            for seed in per_seed:
                tasks = seed["selection"].get(str(step), {}).get("tasks", {})
                if not tasks:
                    continue
                seed_angvel.append(_mean_metric(tasks, condition, "angvel_mae"))
                seed_mae.append(_mean_metric(tasks, condition, "mae"))
            block[condition] = {
                "angvel_mae": seed_level_ci(seed_angvel) if len(seed_angvel) >= 2 else {"n": len(seed_angvel), "mean": float(np.mean(seed_angvel)) if seed_angvel else None},
                "mae": seed_level_ci(seed_mae) if len(seed_mae) >= 2 else {"n": len(seed_mae), "mean": float(np.mean(seed_mae)) if seed_mae else None},
            }
        out[str(step)] = block
    return {"selection_set": out, "interval": "exploratory_student_t_across_training_seeds_df_2"}


def _audit_summary(audit_seeds: list[dict[str, Any]], chosen: int) -> dict[str, Any]:
    def pack(step: int, condition: str) -> list[dict[str, float]]:
        rows = []
        for seed in audit_seeds:
            tasks = seed["checkpoints"][str(step)]
            rows.append(
                {
                    "angvel_real": _mean_metric(tasks, "real", "angvel_mae") if condition == "context" else _mean_metric(tasks, "mlp", "angvel_mae"),
                    "angvel_zero": _mean_metric(tasks, "zero", "angvel_mae") if condition == "context" else float("nan"),
                    "angvel_wrong": _mean_metric(tasks, "wrong", "angvel_mae") if condition == "context" else float("nan"),
                    "mae_real": _mean_metric(tasks, "real", "mae") if condition == "context" else _mean_metric(tasks, "mlp", "mae"),
                    "mae_zero": _mean_metric(tasks, "zero", "mae") if condition == "context" else float("nan"),
                    "h16_real": _mean_metric(tasks, "real", "h16") if condition == "context" else _mean_metric(tasks, "mlp", "h16"),
                    "h16_zero": _mean_metric(tasks, "zero", "h16") if condition == "context" else float("nan"),
                }
            )
        return rows

    selected = pack(int(chosen), "context")
    reference_step = 300 if any("300" in seed["checkpoints"] for seed in audit_seeds) else int(chosen)
    reference = pack(reference_step, "context")
    return {
        "per_seed_selected": selected,
        "per_seed_reference_300": reference,
        "selected_updates": int(chosen),
        "reference_updates": reference_step,
        "selected_intervals": _interval_block(selected),
        "reference_intervals": _interval_block(reference),
    }


def _interval_block(rows: list[dict[str, float]]) -> dict[str, Any]:
    keys = ("angvel_real", "angvel_zero", "angvel_wrong", "mae_real", "mae_zero", "h16_real", "h16_zero")
    out = {}
    for key in keys:
        xs = [float(row[key]) for row in rows]
        out[key] = seed_level_ci(xs) if len(xs) >= 2 else {"n": len(xs), "mean": float(np.mean(xs)) if xs else None}
    if rows:
        bz = [row["angvel_zero"] - row["angvel_real"] for row in rows]
        bw = [row["angvel_wrong"] - row["angvel_real"] for row in rows]
        out["angvel_zero_minus_real"] = seed_level_ci(bz) if len(bz) >= 2 else {"n": len(bz), "mean": float(np.mean(bz))}
        out["angvel_wrong_minus_real"] = seed_level_ci(bw) if len(bw) >= 2 else {"n": len(bw), "mean": float(np.mean(bw))}
    return out


def _classify(chosen: int | None, audit_summary: dict[str, Any], screen: dict[str, Any]) -> dict[str, Any]:
    if chosen is None:
        return {"longer_training_helped": False, "context_useful": False, "label": "incomplete"}
    if int(chosen) == 300:
        return {
            "longer_training_helped": False,
            "context_useful": bool(screen.get("pass")),
            "label": "300_updates_selected",
            "note": "The selection rule preferred 300 updates. Longer training is not claimed to have helped.",
        }
    selected = audit_summary["per_seed_selected"]
    reference = audit_summary["per_seed_reference_300"]
    zero_gain = float(np.mean([r["angvel_zero"] for r in reference]) - np.mean([s["angvel_zero"] for s in selected]))
    real_gain = float(np.mean([r["angvel_real"] for r in reference]) - np.mean([s["angvel_real"] for s in selected]))
    dynamics = zero_gain > 0
    context = bool(screen.get("pass"))
    if dynamics and context:
        label = "dynamics_and_context"
    elif dynamics:
        label = "dynamics_only"
    elif context:
        label = "context_only"
    elif real_gain <= 0:
        label = "selection_did_not_persist"
    else:
        label = "neither"
    return {"longer_training_helped": dynamics or context, "context_useful": context, "dynamics_improved": dynamics, "label": label, "audit_zero_angvel_drop": zero_gain, "audit_real_angvel_drop": real_gain}


def _protocol(cfg: dict[str, Any], smoke: bool, sha: str, source_status: dict[str, Any], checkpoints: list[int], total: int, n_seeds: int) -> dict[str, Any]:
    return {
        "code_version": "context_optimization_diagnostic",
        "config": cfg,
        "executed_updates": checkpoints,
        "executed_total_updates": total,
        "executed_seeds": n_seeds,
        "smoke": bool(smoke),
        "implementation_sha": sha if not source_status.get("source_dirty") else None,
        "source_dirty": bool(source_status.get("source_dirty", True)),
        "git": _git_meta(),
        "confirm_evaluated": False,
        "control_evaluated": False,
        "is_agi": False,
        "h_optimization": cfg.get("h_optimization"),
        "prior_diagnosis": "Real context did not beat zero or wrong context on held-out source prediction at 300 updates.",
    }


def _plot(path: Path, per_seed: list[dict[str, Any]], checkpoints: list[int]) -> None:
    series: dict[str, list[float]] = {}
    bands: dict[str, list[tuple[float, float]]] = {}
    for name in ("real", "zero", "wrong", "mlp"):
        acc = []
        band = []
        for step in checkpoints:
            vals = []
            for seed in per_seed:
                tasks = seed["selection"].get(str(step), {}).get("tasks", {})
                if tasks:
                    vals.append(_mean_metric(tasks, name, "angvel_mae"))
            acc.append(float(np.mean(vals)) if vals else float("nan"))
            band.append((float(np.min(vals)), float(np.max(vals))) if vals else (float("nan"), float("nan")))
        series[name] = acc
        bands[name] = band
    _svg(path, checkpoints, series, bands)
