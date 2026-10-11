"""V0.7 final confirmation: frozen H=3 residual planner, untouched physics."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from nexus.cl.metrics import paired_seed_deltas, seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import source_policy_task
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION
from nexus.world.baselines import heuristic_cartpole, run_episodes
from nexus.world.data import assert_disjoint_seeds, collect_transitions
from nexus.world.freeze import (
    FROZEN_CANDIDATES,
    FROZEN_EPOCHS,
    FROZEN_HORIZONS,
    FROZEN_KIND,
    FROZEN_N_TRAIN,
    FROZEN_N_VAL,
    FROZEN_OBJECTIVE,
    FROZEN_PLAN_BUDGET,
    FROZEN_PRIMARY_HORIZON,
    v073_confirmation_targets,
)
from nexus.world.planning import InferenceCounter, RandomShootingMPC, one_step_greedy
from nexus.world.protocol import COLLECT_TRAIN_SEED, COLLECT_VAL_SEED, CONFIRM_EVAL_SEED_V073
from nexus.world.train import train_world_model
from nexus.world.v072 import _eval_mpc


def run_v073_benchmark(
    *,
    n_model_seeds: int = 10,
    eval_seeds: int = 2,
    eval_episodes: int = 2,
    artifact_path: str | Path | None = "artifacts/v073_world_model.json",
    checkpoint_dir: str | Path = "checkpoints/v073",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    source = source_policy_task()
    confirms = v073_confirmation_targets()
    tasks = (source,) + confirms
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    per_seed: list[dict[str, Any]] = []

    for mseed in range(n_model_seeds):
        train = collect_transitions(
            source,
            n_transitions=FROZEN_N_TRAIN,
            env_seeds=tuple(range(10 + 20 * mseed, 30 + 20 * mseed)),
            base_seed=COLLECT_TRAIN_SEED + 23 * mseed,
            mix=("random", "exploratory"),
        )
        val = collect_transitions(
            source,
            n_transitions=FROZEN_N_VAL,
            env_seeds=tuple(range(600 + 10 * mseed, 608 + 10 * mseed)),
            base_seed=COLLECT_VAL_SEED + 23 * mseed,
            mix=("random", "exploratory"),
        )
        assert_disjoint_seeds(train, val)
        residual, log = train_world_model(
            train, val, kind=FROZEN_KIND, epochs=FROZEN_EPOCHS, seed=5 + 19 * mseed  # type: ignore[arg-type]
        )
        by_task: dict[str, Any] = {}
        inf_tot = 0
        for spec in tasks:
            methods: dict[str, list[float]] = {k: [] for k in ("greedy", "h1", "h3", "h6", "heuristic")}
            env_steps = {k: 0 for k in methods}
            for i in range(eval_seeds):
                es = CONFIRM_EVAL_SEED_V073 + 31 * i
                g_row = run_episodes(spec, act_fn=lambda o, m=residual: one_step_greedy(m, o, 2), episodes=eval_episodes, seed=es)
                methods["greedy"].append(float(g_row["mean_return"]))
                env_steps["greedy"] += int(g_row["env_interactions"])
                h_row = run_episodes(spec, act_fn=heuristic_cartpole, episodes=eval_episodes, seed=es)
                methods["heuristic"].append(float(h_row["mean_return"]))
                env_steps["heuristic"] += int(h_row["env_interactions"])
                for h, key in ((1, "h1"), (3, "h3"), (6, "h6")):
                    inf = InferenceCounter(residual)
                    planner = RandomShootingMPC(
                        model=residual,
                        n_actions=2,
                        horizon=h,
                        n_candidates=FROZEN_CANDIDATES[h],
                        seed=0,
                        inference=inf,
                        objective=FROZEN_OBJECTIVE,  # type: ignore[arg-type]
                    )
                    row = _eval_mpc(spec, planner, episodes=eval_episodes, seed=es)
                    methods[key].append(float(row["mean_return"]))
                    env_steps[key] += int(row["env_interactions"])
                    inf_tot += inf.states
            by_task[spec.task_id] = {
                "returns": {k: float(np.mean(v)) for k, v in methods.items()},
                "per_eval": methods,
                "eval_env_steps": env_steps,
                "physics": dict(spec.params),
                "split": spec.train_split,
            }
        per_seed.append(
            {
                "model_seed": mseed,
                "init_seed": 5 + 19 * mseed,
                "collect_seed": COLLECT_TRAIN_SEED + 23 * mseed,
                "val_loss": log["best_val"],
                "learning_env_steps": train.env_interactions + val.env_interactions,
                "targets": by_task,
                "model_states": inf_tot,
            }
        )
        print(f"v073 seed={mseed} h3_confirm={np.mean([by_task[t.task_id]['returns']['h3'] for t in confirms]):.1f}", flush=True)

    def _across(task_id: str, method: str) -> list[float]:
        return [float(p["targets"][task_id]["returns"][method]) for p in per_seed]

    confirm_ids = [t.task_id for t in confirms]
    source_id = source.task_id

    def _mean_confirm(method: str) -> list[float]:
        out = []
        for p in per_seed:
            xs = [p["targets"][tid]["returns"][method] for tid in confirm_ids]
            out.append(float(np.mean(xs)))
        return out

    paired_confirm: dict[int, dict[str, dict[str, float]]] = {
        int(p["model_seed"]): {
            "confirm": {
                m: float(np.mean([p["targets"][tid]["returns"][m] for tid in confirm_ids]))
                for m in ("greedy", "h1", "h3", "h6", "heuristic")
            }
        }
        for p in per_seed
    }
    payload = {
        "protocol": {
            "code_version": "v0.7.3",
            "parent_commit": "6f0e3d3",
            "physics_version": CARTPOLE_PHYSICS_VERSION,
            "frozen_from": "v0.7.2 residual H=3 recipe",
            "kind": FROZEN_KIND,
            "n_train": FROZEN_N_TRAIN,
            "n_val": FROZEN_N_VAL,
            "epochs": FROZEN_EPOCHS,
            "objective": FROZEN_OBJECTIVE,
            "plan_budget": FROZEN_PLAN_BUDGET,
            "horizons": list(FROZEN_HORIZONS),
            "candidates": {str(k): v for k, v in FROZEN_CANDIDATES.items()},
            "primary_horizon": FROZEN_PRIMARY_HORIZON,
            "confirm_eval_seed": CONFIRM_EVAL_SEED_V073,
            "n_model_seeds": n_model_seeds,
            "confirmation_tasks": confirm_ids,
            "confirmation_params": [dict(t.params) for t in confirms],
            "retuned_on_confirmation": False,
            "planner_uses_simulator": False,
            "planner_uses_privileged_params": False,
            "v08_not_implemented": True,
            "is_agi": False,
        },
        "source": {m: seed_level_ci(_across(source_id, m)) for m in ("greedy", "h1", "h3", "h6", "heuristic")},
        "confirmation_mean": {m: seed_level_ci(_mean_confirm(m)) for m in ("greedy", "h1", "h3", "h6", "heuristic")},
        "confirmation_by_task": {
            tid: {m: seed_level_ci(_across(tid, m)) for m in ("greedy", "h1", "h3", "h6", "heuristic")} for tid in confirm_ids
        },
        "paired_confirmation": {
            "h3_minus_greedy": paired_seed_deltas(per_seed_task=paired_confirm, treatment="h3", baseline="greedy"),
            "h3_minus_h1": paired_seed_deltas(per_seed_task=paired_confirm, treatment="h3", baseline="h1"),
            "h6_minus_h3": paired_seed_deltas(per_seed_task=paired_confirm, treatment="h6", baseline="h3"),
            "h3_minus_heuristic": paired_seed_deltas(per_seed_task=paired_confirm, treatment="h3", baseline="heuristic"),
        },
        "paired_source": {
            "h3_minus_greedy": paired_seed_deltas(
                per_seed_task={int(p["model_seed"]): {"src": p["targets"][source_id]["returns"]} for p in per_seed},
                treatment="h3",
                baseline="greedy",
            )
        },
        "costs": {
            "mean_learning_env_steps": float(np.mean([p["learning_env_steps"] for p in per_seed])),
            "n_train": FROZEN_N_TRAIN,
            "n_val": FROZEN_N_VAL,
            "mean_model_states": float(np.mean([p["model_states"] for p in per_seed])),
        },
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "V0.7 confirmation. Frozen H=3. Not V0.8. Not AGI.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
