"""Retrieved-mean / gated selector bench. Development only. Not science.

Keeps the observation-aware combined descriptor and the locked eight
decide() tasks. Replaces LinUCB argmax when retrieved neighbors are
usable. Persist remains the external baseline. No collection.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from nexus.core.strategy_memory import ContextualStrategyMemory, KERNEL_LENGTH, make_selector_configs
from nexus.core.strategy_memory_decide_bench import FREE_SLOTS, PROPOSALS, _run_task, make_tasks
from nexus.core.strategy_memory_obs_bench import (
    _score_tables,
    _summarize,
    causal_observation_intervention,
    make_heldout_tasks,
)
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.methods import make_methods

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "strategy_memory_selector_bench.json"
SELECT_NAMES = ("memory_combined_ucb", "memory_combined_retrieved", "memory_combined_gated")


def run_benchmark(seed: int = 7) -> dict:
    if grant.grant_unused():
        raise RuntimeError("e217_grant_must_stay_consumed")
    started = time.perf_counter()
    cpu0 = time.process_time()
    tasks = make_tasks()
    if [task.task_id for task in tasks][-1] != "acro_zero_collision":
        raise RuntimeError("collision_task_missing")
    if FREE_SLOTS != 4 or PROPOSALS != 6:
        raise RuntimeError("locked_budget_changed")
    scores = _score_tables(tasks, seed)
    methods = make_methods(seed)
    methods.update(make_selector_configs(seed))
    phases = ("train", "development", "shifted", "collision")
    rows = {name: {phase: [] for phase in phases} for name in methods}
    traces = {}
    for task in tasks:
        unit = scores[task.task_id]["unit"]
        for name, method in methods.items():
            row = _run_task(method, task, unit=unit, update=True)
            rows[name][task.phase].append(row)
            if isinstance(method, ContextualStrategyMemory) and task.phase != "train":
                traces.setdefault(name, {})[task.task_id] = {
                    "first_free": row["first_free"],
                    "first_free_regret": row["first_free_regret"],
                    "regret": row["regret"],
                    "neighbors": method.retrieval_trace(k=4),
                    "selector": method.selector,
                }
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
    causal = {
        selector: causal_observation_intervention(tasks, scores, seed, modes=("combined",), selector=selector)["combined"]
        for selector in ("ucb", "retrieved_mean", "gated")
    }
    heldout_tasks = make_heldout_tasks()
    heldout_scores = _score_tables(heldout_tasks, seed + 3)
    heldout_methods = make_methods(seed + 3)
    heldout_methods.update(make_selector_configs(seed + 3))
    heldout_rows = {name: [] for name in heldout_methods}
    for task in list(tasks) + list(heldout_tasks):
        table = scores.get(task.task_id) or heldout_scores[task.task_id]
        for name, method in heldout_methods.items():
            if task.task_id in scores:
                _run_task(method, task, unit=table["unit"], update=True)
            else:
                heldout_rows[name].append(_run_task(method, task, unit=table["unit"], update=False))
    heldout = {name: _summarize(heldout_rows[name]) for name in heldout_methods}
    persist = summary["persistent_adaptive"]

    def _ok(name: str) -> dict:
        row = summary[name]
        sel = {"memory_combined_ucb": "ucb", "memory_combined_retrieved": "retrieved_mean", "memory_combined_gated": "gated"}[name]
        return {
            "beats_persist_shifted_first_free": row["shifted"]["first_free_regret"] < persist["shifted"]["first_free_regret"],
            "not_worse_stored_dev_first_free": row["development"]["first_free_regret"]
            <= persist["development"]["first_free_regret"] + 1e-9,
            "beats_ucb_shifted_first_free": row["shifted"]["first_free_regret"]
            < summary["memory_combined_ucb"]["shifted"]["first_free_regret"],
            "causal_choice_changes": causal[sel]["choice_changes_with_zero_obs"],
            "causal_better_on_zero": causal[sel]["zero_query_better_on_zero_landscape"],
        }

    checks = {name: _ok(name) for name in SELECT_NAMES}
    winner = None
    for name in ("memory_combined_retrieved", "memory_combined_gated"):
        row = checks[name]
        if row["beats_persist_shifted_first_free"] and row["not_worse_stored_dev_first_free"] and row["causal_better_on_zero"]:
            winner = name
            break
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
        "gate": {"min_dist": KERNEL_LENGTH, "conflict_blocks": True},
        "lookups": lookups,
        "summary": summary,
        "rows": {name: {phase: rows[name][phase] for phase in phases} for name in methods},
        "retrieval_traces": traces,
        "causal_observation_intervention": causal,
        "heldout_separate": True,
        "heldout": heldout,
        "heldout_task_ids": [task.task_id for task in heldout_tasks],
        "checks": checks,
        "development_success": winner is not None,
        "successful_selector": winner,
        "wall_s": wall,
        "cpu_s": cpu,
        "memory_records": methods["memory_combined_retrieved"].memory_state(),
        "note": "Selector development bench, not a scientific result and not AGI.",
    }


def write_artifact(seed: int = 7) -> dict:
    payload = run_benchmark(seed)
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
