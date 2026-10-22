"""Comprehensive unit and integration test suite for the 10-Part NEXUS Seed Integrated Architecture."""
from __future__ import annotations

from pathlib import Path
import pytest

from nexus.seed.integrated_architecture import (
    BAT_STAGES,
    CONTROLLER_ACTIONS,
    CONTROLLER_POLICIES,
    CURRICULUM_STAGES,
    EVIDENCE_STATUS_VALUES,
    FEEDBACK_TIERS,
    LANGUAGE_MODES,
    OPERATING_TIMESCALES,
    BatInvestigationScheduler,
    BeliefWorkspace,
    CognitiveController,
    DeltaDebuggingReducer,
    DevelopmentalCurriculum,
    DiagnosticProcedureLibrary,
    EvidenceKernel,
    EvidenceRecord,
    FailureLibrary,
    MechanismCapsule,
    PerceptionAndLanguageInterface,
    SmallLearnedOptimizer,
    SmallNeuralLanguageCodec,
    SuccessorFeatureLearner,
    TriLibrarySleepConsolidator,
    build_integrated_architecture_report,
    disjunct_matrix_comp,
    evaluate_compound_probe_sensitivity_across_families,
    evaluate_goal_adapters_separately,
    evaluate_targeted_variation_across_four_mechanisms,
    run_conditional_group_testing,
    run_integrated_end_to_end_episode,
    run_seven_isolated_comparisons,
    run_targeted_variation_comparison,
    synthesize_compound_probe,
    verify_d_disjunct,
)

ROOT = Path(__file__).resolve().parents[1]


def test_section_1_and_2_evidence_kernel_tiers_status_and_rollback():
    """Verify 3 operating timescales, 3 feedback tiers, 7 EvidenceStatus values, budget enforcement, and rollback."""
    assert len(OPERATING_TIMESCALES) == 3
    assert len(FEEDBACK_TIERS) == 3
    assert len(EVIDENCE_STATUS_VALUES) == 7

    kernel = EvidenceKernel(max_budget_units=100.0)
    snap0 = kernel.snapshot()

    for status in EVIDENCE_STATUS_VALUES:
        rec = EvidenceRecord(
            claim_id=f"c_{status}",
            statement=f"Statement with status {status}",
            status=status,
            feedback_tier="learning_feedback",
            confidence=0.9,
            supporting_evidence_ids=["ev_1"],
        )
        sha = kernel.register_evidence(rec)
        assert len(sha) == 64

    kernel.charge(12.5, "learning_feedback", "environment_probes")
    kernel.charge(5.0, "promotion_checks", "candidate_predictions")
    kernel.charge(2.5, "final_assessment")
    assert kernel.used_budget_units == 20.0
    assert kernel.counters["learning_feedback_ops"] == 1
    assert kernel.counters["promotion_checks_ops"] == 1
    assert kernel.counters["final_assessment_ops"] == 1

    # Rollback restores exact prior budget and evidence state while incrementing rollbacks counter
    kernel.restore(snap0)
    assert kernel.used_budget_units == 0.0
    assert len(kernel.evidence_records) == 0
    assert kernel.counters["rollbacks"] == 1


