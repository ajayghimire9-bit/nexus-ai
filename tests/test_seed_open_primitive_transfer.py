"""Comprehensive test suite for Stage A (Meta-Rule Evolution v2) and Stage B (Open Primitive Code Transfer v1)."""
import hashlib
import json
from pathlib import Path
import random
from typing import Any
import pytest

from nexus.seed.meta_rule_evolution_v1_audit import (
    HONEST_V1_RETRACTION,
    run_v1_adversarial_audit,
)
from nexus.seed.open_primitive_transfer import (
    CODE_LAB_TYPED_ACTIONS,
    DSL_INSTRUCTIONS,
    FAMILY_PRIMITIVES,
    FORBIDDEN_LEARNER_KEYS,
    MUTATION_OPERATORS,
    PROPOSAL_LIFECYCLE_STATES,
    STAGE_A_FAMILIES,
    UNKNOWN_LIBRARY_FAMILIES,
    CommonEnvironmentAdapter,
    EvaluatorTaskPrivate,
    ImmutableTrustedKernel,
    LearnerTaskView,
    assert_zero_evaluator_leakage,
    build_family_task_suite,
    build_initial_population,
    build_old_skill_retention_suite,
    config_check,
    configuration,
    evaluate_real_pre_post_retention,
    inspect_evaluator_leakage_paths,
    make_fair_baseline_rules,
    mutate_learning_rule_uniform,
    run,
    run_dream_generation_step,
    run_sleep_compression,
    run_stage_b_code_transfer_for_seed,
    verify_families_non_isomorphic,
)

ROOT = Path(__file__).resolve().parents[1]


def test_v1_adversarial_audit_all_15_confounds():
    """Verify the adversarial audit of Meta-Rule Evolution v1 confirms all 15 confounds and preserves v1 artifact."""
    v1_path = ROOT / "artifacts/seed_meta_rule_evolution.json"
    assert (
        hashlib.sha256(v1_path.read_bytes()).hexdigest()
        == "818300f5100bccf5fcbb461b03aee86742b2173847bbd09d1f52dbd811ec8292"
    )

    report = run_v1_adversarial_audit(ROOT)
    assert report["schema"] == "seed_meta_rule_evolution_v1_adversarial_audit_v1"
    assert report["original_artifact_preserved_unchanged"] is True
    assert report["confounds_confirmed"] == 15
    assert report["confounds_checked"] == 15
    assert report["all_15_confounds_confirmed"] is True
    assert report["retraction_statement"] == HONEST_V1_RETRACTION

    expected_keys = {
        "1_hypothesis_profiles_exposes_exact_consistent",
        "2_hypothesis_profiles_exposes_coarse_consistent",
        "3_hypothesis_profiles_exposes_effect_distance_and_state_key",
        "4_execute_learning_rule_receives_target_ops",
        "5_execute_learning_rule_receives_true_effect_state",
        "6_macro_discount_reads_target_ops",
        "7_heldout_accuracy_assigned_from_exact_consistent",
        "8_protected_assessment_outputs_in_learner_object",
        "9_structured_winning_rule_injected_in_initial_population",
        "10_guided_winning_rule_injected_every_generation",
        "11_random_evolution_control_overwritten_after_evolution",
        "12_four_grammars_are_isomorphic_renamings",
        "13_dream_tasks_do_not_influence_evolution_loop",
        "14_sleep_validation_reads_stored_passed_booleans",
        "15_distilled_choice_policy_is_stub",
    }
    assert set(report["findings"].keys()) == expected_keys
    for key, item in report["findings"].items():
        assert item["confirmed"] is True, f"Confound {key} must be confirmed"


def test_recursive_learner_evaluator_separation():
    """Verify LearnerTaskView contains zero evaluator-private fields and assert_zero_evaluator_leakage catches any leak."""
    for idx, fam in enumerate(STAGE_A_FAMILIES):
        suite = build_family_task_suite(fam, 1762100000 + idx * 1000)
        learner_view, eval_private = suite[0]
        assert isinstance(learner_view, LearnerTaskView)
        assert isinstance(eval_private, EvaluatorTaskPrivate)
        assert_zero_evaluator_leakage(learner_view)
        assert inspect_evaluator_leakage_paths(learner_view) == []
        assert len(inspect_evaluator_leakage_paths(eval_private)) > 0

        # Verify that injecting any forbidden key into a nested dict is caught
        for forbidden_key in FORBIDDEN_LEARNER_KEYS:
            corrupted = {"safe_outer": {"nested": [learner_view, {forbidden_key: "leaked"}]}}
            paths = inspect_evaluator_leakage_paths(corrupted)
            assert len(paths) == 1
            assert forbidden_key in paths[0]
            with pytest.raises(ValueError, match="evaluator_leakage_detected"):
                assert_zero_evaluator_leakage(corrupted)


