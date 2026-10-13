"""Pendulum meta-learning pilot: Reptile vs matched-data multitask. Not AGI."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.pendulum_family import (
    PENDULUM_N_ACTIONS,
    PENDULUM_OBS_DIM,
    pendulum_confirmation_targets,
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
from nexus.world.adapt import finetune_world_model, interpolate_world_models
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, collect_transitions, concat_datasets
from nexus.world.dynamics import ArchName, WorldModel
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_HIDDEN, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL, FROZEN_PRIMARY_HORIZON
from nexus.world.memory import checkpoint_nbytes
from nexus.world.planning import PENDULUM_PLAN_CANDIDATES, PENDULUM_PLAN_HORIZON
from nexus.world.protocol import (
    V089G_CONFIRM_EVAL_SEED,
    V089M_ADAPT_SEED,
    V089M_CONFIRM_EVAL_SEED,
    V089M_DEV_EVAL_SEED,
    V089M_META_COLLECT_SEED,
    V089M_SOURCE_COLLECT_SEED,
    V089M_TARGET_COLLECT_SEED,
    V089M_TRAIN_SEED,
    V089M_VAL_SEED,
    V089P_CONFIRM_EVAL_SEED,
    V089X_EVAL_SEED,
)
from nexus.world.session import PersistentSession
from nexus.world.train import train_world_model
from nexus.world.v085 import _git_meta
from nexus.world.v086 import V086_FT_LR
from nexus.world.v087 import paired_control_eval
from nexus.world.v089 import _auc, _prefix, run_mae_persistent
from nexus.world.adapt import WindowThresholdDetector, per_transition_mae
from nexus.world.verify import V085_MAE_RATIO

BUDGETS = (0, 32, 64, 128, 256, 512, 1024)
INITS = ("scratch", "source", "multitask", "reptile")
ARCHS: tuple[ArchName, ...] = ("mlp", "film", "gru")
ARCH_HIDDEN: dict[str, tuple[int, ...]] = {"mlp": (64, 64), "film": (56, 56), "gru": (64, 64)}
CROSS_ENV_HASH = "402ce4151837eb0d"
GENERALITY_HASH = "c32ee7c682467cf9"
TRANSFER_HASH = "7fde7c9c01fc8524"
REPTILE_INNER_EPOCHS = 5
REPTILE_OUTER = 24
REPTILE_EPS = 0.1
PER_TASK_TRAIN, PER_TASK_VAL = 256, 64
MULTITASK_EPOCHS = 48
META_TASK_COLLECT = PER_TASK_TRAIN + PER_TASK_VAL  # 320; 4 tasks → 1280 prior env steps


def validate_prior_artifacts() -> dict[str, Any]:
    def _h(path: str) -> str | None:
        p = json.loads(Path(path).read_text())
        return p.get("protocol", {}).get("protocol_hash")

    return {
        "cross_env_ok": _h("artifacts/cross_environment.json") == CROSS_ENV_HASH,
        "generality_ok": _h("artifacts/planning_generality.json") == GENERALITY_HASH,
        "transfer_ok": _h("artifacts/pendulum_transfer.json") == TRANSFER_HASH,
        "cartpole_horizon": FROZEN_PRIMARY_HORIZON,
        "pendulum_horizon": PENDULUM_PLAN_HORIZON,
        "mae_ratio": V085_MAE_RATIO,
    }


def _prior_physics() -> set[tuple[float, float, float]]:
    specs: list[TaskSpec] = [
        pendulum_source(),
        pendulum_transfer_development(),
        *pendulum_confirmation_targets(),
        *pendulum_transfer_confirmation(),
        *pendulum_transfer_sequence(),
    ]
    return {pendulum_physics_key(s) for s in specs}


def assert_physics_disjoint() -> None:
    prior = _prior_physics()
    used: set[tuple[float, float, float]] = set()
    for spec in (*pendulum_meta_train(), *pendulum_meta_val(), *pendulum_meta_confirm()):
        key = pendulum_physics_key(spec)
        if key in prior:
            raise AssertionError(f"physics leak vs prior suite: {spec.task_id} {key}")
        if key in used:
            raise AssertionError(f"duplicate physics: {spec.task_id}")
        used.add(key)


def _make(arch: ArchName, seed: int) -> WorldModel:
    return WorldModel.create(
        PENDULUM_OBS_DIM, PENDULUM_N_ACTIONS, kind=FROZEN_KIND, hidden=ARCH_HIDDEN[arch], seed=int(seed), arch=arch,
    )


def _collect(spec: TaskSpec, n: int, *, env0: int, base: int) -> TransitionDataset:
    n_env = max(2, min(8, max(1, n // 32)))
    seeds = tuple(range(int(env0), int(env0) + n_env))
    return collect_transitions(spec, n_transitions=int(n), env_seeds=seeds, base_seed=int(base), mix=("random",))


def _fit_from(
    init: WorldModel | None,
    pool: TransitionDataset,
    *,
    budget: int,
    epochs: int,
    seed: int,
    arch: ArchName,
) -> WorldModel:
    take = min(int(budget), len(pool))
    if take <= 0:
        return init.clone() if init is not None else _make(arch, seed)
    n_val = min(32, max(0, take // 4)) if take >= 16 else 0
    n_tr = take - n_val
    tr = _prefix(pool, n_tr)
    va = pool.slice(np.arange(n_tr, take)) if n_val else _prefix(pool, 0)
    if init is None:
        use = tr if n_tr >= 8 else pool
        wm, _ = train_world_model(
            use, va if n_val else use, kind=FROZEN_KIND, epochs=epochs, seed=seed, hidden=ARCH_HIDDEN[arch],
            arch=arch, n_actions=PENDULUM_N_ACTIONS,
        )
        return wm
    if n_tr < 4:
        return init.clone()
    wm, _ = finetune_world_model(init, tr, va, epochs=epochs, seed=seed, lr=V086_FT_LR, select_by_val=len(va) > 0)
    return wm


def _mix_rms(dst: WorldModel, src: WorldModel, alpha: float) -> None:
    a = float(alpha)
    dst.obs_rms.mean = (1.0 - a) * np.asarray(dst.obs_rms.mean) + a * np.asarray(src.obs_rms.mean)
    dst.obs_rms.var = (1.0 - a) * np.asarray(dst.obs_rms.var) + a * np.asarray(src.obs_rms.var)


def reptile_train(
    tasks: list[tuple[TransitionDataset, TransitionDataset]],
    *,
    arch: ArchName,
    seed: int,
    outer: int = REPTILE_OUTER,
    inner: int = REPTILE_INNER_EPOCHS,
    eps: float = REPTILE_EPS,
) -> WorldModel:
    theta = _make(arch, seed)
    if tasks:
        theta.fit_rms(concat_datasets(*[tr for tr, _va in tasks], task_id="meta_rms").obs)
    rng = np.random.default_rng(seed)
    for t in range(int(outer)):
        i = int(rng.integers(0, len(tasks)))
        tr, va = tasks[i]
        phi, _ = finetune_world_model(theta, tr, va, epochs=inner, seed=seed + 17 * t, lr=V086_FT_LR, select_by_val=len(va) > 0)
        theta = interpolate_world_models(theta, phi, alpha=float(eps))
        _mix_rms(theta, phi, float(eps))
    theta.net.eval()
    return theta


def multitask_train(
    tasks: list[tuple[TransitionDataset, TransitionDataset]],
    *,
    arch: ArchName,
    seed: int,
    epochs: int = MULTITASK_EPOCHS,
) -> WorldModel:
    trains = concat_datasets(*[tr for tr, _va in tasks], task_id="meta_mt_tr")
    vals = concat_datasets(*[va for _tr, va in tasks], task_id="meta_mt_va")
    wm, _ = train_world_model(
        trains, vals, kind=FROZEN_KIND, epochs=epochs, seed=seed, hidden=ARCH_HIDDEN[arch], arch=arch, n_actions=PENDULUM_N_ACTIONS,
    )
    return wm


def source_train(spec: TaskSpec, *, arch: ArchName, seed: int, n_total: int, epochs: int) -> tuple[WorldModel, int]:
    n_val = max(32, n_total // 5)
    n_tr = n_total - n_val
    tr = _collect(spec, n_tr, env0=10 + 8 * seed, base=V089M_SOURCE_COLLECT_SEED + 19 * seed)
    va = _collect(spec, n_val, env0=400 + 8 * seed, base=V089M_VAL_SEED + 19 * seed)
    assert_disjoint_seeds(tr, va)
    wm, _ = train_world_model(
        tr, va, kind=FROZEN_KIND, epochs=epochs, seed=V089M_TRAIN_SEED + 13 * seed, hidden=ARCH_HIDDEN[arch],
        arch=arch, n_actions=PENDULUM_N_ACTIONS,
    )
    return wm, int(tr.env_interactions + va.env_interactions)


def collect_meta_tasks(
    specs: tuple[TaskSpec, ...],
    *,
    seed: int,
    n_train: int = PER_TASK_TRAIN,
    n_val: int = PER_TASK_VAL,
) -> tuple[list[tuple[TransitionDataset, TransitionDataset]], int]:
    out: list[tuple[TransitionDataset, TransitionDataset]] = []
    used = 0
    for i, spec in enumerate(specs):
        tr = _collect(spec, n_train, env0=20 + 30 * seed + 8 * i, base=V089M_META_COLLECT_SEED + 50 * seed + 7 * i)
        va = _collect(spec, n_val, env0=500 + 30 * seed + 8 * i, base=V089M_VAL_SEED + 80 * seed + 7 * i)
        assert_disjoint_seeds(tr, va)
        used += int(tr.env_interactions + va.env_interactions)
        out.append((tr, va))
    return out, used


def _curve(
    spec: TaskSpec,
    inits: dict[str, WorldModel | None],
    pool: TransitionDataset,
    *,
    budgets: tuple[int, ...],
    arch: ArchName,
    epochs: int,
    seed: int,
    eval_seed: int,
    episodes: int,
) -> dict[str, Any]:
    curve: dict[str, Any] = {}
    rets: dict[str, list[float]] = {k: [] for k in inits}
    for b in budgets:
        models = {}
        for name, init in inits.items():
            models[name] = _fit_from(init, pool, budget=b, epochs=epochs, seed=seed + int(b), arch=arch)
        ev = paired_control_eval(spec, models, seed=eval_seed, episodes=episodes)
        curve[str(b)] = {k: float(ev[k]["mean_return"]) for k in inits}
        for k in inits:
            rets[k].append(float(ev[k]["mean_return"]))
    return {"curve": curve, "auc": {k: _auc(budgets, rets[k]) for k in inits}, "final": {k: rets[k][-1] for k in inits}}


def run_meta_learning_pilot(
    *,
    n_model_seeds: int = 10,
    n_arch_seeds: int = 2,
    adapt_epochs: int = 8,
    eval_episodes: int = 2,
    artifact_path: str | Path | None = "artifacts/meta_learning_pilot.json",
    checkpoint_dir: str | Path = "checkpoints/meta_learning_pilot",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    assert_physics_disjoint()
    budgets: tuple[int, ...] = BUDGETS
    outer, inner, mt_epochs, src_epochs = REPTILE_OUTER, REPTILE_INNER_EPOCHS, MULTITASK_EPOCHS, FROZEN_EPOCHS
    n_tr, n_va = PER_TASK_TRAIN, PER_TASK_VAL
    pool_n = 1024
    if quick:
        n_model_seeds, n_arch_seeds = min(n_model_seeds, 1), min(n_arch_seeds, 1)
        budgets = (0, 32, 64)
        outer, inner, mt_epochs, src_epochs, adapt_epochs = 2, 1, 1, 1, 1
        n_tr, n_va, pool_n, eval_episodes = 32, 16, 64, 1
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    source_spec = pendulum_source()
    meta_tr = pendulum_meta_train()
    meta_va = pendulum_meta_val()
    confirms = pendulum_meta_confirm()
    if quick:
        meta_tr, meta_va, confirms = meta_tr[:2], meta_va[:1], confirms[:1]
    n_prior_planned = len(meta_tr) * (n_tr + n_va)
    preserved = validate_prior_artifacts()
    git = _git_meta()

    # --- development architecture selection (multitask + FT AUC on meta-val) ---
    arch_rows: list[dict[str, Any]] = []
    arch_auc: dict[str, list[float]] = {a: [] for a in ARCHS}
    for aseed in range(n_arch_seeds):
        tasks, _used = collect_meta_tasks(meta_tr, seed=1000 + aseed, n_train=n_tr, n_val=n_va)
        for arch in ARCHS:
            mt = multitask_train(tasks, arch=arch, seed=V089M_TRAIN_SEED + aseed, epochs=mt_epochs)
            aucs = []
            for spec in meta_va:
                sess = PersistentSession(spec, mt, env_seed=V089M_DEV_EVAL_SEED + aseed, plan_seed=aseed)
                pool = sess.collect(pool_n)
                sess.close()
                row = _curve(
                    spec, {"multitask": mt}, pool, budgets=budgets if quick else (0, 128, min(512, budgets[-1])),
                    arch=arch, epochs=adapt_epochs, seed=V089M_ADAPT_SEED + aseed, eval_seed=V089M_DEV_EVAL_SEED, episodes=eval_episodes,
                )
                aucs.append(float(row["auc"]["multitask"]))
            mean_auc = float(np.mean(aucs))
            arch_auc[arch].append(mean_auc)
            arch_rows.append({"arch_seed": aseed, "arch": arch, "n_params": mt.net.n_parameters(), "val_auc": mean_auc, "nbytes": checkpoint_nbytes(mt)})
    ranked = sorted(((float(np.mean(v)) if v else float("-inf"), a) for a, v in arch_auc.items()), reverse=True)
    selected_arch: ArchName = ranked[0][1] if ranked else "mlp"

    protocol = {
        "code_version": "meta_learning_pilot",
        "parent_commit": "eb7a083",
        "algorithm": "first_order_reptile",
        "inner_learner": "ordinary_finetune",
        "inner_lr": V086_FT_LR,
        "reptile_eps": REPTILE_EPS,
        "reptile_outer": outer,
        "reptile_inner_epochs": inner,
        "selected_arch": selected_arch,
        "arch_hidden": {k: list(v) for k, v in ARCH_HIDDEN.items()},
        "pendulum_horizon": PENDULUM_PLAN_HORIZON,
        "pendulum_candidates": PENDULUM_PLAN_CANDIDATES,
        "mae_ratio": V085_MAE_RATIO,
        "retuned_mae": False,
        "budgets": list(budgets),
        "n_model_seeds": n_model_seeds,
        "n_arch_seeds": n_arch_seeds,
        "confirm_eval_seed": V089M_CONFIRM_EVAL_SEED,
        "prior_eval_unused": [V089X_EVAL_SEED, V089G_CONFIRM_EVAL_SEED, V089P_CONFIRM_EVAL_SEED],
        "primary_success": "reptile_auc_minus_multitask_auc_seed_ci_lo>0",
        "film_uses_privileged_physics": False,
        "is_agi": False,
        "claims_learning_to_learn": False,
        "quick": quick,
        "git": git,
    }
    protocol["protocol_hash"] = hashlib.sha256(dumps_strict(protocol).encode()).hexdigest()[:16]

    per_seed: list[dict[str, Any]] = []
    for mseed in range(n_model_seeds):
        tasks, prior_env = collect_meta_tasks(meta_tr, seed=mseed, n_train=n_tr, n_val=n_va)
        src, src_env = source_train(source_spec, arch=selected_arch, seed=mseed, n_total=n_prior_planned, epochs=src_epochs)
        mt = multitask_train(tasks, arch=selected_arch, seed=V089M_TRAIN_SEED + 3 * mseed, epochs=mt_epochs)
        rep = reptile_train(tasks, arch=selected_arch, seed=V089M_TRAIN_SEED + 9 * mseed, outer=outer, inner=inner)
        inits: dict[str, WorldModel | None] = {"scratch": None, "source": src, "multitask": mt, "reptile": rep}
        confirm_rows: dict[str, Any] = {}
        auc_mean: dict[str, list[float]] = {k: [] for k in INITS}
        final_mean: dict[str, list[float]] = {k: [] for k in INITS}
        for spec in confirms:
            sess = PersistentSession(spec, src, env_seed=V089M_TARGET_COLLECT_SEED + mseed, plan_seed=mseed)
            pool = sess.collect(pool_n)
            sess.close()
            row = _curve(
                spec, inits, pool, budgets=budgets, arch=selected_arch, epochs=adapt_epochs,
                seed=V089M_ADAPT_SEED + 11 * mseed, eval_seed=V089M_CONFIRM_EVAL_SEED, episodes=eval_episodes,
            )
            confirm_rows[spec.task_id] = {"params": dict(spec.params), **row}
            for k in INITS:
                auc_mean[k].append(float(row["auc"][k]))
                final_mean[k].append(float(row["final"][k]))
        mae_row: dict[str, Any] | None = None
        if not quick:
            calib = _collect(source_spec, 32, env0=700, base=V089M_VAL_SEED + mseed)
            det = WindowThresholdDetector(window=32, k=3.0)
            det.fit(per_transition_mae(src, calib.obs, calib.action, calib.next_obs))
            mae_run = run_mae_persistent(
                confirms[0], src, tasks[0][0], cap=pool_n, epochs=adapt_epochs, seed=V089M_TARGET_COLLECT_SEED + 40 + mseed,
                adapt_seed=V089M_ADAPT_SEED + mseed, gate_seed=mseed + 3, detector=det, snapshots_at=(0, pool_n),
            )
            evm = paired_control_eval(confirms[0], {"mae_gated": mae_run["model"], "source": src}, seed=V089M_CONFIRM_EVAL_SEED, episodes=eval_episodes)
            mae_row = {
                "n_accept": mae_run["n_accept"],
                "n_propose": mae_run["n_propose"],
                "return": evm["mae_gated"]["mean_return"],
                "source_return": evm["source"]["mean_return"],
            }
        per_seed.append(
            {
                "model_seed": mseed,
                "prior_env_meta": prior_env,
                "prior_env_source": src_env,
                "n_params": src.net.n_parameters(),
                "nbytes": checkpoint_nbytes(src),
                "confirm": confirm_rows,
                "auc_mean": {k: float(np.mean(v)) for k, v in auc_mean.items()},
                "final_mean": {k: float(np.mean(v)) for k, v in final_mean.items()},
                "mae_extra": mae_row,
            }
        )
        print(f"meta_pilot seed={mseed} arch={selected_arch}", flush=True)

    def _ci(xs: list[float]) -> dict[str, Any] | None:
        return seed_level_ci(xs) if xs else None

    reptile_vs_mt = [float(s["auc_mean"]["reptile"]) - float(s["auc_mean"]["multitask"]) for s in per_seed]
    reptile_vs_src = [float(s["auc_mean"]["reptile"]) - float(s["auc_mean"]["source"]) for s in per_seed]
    mt_vs_src = [float(s["auc_mean"]["multitask"]) - float(s["auc_mean"]["source"]) for s in per_seed]
    fin_r_mt = [float(s["final_mean"]["reptile"]) - float(s["final_mean"]["multitask"]) for s in per_seed]
    rci = _ci(reptile_vs_mt)
    l2l_ok = bool(rci) and float(rci["lo"]) > 0
    payload = {
        "protocol": protocol,
        "audit": preserved,
        "architecture": {
            "selected": selected_arch,
            "ranked": [{"arch": a, "mean_val_auc": float(np.mean(arch_auc[a])) if arch_auc[a] else None} for _, a in ranked] if ranked else [],
            "per_seed": arch_rows,
            "n_params_selected": per_seed[0]["n_params"] if per_seed else None,
        },
        "confirmation": {
            "auc": {k: _ci([float(s["auc_mean"][k]) for s in per_seed]) for k in INITS},
            "final_return": {k: _ci([float(s["final_mean"][k]) for s in per_seed]) for k in INITS},
            "reptile_auc_minus_multitask": rci,
            "reptile_auc_minus_source": _ci(reptile_vs_src),
            "multitask_auc_minus_source": _ci(mt_vs_src),
            "reptile_final_minus_multitask": _ci(fin_r_mt),
            "scratch_final": _ci([float(s["final_mean"]["scratch"]) for s in per_seed]),
        },
        "mae_extra": {
            "accepts": _ci([float((s["mae_extra"] or {}).get("n_accept") or 0) for s in per_seed if s["mae_extra"]]),
            "return": _ci([float((s["mae_extra"] or {}).get("return") or np.nan) for s in per_seed if s["mae_extra"]]),
        },
        "decision": {
            "meta_learning_success": l2l_ok,
            "selected_arch": selected_arch,
            "reason": (
                "Reptile AUC beat matched-data multitask on untouched confirm"
                if l2l_ok
                else "Reptile did not beat equally resourced multitask (CI includes 0 or negative); not learning-to-learn"
            ),
        },
        "costs": {
            "prior_env_per_meta_seed": n_prior_planned,
            "target_pool": pool_n,
            "horizon": PENDULUM_PLAN_HORIZON,
            "candidates": PENDULUM_PLAN_CANDIDATES,
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "Same inner fine-tune and target data. Reptile vs multitask isolates the init rule, not extra data. Not AGI.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
