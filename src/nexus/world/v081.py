"""V0.8.1: prediction-to-control transfer when frozen H=3 is not at ceiling."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from nexus.cl.metrics import paired_seed_deltas, seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v081_confirmation_targets,
    v081_development_target,
    v081_noise_probe,
    v081_safety_ok,
    v081_sequence_tasks,
)
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec
from nexus.world.adapt import (
    METHODS,
    ResidualChangeDetector,
    WindowThresholdDetector,
    adapt_method,
    collect_with_actor,
    per_transition_mae,
    plan_h3,
)
from nexus.world.baselines import heuristic_cartpole
from nexus.world.data import assert_disjoint_seeds, collect_transitions
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_EPOCHS, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL, FROZEN_OBJECTIVE, FROZEN_PRIMARY_HORIZON
from nexus.world.imagine import multi_step_errors
from nexus.world.memory import PredictiveMemory, checkpoint_nbytes
from nexus.world.planning import InferenceCounter, RandomShootingMPC
from nexus.world.protocol import (
    V081_CONFIRM_EVAL_SEED,
    V081_DETECT_CALIB_SEED,
    V081_DEV_EVAL_SEED,
    V081_SEQUENCE_EVAL_SEED,
    V081_SOURCE_COLLECT_SEED,
    V081_TARGET_COLLECT_SEED,
)
from nexus.world.train import one_step_errors, train_world_model


def _mpc_actor(model: Any, seed: int) -> tuple[Any, Any]:
    inf = InferenceCounter(model)
    planner = RandomShootingMPC(
        model=model,
        n_actions=2,
        horizon=FROZEN_PRIMARY_HORIZON,
        n_candidates=FROZEN_CANDIDATES[FROZEN_PRIMARY_HORIZON],
        seed=0,
        inference=inf,
        objective=FROZEN_OBJECTIVE,  # type: ignore[arg-type]
    )

    def act(obs: np.ndarray) -> int:
        a, _meta = planner.act(obs)
        return int(a)

    def on_start(ep: int) -> None:
        planner.reset_episode(int(seed) + 1000 * int(ep))

    return act, on_start, inf


def _metrics(model: Any, ds: Any) -> dict[str, Any]:
    return {"one_step": one_step_errors(model, ds), "multi_step": multi_step_errors(model, ds, (1, 3, 8))}


def _collect_budget(spec: TaskSpec, model: Any, n: int, *, tag: int, mseed: int) -> tuple[Any, int]:
    if n <= 0:
        empty = collect_transitions(spec, n_transitions=1, env_seeds=(1,), base_seed=1)
        return empty.slice(np.zeros(0, dtype=np.int64)), 0
    act, on_start, inf = _mpc_actor(model, V081_TARGET_COLLECT_SEED + tag + mseed)
    ds = collect_with_actor(
        spec,
        n_transitions=n,
        env_seeds=tuple(range(40 + tag + 6 * mseed, 48 + tag + 6 * mseed)),
        base_seed=V081_TARGET_COLLECT_SEED + tag + 37 * mseed,
        actor=act,
        policy_name="frozen_mpc",
        on_episode_start=on_start,
    )
    return ds, int(ds.env_interactions)


def run_v081_benchmark(
    *,
    n_model_seeds: int = 10,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    adapt_epochs: int = 12,
    budgets: tuple[int, ...] = (0, 64, 128, 256, 512),
    eval_episodes: int = 2,
    detect_n: int = 128,
    artifact_path: str | Path | None = "artifacts/v081_adaptation.json",
    checkpoint_dir: str | Path = "checkpoints/v081",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    if quick:
        n_train, n_val, epochs, adapt_epochs = 64, 32, 1, 1
        budgets = (0, 32)
        detect_n, eval_episodes = 32, 1
        n_model_seeds = min(n_model_seeds, 1)
    source_spec = source_policy_task()
    seq = v081_sequence_tasks()
    dev = v081_development_target()
    confirms = v081_confirmation_targets()
    noise_probe = v081_noise_probe()
    for spec in (source_spec,) + seq + (dev, noise_probe) + confirms:
        if spec is source_spec:
            continue
        if not v081_safety_ok(spec):
            raise ValueError(f"safety check failed for {spec.task_id}: {spec.params}")
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    per_seed: list[dict[str, Any]] = []

    for mseed in range(n_model_seeds):
        train = collect_transitions(
            source_spec,
            n_transitions=n_train,
            env_seeds=tuple(range(20 + 30 * mseed, 40 + 30 * mseed)),
            base_seed=V081_SOURCE_COLLECT_SEED + 31 * mseed,
            mix=("random", "exploratory"),
        )
        val = collect_transitions(
            source_spec,
            n_transitions=n_val,
            env_seeds=tuple(range(500 + 10 * mseed, 508 + 10 * mseed)),
            base_seed=V081_SOURCE_COLLECT_SEED + 800 + 31 * mseed,
            mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val)
        source, slog = train_world_model(train, val, kind=FROZEN_KIND, epochs=epochs, seed=11 + 17 * mseed)  # type: ignore[arg-type]
        calib = collect_transitions(
            source_spec,
            n_transitions=detect_n,
            env_seeds=tuple(range(700 + 8 * mseed, 708 + 8 * mseed)),
            base_seed=V081_DETECT_CALIB_SEED + 13 * mseed,
            mix=("random", "exploratory"),
        )
        src_hold = collect_transitions(
            source_spec,
            n_transitions=detect_n,
            env_seeds=tuple(range(750 + 8 * mseed, 758 + 8 * mseed)),
            base_seed=V081_DETECT_CALIB_SEED + 200 + 13 * mseed,
            mix=("random", "exploratory"),
        )
        heur_ds = collect_with_actor(
            source_spec,
            n_transitions=detect_n,
            env_seeds=tuple(range(780 + 8 * mseed, 788 + 8 * mseed)),
            base_seed=V081_DETECT_CALIB_SEED + 400 + 13 * mseed,
            actor=heuristic_cartpole,
            policy_name="heuristic",
        )
        ph = ResidualChangeDetector()
        win = WindowThresholdDetector(window=32, k=3.0)
        calib_err = per_transition_mae(source, calib.obs, calib.action, calib.next_obs)
        ph.fit(calib_err)
        win.fit(calib_err)

        def _scan(spec: TaskSpec, ds: Any) -> dict[str, Any]:
            err = per_transition_mae(source, ds.obs, ds.action, ds.next_obs)
            return {
                "mean_mae": float(err.mean()),
                "page_hinkley": ph.scan(err),
                "window": win.scan(err),
                "env_interactions": int(ds.env_interactions),
                "task_id": spec.task_id,
            }

        noise_ds = collect_transitions(
            noise_probe,
            n_transitions=detect_n,
            env_seeds=tuple(range(810 + 8 * mseed, 818 + 8 * mseed)),
            base_seed=V081_DETECT_CALIB_SEED + 600 + 13 * mseed,
            mix=("random", "exploratory"),
        )
        shift_ds = collect_transitions(
            seq[1],
            n_transitions=detect_n,
            env_seeds=tuple(range(840 + 8 * mseed, 848 + 8 * mseed)),
            base_seed=V081_DETECT_CALIB_SEED + 800 + 13 * mseed,
            mix=("random", "exploratory"),
        )
        detection = {
            "source_holdout": _scan(source_spec, src_hold),
            "policy_heuristic": _scan(source_spec, heur_ds),
            "obs_noise": _scan(noise_probe, noise_ds),
            "shift_B": _scan(seq[1], shift_ds),
            "calib_n": detect_n,
            "calib_env_interactions": calib.env_interactions,
        }

        hold_dev = collect_transitions(
            dev,
            n_transitions=max(48, n_val if not quick else 24),
            env_seeds=tuple(range(900 + 8 * mseed, 908 + 8 * mseed)),
            base_seed=V081_TARGET_COLLECT_SEED + 50 + 19 * mseed,
            mix=("random", "exploratory"),
        )
        max_b = max(budgets)
        dev_pool, dev_used = _collect_budget(dev, source, max_b, tag=100, mseed=mseed)
        order = np.arange(len(dev_pool))
        selected: dict[str, str] = {}
        dev_grid: dict[str, Any] = {}
        for b in budgets:
            prefix = dev_pool.slice(order[:b]) if b and len(dev_pool) else dev_pool.slice(np.zeros(0, dtype=np.int64))
            by_m = {}
            best_m, best_ret = "frozen", -1e9
            for method in METHODS:
                model, log = adapt_method(
                    method, source, train, prefix, epochs=adapt_epochs, seed=21 + mseed, episode_disjoint=True
                )
                plan = plan_h3(dev, model, seed=V081_DEV_EVAL_SEED, episodes=eval_episodes)
                pred = _metrics(model, hold_dev)
                by_m[method] = {
                    "log": {k: v for k, v in log.items() if k != "history"},
                    "prediction": pred,
                    "planning": {k: v for k, v in plan.items() if k != "returns"},
                    "target_interactions": int(prefix.env_interactions) if b else 0,
                    "budget_includes_detect_collect": True,
                }
                ret = float(plan["mean_return"])
                if ret > best_ret:
                    best_ret, best_m = ret, method
            selected[str(b)] = best_m
            dev_grid[str(b)] = {"methods": by_m, "selected_by_dev_return": best_m}

        confirm_rows: dict[str, Any] = {}
        for spec in confirms:
            pool, used = _collect_budget(spec, source, max_b, tag=200 + len(spec.task_id), mseed=mseed)
            hold = collect_transitions(
                spec,
                n_transitions=max(48, n_val if not quick else 24),
                env_seeds=tuple(range(1100 + 9 * mseed, 1108 + 9 * mseed)),
                base_seed=V081_TARGET_COLLECT_SEED + 300 + 23 * mseed + len(spec.task_id),
                mix=("random", "exploratory"),
            )
            by_b: dict[str, Any] = {}
            for b in budgets:
                prefix = pool.slice(np.arange(min(b, len(pool)))) if b else pool.slice(np.zeros(0, dtype=np.int64))
                by_m = {}
                for method in METHODS:
                    model, log = adapt_method(
                        method, source, train, prefix, epochs=adapt_epochs, seed=41 + mseed, episode_disjoint=True
                    )
                    plan = plan_h3(spec, model, seed=V081_CONFIRM_EVAL_SEED, episodes=eval_episodes)
                    by_m[method] = {
                        "log": {k: v for k, v in log.items() if k != "history"},
                        "prediction": _metrics(model, hold),
                        "planning": {k: v for k, v in plan.items() if k != "returns"},
                        "target_interactions": int(prefix.env_interactions) if b else 0,
                    }
                by_b[str(b)] = by_m
            confirm_rows[spec.task_id] = {
                "physics": dict(spec.params),
                "by_budget": by_b,
                "collect_interactions": used,
                "split": spec.train_split,
            }

        seq_budget = 32 if quick else (128 if 128 in budgets else budgets[-1])
        memory = PredictiveMemory(max_entries=6, replay_cap=min(2048, n_train + 2 * seq_budget))
        probe_src = val.slice(np.arange(min(32, len(val))))
        memory.store(source, probe_src, stats={"stage": "source"}, replay=None, label="source")
        shared = source.clone()
        seq_log: list[dict[str, Any]] = []
        hold_a = collect_transitions(
            seq[0],
            n_transitions=max(48, n_val if not quick else 24),
            env_seeds=tuple(range(1200 + 6 * mseed, 1206 + 6 * mseed)),
            base_seed=V081_SEQUENCE_EVAL_SEED + 11 * mseed,
            mix=("random", "exploratory"),
        )
        names = ("A", "B", "C", "A_return")
        specs_loop = (seq[0], seq[1], seq[2], seq[0])
        adapters: dict[str, Any] = {}
        for ti, (sp, name) in enumerate(zip(specs_loop, names)):
            tgt, n_used = _collect_budget(sp, shared, seq_budget, tag=400 + 10 * ti, mseed=mseed)
            probe = tgt.slice(np.arange(min(24, len(tgt)))) if len(tgt) else tgt
            retrieved, ret_meta = memory.retrieve(probe)
            naive, _ = adapt_method("finetune", shared, train, tgt, epochs=adapt_epochs, seed=70 + ti, episode_disjoint=True)
            replay_m, _ = adapt_method("replay", shared, train, tgt, epochs=adapt_epochs, seed=80 + ti, episode_disjoint=True)
            adp, _ = adapt_method("adapter", source, train, tgt, epochs=adapt_epochs, seed=90 + ti, episode_disjoint=True)
            scratch, _ = adapt_method("scratch", source, train, tgt, epochs=adapt_epochs, seed=100 + ti, episode_disjoint=True)
            adapters[name] = adp
            if retrieved is not None:
                from_mem, _ = adapt_method("finetune", retrieved, train, tgt, epochs=adapt_epochs, seed=110 + ti, episode_disjoint=True)
            else:
                from_mem = source
            shared = naive
            memory.store(naive, probe, stats={"stage": name}, replay=tgt, label=name)
            eval_sp = seq[0] if name == "A_return" else sp
            hold = hold_a if eval_sp.task_id == seq[0].task_id else collect_transitions(
                sp,
                n_transitions=max(32, 24 if quick else 48),
                env_seeds=tuple(range(1300 + 10 * ti + 6 * mseed, 1304 + 10 * ti + 6 * mseed)),
                base_seed=V081_SEQUENCE_EVAL_SEED + 80 + 7 * ti + mseed,
                mix=("random", "exploratory"),
            )
            seq_log.append(
                {
                    "stage": name,
                    "task_id": sp.task_id,
                    "target_interactions": n_used,
                    "retrieval": ret_meta,
                    "naive_shared": {"prediction": _metrics(naive, hold), "planning": {k: v for k, v in plan_h3(eval_sp, naive, seed=V081_SEQUENCE_EVAL_SEED, episodes=eval_episodes).items() if k != "returns"}},
                    "replay_shared": {"prediction": _metrics(replay_m, hold), "planning": {k: v for k, v in plan_h3(eval_sp, replay_m, seed=V081_SEQUENCE_EVAL_SEED, episodes=eval_episodes).items() if k != "returns"}},
                    "adapter": {"prediction": _metrics(adp, hold), "planning": {k: v for k, v in plan_h3(eval_sp, adp, seed=V081_SEQUENCE_EVAL_SEED, episodes=eval_episodes).items() if k != "returns"}},
                    "scratch": {"prediction": _metrics(scratch, hold), "planning": {k: v for k, v in plan_h3(eval_sp, scratch, seed=V081_SEQUENCE_EVAL_SEED, episodes=eval_episodes).items() if k != "returns"}},
                    "retrieved_then_ft": {"prediction": _metrics(from_mem, hold), "planning": {k: v for k, v in plan_h3(eval_sp, from_mem, seed=V081_SEQUENCE_EVAL_SEED, episodes=eval_episodes).items() if k != "returns"}},
                    "snapshot_source": {"prediction": _metrics(source, hold), "planning": {k: v for k, v in plan_h3(eval_sp, source, seed=V081_SEQUENCE_EVAL_SEED, episodes=eval_episodes).items() if k != "returns"}},
                    "memory_bytes": memory.bytes_used(),
                    "memory_entries": len(memory.entries),
                }
            )

        src_plan = plan_h3(source_spec, source, seed=V081_DEV_EVAL_SEED, episodes=eval_episodes)
        per_seed.append(
            {
                "model_seed": mseed,
                "source_val_loss": slog["best_val"],
                "source_planning": {k: v for k, v in src_plan.items() if k != "returns"},
                "learning_env_steps": train.env_interactions + val.env_interactions,
                "detect_calib_steps": calib.env_interactions,
                "source_checkpoint_nbytes": checkpoint_nbytes(source),
                "detection": detection,
                "dev_grid": {b: {"selected_by_dev_return": dev_grid[b]["selected_by_dev_return"], "methods": {m: {"planning": v["planning"], "prediction": v["prediction"], "target_interactions": v["target_interactions"]} for m, v in dev_grid[b]["methods"].items()}} for b in dev_grid},
                "selected_by_budget": selected,
                "confirmation": confirm_rows,
                "continual": seq_log,
                "memory_bytes": memory.bytes_used(),
                "memory_retrieval_inferences": memory.retrieval_inferences,
            }
        )
        print(f"v081 seed={mseed} selected={selected.get('128', selected.get('32'))}", flush=True)

    confirm_ids = [t.task_id for t in confirms]

    def _mean_confirm(budget: int, method: str, field: str) -> list[float]:
        out = []
        for p in per_seed:
            xs = []
            for tid in confirm_ids:
                node = p["confirmation"][tid]["by_budget"][str(budget)][method]
                if field == "mae":
                    xs.append(float(node["prediction"]["one_step"]["mae"]))
                elif field == "return":
                    xs.append(float(node["planning"]["mean_return"]))
                else:
                    xs.append(float(node["planning"]["fail_rate"] or 0.0))
            out.append(float(np.mean(xs)))
        return out

    summary: dict[str, Any] = {}
    paired: dict[str, Any] = {}
    for b in budgets:
        summary[str(b)] = {
            "mae": {m: seed_level_ci(_mean_confirm(b, m, "mae")) for m in METHODS},
            "plan_return": {m: seed_level_ci(_mean_confirm(b, m, "return")) for m in METHODS},
            "fail_rate": {m: seed_level_ci(_mean_confirm(b, m, "fail")) for m in METHODS},
        }
        per_seed_task = {
            int(p["model_seed"]): {
                "confirm": {m: float(np.mean([p["confirmation"][tid]["by_budget"][str(b)][m]["planning"]["mean_return"] for tid in confirm_ids])) for m in METHODS}
            }
            for p in per_seed
        }
        paired[str(b)] = {
            "finetune_minus_frozen": paired_seed_deltas(per_seed_task=per_seed_task, treatment="finetune", baseline="frozen"),
            "replay_minus_frozen": paired_seed_deltas(per_seed_task=per_seed_task, treatment="replay", baseline="frozen"),
            "scratch_minus_frozen": paired_seed_deltas(per_seed_task=per_seed_task, treatment="scratch", baseline="frozen"),
            "adapter_minus_frozen": paired_seed_deltas(per_seed_task=per_seed_task, treatment="adapter", baseline="frozen"),
        }

    payload = {
        "protocol": {
            "code_version": "v0.8.1",
            "parent_commit": "3ca8435",
            "physics_version": CARTPOLE_PHYSICS_VERSION,
            "non_saturation_rule": "obs_noise_std=0.08 + unused physics; frozen H=3 screen < 400 on development",
            "selection_split": "dev_v081",
            "selection_metric": "dev_plan_return",
            "episode_disjoint_splits": True,
            "confirm_eval_seed": V081_CONFIRM_EVAL_SEED,
            "n_model_seeds": n_model_seeds,
            "budgets": list(budgets),
            "budget_includes_detection_collect": True,
            "retuned_on_confirmation": False,
            "planner_uses_simulator": False,
            "inference_uses_privileged_physics": False,
            "is_agi": False,
            "quick": quick,
        },
        "tasks": {
            "source": dict(source_spec.params),
            "sequence": [dict(s.params) | {"task_id": s.task_id} for s in seq],
            "development": dict(dev.params) | {"task_id": dev.task_id},
            "confirmation": [dict(t.params) | {"task_id": t.task_id} for t in confirms],
        },
        "detection": {
            "source_window_alarm_frac": seed_level_ci([float(p["detection"]["source_holdout"]["window"]["alarm_frac"]) for p in per_seed]),
            "source_ph_alarm_frac": seed_level_ci([float(p["detection"]["source_holdout"]["page_hinkley"]["ph_alarm_frac"]) for p in per_seed]),
            "noise_window_alarm_frac": seed_level_ci([float(p["detection"]["obs_noise"]["window"]["alarm_frac"]) for p in per_seed]),
            "shift_B_window_alarm_frac": seed_level_ci([float(p["detection"]["shift_B"]["window"]["alarm_frac"]) for p in per_seed]),
            "policy_heuristic_window_alarm_frac": seed_level_ci([float(p["detection"]["policy_heuristic"]["window"]["alarm_frac"]) for p in per_seed]),
            "shift_B_window_delay": seed_level_ci([float(p["detection"]["shift_B"]["window"]["detection_delay"] or detect_n) for p in per_seed]),
            "shift_B_miss_rate": seed_level_ci([1.0 if p["detection"]["shift_B"]["window"]["missed"] else 0.0 for p in per_seed]),
        },
        "confirmation_summary": summary,
        "confirmation_by_task": {
            tid: {
                str(b): {
                    m: {
                        "mae": seed_level_ci([float(p["confirmation"][tid]["by_budget"][str(b)][m]["prediction"]["one_step"]["mae"]) for p in per_seed]),
                        "plan_return": seed_level_ci([float(p["confirmation"][tid]["by_budget"][str(b)][m]["planning"]["mean_return"]) for p in per_seed]),
                        "fail_rate": seed_level_ci([float(p["confirmation"][tid]["by_budget"][str(b)][m]["planning"]["fail_rate"] or 0.0) for p in per_seed]),
                    }
                    for m in METHODS
                }
                for b in budgets
            }
            for tid in confirm_ids
        },
        "paired_planning_vs_frozen": paired,
        "dev_selection": {str(p["model_seed"]): p["selected_by_budget"] for p in per_seed},
        "continual_return_to_A": {
            "naive_return": seed_level_ci([float(p["continual"][-1]["naive_shared"]["planning"]["mean_return"]) for p in per_seed]),
            "snapshot_return": seed_level_ci([float(p["continual"][-1]["snapshot_source"]["planning"]["mean_return"]) for p in per_seed]),
            "retrieved_return": seed_level_ci([float(p["continual"][-1]["retrieved_then_ft"]["planning"]["mean_return"]) for p in per_seed]),
            "naive_mae": seed_level_ci([float(p["continual"][-1]["naive_shared"]["prediction"]["one_step"]["mae"]) for p in per_seed]),
            "snapshot_mae": seed_level_ci([float(p["continual"][-1]["snapshot_source"]["prediction"]["one_step"]["mae"]) for p in per_seed]),
        },
        "costs": {
            "mean_source_env_steps": float(np.mean([p["learning_env_steps"] for p in per_seed])),
            "mean_detect_calib_steps": float(np.mean([p["detect_calib_steps"] for p in per_seed])),
            "mean_memory_bytes": float(np.mean([p["memory_bytes"] for p in per_seed])),
            "mean_retrieval_inferences": float(np.mean([p["memory_retrieval_inferences"] for p in per_seed])),
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.8.1 CartPole with observation noise. Not AGI. Control gains are not assumed from MAE.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
