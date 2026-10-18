"""Methodological diagnosis of E2.17. Does not rewrite the historical label.

Replays recorded revealed returns to recover proposer choices. Tests a
method-sensitive hidden evaluator on synthetic fixtures. Does not collect,
retrain, consume a new grant, or enable scientific dispatch.
"""
from __future__ import annotations

import json
from pathlib import Path

from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_roles as roles
from nexus.evolution2 import persist_reset_science as science
from nexus.evolution2.pendulum_acrobot_protocol_n3_micro import N_BUNDLES
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_diagnosis.json"
SCIENCE = science.RESULTS
HISTORICAL_LABEL = "inconclusive"
ROOT_CAUSE = (
    "run_bundle scored the same locked hidden catalogue variants for every "
    "method and copied that return into each method's score. Proposer "
    "selections never entered hidden evaluation."
)


def load_historical() -> dict:
    payload = json.loads(SCIENCE.read_text())
    if payload.get("primary_label") != HISTORICAL_LABEL:
        raise RuntimeError("historical_label_rewritten")
    if payload.get("analysis", {}).get("label") != HISTORICAL_LABEL:
        raise RuntimeError("historical_analysis_rewritten")
    return payload


def reconstruct_choices(payload: dict) -> dict:
    split = science.locked_split()
    rows = []
    persist_reset_differ = []
    for bundle in payload["bundles"]:
        family_returns = {row["family"]: row["revealed_returns"] for row in bundle["families"]}
        replayed = science.replay_training(int(bundle["bundle"]), family_returns, shared_persist_seed=True)
        comparison = {}
        for name in science.METHODS:
            fingerprints = [
                item["fingerprint"]
                for family_row in replayed["choices"][name]
                for item in family_row["proposals"]
            ]
            comparison[name] = fingerprints
        differ = comparison["persist"] != comparison["reset"]
        persist_reset_differ.append(differ)
        per_family = {}
        for family_row in replayed["choices"]["persist"]:
            family = family_row["family"]

            def _fps(name: str, family: str = family) -> list[str]:
                return [
                    item["fingerprint"]
                    for item in next(row for row in replayed["choices"][name] if row["family"] == family)["proposals"]
                ]

            persist_fp = _fps("persist")
            reset_fp = _fps("reset")
            random_fp = _fps("random")
            evolution_fp = _fps("evolution")
            per_family[family] = {
                "persist": persist_fp,
                "reset": reset_fp,
                "random": random_fp,
                "evolution": evolution_fp,
                "persist_equals_reset": persist_fp == reset_fp,
                "random_equals_persist": random_fp == persist_fp,
                "evolution_equals_persist": evolution_fp == persist_fp,
            }
        rows.append(
            {
                "bundle": bundle["bundle"],
                "family_order": bundle["family_order"],
                "persist_reset_differ_anywhere": differ,
                "families": per_family,
                "shared_proposal_seed": True,
                "note": "Historical runner passed persist proposal_seed to every method.",
            }
        )
    return {
        "revealed_order": [
            {
                "rule": variant.rule.value,
                "generator": variant.generator.value,
                "horizon": variant.horizon,
                "fingerprint": variant.fingerprint,
            }
            for variant in split["revealed"]
        ],
        "hidden_order": [
            {
                "rule": variant.rule.value,
                "generator": variant.generator.value,
                "horizon": variant.horizon,
                "fingerprint": variant.fingerprint,
            }
            for variant in split["hidden"]
        ],
        "bundles": rows,
        "persist_reset_differed_in_any_bundle": any(persist_reset_differ),
        "evolution_differed_from_persist": any(
            not family["evolution_equals_persist"]
            for row in rows
            for family in row["families"].values()
        ),
        "random_differed_from_persist": any(
            not family["random_equals_persist"]
            for row in rows
            for family in row["families"].values()
        ),
    }


