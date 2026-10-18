"""Observation-aware strategy-memory development bench. Not science.

Reuses the locked eight decide() tasks, FakeStepModel scoring, and
ContextualStrategyMemory. Adds a planning-observation sketch and four
descriptor configurations. No collection. E2.17 stays inconclusive.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from nexus.core.strategy_memory import (
    KERNEL_LENGTH,
    OBS_SKETCH_DIM,
    SUPPORT_DIM,
    ContextualStrategyMemory,
    compose_descriptor,
    describe_planning_obs,
    describe_support,
    make_descriptor_configs,
)
from nexus.core.strategy_memory_decide_bench import (
    FREE_SLOTS,
    PROPOSALS,
    SOURCE_ROOT,
    DecideTask,
    _observe,
    _run_task,
    family_context,
    make_tasks,
    near_zero_support,
    raw_catalogue_scores,
    support_from_arrays,
)
from nexus.evolution1.catalogue import digest
from nexus.evolution1.toy_loop import VARIANTS
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.bindings import reviewed_binding
from nexus.evolution2.methods import make_methods
from nexus.evolution2.persist_reset_science import FrozenRevealedScale

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "strategy_memory_obs_bench.json"


def _score_tables(tasks, seed: int) -> dict:
    tables = {}
    for task in tasks:
        raw = raw_catalogue_scores(task, seed + int(digest(task.task_id)[:8], 16) % 1000)
        scale = FrozenRevealedScale(raw)
        tables[task.task_id] = {
            "raw": {variant.fingerprint: raw[variant] for variant in VARIANTS},
            "unit": {variant: scale.unit(raw[variant]) for variant in VARIANTS},
            "oracle_variant": max(VARIANTS, key=lambda variant: raw[variant]).fingerprint,
        }
    return tables


def descriptor_diagnosis(tasks=None) -> dict:
    tasks = tuple(make_tasks() if tasks is None else tasks)
    rows = {}
    for task in tasks:
        support = describe_support(task.support, task.context)
        sketch = describe_planning_obs(task.obs, task.context)
        rows[task.task_id] = {
            "support": [float(x) for x in support],
            "obs_sketch": [float(x) for x in sketch],
            "combined": [float(x) for x in compose_descriptor(task.support, task.context, task.obs, mode="combined")],
            "obs_norm": float(np.linalg.norm(task.obs)),
            "family": task.family,
            "phase": task.phase,
        }

    def _pairs(mode: str) -> dict:
        vecs = {task.task_id: np.asarray(rows[task.task_id][mode], dtype=np.float64) for task in tasks}
        out = {}
        ids = [task.task_id for task in tasks]
        for i, left in enumerate(ids):
            for right in ids[i + 1 :]:
                dist = float(np.linalg.norm(vecs[left] - vecs[right]))
                out[f"{left}__{right}"] = {
                    "distance": dist,
                    "kernel_weight": float(np.exp(-((dist / KERNEL_LENGTH) ** 2))),
                }
        return out

    def _pair(pairs: dict, left: str, right: str) -> dict:
        return pairs.get(f"{left}__{right}") or pairs[f"{right}__{left}"]

    support_pairs = _pairs("support")
    obs_pairs = _pairs("obs_sketch")
    combined_pairs = _pairs("combined")
    return {
        "support_dim": SUPPORT_DIM,
        "obs_sketch_dim": OBS_SKETCH_DIM,
        "combined_dim": SUPPORT_DIM + OBS_SKETCH_DIM,
        "kernel_length": KERNEL_LENGTH,
        "tasks": rows,
        "pairwise": {"support": support_pairs, "obs_sketch": obs_pairs, "combined": combined_pairs},
        "focus": {
            "collision_vs_stored_support": _pair(support_pairs, "acro_store_0", "acro_zero_collision"),
            "collision_vs_zero_support": _pair(support_pairs, "acro_zero_0", "acro_zero_collision"),
            "collision_vs_stored_obs": _pair(obs_pairs, "acro_store_0", "acro_zero_collision"),
            "collision_vs_zero_obs": _pair(obs_pairs, "acro_zero_0", "acro_zero_collision"),
            "collision_vs_stored_combined": _pair(combined_pairs, "acro_store_0", "acro_zero_collision"),
            "collision_vs_zero_combined": _pair(combined_pairs, "acro_zero_0", "acro_zero_collision"),
            "fair_zero_vs_zero_support": _pair(support_pairs, "acro_zero_0", "acro_zero_1"),
            "fair_zero_vs_stored_support": _pair(support_pairs, "acro_store_0", "acro_zero_1"),
        },
        "same_write_query_construction": True,
    }


def _train(memory: ContextualStrategyMemory, tasks, scores, *, phases=("train",)):
    for task in tasks:
        if task.phase in phases:
            _run_task(memory, task, unit=scores[task.task_id]["unit"], update=True)
    return memory


def _first_free(memory, task, unit):
    _observe(memory, task)
    available = [variant for variant in VARIANTS]
    ranks = memory.rank_table(available, task.context)
    chosen = memory.choose(tuple(available), task.context)
    neighbors = memory.retrieval_trace(k=6)
    return {
        "task_id": task.task_id,
        "choice": chosen.fingerprint,
        "choice_unit": float(unit[chosen]),
        "oracle": max(unit.values()),
        "first_free_regret": max(unit.values()) - float(unit[chosen]),
        "ranks": ranks[:4],
        "neighbors": neighbors,
        "descriptor_dim": int(memory._descriptor.shape[0]) if memory._descriptor is not None else 0,
    }


def _unit_table(task: DecideTask, seed: int) -> dict:
    raw = raw_catalogue_scores(task, seed)
    scale = FrozenRevealedScale(raw)
    return {variant: scale.unit(raw[variant]) for variant in VARIANTS}


def causal_observation_intervention(tasks, scores, seed: int = 7, *, modes=("support", "obs", "combined"), selector: str = "ucb") -> dict:
    """Change only the planning observation. Support, weights, store, RNG stay fixed."""
    stored = next(task for task in tasks if task.task_id == "acro_store_0")
    zero_obs = np.zeros(stored.context.obs_dim, dtype=np.float32)
    rng = np.random.default_rng(seed + 19)
    shuffled = np.asarray(stored.obs, dtype=np.float64).copy()
    rng.shuffle(shuffled)
    replaced = rng.normal(0.0, float(np.std(stored.obs) + 1e-6), size=stored.obs.shape).astype(np.float32)
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

    def _select(memory, obs, label: str):
        clone = memory.eval_clone(local_updates=False)
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
        available = list(VARIANTS)
        choice = clone.choose(tuple(available), probe.context)
        return {
            "task_id": probe.task_id,
            "choice": choice.fingerprint,
            "obs_norm": float(np.linalg.norm(obs)),
            "stored_landscape_unit": float(stored_unit[choice]),
            "zero_landscape_unit": float(zero_unit[choice]),
            "neighbors": clone.retrieval_trace(k=6),
            "ranks": clone.rank_table(available, probe.context)[:4],
            "descriptor_dim": int(clone._descriptor.shape[0]) if clone._descriptor is not None else 0,
        }

    payload = {}
    for mode in ("support", "obs", "combined"):
        memory = ContextualStrategyMemory(seed=seed, retrieve=True, persist_memory=True, mode=mode, selector=selector)
        _train(memory, tasks, scores)
        stored_q = _select(memory, stored.obs, f"{mode}_stored")
        zero_q = _select(memory, zero_obs, f"{mode}_zero")
        shuffle_q = _select(memory, shuffled, f"{mode}_shuffle")
        replace_q = _select(memory, replaced, f"{mode}_replace")
        payload[mode] = {
            "stored_obs": stored_q,
            "zero_obs": zero_q,
            "shuffled_obs": shuffle_q,
            "replaced_obs": replace_q,
            "choice_changes_with_zero_obs": stored_q["choice"] != zero_q["choice"],
            "neighbors_change_with_zero_obs": stored_q["neighbors"] != zero_q["neighbors"],
            "zero_query_better_on_zero_landscape": zero_q["zero_landscape_unit"] > stored_q["zero_landscape_unit"],
            "stored_query_not_worse_on_stored_landscape": stored_q["stored_landscape_unit"]
            >= zero_q["stored_landscape_unit"] - 1e-12,
            "shuffle_worse_or_equal_zero_landscape": shuffle_q["zero_landscape_unit"]
            <= zero_q["zero_landscape_unit"] + 1e-12,
        }
    return payload


def make_heldout_tasks() -> tuple[DecideTask, ...]:
    """Independent synthetic/val fixtures. Not the locked eight-task set."""
    from nexus.core.strategy_memory_decide_bench import _task

    def _val(family: str, bundle: int, index: int, task_id: str, phase: str) -> DecideTask:
        data = np.load(SOURCE_ROOT / family / f"bundle{bundle}_val.npz")
        support = support_from_arrays(data["obs"], data["action"], data["next_obs"], n=32)
        obs = np.asarray(data["obs"][index], dtype=np.float32)
        return _task(task_id, phase, family, 80 + bundle, support, obs)

    acro_ctx = family_context("acrobot")
    pend_ctx = family_context("pendulum")
    return (
        _val("pendulum", 0, 40, "hold_pend_val0", "heldout_stored"),
        _val("acrobot", 0, 40, "hold_acro_val0", "heldout_stored"),
        _task(
            "hold_acro_small",
            "heldout_shift",
            "acrobot",
            88,
            near_zero_support(acro_ctx, 99),
            (0.04 * np.ones(reviewed_binding("acrobot").obs_dim)).astype(np.float32),
        ),
        _task(
            "hold_pend_zero",
            "heldout_shift",
            "pendulum",
            89,
            near_zero_support(pend_ctx, 101),
            np.zeros(reviewed_binding("pendulum").obs_dim, dtype=np.float32),
        ),
    )


def _summarize(rows):
    return {
        "best_regret": float(np.mean([row["regret"] for row in rows])),
        "first_free_regret": float(np.mean([row["first_free_regret"] for row in rows])),
        "evals_to_strong": float(np.mean([row["evals_to_strong"] for row in rows])),
        "first_free": [row["first_free"] for row in rows],
        "task_ids": [row["task_id"] for row in rows],
    }


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
    diagnosis = descriptor_diagnosis(tasks)
    methods = make_methods(seed)
    configs = make_descriptor_configs(seed)
    methods.update(configs)
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
    causal = causal_observation_intervention(tasks, scores, seed)
    heldout_tasks = make_heldout_tasks()
    heldout_scores = _score_tables(heldout_tasks, seed + 3)
    heldout_methods = make_methods(seed + 3)
    heldout_methods.update(make_descriptor_configs(seed + 3))
    heldout_rows = {name: [] for name in heldout_methods}
    for task in list(tasks) + list(heldout_tasks):
        table = scores.get(task.task_id) or heldout_scores[task.task_id]
        update = task.task_id in scores
        for name, method in heldout_methods.items():
            if task.task_id in scores:
                _run_task(method, task, unit=table["unit"], update=True)
            else:
                heldout_rows[name].append(_run_task(method, task, unit=table["unit"], update=update))
    heldout = {name: _summarize(heldout_rows[name]) for name in heldout_methods}
    persist = summary["persistent_adaptive"]
    combined = summary["memory_combined"]
    support = summary["memory_support"]
    decision = {
        "combined_beats_persist_shifted_first_free": combined["shifted"]["first_free_regret"]
        < persist["shifted"]["first_free_regret"],
        "combined_not_worse_stored_dev_first_free": combined["development"]["first_free_regret"]
        <= persist["development"]["first_free_regret"] + 1e-9,
        "combined_beats_support_shifted_first_free": combined["shifted"]["first_free_regret"]
        < support["shifted"]["first_free_regret"],
        "causal_combined_choice_changes": causal["combined"]["choice_changes_with_zero_obs"],
        "causal_combined_better_on_zero": causal["combined"]["zero_query_better_on_zero_landscape"],
        "causal_support_choice_stable": not causal["support"]["choice_changes_with_zero_obs"],
    }
    decision["development_success"] = bool(
        decision["combined_beats_persist_shifted_first_free"]
        and decision["combined_not_worse_stored_dev_first_free"]
        and decision["causal_combined_choice_changes"]
        and decision["causal_combined_better_on_zero"]
    )
    if causal["combined"]["neighbors_change_with_zero_obs"] and not causal["combined"]["choice_changes_with_zero_obs"]:
        failure_source = "strategy_value_prediction"
    elif diagnosis["focus"]["collision_vs_stored_combined"]["kernel_weight"] > 0.5:
        failure_source = "retrieval_similarity"
    elif not causal["combined"]["neighbors_change_with_zero_obs"]:
        failure_source = "inadequate_observation_information"
    else:
        failure_source = "insufficient_task_coverage"
    decision["failure_source"] = failure_source
    decision["observation_information_separates"] = (
        diagnosis["focus"]["collision_vs_stored_combined"]["distance"]
        > diagnosis["focus"]["collision_vs_stored_support"]["distance"]
    )
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
        "descriptor_diagnosis": diagnosis,
        "summary": summary,
        "rows": {name: {phase: rows[name][phase] for phase in phases} for name in methods},
        "retrieval_traces": traces,
        "causal_observation_intervention": causal,
        "heldout_separate": True,
        "heldout": heldout,
        "heldout_task_ids": [task.task_id for task in heldout_tasks],
        "decision": decision,
        "oracle_by_task": {task_id: table["oracle_variant"] for task_id, table in scores.items()},
        "wall_s": wall,
        "cpu_s": cpu,
        "memory_records": methods["memory_combined"].memory_state(),
        "note": "Observation-aware development bench, not a scientific result and not AGI.",
    }


def write_artifact(seed: int = 7) -> dict:
    payload = run_benchmark(seed)
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
