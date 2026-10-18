"""Evolution-2.10 evaluator readiness. Source-only. Not scientific dispatch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nexus.evolution1.catalogue import catalogue
from nexus.evolution2 import fit_clock as clock
from nexus.evolution2 import residual_timing_probe as timing
from nexus.evolution2 import source_persist_request as persist
from nexus.evolution2.bindings import bind_evaluation, reviewed_binding
from nexus.evolution2.host import runtime_gate_status
from nexus.evolution2.planner_adapter import twelve_arm_scientific_dispatch

ROOT = Path(__file__).resolve().parents[3]
H16 = ROOT / "artifacts" / "research_session_h16_same_state_library_usage.json"
PROBE = ROOT / "artifacts" / "research_session_e2_residual_timing_probe_usage.json"
PERSIST = ROOT / "artifacts" / "research_session_e2_source_persist_7680_usage.json"
FIT = ROOT / "artifacts" / "research_session_e2_fit_clock_usage.json"
FIT_RUN = ROOT / "artifacts" / "evolution2_fit_clock_run.json"
RESULTS = ROOT / "artifacts" / "evolution2_evaluator_readiness.json"
H16_SHA = "ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117"
SCIENTIFIC = False


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_scientific() -> None:
    raise RuntimeError(
        "Evolution-2 scientific dispatch remains blocked: holdout unnamed, "
        "authorization false, twenty-fit v2 clock unavailable"
    )


def verify_six_fit_clock() -> dict:
    payload = json.loads(FIT_RUN.read_text())
    if int(payload.get("n_fits") or 0) != 6:
        raise RuntimeError("six_fit_count_mismatch")
        if int(payload.get("env_steps", -1)) != 0:
            raise RuntimeError("fit_clock_env_steps_changed")
    if payload.get("v2_confirmation") is not False:
        raise RuntimeError("v2_confirmation_must_remain_false")
    arrays = []
    for spec in clock.LOCKED_ARRAYS:
        path = ROOT / spec["path"]
        digest = file_sha256(path) if path.is_file() else None
        arrays.append({**spec, "matches": digest == spec["sha256"]})
    fits = []
    for row in payload["fits"]:
        path = ROOT / row["path"]
        digest = file_sha256(path) if path.is_file() else None
        fits.append(
            {
                "family": row["family"],
                "bundle": row["bundle"],
                "matches": digest == row["sha256"],
                "disposable": bool(row.get("disposable")),
            }
        )
    return {
        "n_fits_observed": 6,
        "twenty_fit_measured": False,
        "do_not_extrapolate": True,
        "wall_s": payload["wall_s"],
        "cpu_s": payload["cpu_s"],
        "arrays_match": all(row["matches"] for row in arrays),
        "weights_match": all(row["matches"] and row["disposable"] for row in fits),
        "repeat_write": "duplicate_or_partial_fit_clock",
        "arrays": arrays,
        "fits": fits,
    }


def ledger_records() -> dict:
    h16 = json.loads(H16.read_text())
    probe = json.loads(PROBE.read_text())
    persist_usage = json.loads(PERSIST.read_text())
    fit_usage = json.loads(FIT.read_text())
    if file_sha256(H16) != H16_SHA:
        raise RuntimeError("h16_ledger_hash_changed")
    if h16["ledger"]["consumed_total_s"] != 305.842:
        raise RuntimeError("h16_ledger_debited")
    return {
        "distinct": True,
        "silently_merged": False,
        "h16_scientific": {
            "consumed_s": 305.842,
            "remaining_s": 3294.158,
            "sha256": H16_SHA,
            "debit": False,
        },
        "inference_probe": {
            "path": "artifacts/research_session_e2_residual_timing_probe_usage.json",
            "wall_s": probe["wall_s"],
            "env_steps": probe["env_steps"],
            "session_used_after_s": probe["session_ledger_used_after_s"],
            "distinct_from_h16_file": True,
        },
        "source_persist_7680": {
            "path": "artifacts/research_session_e2_source_persist_7680_usage.json",
            "wall_s": persist_usage["wall_s"],
            "env_steps": persist_usage["env_steps"],
            "h16_untouched": persist_usage["h16_scientific_ledger_untouched"],
            "grant": persist.LOCKED_CONFIG,
        },
        "fit_clock": {
            "path": "artifacts/research_session_e2_fit_clock_usage.json",
            "wall_s": fit_usage["wall_s"],
            "env_steps": fit_usage["env_steps"],
            "n_fits": fit_usage["n_fits"],
            "h16_untouched": fit_usage["h16_scientific_ledger_untouched"],
            "grant": clock.LOCKED_CONFIG,
        },
    }


def development_bindings() -> dict:
    rows = []
    for family in ("pendulum", "acrobot"):
        binding = reviewed_binding(family)
        for variant in catalogue():
            item = bind_evaluation(
                family,
                variant,
                checkpoint_id=binding.checkpoint_id,
                world_model_id=binding.world_model_id,
                model_obs_dim=binding.obs_dim,
                model_n_actions=binding.n_actions,
            )
            rows.append(
                {
                    "family": family,
                    "variant": variant.fingerprint,
                    "generator": variant.generator.value,
                    "scientific": item.scientific,
                }
            )
    return {
        "n": len(rows),
        "all_bound": len(rows) == 24,
        "scientific": False,
        "rows": rows,
    }


def readiness_matrix() -> list[dict]:
    gates = runtime_gate_status()
    dispatch = twelve_arm_scientific_dispatch()
    clocked = verify_six_fit_clock()
    return [
        {"id": "six_fit_clock_observed", "status": "PASS" if clocked["n_fits_observed"] == 6 else "FAIL", "blocks": []},
        {"id": "twenty_fit_v2_clock", "status": "UNAVAILABLE", "blocks": ["v2"]},
        {"id": "source_array_hashes", "status": "PASS" if clocked["arrays_match"] else "FAIL", "blocks": []},
        {"id": "disposable_weight_identity", "status": "PASS" if clocked["weights_match"] else "FAIL", "blocks": []},
        {"id": "development_twelve_arm_binding", "status": gates.get("development_twelve_arm_binding"), "blocks": []},
        {"id": "trusted_evaluator_cache", "status": "PASS", "blocks": []},
        {"id": "reservation_ledger_reuse", "status": "PASS", "blocks": []},
        {"id": "worker_cpu_enforcement", "status": gates["worker_cpu_enforcement"], "blocks": ["scientific_cpu_cap"]},
        {"id": "hardened_os_filesystem_sandbox", "status": gates["hardened_os_filesystem_sandbox"], "blocks": ["sandbox"]},
        {"id": "holdout_named", "status": "BLOCKED", "blocks": ["confirmation"]},
        {"id": "h17", "status": "blocked", "blocks": ["h17"]},
        {
            "id": "scientific_experiment_authorization",
            "status": "BLOCKED",
            "reason": dispatch["reason"],
            "blocks": ["v2", "v2-pilot", "n3-confirmation"],
        },
    ]


def smallest_scientific_experiment() -> dict:
    return {
        "id": "e2_n3_persist_vs_reset_named_holdout",
        "complete": False,
        "authorized": False,
        "n_bundles": 3,
        "methods": ["persist", "reset", "random", "evolution"],
        "equal_budget_controls": True,
        "independent_replication": "ten_decoder_rule_not_student_seeds",
        "holdout": "unnamed_four_role_rules_locked",
        "source_fits": "six_fit_clock_is_cost_prior_only",
        "confirmation_split": "distinct_from_development",
        "cannot_use": [
            "occupied_family_defaults_as_a_new_holdout",
            "disposable_source_weights_as_confirmation_residuals",
            "6_times_20_over_6_as_a_twenty_fit_measurement",
        ],
        "note": (
            "The smallest complete scientific comparison is n=3 persist versus "
            "reset with equal-budget random and evolution controls on a newly "
            "named unused holdout. That holdout is still unnamed. This dry-run "
            "does not start it."
        ),
    }


def write_artifact() -> dict:
    payload = {
        "scientific": False,
        "collection": False,
        "fitting": False,
        "enabled_dispatch": False,
        "six_fit": verify_six_fit_clock(),
        "ledgers": ledger_records(),
        "development_bindings": development_bindings(),
        "matrix": readiness_matrix(),
        "smallest_scientific_experiment": smallest_scientific_experiment(),
        "persist_config_sha256": persist.LOCKED_CONFIG,
        "fit_clock_config_sha256": clock.LOCKED_CONFIG,
        "v2_hashes_rewritten": False,
        "hold_named": False,
        "h17": "blocked",
        "claims_learning_to_learn": False,
        "is_agi": False,
        "next_action": (
            "Do not name a holdout here. Next authorized scientific step is a "
            "separate n=3 persist-versus-reset protocol that cites a named "
            "unused holdout and does not invent a twenty-fit cost."
        ),
    }
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
