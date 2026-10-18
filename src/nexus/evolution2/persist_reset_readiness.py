"""Pre-authorization persist-versus-reset readiness. Source-only. Not science.

Reconciles the 7,680-step source worksheet with the 9,600-step
revealed/development worksheet. Occupied-default persist arrays are not
fresh-physics credit. Does not collect, fit, name a holdout, or flip flags.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import pendulum_acrobot_holdout_review as review
from nexus.evolution2 import pendulum_acrobot_protocol_n3_micro as n3
from nexus.evolution2 import pendulum_acrobot_protocol_v2 as v2
from nexus.evolution2 import source_persist_request as persist

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_readiness.json"
DRY_RUN = ROOT / "artifacts" / "evolution2_persist_reset_dry_run.json"
H16 = ROOT / "artifacts" / "research_session_h16_same_state_library_usage.json"
H16_SHA = "ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117"

FRESH_SOURCE_STEPS = n3.N_BUNDLES * 2 * (v2.SOURCE_TRAIN_STEPS + v2.SOURCE_VAL_STEPS)
REVEALED_STEPS = (
    n3.N_BUNDLES * n3.REVEALED_VARIANTS_PER_FAMILY * 2 * v2.EPISODE_STEPS
)
DEVELOPMENT_STEPS = n3.N_BUNDLES * n3.DEVELOPMENT_CONDITIONS * 2 * v2.EPISODE_STEPS
SCREEN_STEPS = REVEALED_STEPS + DEVELOPMENT_STEPS
FRESH_TOTAL_STEPS = FRESH_SOURCE_STEPS + SCREEN_STEPS
OCCUPIED_DEFAULT_PERSIST_STEPS = persist.N3_SOURCE_STEPS
MEASURED_SIX_FIT_WALL_S = 1.215
MEASURED_SIX_FIT_CPU_S = 0.974
MEASURED_DEFAULT_PERSIST_WALL_S = 0.156
BONFERRONI_T_CRIT = n3.BONFERRONI_T_CRIT_DF2
BONFERRONI_POWER_NOTE = (
    "df=2 with the locked five-comparison threshold 9.924843 is "
    "intentionally low-power. A positive lower bound requires "
    "mean > 9.924843 * s / sqrt(3) ≈ 5.730 s. A 0.05 practical-margin "
    "effect would need bundle scatter below ≈ 0.0087. Inconclusive is "
    "the expected label unless the effect is enormous. This is not "
    "n=10 confirmation and must not inherit the v2 df=9 gate."
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def step_worksheet() -> dict:
    n3_sheet = n3.worksheet()
    if n3_sheet["revealed_training_steps"] != REVEALED_STEPS:
        raise RuntimeError("revealed_step_mismatch")
    if n3_sheet["development_evaluation_steps"] != DEVELOPMENT_STEPS:
        raise RuntimeError("development_step_mismatch")
    if n3_sheet["first_screen_total_steps"] != SCREEN_STEPS:
        raise RuntimeError("screen_step_mismatch")
    if persist.N3_SOURCE_STEPS != FRESH_SOURCE_STEPS:
        raise RuntimeError("source_step_mismatch")
    if FRESH_TOTAL_STEPS != 17_280:
        raise RuntimeError("fresh_total_mismatch")
    return {
        "n_bundles": n3.N_BUNDLES,
        "families": 2,
        "source_train_val_per_family_bundle": v2.SOURCE_TRAIN_STEPS + v2.SOURCE_VAL_STEPS,
        "occupied_default_persist_steps": OCCUPIED_DEFAULT_PERSIST_STEPS,
        "fresh_source_steps_required": FRESH_SOURCE_STEPS,
        "revealed_training_steps": REVEALED_STEPS,
        "development_evaluation_steps": DEVELOPMENT_STEPS,
        "n3_revealed_development_worksheet": SCREEN_STEPS,
        "fresh_total_environment_steps": FRESH_TOTAL_STEPS,
        "occupied_defaults_are_not_credit": True,
        "source_persist_authorization_is_not_reusable": True,
        "do_not_silently_add": 7_680 + 9_600,
        "justification": (
            "A complete new-physics n=3 first screen needs a matched residual "
            "source (3×2×1280=7680) plus the locked revealed/development "
            "worksheet (7200+2400=9600). Those operations do not share steps. "
            "Existing 7680 default-family arrays cannot be credited. "
            "Exact fresh total is 17280. Confirmation and n=10 are extra and "
            "unauthorized."
        ),
        "rejected_caps": {
            "7680": "occupied_default_source_only_or_reuse_of_E2.8",
            "9600": "screen_without_matched_fresh_residuals",
            "25600": "v2_n10_source_not_this_request",
        },
    }


def refuse_source_reuse(env_cap: int) -> None:
    if int(env_cap) == OCCUPIED_DEFAULT_PERSIST_STEPS:
        raise RuntimeError(
            "env_cap_7680_reuses_occupied_default_persist_not_fresh_physics"
        )
    if int(env_cap) == SCREEN_STEPS:
        raise RuntimeError("env_cap_9600_omits_fresh_matched_source_residuals")
    if int(env_cap) != FRESH_TOTAL_STEPS:
        raise RuntimeError("env_cap_must_be_17280_fresh_new_physics_steps")


def bonferroni_lock() -> dict:
    if abs(float(lock.worksheet()["bonferroni_t_crit"]) - BONFERRONI_T_CRIT) > 1e-12:
        raise RuntimeError("bonferroni_threshold_rewritten")
    if abs(float(n3.BONFERRONI_T_CRIT_DF2) - 9.924843200918293) > 1e-12:
        raise RuntimeError("n3_bonferroni_rewritten")
    return {
        "t_crit": BONFERRONI_T_CRIT,
        "df": 2,
        "comparisons_locked": 5,
        "listed_controls": 3,
        "conservatism": lock.BONFERRONI_NOTE,
        "low_power": BONFERRONI_POWER_NOTE,
        "not_n10_confirmation": True,
        "v2_df9_forbidden": True,
    }


def cost_estimate() -> dict:
    return {
        "measured": {
            "default_family_persist_7680_wall_s": MEASURED_DEFAULT_PERSIST_WALL_S,
            "six_fit_clock_on_defaults_wall_s": MEASURED_SIX_FIT_WALL_S,
            "six_fit_clock_on_defaults_cpu_s": MEASURED_SIX_FIT_CPU_S,
            "six_fit_env_steps": 0,
            "note": (
                "Six fits equal 3 bundles × 2 families, but the clock used "
                "occupied-default arrays. New-physics fit time is unmeasured."
            ),
        },
        "unknown": {
            "fresh_source_collection_wall_s": None,
            "new_physics_six_fit_wall_s": None,
            "revealed_development_screen_wall_s": None,
            "twenty_fit_v2_wall_s": None,
            "imagined_planning_wall_s": None,
        },
        "do_not_invent_twenty_fit": True,
        "do_not_extrapolate_6_times_20_over_6": True,
        "standing_time_cap_s": 900,
        "h16_scientific_ledger": [305.842, 3294.158],
        "debit": False,
    }


def audit_development_dry_run() -> dict:
    if not DRY_RUN.is_file():
        raise RuntimeError("dry_run_artifact_missing")
    payload = json.loads(DRY_RUN.read_text())
    methods = payload.get("methods_exercised") or []
    if methods != ["persist", "reset", "random", "evolution"]:
        raise RuntimeError("four_methods_not_exercised")
    if payload.get("persist_cross_task", {}).get("weights_changed") is not True:
        raise RuntimeError("persist_did_not_retain_cross_task_state")
    if payload.get("persist_cross_task", {}).get("updates") != 12:
        raise RuntimeError("persist_update_count_mismatch")
    reset = payload.get("reset_genuine") or {}
    if reset.get("after_reset_zero_weights") is not True:
        raise RuntimeError("reset_state_not_discarded")
    if reset.get("after_reset_updates") != [0, 0, 0]:
        raise RuntimeError("reset_did_not_clear_updates")
    lookups = payload.get("lookups_per_method") or {}
    if set(lookups.values()) != {16}:
        raise RuntimeError("unequal_proposal_budget")
    if payload.get("leakage_audit") != "PASS":
        raise RuntimeError("leakage_audit_failed")
    if payload.get("hidden_feedback_isolated") is not True:
        raise RuntimeError("development_leaked_into_training_weights")
    if payload.get("holdout_consumed") is not False:
        raise RuntimeError("holdout_consumed")
    if payload.get("scientific_execution") != "BLOCKED":
        raise RuntimeError("dry_run_must_not_be_science")
    return {
        "status": "PASS" if payload.get("dry_run") == "PASS" else "FAIL",
        "four_methods_exercised": True,
        "persist_retained": True,
        "reset_discarded": True,
        "equal_budget": True,
        "development_not_training_feedback": True,
        "scientific": False,
    }


def scientific_design() -> dict:
    return {
        "reuse": (
            "evolution2.methods, TrustedEvaluator, ReservationLedger, "
            "planner_adapter.decide, v2.bundle_family_order, "
            "v2.paired_bundle_seeds, train_world_model recipe"
        ),
        "model_fitting": {
            "recipe": "residual_mlp_64x64_adam_1e-3_20_epochs_1024_256",
            "n_fits_for_n3": 6,
            "reuse_e29_default_weights": False,
            "reuse_e28_default_arrays": False,
            "status": "BLOCKED",
        },
        "permitted_source_feedback": {
            "revealed_variants_per_family": n3.REVEALED_VARIANTS_PER_FAMILY,
            "training_feedback_type": "evolution1.toy_loop.TrainingFeedback",
            "caller_score_substitution": False,
        },
        "persist_reset_boundaries": {
            "persist": "PersistentAdaptive retains weights across train families; freeze before hidden eval",
            "reset": "ResetAdaptive.reset_task discards weights between tasks",
            "random": "StatelessWrapper independent seeds",
            "evolution": "within-task one-coordinate mutation; crossover illegal",
        },
        "independent_bundle_seeds": {
            "rule": "v2.paired_bundle_seeds(bundle_id) for bundle_id in (0,1,2)",
            "model_seed_base": 80_000_000,
            "planner_seed_base": 81_000_000,
            "proposal_seed_base": 82_000_000,
            "student_seeds_are_not_replications": True,
        },
        "counterbalanced_family_order": {
            "rule": "v2.bundle_family_order",
            "bundle_0": list(v2.bundle_family_order(0)),
            "bundle_1": list(v2.bundle_family_order(1)),
            "bundle_2": list(v2.bundle_family_order(2)),
        },
        "hidden_development": {
            "evaluator": "TrustedEvaluator.hide_development",
            "training_feedback_must_not_see_development": True,
            "dry_run_uses_eval_clone_without_global_update": True,
            "scientific_path_must_hide_not_only_freeze": True,
        },
    }


def scientific_readiness(env_cap: int | None = None) -> dict:
    record = lock.allocation_record()
    hold_named = bool(record.get("hold_named"))
    authorized = record.get("authorized") is True
    requested = 0 if env_cap is None else int(env_cap)
    reuse = requested in {0, OCCUPIED_DEFAULT_PERSIST_STEPS, SCREEN_STEPS}
    fresh_cap = requested == FRESH_TOTAL_STEPS
    gates = {
        "locked_request_hashes": lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG,
        "holdout_named": hold_named,
        "holdout_review": review.VERDICT == "NAMING_BLOCKED",
        "authorized": authorized,
        "fresh_env_cap_17280": fresh_cap,
        "occupied_default_reuse_refused": True,
        "source_persist_not_credited": True,
        "twenty_fit_measured": False,
        "h17": False,
        "scientific_flags_unchanged": record.get("authorized") is False,
        "h16_untouched": file_sha256(H16) == H16_SHA,
    }
    blockers = []
    if not hold_named or review.VERDICT == "NAMING_BLOCKED":
        blockers.append("holdout_unnamed")
    if not authorized:
        blockers.append("unauthorized")
    if not fresh_cap:
        blockers.append("env_cap_not_17280_fresh")
    if reuse and requested == OCCUPIED_DEFAULT_PERSIST_STEPS:
        blockers.append("occupied_default_reuse")
    blockers.extend(["scientific_runner_refuses", "twenty_fit_unmeasured_not_required_for_n3"])
    status = "GO" if not blockers else "BLOCKED"
    return {
        "status": status,
        "reason": (
            "scientific_execution_blocked:" + ",".join(blockers)
            if blockers
            else "ready"
        ),
        "blockers": blockers,
        "gates": gates,
        "requested_env_cap": requested,
        "required_env_cap": FRESH_TOTAL_STEPS,
        "holdout_integrity": "BLOCKED",
        "real_source_fitting_path": "BLOCKED",
        "scientific_execution_readiness": "BLOCKED",
    }


def require_scientific_prerequisites(env_cap: int) -> None:
    refuse_source_reuse(int(env_cap))
    report = scientific_readiness(int(env_cap))
    if report["status"] != "GO":
        raise RuntimeError(report["reason"])


def write_artifact() -> dict:
    payload = {
        "scientific": False,
        "collection": False,
        "fitting": False,
        "enabled_dispatch": False,
        "github_commit": "9428e18345a44870838f9cefc6c144f549f7af35",
        "worksheet": step_worksheet(),
        "bonferroni": bonferroni_lock(),
        "costs": cost_estimate(),
        "dry_run": audit_development_dry_run(),
        "design": scientific_design(),
        "readiness": scientific_readiness(0),
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "h16_scientific_ledger_untouched": True,
        "scientific_ledger_preserved": [305.842, 3294.158],
        "claims_learning_to_learn": False,
        "is_agi": False,
        "next_action": (
            "Do not collect. A later approval must cite 8e90b74a, name a "
            "four-role unused holdout, set env_cap=17280 for fresh physics, "
            "and accept the refuse-only runner until those gates pass. "
            "continue is not approval."
        ),
    }
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