def test_section_3_perception_language_modes_intent_routing_and_document_claims():
    """Verify state encoding + feature discovery, 3 language modes (with pretrained flag), 3-way intent routing, and attributed document claims."""
    for mode in LANGUAGE_MODES:
        pli = PerceptionAndLanguageInterface(mode=mode)
        assert pli.pretrained_assisted is (mode == "optional_local_pretrained")

        # 1. Casual greeting must NOT trigger an experiment or capsule
        r_greet = pli.route_user_intent("Hi, how are you?")
        assert r_greet["route"] == "ordinary_conversation"
        assert r_greet["triggers_experiment"] is False
        assert r_greet["creates_capsule"] is False

        # 2. Historical/document question routes to attributed knowledge retrieval
        r_doc = pli.route_user_intent("What caused the French Revolution?")
        assert r_doc["route"] == "knowledge_retrieval_and_explanation"
        assert r_doc["triggers_experiment"] is False

        # 3. Function discovery routes to mechanism investigation
        r_inv = pli.route_user_intent("Learn what this function does")
        assert r_inv["route"] == "mechanism_investigation"
        assert r_inv["triggers_experiment"] is True

        # 4. Document reading extracts attributed claims with versions, dates, and contradictory passages
        docs = [
            dict(doc_id="d1", version="v1.0", date="1789", text="Fiscal debt crisis triggered reform demands."),
            dict(doc_id="d2", version="v2.0", date="1995", text="Contrary accounts show bread prices disputed royal legitimacy."),
        ]
        claims = pli.extract_attributed_claims_from_documents("French Revolution", docs)
        assert len(claims) == 1
        assert claims[0].evidence_status == "disputed"
        assert len(claims[0].supporting_passages) == 1
        assert len(claims[0].contradictory_evidence) == 1
        assert claims[0].extraction_uncertainty > 0.20

    # Verify predictive feature discovery when two inputs share (len, first_last_delta, has_duplicates) but differ in output
    pli_enc = PerceptionAndLanguageInterface()
    enc = pli_enc.encode_observation_and_history(
        inputs=[[1, 2, 3, 5], [1, 3, 2, 5]],
        outputs=[[10, 20], [30, 40]],
    )
    assert enc["residual_ambiguity_detected"] is True
    assert enc["newly_discovered_feature"] == "parity_run_structure"


def test_section_4_belief_workspace_regimes_and_equivalence_group_splitting():
    """Verify Bayesian posterior updates, splittable ObservationalEquivalenceGroups, and unfamiliar mechanism detection."""
    hyps = {
        "h_add1": lambda xs: [x + 1 for x in xs],
        "h_add1_abs": lambda xs: [abs(x) + 1 for x in xs],
        "h_double": lambda xs: [2 * x for x in xs],
    }
    ws = BeliefWorkspace(hyps)
    assert len(ws.equivalence_groups) == 1  # Before any probes, all 3 agree on empty probe list

    # Probe 1: positive numbers [2, 3] -> h_add1 and h_add1_abs agree ([3, 4]), while h_double gives [4, 6]
    u1 = ws.update_posterior([2, 3], [3, 4])
    assert u1["regime"] == "MULTIPLE_PLAUSIBLE_HYPOTHESES"
    assert len(ws.equivalence_groups) == 2

    # Probe 2: negative number [-2, 3] -> splits the surviving equivalence group between h_add1 ([-1, 4]) and h_add1_abs ([3, 4])
    u2 = ws.update_posterior([-2, 3], [-1, 4])
    assert u2["regime"] == "UNIQUE_IDENTIFIED_HYPOTHESIS"
    assert len(ws.equivalence_groups) == 3
    assert u2["top_hypothesis"] == "h_add1"

    # Probe 3: if an unfamiliar mechanism produces an output that NO hypothesis in `hyps` matches,
    # workspace must transition to UNFAMILIAR_MECHANISM_INADEQUATE_FIT rather than staying overconfident!
    u3 = ws.update_posterior([1, 2, 3], [99, 88, 77])
    assert u3["regime"] == "UNFAMILIAR_MECHANISM_INADEQUATE_FIT"


def test_section_5_compound_probes_conditional_group_testing_bat_scheduler_and_diagnostics():
    """Verify compound probe `[-4, -1, 0, 2, 2, 7]`, Kautz-Singleton 2-disjunct matrix, 3-stage bat scheduler, and DiagnosticProcedureLibrary."""
    cp = synthesize_compound_probe()
    assert cp["probe"] == [-4, -1, 0, 2, 2, 7]
    assert cp["input_length_cost"] > 0.0

    mat = disjunct_matrix_comp(12, 2)
    assert len(mat) == 9 and len(mat[0]) == 12
    assert verify_d_disjunct(mat, 2) is True

    # Conditional group testing uses disjunct matrix ONLY when sparse Boolean-OR model holds
    gt_bool = run_conditional_group_testing("sparse_boolean_or_pool", [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0], max_defective=2)
    assert gt_bool["used_disjunct_matrix"] is True
    assert gt_bool["exact_recovery"] is True
    assert gt_bool["num_tests"] == 9

    gt_nonlin = run_conditional_group_testing("nonlinear_composition", [0, 1, 0, 1, 0, 0, 0, 0], max_defective=2)
    assert gt_nonlin["used_disjunct_matrix"] is False

    # Verify BatInvestigationScheduler does NOT assume 1 surviving hypothesis == solved without VALIDATE_AND_ACT
    ws_single = BeliefWorkspace({"only_hyp": lambda xs: [x + 1 for x in xs]})
    ws_single.update_posterior([1, 2], [2, 3])
    assert ws_single.diagnose_regime() == "UNIQUE_IDENTIFIED_HYPOTHESIS"
    sched = BatInvestigationScheduler()
    decision = sched.select_stage_and_probe(ws_single, [[1, 2]], validation_probe=[5, 6])
    assert decision["stage"] == "VALIDATE_AND_ACT"
    # If validation probe fails on the sole hypothesis, regime transitions to UNFAMILIAR_MECHANISM_INADEQUATE_FIT
    upd_fail = ws_single.update_posterior([5, 6], [0, 0])
    assert upd_fail["regime"] == "UNFAMILIAR_MECHANISM_INADEQUATE_FIT"


