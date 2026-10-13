"""Pendulum adaptation and transfer. Frozen H=16 residual planner. Not learning-to-learn a priori. Not AGI."""

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
    PENDULUM_PLAN_HORIZON,
    pendulum_confirmation_targets,
    pendulum_physics_key,
    pendulum_source,
    pendulum_transfer_confirmation,
    pendulum_transfer_development,
    pendulum_transfer_sequence,
)
from nexus.tasks.spec import TaskSpec
from nexus.world.adapt import WindowThresholdDetector, per_transition_mae
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, collect_transitions
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_HIDDEN, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL, FROZEN_PRIMARY_HORIZON
from nexus.world.imagine import multi_step_errors
from nexus.world.memory import PredictiveMemory, checkpoint_nbytes
from nexus.world.planning import PENDULUM_PLAN_CANDIDATES as PLAN_CAND
from nexus.world.planning import PENDULUM_PLAN_HORIZON as PLAN_H
from nexus.world.protocol import (
    V089G_CONFIRM_EVAL_SEED,
    V089P_ADAPT_SEED,
    V089P_CONFIRM_EVAL_SEED,
    V089P_DETECT_SEED,
    V089P_GATE_SEED,
    V089P_SEQUENCE_EVAL_SEED,
    V089P_SOURCE_COLLECT_SEED,
    V089P_TARGET_COLLECT_SEED,
    V089P_TRAIN_SEED,
    V089P_VAL_SEED,
    V089X_EVAL_SEED,
)
from nexus.world.session import PersistentSession
from nexus.world.train import one_step_errors, train_world_model
from nexus.world.v085 import _git_meta
from nexus.world.v086 import apply_method
from nexus.world.v087 import paired_control_eval
from nexus.world.v088 import copy_detector
from nexus.world.v089 import (
    BUDGETS,
    STAGE_CAP,
    TRAIN_N,
    VAL_N,
    _auc,
    _prefix,
    adapt_stage,
    exploit_diagnostics,
    run_detection_compare,
    run_mae_persistent,
)
from nexus.world.verify import V085_MAE_RATIO

METHODS = ("frozen", "scratch", "always_adapt", "low_lr", "mae_gated", "retrieved")
CROSS_ENV_HASH = "402ce4151837eb0d"
GENERALITY_HASH = "c32ee7c682467cf9"
PLANNING_H16 = 16


def validate_prior_artifacts() -> dict[str, Any]:
    ce = json.loads(Path("artifacts/cross_environment.json").read_text())
    pg = json.loads(Path("artifacts/planning_generality.json").read_text())
    return {
        "cross_env_ok": ce.get("protocol", {}).get("protocol_hash") == CROSS_ENV_HASH,
        "generality_ok": pg.get("protocol", {}).get("protocol_hash") == GENERALITY_HASH,
        "cross_env_hash": ce.get("protocol", {}).get("protocol_hash"),
        "generality_hash": pg.get("protocol", {}).get("protocol_hash"),
        "cartpole_horizon_untouched": FROZEN_PRIMARY_HORIZON == 3,
        "pendulum_horizon": PLAN_H == PLANNING_H16 == PENDULUM_PLAN_HORIZON,
        "mae_ratio": V085_MAE_RATIO,
    }


