"""Persist vs persist+obs vs retrieved-mean. Development only. Not science.

Locked eight decide() tasks. Historical PersistentAdaptive is unchanged.
No collection. E2.17 stays inconclusive.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from nexus.core.persist_obs import PersistentAdaptiveObs
from nexus.core.strategy_memory import ContextualStrategyMemory
from nexus.core.strategy_memory_decide_bench import FREE_SLOTS, PROPOSALS, DecideTask, _observe, _run_task, make_tasks
from nexus.core.strategy_memory_obs_bench import _score_tables, _summarize, _train, _unit_table, make_heldout_tasks
from nexus.evolution1.toy_loop import VARIANTS
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.methods import PersistentAdaptive, make_methods

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "strategy_memory_persist_obs_bench.json"
COMPARE = ("persistent_adaptive", "persistent_adaptive_obs", "memory_combined_retrieved")


def _make_methods(seed: int) -> dict:
    methods = make_methods(seed)
    methods["persistent_adaptive_obs"] = PersistentAdaptiveObs(seed=seed)
    methods["memory_combined_retrieved"] = ContextualStrategyMemory(
        seed=seed, retrieve=True, persist_memory=True, mode="combined", selector="retrieved_mean"
    )
    return methods


def causal_persist_obs(tasks, scores, seed: int = 7) -> dict:
    stored = next(task for task in tasks if task.task_id == "acro_store_0")
    zero_obs = np.zeros(stored.context.obs_dim, dtype=np.float32)
    rng = np.random.default_rng(seed + 19)
    shuffled = np.asarray(stored.obs, dtype=np.float64).copy()
    rng.shuffle(shuffled)
    stored_unit = scores[stored.task_id]["unit"]
    zero_probe = DecideTask(
        "causal_zero_landscape",
        "causal",
        stored.family,
        91,
        stored.context,
        stored.support,
        zero_obs,
        stored.model,
        False,
    )
    zero_unit = _unit_table(zero_probe, seed + 91)

    def _select(method, obs, label: str):
        if hasattr(method, "eval_clone"):
            clone = method.eval_clone(local_updates=False)
        else:
            clone = method
        probe = DecideTask(
            f"causal_{label}",
            "causal",
            stored.family,
            90,
            stored.context,
            stored.support,
            np.asarray(obs, dtype=np.float32),
            stored.model,
            False,
        )
        _observe(clone, probe)
        choice = clone.choose(tuple(VARIANTS), probe.context)
        return {
            "choice": choice.fingerprint,
            "obs_norm": float(np.linalg.norm(obs)),
            "stored_landscape_unit": float(stored_unit[choice]),
            "zero_landscape_unit": float(zero_unit[choice]),
        }

    payload = {}
    builders = {
        "persistent_adaptive": lambda: PersistentAdaptive(seed=seed),
        "persistent_adaptive_obs": lambda: PersistentAdaptiveObs(seed=seed),
        "memory_combined_retrieved": lambda: ContextualStrategyMemory(
            seed=seed, retrieve=True, persist_memory=True, mode="combined", selector="retrieved_mean"
        ),
    }
    for name, build in builders.items():
        method = build()
        if name == "persistent_adaptive":
            for task in tasks:
                if task.phase == "train":
                    _run_task(method, task, unit=scores[task.task_id]["unit"], update=True)
            if hasattr(method, "freeze"):
                method.freeze()
        else:
            _train(method, tasks, scores)
            if hasattr(method, "freeze"):
                method.freeze()
        stored_q = _select(method, stored.obs, f"{name}_stored")
        zero_q = _select(method, zero_obs, f"{name}_zero")
        shuffle_q = _select(method, shuffled, f"{name}_shuffle")
        payload[name] = {
            "stored_obs": stored_q,
            "zero_obs": zero_q,
            "shuffled_obs": shuffle_q,
            "choice_changes_with_zero_obs": stored_q["choice"] != zero_q["choice"],
            "zero_query_better_on_zero_landscape": zero_q["zero_landscape_unit"] > stored_q["zero_landscape_unit"],
            "stored_query_not_worse_on_stored_landscape": stored_q["stored_landscape_unit"]
            >= zero_q["stored_landscape_unit"] - 1e-12,
        }
    return payload


def run_benchmark(seed: int = 7) -> dict:
    if grant.grant_unused():
        raise RuntimeError("e217_grant_must_stay_consumed")
    started = time.perf_counter()
    cpu0 = time.process_time()
    tasks = make_tasks()
    if [task.task_id for task in tasks][-1] != "acro_zero_collision":
        raise RuntimeError("collision_task_missing")
    scores = _score_tables(tasks, seed)
    methods = _make_methods(seed)
    phases = ("train", "development", "shifted", "collision")
    rows = {name: {phase: [] for phase in phases} for name in methods}
    for task in tasks:
        unit = scores[task.task_id]["unit"]
        for name, method in methods.items():
            rows[name][task.phase].append(_run_task(method, task, unit=unit, update=True))
    lookups = {name: sum(len(block) * PROPOSALS for block in rows[name].values()) for name in methods}
    if len(set(lookups.values())) != 1:
        raise RuntimeError("unmatched_lookup_budget")
    summary = {
        name: {
            "train": _summarize(rows[name]["train"]),
            "development": _summarize(rows[name]["development"]),
            "shifted": _summarize(rows[name]["shifted"]),
            "collision": _summarize(rows[name]["collision"]),
        }
        for name in methods
    }
    causal = causal_persist_obs(tasks, scores, seed)
    heldout_tasks = make_heldout_tasks()
    heldout_scores = _score_tables(heldout_tasks, seed + 3)
    heldout_methods = _make_methods(seed + 3)
    heldout_rows = {name: [] for name in heldout_methods}
    for task in list(tasks) + list(heldout_tasks):
        table = scores.get(task.task_id) or heldout_scores[task.task_id]
        for name, method in heldout_methods.items():
            if task.task_id in scores:
                _run_task(method, task, unit=table["unit"], update=True)
            else:
                heldout_rows[name].append(_run_task(method, task, unit=table["unit"], update=False))
    heldout = {name: _summarize(heldout_rows[name]) for name in COMPARE}
    persist = summary["persistent_adaptive"]
    persist_obs = summary["persistent_adaptive_obs"]
    memory = summary["memory_combined_retrieved"]
    decision = {
        "persist_obs_beats_persist_shifted_first_free": persist_obs["shifted"]["first_free_regret"]
        < persist["shifted"]["first_free_regret"],
        "persist_obs_not_worse_stored_dev": persist_obs["development"]["first_free_regret"]
        <= persist["development"]["first_free_regret"] + 1e-9,
        "persist_obs_beats_memory_shifted_first_free": persist_obs["shifted"]["first_free_regret"]
        < memory["shifted"]["first_free_regret"],
        "causal_persist_stable": not causal["persistent_adaptive"]["choice_changes_with_zero_obs"],
        "causal_persist_obs_changes": causal["persistent_adaptive_obs"]["choice_changes_with_zero_obs"],
        "causal_persist_obs_better_on_zero": causal["persistent_adaptive_obs"]["zero_query_better_on_zero_landscape"],
        "historical_persist_weights": 6,
        "persist_obs_weights": 22,
    }
    decision["persist_obs_helps"] = bool(
        decision["persist_obs_beats_persist_shifted_first_free"] and decision["persist_obs_not_worse_stored_dev"]
    )
    decision["stop_fakestep_line"] = not decision["persist_obs_helps"]
    wall = time.perf_counter() - started
    cpu = time.process_time() - cpu0
    return {
        "scientific": False,
        "collection": False,
        "gymnasium": False,
        "env_steps": 0,
        "claims_agi": False,
        "claims_learning_to_learn": False,
        "historical_e217_label": "inconclusive",
        "grant_consumed": True,
        "used_e217_science_arrays": False,
        "score_source": "decide_fake_step_model",
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "seed": seed,
        "matched_proposals": PROPOSALS,
        "free_slots": FREE_SLOTS,
        "lookups": lookups,
        "summary": {name: summary[name] for name in list(COMPARE) + ["reset_adaptive"]},
        "rows": {name: {phase: rows[name][phase] for phase in phases} for name in COMPARE},
        "causal_observation_intervention": causal,
        "heldout_separate": True,
        "heldout": heldout,
        "decision": decision,
        "wall_s": wall,
        "cpu_s": cpu,
        "note": "Persist+obs development bench, not a scientific result and not AGI.",
    }


def write_artifact(seed: int = 7) -> dict:
    payload = run_benchmark(seed)
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
