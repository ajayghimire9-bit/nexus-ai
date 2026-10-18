"""E2.20 method-sensitive next-screen lock. Development only. Not science.

Wires the corrected hidden evaluator as the only future persist-versus-reset
path. Refuses collection, the consumed E2.17 grant, env_cap=17280, env_cap=7680,
continue, and E2.17 development as confirmation. Does not name a holdout or
create a grant.
"""
from __future__ import annotations

import json
from pathlib import Path

from nexus.evolution2 import persist_reset_approval as gate
from nexus.evolution2 import persist_reset_executor as exe
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_roles as roles
from nexus.evolution2 import persist_reset_science as science
from nexus.evolution2.pendulum_acrobot_protocol_v2 import paired_bundle_seeds

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_method_sensitive.json"
FRESH_TOTAL_UPPER = 24_480
FRESH_TOTAL_IF_COLLIDE = 17_280
CONSUMED_ENV_CAP = grant.REQUIRED_ENV_CAP
HISTORICAL_HIDDEN_LOOP = "run_bundle"
NEXT_HIDDEN_LOOP = "corrected_hidden_scores"
E217_ROLES = dict(grant.APPROVED_ROLES)


def budget() -> dict:
    estimate = science.fresh_budget_estimate()
    if estimate["fresh_total_upper"] != FRESH_TOTAL_UPPER:
        raise RuntimeError("fresh_upper_rewritten")
    if estimate["fresh_total_if_identical_selections"] != FRESH_TOTAL_IF_COLLIDE:
        raise RuntimeError("collide_budget_rewritten")
    return estimate


def persist_reset_crn(bundle_id: int) -> dict:
    seeds = paired_bundle_seeds(int(bundle_id))
    persist = int(seeds["persist"]["proposal_seed"])
    reset = int(seeds["reset"]["proposal_seed"])
    if persist != reset:
        raise RuntimeError("persist_reset_rng_must_match")
    return {
        "bundle": int(bundle_id),
        "persist_seed": persist,
        "reset_seed": reset,
        "matched": True,
        "other_baselines_may_use_own_seeds": True,
    }


def refuse_caps(env_cap: int) -> None:
    cap = int(env_cap)
    if cap == 7680:
        raise RuntimeError("occupied_default_persist_not_fresh_physics")
    if cap == CONSUMED_ENV_CAP:
        raise RuntimeError("consumed_e217_env_cap_17280")
    if cap != FRESH_TOTAL_UPPER:
        raise RuntimeError("env_cap_must_be_24480_upper")


def refuse_consumed_grant() -> dict:
    if grant.grant_unused():
        raise RuntimeError("e217_grant_must_stay_consumed")
    record = grant.grant_record()
    if record.get("consumed") is not True or int(record.get("runs") or 0) != 1:
        raise RuntimeError("e217_grant_must_stay_consumed")
    if int(record.get("env_cap") or 0) != CONSUMED_ENV_CAP:
        raise RuntimeError("e217_grant_must_not_be_rewritten")
    return record


def refuse_e217_confirmation(approval_text: str) -> None:
    named = gate.extract_named_roles(approval_text)
    if not named:
        return
    checked = roles.validate_named_roles(named)
    if checked.get("valid"):
        raise RuntimeError("e217_development_is_not_confirmation")


def execute_scientific(env_cap: int, approval_text: str = "") -> None:
    """Refuse-first future screen. Does not collect."""
    refuse_caps(env_cap)
    refuse_consumed_grant()
    refuse_e217_confirmation(approval_text)
    parsed = gate.parse_approval(approval_text)
    if parsed["status"] != "COMPLETE_TEXT_ONLY" or not parsed["four_role_valid"]:
        raise RuntimeError(
            "method_sensitive_screen_unauthorized:" + ",".join(parsed["missing"] or ["insufficient"])
        )
    lock.require_named_holdout()
    raise RuntimeError("unused_24480_grant_missing")


def dispatch(env_cap: int) -> None:
    exe.dispatch(int(env_cap))


def score_saved_bundle(bundle_id: int, produce_score) -> dict:
    """Replay saved E2.17 revealed returns. No environment."""
    historical = json.loads(science.RESULTS.read_text())
    if historical.get("primary_label") != "inconclusive":
        raise RuntimeError("historical_label_rewritten")
    row = next(item for item in historical["bundles"] if int(item["bundle"]) == int(bundle_id))
    family_returns = {item["family"]: item["revealed_returns"] for item in row["families"]}
    persist_reset_crn(bundle_id)
    replayed = science.replay_training(int(bundle_id), family_returns, shared_persist_seed=True)
    report = science.corrected_hidden_scores(replayed["methods"], int(bundle_id), produce_score)
    logical = {name: report["charges"]["per_method"][name]["logical"] for name in science.METHODS}
    if len(set(logical.values())) != 1:
        raise RuntimeError("unequal_hidden_evaluation_budget")
    return {
        "bundle": int(bundle_id),
        "historical_label_preserved": historical["primary_label"],
        "scores": report["scores"],
        "selections": report["selections"],
        "charges": report["charges"],
        "persist_reset_scores_differ": report["scores"]["persist"] != report["scores"]["reset"],
        "hidden_loop": NEXT_HIDDEN_LOOP,
        "historical_loop_unused": HISTORICAL_HIDDEN_LOOP,
    }


def lock_status() -> dict:
    estimate = budget()
    return {
        "scientific": False,
        "collection": False,
        "fitting": False,
        "env_steps": 0,
        "historical_label_preserved": "inconclusive",
        "grant_consumed": True,
        "e217_roles_not_confirmation": True,
        "dispatch_refused": True,
        "h17": "blocked",
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "fresh_total_upper": FRESH_TOTAL_UPPER,
        "fresh_total_if_identical_selections": estimate["fresh_total_if_identical_selections"],
        "hidden_controller": "method.choose after revealed training",
        "persist_reset_crn": True,
        "historical_run_bundle_forbidden": True,
        "next_hidden_loop": NEXT_HIDDEN_LOOP,
        "unused_24480_grant": False,
        "hold_named": False,
        "continue_is_not_approval": True,
        "budget": estimate,
        "scientific_ledger_session": [327.869, 3272.131],
        "claims_learning_to_learn": False,
        "is_agi": False,
    }


def write_artifact() -> dict:
    payload = lock_status()
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
