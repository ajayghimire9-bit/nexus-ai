"""Integration and unit tests for the Combined Dual-Engine Architecture &
Learned Investigation Policy (`src/nexus/seed/combined_investigation_engine.py`).
"""
from __future__ import annotations

import copy
from pathlib import Path

from nexus.seed.combined_investigation_engine import (
    AttributedClaim,
    AttributedClaimStore,
    BoundedContractCounterexampleSearcher,
    BoundedEGraphOrganizer,
    CombinedNexusArchitecture,
    ConformalCandidateCalibrator,
    IndependentEvaluator,
    InvestigationObjectiveWeights,
    MechanismBActiveEnvironment,
    OuterInvestigationPolicyTrainer,
    RewriteRule,
    VersionedCapsule,
    VersionedCompiledArtifactMonitor,
    build_training_and_excluded_tasks,
    execute_pipeline,
)
from nexus.seed.lab import SeedWorkspace


def test_three_separately_resettable_knowledge_stores() -> None:
    arch = CombinedNexusArchitecture()
    h0 = arch.knowledge.snapshot_hashes()

    # 1. Populate skills, strategy, and language knowledge
    arch.knowledge.skills.register(VersionedCapsule(
        capsule_id="cap_test_1",
        name="abs_sort",
        domain="sequence_pipeline",
        skeleton_ops=["abs_val", "sort_asc"],
        schema_assumptions={"version": 1},
        source_code="abs_val -> sort_asc",
    ))
    training_pool, _, _ = build_training_and_excluded_tasks()
    curr, meta = arch.curriculum_generator.select_training_curriculum(
        training_pool, budget_tasks=8, mode="curriculum"
    )
    learned_params, _ = OuterInvestigationPolicyTrainer.train_policy(
        curr, meta, arch.objective_weights
    )
    arch.knowledge.learning_strategy.set_parameters(learned_params)
    arch.knowledge.language_knowledge.conformal_quantile_95 = 0.88
    arch.knowledge.language_knowledge.calibrated = True

    h1 = arch.knowledge.snapshot_hashes()
    assert h1["skills_hash"] != h0["skills_hash"]
    assert h1["learning_strategy_hash"] != h0["learning_strategy_hash"]
    assert h1["language_knowledge_hash"] != h0["language_knowledge_hash"]

    # Reset ONLY skills: strategy and language hashes must remain intact
    arch.knowledge.reset_skills()
    h_after_skills = arch.knowledge.snapshot_hashes()
    assert h_after_skills["skills_hash"] == h0["skills_hash"]
    assert h_after_skills["learning_strategy_hash"] == h1["learning_strategy_hash"]
    assert h_after_skills["language_knowledge_hash"] == h1["language_knowledge_hash"]

    # Reset ONLY learning_strategy: language hash must remain intact
    arch.knowledge.reset_learning_strategy()
    h_after_strategy = arch.knowledge.snapshot_hashes()
    assert h_after_strategy["learning_strategy_hash"] == h0["learning_strategy_hash"]
    assert h_after_strategy["language_knowledge_hash"] == h1["language_knowledge_hash"]

    # Reset language_knowledge: all three match initial baseline
    arch.knowledge.reset_language_knowledge()
    h_after_lang = arch.knowledge.snapshot_hashes()
    assert h_after_lang == h0


def test_five_engineering_replacements() -> None:
    arch = CombinedNexusArchitecture()
    rep = arch.run_engineering_replacements_suite()

    # 1. Conformal calibration
    conf = rep["conformal_calibration"]
    assert conf["empirical_top5_coverage"] < 0.95
    assert conf["top5_guarantees_95_percent"] is False
    assert conf["empirical_conformal_coverage"] >= 0.95

    # 2. E-graph equivalence organization vs unsound rule detection
    eg = rep["egraph_organization"]
    assert eg["canonical_representative"] == ["sort_asc"]
    assert eg["sound_rule_check"]["sound_on_probes"] is True
    assert eg["sound_rule_check"]["universal_proof_claimed"] is False
    assert eg["unsound_rule_check"]["sound_on_probes"] is False
    assert len(eg["unsound_rule_check"]["counterexamples"]) > 0

    # 3. Contract counterexample search within bounds
    ce = rep["contract_counterexample_search"]
    assert ce["buggy_function_result"]["status"] == "counterexample_found"
    assert ce["buggy_function_result"]["universal_verification_claimed"] is False
    assert ce["sound_function_result"]["status"] == "no_counterexample_within_bounds"
    assert ce["sound_function_result"]["universal_verification_claimed"] is False

    # 4. Attributed claims with scope, dates, and contradictions
    claims = rep["attributed_claims"]
    assert claims["overlapping_dates_query"]["verified_fact"] is False
    assert claims["overlapping_dates_query"]["has_contradiction"] is True
    assert claims["overlapping_dates_query"]["epistemic_status"] == "contradictory_attributed_claims"
    assert claims["post_v2_expiry_query"]["has_contradiction"] is False
    assert len(claims["post_v2_expiry_query"]["claims"]) == 1

    # 5. Versioned compiled artifact monitoring & invalidation
    mon = rep["versioned_artifact_monitoring"]
    assert mon["valid_assumption_execution"]["executed"] is True
    assert mon["changed_assumption_invalidation"]["executed"] is False
    assert mon["changed_assumption_invalidation"]["status"] == "invalidated_on_assumption_change"
    assert rep["bounded_worker_smoke_passed"] is True