def causal_sensitivity_tests() -> dict:
    variants = science.locked_split()["revealed"]
    high, low = variants[0], variants[1]
    known = {high: 0.91, low: 0.17}

    def produce(variant, seed_key):
        return known[variant]

    evaluator = science.MethodSensitiveHiddenEval(produce)
    seed = science.matched_hidden_seed(0, "pendulum", 0)
    persist_high = evaluator.evaluate("persist", high, seed_key=seed)
    reset_low = evaluator.evaluate("reset", low, seed_key=seed)
    persist_low = evaluator.evaluate("persist", low, seed_key=seed)
    reset_high = evaluator.evaluate("reset", high, seed_key=seed)
    persist_high_again = evaluator.evaluate("persist", high, seed_key=seed)
    identical = evaluator.evaluate("random", high, seed_key=seed)
    training = TrustedEvaluator(variants, family="pendulum", bundle_id=0, produce_score=lambda variant: 0.5)
    training.hide_development(high, persist_high)
    training.hide_development(low, reset_low)
    hidden_blocked = False
    try:
        training.evaluate("persist", high, family="pendulum", bundle_id=0)
    except RuntimeError as exc:
        hidden_blocked = "hidden_development_outcome" in str(exc)
    logical = {name: evaluator.per_method[name]["logical"] for name in ("persist", "reset")}
    return {
        "different_selections_differ": persist_high != reset_low and persist_high == known[high] and reset_low == known[low],
        "scores_follow_swapped_selections": persist_low == known[low] and reset_high == known[high],
        "identical_selection_and_seed_match": persist_high_again == persist_high == identical == known[high],
        "hidden_blocked_from_training": hidden_blocked,
        "cache_hit_on_identical_seed": evaluator.cached >= 2,
        "physical_unique_pairs": evaluator.physical == 2,
        "logical_persist_reset": logical,
        "before_historical_hidden_was_method_independent": True,
    }


def corrected_design() -> dict:
    budget = science.fresh_budget_estimate()
    return {
        "hidden_controller": "method.choose from revealed after training; that variant is rolled out on hidden physics",
        "matched_initial_states_and_seeds": "matched_hidden_seed(bundle, family, slot) shared across methods",
        "equal_logical_slots": N_BUNDLES * 2 * science.HIDDEN_SLOTS_PER_FAMILY,
        "physical_vs_logical": "physical episode once per (bundle, family, slot, variant); later identical selections are cache hits",
        "proposal_seeds": "v2.paired_bundle_seeds(bundle)[method] after the repair; historical run shared persist seed",
        "completed_e217_is_observed": True,
        "cannot_confirm_on_e217_development": True,
        "budget": budget,
        "next_experiment": (
            "One new-physics n=3 persist-versus-reset screen using "
            "method-sensitive hidden evaluation, env_cap equal to the "
            "fresh_total_upper unless a later grant names a smaller physical "
            "hidden cap. New unused holdout required. E2.17 grant is consumed."
        ),
    }


def diagnose() -> dict:
    historical = load_historical()
    choices = reconstruct_choices(historical)
    sensitivity = causal_sensitivity_tests()
    if not all(
        (
            sensitivity["different_selections_differ"],
            sensitivity["scores_follow_swapped_selections"],
            sensitivity["identical_selection_and_seed_match"],
            sensitivity["hidden_blocked_from_training"],
        )
    ):
        raise RuntimeError("causal_sensitivity_failed")
    if grant.grant_unused():
        raise RuntimeError("consumed_grant_must_stay_consumed")
    if lock.file_sha256(roles.H16) != roles.H16_SHA:
        raise RuntimeError("h16_scientific_ledger_mutated")
    return {
        "historical_label_preserved": historical["primary_label"],
        "root_cause": ROOT_CAUSE,
        "code": {
            "hidden_loop": "src/nexus/evolution2/persist_reset_science.py:run_bundle",
            "assignment": "for name in METHODS: hidden_raw[name].append(ret)",
            "trusted_evaluator_unused_on_hidden": True,
        },
        "proposer_choices": choices,
        "causal_sensitivity": sensitivity,
        "corrected_design": corrected_design(),
        "scientific": False,
        "collection": False,
        "fitting": False,
        "grant_consumed": True,
        "dispatch_refused": True,
        "h17": "blocked",
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "scientific_ledger_session": [327.869, 3272.131],
        "claims_learning_to_learn": False,
        "is_agi": False,
    }


def write_artifact() -> dict:
    payload = diagnose()
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
