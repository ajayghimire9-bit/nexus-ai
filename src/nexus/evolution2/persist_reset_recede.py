"""Receding decide() clock on locked stored observations. env_cap=0. Not science.

Walks 200 recorded states per family through the trusted planner. Does not
step a Gymnasium env, collect, fit, grant 7680, or enable dispatch.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from nexus.evolution1.catalogue import plan_bound
from nexus.evolution1.resources import Clock, Limits, Operation, ReservationLedger, Work
from nexus.evolution1.toy_loop import ANCHORS
from nexus.evolution2 import evaluator_dry_run as dry
from nexus.evolution2 import evaluator_readiness as eval_ready
from nexus.evolution2 import fit_clock as clock
from nexus.evolution2 import persist_reset_budget as budget
from nexus.evolution2 import persist_reset_path as path
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2.bindings import reviewed_binding
from nexus.evolution2.planner_adapter import decide, twelve_arm_scientific_dispatch

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_recede.json"
USAGE = ROOT / "artifacts" / "research_session_e2_persist_reset_recede_usage.json"
H16 = budget.H16
H16_SHA = budget.H16_SHA
EPISODE_STEPS = 200
FAMILIES = ("pendulum", "acrobot")


def source_obs_sequence(family: str, bundle: int = 0, n: int = EPISODE_STEPS) -> np.ndarray:
    spec = next(
        row
        for row in clock.LOCKED_ARRAYS
        if row["family"] == family and int(row["bundle"]) == int(bundle) and row["split"] == "train"
    )
    file_path = ROOT / spec["path"]
    if eval_ready.file_sha256(file_path) != spec["sha256"]:
        raise RuntimeError("source_array_hash_mismatch")
    data = np.load(file_path)
    obs = np.asarray(data["obs"][: int(n)], dtype=np.float32)
    if obs.shape[0] != int(n):
        raise RuntimeError("stored_sequence_too_short")
    if obs.shape[-1] != reviewed_binding(family).obs_dim:
        raise RuntimeError("observation_layout_mismatch")
    return obs


def _key(family: str, variant, step: int) -> str:
    return f"{family}_{variant.rule.value}_{variant.generator.value}_{variant.horizon}_s{step}"


def measure_recede_clock() -> dict:
    path.refuse_science()
    imagined = 0
    n_decisions = 0
    decoded = 0
    rows = []
    cpu0 = time.process_time()
    wall0 = time.perf_counter()
    for family in FAMILIES:
        binding = reviewed_binding(family)
        obs = source_obs_sequence(family, 0, EPISODE_STEPS)
        model = path.disposable_model(family, 0)
        operations = []
        for variant in ANCHORS:
            bound = plan_bound(variant, binding.n_actions, 1536)
            for step in range(EPISODE_STEPS):
                operations.append(
                    Operation(
                        _key(family, variant, step),
                        "model",
                        Work(
                            imagined_transitions=bound.imagined_per_decision,
                            model_calls=1,
                            network_forwards=1,
                        ),
                    )
                )
        physical = Work()
        logical = Work()
        for operation in operations:
            physical = physical.plus(operation.physical_cost)
            logical = logical.plus(operation.cost)
        ticks = [0]

        def clock_read(ticks=ticks) -> Clock:
            ticks[0] += 1
            return Clock(0, ticks[0])

        ledger = ReservationLedger(tuple(operations), Limits(physical, logical, 10**12, 10**12))
        for variant in ANCHORS:
            for step, state in enumerate(obs):
                ticket = ledger.reserve(_key(family, variant, step), clock_read())
                decision = decide(family, variant, state, model, seed=step)
                dry.decode_action(binding, decision.action)
                ledger.settle(ticket, "success", clock_read())
                imagined += int(decision.imagined)
                n_decisions += 1
                decoded += 1
            rows.append(
                {
                    "family": family,
                    "rule": variant.rule.value,
                    "generator": variant.generator.value,
                    "horizon": variant.horizon,
                    "steps": EPISODE_STEPS,
                }
            )
        closed = ledger.close(clock_read())
        if closed.status != "complete_execution":
            raise RuntimeError("ledger_incomplete")
    wall_s = time.perf_counter() - wall0
    cpu_s = time.process_time() - cpu0
    per = wall_s / n_decisions if n_decisions else None
    return {
        "scientific": False,
        "gymnasium": False,
        "env_steps": 0,
        "env_cap": 0,
        "granted_7680": False,
        "n_decisions": n_decisions,
        "n_episode_equivalents": len(rows),
        "episode_steps": EPISODE_STEPS,
        "imagined": imagined,
        "decoded": decoded,
        "wall_s": wall_s,
        "cpu_s": cpu_s,
        "seconds_per_decision": per,
        "episode_prior_s": None if per is None else per * EPISODE_STEPS,
        "screen_9600_prior_s": None if per is None else per * budget.SCREEN_DECISIONS_UPPER,
        "prior_label": "receding_on_stored_default_obs_not_new_physics",
        "do_not_treat_as_scientific_clock": True,
        "rows": rows,
        "twelve_arm_scientific": twelve_arm_scientific_dispatch()["status"],
        "enabled_dispatch": False,
    }


def write_artifact() -> dict:
    recede = measure_recede_clock()
    if recede["env_steps"] != 0 or recede["granted_7680"] is not False:
        raise RuntimeError("recede_clock_must_not_collect_or_grant")
    if recede["n_decisions"] != 2 * 2 * EPISODE_STEPS:
        raise RuntimeError("recede_decision_count_mismatch")
    usage = {
        "scientific": False,
        "env_steps": 0,
        "env_cap": 0,
        "wall_s": recede["wall_s"],
        "cpu_s": recede["cpu_s"],
        "h16_scientific_ledger_untouched": budget.file_sha256(H16) == H16_SHA,
        "session_ledger_used_after_s": 305.842,
        "granted_7680": False,
    }
    USAGE.write_text(json.dumps(usage, indent=2) + "\n")
    payload = {
        "scientific": False,
        "collection": False,
        "fitting": False,
        "granted_7680": False,
        "hold_named": False,
        "budget": budget.resource_budget(),
        "recede": recede,
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "h16_scientific_ledger_untouched": usage["h16_scientific_ledger_untouched"],
        "scientific_ledger_preserved": [305.842, 3294.158],
        "claims_learning_to_learn": False,
        "is_agi": False,
        "next_action": (
            "Do not grant 7680. Do not collect. A later persist-versus-reset "
            "approval must cite 8e90b74a, name a four-role unused holdout, "
            "and set env_cap=17280. continue is not that approval."
        ),
    }
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