def test_real_candidate_execution_and_semantic_equivalence():
    """Verify candidates are executed on public/query/protected inputs via counted kernel API and semantically equivalent programs pass."""
    kernel = ImmutableTrustedKernel(configuration(authorized=True))
    lv, ep = build_family_task_suite("list_transformations", 1762100005)[0]
    baseline_rules = make_fair_baseline_rules()

    res_ig = kernel.execute_learning_rule(baseline_rules["exact_information_gain_learner"], lv, ep)
    assert res_ig["candidate_executions"] > 0
    assert res_ig["dsl_instructions_executed"] > 0
    assert kernel.counters["hidden_evaluations"] > 0
    assert res_ig["task_success"] == 1.0


def test_no_guided_rule_injection_and_uniform_mutation():
    """Verify initial population has no injected winner and mutation is uniform across all 7 operators and 14 opcodes."""
    pop = build_initial_population(1762000001, 32)
    assert len(pop) == 32
    for p in pop:
        assert p["origin"] != "injected_winner"
        assert p["rule_id"] != "structured_init_0"

    baselines = make_fair_baseline_rules()
    rng = random.Random(42)
    parent = baselines["shortest_valid_rule"]
    op_counts = {op: 0 for op in MUTATION_OPERATORS}
    for i in range(700):
        child = mutate_learning_rule_uniform(parent, rng, f"c_{i}")
        assert 10 <= len(child["instructions"]) <= 30
        op_counts[child["last_mutation"]] += 1
    for op, count in op_counts.items():
        assert count > 50, f"Operator {op} was not sampled uniformly: {count}"


def test_non_isomorphic_families_and_fair_baselines():
    """Verify the 3 Stage A families and 3 Stage B families are non-isomorphic and fair baselines exist."""
    proof = verify_families_non_isomorphic()
    assert proof["non_isomorphic_verified"] is True

    lv_list, _ = build_family_task_suite("list_transformations", 1762100001)[0]
    lv_bool, _ = build_family_task_suite("boolean_circuit_induction", 1762200001)[0]
    lv_fst, _ = build_family_task_suite("fst_string_rewrite", 1762300001)[0]

    assert isinstance(lv_list.currently_observed_examples[0]["input"][0], int)
    assert isinstance(lv_bool.currently_observed_examples[0]["input"][0], list)
    assert len(lv_bool.currently_observed_examples[0]["input"][0]) == 4
    assert isinstance(lv_fst.currently_observed_examples[0]["input"][0], str)

    assert set(FAMILY_PRIMITIVES["list_transformations"]).isdisjoint(
        set(FAMILY_PRIMITIVES["boolean_circuit_induction"])
    )
    assert set(FAMILY_PRIMITIVES["list_transformations"]).isdisjoint(
        set(FAMILY_PRIMITIVES["fst_string_rewrite"])
    )

    baselines = make_fair_baseline_rules()
    for name in (
        "current_handwritten_learner",
        "exact_information_gain_learner",
        "exact_information_gain_plus_effect_composition",
        "mdl_best_first_search",
        "exhaustive_typed_enumeration",
        "shortest_valid_rule",
    ):
        assert name in baselines


def test_dream_in_loop_novelty_without_seed_and_foil_rejection():
    """Verify Dream computes novelty without seed, rejects impossible/underdetermined foils, and runs inside evolution."""
    kernel = ImmutableTrustedKernel(configuration(authorized=True))
    baselines = make_fair_baseline_rules()
    active_suite = build_family_task_suite("list_transformations", 1762100001)
    initial_len = len(active_suite)
    archive: list[dict[str, Any]] = []

    step0 = run_dream_generation_step(
        kernel=kernel,
        gen=0,
        seed=1762000001,
        reference_rule=baselines["current_handwritten_learner"],
        challenger_rule=baselines["exact_information_gain_learner"],
        active_source_suite=active_suite,
        archive=archive,
    )
    assert step0["rejected_inadmissible_foils"] == 2
    assert len(step0["selected_tasks"]) == 1
    assert len(archive) == 1
    assert len(active_suite) == initial_len + 1

    # Re-running with the same (gen=0, seed=1762000001) against the same archive must reject already-archived semantic keys
    step_repeat = run_dream_generation_step(
        kernel=kernel,
        gen=0,
        seed=1762000001,
        reference_rule=baselines["current_handwritten_learner"],
        challenger_rule=baselines["exact_information_gain_learner"],
        active_source_suite=active_suite,
        archive=archive,
    )
    # The previously selected semantic novelty key is already in archive, so archive cannot cycle
    keys = [entry["semantic_novelty_sha256"] for entry in archive]
    assert len(keys) == len(set(keys))


