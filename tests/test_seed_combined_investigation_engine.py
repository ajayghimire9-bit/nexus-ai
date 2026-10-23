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
    EqualizedControllerConfig,
    EqualizedInvestigationEngineV2,
    EvaluatorPrivateTaskOracle,
    IndependentEvaluator,
    InvestigationObjectiveWeights,
    MechanismBActiveEnvironment,
    OuterInvestigationPolicyTrainer,
    RewriteRule,
    VersionedCapsule,
    VersionedCompiledArtifactMonitor,
    build_training_and_excluded_tasks,
    build_v2_disjoint_tasks_and_real_repos,
    execute_pipeline,
    verify_disjoint_task_inputs,
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


def test_v2_equalized_unconfounded_engine() -> None:
    training_pool, source_tasks, excluded_tasks = build_v2_disjoint_tasks_and_real_repos()

    # 1. Verify strict pairwise disjointness of support, probe pool, and assessment inputs
    for task in training_pool + source_tasks + excluded_tasks:
        d_check = verify_disjoint_task_inputs(task)
        assert d_check["pairwise_disjoint"] is True, f"Overlap in {task.task_id}: {d_check}"

    # 2. Verify zero task or target_ops overlap between source_tasks (2-step) and excluded_tasks (3-step/repo)
    src_ids = {t.task_id for t in source_tasks}
    ex_ids = {t.task_id for t in excluded_tasks}
    assert len(src_ids & ex_ids) == 0
    src_seq_targets = {t.target_ops for t in source_tasks}
    ex_seq_targets = {t.target_ops for t in excluded_tasks if t.domain == "sequence_pipeline"}
    assert len(src_seq_targets & ex_seq_targets) == 0

    engine = EqualizedInvestigationEngineV2()
    all_oracles = {
        t.task_id: EvaluatorPrivateTaskOracle(
            task_id=t.task_id,
            target_ops=t.target_ops,
            oracle_fn=t.oracle_fn,
            assessment_inputs=t.assessment_inputs,
            candidate_pool=t.candidate_pool,
        )
        for t in (source_tasks + excluded_tasks)
    }

    curr_params, curr_rep = engine.select_and_train_v2(training_pool, budget_tasks=8, mode="curriculum")
    rand_params, rand_rep = engine.select_and_train_v2(training_pool, budget_tasks=8, mode="random_sampling")
    assert curr_rep["outer_total_candidate_calls"] > 0

    # Equalized active controller config: identical shortlist_limit=3 and allow_questions=True!
    equal_ctrl = EqualizedControllerConfig(shortlist_limit=3, allow_questions=True, max_questions_per_task=2)

    def run_policy(mode: str, params_to_set, allow_capsules: bool = False) -> list[dict]:
        if not allow_capsules:
            engine.reset_skills()
        if params_to_set is None:
            engine.reset_strategy()
        else:
            engine.set_strategy_params(params_to_set)
        env = MechanismBActiveEnvironment(all_oracles)
        out = []
        for t in excluded_tasks:
            ep = engine.investigate_v2(
                t, env, equal_ctrl, policy_mode=mode, allow_compositional_capsules=allow_capsules
            )
            ev = engine.evaluate_v2_episode(t, ep, verify_in_bounded_worker=(t.domain == "repo_patch" and mode == "learned_policy_curriculum_active"))
            assert ev["n_candidate_calls"] == len(ev["candidate_call_log"])
            assert ev["n_questions"] == len(ev["oracle_question_log"])
            out.append(ev)
        return out

    res_untrained = run_policy("untrained_default_active", None)
    res_freq = run_policy("simple_frequency_active", curr_params)
    res_infogain = run_policy("fixed_infogain_active", curr_params)
    res_rank_only = run_policy("learned_ranker_only_active", curr_params)
    res_rand_curr = run_policy("learned_policy_random_curr_active", rand_params)
    res_curr = run_policy("learned_policy_curriculum_active", curr_params)

    # Reset strategy while KEEPING equalized active controller (`allow_questions=True`, `shortlist=4`)
    engine.set_strategy_params(curr_params)
    engine.reset_strategy()
    res_reset = run_policy("learned_policy_curriculum_active", None)

    calls_untrained = sum(r["n_candidate_calls"] for r in res_untrained)
    calls_freq = sum(r["n_candidate_calls"] for r in res_freq)
    calls_infogain = sum(r["n_candidate_calls"] for r in res_infogain)
    calls_rank_only = sum(r["n_candidate_calls"] for r in res_rank_only)
    calls_rand_curr = sum(r["n_candidate_calls"] for r in res_rand_curr)
    calls_curr = sum(r["n_candidate_calls"] for r in res_curr)
    calls_reset = sum(r["n_candidate_calls"] for r in res_reset)

    solved_curr = sum(1 for r in res_curr if r["solved"])
    assert solved_curr == 24
    assert all(r["worker_verified"] is True for r in res_curr if r["domain"] == "repo_patch")
    assert calls_curr < calls_untrained
    assert calls_curr < calls_freq
    assert calls_curr < calls_infogain
    assert calls_curr < calls_rank_only
    assert calls_curr < calls_rand_curr
    assert calls_reset == calls_untrained

    # 3. Autonomous Source Skill Acquisition -> Compositional Prefix Transfer
    engine.reset_skills()
    engine.set_strategy_params(curr_params)
    env_src = MechanismBActiveEnvironment(all_oracles)
    for st in source_tasks:
        ep_s = engine.investigate_v2(
            st, env_src, equal_ctrl, policy_mode="learned_policy_curriculum_active", consolidate_on_solve=True
        )
        ev_s = engine.evaluate_v2_episode(st, ep_s)
        assert ev_s["solved"] is True
    assert len(engine.knowledge.skills.active_capsules()) == 8

    res_dual = run_policy("learned_policy_curriculum_active", curr_params, allow_capsules=True)
    calls_dual = sum(r["n_candidate_calls"] for r in res_dual)
    assert sum(1 for r in res_dual if r["solved"]) == 24
    assert calls_dual < calls_curr


if __name__ == "__main__":
    import tempfile

    test_three_separately_resettable_knowledge_stores()
    test_five_engineering_replacements()
    with tempfile.TemporaryDirectory() as td:
        test_memory_reset_learning_to_learn_and_strategy_ablation(Path(td))
    test_v2_equalized_unconfounded_engine()
    print("ALL COMBINED INVESTIGATION ENGINE V1 + V2 TESTS PASSED")