def fit_budget_models(
    source: Any,
    replay: Any,
    pool: TransitionDataset,
    *,
    budget: int,
    epochs: int,
    seed: int,
    memory: PredictiveMemory,
    probe_n: int,
) -> dict[str, Any]:
    take = min(int(budget), len(pool))
    if take <= 0:
        empty = _prefix(pool, 0)
        retrieved, meta = memory.retrieve(empty)
        return {
            "scratch": WorldModel.create(PENDULUM_OBS_DIM, PENDULUM_N_ACTIONS, kind="residual", seed=int(seed)),
            "frozen": source,
            "always_adapt": source,
            "low_lr": source,
            "retrieved": retrieved or source,
            "val_n": 0,
            "train_n": 0,
            "probe_n": 0,
            "retrieval": meta,
        }
    n_val = min(32, max(0, take // 4)) if take >= 16 else 0
    n_tr = take - n_val
    tr = _prefix(pool, n_tr)
    va = pool.slice(np.arange(n_tr, take)) if n_val else _prefix(pool, 0)
    use_tr = tr if n_tr >= 8 else pool
    scratch, _ = train_world_model(
        use_tr, va if n_val else use_tr, kind=FROZEN_KIND, epochs=epochs, seed=int(seed), hidden=FROZEN_HIDDEN, n_actions=PENDULUM_N_ACTIONS,
    )  # type: ignore[arg-type]
    always, _ = apply_method("finetune", source, replay, tr, va, epochs=epochs, seed=int(seed) + 1)
    low, _ = apply_method("low_lr", source, replay, tr, va, epochs=epochs, seed=int(seed) + 2)
    probe = _prefix(va if n_val else tr, min(int(probe_n), len(va) if n_val else len(tr)))
    retrieved, meta = memory.retrieve(probe)
    return {
        "scratch": scratch,
        "frozen": source,
        "always_adapt": always,
        "low_lr": low,
        "retrieved": retrieved or source,
        "val_n": n_val,
        "train_n": n_tr,
        "probe_n": len(probe),
        "retrieval": meta,
    }


def _pred(wm: Any, ds: TransitionDataset) -> dict[str, Any]:
    if len(ds) == 0:
        return {"mae": None, "multi_h3": None, "multi_h8": None}
    ms = multi_step_errors(wm, ds, (1, 3, 8))
    return {
        "mae": float(one_step_errors(wm, ds)["mae"]),
        "multi_h3": ms.get("3", {}).get("mean_mae"),
        "multi_h8": ms.get("8", {}).get("mean_mae"),
    }


def run_pendulum_transfer(
    *,
    n_model_seeds: int = 10,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    adapt_epochs: int = 8,
    eval_episodes: int = 2,
    artifact_path: str | Path | None = "artifacts/pendulum_transfer.json",
    checkpoint_dir: str | Path = "checkpoints/pendulum_transfer",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    budgets: tuple[int, ...] = BUDGETS
    pool_n = 1024
    stage = STAGE_CAP
    det_src_n, det_tgt_n, recalib_n = 64, 128, 32
    exploit_n = 48
    if quick:
        n_train, n_val, epochs, adapt_epochs = 48, 24, 1, 1
        n_model_seeds = min(n_model_seeds, 1)
        eval_episodes = 1
        budgets = (0, 32, 64)
        pool_n, stage = 64, 24
        det_src_n, det_tgt_n, recalib_n, exploit_n = 16, 24, 8, 16
    source_spec = pendulum_source()
    dev = pendulum_transfer_development()
    confirms = pendulum_transfer_confirmation()
    seq = pendulum_transfer_sequence()
    curve_spec = confirms[0]
    if quick:
        confirms = confirms[:1]
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    preserved = validate_prior_artifacts()
    git = _git_meta()
    protocol = {
        "code_version": "pendulum_transfer",
        "parent_commit": "a63c391",
        "kind": FROZEN_KIND,
        "hidden": list(FROZEN_HIDDEN),
        "pendulum_horizon": PLAN_H,
        "pendulum_candidates": PLAN_CAND,
        "cartpole_horizon_frozen": FROZEN_PRIMARY_HORIZON,
        "mae_ratio": V085_MAE_RATIO,
        "retuned_mae": False,
        "retuned_width": False,
        "budgets": list(budgets),
        "stage_cap": stage,
        "n_train": n_train,
        "n_val": n_val,
        "epochs": epochs,
        "n_model_seeds": n_model_seeds,
        "eval_episodes": eval_episodes,
        "confirm_eval_seed": V089P_CONFIRM_EVAL_SEED,
        "prior_eval_seeds_unused": [V089X_EVAL_SEED, V089G_CONFIRM_EVAL_SEED],
        "primary_success": "mae_gated_minus_frozen_at_max_budget_seed_ci_lo>0",
        "l2l_success": "ABC_then_D_beats_naive_and_matched_volume_ci_lo>0",
        "cross_env_hash_frozen": CROSS_ENV_HASH,
        "generality_hash_frozen": GENERALITY_HASH,
        "is_agi": False,
        "claims_learning_to_learn": False,
        "quick": quick,
        "git": git,
    }
    protocol["protocol_hash"] = hashlib.sha256(dumps_strict(protocol).encode()).hexdigest()[:16]

    per_seed: list[dict[str, Any]] = []
    for mseed in range(n_model_seeds):
        train = collect_transitions(
            source_spec, n_transitions=n_train, env_seeds=tuple(range(10 + 8 * mseed, 18 + 8 * mseed)),
            base_seed=V089P_SOURCE_COLLECT_SEED + 19 * mseed, mix=("random",),
        )
        val = collect_transitions(
            source_spec, n_transitions=n_val, env_seeds=tuple(range(400 + 8 * mseed, 408 + 8 * mseed)),
            base_seed=V089P_VAL_SEED + 19 * mseed, mix=("random",),
        )
        assert_disjoint_seeds(train, val)
        pretrain = int(train.env_interactions + val.env_interactions)
        source, slog = train_world_model(
            train, val, kind=FROZEN_KIND, epochs=epochs, seed=V089P_TRAIN_SEED + 13 * mseed, hidden=FROZEN_HIDDEN, n_actions=PENDULUM_N_ACTIONS,
        )  # type: ignore[arg-type]
        calib = collect_transitions(
            source_spec, n_transitions=16 if quick else 48, env_seeds=tuple(range(700, 706)),
            base_seed=V089P_DETECT_SEED + mseed, mix=("random",),
        )
        pretrain += int(calib.env_interactions)
        det = WindowThresholdDetector(window=8 if quick else 32, k=3.0)
        det.fit(per_transition_mae(source, calib.obs, calib.action, calib.next_obs))
        detect = run_detection_compare(
            source_spec, dev, source, det, seed=mseed + 1, n_source=det_src_n, n_target=det_tgt_n, recalib_n=recalib_n,
        )
        adapt_s = V089P_ADAPT_SEED + 13 * mseed
        gate_s = V089P_GATE_SEED + 11 * mseed
        pool_sess = PersistentSession(curve_spec, source, env_seed=V089P_TARGET_COLLECT_SEED + mseed, plan_seed=mseed)
        pool = pool_sess.collect(pool_n)
        pool_sess.close()
        mem = PredictiveMemory(max_entries=6, replay_cap=n_train + pool_n)
        mem.store(source, val.slice(np.arange(min(24, len(val)))), stats={"stage": "source"}, label="source")
        proposals: list[dict[str, Any]] = []
        mae_run = run_mae_persistent(
            curve_spec, source, train, cap=pool_n, epochs=adapt_epochs, seed=V089P_TARGET_COLLECT_SEED + 50 + mseed,
            adapt_seed=adapt_s, gate_seed=gate_s, detector=det, snapshots_at=budgets, proposals_out=proposals,
        )
        cand_for_exploit = mae_run["model"] if mae_run["n_accept"] else apply_method(
            "low_lr", source, train, _prefix(pool, min(128, len(pool))), _prefix(pool, 0), epochs=adapt_epochs, seed=adapt_s,
        )[0]
        exploit = exploit_diagnostics(curve_spec, source, cand_for_exploit, seed=mseed, n=exploit_n)
        paired_ctrl = paired_control_eval(
            curve_spec, {"never": source, "adapted": cand_for_exploit}, seed=V089P_CONFIRM_EVAL_SEED, episodes=eval_episodes,
        )
        exploit["return_never"] = paired_ctrl["never"]["mean_return"]
        exploit["return_adapted"] = paired_ctrl["adapted"]["mean_return"]
        exploit["delta_return"] = float(paired_ctrl["adapted"]["mean_return"]) - float(paired_ctrl["never"]["mean_return"])
        n_ben = sum(1 for p in proposals if p.get("decision") == "accept" and float(p.get("control_delta") or 0) > 0)
        n_harm = sum(1 for p in proposals if p.get("decision") == "accept" and float(p.get("control_delta") or 0) < 0)

        curve: dict[str, Any] = {}
        rets: dict[str, list[float]] = {m: [] for m in METHODS}
        pred_at_max: dict[str, Any] = {}
        for b in budgets:
            fitted = fit_budget_models(source, train, pool, budget=b, epochs=adapt_epochs, seed=adapt_s + b, memory=mem, probe_n=8 if quick else 16)
            mae_m = mae_run["snapshots"].get(b, mae_run["model"])
            models = {k: fitted[k] for k in ("scratch", "frozen", "always_adapt", "low_lr", "retrieved")}
            models["mae_gated"] = mae_m
            ev = paired_control_eval(curve_spec, models, seed=V089P_CONFIRM_EVAL_SEED, episodes=eval_episodes)
            row = {
                "eval": {m: ev[m]["mean_return"] for m in METHODS},
                "train_n": fitted["train_n"],
                "val_n": fitted["val_n"],
                "probe_n": fitted["probe_n"],
                "mae_accept_so_far": mae_run["n_accept"],
            }
            if b == budgets[-1]:
                pred_at_max = {m: _pred(models[m], val) for m in METHODS}
                row["prediction_on_source_val"] = pred_at_max
            curve[str(b)] = row
            for m in METHODS:
                rets[m].append(float(ev[m]["mean_return"]))
        auc = {m: _auc(budgets, rets[m]) for m in METHODS}

        confirm_final: dict[str, Any] = {}
        for spec in confirms:
            fitted = fit_budget_models(
                source, train, pool if spec.task_id == curve_spec.task_id else pool,
                budget=budgets[-1], epochs=adapt_epochs, seed=adapt_s + 999, memory=mem, probe_n=8 if quick else 16,
            )
            # Independent target pool for non-curve confirm physics so g/m/l eval is not the curve collect.
            if spec.task_id != curve_spec.task_id:
                tsess = PersistentSession(spec, source, env_seed=V089P_TARGET_COLLECT_SEED + 80 + mseed, plan_seed=mseed + 7)
                tpool = tsess.collect(pool_n)
                tsess.close()
                fitted = fit_budget_models(source, train, tpool, budget=budgets[-1], epochs=adapt_epochs, seed=adapt_s + 1000, memory=mem, probe_n=8 if quick else 16)
                mae_t = run_mae_persistent(
                    spec, source, train, cap=pool_n, epochs=adapt_epochs, seed=V089P_TARGET_COLLECT_SEED + 90 + mseed,
                    adapt_seed=adapt_s, gate_seed=gate_s, detector=copy_detector(det), snapshots_at=(0, pool_n),
                )
                mae_m = mae_t["model"]
                n_acc_t, n_prop_t = mae_t["n_accept"], mae_t["n_propose"]
            else:
                mae_m = mae_run["model"]
                n_acc_t, n_prop_t = mae_run["n_accept"], mae_run["n_propose"]
            models = {k: fitted[k] for k in ("scratch", "frozen", "always_adapt", "low_lr", "retrieved")}
            models["mae_gated"] = mae_m
            ev = paired_control_eval(spec, models, seed=V089P_CONFIRM_EVAL_SEED, episodes=eval_episodes)
            confirm_final[spec.task_id] = {
                "params": dict(spec.params),
                "eval": {m: ev[m]["mean_return"] for m in METHODS},
                "mae_accept": n_acc_t,
                "mae_propose": n_prop_t,
            }

        a, btsk, c, d = seq
        abc = source.clone()
        acc_seq = 0
        for ti, sp in enumerate((a, btsk, c)):
            st = adapt_stage(sp, abc, train, cap=stage, epochs=adapt_epochs, seed=V089P_SEQUENCE_EVAL_SEED + ti + 10 * mseed, adapt_seed=adapt_s, gate_seed=gate_s, detector=det)
            abc = st["model"]
            acc_seq += int(st["n_accept"])
            mem.store(abc, val.slice(np.arange(min(8, len(val)))), stats={"stage": f"seq{ti}"}, label=f"s{ti}")
        d_from_abc = adapt_stage(d, abc, train, cap=stage, epochs=adapt_epochs, seed=V089P_SEQUENCE_EVAL_SEED + 80 + mseed, adapt_seed=adapt_s, gate_seed=gate_s, detector=det)
        d_naive = adapt_stage(d, source, train, cap=stage, epochs=adapt_epochs, seed=V089P_SEQUENCE_EVAL_SEED + 100 + mseed, adapt_seed=adapt_s, gate_seed=gate_s, detector=det)
        d_matched = adapt_stage(d, source, train, cap=4 * stage, epochs=adapt_epochs, seed=V089P_SEQUENCE_EVAL_SEED + 110 + mseed, adapt_seed=adapt_s, gate_seed=gate_s, detector=det)
        transfer_models = {
            "naive_D": d_naive["model"],
            "ABC_then_D": d_from_abc["model"],
            "matched_D_volume": d_matched["model"],
            "source": source,
        }
        tr_eval = paired_control_eval(d, transfer_models, seed=V089P_CONFIRM_EVAL_SEED, episodes=eval_episodes)

        def _mean_method(name: str) -> float:
            return float(np.mean([confirm_final[tid]["eval"][name] for tid in confirm_final]))

        per_seed.append(
            {
                "model_seed": mseed,
                "pretrain": pretrain,
                "source_val": slog["best_val"],
                "nbytes": checkpoint_nbytes(source),
                "detection": detect,
                "exploit": exploit,
                "curve": curve,
                "auc": auc,
                "prediction_at_max": pred_at_max,
                "mae_online": {
                    "n_accept": mae_run["n_accept"],
                    "n_propose": mae_run["n_propose"],
                    "n_reject": mae_run["n_reject"],
                    "n_beneficial_accept": n_ben,
                    "n_harmful_accept": n_harm,
                    "ledger": mae_run["ledger"],
                    "n_resets": mae_run["n_resets"],
                },
                "confirm_final": confirm_final,
                "confirm_mean": {m: _mean_method(m) for m in METHODS},
                "pool_interactions": int(pool.env_interactions),
                "transfer": {
                    "D": {k: tr_eval[k]["mean_return"] for k in tr_eval},
                    "delta_ABC_vs_naive": float(tr_eval["ABC_then_D"]["mean_return"]) - float(tr_eval["naive_D"]["mean_return"]),
                    "delta_ABC_vs_matched": float(tr_eval["ABC_then_D"]["mean_return"]) - float(tr_eval["matched_D_volume"]["mean_return"]),
                    "abc_accepts": acc_seq,
                    "D_accepts": {"naive": d_naive["n_accept"], "abc": d_from_abc["n_accept"], "matched": d_matched["n_accept"]},
                    "stage_cap": stage,
                    "matched_cap": 4 * stage,
                },
            }
        )
        print(f"pendulum_transfer seed={mseed}", flush=True)

    def _ci(xs: list[float]) -> dict[str, Any] | None:
        return seed_level_ci(xs) if xs else None

    mae_vs_fr = [float(s["confirm_mean"]["mae_gated"]) - float(s["confirm_mean"]["frozen"]) for s in per_seed]
    low_vs_fr = [float(s["confirm_mean"]["low_lr"]) - float(s["confirm_mean"]["frozen"]) for s in per_seed]
    alw_vs_fr = [float(s["confirm_mean"]["always_adapt"]) - float(s["confirm_mean"]["frozen"]) for s in per_seed]
    scr_vs_fr = [float(s["confirm_mean"]["scratch"]) - float(s["confirm_mean"]["frozen"]) for s in per_seed]
    abc_vs_n = [float(s["transfer"]["delta_ABC_vs_naive"]) for s in per_seed]
    abc_vs_m = [float(s["transfer"]["delta_ABC_vs_matched"]) for s in per_seed]
    mae_ci = _ci(mae_vs_fr)
    l2l_ci_n = _ci(abc_vs_n)
    l2l_ci_m = _ci(abc_vs_m)
    adapt_ok = bool(mae_ci) and float(mae_ci["lo"]) > 0
    l2l_ok = bool(l2l_ci_n) and float(l2l_ci_n["lo"]) > 0 and bool(l2l_ci_m) and float(l2l_ci_m["lo"]) > 0
    payload = {
        "protocol": protocol,
        "audit": preserved,
        "tasks": {
            "source": dict(source_spec.params) | {"task_id": source_spec.task_id},
            "development": dict(dev.params) | {"task_id": dev.task_id},
            "confirmation": [dict(t.params) | {"task_id": t.task_id} for t in confirms],
            "sequence": [dict(t.params) | {"task_id": t.task_id} for t in seq],
            "curve_task": curve_spec.task_id,
        },
        "detection": {
            k: {
                "source_alarm_frac": _ci([float(s["detection"]["fpr"][k]["alarm_frac"]) for s in per_seed]),
                "target_delay": _ci([float(s["detection"]["target"][k]["delay"]) for s in per_seed if s["detection"]["target"][k]["delay"] is not None]),
                "target_miss": _ci([float(s["detection"]["target"][k]["missed"]) for s in per_seed]),
            }
            for k in ("fixed", "recalib", "trend")
        },
        "learning_curve": {
            "budgets": list(budgets),
            "curve_task": curve_spec.task_id,
            "offline_note": "always_adapt and low_lr fit the persistent pool prefix (train+val inside the budget). mae_gated is deployed online.",
            "mae_gated_accepts": _ci([float(s["mae_online"]["n_accept"]) for s in per_seed]),
            "mae_gated_proposes": _ci([float(s["mae_online"]["n_propose"]) for s in per_seed]),
            "beneficial_accepts": _ci([float(s["mae_online"]["n_beneficial_accept"]) for s in per_seed]),
            "harmful_accepts": _ci([float(s["mae_online"]["n_harmful_accept"]) for s in per_seed]),
            "final_return_curve_task": {m: _ci([float(s["curve"][str(budgets[-1])]["eval"][m]) for s in per_seed]) for m in METHODS},
            "auc": {m: _ci([float(s["auc"][m]) for s in per_seed]) for m in METHODS},
            "auc_minus_frozen": {m: _ci([float(s["auc"][m]) - float(s["auc"]["frozen"]) for s in per_seed]) for m in METHODS if m != "frozen"},
            "mean_return_by_budget": {
                m: {str(b): float(np.mean([s["curve"][str(b)]["eval"][m] for s in per_seed])) for b in budgets} for m in METHODS
            },
        },
        "confirmation": {
            "mean_return": {m: _ci([float(s["confirm_mean"][m]) for s in per_seed]) for m in METHODS},
            "mae_gated_minus_frozen": mae_ci,
            "low_lr_minus_frozen": _ci(low_vs_fr),
            "always_adapt_minus_frozen": _ci(alw_vs_fr),
            "scratch_minus_frozen": _ci(scr_vs_fr),
            "retrieved_minus_frozen": _ci([float(s["confirm_mean"]["retrieved"]) - float(s["confirm_mean"]["frozen"]) for s in per_seed]),
        },
        "transfer": {
            "D_naive": _ci([float(s["transfer"]["D"]["naive_D"]) for s in per_seed]),
            "D_ABC": _ci([float(s["transfer"]["D"]["ABC_then_D"]) for s in per_seed]),
            "D_matched_volume": _ci([float(s["transfer"]["D"]["matched_D_volume"]) for s in per_seed]),
            "delta_ABC_vs_naive": l2l_ci_n,
            "delta_ABC_vs_matched": l2l_ci_m,
        },
        "decision": {
            "adaptation_success": adapt_ok,
            "learning_to_learn_success": l2l_ok,
            "reason": (
                "MAE-gated return beats frozen on confirm"
                if adapt_ok
                else "MAE-gated vs frozen CI includes 0 or is negative"
            )
            + (
                "; prior tasks improved D under matched compute"
                if l2l_ok
                else "; prior-task experience did not improve D under fair controls (not L2L)"
            ),
        },
        "costs": {
            "mean_pretrain": float(np.mean([s["pretrain"] for s in per_seed])) if per_seed else 0.0,
            "mean_nbytes": float(np.mean([s["nbytes"] for s in per_seed])) if per_seed else 0.0,
            "pool_n": pool_n,
            "stage_cap": stage,
            "horizon": PLAN_H,
            "candidates": PLAN_CAND,
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "Independent source models, same algorithm. Beating frozen is not learning-to-learn. Not AGI.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload


def unused_prior_confirm_g() -> set[tuple[float, float, float]]:
    keys = {pendulum_physics_key(t) for t in pendulum_confirmation_targets()}
    keys.add(pendulum_physics_key(pendulum_source()))
    return keys