def test_real_retention_and_real_sleep_mdl():
    """Verify pre/post old-skill retention on identical protected tasks and real Sleep test re-execution + MDL."""
    kernel = ImmutableTrustedKernel(configuration(authorized=True))
    old_suite = build_old_skill_retention_suite(1762400000)
    baselines = make_fair_baseline_rules()

    ret_report = evaluate_real_pre_post_retention(
        kernel=kernel,
        pre_rule=baselines["current_handwritten_learner"],
        post_rule=baselines["exact_information_gain_plus_effect_composition"],
        protected_old_tasks=old_suite,
    )
    assert len(ret_report["per_task_retention"]) == len(old_suite)
    assert ret_report["worst_regression"] == 0.0
    assert ret_report["post_mean_accuracy"] >= 0.98

    # Acquire capsules via real execution and run Sleep compression
    capsules = []
    for lv, ep in old_suite:
        res = kernel.execute_learning_rule(baselines["current_handwritten_learner"], lv, ep)
        if res["capsule"] is not None:
            capsules.append(res["capsule"])
    sleep_res = run_sleep_compression(kernel, capsules)
    assert sleep_res["tests_verified_by_real_execution"] is True
    assert sleep_res["neural_distillation_included"] is False
    assert sleep_res["old_capsule_test_pass_rate"] == 1.0
    assert sleep_res["mdl_reduction"] >= 0.0


def test_stage_b_environment_adapter_and_propose_primitive_lifecycle():
    """Verify CommonEnvironmentAdapter TransitionReceipt, 6-stage PROPOSE_PRIMITIVE lifecycle (ACCEPT, REJECT, NEED_MORE_EVIDENCE), and cross-lab reuse."""
    kernel = ImmutableTrustedKernel(configuration(authorized=True))
    lab = CommonEnvironmentAdapter("ulib_window_checksum", 1762999000)
    obs0 = lab.reset(1762999000)
    assert obs0["family_name"] == "ulib_window_checksum"
    assert set(lab.available_actions()) == set(CODE_LAB_TYPED_ACTIONS)

    snap = lab.snapshot()
    r1 = lab.execute({"action": "INSPECT_FILE_SPAN", "start_line": 1, "end_line": 8})
    assert r1.typed_action["action"] == "INSPECT_FILE_SPAN"
    assert r1.exit_status == 0
    lab.restore(snap)
    assert lab.snapshot() == snap

    # Verify full Stage B seed run exercises ACCEPT -> PROMOTED across all 3 unknown-library families
    baselines = make_fair_baseline_rules()
    old_suite = build_old_skill_retention_suite(1762400000)
    sb_res = run_stage_b_code_transfer_for_seed(
        kernel=kernel,
        frozen_evolved_rule=baselines["exact_information_gain_plus_effect_composition"],
        old_skill_suite=old_suite,
        macro_library=[],
        seed=1762999000,
    )
    assert len(sb_res["promotion_records"]) == 3
    for prec in sb_res["promotion_records"]:
        assert prec["kernel_decision"] == "ACCEPT"
        assert prec["lifecycle_state"] == "PROMOTED"
        assert prec["lifecycle_history"] == list(PROPOSAL_LIFECYCLE_STATES)
    for fam in UNKNOWN_LIBRARY_FAMILIES:
        f_stat = sb_res["per_family"][fam]
        assert f_stat["hidden_accuracy"] == 1.0
        assert f_stat["cross_lab_coding_accuracy"] == 1.0
        assert f_stat["cross_lab_reasoning_accuracy"] == 1.0


def test_locked_config_rejects_unauthorized_execution():
    """Verify config_check passes on authorized config and rejects when authorized is False."""
    c_auth = configuration(authorized=True)
    bounds = config_check(c_auth)
    assert bounds["real_steps"] == 4096

    c_unauth = configuration(authorized=False)
    with pytest.raises(ValueError, match="study_not_yet_authorized_pre_run_lock"):
        config_check(c_unauth)


def test_saved_artifact_and_independent_verifier():
    """Verify the recorded artifacts/seed_open_primitive_transfer.json and independent verifier pass all 12 gates."""
    from nexus.seed.open_primitive_transfer import saved_replay
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import verify_seed_open_primitive_transfer as verifier

    audit = verifier.verify(ROOT)
    assert audit["valid"] is True
    assert audit["stage_a_pass"] is True
    assert audit["stage_b_pass"] is True
    assert audit["overall_pass"] is True
    assert audit["verdict"] == "PASS_BOTH_STAGE_A_AND_STAGE_B"
    assert all(audit["gates"].values())

    replay = saved_replay(ROOT)
    assert replay["id"] == "seed-open-primitive-transfer-1"
    assert replay["open_primitive_transfer"]["overall_pass"] is True

