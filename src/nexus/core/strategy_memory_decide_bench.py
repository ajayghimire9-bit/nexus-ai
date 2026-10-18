"""Development benchmark: ContextualStrategyMemory vs persist/reset on decide() scores.

Uses FakeStepModel returns owned by fixture_hidden_return. Six matched
proposals per task (two anchors + four free). No collection. Not science.
Does not reuse E2.17 development as confirmation.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nexus.core.strategy_memory import (
    ContextualStrategyMemory,
    SupportBatch,
    describe_support,
    make_memory_pair,
    support_from_arrays,
)
from nexus.evolution1.catalogue import digest
from nexus.evolution1.fixtures import PublicFixtureContext
from nexus.evolution1.toy_loop import ANCHORS, TrainingFeedback, VARIANTS
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.bindings import reviewed_binding
from nexus.evolution2.methods import make_methods
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator
from nexus.evolution2.persist_reset_science import FrozenRevealedScale, fixture_hidden_return
from nexus.evolution2.planner_adapter import FakeStepModel
from nexus.evolution2.screen import SHARED_PROBES, feedback_event

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "strategy_memory_decide_bench.json"
SOURCE_ROOT = ROOT / "artifacts" / "evolution2_source_arrays"
SCIENCE_ARRAYS = ROOT / "artifacts" / "evolution2_persist_reset_science_arrays"
PROPOSALS = 6
FREE_SLOTS = PROPOSALS - SHARED_PROBES
STRONG = 0.95


@dataclass(frozen=True)
class DecideTask:
    task_id: str
    phase: str
    family: str
    bundle_id: int
    context: PublicFixtureContext
    support: SupportBatch
    obs: np.ndarray
    model: FakeStepModel
    expected_failure: bool


def family_context(family: str) -> PublicFixtureContext:
    binding = reviewed_binding(family)
    return PublicFixtureContext(binding.n_actions, binding.obs_dim, binding.episode_steps, 1536)


def _load_arrays(family: str, bundle: int, split: str = "train"):
    path = SOURCE_ROOT / family / f"bundle{bundle}_{split}.npz"
    if not path.is_file():
        raise RuntimeError("permitted_source_array_missing")
    if SCIENCE_ARRAYS in path.parents or "persist_reset_science" in str(path):
        raise RuntimeError("e217_science_arrays_forbidden")
    return np.load(path)


def support_from_source(family: str, bundle: int, *, start: int = 0, n: int = 32) -> SupportBatch:
    data = _load_arrays(family, bundle)
    return support_from_arrays(data["obs"][start:], data["action"][start:], data["next_obs"][start:], n=n)


def obs_from_source(family: str, bundle: int, index: int = 64) -> np.ndarray:
    data = _load_arrays(family, bundle)
    return np.asarray(data["obs"][index], dtype=np.float32)


def near_zero_support(context: PublicFixtureContext, seed: int, n: int = 32) -> SupportBatch:
    rng = np.random.default_rng(int(seed))
    obs = rng.normal(0.0, 0.02, size=(n, context.obs_dim)).astype(np.float64)
    action = rng.integers(0, context.n_actions, size=n)
    nxt = obs.copy()
    nxt[:, 0] = nxt[:, 0] + 0.01 * (action.astype(np.float64) - (context.n_actions - 1) / 2.0)
    reward = -np.mean(obs * obs, axis=1)
    return SupportBatch(obs, action, nxt, reward)


def _task(task_id: str, phase: str, family: str, bundle_id: int, support: SupportBatch, obs, *, expected_failure: bool = False) -> DecideTask:
    binding = reviewed_binding(family)
    return DecideTask(
        task_id,
        phase,
        family,
        bundle_id,
        family_context(family),
        support,
        np.asarray(obs, dtype=np.float32),
        FakeStepModel(binding.obs_dim, binding.n_actions),
        expected_failure,
    )


def make_tasks() -> tuple[DecideTask, ...]:
    return (
        _task("pend_store_0", "train", "pendulum", 0, support_from_source("pendulum", 0), obs_from_source("pendulum", 0)),
        _task("acro_store_0", "train", "acrobot", 0, support_from_source("acrobot", 0), obs_from_source("acrobot", 0)),
        _task("pend_store_1", "train", "pendulum", 1, support_from_source("pendulum", 1), obs_from_source("pendulum", 1)),
        _task(
            "acro_zero_0",
            "train",
            "acrobot",
            10,
            near_zero_support(family_context("acrobot"), 10),
            np.zeros(reviewed_binding("acrobot").obs_dim, dtype=np.float32),
        ),
        _task("pend_store_2", "development", "pendulum", 2, support_from_source("pendulum", 2), obs_from_source("pendulum", 2)),
        _task("acro_store_1", "development", "acrobot", 1, support_from_source("acrobot", 1), obs_from_source("acrobot", 1)),
        _task(
            "acro_zero_1",
            "shifted",
            "acrobot",
            11,
            near_zero_support(family_context("acrobot"), 11),
            np.zeros(reviewed_binding("acrobot").obs_dim, dtype=np.float32),
        ),
        _task(
            "acro_zero_collision",
            "collision",
            "acrobot",
            12,
            support_from_source("acrobot", 2),
            np.zeros(reviewed_binding("acrobot").obs_dim, dtype=np.float32),
            expected_failure=True,
        ),
    )


def raw_catalogue_scores(task: DecideTask, seed: int) -> dict:
    return {
        variant: fixture_hidden_return(task.family, variant, task.model, task.obs, seed=int(seed))
        for variant in VARIANTS
    }


def _observe(method, task: DecideTask):
    if isinstance(method, ContextualStrategyMemory):
        method.observe_support(task.support, task.context, planning_obs=task.obs)
    elif hasattr(method, "observe_planning_obs"):
        method.observe_planning_obs(task.obs, task.context)


def _run_task(method, task: DecideTask, *, unit: dict, update: bool):
    _observe(method, task)
    if getattr(method, "resets", False):
        method.reset_task()
        _observe(method, task)
    if isinstance(method, ContextualStrategyMemory) and not method.persist_memory:
        method.reset_task()
        _observe(method, task)
    evaluator = TrustedEvaluator(
        VARIANTS,
        family=task.family,
        bundle_id=task.bundle_id,
        produce_score=lambda variant, unit=unit: float(unit[variant]),
    )
    available = list(VARIANTS)
    records = []
    first_free = None
    for slot in range(PROPOSALS):
        if slot < SHARED_PROBES:
            variant = next(item for item in available if item.fingerprint == ANCHORS[slot].fingerprint)
        else:
            variant = method.choose(tuple(available), task.context)
            if first_free is None:
                first_free = variant
        score = evaluator.evaluate(method.name, variant, family=task.family, bundle_id=task.bundle_id)
        if update:
            method.update(
                TrainingFeedback(variant.fingerprint, score, False, feedback_event(task, slot, variant.fingerprint)),
                task.context,
            )
        records.append((slot, variant, score))
        available.remove(variant)
    oracle = max(unit.values())
    best = max(row[2] for row in records)
    strong = next((row[0] + 1 for row in records if row[2] >= STRONG), PROPOSALS)
    return {
        "task_id": task.task_id,
        "family": task.family,
        "phase": task.phase,
        "expected_failure": task.expected_failure,
        "best": best,
        "regret": oracle - best,
        "oracle": oracle,
        "first_free": None if first_free is None else first_free.fingerprint,
        "first_free_score": None if first_free is None else float(unit[first_free]),
        "first_free_regret": None if first_free is None else oracle - float(unit[first_free]),
        "evals_to_strong": strong,
        "variants": [row[1].fingerprint for row in records],
        "scores": [row[2] for row in records],
        "physical": evaluator.physical,
        "charged": evaluator.charged,
        "score_source": "decide_fake_step_model",
    }


def _mean(rows, key):
    values = [row[key] for row in rows if row.get(key) is not None]
    return float(sum(values) / len(values)) if values else 0.0


def causal_memory_effect(tasks: tuple[DecideTask, ...], scores: dict, seed: int) -> dict:
    memory = ContextualStrategyMemory(seed=seed, retrieve=True, persist_memory=True)
    for task in tasks:
        if task.phase != "train":
            continue
        _run_task(memory, task, unit=scores[task.task_id]["unit"], update=True)
    probe = next(task for task in tasks if task.phase == "development")
    _observe(memory, probe)
    available = list(VARIANTS)
    with_mem = memory.choose(tuple(available), probe.context, retrieve=True)
    without = memory.choose(tuple(available), probe.context, retrieve=False)
    return {
        "probe": probe.task_id,
        "with_memory": with_mem.fingerprint,
        "without_memory": without.fingerprint,
        "changed": with_mem.fingerprint != without.fingerprint,
        "same_weights": True,
        "same_seed": True,
        "same_support": True,
        "score_source": "decide_fake_step_model",
    }


def run_benchmark(seed: int = 7) -> dict:
    if grant.grant_unused():
        raise RuntimeError("e217_grant_must_stay_consumed")
    if SCIENCE_ARRAYS.is_dir() and any(SCIENCE_ARRAYS.rglob("*.npz")):
        # Presence is allowed; this runner must not load those files.
        pass
    started = time.perf_counter()
    cpu0 = time.process_time()
    tasks = make_tasks()
    if FREE_SLOTS <= 2:
        raise RuntimeError("need_more_than_two_free_slots")
    score_tables = {}
    for task in tasks:
        raw = raw_catalogue_scores(task, seed + int(digest(task.task_id)[:8], 16) % 1000)
        scale = FrozenRevealedScale(raw)
        score_tables[task.task_id] = {
            "raw": {variant.fingerprint: raw[variant] for variant in VARIANTS},
            "unit": {variant: scale.unit(raw[variant]) for variant in VARIANTS},
            "oracle_variant": max(VARIANTS, key=lambda variant: raw[variant]).fingerprint,
            "scale_lo": scale.lo,
            "scale_hi": scale.hi,
            "expected_failure": task.expected_failure,
        }
    methods = make_methods(seed)
    pair = make_memory_pair(seed)
    methods["contextual_strategy_memory"] = pair["memory"]
    methods["memory_ablated"] = pair["memory_ablated"]
    phases = ("train", "development", "shifted", "collision")
    rows = {name: {phase: [] for phase in phases} for name in methods}
    for task in tasks:
        unit = score_tables[task.task_id]["unit"]
        for name, method in methods.items():
            rows[name][task.phase].append(_run_task(method, task, unit=unit, update=True))
    lookups = {name: sum(len(block) * PROPOSALS for block in rows[name].values()) for name in methods}
    if len(set(lookups.values())) != 1:
        raise RuntimeError("unmatched_lookup_budget")
    causal = causal_memory_effect(tasks, score_tables, seed)
    summary = {}
    for name in methods:
        summary[name] = {
            "train_regret": _mean(rows[name]["train"], "regret"),
            "dev_regret": _mean(rows[name]["development"], "regret"),
            "shifted_regret": _mean(rows[name]["shifted"], "regret"),
            "collision_regret": _mean(rows[name]["collision"], "regret"),
            "dev_evals_to_strong": _mean(rows[name]["development"], "evals_to_strong"),
            "shifted_evals_to_strong": _mean(rows[name]["shifted"], "evals_to_strong"),
            "collision_evals_to_strong": _mean(rows[name]["collision"], "evals_to_strong"),
            "dev_first_free_score": _mean(rows[name]["development"], "first_free_score"),
            "dev_first_free_regret": _mean(rows[name]["development"], "first_free_regret"),
            "shifted_first_free_regret": _mean(rows[name]["shifted"], "first_free_regret"),
            "collision_first_free_regret": _mean(rows[name]["collision"], "first_free_regret"),
        }
    memory = summary["contextual_strategy_memory"]
    persist = summary["persistent_adaptive"]
    reset = summary["reset_adaptive"]
    ablated = summary["memory_ablated"]
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
        "anchors": SHARED_PROBES,
        "lookups": lookups,
        "summary": summary,
        "rows": {name: {phase: rows[name][phase] for phase in phases} for name in methods},
        "oracle_by_task": {task_id: table["oracle_variant"] for task_id, table in score_tables.items()},
        "causal_memory_changes_choice": causal,
        "negative_transfer_collision_memory_minus_ablated_regret": memory["collision_regret"] - ablated["collision_regret"],
        "memory_improves_dev_selection": memory["dev_regret"] < min(persist["dev_regret"], reset["dev_regret"], ablated["dev_regret"]),
        "memory_improves_dev_first_free": memory["dev_first_free_regret"]
        < min(persist["dev_first_free_regret"], reset["dev_first_free_regret"], ablated["dev_first_free_regret"]),
        "expected_failure": {
            "task": "acro_zero_collision",
            "reason": "stored-acrobot support with zero-obs decide() landscape; successor-16 wins, flat-4 memories mislead",
        },
        "permitted_descriptor": {
            "available": True,
            "dim": int(describe_support(tasks[0].support, tasks[0].context).shape[0]),
            "finite": bool(np.all(np.isfinite(describe_support(tasks[0].support, tasks[0].context)))),
        },
        "wall_s": wall,
        "cpu_s": cpu,
        "memory_records": methods["contextual_strategy_memory"].memory_state()["records"],
        "note": "Development decide() benchmark, not a scientific result and not AGI.",
    }


def write_artifact(seed: int = 7) -> dict:
    payload = run_benchmark(seed)
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
