"""Persist vs retrieved-mean on disposable residual decide() scores.

Uses E2.9 fit-clock residuals and E2.8 source arrays only. Does not
load E2.17 science arrays or science fits. No collection. Not science.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from nexus.core.strategy_memory import ContextualStrategyMemory
from nexus.core.strategy_memory_decide_bench import (
    FREE_SLOTS,
    PROPOSALS,
    SCIENCE_ARRAYS,
    DecideTask,
    _run_task,
    family_context,
    near_zero_support,
    obs_from_source,
    support_from_source,
)
from nexus.core.strategy_memory_obs_bench import _score_tables, _summarize
from nexus.evolution1.toy_loop import VARIANTS
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.bindings import reviewed_binding
from nexus.evolution2.methods import make_methods
from nexus.evolution2.persist_reset_path import disposable_model

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "strategy_memory_residual_bench.json"
SCIENCE_FITS = ROOT / "artifacts" / "evolution2_persist_reset_science_fits"
DISPOSABLE = ROOT / "artifacts" / "evolution2_fit_clock_disposable"
COMPARE = ("persistent_adaptive", "memory_combined_retrieved", "reset_adaptive")


def _refuse_science_files(path: Path) -> None:
    text = str(path)
    if "persist_reset_science" in text or SCIENCE_ARRAYS in path.parents or SCIENCE_FITS in path.parents:
        raise RuntimeError("e217_science_artifacts_forbidden")


def residual_model(family: str, bundle: int):
    path = DISPOSABLE / family / f"bundle{bundle}.pt"
    _refuse_science_files(path)
    if not path.is_file():
        raise RuntimeError("disposable_residual_missing")
    model = disposable_model(family, bundle)
    if getattr(model, "uses_simulator", False):
        raise RuntimeError("simulator_use_forbidden")
    return model


def _task(task_id: str, phase: str, family: str, model_bundle: int, support, obs, *, expected_failure: bool = False) -> DecideTask:
    return DecideTask(
        task_id,
        phase,
        family,
        200 + 10 * model_bundle + (0 if family == "pendulum" else 1),
        family_context(family),
        support,
        np.asarray(obs, dtype=np.float32),
        residual_model(family, model_bundle),
        expected_failure,
    )


def make_residual_tasks() -> tuple[DecideTask, ...]:
    acro_ctx = family_context("acrobot")
    return (
        _task("res_pend_store_0", "train", "pendulum", 0, support_from_source("pendulum", 0), obs_from_source("pendulum", 0)),
        _task("res_acro_store_0", "train", "acrobot", 0, support_from_source("acrobot", 0), obs_from_source("acrobot", 0)),
        _task("res_pend_store_1", "train", "pendulum", 1, support_from_source("pendulum", 1), obs_from_source("pendulum", 1)),
        _task("res_acro_store_1", "train", "acrobot", 1, support_from_source("acrobot", 1), obs_from_source("acrobot", 1)),
        _task("res_pend_store_2", "development", "pendulum", 2, support_from_source("pendulum", 2), obs_from_source("pendulum", 2)),
        _task("res_acro_store_2", "development", "acrobot", 2, support_from_source("acrobot", 2), obs_from_source("acrobot", 2)),
        _task(
            "res_acro_zero",
            "shifted",
            "acrobot",
            0,
            near_zero_support(acro_ctx, 21),
            np.zeros(reviewed_binding("acrobot").obs_dim, dtype=np.float32),
        ),
        _task(
            "res_acro_collision",
            "collision",
            "acrobot",
            0,
            support_from_source("acrobot", 2),
            np.zeros(reviewed_binding("acrobot").obs_dim, dtype=np.float32),
            expected_failure=True,
        ),
    )


def _oracles(score_tables: dict) -> dict:
    out = {}
    for task_id, table in score_tables.items():
        variant = next(item for item in VARIANTS if item.fingerprint == table["oracle_variant"])
        out[task_id] = {
            "variant": table["oracle_variant"],
            "rule": variant.rule.value,
            "horizon": variant.horizon,
        }
    return out


def run_benchmark(seed: int = 7) -> dict:
    if grant.grant_unused():
        raise RuntimeError("e217_grant_must_stay_consumed")
    if SCIENCE_FITS.is_dir() and any(SCIENCE_FITS.rglob("*.pt")):
        pass
    started = time.perf_counter()
    cpu0 = time.process_time()
    tasks = make_residual_tasks()
    if FREE_SLOTS != 4 or PROPOSALS != 6:
        raise RuntimeError("locked_budget_changed")
    scores = _score_tables(tasks, seed)
    oracles = _oracles(scores)
    ranking_shift = len({row["rule"] + str(row["horizon"]) for row in oracles.values()}) > 1
    methods = make_methods(seed)
    methods["memory_combined_retrieved"] = ContextualStrategyMemory(
        seed=seed, retrieve=True, persist_memory=True, mode="combined", selector="retrieved_mean"
    )
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
    persist = summary["persistent_adaptive"]
    memory = summary["memory_combined_retrieved"]
    decision = {
        "residual_scores_available": True,
        "used_e217_science_arrays": False,
        "used_e217_science_fits": False,
        "source": "evolution2_fit_clock_disposable",
        "planner_ranking_shifts_across_tasks": ranking_shift,
        "memory_beats_persist_shifted_first_free": memory["shifted"]["first_free_regret"]
        < persist["shifted"]["first_free_regret"],
        "memory_not_worse_stored_dev": memory["development"]["first_free_regret"]
        <= persist["development"]["first_free_regret"] + 1e-9,
        "memory_beats_persist_dev": memory["development"]["first_free_regret"] < persist["development"]["first_free_regret"],
    }
    decision["development_success"] = bool(
        decision["planner_ranking_shifts_across_tasks"]
        and decision["memory_beats_persist_shifted_first_free"]
        and decision["memory_not_worse_stored_dev"]
    )
    decision["stop_residual_catalogue_line"] = not decision["planner_ranking_shifts_across_tasks"]
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
        "score_source": "decide_disposable_residual",
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "seed": seed,
        "matched_proposals": PROPOSALS,
        "free_slots": FREE_SLOTS,
        "lookups": lookups,
        "oracles": oracles,
        "summary": {name: summary[name] for name in COMPARE},
        "rows": {name: {phase: rows[name][phase] for phase in phases} for name in COMPARE},
        "decision": decision,
        "wall_s": wall,
        "cpu_s": cpu,
        "note": "Disposable residual decide() bench, not a scientific result and not AGI.",
    }


def write_artifact(seed: int = 7) -> dict:
    payload = run_benchmark(seed)
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
