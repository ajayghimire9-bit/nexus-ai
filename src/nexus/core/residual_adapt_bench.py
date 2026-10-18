"""Select or adapt E2.9 residuals from permitted support. Not science.

One revealed MAE per method per task. Query val MAE is hidden.
Does not load E2.17 science arrays or fits. No collection.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from nexus.core.residual_adapt import (
    ADAPT_STEPS,
    ARMS,
    ResidualMemory,
    adapt_clone,
    load_support,
    prediction_mae,
)
from nexus.core.strategy_memory_decide_bench import SCIENCE_ARRAYS, family_context
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.persist_reset_path import disposable_model

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "residual_adapt_bench.json"
SCIENCE_FITS = ROOT / "artifacts" / "evolution2_persist_reset_science_fits"
SOURCE = ROOT / "artifacts" / "evolution2_source_arrays"
POLICIES = ("default", "random", "persist", "persist_best", "memory")
TASKS = (
    ("pendulum", 0, "train"),
    ("acrobot", 0, "train"),
    ("pendulum", 1, "train"),
    ("acrobot", 1, "train"),
    ("pendulum", 2, "development"),
    ("acrobot", 2, "development"),
)


def _arrays(family: str, bundle: int, split: str):
    path = SOURCE / family / f"bundle{bundle}_{split}.npz"
    if SCIENCE_ARRAYS in path.parents or "persist_reset_science" in str(path):
        raise RuntimeError("e217_science_arrays_forbidden")
    return np.load(path)


def _models(family: str):
    return {arm: disposable_model(family, arm) for arm in ARMS}


def query_table() -> dict:
    table = {}
    for family, bundle, _phase in TASKS:
        val = _arrays(family, bundle, "val")
        models = _models(family)
        maes = {arm: prediction_mae(models[arm], val["obs"], val["action"], val["next_obs"]) for arm in ARMS}
        table[f"{family}:{bundle}"] = {
            "mae": maes,
            "oracle": min(maes, key=maes.get),
            "oracle_mae": maes[min(maes, key=maes.get)],
        }
    return table


def run_benchmark(seed: int = 7) -> dict:
    if grant.grant_unused():
        raise RuntimeError("e217_grant_must_stay_consumed")
    started = time.perf_counter()
    cpu0 = time.process_time()
    hidden = query_table()
    rows = {policy: [] for policy in POLICIES}
    adapted = {policy: [] for policy in POLICIES}
    memories = {policy: ResidualMemory(seed=seed) for policy in POLICIES}
    revealed_evals = {policy: 0 for policy in POLICIES}
    for family, bundle, phase in TASKS:
        context = family_context(family)
        support, desc = load_support(family, bundle, 0, 32, context)
        revealed = _arrays(family, bundle, "train")
        r_obs, r_act, r_nxt = revealed["obs"][32:96], revealed["action"][32:96], revealed["next_obs"][32:96]
        models = _models(family)
        query = hidden[f"{family}:{bundle}"]
        for policy in POLICIES:
            arm = memories[policy].choose(family, desc, policy=policy, explore=phase == "train")
            mae_revealed = prediction_mae(models[arm], r_obs, r_act, r_nxt)
            memories[policy].update(family, desc, arm, mae_revealed)
            revealed_evals[policy] += 1
            mae_query = query["mae"][arm]
            rows[policy].append(
                {
                    "task": f"{family}:{bundle}",
                    "phase": phase,
                    "arm": arm,
                    "revealed_mae": mae_revealed,
                    "query_mae": mae_query,
                    "regret": mae_query - query["oracle_mae"],
                    "oracle": query["oracle"],
                }
            )
            adapted_model = adapt_clone(models[arm], support.obs, support.action, support.next_obs, seed=seed)
            adapt_mae = prediction_mae(adapted_model, _arrays(family, bundle, "val")["obs"], _arrays(family, bundle, "val")["action"], _arrays(family, bundle, "val")["next_obs"])
            adapted[policy].append({"task": f"{family}:{bundle}", "phase": phase, "arm": arm, "query_mae": adapt_mae, "regret": adapt_mae - query["oracle_mae"]})
    if len(set(revealed_evals.values())) != 1:
        raise RuntimeError("unmatched_revealed_budget")

    def _phase(block, phase):
        part = [row for row in block if row["phase"] == phase]
        return {
            "regret": float(np.mean([row["regret"] for row in part])),
            "mae": float(np.mean([row["query_mae"] for row in part])),
            "arms": [row["arm"] for row in part],
            "tasks": [row["task"] for row in part],
        }

    summary = {policy: {"train": _phase(rows[policy], "train"), "development": _phase(rows[policy], "development")} for policy in POLICIES}
    adapt_summary = {policy: {"train": _phase(adapted[policy], "train"), "development": _phase(adapted[policy], "development")} for policy in POLICIES}
    pend0 = load_support("pendulum", 0, 0, 32, family_context("pendulum"))[1]
    pend2 = load_support("pendulum", 2, 0, 32, family_context("pendulum"))[1]
    acro0 = load_support("acrobot", 0, 0, 32, family_context("acrobot"))[1]
    acro2 = load_support("acrobot", 2, 0, 32, family_context("acrobot"))[1]
    mem = ResidualMemory(seed=seed)
    for family, bundle, phase in TASKS:
        if phase != "train":
            continue
        context = family_context(family)
        support, desc = load_support(family, bundle, 0, 32, context)
        revealed = _arrays(family, bundle, "train")
        arm = mem.choose(family, desc, policy="memory")
        mae = prediction_mae(_models(family)[arm], revealed["obs"][32:96], revealed["action"][32:96], revealed["next_obs"][32:96])
        mem.update(family, desc, arm, mae)
    causal = {
        "pend0": mem.choose("pendulum", pend0, policy="memory", explore=False),
        "pend2": mem.choose("pendulum", pend2, policy="memory", explore=False),
        "acro0": mem.choose("acrobot", acro0, policy="memory", explore=False),
        "acro2": mem.choose("acrobot", acro2, policy="memory", explore=False),
        "pend_descriptor_distance": float(np.linalg.norm(pend0 - pend2)),
        "acro_descriptor_distance": float(np.linalg.norm(acro0 - acro2)),
        "retrieved": {
            key: {
                str(arm): {
                    "shrunk": float(vals[0]),
                    "mass": float(vals[1]),
                    "min_dist": None if not np.isfinite(vals[2]) else float(vals[2]),
                }
                for arm, vals in (
                    (a, mem._retrieve(family, desc, a)) for a in ARMS
                )
            }
            for key, family, desc in (("pend2", "pendulum", pend2), ("acro2", "acrobot", acro2))
        },
    }
    causal["changed"] = causal["pend0"] != causal["pend2"] or causal["acro0"] != causal["acro2"]
    memory_dev = summary["memory"]["development"]
    persist_dev = summary["persist"]["development"]
    persist_best_dev = summary["persist_best"]["development"]
    default_dev = summary["default"]["development"]
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
        "used_e217_science_arrays": False,
        "used_e217_science_fits": False,
        "source": "evolution2_fit_clock_disposable",
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "seed": seed,
        "revealed_evals": revealed_evals,
        "adapt_steps": ADAPT_STEPS,
        "hidden_oracles": {key: {"oracle": val["oracle"], "mae": val["mae"]} for key, val in hidden.items()},
        "summary": summary,
        "adapted": adapt_summary,
        "rows": rows,
        "causal": causal,
        "decision": {
            "memory_beats_persist_dev": memory_dev["regret"] < persist_dev["regret"],
            "memory_beats_persist_best_dev": memory_dev["regret"] < persist_best_dev["regret"],
            "memory_beats_default_dev": memory_dev["regret"] < default_dev["regret"],
            "causal_choice_changes": causal["changed"],
            "development_success": memory_dev["regret"] < min(persist_dev["regret"], persist_best_dev["regret"], default_dev["regret"]),
        },
        "wall_s": wall,
        "cpu_s": cpu,
        "note": "Residual-selection development bench, not a scientific result and not AGI.",
    }


def write_artifact(seed: int = 7) -> dict:
    payload = run_benchmark(seed)
    RESULTS.write_text(json.dumps(payload, indent=2, default=float) + "\n")
    return payload
