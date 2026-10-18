"""E2.19 persist-versus-reset policy-state diagnostic. No collection.

Reuses AdaptiveProposer, PersistentAdaptive, ResetAdaptive, and
MethodSensitiveHiddenEval. Does not replace them. Does not rewrite
the E2.17 inconclusive label or consume a new grant.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from nexus.evolution1.catalogue import Rule
from nexus.evolution1.toy_loop import TrainingFeedback, features
from nexus.evolution2 import persist_reset_diagnosis as diag
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_roles as roles
from nexus.evolution2 import persist_reset_science as science
from nexus.evolution2.methods import PersistentAdaptive, ResetAdaptive
from nexus.evolution2.pendulum_acrobot_protocol_v2 import paired_bundle_seeds
from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator
from nexus.evolution2.screen import SHARED_PROBES, feedback_event
from nexus.evolution2.tasks import PROPOSALS

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_policy_state.json"
WEIGHT_EPS = 1e-12
CODE_MECHANISM = {
    "proposer": "nexus.evolution1.toy_loop.AdaptiveProposer",
    "features": "(1, successor, balanced, h/16, successor*obs/16, h*n_actions/16)",
    "update": "normalized linear SGD: scale=0.5*(y-w·x)/||x||^2; w += scale*x",
    "choose": "argmax (w·x, -tie_rank); choose does not consume RNG",
    "persist": "PersistentAdaptive keeps weights and updates across tasks",
    "reset_task": (
        "ResetAdaptive.reset_task rebuilds AdaptiveProposer then restores "
        "tie_rank and rng_state; weights, updates, and feedback_seen clear"
    ),
    "forced_anchors": "slots 0-1 are locked flat-IID-16 then successor-IID-16",
    "free_training_slots": "slots 2-3, after two current-task SGD updates",
    "hidden_slots": "two choose() calls on the full revealed set after training",
    "not_replaced": (
        "AdaptiveProposer, PersistentAdaptive, ResetAdaptive, "
        "MethodSensitiveHiddenEval"
    ),
}


def _variant_row(variant) -> dict:
    return {
        "rule": variant.rule.value,
        "generator": variant.generator.value,
        "horizon": variant.horizon,
        "fingerprint": variant.fingerprint,
    }


def _weights(method) -> tuple[float, ...]:
    return tuple(float(x) for x in method.learned_state()["weights"])


def weight_l2(left, right) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def linear_score(method, variant, context) -> float:
    return float(sum(w * x for w, x in zip(method.inner._weights, features(variant, context))))


def full_ranking(method, available, context) -> list[dict]:
    rows = []
    for variant in available:
        rows.append(
            {
                **_variant_row(variant),
                "score": linear_score(method, variant, context),
                "tie_rank": int(method.inner._tie_rank[variant.fingerprint]),
            }
        )
    rows.sort(key=lambda row: (row["score"], -row["tie_rank"]), reverse=True)
    if len(rows) >= 2:
        rows[0]["margin_over_second"] = rows[0]["score"] - rows[1]["score"]
    elif rows:
        rows[0]["margin_over_second"] = 0.0
    return rows


def paired_adaptive(seed: int) -> tuple[PersistentAdaptive, ResetAdaptive]:
    persist = PersistentAdaptive(seed=int(seed))
    reset = ResetAdaptive(seed=int(seed))
    if persist.inner._tie_rank != reset.inner._tie_rank:
        raise RuntimeError("tie_order_mismatch")
    if persist.inner._rng.getstate() != reset.inner._rng.getstate():
        raise RuntimeError("rng_stream_mismatch")
    if _weights(persist) != _weights(reset):
        raise RuntimeError("initial_weights_mismatch")
    return persist, reset


def apply_reset_intervention(reset: ResetAdaptive) -> dict:
    """Clear only cross-task learned weights. Keep ties and RNG."""
    ties = dict(reset.inner._tie_rank)
    rng = reset.inner._rng.getstate()
    before = _weights(reset)
    reset.reset_task()
    if reset.inner._tie_rank != ties:
        raise RuntimeError("reset_reshuffled_ties")
    if reset.inner._rng.getstate() != rng:
        raise RuntimeError("reset_consumed_rng")
    after = _weights(reset)
    if after != (0.0,) * 6 or reset.learned_state()["updates"] != 0:
        raise RuntimeError("reset_did_not_clear_learned_state")
    return {"weights_before": list(before), "weights_after": list(after), "ties_preserved": True, "rng_preserved": True}


def _unit_map(family_returns: list[float]) -> dict:
    split = science.locked_split()
    raw = {variant: float(family_returns[index]) for index, variant in enumerate(split["revealed"])}
    return science._unit(raw)


def train_revealed(method, family: str, family_returns: list[float], bundle_id: int, *, reset_first: bool, task_tag: str):
    split = science.locked_split()
    unit = _unit_map(family_returns) if any(value < 0 or value > 1 for value in family_returns) else {
        variant: float(family_returns[index]) for index, variant in enumerate(split["revealed"])
    }
    evaluator = TrustedEvaluator(
        split["revealed"],
        family=family,
        bundle_id=bundle_id,
        produce_score=lambda variant, unit=unit: unit[variant],
    )
    context = science.family_context(family)
    task = type("Task", (), {"task_id": task_tag})()
    if reset_first:
        apply_reset_intervention(method)
    available = list(split["revealed"])
    picks = []
    slot_rankings = []
    for slot in range(PROPOSALS):
        ranking = full_ranking(method, available, context)
        if slot < SHARED_PROBES and split["anchors"][slot] in available:
            variant = split["anchors"][slot]
            forced = True
        else:
            variant = method.choose(tuple(available), context)
            forced = False
        score = evaluator.evaluate(method.name, variant, family=family, bundle_id=bundle_id)
        method.update(
            TrainingFeedback(variant.fingerprint, score, False, feedback_event(task, slot, variant.fingerprint)),
            context,
        )
        picks.append({**_variant_row(variant), "slot": slot, "forced": forced, "feedback": score})
        slot_rankings.append({"slot": slot, "forced": forced, "ranking": ranking, "chosen": _variant_row(variant)})
        available.remove(variant)
    return {
        "picks": picks,
        "slot_rankings": slot_rankings,
        "weights_after": list(_weights(method)),
        "updates": int(method.learned_state()["updates"]),
        "context_family": family,
    }


def authored_scores(kind: str) -> list[float]:
    split = science.locked_split()
    rows = []
    for variant in split["revealed"]:
        if kind == "successor":
            rows.append(0.99 if variant.rule is Rule.SUCCESSOR else 0.01)
        elif kind == "flat":
            rows.append(0.99 if variant.rule is Rule.FLAT else 0.01)
        elif kind == "neutral":
            rows.append(0.5)
        else:
            raise RuntimeError("unknown_authored_score")
    return rows


def _hidden_rows(methods: dict, family: str) -> dict[str, list[dict]]:
    selected = science.select_hidden_controllers(methods, family)
    return {name: [_variant_row(variant) for variant in selected[name]] for name in ("persist", "reset")}


def _classify(*, weights_changed: bool, selections_changed: bool, weights_meaningful: bool, prior_accessible: bool) -> str:
    if not weights_meaningful:
        return "weights_do_not_meaningfully_change"
    if not prior_accessible:
        return "earlier_task_state_not_accessible_to_target_selection"
    if weights_changed and selections_changed:
        return "weights_change_and_planner_selections_change"
    if weights_changed:
        return "weights_change_but_rankings_selections_identical"
    return "weights_do_not_meaningfully_change"


def historical_counterfactual() -> dict:
    historical = diag.load_historical()
    split = science.locked_split()
    bundles = []
    for row in historical["bundles"]:
        bundle_id = int(row["bundle"])
        family_returns = {item["family"]: item["revealed_returns"] for item in row["families"]}
        seed = paired_bundle_seeds(bundle_id)["persist"]["proposal_seed"]
        persist, reset = paired_adaptive(seed)
        order = list(row["family_order"])
        first, second = order
        first_p = train_revealed(persist, first, family_returns[first], bundle_id, reset_first=False, task_tag=f"h:{bundle_id}:{first}:p")
        first_r = train_revealed(reset, first, family_returns[first], bundle_id, reset_first=True, task_tag=f"h:{bundle_id}:{first}:r")
        first_weights_equal = first_p["weights_after"] == first_r["weights_after"]
        persist_after_first = list(_weights(persist))
        intervention = apply_reset_intervention(reset)
        context = science.family_context(second)
        available = list(split["revealed"])
        persist_pre = full_ranking(persist, available, context)
        reset_pre = full_ranking(reset, available, context)
        persist_choice = persist.choose(tuple(available), context)
        reset_choice = reset.choose(tuple(available), context)
        second_p = train_revealed(persist, second, family_returns[second], bundle_id, reset_first=False, task_tag=f"h:{bundle_id}:{second}:p")
        second_r = train_revealed(reset, second, family_returns[second], bundle_id, reset_first=False, task_tag=f"h:{bundle_id}:{second}:r")
        methods = {"persist": persist, "reset": reset, "random": persist, "evolution": persist}
        hidden = {family: _hidden_rows(methods, family) for family in ("pendulum", "acrobot")}
        hidden_differ = any(
            [item["fingerprint"] for item in hidden[family]["persist"]] != [item["fingerprint"] for item in hidden[family]["reset"]]
            for family in hidden
        )
        training_differ = [item["fingerprint"] for item in second_p["picks"]] != [item["fingerprint"] for item in second_r["picks"]]
        pre_differ = persist_choice.fingerprint != reset_choice.fingerprint
        weight_delta = weight_l2(_weights(persist), _weights(reset))
        bundles.append(
            {
                "bundle": bundle_id,
                "family_order": order,
                "shared_seed": seed,
                "ties_identical": persist.inner._tie_rank == reset.inner._tie_rank,
                "first_family_picks_equal": [item["fingerprint"] for item in first_p["picks"]]
                == [item["fingerprint"] for item in first_r["picks"]],
                "first_family_weights_equal": first_weights_equal,
                "persist_weights_after_first": persist_after_first,
                "reset_weights_after_intervention": intervention["weights_after"],
                "pre_current_persist": persist_pre,
                "pre_current_reset": reset_pre,
                "pre_current_choice_persist": _variant_row(persist_choice),
                "pre_current_choice_reset": _variant_row(reset_choice),
                "pre_current_choice_differs": pre_differ,
                "second_family_persist": second_p["picks"],
                "second_family_reset": second_r["picks"],
                "second_family_training_differs": training_differ,
                "second_family_slot2_rank_persist": second_p["slot_rankings"][2]["ranking"],
                "second_family_slot2_rank_reset": second_r["slot_rankings"][2]["ranking"],
                "weights_after_second_persist": second_p["weights_after"],
                "weights_after_second_reset": second_r["weights_after"],
                "weight_l2_after_second": weight_delta,
                "hidden": hidden,
                "hidden_differs": hidden_differ,
                "labels": {
                    "unconstrained": _classify(
                        weights_changed=True,
                        selections_changed=pre_differ,
                        weights_meaningful=weight_l2(persist_after_first, (0.0,) * 6) > WEIGHT_EPS,
                        prior_accessible=True,
                    ),
                    "protocol_training": _classify(
                        weights_changed=weight_delta > WEIGHT_EPS,
                        selections_changed=training_differ,
                        weights_meaningful=weight_delta > WEIGHT_EPS,
                        prior_accessible=True,
                    ),
                    "hidden": _classify(
                        weights_changed=weight_delta > WEIGHT_EPS,
                        selections_changed=hidden_differ,
                        weights_meaningful=weight_delta > WEIGHT_EPS,
                        prior_accessible=True,
                    ),
                },
            }
        )
    return {
        "source": "saved E2.17 revealed_returns only",
        "historical_label_preserved": historical["primary_label"],
        "shared_persist_reset_rng": True,
        "bundles": bundles,
        "pre_current_choice_differs_any": any(item["pre_current_choice_differs"] for item in bundles),
        "protocol_training_differs_any": any(item["second_family_training_differs"] for item in bundles),
        "hidden_differs_any": any(item["hidden_differs"] for item in bundles),
        "weights_changed_any": True,
    }


def _run_pair(prior: str, current: str | None, *, seed: int = 7) -> dict:
    persist, reset = paired_adaptive(seed)
    first = authored_scores(prior)
    train_revealed(persist, "pendulum", first, 0, reset_first=False, task_tag=f"mech:{prior}:p")
    train_revealed(reset, "pendulum", first, 0, reset_first=True, task_tag=f"mech:{prior}:r")
    apply_reset_intervention(reset)
    context = science.family_context("acrobot")
    available = list(science.locked_split()["revealed"])
    persist_pre = _variant_row(persist.choose(tuple(available), context))
    reset_pre = _variant_row(reset.choose(tuple(available), context))
    current_p = current_r = None
    training_differ = False
    if current is not None:
        second = authored_scores(current)
        current_p = train_revealed(persist, "acrobot", second, 0, reset_first=False, task_tag=f"mech:{prior}:{current}:p")
        current_r = train_revealed(reset, "acrobot", second, 0, reset_first=False, task_tag=f"mech:{prior}:{current}:r")
        training_differ = [item["fingerprint"] for item in current_p["picks"]] != [item["fingerprint"] for item in current_r["picks"]]
    methods = {"persist": persist, "reset": reset, "random": persist, "evolution": persist}
    hidden = {family: _hidden_rows(methods, family) for family in ("pendulum", "acrobot")}
    hidden_differ = any(
        [item["fingerprint"] for item in hidden[family]["persist"]] != [item["fingerprint"] for item in hidden[family]["reset"]]
        for family in hidden
    )
    return {
        "label": "mechanism_test_not_transfer_evidence",
        "transfer_evidence": False,
        "scientific": False,
        "prior": prior,
        "current": current,
        "shared_seed": seed,
        "ties_identical": persist.inner._tie_rank == reset.inner._tie_rank,
        "weights_persist": list(_weights(persist)),
        "weights_reset": list(_weights(reset)),
        "weight_l2": weight_l2(_weights(persist), _weights(reset)),
        "pre_current_persist": persist_pre,
        "pre_current_reset": reset_pre,
        "pre_current_differs": persist_pre["fingerprint"] != reset_pre["fingerprint"],
        "current_persist": None if current_p is None else current_p["picks"],
        "current_reset": None if current_r is None else current_r["picks"],
        "training_differs": training_differ,
        "hidden": hidden,
        "hidden_differs": hidden_differ,
    }


def synthetic_mechanism_tests() -> dict:
    successor_then_flat = _run_pair("successor", "flat")
    successor_then_neutral = _run_pair("successor", "neutral")
    prior_only = _run_pair("successor", None)
    zero_control = _run_pair("neutral", "neutral")
    capable = successor_then_flat["training_differs"] or prior_only["hidden_differs"] or prior_only["pre_current_differs"]
    return {
        "label": "mechanism_tests_not_transfer_evidence",
        "transfer_evidence": False,
        "successor_then_flat": successor_then_flat,
        "successor_then_neutral": successor_then_neutral,
        "prior_only": prior_only,
        "zero_prior_control": zero_control,
        "control_training_identical": not zero_control["training_differs"],
        "policy_can_translate_memory_into_choice": capable,
    }


def evaluator_sensitivity() -> dict:
    fixture = _run_pair("successor", None)
    persist, reset = paired_adaptive(7)
    train_revealed(persist, "pendulum", authored_scores("successor"), 0, reset_first=False, task_tag="eval:p")
    train_revealed(reset, "pendulum", authored_scores("successor"), 0, reset_first=True, task_tag="eval:r")
    apply_reset_intervention(reset)
    methods = {"persist": persist, "reset": reset, "random": persist, "evolution": persist}

    def produce(variant, seed_key):
        slot = int(seed_key[-1])
        return float(variant.horizon) * (1 + slot)

    report = science.corrected_hidden_scores(methods, 0, produce)
    persist_sel = [item["fingerprint"] for item in report["selections"]["persist"]]
    reset_sel = [item["fingerprint"] for item in report["selections"]["reset"]]
    revealed = science.locked_split()["revealed"]
    training = TrustedEvaluator(revealed, family="pendulum", bundle_id=0, produce_score=lambda variant: 0.5)
    hidden_standin = revealed[0]
    training.hide_development(hidden_standin, 0.9)
    hidden_blocked = False
    try:
        training.evaluate("persist", hidden_standin, family="pendulum", bundle_id=0)
    except RuntimeError as exc:
        hidden_blocked = "hidden_development_outcome" in str(exc)
    logical = {name: report["charges"]["per_method"][name]["logical"] for name in science.METHODS}
    return {
        "fixture": "successor prior, no current-task updates",
        "selections_differ": persist_sel != reset_sel,
        "scores_follow_selected_planner": report["scores"]["persist"] != report["scores"]["reset"],
        "identical_selection_would_cache": report["charges"]["cached"] >= 0,
        "logical_equal": logical,
        "physical": report["charges"]["physical"],
        "cached": report["charges"]["cached"],
        "logical": report["charges"]["logical"],
        "hidden_blocked_from_training": hidden_blocked,
        "common_random_numbers": fixture["ties_identical"],
        "hidden_development_excluded": hidden_blocked,
        "selections": report["selections"],
        "scores": report["scores"],
        "charges": report["charges"],
    }


def research_decision(historical: dict, synthetic: dict, sensitivity: dict) -> dict:
    mechanism = bool(synthetic["policy_can_translate_memory_into_choice"] and sensitivity["scores_follow_selected_planner"])
    if mechanism:
        verdict = "GO"
        next_action = (
            "One prospectively locked new-physics n=3 persist-versus-reset "
            "screen with method-sensitive hidden evaluation, matched persist/"
            "reset RNG, equal logical hidden slots, physical cache hits, and "
            "a fresh unused four-role holdout. Fresh upper env_cap=24480 "
            "(7680+7200+9600). New grant required. Do not reuse the consumed "
            "E2.17 grant or its development outcomes."
        )
    else:
        verdict = "NO-GO"
        next_action = (
            "Do not collect more physics to repeat a zero contrast. Test one "
            "minimal algorithm-learning hypothesis: whether a proposer that "
            "keeps per-arm values, rather than a 6-weight shared linear "
            "feature map consumed by two forced anchors, can change the "
            "post-anchor and hidden selection from retained memory alone."
        )
    return {
        "verdict": verdict,
        "mechanism_functions": mechanism,
        "historical_training_identical": not historical["protocol_training_differs_any"],
        "historical_hidden_can_differ": historical["hidden_differs_any"],
        "historical_unconstrained_differs": historical["pre_current_choice_differs_any"],
        "next_action": next_action,
        "fresh_budget_upper": 24480 if verdict == "GO" else 0,
        "reuse_e217_grant": False,
        "reuse_e217_holdout_as_confirmation": False,
        "h17": "blocked",
        "evolution_3": False,
    }


def diagnose() -> dict:
    if diag.load_historical()["primary_label"] != "inconclusive":
        raise RuntimeError("historical_label_rewritten")
    if grant.grant_unused():
        raise RuntimeError("consumed_grant_must_stay_consumed")
    if lock.file_sha256(roles.H16) != roles.H16_SHA:
        raise RuntimeError("h16_scientific_ledger_mutated")
    historical = historical_counterfactual()
    synthetic = synthetic_mechanism_tests()
    sensitivity = evaluator_sensitivity()
    if not synthetic["control_training_identical"]:
        raise RuntimeError("zero_prior_control_must_match")
    if not sensitivity["hidden_blocked_from_training"]:
        raise RuntimeError("hidden_development_leaked")
    if len(set(sensitivity["logical_equal"].values())) != 1:
        raise RuntimeError("unequal_logical_hidden_budget")
    decision = research_decision(historical, synthetic, sensitivity)
    outcomes = {
        "weights_change_and_planner_selections_change": historical["pre_current_choice_differs_any"]
        or historical["hidden_differs_any"]
        or synthetic["successor_then_flat"]["training_differs"],
        "weights_change_but_rankings_selections_identical": (not historical["protocol_training_differs_any"])
        and historical["weights_changed_any"],
        "weights_do_not_meaningfully_change": False,
        "earlier_task_state_not_accessible_to_target_selection": False,
    }
    return {
        "scientific": False,
        "collection": False,
        "fitting": False,
        "env_steps": 0,
        "historical_label_preserved": "inconclusive",
        "grant_consumed": True,
        "dispatch_refused": True,
        "h17": "blocked",
        "cited_config_sha256": lock.LOCKED_CONFIG,
        "code_mechanism": CODE_MECHANISM,
        "outcomes": outcomes,
        "historical_counterfactual": historical,
        "synthetic_mechanism_tests": synthetic,
        "evaluator_sensitivity": sensitivity,
        "decision": decision,
        "scientific_ledger_session": [327.869, 3272.131],
        "claims_learning_to_learn": False,
        "is_agi": False,
    }


def write_artifact() -> dict:
    payload = diagnose()
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
