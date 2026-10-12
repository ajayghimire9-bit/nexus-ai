"""V0.8.7 online learning bridge. Frozen V0.8.5 MAE / V0.8.6 low_lr. Not AGI."""

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
    v087_confirmation_targets,
    v087_development_target,
    v087_sequence_tasks,
)
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec
from nexus.world.adapt import WindowThresholdDetector, per_transition_mae
from nexus.world.agent import InteractionLedger, collect_planned_belief, plan_with_belief
from nexus.world.belief import IdentityBelief
from nexus.world.data import assert_disjoint_seeds, collect_transitions
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL
from nexus.world.memory import PredictiveMemory
from nexus.world.protocol import (
    V087_ADAPT_SEED,
    V087_CONFIRM_EVAL_SEED,
    V087_DEV_EVAL_SEED,
    V087_GATE_SEED,
    V087_REF_SEED,
    V087_SEQUENCE_EVAL_SEED,
    V087_SOURCE_COLLECT_SEED,
    V087_TARGET_COLLECT_SEED,
    V087_VAL_COLLECT_SEED,
)
from nexus.world.train import one_step_errors, train_world_model
from nexus.world.v085 import CandidatePair, _git_meta, reference_eval
from nexus.world.v086 import apply_method, collect_matched
from nexus.world.verify import (
    GateInput,
    V085_MAE_RATIO,
    V085_MAE_STEPS,
    V085_REF_EPISODES,
    V085_REF_HORIZON,
    V085_REF_MARGIN,
    run_gate,
    weights_hash,
)

GateName = Literal["never", "always", "mae"]
MethodName = Literal["finetune", "low_lr"]

BANK_TRAIN, BANK_VAL = 128, 64
SPLIT_TRAIN, SPLIT_VAL = 64, 32
PRIMARY_CAP = 256


def paired_control_eval(spec: TaskSpec, models: dict[str, Any], *, seed: int, episodes: int) -> dict[str, Any]:
    """Identical eval seed and episode count for every method (Phase 1)."""
    out: dict[str, Any] = {}
    for name, wm in models.items():
        row = plan_with_belief(spec, wm, IdentityBelief(), seed=int(seed), episodes=int(episodes))
        out[name] = {k: row[k] for k in ("mean_return", "fail_rate", "env_interactions", "model_states")}
    return out


