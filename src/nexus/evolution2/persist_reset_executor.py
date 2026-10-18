"""Gated persist-versus-reset executor. Development verify only. Not science.

Plans the locked 17,280-step budget, six matched new-physics residual
slots, four equal-budget methods, hide_development isolation, and
ReservationLedger interruption accounting. Does not collect, fit, flip
flags, or enable scientific dispatch.
"""
from __future__ import annotations

import json
from pathlib import Path

from nexus.evolution1.resources import Clock, Limits, Operation, ReservationLedger, Work
from nexus.evolution2 import fit_clock as clock
from nexus.evolution2 import persist_reset_budget as budget
from nexus.evolution2 import persist_reset_dry_run as dry
from nexus.evolution2 import persist_reset_path as path
from nexus.evolution2 import persist_reset_readiness as ready
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_roles as roles
from nexus.evolution2.pendulum_acrobot_protocol_n3_micro import (
    DEVELOPMENT_CONDITIONS,
    N_BUNDLES,
    REVEALED_VARIANTS_PER_FAMILY,
)
from nexus.evolution2.pendulum_acrobot_protocol_v2 import (
    EPISODE_STEPS,
    SOURCE_TRAIN_STEPS,
    SOURCE_VAL_STEPS,
    bundle_family_order,
    paired_bundle_seeds,
)

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_executor.json"
METHODS = ("persist", "reset", "random", "evolution")
SOURCE_PER_FAMILY_BUNDLE = SOURCE_TRAIN_STEPS + SOURCE_VAL_STEPS
REVEALED_PER_FAMILY_BUNDLE = REVEALED_VARIANTS_PER_FAMILY * EPISODE_STEPS
DEVELOPMENT_PER_FAMILY_BUNDLE = DEVELOPMENT_CONDITIONS * EPISODE_STEPS


def refuse_science() -> None:
    path.refuse_science()
    if lock.persist_reset_authorized(budget.FRESH_TOTAL_STEPS):
        raise RuntimeError("scientific_authorization_must_remain_false")


def planned_fits() -> tuple[dict, ...]:
    slots = []
    for bundle_id in range(N_BUNDLES):
        seeds = paired_bundle_seeds(bundle_id)
        model_seed = seeds["persist"]["model_seed"]
        for family in bundle_family_order(bundle_id):
            slots.append(
                {
                    "family": family,
                    "bundle": bundle_id,
                    "model_seed": model_seed,
                    "recipe": dict(clock.RECIPE),
                    "status": "planned_not_executed",
                }
            )
    if len(slots) != budget.N_FITS:
        raise RuntimeError("six_matched_fits_required")
    families = {slot["family"] for slot in slots}
    if families != {"pendulum", "acrobot"}:
        raise RuntimeError("both_families_required")
    return tuple(slots)


def planned_budget() -> dict:
    source = N_BUNDLES * 2 * SOURCE_PER_FAMILY_BUNDLE
    revealed = N_BUNDLES * 2 * REVEALED_PER_FAMILY_BUNDLE
    development = N_BUNDLES * 2 * DEVELOPMENT_PER_FAMILY_BUNDLE
    total = source + revealed + development
    if source != budget.FRESH_SOURCE_STEPS or total != budget.FRESH_TOTAL_STEPS:
        raise RuntimeError("fresh_budget_rewritten")
    if total != 17_280:
        raise RuntimeError("fresh_total_must_be_17280")
    return {
        "fresh_source": source,
        "revealed": revealed,
        "development": development,
        "fresh_total": total,
        "fits": budget.N_FITS,
        "methods": list(METHODS),
        "equal_budget": True,
        "occupied_default_credit": 0,
        "authorized_env_cap": lock.allocation_record().get("env_cap"),
    }


def planned_step_accounts() -> tuple[dict, ...]:
    rows = []
    for bundle_id in range(N_BUNDLES):
        for family in bundle_family_order(bundle_id):
            rows.extend(
                (
                    {
                        "key": f"{family}-b{bundle_id}-src",
                        "phase": "source",
                        "real_steps": SOURCE_PER_FAMILY_BUNDLE,
                    },
                    {
                        "key": f"{family}-b{bundle_id}-rev",
                        "phase": "revealed",
                        "real_steps": REVEALED_PER_FAMILY_BUNDLE,
                    },
                    {
                        "key": f"{family}-b{bundle_id}-dev",
                        "phase": "development",
                        "real_steps": DEVELOPMENT_PER_FAMILY_BUNDLE,
                    },
                )
            )
    real = sum(int(row["real_steps"]) for row in rows)
    if real != budget.FRESH_TOTAL_STEPS:
        raise RuntimeError("reservation_plan_step_mismatch")
    return tuple(rows)


