"""V0.8.3 decision-aware online adaptation. GRU is estimation-only, not MPC."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from nexus.cl.metrics import paired_seed_deltas, seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v083_confirmation_targets,
    v083_development_target,
    v083_sequence_tasks,
)
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION
from nexus.world.adapt import WindowThresholdDetector, per_transition_mae
from nexus.world.agent import InteractionLedger, plan_with_belief
from nexus.world.belief import IdentityBelief, train_gru_belief
from nexus.world.data import assert_disjoint_seeds, collect_transitions
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL
from nexus.world.memory import PredictiveMemory, checkpoint_nbytes
from nexus.world.online import GatePolicy, run_online_learning
from nexus.world.protocol import (
    V083_CONFIRM_EVAL_SEED,
    V083_DEV_EVAL_SEED,
    V083_SEQUENCE_EVAL_SEED,
    V083_SOURCE_COLLECT_SEED,
    V083_TARGET_COLLECT_SEED,
)
from nexus.world.train import train_world_model

POLICIES: tuple[GatePolicy, ...] = ("never", "always", "mae", "action", "control")


def _detector(errors: np.ndarray) -> WindowThresholdDetector:
    d = WindowThresholdDetector(window=32, k=3.0)
    d.fit(errors)
    return d


def run_v083_benchmark(
    *,
    n_model_seeds: int = 10,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    adapt_epochs: int = 8,
    budgets: tuple[int, ...] = (0, 128, 256),
    eval_episodes: int = 2,
    artifact_path: str | Path | None = "artifacts/v083_learning.json",
    checkpoint_dir: str | Path = "checkpoints/v083",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    if quick:
        n_train, n_val, epochs, adapt_epochs = 48, 24, 1, 1
        budgets = (0, 24)
        eval_episodes = 1
        n_model_seeds = min(n_model_seeds, 1)
    source_spec = source_policy_task()
    dev = v083_development_target()
    seq = v083_sequence_tasks()
    confirms = v083_confirmation_targets()
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    per_seed: list[dict[str, Any]] = []

    for mseed in range(n_model_seeds):
        train = collect_transitions(
            source_spec,
            n_transitions=n_train,
            env_seeds=tuple(range(12 + 20 * mseed, 32 + 20 * mseed)),
            base_seed=V083_SOURCE_COLLECT_SEED + 19 * mseed,
            mix=("random", "exploratory"),
        )
        val = collect_transitions(
            source_spec,
            n_transitions=n_val,
            env_seeds=tuple(range(420 + 8 * mseed, 428 + 8 * mseed)),
            base_seed=V083_SOURCE_COLLECT_SEED + 300 + 19 * mseed,
            mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val)
        pretrain = train.env_interactions + val.env_interactions
        source, slog = train_world_model(train, val, kind=FROZEN_KIND, epochs=epochs, seed=4 + 13 * mseed)  # type: ignore[arg-type]
        gru, gru_log = train_gru_belief(train, val, epochs=max(1, adapt_epochs), seed=8 + mseed)
        gru_mae = float(per_transition_mae(source, val.obs, val.action, val.next_obs).mean())
        # GRU estimation-only: next-obs MAE via observe loop is reported as val loss
        calib = collect_transitions(
            source_spec,
            n_transitions=48 if not quick else 16,
            env_seeds=tuple(range(700 + 6 * mseed, 706 + 6 * mseed)),
            base_seed=V083_SOURCE_COLLECT_SEED + 500 + mseed,
            mix=("random", "exploratory"),
        )
        calib_err = per_transition_mae(source, calib.obs, calib.action, calib.next_obs)
        # calib is source holdout → pretrain bucket, not target cap
        pretrain += calib.env_interactions

        def _eval(spec, wm, seed) -> dict[str, Any]:
            est = IdentityBelief()
            row = plan_with_belief(spec, wm, est, seed=seed, episodes=eval_episodes)
            return row

        dev_sel: dict[str, Any] = {}
        best_pol: GatePolicy = "never"
        best_ret = -1.0
        cap_dev = 24 if quick else 128
        for pol in POLICIES:
            loop = run_online_learning(
                dev,
                source,
                train,
                IdentityBelief(),
                target_cap=cap_dev,
                policy=pol,
                epochs=adapt_epochs,
                seed=V083_TARGET_COLLECT_SEED + 3 * mseed,
                detector=_detector(calib_err),
            )
            plan = _eval(dev, loop["model"], V083_DEV_EVAL_SEED)
            snap = loop["ledger"]
            assert snap["no_double_count"] and snap["within_cap"]
            dev_sel[pol] = {
                "planning": {k: plan[k] for k in ("mean_return", "fail_rate", "env_interactions")},
                "ledger": snap,
                "n_commit": loop.get("n_commit", 0),
                "n_reject": loop.get("n_reject", 0),
                "commits": loop.get("commits"),
                "rejects": loop.get("rejects"),
            }
            if float(plan["mean_return"]) > best_ret:
                best_ret, best_pol = float(plan["mean_return"]), pol

        confirm_rows: dict[str, Any] = {}
        for spec in confirms:
            by_b: dict[str, Any] = {}
            for b in budgets:
                by_p: dict[str, Any] = {}
                never_ret = None
                for pol in POLICIES:
                    loop = run_online_learning(
                        spec,
                        source,
                        train,
                        IdentityBelief(),
                        target_cap=int(b),
                        policy=pol,
                        epochs=adapt_epochs,
                        seed=V083_TARGET_COLLECT_SEED + 11 * mseed + int(b),
                        detector=_detector(calib_err),
                    )
                    plan = _eval(spec, loop["model"], V083_CONFIRM_EVAL_SEED)
                    if pol == "never":
                        never_ret = float(plan["mean_return"])
                    harmful = None
                    beneficial = None
                    if pol != "never" and never_ret is not None and loop.get("n_commit", 0):
                        harmful = bool(float(plan["mean_return"]) < never_ret - 1e-6)
                        beneficial = bool(float(plan["mean_return"]) > never_ret + 1e-6)
                    led = loop["ledger"]
                    led["pretrain"] = pretrain
                    led["eval_only"] = int(plan["env_interactions"])
                    by_p[pol] = {
                        "planning": {k: plan[k] for k in ("mean_return", "fail_rate", "env_interactions", "model_states")},
                        "ledger": led,
                        "n_commit": loop.get("n_commit", 0),
                        "n_reject": loop.get("n_reject", 0),
                        "commits": loop.get("commits"),
                        "rejects": loop.get("rejects"),
                        "harmful_commit": harmful,
                        "beneficial_commit": beneficial,
                    }
                by_b[str(b)] = by_p
            confirm_rows[spec.task_id] = {"params": dict(spec.params), "by_budget": by_b}
        # restore never_ret per task inside loop - harmful uses never of that task. Good.

        seq_budget = 24 if quick else 128
        memory = PredictiveMemory(max_entries=6, replay_cap=n_train + seq_budget)
        memory.store(source, val.slice(np.arange(min(24, len(val)))), stats={"stage": "source"}, label="source")
        seq_log = []
        names = ("A", "B", "C", "A_return")
        specs_l = (seq[0], seq[1], seq[2], seq[0])
        shared_always = source.clone()
        shared_gate = source.clone()
        for ti, (sp, name) in enumerate(zip(specs_l, names)):
            never_l = run_online_learning(sp, source, train, IdentityBelief(), target_cap=seq_budget, policy="never", epochs=adapt_epochs, seed=V083_SEQUENCE_EVAL_SEED + ti, detector=_detector(calib_err))
            alw = run_online_learning(sp, shared_always, train, IdentityBelief(), target_cap=seq_budget, policy="always", epochs=adapt_epochs, seed=V083_SEQUENCE_EVAL_SEED + 20 + ti, detector=_detector(calib_err))
            gat = run_online_learning(sp, shared_gate, train, IdentityBelief(), target_cap=seq_budget, policy="control", epochs=adapt_epochs, seed=V083_SEQUENCE_EVAL_SEED + 40 + ti, detector=_detector(calib_err))
            shared_always = alw["model"]
            shared_gate = gat["model"]
            retrieved, meta = memory.retrieve(val.slice(np.arange(min(16, len(val)))))
            memory.store(shared_gate, val.slice(np.arange(min(16, len(val)))), stats={"stage": name}, label=name)
            eval_sp = seq[0] if name == "A_return" else sp
            seq_log.append(
                {
                    "stage": name,
                    "never": _eval(eval_sp, never_l["model"], V083_SEQUENCE_EVAL_SEED),
                    "naive_shared": _eval(eval_sp, shared_always, V083_SEQUENCE_EVAL_SEED),
                    "gated_shared": _eval(eval_sp, shared_gate, V083_SEQUENCE_EVAL_SEED),
                    "snapshot": _eval(eval_sp, source, V083_SEQUENCE_EVAL_SEED),
                    "retrieved": _eval(eval_sp, retrieved or source, V083_SEQUENCE_EVAL_SEED),
                    "retrieval": meta,
                    "memory_bytes": memory.bytes_used(),
                    "naive_ledger": alw["ledger"],
                    "gated_ledger": gat["ledger"],
                }
            )

        per_seed.append(
            {
                "model_seed": mseed,
                "pretrain": pretrain,
                "source_val": slog["best_val"],
                "gru_val": gru_log["best_val"],
                "identity_val_mae": gru_mae,
                "source_nbytes": checkpoint_nbytes(source),
                "dev": dev_sel,
                "selected_policy": best_pol,
                "confirmation": confirm_rows,
                "continual": seq_log,
                "memory_bytes": memory.bytes_used(),
            }
        )
        print(f"v083 seed={mseed} selected={best_pol}", flush=True)

    noisy_ids = [t.task_id for t in confirms if "noisy" in t.task_id]
    clean_ids = [t.task_id for t in confirms if "clean" in t.task_id]

    def _rets(ids: list[str], b: int, pol: str) -> list[float]:
        return [float(np.mean([p["confirmation"][tid]["by_budget"][str(b)][pol]["planning"]["mean_return"] for tid in ids])) for p in per_seed]

    noisy_sum = {
        str(b): {pol: {"plan_return": seed_level_ci(_rets(noisy_ids, b, pol)), "fail_rate": seed_level_ci([float(np.mean([p["confirmation"][tid]["by_budget"][str(b)][pol]["planning"]["fail_rate"] or 0 for tid in noisy_ids])) for p in per_seed])} for pol in POLICIES}
        for b in budgets
    }
    paired = {}
    bb = 128 if 128 in budgets else budgets[-1]
    per_seed_task = {int(p["model_seed"]): {"noisy": {pol: float(np.mean([p["confirmation"][tid]["by_budget"][str(bb)][pol]["planning"]["mean_return"] for tid in noisy_ids])) for pol in POLICIES}} for p in per_seed}
    for pol in POLICIES:
        if pol == "never":
            continue
        paired[f"{pol}_minus_never"] = paired_seed_deltas(per_seed_task=per_seed_task, treatment=pol, baseline="never")

    def _harm(pol: str, b: int) -> list[float]:
        xs = []
        for p in per_seed:
            hs = [p["confirmation"][tid]["by_budget"][str(b)][pol]["harmful_commit"] for tid in noisy_ids]
            hs = [1.0 if h else 0.0 for h in hs if h is not None]
            xs.append(float(np.mean(hs)) if hs else 0.0)
        return xs

    payload = {
        "protocol": {
            "code_version": "v0.8.3",
            "parent_commit": "5ff59a1",
            "physics_version": CARTPOLE_PHYSICS_VERSION,
            "gru_in_mpc": False,
            "gru_status": "estimation_only_inconsistent_imagination_excluded",
            "online": True,
            "prev_action_to_estimator": True,
            "confirm_eval_seed": V083_CONFIRM_EVAL_SEED,
            "selection_split": "dev_v083",
            "n_model_seeds": n_model_seeds,
            "budgets": list(budgets),
            "policies": list(POLICIES),
            "retuned_on_confirmation": False,
            "planner_uses_simulator": False,
            "target_budget_enforced": True,
            "is_agi": False,
            "quick": quick,
        },
        "tasks": {
            "development": dict(dev.params) | {"task_id": dev.task_id},
            "confirmation": [dict(t.params) | {"task_id": t.task_id} for t in confirms],
        },
        "dev_selection": {str(p["model_seed"]): p["selected_policy"] for p in per_seed},
        "noisy_confirmation": noisy_sum,
        "clean_confirmation": {str(b): {pol: seed_level_ci(_rets(clean_ids, b, pol)) for pol in POLICIES} for b in budgets},
        "paired_noisy": paired,
        "harmful_commit_rate_noisy": {str(b): {pol: seed_level_ci(_harm(pol, b)) for pol in POLICIES if pol != "never"} for b in budgets if b},
        "continual_return_to_A": {
            "never": seed_level_ci([float(p["continual"][-1]["never"]["mean_return"]) for p in per_seed]),
            "naive_shared": seed_level_ci([float(p["continual"][-1]["naive_shared"]["mean_return"]) for p in per_seed]),
            "gated_shared": seed_level_ci([float(p["continual"][-1]["gated_shared"]["mean_return"]) for p in per_seed]),
            "snapshot": seed_level_ci([float(p["continual"][-1]["snapshot"]["mean_return"]) for p in per_seed]),
            "retrieved": seed_level_ci([float(p["continual"][-1]["retrieved"]["mean_return"]) for p in per_seed]),
        },
        "costs": {
            "mean_pretrain": float(np.mean([p["pretrain"] for p in per_seed])),
            "mean_memory_bytes": float(np.mean([p["memory_bytes"] for p in per_seed])),
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.8.3 decision-aware CartPole. Not AGI. GRU excluded from MPC.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