def test_section_6_and_7_capsule_goal_adapter_targeted_variation_and_ddmin():
    """Verify 6-part MechanismCapsule, separate goal_adapter test, 4-way targeted variation, and bounded ddmin 1-minimality."""
    cap = MechanismCapsule(
        capsule_id="cap_test_v1",
        version=1,
        mechanism=dict(name="reverse", callable=lambda xs: list(reversed(xs))),
        conditions=dict(input_type="list"),
        goal_adapter=dict(grid_navigation="invert_directions_and_reverse_order"),
        language_bindings=dict(invented_word="blisp"),
        evidence=dict(status="tested", validation_tests=[]),
        diagnostics=dict(probe=[-4, -1, 0, 2, 2, 7]),
    )
    ga_res = evaluate_goal_adapters_separately(cap)
    assert ga_res["naive_sequence_reversal_reaches_start"] is False
    assert ga_res["goal_adapter_reaches_start"] is True

    # Verify bounded ddmin counterexample reduction and private assessment protection
    reducer = DeltaDebuggingReducer()
    ref_fn = lambda xs: [x + 1 for x in xs]
    buggy_fn = lambda xs: [0 for _ in xs] if (-3 in xs and -5 in xs) else [x + 1 for x in xs]
    rec = reducer.reduce_counterexample(
        failing_input=[10, 20, -3, 40, -5, 60, 70, 80],
        buggy_fn=buggy_fn,
        reference_oracle_fn=ref_fn,
        max_reduction_budget=48,
        noise_repeats=2,
        is_private_assessment_case=False,
    )
    assert rec.reduced_witness_input == [-3, -5]
    assert rec.is_1_minimal is True

    # When budget is exhausted before 1-minimality check completes, is_1_minimal must be False
    rec_tight = reducer.reduce_counterexample(
        failing_input=[10, 20, -3, 40, -5, 60, 70, 80],
        buggy_fn=buggy_fn,
        reference_oracle_fn=ref_fn,
        max_reduction_budget=6,
        noise_repeats=2,
        is_private_assessment_case=False,
    )
    assert rec_tight.is_1_minimal is False

    with pytest.raises(ValueError, match="ddmin_forbidden_on_private_assessment_case"):
        reducer.reduce_counterexample(
            failing_input=[10, -3, -5],
            buggy_fn=buggy_fn,
            reference_oracle_fn=ref_fn,
            is_private_assessment_case=True,
        )