def isolation_plan() -> dict:
    return {
        "evaluator": "TrustedEvaluator.hide_development",
        "training_feedback_must_not_see_development": True,
        "occupied_defaults_are_not_holdout": True,
        "methods_share_equal_proposal_slots": True,
    }


def interrupt_accounting() -> dict:
    accounts = planned_step_accounts()
    planned_real = sum(int(row["real_steps"]) for row in accounts)
    operations = (
        Operation("interrupt-src", "environment", Work(real_steps=1)),
        Operation("interrupt-rev", "environment", Work(real_steps=1)),
        Operation("never-started", "environment", Work(real_steps=1)),
    )
    physical = Work()
    logical = Work()
    for operation in operations:
        physical = physical.plus(operation.physical_cost)
        logical = logical.plus(operation.cost)
    ledger = ReservationLedger(operations, Limits(physical, logical, 10**12, 10**12))
    ticket = ledger.reserve("interrupt-src", Clock(0, 1))
    ledger.settle(ticket, "interrupted", Clock(0, 2))
    report = ledger.close(Clock(0, 3))
    probe = dry.interrupted_evaluation()
    return {
        "planned_real_steps": planned_real,
        "accounts": list(accounts),
        "status": report.status,
        "reason": report.reason,
        "unresolved": list(report.unresolved_keys),
        "physical_completed": report.physical_completed_reported.payload(),
        "physical_unknown": report.physical_unknown_upper_bound.payload(),
        "logical_charged": report.logical_charged.payload(),
        "probe": probe,
        "env_steps_collected": 0,
    }


def execute_development() -> dict:
    refuse_science()
    role_report = roles.verify_four_roles()
    if role_report["status"] != "PASS":
        raise RuntimeError("four_role_assignment_failed")
    sheet = planned_budget()
    fits = planned_fits()
    isolation = isolation_plan()
    interruption = interrupt_accounting()
    path_report = path.verify_execution_path()
    if path_report["methods_exercised"] != list(METHODS):
        raise RuntimeError("four_methods_not_exercised")
    if path_report["hidden_development_blocked"] is not True:
        raise RuntimeError("development_not_isolated")
    if path_report["env_steps"] != 0:
        raise RuntimeError("env_steps_must_remain_zero")
    readiness = ready.scientific_readiness(0)
    if readiness["status"] != "BLOCKED":
        raise RuntimeError("science_must_remain_blocked")
    if interruption["planned_real_steps"] != 17_280:
        raise RuntimeError("interrupt_plan_must_cover_17280")
    return {
        "status": "DEVELOPMENT_PASS_SCIENCE_BLOCKED",
        "scientific": False,
        "collection": False,
        "fitting": False,
        "fits_executed": 0,
        "env_steps": 0,
        "env_cap": 0,
        "granted_7680": False,
        "hold_named": False,
        "budget": sheet,
        "step_accounts": list(planned_step_accounts()),
        "fits_planned": list(fits),
        "methods": list(METHODS),
        "isolation": isolation,
        "path": path_report,
        "interruption": interruption,
        "roles": {
            "status": role_report["status"],
            "digests": role_report["digests"],
            "historical_exclusion_clean": role_report["historical_exclusion_clean"],
            "hold_named": False,
        },
        "readiness": readiness,
        "runner_readiness": "DEVELOPMENT_READY_SCIENCE_BLOCKED",
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "h17": "blocked",
        "scientific_ledger_preserved": [305.842, 3294.158],
        "claims_learning_to_learn": False,
        "is_agi": False,
    }


def execute_scientific(env_cap: int, approval_text: str = "") -> None:
    lock.require_named_holdout()
    from nexus.evolution2 import persist_reset_approval as gate

    parsed = gate.parse_approval(approval_text)
    if parsed["status"] != "COMPLETE_TEXT_ONLY" or not parsed["four_role_valid"]:
        raise RuntimeError(
            "persist_versus_reset_approval_insufficient:" + ",".join(parsed["missing"])
        )
    if not lock.persist_reset_authorized(int(env_cap)):
        lock.require_scientific()
    ready.require_scientific_prerequisites(int(env_cap))
    raise RuntimeError("scientific_persist_versus_reset_blocked_until_independent_authorization")


def dispatch(env_cap: int) -> None:
    execute_scientific(int(env_cap))


def write_artifact() -> dict:
    payload = execute_development()
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
