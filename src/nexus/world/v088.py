"""V0.8.8 genuine continual online learning. Frozen V0.8.7 MAE / low_lr. Not AGI."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Literal

import numpy as np

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v088_confirmation_targets,
    v088_development_target,
    v088_sequence_tasks,
)
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec
from nexus.world.adapt import WindowThresholdDetector, per_transition_mae
from nexus.world.agent import InteractionLedger, collect_planned_belief
from nexus.world.belief import IdentityBelief
from nexus.world.data import TransitionDataset, assert_disjoint_seeds, collect_transitions, concat_datasets
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL
from nexus.world.memory import PredictiveMemory
from nexus.world.protocol import (
    V088_ADAPT_SEED,
    V088_CONFIRM_EVAL_SEED,
    V088_DETECT_SEED,
    V088_DEV_EVAL_SEED,
    V088_GATE_SEED,
    V088_SEQUENCE_EVAL_SEED,
    V088_SOURCE_COLLECT_SEED,
    V088_TARGET_COLLECT_SEED,
    V088_VAL_COLLECT_SEED,
)
from nexus.world.train import one_step_errors, train_world_model
from nexus.world.v085 import _git_meta
from nexus.world.v086 import apply_method
from nexus.world.v087 import paired_control_eval
from nexus.world.verify import GateInput, V085_MAE_RATIO, V085_MAE_STEPS, run_gate, weights_hash

GateName = Literal["never", "always", "mae"]
MethodName = Literal["finetune", "low_lr"]

FROZEN_TRAIN, FROZEN_VAL = 128, 64
MAX_CYCLES = 3
CYCLE_COST = FROZEN_TRAIN + FROZEN_VAL + V085_MAE_STEPS
PRIMARY_CAP = MAX_CYCLES * CYCLE_COST  # 672, pre-registered; not from V0.8.7 confirm
CHUNK = 8
PROBE_N = 16
TRAIN_GRID = (64, 128)
VAL_GRID = (32, 64)
CYCLE_GRID = (1, 2)
POOL_TRAIN, POOL_VAL = 256, 128


def copy_detector(src: WindowThresholdDetector) -> WindowThresholdDetector:
    out = WindowThresholdDetector(window=src.window, k=src.k)
    out.source_mean = float(src.source_mean)
    out.source_std = float(src.source_std)
    out.threshold = float(src.threshold)
    out._buf = list(src._buf)
    return out


def _empty(spec: TaskSpec) -> TransitionDataset:
    z = np.zeros((0, spec.obs_dim), dtype=np.float32)
    return TransitionDataset(
        obs=z,
        action=np.zeros((0,), dtype=np.int64),
        next_obs=z.copy(),
        reward=np.zeros((0,), dtype=np.float32),
        terminated=np.zeros((0,), dtype=np.bool_),
        truncated=np.zeros((0,), dtype=np.bool_),
        task_id=spec.task_id,
        seed=np.zeros((0,), dtype=np.int64),
        episode_id=np.zeros((0,), dtype=np.int64),
        policy=np.array([], dtype=object),
        physics=dict(spec.params),
        env_interactions=0,
    )


def _concat(spec: TaskSpec, a: TransitionDataset, b: TransitionDataset) -> TransitionDataset:
    if len(a) == 0:
        return b
    if len(b) == 0:
        return a
    return concat_datasets(a, b, task_id=spec.task_id)


def _slice(ds: TransitionDataset, start: int, n: int) -> TransitionDataset:
    if n <= 0 or start >= len(ds):
        return ds.slice(np.zeros((0,), dtype=np.int64)) if len(ds) else ds
    idx = np.arange(int(start), min(int(start) + int(n), len(ds)))
    return ds.slice(idx)


def run_pool_cycles(
    source: Any,
    source_replay: Any,
    pool_train: TransitionDataset,
    pool_val: TransitionDataset,
    spec: TaskSpec,
    method: MethodName,
    *,
    train_n: int,
    val_n: int,
    n_cycles: int,
    epochs: int,
    adapt_seed: int,
    gate_seed: int,
    stride_train: int | None = None,
    stride_val: int | None = None,
) -> dict[str, Any]:
    """MAE cycles on a frozen transition pool. Isolates train_n / val_n / cycle count."""
    deployed = source.clone()
    hashes = [{"stage": "start", "hash": weights_hash(deployed), "accepted": False}]
    cycles: list[dict[str, Any]] = []
    n_accept = n_propose = n_reject = 0
    st = int(stride_train) if stride_train is not None else int(train_n)
    sv = int(stride_val) if stride_val is not None else int(val_n)
    for c in range(int(n_cycles)):
        tr = _slice(pool_train, c * st, int(train_n))
        va = _slice(pool_val, c * sv, int(val_n))
        if len(tr) < 8:
            break
        cand, tlog = apply_method(method, deployed, source_replay, tr, va, epochs=epochs, seed=int(adapt_seed) + c)
        n_propose += 1
        before = weights_hash(deployed)
        led = InteractionLedger(target_cap=V085_MAE_STEPS)
        g = run_gate("mae", GateInput(spec=spec, incumbent=deployed, candidate=cand, ledger=led, seed=int(gate_seed) + c))
        accepted = g["decision"] == "accept"
        if accepted:
            deployed = cand
            n_accept += 1
        else:
            n_reject += 1
        after = weights_hash(deployed)
        hashes.append({"stage": f"cycle{c}", "hash": after, "before": before, "accepted": accepted, "reason": g.get("reason")})
        cycles.append(
            {
                "cycle": c,
                "train_n": len(tr),
                "val_n": len(va),
                "accepted": accepted,
                "reason": g.get("reason"),
                "before": before,
                "after": after,
                "val_mae": one_step_errors(deployed, va)["mae"] if len(va) else None,
                "epochs_run": tlog.get("epochs_run"),
                "mae_ledger": led.snapshot(),
            }
        )
    return {
        "model": deployed,
        "n_accept": n_accept,
        "n_propose": n_propose,
        "n_reject": n_reject,
        "hashes": hashes,
        "cycles": cycles,
        "train_n": train_n,
        "val_n": val_n,
        "n_cycles": n_cycles,
        "committed_hash": weights_hash(deployed),
        "source_hash": weights_hash(source),
        "independent_pool": True,
    }


def run_change_triggered(
    spec: TaskSpec,
    source: Any,
    source_replay: Any,
    method: MethodName,
    *,
    target_cap: int,
    epochs: int,
    seed: int,
    gate: GateName,
    train_n: int,
    val_n: int,
    max_cycles: int,
    adapt_seed: int,
    gate_seed: int,
    detector: WindowThresholdDetector,
    require_alarm: bool = True,
    chunk: int = CHUNK,
) -> dict[str, Any]:
    """Stream with the deployed model; adapt only after a residual-error alarm (if required)."""
    deployed = source.clone()
    det = copy_detector(detector)
    det._buf = []
    ledger = InteractionLedger(target_cap=int(target_cap))
    hashes = [{"stage": "start", "hash": weights_hash(deployed), "accepted": False}]
    cycles: list[dict[str, Any]] = []
    n_accept = n_propose = n_reject = n_skip_alarm = 0
    first_alarm: int | None = None
    n_alarm_steps = 0
    n_detect_steps = 0
    watch = _empty(spec)
    ep_base = 0
    cycle_i = 0

    def _collect(n: int, tag: int) -> TransitionDataset:
        nonlocal ep_base
        if n <= 0:
            return _empty(spec)
        ds = collect_planned_belief(
            spec,
            deployed,
            IdentityBelief(),
            int(n),
            env_seeds=tuple(range(int(seed) + 17 * ep_base, int(seed) + 17 * ep_base + 8)),
            base_seed=V088_TARGET_COLLECT_SEED + int(seed) + 3 * ep_base + int(tag),
        )
        ep_base += 1
        return ds

    if target_cap <= 0:
        return {
            "model": deployed,
            "ledger": ledger.snapshot(),
            "n_accept": 0,
            "n_propose": 0,
            "n_reject": 0,
            "n_skip_alarm": 0,
            "hashes": hashes,
            "cycles": cycles,
            "first_alarm": None,
            "missed": True,
            "detection_delay": None,
            "n_alarm_steps": 0,
            "n_detect_steps": 0,
            "false_alarm_rate": 0.0,
            "committed_hash": weights_hash(deployed),
            "source_hash": weights_hash(source),
            "gate": gate,
            "method": method,
        }

    while ledger.remaining > 0 and cycle_i < int(max_cycles):
        mae_need = V085_MAE_STEPS if gate == "mae" else 0
        need_after_watch = int(val_n) + int(mae_need)
        if gate != "never" and ledger.remaining < max(16, need_after_watch):
            break
        take = min(int(chunk), ledger.remaining)
        ds = _collect(take, 0)
        ledger.charge(int(ds.env_interactions), "detect")
        if len(ds):
            err = per_transition_mae(deployed, ds.obs, ds.action, ds.next_obs)
            for e in err:
                n_detect_steps += 1
                u = det.update(float(e))
                if u["alarm"]:
                    n_alarm_steps += 1
                    if first_alarm is None:
                        first_alarm = n_detect_steps
            watch = _concat(spec, watch, ds)
        if gate == "never":
            continue
        armed = (not require_alarm) or (first_alarm is not None)
        if not armed:
            continue
        extra_train = max(0, int(train_n) - len(watch))
        if ledger.remaining < extra_train + int(val_n) + int(mae_need):
            n_skip_alarm += 1
            break
        if extra_train:
            more = _collect(extra_train, 1)
            ledger.charge(int(more.env_interactions), "adapt_collect")
            watch = _concat(spec, watch, more)
        train_ds = _slice(watch, 0, int(train_n)) if len(watch) >= int(train_n) else watch
        take_val = min(int(val_n), max(0, ledger.remaining - int(mae_need)))
        val_ds = _collect(take_val, 2)
        if len(val_ds):
            ledger.charge(int(val_ds.env_interactions), "adapt_collect")
        cand, tlog = apply_method(method, deployed, source_replay, train_ds, val_ds, epochs=epochs, seed=int(adapt_seed) + cycle_i)
        n_propose += 1
        before = weights_hash(deployed)
        reason = "unevaluated"
        accepted = False
        if gate == "always":
            deployed = cand
            accepted = True
            n_accept += 1
            reason = "always"
        elif gate == "mae":
            g = run_gate("mae", GateInput(spec=spec, incumbent=deployed, candidate=cand, ledger=ledger, seed=int(gate_seed) + cycle_i))
            reason = str(g.get("reason"))
            if g["decision"] == "accept":
                deployed = cand
                accepted = True
                n_accept += 1
            else:
                n_reject += 1
        after = weights_hash(deployed)
        hashes.append({"stage": f"cycle{cycle_i}", "hash": after, "before": before, "accepted": accepted, "reason": reason})
        cycles.append(
            {
                "cycle": cycle_i,
                "train_n": len(train_ds),
                "val_n": len(val_ds),
                "accepted": accepted,
                "reason": reason,
                "before": before,
                "after": after,
                "val_mae": one_step_errors(deployed, val_ds)["mae"] if len(val_ds) else None,
                "epochs_run": tlog.get("epochs_run"),
                "alarm_at": first_alarm,
            }
        )
        cycle_i += 1
        watch = _empty(spec)
        det._buf = []
        first_alarm = None

    if ledger.remaining > 0:
        extra = _collect(ledger.remaining, 9)
        ledger.charge(int(extra.env_interactions), "detect")

    missed = first_alarm is None and n_propose == 0 and gate != "never"
    # first_alarm is reset after each cycle; recover from cycle log / n_alarm
    delay = cycles[0]["alarm_at"] if cycles else (None if n_alarm_steps == 0 else n_detect_steps)
    return {
        "model": deployed,
        "ledger": ledger.snapshot(),
        "n_accept": n_accept,
        "n_propose": n_propose,
        "n_reject": n_reject,
        "n_skip_alarm": n_skip_alarm,
        "hashes": hashes,
        "cycles": cycles,
        "first_alarm": cycles[0]["alarm_at"] if cycles else None,
        "missed": bool(n_propose == 0 and gate != "never"),
        "detection_delay": delay,
        "n_alarm_steps": n_alarm_steps,
        "n_detect_steps": n_detect_steps,
        "false_alarm_rate": float(n_alarm_steps / n_detect_steps) if n_detect_steps else 0.0,
        "committed_hash": weights_hash(deployed),
        "source_hash": weights_hash(source),
        "gate": gate,
        "method": method,
        "train_n": train_n,
        "val_n": val_n,
        "require_alarm": require_alarm,
    }


def retrieve_with_probe(
    spec: TaskSpec,
    memory: PredictiveMemory,
    deployed: Any,
    *,
    seed: int,
    n: int = PROBE_N,
) -> tuple[Any, dict[str, Any], int]:
    """Collect a current-env probe; retrieve by MAE. No task_id."""
    probe = collect_planned_belief(
        spec,
        deployed,
        IdentityBelief(),
        int(n),
        env_seeds=tuple(range(int(seed), int(seed) + 4)),
        base_seed=int(seed) + 17,
    )
    model, meta = memory.retrieve(probe)
    meta = dict(meta)
    meta["used_task_id"] = False
    meta["probe_n"] = len(probe)
    return (model or deployed), meta, int(probe.env_interactions)


def run_v088_benchmark(
    *,
    n_model_seeds: int = 10,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    adapt_epochs: int = 8,
    target_cap: int = PRIMARY_CAP,
    eval_episodes: int = 2,
    artifact_path: str | Path | None = "artifacts/v088_online.json",
    checkpoint_dir: str | Path = "checkpoints/v088",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    train_n, val_n, max_cycles = FROZEN_TRAIN, FROZEN_VAL, MAX_CYCLES
    pool_tr, pool_va = POOL_TRAIN, POOL_VAL
    probe_n = PROBE_N
    fpr_cap = 128
    if quick:
        n_train, n_val, epochs, adapt_epochs = 48, 24, 1, 1
        n_model_seeds = min(n_model_seeds, 1)
        target_cap, eval_episodes = 80, 1
        train_n, val_n, max_cycles = 16, 8, 2
        pool_tr, pool_va = 32, 16
        probe_n, fpr_cap = 8, 24
    source_spec = source_policy_task()
    dev = v088_development_target()
    confirms = v088_confirmation_targets()
    seq = v088_sequence_tasks()
    if quick:
        confirms = confirms[:1]
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    git = _git_meta()
    protocol = {
        "code_version": "v0.8.8",
        "parent_commit": "6b62fe4",
        "physics_version": CARTPOLE_PHYSICS_VERSION,
        "mae_ratio": V085_MAE_RATIO,
        "mae_steps": V085_MAE_STEPS,
        "generator_default": "low_lr",
        "retuned_mae": False,
        "retuned_from_v087_confirm": False,
        "target_cap": target_cap,
        "frozen_train_n": train_n,
        "frozen_val_n": val_n,
        "frozen_max_cycles": max_cycles,
        "require_alarm": True,
        "confirm_eval_seed": V088_CONFIRM_EVAL_SEED,
        "dev_eval_seed": V088_DEV_EVAL_SEED,
        "n_model_seeds": n_model_seeds,
        "paired_eval": True,
        "reference_feeds_gate": False,
        "cycle_cost": int(train_n) + int(val_n) + (V085_MAE_STEPS if not quick else 0),
        "planned_runtime_note": "n=10 factorial pool ablation + FPR + 3-cycle alarm online + A-B-C-A probe retrieval; ~15–30 min CPU",
        "is_agi": False,
        "quick": quick,
        "git": git,
    }
    protocol["protocol_hash"] = hashlib.sha256(dumps_strict(protocol).encode()).hexdigest()[:16]

    per_seed: list[dict[str, Any]] = []
    factor_keys = [f"tr{t}_va{v}_c{c}" for t in TRAIN_GRID for v in VAL_GRID for c in CYCLE_GRID]
    if quick:
        factor_keys = [f"tr{train_n}_va{val_n}_c1", f"tr{train_n}_va{val_n}_c{max_cycles}"]
    abl_acc: dict[str, list[float]] = {k: [] for k in factor_keys}
    fpr_vals: list[float] = []
    delay_vals: list[float] = []
    miss_vals: list[float] = []

    policies: tuple[tuple[str, MethodName, GateName], ...] = (
        ("never", "low_lr", "never"),
        ("always_low_lr", "low_lr", "always"),
        ("mae_low_lr", "low_lr", "mae"),
        ("mae_finetune", "finetune", "mae"),
    )

    for mseed in range(n_model_seeds):
        train = collect_transitions(
            source_spec,
            n_transitions=n_train,
            env_seeds=tuple(range(12 + 20 * mseed, 32 + 20 * mseed)),
            base_seed=V088_SOURCE_COLLECT_SEED + 19 * mseed,
            mix=("random", "exploratory"),
        )
        val = collect_transitions(
            source_spec,
            n_transitions=n_val,
            env_seeds=tuple(range(420 + 8 * mseed, 428 + 8 * mseed)),
            base_seed=V088_SOURCE_COLLECT_SEED + 300 + 19 * mseed,
            mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val)
        pretrain = train.env_interactions + val.env_interactions
        source, slog = train_world_model(train, val, kind=FROZEN_KIND, epochs=epochs, seed=4 + 13 * mseed)  # type: ignore[arg-type]
        calib = collect_transitions(
            source_spec,
            n_transitions=16 if quick else 48,
            env_seeds=tuple(range(700, 706)),
            base_seed=V088_DETECT_SEED + mseed,
            mix=("random",),
        )
        pretrain += calib.env_interactions
        det = WindowThresholdDetector(window=8 if quick else 32, k=3.0)
        det.fit(per_transition_mae(source, calib.obs, calib.action, calib.next_obs))

        pool_train = collect_planned_belief(
            dev,
            source,
            IdentityBelief(),
            pool_tr,
            env_seeds=tuple(range(50 + mseed, 58 + mseed)),
            base_seed=V088_TARGET_COLLECT_SEED + mseed,
        )
        pool_val = collect_planned_belief(
            dev,
            source,
            IdentityBelief(),
            pool_va,
            env_seeds=tuple(range(90 + mseed, 98 + mseed)),
            base_seed=V088_VAL_COLLECT_SEED + mseed,
        )
        assert_disjoint_seeds(pool_train, pool_val)
        adapt_s = V088_ADAPT_SEED + 13 * mseed
        gate_s = V088_GATE_SEED + 11 * mseed
        models_abl: dict[str, Any] = {"never": source}
        abl: dict[str, Any] = {}
        grid = [(train_n, val_n, 1), (train_n, val_n, max_cycles)] if quick else [(t, v, c) for t in TRAIN_GRID for v in VAL_GRID for c in CYCLE_GRID]
        for t, v, cyc in grid:
            key = f"tr{t}_va{v}_c{cyc}"
            row = run_pool_cycles(
                source, train, pool_train, pool_val, dev, "low_lr",
                train_n=t, val_n=v, n_cycles=cyc, epochs=adapt_epochs, adapt_seed=adapt_s, gate_seed=gate_s,
                stride_train=128 if not quick else train_n, stride_val=64 if not quick else val_n,
            )
            abl[key] = {"n_accept": row["n_accept"], "n_propose": row["n_propose"], "n_reject": row["n_reject"], "cycles": row["cycles"]}
            models_abl[key] = row["model"]
            abl_acc[key].append(float(row["n_accept"] > 0))
        paired_abl = paired_control_eval(dev, models_abl, seed=V088_DEV_EVAL_SEED, episodes=eval_episodes)

        fpr_run = run_change_triggered(
            source_spec, source, train, "low_lr",
            target_cap=fpr_cap, epochs=adapt_epochs, seed=mseed, gate="mae",
            train_n=train_n, val_n=val_n, max_cycles=max_cycles,
            adapt_seed=adapt_s, gate_seed=gate_s, detector=det, require_alarm=True,
        )
        fpr_vals.append(float(fpr_run["false_alarm_rate"]))

        tgt_det = run_change_triggered(
            dev, source, train, "low_lr",
            target_cap=target_cap, epochs=adapt_epochs, seed=mseed + 3, gate="mae",
            train_n=train_n, val_n=val_n, max_cycles=max_cycles,
            adapt_seed=adapt_s, gate_seed=gate_s, detector=det, require_alarm=True,
        )
        if tgt_det["detection_delay"] is not None:
            delay_vals.append(float(tgt_det["detection_delay"]))
        miss_vals.append(float(tgt_det["missed"]))

        per_seed.append(
            {
                "model_seed": mseed,
                "pretrain": pretrain,
                "source_val": slog["best_val"],
                "ablation": abl,
                "paired_dev": paired_abl,
                "fpr_source": fpr_run["false_alarm_rate"],
                "dev_detection": {
                    "delay": tgt_det["detection_delay"],
                    "missed": tgt_det["missed"],
                    "n_alarm_steps": tgt_det["n_alarm_steps"],
                    "n_propose": tgt_det["n_propose"],
                    "n_accept": tgt_det["n_accept"],
                    "ledger": tgt_det["ledger"],
                },
                "_hold": {"source": source, "train": train, "val": val, "det": det},
            }
        )
        print(f"v088 abl seed={mseed}", flush=True)

    for item in per_seed:
        mseed = int(item["model_seed"])
        source, train, val, det = item["_hold"]["source"], item["_hold"]["train"], item["_hold"]["val"], item["_hold"]["det"]
        del item["_hold"]
        confirm_rows = {}
        for spec in confirms:
            by_p: dict[str, Any] = {}
            models: dict[str, Any] = {"snapshot": source}
            logs: dict[str, Any] = {}
            for pname, method, gate in policies:
                logs[pname] = run_change_triggered(
                    spec, source, train, method,
                    target_cap=target_cap, epochs=adapt_epochs, seed=V088_TARGET_COLLECT_SEED + mseed,
                    gate=gate, train_n=train_n, val_n=val_n, max_cycles=max_cycles,
                    adapt_seed=V088_ADAPT_SEED + 13 * mseed, gate_seed=V088_GATE_SEED + 11 * mseed,
                    detector=det, require_alarm=gate != "never",
                )
                models[pname] = logs[pname]["model"]
            paired = paired_control_eval(spec, models, seed=V088_CONFIRM_EVAL_SEED, episodes=eval_episodes)
            never_ret = float(paired["never"]["mean_return"])
            for pname, _m, _g in policies:
                lg = logs[pname]
                dlt = float(paired[pname]["mean_return"]) - never_ret
                by_p[pname] = {
                    "planning": paired[pname],
                    "delta_vs_never": dlt,
                    "n_accept": lg["n_accept"],
                    "n_propose": lg["n_propose"],
                    "n_reject": lg["n_reject"],
                    "missed": lg["missed"],
                    "detection_delay": lg["detection_delay"],
                    "false_alarm_rate": lg["false_alarm_rate"],
                    "beneficial_accept": int(lg["n_accept"] > 0 and dlt > 0),
                    "harmful_accept": int(lg["n_accept"] > 0 and dlt < 0),
                    "hashes": lg["hashes"],
                    "cycles": lg["cycles"],
                    "ledger": lg["ledger"],
                    "source_hash": lg["source_hash"],
                    "committed_hash": lg["committed_hash"],
                }
            by_p["snapshot"] = {
                "planning": paired["snapshot"],
                "delta_vs_never": float(paired["snapshot"]["mean_return"]) - never_ret,
                "n_accept": 0,
                "hashes": [{"stage": "snapshot", "hash": weights_hash(source)}],
            }
            confirm_rows[spec.task_id] = {"params": dict(spec.params), "policies": by_p}

        seq_budget = 24 if quick else CYCLE_COST
        memory = PredictiveMemory(max_entries=6, replay_cap=n_train + seq_budget)
        memory.store(source, val.slice(np.arange(min(24, len(val)))), stats={"stage": "source"}, label="source")
        names = ("A", "B", "C", "A_return")
        specs_l = (seq[0], seq[1], seq[2], seq[0])
        shared_always = source.clone()
        shared_mae = source.clone()
        seq_log = []
        probe_cost = 0
        for ti, (sp, name) in enumerate(zip(specs_l, names)):
            never_l = run_change_triggered(
                sp, source, train, "low_lr", target_cap=seq_budget, epochs=adapt_epochs,
                seed=V088_SEQUENCE_EVAL_SEED + ti, gate="never", train_n=train_n, val_n=val_n, max_cycles=1,
                adapt_seed=V088_ADAPT_SEED, gate_seed=V088_GATE_SEED, detector=det, require_alarm=False,
            )
            alw = run_change_triggered(
                sp, shared_always, train, "low_lr", target_cap=seq_budget, epochs=adapt_epochs,
                seed=V088_SEQUENCE_EVAL_SEED + 20 + ti, gate="always", train_n=train_n, val_n=val_n, max_cycles=1,
                adapt_seed=V088_ADAPT_SEED, gate_seed=V088_GATE_SEED, detector=det, require_alarm=True,
            )
            gat = run_change_triggered(
                sp, shared_mae, train, "low_lr", target_cap=seq_budget, epochs=adapt_epochs,
                seed=V088_SEQUENCE_EVAL_SEED + 40 + ti, gate="mae", train_n=train_n, val_n=val_n, max_cycles=1,
                adapt_seed=V088_ADAPT_SEED, gate_seed=V088_GATE_SEED, detector=det, require_alarm=True,
            )
            shared_always, shared_mae = alw["model"], gat["model"]
            retrieved, meta, p_int = retrieve_with_probe(sp, memory, shared_mae, seed=V088_SEQUENCE_EVAL_SEED + 80 + ti, n=probe_n)
            probe_cost += p_int
            memory.store(shared_mae, val.slice(np.arange(min(16, len(val)))), stats={"stage": name}, label=name)
            eval_sp = seq[0] if name == "A_return" else sp
            models = {
                "never": never_l["model"],
                "naive_shared": shared_always,
                "gated_shared": shared_mae,
                "snapshot": source,
                "retrieved": retrieved,
            }
            paired = paired_control_eval(eval_sp, models, seed=V088_SEQUENCE_EVAL_SEED, episodes=eval_episodes)
            seq_log.append(
                {
                    "stage": name,
                    **paired,
                    "always_accept": alw["n_accept"],
                    "mae_accept": gat["n_accept"],
                    "always_hash": alw["committed_hash"],
                    "mae_hash": gat["committed_hash"],
                    "source_hash": weights_hash(source),
                    "retrieval": meta,
                    "probe_interactions": p_int,
                    "memory_bytes": memory.bytes_used(),
                    "ledgers": {"never": never_l["ledger"], "always": alw["ledger"], "mae": gat["ledger"]},
                }
            )

        item["confirmation"] = confirm_rows
        item["continual"] = seq_log
        item["probe_interactions_total"] = probe_cost
        item["memory_bytes"] = memory.bytes_used()
        print(f"v088 confirm seed={mseed}", flush=True)

    noisy_ids = [t.task_id for t in confirms if "noisy" in t.task_id] or [t.task_id for t in confirms]
    pol_names = [p[0] for p in policies] + ["snapshot"]

    def _seed_rets(pol: str) -> list[float]:
        return [float(np.mean([s["confirmation"][tid]["policies"][pol]["planning"]["mean_return"] for tid in noisy_ids])) for s in per_seed]

    def _seed_delta(pol: str) -> list[float]:
        return [float(np.mean([s["confirmation"][tid]["policies"][pol]["delta_vs_never"] for tid in noisy_ids])) for s in per_seed]

    def _seed_acc(pol: str) -> list[float]:
        return [float(np.mean([s["confirmation"][tid]["policies"][pol].get("n_accept", 0) for tid in noisy_ids])) for s in per_seed]

    def _seed_field(pol: str, field: str) -> list[float]:
        return [float(np.mean([s["confirmation"][tid]["policies"][pol].get(field, 0) for tid in noisy_ids])) for s in per_seed]

    payload = {
        "protocol": protocol,
        "tasks": {
            "development": dict(dev.params) | {"task_id": dev.task_id},
            "confirmation": [dict(t.params) | {"task_id": t.task_id} for t in confirms],
        },
        "ablation": {
            "accept_rate": {k: seed_level_ci(v) for k, v in abl_acc.items() if v},
            "note": "Shared source weights, pool, adapt_seed, gate_seed. Varied train_n, val_n, n_cycles.",
        },
        "detection": {
            "source_false_alarm_rate": seed_level_ci(fpr_vals) if fpr_vals else None,
            "dev_detection_delay": seed_level_ci(delay_vals) if delay_vals else None,
            "dev_miss_rate": seed_level_ci(miss_vals) if miss_vals else None,
        },
        "noisy_confirmation": {
            pol: {
                "plan_return": seed_level_ci(_seed_rets(pol)),
                "delta_vs_never": seed_level_ci(_seed_delta(pol)),
                "n_accept": seed_level_ci(_seed_acc(pol)) if pol != "snapshot" else None,
                "beneficial_accept": seed_level_ci(_seed_field(pol, "beneficial_accept")) if pol != "snapshot" else None,
                "harmful_accept": seed_level_ci(_seed_field(pol, "harmful_accept")) if pol != "snapshot" else None,
                "miss_rate": seed_level_ci(_seed_field(pol, "missed")) if pol != "snapshot" else None,
            }
            for pol in pol_names
        },
        "continual_return_to_A": {
            k: seed_level_ci([float(p["continual"][-1][k]["mean_return"]) for p in per_seed])
            for k in ("never", "naive_shared", "gated_shared", "snapshot", "retrieved")
        },
        "costs": {
            "target_cap": target_cap,
            "mean_probe_interactions": float(np.mean([p.get("probe_interactions_total", 0) for p in per_seed])) if per_seed else 0.0,
            "mean_memory_bytes": float(np.mean([p.get("memory_bytes", 0) for p in per_seed])) if per_seed else 0.0,
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.8.8 continual online. Frozen MAE 0.97 / low_lr. Not AGI. Confirmation not used to retune.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
