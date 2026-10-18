"""E2.21 executable method-sensitive scoring. Development fixtures only.

Connects MethodSensitiveHiddenEval to decide() on synthetic models.
Does not collect, fit, name a holdout, or authorize science.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_method_sensitive as nxt
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_roles as roles
from nexus.evolution2 import persist_reset_science as science
from nexus.evolution2.bindings import reviewed_binding
from nexus.evolution2.methods import PersistentAdaptive, ResetAdaptive, make_methods
from nexus.evolution2.pendulum_acrobot_protocol_n3_micro import (
    BONFERRONI_T_CRIT_DF2,
    N_BUNDLES,
    REVEALED_VARIANTS_PER_FAMILY,
)
from nexus.evolution2.pendulum_acrobot_protocol_v2 import (
    BONFERRONI_T_CRIT_DF9,
    EPISODE_STEPS,
    SOURCE_TRAIN_STEPS,
    SOURCE_VAL_STEPS,
    paired_bundle_seeds,
)
from nexus.evolution2.planner_adapter import FakeStepModel
from nexus.evolution2.screen import SHARED_PROBES, feedback_event
from nexus.evolution1.toy_loop import TrainingFeedback
from nexus.evolution2.tasks import PROPOSALS

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "artifacts" / "evolution2_persist_reset_scoring.json"
E217_WALL_S = 22.027
E217_STEPS = 17_280
E29_SIX_FIT_S = 1.215
E214_9600_PLANNER_S = 27.7
STANDING_TIME_S = 900
STANDING_ENV = 100_000
SESSION_REMAINING_S = 3272.131
N10_BUNDLES = 10
N10_FITS = 20


def persist_reset_matched(seed: int = 7) -> dict:
    persist = PersistentAdaptive(seed=int(seed))
    reset = ResetAdaptive(seed=int(seed))
    if persist.inner._tie_rank != reset.inner._tie_rank:
        raise RuntimeError("persist_reset_tie_mismatch")
    if persist.inner._rng.getstate() != reset.inner._rng.getstate():
        raise RuntimeError("persist_reset_rng_mismatch")
    if persist.learned_state()["weights"] != reset.learned_state()["weights"]:
        raise RuntimeError("persist_reset_initial_weights_mismatch")
    return {
        "matched_initial_rng": True,
        "matched_tie_order": True,
        "matched_initial_weights": True,
        "only_intended_difference": "retained_cross_task_weights",
        "random_and_evolution_separate_controls": True,
    }


def feedback_normalization_boundary_audit():
    """Fixed synthetic integration audit: no planner, environment or model."""
    import time
    from nexus.evolution1.catalogue import digest
    from nexus.evolution1.toy_loop import ANCHORS,AdaptiveProposer,VARIANTS
    from nexus.evolution2.pendulum_acrobot_protocol_v2_pilot import TrustedEvaluator,feedback_reference_digest
    t0,cpu0 = time.perf_counter(),time.process_time()
    result_path = ROOT/"artifacts/evolution2_26_feedback_boundary.json"
    historical = {str(p.relative_to(ROOT)):lock.file_sha256(p) for p in (ROOT/"artifacts").glob("*.json") if p!=result_path}
    reference = tuple(ANCHORS)
    expected = feedback_reference_digest("pendulum",0,reference) # before scores
    calls = 0
    def producer(table):
        def get(variant):
            nonlocal calls
            calls += 1
            return table[variant]
        return get
    source = TrustedEvaluator(VARIANTS,family="pendulum",bundle_id=0,
               produce_score=producer({reference[0]:-10.,reference[1]:10.,VARIANTS[0]:999.}))
    for v in reference:source.evaluate("persist",v)
    snapshot = source.freeze_feedback_scale("persist",reference=reference,expected_reference_digest=expected)
    snapshot_before = snapshot.payload()
    outputs = []
    for extreme in (-1e8,1e8):
        q = TrustedEvaluator(VARIANTS,family="pendulum",bundle_id=1,
              produce_score=producer({reference[0]:2.,reference[1]:8.,VARIANTS[0]:extreme}))
        policy = AdaptiveProposer(seed=7)
        normalized = []
        for slot,v in enumerate(reference):
            unit = snapshot.unit(q.evaluate("persist",v)); normalized.append(unit)
            policy.update(TrainingFeedback(v.fingerprint,unit,False,digest(["boundary",slot])),science.family_context("pendulum"))
        choice = policy.choose(tuple(v for v in VARIANTS if v not in reference),science.family_context("pendulum"))
        outputs.append({"unobserved_extreme":extreme,"public_feedback":normalized,
                        "policy_state":policy.learned_state(),"choice":choice.fingerprint,
                        "query_raw_lookups":q.physical})
    source.evaluate("persist",VARIANTS[0])
    blocked = False
    try:source.freeze_feedback_scale("persist",reference=reference,expected_reference_digest=expected)
    except RuntimeError as e:blocked = "already_frozen" in str(e)
    same = all(outputs[0][key]==outputs[1][key] for key in ("public_feedback","policy_state","choice"))
    unchanged = snapshot_before==snapshot.payload()
    preserved = all(lock.file_sha256(ROOT/p)==h for p,h in historical.items())
    complete = same and unchanged and blocked and preserved and calls==7
    if not complete or time.perf_counter()-t0 >= 10:
        raise RuntimeError("feedback_boundary_audit_failed_or_capped")
    return {"declared_complete":True,"scientific":False,"base_sha":"5b9a243cfb4aa348f52b7a60c091c59fd174f183",
            "cases":outputs,"reference_snapshot":snapshot.payload(),"snapshot_digest":snapshot.snapshot_digest,
            "same_feedback_weights_choice":same,"future_cache_growth_preserves_snapshot":unchanged,
            "refit_blocked":blocked,"historical_artifacts_preserved":preserved,
            "historical_artifacts_sha256":historical,
            "clipping_examples":[snapshot.transform(-20.),snapshot.transform(20.)],
            "resources":{"wall_s":time.perf_counter()-t0,"cpu_s":time.process_time()-cpu0,
                         "synthetic_raw_lookups":calls,"real_interactions":0,"imagined_transitions":0,
                         "model_inference":0,"neural_training":0,"optimizer_steps":0,"cap_s":10},
            "scientific_ledger":{"used_s":327.869,"remaining_s":3272.131},
            "limitations":["Only the opt-in path is tested; historical runners remain unchanged.",
                           "Trusted raw producers and precommitted reference provenance remain necessary.",
                           "Saturation loses ranking information outside training range; report raw returns and clipping.",
                           "This is synthetic interface evidence, not control, generalization or learning-to-learn."]}


def _synthetic_model(family: str):
    binding = reviewed_binding(family)
    return FakeStepModel(binding.obs_dim, binding.n_actions)


def _fixture_obs(family: str) -> np.ndarray:
    return np.zeros(reviewed_binding(family).obs_dim, dtype=np.float32)


def train_equal_budget(methods: dict, family: str, unit: dict, bundle_id: int) -> dict:
    context = science.family_context(family)
    task = type("Task", (), {"task_id": f"fix:{family}:{bundle_id}"})()
    counts = {}
    for name, method in methods.items():
        if method.resets:
            method.reset_task()
        available = list(science.locked_split()["revealed"])
        for slot in range(PROPOSALS):
            if slot < SHARED_PROBES and science.locked_split()["anchors"][slot] in available:
                variant = science.locked_split()["anchors"][slot]
            else:
                variant = method.choose(tuple(available), context)
            score = float(unit[variant])
            method.update(
                TrainingFeedback(variant.fingerprint, score, False, feedback_event(task, slot, variant.fingerprint)),
                context,
            )
            available.remove(variant)
        counts[name] = PROPOSALS
    if len(set(counts.values())) != 1:
        raise RuntimeError("unequal_training_budget")
    return counts


def executable_fixture_path() -> dict:
    persist_reset_matched(7)
    nxt.persist_reset_crn(0)
    split = science.locked_split()
    revealed = split["revealed"]
    revealed_raw = {variant: float(index - 2) for index, variant in enumerate(revealed)}
    scale = science.FrozenRevealedScale(revealed_raw)
    if scale.frozen_before_hidden is not True:
        raise RuntimeError("scale_not_frozen")
    unit = {variant: scale.unit(revealed_raw[variant]) for variant in revealed}
    methods = {short: make_methods(7)[inner] for short, inner in science.METHOD_KEYS.items()}
    train_equal_budget(methods, "pendulum", unit, 0)
    models = {family: _synthetic_model(family) for family in ("pendulum", "acrobot")}
    obs = {family: _fixture_obs(family) for family in ("pendulum", "acrobot")}

    def produce(variant, seed_key):
        family = seed_key[2]
        slot = int(seed_key[-1])
        seed = science.hidden_rollout_seed(0, family, slot)
        return science.fixture_hidden_return(family, variant, models[family], obs[family], seed=seed)

    high, low = revealed[0], revealed[1]
    forced_swap = {
        family: {
            "persist": (high, revealed[2]),
            "reset": (low, revealed[3]),
            "random": (high, revealed[2]),
            "evolution": (low, revealed[3]),
        }
        for family in ("pendulum", "acrobot")
    }
    swapped = science.corrected_hidden_scores(methods, 0, produce, scale=scale, forced_selections=forced_swap)
    forced_same = {
        family: {name: (high, revealed[2]) for name in science.METHODS} for family in ("pendulum", "acrobot")
    }
    identical = science.corrected_hidden_scores(methods, 0, produce, scale=scale, forced_selections=forced_same)
    overlap = [{"fingerprint": high.fingerprint, "score": unit[high], "provenance": "revealed"}]
    swapped["evaluator"].training_must_not_see(overlap)
    leaked = False
    hidden = swapped["hidden_outcomes"][0]
    try:
        swapped["evaluator"].training_must_not_see(
            [{"fingerprint": hidden["fingerprint"], "score": hidden["unit"], "provenance": science.HIDDEN_PROVENANCE, "outcome_id": hidden["outcome_id"]}]
        )
    except RuntimeError as exc:
        leaked = "hidden_development_leaked_into_training" in str(exc)
    if not leaked:
        raise RuntimeError("hidden_return_provenance_not_enforced")
    logical = [identical["charges"]["per_method"][name]["logical"] for name in science.METHODS]
    if logical != [4, 4, 4, 4]:
        raise RuntimeError("unequal_logical_hidden_budget")
    if identical["charges"]["physical"] + identical["charges"]["cached"] != identical["charges"]["logical"]:
        raise RuntimeError("charge_identity_failed")
    return {
        "scientific": False,
        "collection": False,
        "gymnasium": False,
        "env_steps": 0,
        "controller_is_method_selected_planner": True,
        "scale_frozen_before_hidden": True,
        "forced_swap_scores_differ": swapped["scores"]["persist"] != swapped["scores"]["reset"],
        "identical_selection_scores_equal": identical["scores"]["persist"] == identical["scores"]["reset"] == identical["scores"]["random"],
        "identical_physical": identical["charges"]["physical"],
        "identical_cached": identical["charges"]["cached"],
        "identical_logical": identical["charges"]["logical"],
        "logical_equal": logical,
        "fingerprint_overlap_allowed": True,
        "hidden_return_blocked_from_training": leaked,
        "persist_reset": persist_reset_matched(7),
    }


def screen_budget(n_bundles: int) -> dict:
    source = n_bundles * 2 * (SOURCE_TRAIN_STEPS + SOURCE_VAL_STEPS)
    revealed = n_bundles * 2 * REVEALED_VARIANTS_PER_FAMILY * EPISODE_STEPS
    hidden_logical = n_bundles * 2 * science.HIDDEN_SLOTS_PER_FAMILY * len(science.METHODS)
    hidden_upper = hidden_logical * EPISODE_STEPS
    hidden_collide = n_bundles * 2 * science.HIDDEN_SLOTS_PER_FAMILY * EPISODE_STEPS
    fits = n_bundles * 2
    return {
        "n_bundles": n_bundles,
        "source": source,
        "revealed": revealed,
        "hidden_physical_upper": hidden_upper,
        "hidden_physical_if_cache": hidden_collide,
        "fresh_total_upper": source + revealed + hidden_upper,
        "fresh_total_if_identical_selections": source + revealed + hidden_collide,
        "fits": fits,
        "df": n_bundles - 1,
    }


def compare_screens() -> dict:
    n3 = screen_budget(N_BUNDLES)
    n10 = screen_budget(N10_BUNDLES)
    if n3["fresh_total_upper"] != 24_480:
        raise RuntimeError("n3_upper_mismatch")
    if n10["fresh_total_upper"] != 81_600:
        raise RuntimeError("n10_upper_mismatch")
    n3_plan = {
        **n3,
        "bonferroni_t": BONFERRONI_T_CRIT_DF2,
        "fits_measured": True,
        "six_fit_clock_s": E29_SIX_FIT_S,
        "e217_wall_s": E217_WALL_S,
        "planned_wall_s": E217_WALL_S * n3["fresh_total_upper"] / E217_STEPS,
        "env_fits_standing": n3["fresh_total_upper"] <= STANDING_ENV,
        "time_fits_standing": True,
        "planning_only": True,
        "e217_is_not_proof_of_new_cost": True,
    }
    n10_plan = {
        **n10,
        "bonferroni_t": BONFERRONI_T_CRIT_DF9,
        "fits_measured": False,
        "twenty_fit_clock_s": None,
        "twenty_fit_planning_s": E29_SIX_FIT_S * N10_FITS / 6,
        "e217_wall_s": E217_WALL_S,
        "planned_wall_from_e217_s": E217_WALL_S * n10["fresh_total_upper"] / E217_STEPS,
        "planner_prior_from_e214_s": E214_9600_PLANNER_S
        * (n10["revealed"] + n10["hidden_physical_upper"])
        / 9600,
        "env_fits_standing": n10["fresh_total_upper"] <= STANDING_ENV,
        "time_fits_standing_if_linear": (
            E217_WALL_S * n10["fresh_total_upper"] / E217_STEPS
            + E29_SIX_FIT_S * N10_FITS / 6
        )
        < STANDING_TIME_S,
        "planning_only": True,
        "e217_is_not_proof_of_new_cost": True,
        "twenty_fit_unmeasured": True,
    }
    n10_fits_resources = bool(n10_plan["env_fits_standing"] and n10_plan["time_fits_standing_if_linear"])
    if n10_fits_resources:
        verdict = "n10_prospective"
        next_experiment = (
            "One new-physics n=10 persist-versus-reset screen with "
            "method-sensitive hidden evaluation, matched persist/reset RNG, "
            "equal logical slots, physical cache hits, twenty residual fits, "
            "fresh unused four-role physics, and env_cap=81600. New grant "
            "required. Do not rewrite E2.17 or E2.20. Do not reuse the "
            "consumed grant or H17. Twenty-fit wall remains unmeasured; "
            "E2.17/E2.9 times are planning evidence only."
        )
        env_cap = 81_600
    else:
        verdict = "n3_exploratory"
        next_experiment = (
            "One new-physics n=3 persist-versus-reset screen with "
            "method-sensitive hidden evaluation and env_cap=24480. New unused "
            "four-role holdout and grant required."
        )
        env_cap = 24_480
    return {
        "n3": n3_plan,
        "n10": n10_plan,
        "standing_time_s": STANDING_TIME_S,
        "standing_env": STANDING_ENV,
        "session_remaining_s": SESSION_REMAINING_S,
        "does_not_rewrite_locked_protocols": True,
        "verdict": verdict,
        "recommended_env_cap": env_cap,
        "next_experiment": next_experiment,
        "n10_fits_standing_numeric_caps": n10_fits_resources,
    }


def diagnose() -> dict:
    if grant.grant_unused():
        raise RuntimeError("e217_grant_must_stay_consumed")
    if lock.file_sha256(roles.H16) != roles.H16_SHA:
        raise RuntimeError("h16_scientific_ledger_mutated")
    path = executable_fixture_path()
    comparison = compare_screens()
    if not path["forced_swap_scores_differ"] or not path["identical_selection_scores_equal"]:
        raise RuntimeError("executable_scoring_failed")
    if not path["hidden_return_blocked_from_training"] or not path["fingerprint_overlap_allowed"]:
        raise RuntimeError("isolation_provenance_failed")
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
        "path": {key: value for key, value in path.items() if key != "persist_reset"} | path["persist_reset"],
        "screens": comparison,
        "decision": {
            "verdict": comparison["verdict"],
            "next_experiment": comparison["next_experiment"],
            "env_cap": comparison["recommended_env_cap"],
            "reuse_e217_grant": False,
            "reuse_e217_holdout": False,
        },
        "scientific_ledger_session": [327.869, 3272.131],
        "claims_learning_to_learn": False,
        "is_agi": False,
    }


def write_artifact() -> dict:
    payload = diagnose()
    RESULTS.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