def test_memory_reset_learning_to_learn_and_strategy_ablation(tmp_path: Path) -> None:
    arch = CombinedNexusArchitecture()
    training_pool, excluded_tasks, _ = build_training_and_excluded_tasks()
    oracles = {priv.task_id: priv for _pub, priv in excluded_tasks}
    evaluator = IndependentEvaluator(oracles, arch.objective_weights)

    # Train policy via CurriculumGenerator
    curr_tasks, curr_meta = arch.curriculum_generator.select_training_curriculum(
        training_pool, budget_tasks=8, mode="curriculum"
    )
    learned_params, train_report = OuterInvestigationPolicyTrainer.train_policy(
        curr_tasks, curr_meta, arch.objective_weights
    )
    assert train_report["outer_training_executions"] > 0

    # Clear all acquired skills (Memory-Reset Test) and retain learned strategy
    arch.knowledge.reset_skills()
    arch.knowledge.learning_strategy.set_parameters(learned_params)
    assert len(arch.knowledge.skills.active_capsules()) == 0

    env_learned = MechanismBActiveEnvironment(oracles)
    learned_outcomes = [
        evaluator.evaluate_episode(
            arch.investigation_policy.investigate(
                pub,
                priv.candidate_pool,
                env_learned,
                policy_mode="learned_investigation_policy",
                allow_capsule_retrieval=False,
            )
        )
        for pub, priv in excluded_tasks[:10]
    ]

    # Compare against untrained policy and strong fixed infogain
    env_untrained = MechanismBActiveEnvironment(oracles)
    untrained_outcomes = [
        evaluator.evaluate_episode(
            arch.investigation_policy.investigate(
                pub,
                priv.candidate_pool,
                env_untrained,
                policy_mode="original_untrained_policy",
                allow_capsule_retrieval=False,
            )
        )
        for pub, priv in excluded_tasks[:10]
    ]

    env_infogain = MechanismBActiveEnvironment(oracles)
    infogain_outcomes = [
        evaluator.evaluate_episode(
            arch.investigation_policy.investigate(
                pub,
                priv.candidate_pool,
                env_infogain,
                policy_mode="strong_fixed_infogain",
                allow_capsule_retrieval=False,
            )
        )
        for pub, priv in excluded_tasks[:10]
    ]

    learned_solved = sum(1 for r in learned_outcomes if r["solved"])
    untrained_solved = sum(1 for r in untrained_outcomes if r["solved"])
    learned_execs = sum(r["n_executions"] for r in learned_outcomes)
    infogain_execs = sum(r["n_executions"] for r in infogain_outcomes)
    learned_j = sum(r["objective_J_phi"] for r in learned_outcomes) / len(learned_outcomes)
    untrained_j = sum(r["objective_J_phi"] for r in untrained_outcomes) / len(untrained_outcomes)
    infogain_j = sum(r["objective_J_phi"] for r in infogain_outcomes) / len(infogain_outcomes)

    assert learned_solved == 10
    assert learned_solved > untrained_solved
    assert learned_execs < infogain_execs
    assert learned_j < untrained_j
    assert learned_j < infogain_j

    # Now reset the learned strategy: its advantage must disappear
    arch.knowledge.reset_learning_strategy()
    env_reset = MechanismBActiveEnvironment(oracles)
    reset_outcomes = [
        evaluator.evaluate_episode(
            arch.investigation_policy.investigate(
                pub,
                priv.candidate_pool,
                env_reset,
                policy_mode="learned_investigation_policy",
                allow_capsule_retrieval=False,
            )
        )
        for pub, priv in excluded_tasks[:10]
    ]
    reset_solved = sum(1 for r in reset_outcomes if r["solved"])
    assert reset_solved == untrained_solved

    # Verify Workbench API & Chat integration
    ws = SeedWorkspace(tmp_path / "wb_store", attach_local_runtime=False)
    sid = ws.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]
    api_res = ws.dispatch(dict(
        session_id=sid,
        request={"op": "workbench_investigation_engine", "args": {"sub_op": "status"}},
    ))["response"]
    assert "hashes" in api_res["result"]["result"]


if __name__ == "__main__":
    import tempfile

    test_three_separately_resettable_knowledge_stores()
    test_five_engineering_replacements()
    with tempfile.TemporaryDirectory() as td:
        test_memory_reset_learning_to_learn_and_strategy_ablation(Path(td))
    print("ALL COMBINED INVESTIGATION ENGINE TESTS PASSED")