def run_online_cycles(
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
    require_alarm: bool = False,
    detector: WindowThresholdDetector | None = None,
) -> dict[str, Any]:
    """Bounded online cycles. Deployed weights collect the next batch after a commit."""
    deployed = source.clone()
    ledger = InteractionLedger(target_cap=int(target_cap))
    hashes = [{"stage": "start", "hash": weights_hash(deployed), "accepted": False}]
    cycles: list[dict[str, Any]] = []
    n_accept = 0
    n_propose = 0
    n_skip_alarm = 0
    n_reject = 0
    if target_cap <= 0:
        return {
            "model": deployed,
            "ledger": ledger.snapshot(),
            "n_accept": 0,
            "n_propose": 0,
            "n_skip_alarm": 0,
            "n_reject": 0,
            "hashes": hashes,
            "cycles": cycles,
            "gate": gate,
            "method": method,
            "train_n": train_n,
            "val_n": val_n,
        }

    mae_need = V085_MAE_STEPS if gate == "mae" else 0
    cycle_i = 0
    while ledger.remaining > 0 and cycle_i < int(max_cycles):
        need = int(train_n) + int(val_n) + int(mae_need)
        take_train = min(int(train_n), ledger.remaining if gate == "never" else max(0, ledger.remaining - int(val_n) - int(mae_need)))
        if take_train < 16:
            break
        tr_seeds = tuple(range(int(seed) + 17 * cycle_i, int(seed) + 17 * cycle_i + 8))
        train_ds = collect_planned_belief(
            spec,
            deployed,
            IdentityBelief(),
            take_train,
            env_seeds=tr_seeds,
            base_seed=V087_TARGET_COLLECT_SEED + int(seed) + 3 * cycle_i,
        )
        bucket = "detect" if gate == "never" else "adapt_collect"
        ledger.charge(int(train_ds.env_interactions), bucket)
        if gate == "never":
            hashes.append({"stage": f"cycle{cycle_i}", "hash": weights_hash(deployed), "accepted": False, "reason": "never"})
            cycle_i += 1
            continue
        take_val = min(int(val_n), max(0, ledger.remaining - int(mae_need)))
        va_seeds = tuple(range(int(seed) + 80 + 17 * cycle_i, int(seed) + 88 + 17 * cycle_i))
        val_ds = collect_planned_belief(
            spec,
            deployed,
            IdentityBelief(),
            take_val,
            env_seeds=va_seeds,
            base_seed=V087_VAL_COLLECT_SEED + int(seed) + 3 * cycle_i,
        )
        if len(val_ds):
            ledger.charge(int(val_ds.env_interactions), "adapt_collect")
        if require_alarm and detector is not None and len(train_ds):
            err = per_transition_mae(deployed, train_ds.obs, train_ds.action, train_ds.next_obs)
            scan = detector.scan(err)
            if scan.get("missed"):
                n_skip_alarm += 1
                hashes.append({"stage": f"cycle{cycle_i}", "hash": weights_hash(deployed), "accepted": False, "reason": "no_alarm"})
                cycle_i += 1
                continue
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
        pred = one_step_errors(deployed, val_ds)["mae"] if len(val_ds) else None
        cycles.append(
            {
                "cycle": cycle_i,
                "train_n": len(train_ds),
                "val_n": len(val_ds),
                "accepted": accepted,
                "reason": reason,
                "before": before,
                "after": after,
                "val_mae": pred,
                "epochs_run": tlog.get("epochs_run"),
                "lr": tlog.get("lr"),
            }
        )
        cycle_i += 1
        del need

    if ledger.remaining > 0:
        extra = collect_planned_belief(
            spec,
            deployed,
            IdentityBelief(),
            ledger.remaining,
            env_seeds=tuple(range(int(seed) + 200, int(seed) + 208)),
            base_seed=int(seed) + 99,
        )
        ledger.charge(int(extra.env_interactions), "detect")

    return {
        "model": deployed,
        "ledger": ledger.snapshot(),
        "n_accept": n_accept,
        "n_propose": n_propose,
        "n_skip_alarm": n_skip_alarm,
        "n_reject": n_reject,
        "hashes": hashes,
        "cycles": cycles,
        "gate": gate,
        "method": method,
        "train_n": train_n,
        "val_n": val_n,
        "committed_hash": weights_hash(deployed),
        "source_hash": weights_hash(source),
    }


def _bank_once(
    spec: TaskSpec,
    source: Any,
    replay: Any,
    *,
    mseed: int,
    method: MethodName,
    train_n: int,
    val_n: int,
    epochs: int,
    collect_pair_i: int,
    adapt_seed: int,
    gate_seed: int,
) -> dict[str, Any]:
    train_ds, val_ds = collect_matched(spec, source, model_seed=mseed, pair_i=collect_pair_i, collect_n=train_n, val_n=val_n)
    cand, log = apply_method(method, source, replay, train_ds, val_ds, epochs=epochs, seed=adapt_seed)
    led = InteractionLedger(target_cap=V085_MAE_STEPS)
    g = run_gate("mae", GateInput(spec=spec, incumbent=source, candidate=cand, ledger=led, seed=gate_seed))
    pair = CandidatePair(
        pair_id=f"ablate_s{mseed}_{spec.task_id}_{train_n}_{val_n}_{method}",
        model_seed=mseed,
        spec=spec,
        recipe=f"{train_n}_{val_n}",
        incumbent=source,
        candidate=cand,
        train_n=len(train_ds),
        val_n=len(val_ds),
        independent_validation=bool(log.get("independent_validation")),
        checkpoint_rule=str(log.get("checkpoint_rule", "")),
        inc_hash=weights_hash(source),
        cand_hash=weights_hash(cand),
        collect_n=len(train_ds),
        val_collect_n=len(val_ds),
        collect_interactions=int(train_ds.env_interactions + val_ds.env_interactions),
        train_seeds=[int(x) for x in np.unique(train_ds.seed).tolist()] if len(train_ds) else [],
        val_seeds=[int(x) for x in np.unique(val_ds.seed).tolist()] if len(val_ds) else [],
    )
    return {
        "pair": pair,
        "candidate": cand,
        "mae": g,
        "train_n": len(train_ds),
        "val_n": len(val_ds),
        "collect_train": int(train_ds.env_interactions),
        "collect_val": int(val_ds.env_interactions),
        "log": {k: log[k] for k in log if k != "history"},
    }


