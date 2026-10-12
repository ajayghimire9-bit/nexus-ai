"""V0.8.4 fair adaptation verification. GRU remains estimation-only (not used here)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from nexus.cl.metrics import paired_seed_deltas, seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v084_confirmation_targets,
    v084_development_target,
    v084_sequence_tasks,
)
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION
from nexus.world.adapt import WindowThresholdDetector, per_transition_mae
from nexus.world.agent import plan_with_belief
from nexus.world.belief import IdentityBelief
from nexus.world.data import assert_disjoint_seeds, collect_transitions
from nexus.world.freeze import FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL
from nexus.world.memory import PredictiveMemory, checkpoint_nbytes
from nexus.world.online import FairGatePolicy, run_fair_online
from nexus.world.protocol import (
    V084_CONFIRM_EVAL_SEED,
    V084_DEV_EVAL_SEED,
    V084_SEQUENCE_EVAL_SEED,
    V084_SOURCE_COLLECT_SEED,
    V084_TARGET_COLLECT_SEED,
)
from nexus.world.train import train_world_model
from nexus.world.verify import CONTROL_VAL_HORIZON, MIN_IMPROVE

POLICIES: tuple[FairGatePolicy, ...] = ("never", "always", "mae", "control_fair")


def _detector(errors: np.ndarray) -> WindowThresholdDetector:
    d = WindowThresholdDetector(window=32, k=3.0)
    d.fit(errors)
    return d


def run_v084_benchmark(
    *,
    n_model_seeds: int = 10,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    adapt_epochs: int = 8,
    budgets: tuple[int, ...] = (0, 128, 256),
    eval_episodes: int = 2,
    artifact_path: str | Path | None = "artifacts/v084_verification.json",
    checkpoint_dir: str | Path = "checkpoints/v084",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    if quick:
        n_train, n_val, epochs, adapt_epochs = 48, 24, 1, 1
        budgets = (0, 24)
        eval_episodes = 1
        n_model_seeds = min(n_model_seeds, 1)
    source_spec = source_policy_task()
    dev = v084_development_target()
    seq = v084_sequence_tasks()
    confirms = v084_confirmation_targets()
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    per_seed: list[dict[str, Any]] = []
    dev_returns: dict[str, list[float]] = {p: [] for p in POLICIES}

    for mseed in range(n_model_seeds):
        train = collect_transitions(
            source_spec,
            n_transitions=n_train,
            env_seeds=tuple(range(12 + 20 * mseed, 32 + 20 * mseed)),
            base_seed=V084_SOURCE_COLLECT_SEED + 19 * mseed,
            mix=("random", "exploratory"),
        )
        val = collect_transitions(
            source_spec,
            n_transitions=n_val,
            env_seeds=tuple(range(420 + 8 * mseed, 428 + 8 * mseed)),
            base_seed=V084_SOURCE_COLLECT_SEED + 300 + 19 * mseed,
            mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val)
        pretrain = train.env_interactions + val.env_interactions
        source, slog = train_world_model(train, val, kind=FROZEN_KIND, epochs=epochs, seed=4 + 13 * mseed)  # type: ignore[arg-type]
        calib = collect_transitions(
            source_spec,
            n_transitions=48 if not quick else 16,
            env_seeds=tuple(range(700 + 6 * mseed, 706 + 6 * mseed)),
            base_seed=V084_SOURCE_COLLECT_SEED + 500 + mseed,
            mix=("random", "exploratory"),
        )
        calib_err = per_transition_mae(source, calib.obs, calib.action, calib.next_obs)
        pretrain += calib.env_interactions

        def _eval(spec, wm, seed) -> dict[str, Any]:
            return plan_with_belief(spec, wm, IdentityBelief(), seed=seed, episodes=eval_episodes)

        dev_sel: dict[str, Any] = {}
        cap_dev = 24 if quick else 128
        for pol in POLICIES:
            loop = run_fair_online(
                dev,
                source,
                train,
                IdentityBelief(),
                target_cap=cap_dev,
                policy=pol,
                epochs=adapt_epochs,
                seed=V084_TARGET_COLLECT_SEED + 3 * mseed,
                detector=_detector(calib_err),
            )
            plan = _eval(dev, loop["model"], V084_DEV_EVAL_SEED)
            snap = loop["ledger"]
            assert snap["no_double_count"] and snap["within_cap"]
            assert loop["observe_once"]
            assert loop["uses_confirmation"] is False
            dev_sel[pol] = {
                "planning": {k: plan[k] for k in ("mean_return", "fail_rate", "env_interactions")},
                "ledger": snap,
                "n_accept": loop.get("n_accept", 0),
                "n_proposals": loop.get("n_proposals", 0),
                "n_insufficient": loop.get("n_insufficient", 0),
                "acceptance_rate": loop.get("acceptance_rate"),
                "insufficient_evidence_rate": loop.get("insufficient_evidence_rate"),
                "conditional_harm": loop.get("conditional_harm"),
                "traces": loop.get("proposal_traces"),
            }
            dev_returns[pol].append(float(plan["mean_return"]))

        confirm_rows: dict[str, Any] = {}
        for spec in confirms:
            by_b: dict[str, Any] = {}
            for b in budgets:
                by_p: dict[str, Any] = {}
                never_ret = None
                for pol in POLICIES:
                    loop = run_fair_online(
                        spec,
                        source,
                        train,
                        IdentityBelief(),
                        target_cap=int(b),
                        policy=pol,
                        epochs=adapt_epochs,
                        seed=V084_TARGET_COLLECT_SEED + 11 * mseed + int(b),
                        detector=_detector(calib_err),
                    )
                    plan = _eval(spec, loop["model"], V084_CONFIRM_EVAL_SEED)
                    if pol == "never":
                        never_ret = float(plan["mean_return"])
                    final_vs_never = None
                    if pol != "never" and never_ret is not None:
                        final_vs_never = float(plan["mean_return"]) - never_ret
                    led = loop["ledger"]
                    led["pretrain"] = pretrain
                    led["eval_only"] = int(led.get("eval_only", 0)) + int(plan["env_interactions"])
                    by_p[pol] = {
                        "planning": {k: plan[k] for k in ("mean_return", "fail_rate", "env_interactions", "model_states")},
                        "ledger": led,
                        "n_accept": loop.get("n_accept", 0),
                        "n_proposals": loop.get("n_proposals", 0),
                        "n_insufficient": loop.get("n_insufficient", 0),
                        "n_inconclusive": loop.get("n_inconclusive", 0),
                        "acceptance_rate": loop.get("acceptance_rate"),
                        "insufficient_evidence_rate": loop.get("insufficient_evidence_rate"),
                        "conditional_harm": loop.get("conditional_harm"),
                        "n_audit_beneficial": loop.get("n_audit_beneficial", 0),
                        "n_audit_harmful": loop.get("n_audit_harmful", 0),
                        "final_minus_never": final_vs_never,
                        "observe_once": loop.get("observe_once"),
                        "traces": loop.get("proposal_traces"),
                    }
                by_b[str(b)] = by_p
            confirm_rows[spec.task_id] = {"params": dict(spec.params), "by_budget": by_b}

        seq_budget = 24 if quick else 128
        memory = PredictiveMemory(max_entries=6, replay_cap=n_train + seq_budget)
        memory.store(source, val.slice(np.arange(min(24, len(val)))), stats={"stage": "source"}, label="source")
        seq_log = []
        names = ("A", "B", "C", "A_return")
        specs_l = (seq[0], seq[1], seq[2], seq[0])
        shared_always = source.clone()
        shared_gate = source.clone()
        for ti, (sp, name) in enumerate(zip(specs_l, names)):
            never_l = run_fair_online(sp, source, train, IdentityBelief(), target_cap=seq_budget, policy="never", epochs=adapt_epochs, seed=V084_SEQUENCE_EVAL_SEED + ti, detector=_detector(calib_err))
            alw = run_fair_online(sp, shared_always, train, IdentityBelief(), target_cap=seq_budget, policy="always", epochs=adapt_epochs, seed=V084_SEQUENCE_EVAL_SEED + 20 + ti, detector=_detector(calib_err))
            gat = run_fair_online(sp, shared_gate, train, IdentityBelief(), target_cap=seq_budget, policy="control_fair", epochs=adapt_epochs, seed=V084_SEQUENCE_EVAL_SEED + 40 + ti, detector=_detector(calib_err))
            shared_always = alw["model"]
            shared_gate = gat["model"]
            retrieved, meta = memory.retrieve(val.slice(np.arange(min(16, len(val)))))
            memory.store(shared_gate, val.slice(np.arange(min(16, len(val)))), stats={"stage": name}, label=name)
            eval_sp = seq[0] if name == "A_return" else sp
            seq_log.append(
                {
                    "stage": name,
                    "never": _eval(eval_sp, never_l["model"], V084_SEQUENCE_EVAL_SEED),
                    "naive_shared": _eval(eval_sp, shared_always, V084_SEQUENCE_EVAL_SEED),
                    "gated_shared": _eval(eval_sp, shared_gate, V084_SEQUENCE_EVAL_SEED),
                    "snapshot": _eval(eval_sp, source, V084_SEQUENCE_EVAL_SEED),
                    "retrieved": _eval(eval_sp, retrieved or source, V084_SEQUENCE_EVAL_SEED),
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
                "source_nbytes": checkpoint_nbytes(source),
                "dev": dev_sel,
                "confirmation": confirm_rows,
                "continual": seq_log,
                "memory_bytes": memory.bytes_used(),
            }
        )
        print(f"v084 seed={mseed}", flush=True)

    mean_dev = {p: float(np.mean(dev_returns[p])) for p in POLICIES}
    selected = max(POLICIES, key=lambda p: (mean_dev[p], {"control_fair": 3, "mae": 2, "always": 1, "never": 0}[p]))
    noisy_ids = [t.task_id for t in confirms if "noisy" in t.task_id]
    clean_ids = [t.task_id for t in confirms if "clean" in t.task_id]

    def _rets(ids: list[str], b: int, pol: str) -> list[float]:
        return [float(np.mean([p["confirmation"][tid]["by_budget"][str(b)][pol]["planning"]["mean_return"] for tid in ids])) for p in per_seed]

    def _metric(ids: list[str], b: int, pol: str, key: str) -> list[float]:
        xs = []
        for p in per_seed:
            vals = [p["confirmation"][tid]["by_budget"][str(b)][pol].get(key) for tid in ids]
            nums = [float(v) for v in vals if isinstance(v, (int, float))]
            xs.append(float(np.mean(nums)) if nums else 0.0)
        return xs

    noisy_sum = {
        str(b): {
            pol: {
                "plan_return": seed_level_ci(_rets(noisy_ids, b, pol)),
                "fail_rate": seed_level_ci(
                    [float(np.mean([p["confirmation"][tid]["by_budget"][str(b)][pol]["planning"]["fail_rate"] or 0 for tid in noisy_ids])) for p in per_seed]
                ),
                "n_accept": seed_level_ci(_metric(noisy_ids, b, pol, "n_accept")),
                "n_proposals": seed_level_ci(_metric(noisy_ids, b, pol, "n_proposals")),
                "acceptance_rate": seed_level_ci(_metric(noisy_ids, b, pol, "acceptance_rate")),
                "insufficient_evidence_rate": seed_level_ci(_metric(noisy_ids, b, pol, "insufficient_evidence_rate")),
            }
            for pol in POLICIES
        }
        for b in budgets
    }
    paired: dict[str, Any] = {}
    bb = 128 if 128 in budgets else budgets[-1]
    per_seed_task = {
        int(p["model_seed"]): {
            "noisy": {pol: float(np.mean([p["confirmation"][tid]["by_budget"][str(bb)][pol]["planning"]["mean_return"] for tid in noisy_ids])) for pol in POLICIES}
        }
        for p in per_seed
    }
    for pol in POLICIES:
        if pol == "never":
            continue
        paired[f"{pol}_minus_never"] = paired_seed_deltas(per_seed_task=per_seed_task, treatment=pol, baseline="never")

    def _cond_harm(pol: str, b: int) -> dict[str, Any]:
        rates = []
        accepts = []
        for p in per_seed:
            for tid in noisy_ids:
                row = p["confirmation"][tid]["by_budget"][str(b)][pol]
                acc = int(row.get("n_accept") or 0)
                accepts.append(acc)
                ch = row.get("conditional_harm")
                if acc == 0 or ch == "not_applicable":
                    continue
                rates.append(float(ch))
        if not rates:
            return {"conditional_on_acceptance": "not_applicable", "n_accept_total": int(sum(accepts))}
        return {"conditional_on_acceptance": seed_level_ci(rates), "n_accept_total": int(sum(accepts))}

    payload = {
        "protocol": {
            "code_version": "v0.8.4",
            "parent_commit": "93a08bd",
            "physics_version": CARTPOLE_PHYSICS_VERSION,
            "gru_in_mpc": False,
            "fair_control_horizon": CONTROL_VAL_HORIZON,
            "min_improve": MIN_IMPROVE,
            "online": True,
            "observe_once": True,
            "confirm_eval_seed": V084_CONFIRM_EVAL_SEED,
            "selection_split": "dev_v084",
            "n_model_seeds": n_model_seeds,
            "budgets": list(budgets),
            "policies": list(POLICIES),
            "selected_protocol": selected,
            "dev_mean_return": mean_dev,
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
        "noisy_confirmation": noisy_sum,
        "clean_confirmation": {str(b): {pol: seed_level_ci(_rets(clean_ids, b, pol)) for pol in POLICIES} for b in budgets},
        "paired_noisy": paired,
        "conditional_harm_noisy": {str(b): {pol: _cond_harm(pol, b) for pol in POLICIES if pol != "never"} for b in budgets if b},
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
        "caveat": "V0.8.4 fair CartPole verification. Not AGI. Rejection-only is not adaptation success.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
