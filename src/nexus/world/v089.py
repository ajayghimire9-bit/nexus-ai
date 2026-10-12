"""V0.8.9 learning efficiency and persistent online control. Frozen MAE 0.97. Not AGI."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import numpy as np

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v089_confirmation_targets,
    v089_development_target,
    v089_sequence_tasks,
)
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec
from nexus.world.adapt import WindowThresholdDetector, per_transition_mae
from nexus.world.agent import InteractionLedger
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, collect_transitions, concat_datasets
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL
from nexus.world.imagine import multi_step_errors
from nexus.world.memory import PredictiveMemory
from nexus.world.protocol import (
    V089_ADAPT_SEED,
    V089_CONFIRM_EVAL_SEED,
    V089_DETECT_SEED,
    V089_DEV_EVAL_SEED,
    V089_EXPLOIT_SEED,
    V089_GATE_SEED,
    V089_SEQUENCE_EVAL_SEED,
    V089_SOURCE_COLLECT_SEED,
    V089_TARGET_COLLECT_SEED,
)
from nexus.world.session import PersistentSession
from nexus.world.train import one_step_errors, train_world_model
from nexus.world.v085 import _git_meta
from nexus.world.v086 import apply_method
from nexus.world.v087 import paired_control_eval
from nexus.world.v088 import copy_detector
from nexus.world.verify import GateInput, V085_MAE_RATIO, V085_MAE_STEPS, mpc_action_disagreement, run_gate, weights_hash

BUDGETS = (0, 64, 128, 256, 512, 1024)
TRAIN_N, VAL_N = 128, 64
STAGE_CAP = TRAIN_N + VAL_N + V085_MAE_STEPS  # 224: one full MAE cycle; not from confirmation
FAIL_TAIL = 8


def _auc(xs: list[int] | tuple[int, ...], ys: list[float]) -> float:
    x = np.asarray(xs, dtype=np.float64)
    y = np.asarray(ys, dtype=np.float64)
    if x.size < 2:
        return 0.0
    fn = getattr(np, "trapezoid", None) or np.trapz
    return float(fn(y, x))


def _mae(wm: Any, ds: TransitionDataset) -> float | None:
    if len(ds) == 0:
        return None
    return float(one_step_errors(wm, ds)["mae"])


def fail_tail_mae(wm: Any, ds: TransitionDataset, k: int = FAIL_TAIL) -> float | None:
    if len(ds) == 0:
        return None
    idx = np.where(np.asarray(ds.terminated))[0]
    if idx.size == 0:
        return None
    sl: list[int] = []
    for t in idx:
        lo = max(0, int(t) - int(k) + 1)
        sl.extend(range(lo, int(t) + 1))
    sl_u = np.unique(np.asarray(sl, dtype=np.int64))
    return _mae(wm, ds.slice(sl_u))


def scan_detector(det: WindowThresholdDetector, errors: np.ndarray) -> dict[str, Any]:
    d = copy_detector(det)
    d._buf = []
    return d.scan(errors)


def run_detection_compare(
    source_spec: TaskSpec,
    target_spec: TaskSpec,
    source: Any,
    source_det: WindowThresholdDetector,
    *,
    seed: int,
    n_source: int,
    n_target: int,
    recalib_n: int,
) -> dict[str, Any]:
    """Independent detection streams. No candidate training data."""
    sess = PersistentSession(source_spec, source, env_seed=int(seed), plan_seed=V089_DETECT_SEED + int(seed))
    src_ds = sess.collect(int(n_source))
    src_err = per_transition_mae(source, src_ds.obs, src_ds.action, src_ds.next_obs) if len(src_ds) else np.zeros(0)
    n_fit = min(int(recalib_n), max(0, len(src_err) // 2))
    hold_src = src_err[:n_fit] if n_fit else src_err
    scan_src = src_err[n_fit:] if n_fit else src_err
    fixed = copy_detector(source_det)
    recal = WindowThresholdDetector(window=source_det.window, k=source_det.k)
    if hold_src.size:
        recal.fit(hold_src)
    else:
        recal.fit(np.asarray([source_det.source_mean]))
    trend = WindowThresholdDetector(window=source_det.window, k=source_det.k)
    if hold_src.size:
        trend.fit(hold_src)
    else:
        trend.fit(np.asarray([source_det.source_mean]))
    fpr = {
        "fixed": scan_detector(fixed, scan_src) if scan_src.size else {"n_alarm": 0, "missed": True, "detection_delay": None, "alarm_frac": 0.0},
        "recalib": scan_detector(recal, scan_src) if scan_src.size else {"n_alarm": 0, "missed": True, "detection_delay": None, "alarm_frac": 0.0},
        "trend": scan_detector(trend, scan_src) if scan_src.size else {"n_alarm": 0, "missed": True, "detection_delay": None, "alarm_frac": 0.0},
    }
    sess.switch_task(target_spec, env_seed=int(seed) + 17)
    tgt_ds = sess.collect(int(n_target))
    tgt_err = per_transition_mae(source, tgt_ds.obs, tgt_ds.action, tgt_ds.next_obs) if len(tgt_ds) else np.zeros(0)
    delay = {
        "fixed": scan_detector(fixed, tgt_err),
        "recalib": scan_detector(recal, tgt_err),
        "trend": scan_detector(trend, tgt_err),
    }
    sess.close()
    return {
        "source_interactions": int(src_ds.env_interactions),
        "target_interactions": int(tgt_ds.env_interactions),
        "n_resets": sess.n_resets,
        "n_scheduled_switches": sess.n_scheduled_switches,
        "recalib_n": n_fit,
        "used_train_for_detection": False,
        "fpr": {k: {"alarm_frac": float(v.get("alarm_frac") or 0.0), "n_alarm": v.get("n_alarm")} for k, v in fpr.items()},
        "target": {
            k: {
                "delay": v.get("detection_delay"),
                "missed": bool(v.get("missed")),
                "alarm_frac": float(v.get("alarm_frac") or 0.0),
            }
            for k, v in delay.items()
        },
    }


def exploit_diagnostics(
    spec: TaskSpec,
    incumbent: Any,
    candidate: Any,
    *,
    seed: int,
    n: int,
) -> dict[str, Any]:
    si = PersistentSession(spec, incumbent, env_seed=int(seed), plan_seed=V089_EXPLOIT_SEED + int(seed))
    sc = PersistentSession(spec, candidate, env_seed=int(seed) + 3, plan_seed=V089_EXPLOIT_SEED + 50 + int(seed))
    tr_i = si.collect(int(n))
    tr_c = sc.collect(int(n))
    si.close()
    sc.close()
    ms_i_on_i = multi_step_errors(incumbent, tr_i, (1, 3, 8))
    ms_c_on_c = multi_step_errors(candidate, tr_c, (1, 3, 8))
    ms_c_on_i = multi_step_errors(candidate, tr_i, (1, 3, 8))
    disag = mpc_action_disagreement(incumbent, candidate, tr_i.obs, seed=int(seed))
    return {
        "collect_inc": int(tr_i.env_interactions),
        "collect_cand": int(tr_c.env_interactions),
        "one_step_mae_inc_on_inc": _mae(incumbent, tr_i),
        "one_step_mae_cand_on_inc": _mae(candidate, tr_i),
        "one_step_mae_inc_on_cand": _mae(incumbent, tr_c),
        "one_step_mae_cand_on_cand": _mae(candidate, tr_c),
        "fail_tail_mae_inc_on_inc": fail_tail_mae(incumbent, tr_i),
        "fail_tail_mae_cand_on_cand": fail_tail_mae(candidate, tr_c),
        "multi_h3_inc_on_inc": ms_i_on_i.get("3", {}).get("mean_mae"),
        "multi_h3_cand_on_cand": ms_c_on_c.get("3", {}).get("mean_mae"),
        "multi_h3_cand_on_inc": ms_c_on_i.get("3", {}).get("mean_mae"),
        "action_disagreement": disag,
        "shift_on_own_traj": bool(
            _mae(candidate, tr_c) is not None
            and _mae(incumbent, tr_i) is not None
            and float(_mae(candidate, tr_c) or 0) > float(_mae(incumbent, tr_i) or 0)
        ),
    }


def run_mae_persistent(
    spec: TaskSpec,
    source: Any,
    replay: Any,
    *,
    cap: int,
    epochs: int,
    seed: int,
    adapt_seed: int,
    gate_seed: int,
    detector: WindowThresholdDetector,
    train_n: int = TRAIN_N,
    val_n: int = VAL_N,
    snapshots_at: tuple[int, ...] = BUDGETS,
) -> dict[str, Any]:
    deployed = source.clone()
    det = copy_detector(detector)
    det._buf = []
    sess = PersistentSession(spec, deployed, env_seed=int(seed), plan_seed=int(seed) + 9)
    ledger = InteractionLedger(target_cap=int(cap))
    snaps: dict[int, Any] = {0: source.clone()}
    n_accept = n_propose = n_reject = 0
    watch: list[dict[str, Any]] = []
    hashes = [{"stage": "start", "hash": weights_hash(deployed)}]
    used = 0

    def _flush_watch() -> TransitionDataset:
        nonlocal watch
        if not watch:
            return sess.collect(0)
        recs, watch = watch, []
        return TransitionDataset(
            obs=np.stack([r["obs"] for r in recs]),
            action=np.asarray([r["action"] for r in recs], dtype=np.int64),
            next_obs=np.stack([r["next_obs"] for r in recs]),
            reward=np.asarray([r["reward"] for r in recs], dtype=np.float32),
            terminated=np.asarray([r["terminated"] for r in recs], dtype=np.bool_),
            truncated=np.asarray([r["truncated"] for r in recs], dtype=np.bool_),
            task_id=spec.task_id,
            seed=np.asarray([r["seed"] for r in recs], dtype=np.int64),
            episode_id=np.asarray([r["episode_id"] for r in recs], dtype=np.int64),
            policy=np.asarray(["persistent_mpc"] * len(recs), dtype=object),
            physics=dict(spec.params),
            env_interactions=len(recs),
        )

    while ledger.remaining > 0:
        rec = sess.step()
        ledger.charge(1, "detect")
        used += 1
        err = float(per_transition_mae(deployed, rec["obs"][None], np.asarray([rec["action"]]), rec["next_obs"][None])[0])
        alarm = bool(det.update(err)["alarm"])
        watch.append(rec)
        if int(ledger.target_used) in snapshots_at:
            snaps[int(ledger.target_used)] = deployed.clone()
        need = int(train_n) + int(val_n) + int(V085_MAE_STEPS)
        if alarm and len(watch) >= int(train_n) and ledger.remaining >= int(val_n) + int(V085_MAE_STEPS):
            train_ds = _flush_watch()
            if len(train_ds) > int(train_n):
                train_ds = train_ds.slice(np.arange(int(train_n)))
            val_ds = sess.collect(min(int(val_n), ledger.remaining - int(V085_MAE_STEPS)))
            if len(val_ds):
                ledger.charge(int(val_ds.env_interactions), "adapt_collect")
            cand, _log = apply_method("low_lr", deployed, replay, train_ds, val_ds, epochs=epochs, seed=int(adapt_seed) + n_propose)
            n_propose += 1
            g = run_gate("mae", GateInput(spec=spec, incumbent=deployed, candidate=cand, ledger=ledger, seed=int(gate_seed) + n_propose))
            if g["decision"] == "accept":
                deployed = cand
                sess.set_model(deployed)
                n_accept += 1
                hashes.append({"stage": f"acc{n_accept}", "hash": weights_hash(deployed), "accepted": True})
            else:
                n_reject += 1
            det._buf = []
        del need
    for b in snapshots_at:
        if b not in snaps and used >= b:
            snaps[b] = deployed.clone()
        elif b not in snaps:
            snaps[b] = snaps[max(k for k in snaps if k <= b)] if any(k <= b for k in snaps) else source.clone()
    sess.close()
    snaps[int(cap)] = deployed.clone()
    return {
        "model": deployed,
        "snapshots": snaps,
        "n_accept": n_accept,
        "n_propose": n_propose,
        "n_reject": n_reject,
        "ledger": ledger.snapshot(),
        "n_resets": sess.n_resets,
        "hashes": hashes,
        "committed_hash": weights_hash(deployed),
        "source_hash": weights_hash(source),
    }


def _prefix(ds: TransitionDataset, n: int) -> TransitionDataset:
    n = max(0, min(int(n), len(ds)))
    return ds.slice(np.arange(n)) if n else ds.slice(np.zeros((0,), dtype=np.int64))


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
    """Off-policy methods on a frozen persistent pool prefix. Val is a suffix of the prefix."""
    take = min(int(budget), len(pool))
    if take <= 0:
        empty = _prefix(pool, 0)
        retrieved, meta = memory.retrieve(empty)
        return {
            "scratch": WorldModel.create(4, 2, kind="residual", seed=int(seed)),
            "frozen": source,
            "low_lr": source,
            "replay": source,
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
    scratch, _ = train_world_model(tr if n_tr >= 8 else pool, va if n_val else tr, kind=FROZEN_KIND, epochs=epochs, seed=int(seed))  # type: ignore[arg-type]
    low, _ = apply_method("low_lr", source, replay, tr, va, epochs=epochs, seed=int(seed) + 1)
    rep, _ = apply_method("replay", source, replay, tr, va, epochs=epochs, seed=int(seed) + 2)
    probe = _prefix(va if n_val else tr, min(int(probe_n), len(va) if n_val else len(tr)))
    retrieved, meta = memory.retrieve(probe)
    return {
        "scratch": scratch,
        "frozen": source,
        "low_lr": low,
        "replay": rep,
        "retrieved": retrieved or source,
        "val_n": n_val,
        "train_n": n_tr,
        "probe_n": len(probe),
        "retrieval": meta,
    }


def adapt_stage(spec: TaskSpec, wm: Any, replay: Any, *, cap: int, epochs: int, seed: int, adapt_seed: int, gate_seed: int, detector: WindowThresholdDetector) -> dict[str, Any]:
    return run_mae_persistent(
        spec, wm, replay, cap=cap, epochs=epochs, seed=seed, adapt_seed=adapt_seed, gate_seed=gate_seed, detector=detector, snapshots_at=(0, cap),
    )


def run_v089_benchmark(
    *,
    n_model_seeds: int = 10,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    adapt_epochs: int = 8,
    eval_episodes: int = 2,
    artifact_path: str | Path | None = "artifacts/v089_learning.json",
    checkpoint_dir: str | Path = "checkpoints/v089",
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
    source_spec = source_policy_task()
    dev = v089_development_target()
    confirms = v089_confirmation_targets()
    seq = v089_sequence_tasks()
    curve_spec = confirms[0]
    if quick:
        confirms = confirms[:1]
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    git = _git_meta()
    protocol = {
        "code_version": "v0.8.9",
        "parent_commit": "24ca276",
        "physics_version": CARTPOLE_PHYSICS_VERSION,
        "mae_ratio": V085_MAE_RATIO,
        "retuned_mae": False,
        "budgets": list(budgets),
        "stage_cap": stage,
        "confirm_eval_seed": V089_CONFIRM_EVAL_SEED,
        "dev_eval_seed": V089_DEV_EVAL_SEED,
        "n_model_seeds": n_model_seeds,
        "paired_eval": True,
        "persistent_episodes": True,
        "reference_feeds_gate": False,
        "planned_runtime_note": "n=10 persistent detection + exploitation + learning curve + A-B-C-A / A-B-D; ~15–35 min CPU",
        "is_agi": False,
        "quick": quick,
        "git": git,
    }
    protocol["protocol_hash"] = hashlib.sha256(dumps_strict(protocol).encode()).hexdigest()[:16]

    per_seed: list[dict[str, Any]] = []
    methods = ("scratch", "frozen", "low_lr", "replay", "retrieved", "mae_gated")

    for mseed in range(n_model_seeds):
        train = collect_transitions(
            source_spec, n_transitions=n_train, env_seeds=tuple(range(12 + 20 * mseed, 32 + 20 * mseed)),
            base_seed=V089_SOURCE_COLLECT_SEED + 19 * mseed, mix=("random", "exploratory"),
        )
        val = collect_transitions(
            source_spec, n_transitions=n_val, env_seeds=tuple(range(420 + 8 * mseed, 428 + 8 * mseed)),
            base_seed=V089_SOURCE_COLLECT_SEED + 300 + 19 * mseed, mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val)
        pretrain = train.env_interactions + val.env_interactions
        source, slog = train_world_model(train, val, kind=FROZEN_KIND, epochs=epochs, seed=4 + 13 * mseed)  # type: ignore[arg-type]
        calib = collect_transitions(
            source_spec, n_transitions=16 if quick else 48, env_seeds=tuple(range(700, 706)),
            base_seed=V089_DETECT_SEED + mseed, mix=("random",),
        )
        pretrain += calib.env_interactions
        det = WindowThresholdDetector(window=8 if quick else 32, k=3.0)
        det.fit(per_transition_mae(source, calib.obs, calib.action, calib.next_obs))

        detect = run_detection_compare(
            source_spec, dev, source, det, seed=mseed + 1, n_source=det_src_n, n_target=det_tgt_n, recalib_n=recalib_n,
        )

        adapt_s = V089_ADAPT_SEED + 13 * mseed
        gate_s = V089_GATE_SEED + 11 * mseed
        pool_sess = PersistentSession(curve_spec, source, env_seed=V089_TARGET_COLLECT_SEED + mseed, plan_seed=mseed)
        pool = pool_sess.collect(pool_n)
        pool_sess.close()
        mem = PredictiveMemory(max_entries=6, replay_cap=n_train + pool_n)
        mem.store(source, val.slice(np.arange(min(24, len(val)))), stats={"stage": "source"}, label="source")

        mae_run = run_mae_persistent(
            curve_spec, source, train, cap=pool_n, epochs=adapt_epochs, seed=V089_TARGET_COLLECT_SEED + 50 + mseed,
            adapt_seed=adapt_s, gate_seed=gate_s, detector=det, snapshots_at=budgets,
        )
        cand_for_exploit = mae_run["model"] if mae_run["n_accept"] else apply_method(
            "low_lr", source, train, _prefix(pool, min(128, len(pool))), _prefix(pool, 0), epochs=adapt_epochs, seed=adapt_s,
        )[0]
        exploit = exploit_diagnostics(curve_spec, source, cand_for_exploit, seed=mseed, n=exploit_n)
        paired_ctrl = paired_control_eval(
            curve_spec, {"never": source, "adapted": cand_for_exploit}, seed=V089_CONFIRM_EVAL_SEED, episodes=eval_episodes,
        )
        exploit["return_never"] = paired_ctrl["never"]["mean_return"]
        exploit["return_adapted"] = paired_ctrl["adapted"]["mean_return"]
        exploit["delta_return"] = float(paired_ctrl["adapted"]["mean_return"]) - float(paired_ctrl["never"]["mean_return"])

        curve: dict[str, Any] = {}
        rets: dict[str, list[float]] = {m: [] for m in methods}
        for b in budgets:
            fitted = fit_budget_models(source, train, pool, budget=b, epochs=adapt_epochs, seed=adapt_s + b, memory=mem, probe_n=8 if quick else 16)
            mae_m = mae_run["snapshots"].get(b, mae_run["model"])
            models = {k: fitted[k] for k in ("scratch", "frozen", "low_lr", "replay", "retrieved")}
            models["mae_gated"] = mae_m
            ev = paired_control_eval(curve_spec, models, seed=V089_CONFIRM_EVAL_SEED, episodes=eval_episodes)
            curve[str(b)] = {
                "eval": {m: ev[m]["mean_return"] for m in methods},
                "train_n": fitted["train_n"],
                "val_n": fitted["val_n"],
                "probe_n": fitted["probe_n"],
                "mae_accept_so_far": mae_run["n_accept"],
            }
            for m in methods:
                rets[m].append(float(ev[m]["mean_return"]))

        auc = {m: _auc(budgets, rets[m]) for m in methods}

        # Transfer: A-B-C then D vs naive D vs data-matched D
        a, b, c, d = seq
        abc = source.clone()
        replay_abc = train
        acc_seq = 0
        for ti, sp in enumerate((a, b, c)):
            st = adapt_stage(sp, abc, replay_abc, cap=stage, epochs=adapt_epochs, seed=V089_SEQUENCE_EVAL_SEED + ti + 10 * mseed, adapt_seed=adapt_s, gate_seed=gate_s, detector=det)
            abc = st["model"]
            acc_seq += int(st["n_accept"])
            mem.store(abc, val.slice(np.arange(min(8, len(val)))), stats={"stage": f"seq{ti}"}, label=f"s{ti}")
        abd_skip_c = source.clone()
        for ti, sp in enumerate((a, b)):
            st = adapt_stage(sp, abd_skip_c, train, cap=stage, epochs=adapt_epochs, seed=V089_SEQUENCE_EVAL_SEED + 30 + ti + 10 * mseed, adapt_seed=adapt_s, gate_seed=gate_s, detector=det)
            abd_skip_c = st["model"]
        d_from_abc = adapt_stage(d, abc, replay_abc, cap=stage, epochs=adapt_epochs, seed=V089_SEQUENCE_EVAL_SEED + 80 + mseed, adapt_seed=adapt_s, gate_seed=gate_s, detector=det)
        d_from_ab = adapt_stage(d, abd_skip_c, train, cap=stage, epochs=adapt_epochs, seed=V089_SEQUENCE_EVAL_SEED + 90 + mseed, adapt_seed=adapt_s, gate_seed=gate_s, detector=det)
        d_naive = adapt_stage(d, source, train, cap=stage, epochs=adapt_epochs, seed=V089_SEQUENCE_EVAL_SEED + 100 + mseed, adapt_seed=adapt_s, gate_seed=gate_s, detector=det)
        d_matched = adapt_stage(d, source, train, cap=4 * stage, epochs=adapt_epochs, seed=V089_SEQUENCE_EVAL_SEED + 110 + mseed, adapt_seed=adapt_s, gate_seed=gate_s, detector=det)
        a_return = adapt_stage(a, abc, replay_abc, cap=stage, epochs=adapt_epochs, seed=V089_SEQUENCE_EVAL_SEED + 120 + mseed, adapt_seed=adapt_s, gate_seed=gate_s, detector=det)
        transfer_models = {
            "naive_D": d_naive["model"],
            "ABC_then_D": d_from_abc["model"],
            "AB_then_D": d_from_ab["model"],
            "matched_D_volume": d_matched["model"],
            "source": source,
            "A_return": a_return["model"],
        }
        tr_eval = paired_control_eval(d, {k: v for k, v in transfer_models.items() if k != "A_return"}, seed=V089_CONFIRM_EVAL_SEED, episodes=eval_episodes)
        a_eval = paired_control_eval(a, {"A_return": a_return["model"], "source": source, "naive": source}, seed=V089_CONFIRM_EVAL_SEED, episodes=eval_episodes)

        per_seed.append(
            {
                "model_seed": mseed,
                "pretrain": pretrain,
                "source_val": slog["best_val"],
                "detection": detect,
                "exploit": exploit,
                "curve": curve,
                "auc": auc,
                "mae_online": {"n_accept": mae_run["n_accept"], "n_propose": mae_run["n_propose"], "n_reject": mae_run["n_reject"], "ledger": mae_run["ledger"], "n_resets": mae_run["n_resets"]},
                "pool_interactions": int(pool.env_interactions),
                "transfer": {
                    "D": {k: tr_eval[k]["mean_return"] for k in tr_eval},
                    "delta_ABC_vs_naive": float(tr_eval["ABC_then_D"]["mean_return"]) - float(tr_eval["naive_D"]["mean_return"]),
                    "delta_ABC_vs_matched": float(tr_eval["ABC_then_D"]["mean_return"]) - float(tr_eval["matched_D_volume"]["mean_return"]),
                    "A_return": a_eval["A_return"]["mean_return"],
                    "A_source": a_eval["source"]["mean_return"],
                    "abc_accepts": acc_seq,
                    "D_accepts": {"naive": d_naive["n_accept"], "abc": d_from_abc["n_accept"], "matched": d_matched["n_accept"]},
                    "stage_cap": stage,
                    "matched_cap": 4 * stage,
                },
            }
        )
        print(f"v089 seed={mseed}", flush=True)

    def _g(path: str) -> list[float]:
        out = []
        for s in per_seed:
            cur = s
            for p in path.split("."):
                cur = cur[p] if not p.isdigit() else cur[p]
            out.append(float(cur))
        return out

    det_keys = ("fixed", "recalib", "trend")
    payload = {
        "protocol": protocol,
        "tasks": {
            "development": dict(dev.params) | {"task_id": dev.task_id},
            "confirmation": [dict(t.params) | {"task_id": t.task_id} for t in confirms],
            "curve_task": curve_spec.task_id,
        },
        "detection": {
            k: {
                "source_alarm_frac": seed_level_ci([float(s["detection"]["fpr"][k]["alarm_frac"]) for s in per_seed]),
                "target_delay": seed_level_ci([float(s["detection"]["target"][k]["delay"]) for s in per_seed if s["detection"]["target"][k]["delay"] is not None]) if any(s["detection"]["target"][k]["delay"] is not None for s in per_seed) else None,
                "target_miss": seed_level_ci([float(s["detection"]["target"][k]["missed"]) for s in per_seed]),
            }
            for k in det_keys
        },
        "exploitation": {
            "delta_return": seed_level_ci([float(s["exploit"]["delta_return"]) for s in per_seed]),
            "action_disagreement": seed_level_ci([float(s["exploit"]["action_disagreement"]) for s in per_seed]),
            "mae_cand_on_cand": seed_level_ci([float(s["exploit"]["one_step_mae_cand_on_cand"] or np.nan) for s in per_seed]),
            "mae_inc_on_inc": seed_level_ci([float(s["exploit"]["one_step_mae_inc_on_inc"] or np.nan) for s in per_seed]),
            "shift_on_own_traj_rate": seed_level_ci([float(s["exploit"]["shift_on_own_traj"]) for s in per_seed]),
        },
        "learning_curve": {
            "budgets": list(budgets),
            "mae_gated_accepts": seed_level_ci([float(s["mae_online"]["n_accept"]) for s in per_seed]),
            "mae_gated_proposes": seed_level_ci([float(s["mae_online"]["n_propose"]) for s in per_seed]),
            "final_return": {
                m: seed_level_ci([float(s["curve"][str(budgets[-1])]["eval"][m]) for s in per_seed]) for m in methods
            },
            "auc": {m: seed_level_ci([float(s["auc"][m]) for s in per_seed]) for m in methods},
            "mean_return_by_budget": {
                m: {str(b): float(np.mean([s["curve"][str(b)]["eval"][m] for s in per_seed])) for b in budgets} for m in methods
            },
        },
        "transfer": {
            "D_naive": seed_level_ci([float(s["transfer"]["D"]["naive_D"]) for s in per_seed]),
            "D_ABC": seed_level_ci([float(s["transfer"]["D"]["ABC_then_D"]) for s in per_seed]),
            "D_AB": seed_level_ci([float(s["transfer"]["D"]["AB_then_D"]) for s in per_seed]),
            "D_matched_volume": seed_level_ci([float(s["transfer"]["D"]["matched_D_volume"]) for s in per_seed]),
            "delta_ABC_vs_naive": seed_level_ci([float(s["transfer"]["delta_ABC_vs_naive"]) for s in per_seed]),
            "delta_ABC_vs_matched": seed_level_ci([float(s["transfer"]["delta_ABC_vs_matched"]) for s in per_seed]),
            "A_return": seed_level_ci([float(s["transfer"]["A_return"]) for s in per_seed]),
        },
        "failures": [
            {"model_seed": s["model_seed"], "delta_return": s["exploit"]["delta_return"], "auc_mae_vs_frozen": s["auc"]["mae_gated"] - s["auc"]["frozen"]}
            for s in per_seed
            if s["exploit"]["delta_return"] < 0 or s["auc"]["mae_gated"] < s["auc"]["frozen"]
        ],
        "costs": {
            "mean_pretrain": float(np.mean([s["pretrain"] for s in per_seed])) if per_seed else 0.0,
            "pool_n": pool_n,
            "stage_cap": stage,
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.8.9 learning efficiency. Frozen MAE 0.97. Not AGI. Confirmation not used to retune.",
    }
    del _g
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