def _select_protocol(dev_rows: dict[str, list[dict[str, Any]]]) -> tuple[str, str]:
    """Max MAE accept rate, then mean paired return vs never. Dev only."""
    best: tuple[float, float, str] | None = None
    for name, rows in dev_rows.items():
        n = max(len(rows), 1)
        acc = float(np.mean([r["n_accept"] > 0 for r in rows]))
        ret = float(np.mean([r["eval"]["mean_return"] for r in rows]))
        key = (acc, ret, name)
        if best is None or key[:2] > best[:2] or (key[:2] == best[:2] and name < best[2]):
            best = (acc, ret, name)
    assert best is not None
    return best[2], "max_mae_accept_rate_then_return"


def run_v087_benchmark(
    *,
    n_model_seeds: int = 10,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    adapt_epochs: int = 8,
    target_cap: int = PRIMARY_CAP,
    eval_episodes: int = 2,
    artifact_path: str | Path | None = "artifacts/v087_online.json",
    checkpoint_dir: str | Path = "checkpoints/v087",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    bank_tr, bank_va = BANK_TRAIN, BANK_VAL
    split_tr, split_va = SPLIT_TRAIN, SPLIT_VAL
    ref_h, ref_ep = V085_REF_HORIZON, V085_REF_EPISODES
    if quick:
        n_train, n_val, epochs, adapt_epochs = 48, 24, 1, 1
        n_model_seeds = min(n_model_seeds, 1)
        target_cap, eval_episodes = 80, 1
        bank_tr, bank_va, split_tr, split_va = 24, 8, 16, 8
        ref_h, ref_ep = 24, 1
    source_spec = source_policy_task()
    dev = v087_development_target()
    confirms = v087_confirmation_targets()
    seq = v087_sequence_tasks()
    if quick:
        confirms = confirms[:1]
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    git = _git_meta()
    protocol = {
        "code_version": "v0.8.7",
        "parent_commit": "9ee7003",
        "physics_version": CARTPOLE_PHYSICS_VERSION,
        "mae_ratio": V085_MAE_RATIO,
        "mae_steps": V085_MAE_STEPS,
        "generator_default": "low_lr",
        "retuned_mae": False,
        "target_cap": target_cap,
        "bank_train_val": [bank_tr, bank_va],
        "split_train_val": [split_tr, split_va],
        "confirm_eval_seed": V087_CONFIRM_EVAL_SEED,
        "dev_eval_seed": V087_DEV_EVAL_SEED,
        "n_model_seeds": n_model_seeds,
        "paired_eval": True,
        "reference_feeds_gate": False,
        "planned_runtime_note": "n=10 ablation 3 collect recipes + confirm 3 tasks × 5 policies + A-B-C-A; ~10–20 min CPU",
        "is_agi": False,
        "quick": quick,
        "git": git,
    }
    protocol["protocol_hash"] = hashlib.sha256(dumps_strict(protocol).encode()).hexdigest()[:16]

    per_seed: list[dict[str, Any]] = []
    abl_acc: dict[str, list[float]] = {"bank": [], "online_split": [], "matched_sizes": []}
    abl_ret: dict[str, list[float]] = {k: [] for k in abl_acc}

    for mseed in range(n_model_seeds):
        train = collect_transitions(
            source_spec,
            n_transitions=n_train,
            env_seeds=tuple(range(12 + 20 * mseed, 32 + 20 * mseed)),
            base_seed=V087_SOURCE_COLLECT_SEED + 19 * mseed,
            mix=("random", "exploratory"),
        )
        val = collect_transitions(
            source_spec,
            n_transitions=n_val,
            env_seeds=tuple(range(420 + 8 * mseed, 428 + 8 * mseed)),
            base_seed=V087_SOURCE_COLLECT_SEED + 300 + 19 * mseed,
            mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val)
        pretrain = train.env_interactions + val.env_interactions
        source, slog = train_world_model(train, val, kind=FROZEN_KIND, epochs=epochs, seed=4 + 13 * mseed)  # type: ignore[arg-type]
        calib = collect_transitions(source_spec, n_transitions=16 if quick else 48, env_seeds=tuple(range(700, 706)), base_seed=mseed, mix=("random",))
        pretrain += calib.env_interactions
        det = WindowThresholdDetector(window=16 if quick else 32, k=3.0)
        det.fit(per_transition_mae(source, calib.obs, calib.action, calib.next_obs))

        adapt_s = V087_ADAPT_SEED + 13 * mseed
        gate_s = V087_GATE_SEED + 11 * mseed
        bank = _bank_once(dev, source, train, mseed=mseed, method="low_lr", train_n=bank_tr, val_n=bank_va, epochs=adapt_epochs, collect_pair_i=0, adapt_seed=adapt_s, gate_seed=gate_s)
        split = run_online_cycles(
            dev, source, train, "low_lr", target_cap=target_cap, epochs=adapt_epochs, seed=mseed + 3, gate="mae",
            train_n=split_tr, val_n=split_va, max_cycles=2, adapt_seed=adapt_s, gate_seed=gate_s, require_alarm=False,
        )
        matched = run_online_cycles(
            dev, source, train, "low_lr", target_cap=target_cap, epochs=adapt_epochs, seed=mseed + 3, gate="mae",
            train_n=bank_tr, val_n=bank_va, max_cycles=1, adapt_seed=adapt_s, gate_seed=gate_s, require_alarm=False,
        )
        paired = paired_control_eval(
            dev,
            {"never": source, "bank": bank["candidate"], "online_split": split["model"], "matched_sizes": matched["model"]},
            seed=V087_DEV_EVAL_SEED,
            episodes=eval_episodes,
        )
        bank_ref = reference_eval(bank["pair"], seed=V087_REF_SEED + mseed, horizon=ref_h, n_episodes=ref_ep)
        abl = {
            "bank": {"n_accept": int(bank["mae"]["decision"] == "accept"), "reason": bank["mae"]["reason"], "train_n": bank["train_n"], "val_n": bank["val_n"], "eval": paired["bank"], "ref_label": bank_ref["label"], "ref_diff": bank_ref["diff"]},
            "online_split": {"n_accept": split["n_accept"], "n_propose": split["n_propose"], "n_reject": split["n_reject"], "train_n": split["train_n"], "val_n": split["val_n"], "eval": paired["online_split"], "cycles": split["cycles"]},
            "matched_sizes": {"n_accept": matched["n_accept"], "n_propose": matched["n_propose"], "n_reject": matched["n_reject"], "train_n": matched["train_n"], "val_n": matched["val_n"], "eval": paired["matched_sizes"], "cycles": matched["cycles"]},
        }
        for k in abl_acc:
            abl_acc[k].append(float(abl[k]["n_accept"] > 0))
            abl_ret[k].append(float(paired[k]["mean_return"]) - float(paired["never"]["mean_return"]))

        # Freeze protocol from running mean so far only after all seeds — store abl, select later.
        per_seed.append(
            {
                "model_seed": mseed,
                "pretrain": pretrain,
                "source_val": slog["best_val"],
                "ablation": abl,
                "paired_dev": paired,
                "_hold": {"source": source, "train": train, "val": val, "det": det},
            }
        )
        print(f"v087 abl seed={mseed}", flush=True)

    # Select online recipe on development paired deltas / accept rates.
    proto_stats = {
        "online_split": {"accept_rate": float(np.mean(abl_acc["online_split"])), "delta": float(np.mean(abl_ret["online_split"]))},
        "matched_sizes": {"accept_rate": float(np.mean(abl_acc["matched_sizes"])), "delta": float(np.mean(abl_ret["matched_sizes"]))},
    }
    selected_proto = "matched_sizes" if (proto_stats["matched_sizes"]["accept_rate"], proto_stats["matched_sizes"]["delta"]) >= (proto_stats["online_split"]["accept_rate"], proto_stats["online_split"]["delta"]) else "online_split"
    protocol["selected_online_protocol"] = selected_proto
    protocol["selection_reason"] = "dev_max_accept_rate_then_paired_delta"
    if selected_proto == "matched_sizes":
        use_tr, use_va, use_cyc = bank_tr, bank_va, 1
    else:
        use_tr, use_va, use_cyc = split_tr, split_va, 2
    protocol["frozen_train_n"] = use_tr
    protocol["frozen_val_n"] = use_va
    protocol["frozen_max_cycles"] = use_cyc

    policies: tuple[tuple[str, MethodName, GateName], ...] = (
        ("never", "low_lr", "never"),
        ("always_low_lr", "low_lr", "always"),
        ("mae_low_lr", "low_lr", "mae"),
        ("mae_finetune", "finetune", "mae"),
    )

    for item in per_seed:
        mseed = int(item["model_seed"])
        source, train, val, det = item["_hold"]["source"], item["_hold"]["train"], item["_hold"]["val"], item["_hold"]["det"]
        del item["_hold"]
        confirm_rows = {}
        for spec in confirms:
            by_p = {}
            models: dict[str, Any] = {"snapshot": source}
            logs: dict[str, Any] = {}
            for pname, method, gate in policies:
                logs[pname] = run_online_cycles(
                    spec,
                    source,
                    train,
                    method,
                    target_cap=target_cap,
                    epochs=adapt_epochs,
                    seed=V087_TARGET_COLLECT_SEED + mseed,
                    gate=gate,
                    train_n=use_tr,
                    val_n=use_va,
                    max_cycles=use_cyc if gate != "never" else 4,
                    adapt_seed=V087_ADAPT_SEED + 13 * mseed,
                    gate_seed=V087_GATE_SEED + 11 * mseed,
                    require_alarm=False,
                    detector=det,
                )
                models[pname] = logs[pname]["model"]
            paired = paired_control_eval(spec, models, seed=V087_CONFIRM_EVAL_SEED, episodes=eval_episodes)
            never_ret = float(paired["never"]["mean_return"])
            for pname, _m, _g in policies:
                lg = logs[pname]
                by_p[pname] = {
                    "planning": paired[pname],
                    "delta_vs_never": float(paired[pname]["mean_return"]) - never_ret,
                    "n_accept": lg["n_accept"],
                    "n_propose": lg["n_propose"],
                    "n_reject": lg["n_reject"],
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

        seq_budget = 24 if quick else target_cap
        memory = PredictiveMemory(max_entries=6, replay_cap=n_train + seq_budget)
        memory.store(source, val.slice(np.arange(min(24, len(val)))), stats={"stage": "source"}, label="source")
        names = ("A", "B", "C", "A_return")
        specs_l = (seq[0], seq[1], seq[2], seq[0])
        shared_always = source.clone()
        shared_mae = source.clone()
        seq_log = []
        for ti, (sp, name) in enumerate(zip(specs_l, names)):
            never_l = run_online_cycles(sp, source, train, "low_lr", target_cap=seq_budget, epochs=adapt_epochs, seed=V087_SEQUENCE_EVAL_SEED + ti, gate="never", train_n=use_tr, val_n=use_va, max_cycles=use_cyc, adapt_seed=V087_ADAPT_SEED, gate_seed=V087_GATE_SEED, require_alarm=False)
            alw = run_online_cycles(sp, shared_always, train, "low_lr", target_cap=seq_budget, epochs=adapt_epochs, seed=V087_SEQUENCE_EVAL_SEED + 20 + ti, gate="always", train_n=use_tr, val_n=use_va, max_cycles=use_cyc, adapt_seed=V087_ADAPT_SEED, gate_seed=V087_GATE_SEED, require_alarm=False)
            gat = run_online_cycles(sp, shared_mae, train, "low_lr", target_cap=seq_budget, epochs=adapt_epochs, seed=V087_SEQUENCE_EVAL_SEED + 40 + ti, gate="mae", train_n=use_tr, val_n=use_va, max_cycles=use_cyc, adapt_seed=V087_ADAPT_SEED, gate_seed=V087_GATE_SEED, require_alarm=False)
            shared_always, shared_mae = alw["model"], gat["model"]
            retrieved, meta = memory.retrieve(val.slice(np.arange(min(16, len(val)))))
            memory.store(shared_mae, val.slice(np.arange(min(16, len(val)))), stats={"stage": name}, label=name)
            eval_sp = seq[0] if name == "A_return" else sp
            models = {
                "never": never_l["model"],
                "naive_shared": shared_always,
                "gated_shared": shared_mae,
                "snapshot": source,
                "retrieved": retrieved or source,
            }
            paired = paired_control_eval(eval_sp, models, seed=V087_SEQUENCE_EVAL_SEED, episodes=eval_episodes)
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
                    "ledgers": {"never": never_l["ledger"], "always": alw["ledger"], "mae": gat["ledger"]},
                }
            )

        item["confirmation"] = confirm_rows
        item["continual"] = seq_log
        print(f"v087 confirm seed={mseed} proto={selected_proto}", flush=True)

    noisy_ids = [t.task_id for t in confirms if "noisy" in t.task_id] or [t.task_id for t in confirms]
    pol_names = [p[0] for p in policies] + ["snapshot"]

    def _seed_rets(pol: str) -> list[float]:
        xs = []
        for s in per_seed:
            xs.append(float(np.mean([s["confirmation"][tid]["policies"][pol]["planning"]["mean_return"] for tid in noisy_ids])))
        return xs

    def _seed_delta(pol: str) -> list[float]:
        xs = []
        for s in per_seed:
            xs.append(float(np.mean([s["confirmation"][tid]["policies"][pol]["delta_vs_never"] for tid in noisy_ids])))
        return xs

    def _seed_acc(pol: str) -> list[float]:
        xs = []
        for s in per_seed:
            xs.append(float(np.mean([s["confirmation"][tid]["policies"][pol].get("n_accept", 0) for tid in noisy_ids])))
        return xs

    payload = {
        "protocol": protocol,
        "tasks": {
            "development": dict(dev.params) | {"task_id": dev.task_id},
            "confirmation": [dict(t.params) | {"task_id": t.task_id} for t in confirms],
        },
        "ablation": {
            "accept_rate": {k: seed_level_ci(v) for k, v in abl_acc.items()},
            "paired_delta_vs_never": {k: seed_level_ci(v) for k, v in abl_ret.items()},
            "proto_stats": proto_stats,
        },
        "noisy_confirmation": {
            pol: {
                "plan_return": seed_level_ci(_seed_rets(pol)),
                "delta_vs_never": seed_level_ci(_seed_delta(pol)),
                "n_accept": seed_level_ci(_seed_acc(pol)) if pol != "snapshot" else None,
            }
            for pol in pol_names
        },
        "continual_return_to_A": {
            k: seed_level_ci([float(p["continual"][-1][k]["mean_return"]) for p in per_seed])
            for k in ("never", "naive_shared", "gated_shared", "snapshot", "retrieved")
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.8.7 online bridge. Bank vs online diagnosed. Not AGI. MAE not retuned.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
