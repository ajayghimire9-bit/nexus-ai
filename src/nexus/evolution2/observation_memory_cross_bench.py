"""E2.23 source-only cross-bundle calibration screen. Not science.

Freezes leave-one-bundle-out thresholds before the E2.22 development
tasks. Does not use those task scores to set the gate. No collection.
Does not load E2.17 science arrays.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from nexus.core.strategy_memory_decide_bench import FREE_SLOTS, PROPOSALS, SCIENCE_ARRAYS
from nexus.evolution1.catalogue import digest
from nexus.evolution1.toy_loop import VARIANTS
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.methods import make_methods
from nexus.evolution2.observation_memory import (
    calibrate_cross_bundle,
    calibrate_from_source,
    fit_family_normalizers,
    make_cross_bundle_methods,
)
from nexus.evolution2.observation_memory_bench import (
    PHASES,
    _causal_obs_only,
    _mean,
    _run_task,
    make_e222_tasks,
)
from nexus.evolution2.persist_reset_science import FrozenRevealedScale
from nexus.evolution2.screen import SHARED_PROBES
from nexus.core.strategy_memory_decide_bench import raw_catalogue_scores

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_23_cross_bundle_memory.json"


def run_benchmark(seed: int = 7) -> dict:
    if grant.grant_unused():
        raise RuntimeError("e217_grant_must_stay_consumed")
    if SCIENCE_ARRAYS.is_dir() and any(SCIENCE_ARRAYS.rglob("*.npz")):
        pass
    started = time.perf_counter()
    cpu0 = time.process_time()
    normalizers = fit_family_normalizers()
    within = calibrate_from_source(normalizers, seed=seed)
    cross = calibrate_cross_bundle(normalizers, seed=seed)
    if not cross.frozen or cross.rule != "cross_bundle_lobo_p95":
        raise RuntimeError("cross_bundle_calibration_not_frozen")
    if cross.extra.get("used_e222_shifted_outcomes"):
        raise RuntimeError("shifted_outcomes_used_for_calibration")
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
        }
    methods = make_methods(seed)
    methods.pop("fixed")
    methods.pop("evolutionary")
    methods.pop("random")
    methods.update(make_cross_bundle_methods(seed, normalizers, within, cross))
    causal = _causal_obs_only(make_cross_bundle_methods(seed + 1, normalizers, within, cross)["observation_cross_bundle"], tasks, score_tables)
    rows = {name: {phase: [] for phase in PHASES} for name in methods}
    for task in tasks:
        unit = score_tables[task.task_id]["unit"]
        for name, method in methods.items():
            rows[name][task.phase].append(_run_task(method, task, unit=unit, update=True))
    lookups = {name: sum(len(block) * PROPOSALS for block in rows[name].values()) for name in methods}
    if len(set(lookups.values())) != 1:
        raise RuntimeError("unmatched_lookup_budget")
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
            "dev_free_regret_sum": float(sum(row["first_free_regret"] for row in block["development"])),
            "shifted_free_regret_sum": float(sum(row["first_free_regret"] for row in block["shifted"])),
            "dev_retrieves": _mean(block["development"], "retrieves"),
            "dev_fallbacks": _mean(block["development"], "fallbacks"),
            "shifted_retrieves": _mean(block["shifted"], "retrieves"),
            "shifted_fallbacks": _mean(block["shifted"], "fallbacks"),
        }
    persist = summary["persistent_adaptive"]
    reset = summary["reset_adaptive"]
    fixed = summary["observation_fixed_gate"]
    cross_row = summary["observation_cross_bundle"]
    ungated = summary["observation_ungated_memory"]
    reset_fb = summary["observation_cross_reset_fallback"]
    familiar_retrieve = cross_row["dev_retrieves"] > 0
    beats_persist_dev = cross_row["dev_first_free_regret"] < persist["dev_first_free_regret"] - 1e-12
    beats_ungated_dev = cross_row["dev_first_free_regret"] < ungated["dev_first_free_regret"] - 1e-12
    beats_ungated_shift = cross_row["shifted_first_free_regret"] < ungated["shifted_first_free_regret"] - 1e-12
    preserves = cross_row["dev_first_free_regret"] <= persist["dev_first_free_regret"] + 1e-12
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
        "used_e222_shifted_outcomes_for_calibration": False,
        "score_source": "decide_fake_step_model_proxy",
        "score_is_real_control": False,
        "development_scenarios_are_confirmation": False,
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "base_sha": "cfc753a0cb86405e39033de067a950a2aeae7a32",
        "seed": seed,
        "matched_proposals": PROPOSALS,
        "free_slots": FREE_SLOTS,
        "anchors": SHARED_PROBES,
        "calibration_within": {
            "rule": within.rule,
            "kernel_length": within.kernel_length,
            "gate_threshold": within.gate_threshold,
        },
        "calibration_cross": {
            "rule": cross.rule,
            "frozen": cross.frozen,
            "kernel_length": cross.kernel_length,
            "gate_threshold": cross.gate_threshold,
            **cross.extra,
        },
        "lookups": lookups,
        "summary": summary,
        "rows": {name: {phase: rows[name][phase] for phase in PHASES} for name in methods},
        "oracle_by_task": {task_id: table["oracle_variant"] for task_id, table in score_tables.items()},
        "causal_observation_only": causal,
        "decision": {
            "cross_retrieves_familiar": familiar_retrieve,
            "preserves_familiar_vs_persist": preserves,
            "beats_persist_familiar": beats_persist_dev,
            "beats_fixed_familiar_retrieve": cross_row["dev_retrieves"] > fixed["dev_retrieves"],
            "beats_ungated_familiar": beats_ungated_dev,
            "beats_ungated_shifted": beats_ungated_shift,
            "beats_persist_shifted": cross_row["shifted_first_free_regret"] < persist["shifted_first_free_regret"] - 1e-12,
            "reset_fallback_vs_persist_fallback_dev": reset_fb["dev_first_free_regret"] - cross_row["dev_first_free_regret"],
            "causal_obs_changes": causal["changed_zero"] or causal["changed_far"],
            "gating_adds_value_vs_ungated": beats_ungated_dev or beats_ungated_shift,
            "development_success": familiar_retrieve and preserves and (beats_persist_dev or beats_ungated_dev or beats_ungated_shift),
            "vs_persist_dev": cross_row["dev_first_free_regret"] - persist["dev_first_free_regret"],
            "vs_ungated_dev": cross_row["dev_first_free_regret"] - ungated["dev_first_free_regret"],
            "vs_reset_dev": cross_row["dev_first_free_regret"] - reset["dev_first_free_regret"],
        },
        "wall_s": wall,
        "cpu_s": cpu,
        "note": "E2.23 development proxy screen, not a scientific result and not AGI.",
    }


def write_artifact(seed: int = 7) -> dict:
    payload = run_benchmark(seed)
    RESULTS.write_text(json.dumps(payload, indent=2, default=float) + "\n")
    return payload
