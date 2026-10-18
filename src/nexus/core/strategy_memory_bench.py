"""Development benchmark for ContextualStrategyMemory. Not science.

Uses synthetic Evolution-2 families and permitted source arrays only.
Does not collect, name a holdout, or consume the E2.17 grant.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from nexus.core.strategy_memory import (
    ContextualStrategyMemory,
    describe_support,
    make_memory_pair,
    support_from_arrays,
    synthetic_support,
)
from nexus.evolution1.catalogue import digest
from nexus.evolution1.toy_loop import ANCHORS, TrainingFeedback, VARIANTS
from nexus.evolution2.methods import make_methods
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator
from nexus.evolution2.screen import SHARED_PROBES, feedback_event
from nexus.evolution2.tasks import HOLDOUT_FAMILY, PROPOSALS, SHIFTED_FAMILY, default_split, hidden_score, oracle_best
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "strategy_memory_bench.json"
SOURCE_ARRAY = ROOT / "artifacts" / "evolution2_source_arrays" / "pendulum" / "bundle0_train.npz"
CONTROLS = ("persistent_adaptive", "reset_adaptive", "random", "evolutionary")


def _observe(method, task, seed: int):
    if isinstance(method, ContextualStrategyMemory):
        task_seed = seed + int(digest(task.task_id)[:8], 16) % 10_000
        method.observe_support(synthetic_support(task.context, task_seed), task.context)


def _run_task(method, task, *, seed: int, update: bool):
    _observe(method, task, seed)
    if getattr(method, "resets", False):
        method.reset_task()
        _observe(method, task, seed)
    if isinstance(method, ContextualStrategyMemory) and not method.persist_memory:
        method.reset_task()
        _observe(method, task, seed)
    evaluator = TrustedEvaluator(
        VARIANTS,
        family=task.family,
        bundle_id=task.instance,
        produce_score=lambda variant, task=task: hidden_score(task, variant),
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
        score = evaluator.evaluate(method.name, variant, family=task.family, bundle_id=task.instance)
        receipt = TrainingFeedback(variant.fingerprint, score, False, feedback_event(task, slot, variant.fingerprint))
        if update:
            method.update(receipt, task.context)
        records.append((slot, variant, score))
        available.remove(variant)
    best = max(row[2] for row in records)
    oracle_id, oracle = oracle_best(task)
    strong = next((row[0] + 1 for row in records if row[2] >= oracle - 0.05), PROPOSALS)
    return {
        "task_id": task.task_id,
        "family": task.family,
        "best": best,
        "mean": sum(row[2] for row in records) / len(records),
        "regret": oracle - best,
        "oracle": oracle,
        "oracle_id": oracle_id,
        "first_free": None if first_free is None else first_free.fingerprint,
        "first_free_score": None if first_free is None else hidden_score(task, first_free),
        "evals_to_strong": strong,
        "variants": [row[1].fingerprint for row in records],
        "scores": [row[2] for row in records],
    }


def _mean(rows, key):
    return float(sum(row[key] for row in rows) / len(rows)) if rows else 0.0


def causal_memory_effect(seed: int = 7) -> dict:
    split = default_split()
    memory = ContextualStrategyMemory(seed=seed, retrieve=True, persist_memory=True)
    for task in split["train"]:
        _run_task(memory, task, seed=seed, update=True)
    probe = split["development"][0]
    _observe(memory, probe, seed)
    available = [v for v in VARIANTS]
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
    }


def permitted_descriptor_smoke() -> dict:
    if not SOURCE_ARRAY.is_file():
        return {"available": False}
    data = np.load(SOURCE_ARRAY)
    from nexus.evolution1.fixtures import PublicFixtureContext

    context = PublicFixtureContext(3, 3, 1, 1536)
    support = support_from_arrays(data["obs"], data["action"], data["next_obs"])
    desc = describe_support(support, context)
    return {"available": True, "path": str(SOURCE_ARRAY.relative_to(ROOT)), "dim": int(desc.shape[0]), "finite": bool(np.all(np.isfinite(desc)))}


def run_benchmark(seed: int = 7) -> dict:
    if grant.grant_unused():
        raise RuntimeError("e217_grant_must_stay_consumed")
    started = time.perf_counter()
    cpu0 = time.process_time()
    split = default_split()
    if any(task.family == HOLDOUT_FAMILY for task in split["train"] + split["development"] + split["shifted"]):
        raise RuntimeError("holdout_family_consumed")
    methods = make_methods(seed)
    pair = make_memory_pair(seed)
    methods["contextual_strategy_memory"] = pair["memory"]
    methods["memory_ablated"] = pair["memory_ablated"]
    phases = {
        "train": split["train"],
        "development": split["development"],
        "shifted": split["shifted"],
    }
    rows = {name: {phase: [] for phase in phases} for name in methods}
    for phase, tasks in phases.items():
        for task in tasks:
            for name, method in methods.items():
                rows[name][phase].append(_run_task(method, task, seed=seed, update=True))
    lookups = {name: sum(len(block) * PROPOSALS for block in rows[name].values()) for name in methods}
    if len(set(lookups.values())) != 1:
        raise RuntimeError("unmatched_lookup_budget")
    causal = causal_memory_effect(seed)
    summary = {}
    for name in methods:
        summary[name] = {
            "train_regret": _mean(rows[name]["train"], "regret"),
            "dev_regret": _mean(rows[name]["development"], "regret"),
            "shifted_regret": _mean(rows[name]["shifted"], "regret"),
            "train_evals_to_strong": _mean(rows[name]["train"], "evals_to_strong"),
            "dev_evals_to_strong": _mean(rows[name]["development"], "evals_to_strong"),
            "shifted_evals_to_strong": _mean(rows[name]["shifted"], "evals_to_strong"),
            "dev_first_free_score": _mean(
                [row for row in rows[name]["development"] if row["first_free_score"] is not None],
                "first_free_score",
            ),
            "shifted_first_free_score": _mean(
                [row for row in rows[name]["shifted"] if row["first_free_score"] is not None],
                "first_free_score",
            ),
        }
        summary[name]["dev_first_free_regret"] = float(
            sum(row["oracle"] - row["first_free_score"] for row in rows[name]["development"] if row["first_free_score"] is not None)
            / max(1, len(rows[name]["development"]))
        )
        summary[name]["shifted_first_free_regret"] = float(
            sum(row["oracle"] - row["first_free_score"] for row in rows[name]["shifted"] if row["first_free_score"] is not None)
            / max(1, len(rows[name]["shifted"]))
        )
    memory = summary["contextual_strategy_memory"]
    persist = summary["persistent_adaptive"]
    reset = summary["reset_adaptive"]
    ablated = summary["memory_ablated"]
    negative = memory["shifted_regret"] - ablated["shifted_regret"]
    improved_dev = memory["dev_regret"] < min(persist["dev_regret"], reset["dev_regret"], ablated["dev_regret"])
    wall = time.perf_counter() - started
    cpu = time.process_time() - cpu0
    return {
        "scientific": False,
        "collection": False,
        "env_steps": 0,
        "claims_agi": False,
        "claims_learning_to_learn": False,
        "historical_e217_label": "inconclusive",
        "grant_consumed": True,
        "holdout_family_untouched": HOLDOUT_FAMILY,
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "seed": seed,
        "matched_proposals": PROPOSALS,
        "lookups": lookups,
        "summary": summary,
        "rows": {name: {phase: rows[name][phase] for phase in phases} for name in methods},
        "causal_memory_changes_choice": causal,
        "negative_transfer_shifted_memory_minus_ablated_regret": negative,
        "memory_improves_dev_selection": improved_dev,
        "permitted_descriptor": permitted_descriptor_smoke(),
        "wall_s": wall,
        "cpu_s": cpu,
        "memory_records": methods["contextual_strategy_memory"].memory_state()["records"],
        "expected_failure": {
            "family": SHIFTED_FAMILY,
            "reason": "same public context as successor_scale, inverted hidden scores",
        },
        "note": "Synthetic development benchmark, not a scientific result and not AGI.",
    }


def write_artifact(seed: int = 7) -> dict:
    payload = run_benchmark(seed)
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