def test_section_8_9_10_sleep_gpi_learned_optimizer_controller_and_full_report():
    """Verify Trajectory-Learned SuccessorFeatureLearner GPI, Outer-Loop SmallLearnedOptimizer,
    Trainable SmallNeuralLanguageCodec, Compound Probe Sensitivity, 4-Mechanism Evidence-Directed
    Mutation, 11-action CognitiveController, 7 isolated comparisons, full episode, and tamper-rejecting verifier."""
    # 1. Trainable SmallNeuralLanguageCodec: real backprop training, saved weights, 36 held-out utterances, char-trigram subwords, token decoder, no XML tags
    codec = SmallNeuralLanguageCodec(seed=1762700101)
    arch = codec.architectural_dimensions()
    assert arch["handcrafted_structural_features"] == 0
    assert arch["vocab_size"] == 55
    assert arch["char_trigram_buckets"] == 64
    assert arch["input_dim"] == 119
    assert arch["hidden_dim"] == 16
    assert arch["dec_hidden_dim"] == 16
    assert arch["decoder_vocab_size"] == 35
    assert arch["decoder_type"] == "fixed_length_position_conditioned_token_decoder"
    assert arch["previous_generated_tokens_fed_as_inputs"] is False
    assert arch["parameter_count"] == 10970
    tr_sum = codec.train_on_source_corpus(epochs=55, lr=0.18)
    assert tr_sum["final_loss"] < tr_sum["initial_loss"] * 0.25
    heldout_eval = codec.evaluate_unfamiliar_paraphrases_and_compositions()
    assert heldout_eval["heldout_count"] == 36
    assert heldout_eval["unfamiliar_intent_accuracy"] == 1.0
    assert heldout_eval["composition_clause_accuracy"] == 1.0
    assert heldout_eval["ood_epistemic_abstention_accuracy"] == 1.0
    assert heldout_eval["token_level_decoder_accuracy"] == 1.0
    assert heldout_eval["category_breakdown"]["subword_morphology_and_typo"]["accuracy"] == 1.0

    pli_neural = PerceptionAndLanguageInterface(mode="nexus_small_neural", neural_codec=codec)
    v_neural = pli_neural.verbalize_response(
        "mechanism_investigation",
        {"capsule_id": "cap_1", "evidence_status": "tested", "invented_word": "krelv"},
    )
    assert "<neural_codec>" not in v_neural["response_text"]
    assert v_neural["neural_decoder_used"] is True
    assert len(v_neural["chosen_clause_indices"]) == 3
    assert len(v_neural["decoded_tokens"]) > 0

    # 2. Dynamic compound-probe synthesis: changing hypothesis families changes selected probe
    sens = evaluate_compound_probe_sensitivity_across_families()
    assert sens["changing_hypotheses_changes_selected_probe"] is True
    assert sens["unique_selected_probe_count"] == 3

    # 3. Evidence-directed mutation across 4 distinct mechanisms without hardcoded operator bias
    mm = evaluate_targeted_variation_across_four_mechanisms()
    assert mm["zero_hardcoded_operator_preference"] is True
    assert mm["all_mechanisms_solved_fastest_by_evidence_directed"] is True

    # 4. Trajectory-learned SuccessorFeatureLearner & closed-loop GPI rollout in ResourceGridEnv
    sf = SuccessorFeatureLearner()
    gpi_res = sf.evaluate_gpi_under_changed_goal((1.0, 0.0, 0.5), (0.0, 1.0, 0.5))
    assert gpi_res["learned_from_trajectories"] is True
    assert gpi_res["final_td_bellman_error"] < gpi_res["initial_td_bellman_error"]
    assert gpi_res["zero_shot_gpi_gain"] > 0.0
    assert len(gpi_res["gpi_trajectory"]) == 10
    assert gpi_res["environment_relearning_steps_required"] == 0

    # 5. Outer-loop meta-trained SmallLearnedOptimizer frozen before target evaluation vs tuned SGD/Momentum/Adam
    opt = SmallLearnedOptimizer()
    opt_res = opt.evaluate_on_heldout_quadratics(steps=12)
    assert opt_res["frozen_before_target_evaluation"] is True
    assert opt_res["final_source_mean_loss"] < opt_res["initial_source_mean_loss"]
    assert opt_res["beats_fixed_sgd_and_momentum"] is True
    assert opt_res["beats_all_tuned_conventional_optimizers"] is True

    # 6. Controller & Curriculum
    ctrl = CognitiveController()
    assert len(CONTROLLER_ACTIONS) == 11
    assert len(CONTROLLER_POLICIES) == 5
    pol_comp = ctrl.compare_five_controller_policies()
    assert pol_comp["bayesian_planning"]["decision_accuracy"] == 1.0

    cur = DevelopmentalCurriculum()
    assert len(CURRICULUM_STAGES) == 6
    cur_res = cur.evaluate_progression()
    assert cur_res["all_6_stages_completed"] is True

    # 7. Full report & independent tamper-rejecting verifier
    from scripts.verify_seed_integrated_architecture import verify as verify_integrated

    audit = verify_integrated(ROOT, write_artifact=False)
    assert audit["valid"] is True
    assert audit["all_gates_passed"] is True
    assert audit["independent_replay_verified"] is True
    assert all(audit["tamper_rejection_checks"].values())
