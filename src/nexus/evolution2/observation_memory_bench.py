"""E2.22 source-only observation-memory screen. Not science.

Reuses the six-proposal / four-free-slot decide() contract, FakeStepModel
proxy scores, E2.8 arrays, and Evolution-2 methods. No collection.
Does not load E2.17 science arrays or consume a new grant.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from nexus.core.strategy_memory_decide_bench import (
    FREE_SLOTS,
    PROPOSALS,
    SCIENCE_ARRAYS,
    STRONG,
    DecideTask,
    family_context,
    make_tasks,
    raw_catalogue_scores,
    support_from_source,
)
from nexus.evolution1.catalogue import digest
from nexus.evolution1.toy_loop import ANCHORS, TrainingFeedback, VARIANTS
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.bindings import reviewed_binding
from nexus.evolution2.methods import make_methods
from nexus.evolution2.observation_memory import (
    ObservationAwareAdaptive,
    calibrate_from_source,
    fit_family_normalizers,
    make_observation_methods,
    support_digest,
)
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator
from nexus.evolution2.persist_reset_science import FrozenRevealedScale
from nexus.evolution2.planner_adapter import FakeStepModel
from nexus.evolution2.screen import SHARED_PROBES, feedback_event

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_22_observation_memory.json"
PHASES = ("train", "development", "shifted", "collision")


def _task(task_id: str, phase: str, family: str, bundle_id: int, support, obs, *, expected_failure: bool = False) -> DecideTask:
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


def make_e222_tasks(normalizers) -> tuple[DecideTask, ...]:
    locked = make_tasks()
    pend_far = _task(
        "pend_far_2",
        "shifted",
        "pendulum",
        22,
        support_from_source("pendulum", 2),
        normalizers["pendulum"].far_observation(),
    )
    acro_far = _task(
        "acro_far_1",
        "shifted",
        "acrobot",
        23,
        support_from_source("acrobot", 1),
        normalizers["acrobot"].far_observation(),
    )
    return locked + (pend_far, acro_far)


def _observe(method, task: DecideTask) -> None:
    if isinstance(method, ObservationAwareAdaptive):
        method.observe(
            task.family,
            task.obs,
            task.context,
            provenance=f"e28:{task.family}:bundle{task.bundle_id}:{task.task_id}",
            support_digest=support_digest(task.support),
        )


def _run_task(method, task: DecideTask, *, unit: dict, update: bool):
    _observe(method, task)
    if getattr(method, "resets", False):
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
    traces = []
    for slot in range(PROPOSALS):
        if slot < SHARED_PROBES:
            variant = next(item for item in available if item.fingerprint == ANCHORS[slot].fingerprint)
            traces.append({"slot": slot, "action": "anchor", "choice": variant.fingerprint})
        else:
            variant = method.choose(tuple(available), task.context)
            if first_free is None:
                first_free = variant
            traces.append(getattr(method, "last_decision", lambda: {"action": "proposer", "choice": variant.fingerprint})())
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
    fallbacks = sum(1 for row in traces if row.get("action") == "fallback")
    retrieves = sum(1 for row in traces if row.get("action") == "retrieve")
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
        "fallbacks": fallbacks,
        "retrieves": retrieves,
        "score_source": "decide_fake_step_model_proxy",
    }


def _mean(rows, key):
    values = [row[key] for row in rows if row.get(key) is not None]
    return float(sum(values) / len(values)) if values else 0.0


def _causal_obs_only(method: ObservationAwareAdaptive, tasks, scores) -> dict:
    for task in tasks:
        if task.phase != "train":
            continue
        _run_task(method, task, unit=scores[task.task_id]["unit"], update=True)
    probe = next(task for task in tasks if task.task_id == "acro_store_1")
    stored = np.asarray(probe.obs, dtype=np.float32)
    zero = np.zeros_like(stored)
    far = method.normalizers[probe.family].far_observation()
    out = {}
    available = list(VARIANTS)
    for name, obs in (("stored", stored), ("zero", zero), ("far", far)):
        method.observe(probe.family, obs, probe.context, provenance="causal_obs_only", support_digest=support_digest(probe.support))
        choice = method.choose(tuple(available), probe.context)
        trace = method.last_decision()
        out[name] = {
            "choice": choice.fingerprint,
            "action": trace.get("action"),
            "confidence": trace.get("confidence"),
            "nearest": trace.get("nearest"),
            "fallback": trace.get("fallback"),
        }
    out["changed_zero"] = out["stored"]["choice"] != out["zero"]["choice"] or out["stored"]["action"] != out["zero"]["action"]
    out["changed_far"] = out["stored"]["choice"] != out["far"]["choice"] or out["stored"]["action"] != out["far"]["action"]
    out["same_memory_records"] = True
    out["same_weights"] = True
    return out


def run_benchmark(seed: int = 7) -> dict:
    if grant.grant_unused():
        raise RuntimeError("e217_grant_must_stay_consumed")
    if SCIENCE_ARRAYS.is_dir() and any(SCIENCE_ARRAYS.rglob("*.npz")):
        pass
    started = time.perf_counter()
    cpu0 = time.process_time()
    normalizers = fit_family_normalizers()
    calibration = calibrate_from_source(normalizers, seed=seed)
    tasks = make_e222_tasks(normalizers)
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
        }
    methods = make_methods(seed)
    methods.pop("fixed")
    methods.update(make_observation_methods(seed, normalizers, calibration))
    causal_method = make_observation_methods(seed + 1, normalizers, calibration)["observation_aware_memory"]
    rows = {name: {phase: [] for phase in PHASES} for name in methods}
    for task in tasks:
        unit = score_tables[task.task_id]["unit"]
        for name, method in methods.items():
            rows[name][task.phase].append(_run_task(method, task, unit=unit, update=True))
    lookups = {name: sum(len(block) * PROPOSALS for block in rows[name].values()) for name in methods}
    if len(set(lookups.values())) != 1:
        raise RuntimeError("unmatched_lookup_budget")
    causal = _causal_obs_only(causal_method, tasks, score_tables)
    summary = {}
    for name in methods:
        block = rows[name]
        summary[name] = {
            "train_regret": _mean(block["train"], "regret"),
            "dev_regret": _mean(block["development"], "regret"),
            "shifted_regret": _mean(block["shifted"], "regret"),
            "collision_regret": _mean(block["collision"], "regret"),
            "dev_first_free_regret": _mean(block["development"], "first_free_regret"),
            "shifted_first_free_regret": _mean(block["shifted"], "first_free_regret"),
            "collision_first_free_regret": _mean(block["collision"], "first_free_regret"),
            "dev_best": _mean(block["development"], "best"),
            "shifted_best": _mean(block["shifted"], "best"),
            "dev_retrieves": _mean(block["development"], "retrieves"),
            "shifted_fallbacks": _mean(block["shifted"], "fallbacks"),
            "dev_fallbacks": _mean(block["development"], "fallbacks"),
            "shifted_retrieves": _mean(block["shifted"], "retrieves"),
        }
    memory = summary["observation_aware_memory"]
    persist = summary["persistent_adaptive"]
    reset = summary["reset_adaptive"]
    ungated = summary["observation_ungated_memory"]
    shuffled = summary["observation_shuffled_memory"]
    wall = time.perf_counter() - started
    cpu = time.process_time() - cpu0
    familiar_ok = memory["dev_first_free_regret"] <= persist["dev_first_free_regret"] + 1e-12
    shift_better = memory["shifted_first_free_regret"] < persist["shifted_first_free_regret"] - 1e-12
    not_global_fallback = memory["dev_retrieves"] > 0
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
        "score_source": "decide_fake_step_model_proxy",
        "score_is_real_control": False,
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "seed": seed,
        "matched_proposals": PROPOSALS,
        "free_slots": FREE_SLOTS,
        "anchors": SHARED_PROBES,
        "calibration": {
            "kernel_length": calibration.kernel_length,
            "gate_threshold": calibration.gate_threshold,
            "pairwise_median": calibration.pairwise_median,
            "source_nn_p75": calibration.source_nn_p75,
            "n_obs": calibration.n_obs,
            "fit_bundles": list(normalizers),
            "far_sigma": 4.0,
        },
        "lookups": lookups,
        "summary": summary,
        "rows": {name: {phase: rows[name][phase] for phase in PHASES} for name in methods},
        "oracle_by_task": {task_id: table["oracle_variant"] for task_id, table in score_tables.items()},
        "causal_observation_only": causal,
        "decision": {
            "preserves_familiar": familiar_ok,
            "improves_shifted_vs_persist": shift_better,
            "not_global_fallback": not_global_fallback,
            "beats_ungated_shifted": memory["shifted_first_free_regret"] < ungated["shifted_first_free_regret"],
            "beats_shuffled_shifted": memory["shifted_first_free_regret"] < shuffled["shifted_first_free_regret"],
            "causal_obs_changes_choice_or_gate": causal["changed_zero"] or causal["changed_far"],
            "development_success": familiar_ok and shift_better and not_global_fallback,
            "vs_reset_shifted": memory["shifted_first_free_regret"] - reset["shifted_first_free_regret"],
            "vs_persist_shifted": memory["shifted_first_free_regret"] - persist["shifted_first_free_regret"],
            "vs_persist_dev": memory["dev_first_free_regret"] - persist["dev_first_free_regret"],
        },
        "wall_s": wall,
        "cpu_s": cpu,
        "note": "E2.22 development proxy screen, not a scientific result and not AGI.",
    }


def write_artifact(seed: int = 7) -> dict:
    payload = run_benchmark(seed)
    RESULTS.write_text(json.dumps(payload, indent=2, default=float) + "\n")
    return payload
