"""Comprehensive test suite for `seed_real_data_adapter_learning_v1`."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from nexus.seed.real_data_adapter_learning import (
    DEFAULT_ARTIFACT_PATH,
    AutodidactTracerSlicer,
    CausalInterventionAndLakatosEngine,
    EvidenceKernel,
    FunctorialCategoryBridge,
    GrammarConstrainedLocalIntentModel,
    PidginBootstrapAndCounterfactualExplainer,
    RealDataWorkspaceAdapter,
    build_type_directed_candidate_space,
    compare_search_methods_on_tasks,
    evaluate_unfamiliar_derived_composition_and_transfer,
    execute_method_on_task_sequence,
    extract_parameterized_template_from_winner,
    infer_schema_role_candidates,
    run_active_disambiguation_and_ambiguity_check,
    run_three_way_local_model_benchmark,
    verify_skeleton_ast_controls_instantiation_and_sql,
    verify_unbounded_composition_and_missing_value_semantics,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_real_data_workspace_readonly_source_and_separate_output() -> None:
    ws = RealDataWorkspaceAdapter("S1_filter_and_normalize_error_logs")
    try:
        assert ws.read_only_source_path.exists()
        assert ws.verify_read_only_source_integrity() is True
        assert ws.spec["private_heldout_exposed"] is False
        assert "private_heldout_rows" not in ws.spec

        rows = ws.read_source_records()
        assert len(rows) >= 5
        out_path = ws.write_output_records(ws.spec["demonstration_expected_output"])
        assert out_path.exists()
        assert out_path.parent == ws.output_dir
        assert ws.output_dir != ws.read_only_source_path.parent
        assert ws.verify_read_only_source_integrity() is True
    finally:
        ws.close()


def test_skeleton_ast_controls_instantiation_and_sql_directly() -> None:
    ws = RealDataWorkspaceAdapter("S2_endpoint_latency_grouped_summary")
    try:
        spec = ws.spec
        demo_in = spec["demonstration_input_rows"]
        demo_out = spec["demonstration_expected_output"]
        req_cols = spec["required_output_columns"]
        roles = infer_schema_role_candidates(demo_in, demo_out, req_cols)
        assert roles["inferred_structural_signature"] == "grouped_summary"

        cands = build_type_directed_candidate_space(spec)
        winner = next(c for c in cands if c.execute(demo_in) == demo_out)
        tpl = extract_parameterized_template_from_winner(
            "S2_endpoint_latency_grouped_summary",
            roles["inferred_structural_signature"],
            winner,
            spec,
            EvidenceKernel(100.0),
        )
        proof = verify_skeleton_ast_controls_instantiation_and_sql(tpl, spec)
        assert proof["skeleton_controls_execution_verified"] is True
        assert proof["sort_mutation_reverses_execution_output"] is True
        assert proof["filter_removal_removes_instantiated_filter"] is True
        assert proof["empty_skeleton_produces_zero_ops"] is True
    finally:
        ws.close()


def test_naturally_occurring_python_stdlib_ast_task_and_relational_sqlite_join() -> None:
    # 1. Naturally occurring Python stdlib AST task (R1)
    r1_res = execute_method_on_task_sequence(
        "active_growing_library",
        ["R1_repo_python_ast_metrics"],
    )
    assert r1_res["mean_heldout_accuracy"] == 1.0
    assert r1_res["per_task_records"][0]["task_id"] == "R1_repo_python_ast_metrics"

    # 2. Normalized 2-table relational SQLite transfer (dim_entities + fact_events)
    sql_res = execute_method_on_task_sequence(
        "active_growing_library",
        ["SQL1_service_telemetry_db", "SQL2_supply_chain_shipments_db"],
    )
    assert sql_res["mean_heldout_accuracy"] == 1.0
    for rec in sql_res["per_task_records"]:
        assert rec["relational_sql_exact_match"] is True
        assert 'JOIN "dim_entities"' in str(rec["submitted_sql_query"])


def test_compositional_adapter_exceeds_15_ops_and_handles_missing_values() -> None:
    res = verify_unbounded_composition_and_missing_value_semantics()
    assert res["verified"] is True
    assert res["pipeline_operation_count"] == 18
    assert res["exceeds_15_operation_limit"] is True
    assert res["missing_a_dropped_cleanly"] is True
    assert res["corrupted_b_filled_with_default"] is True


def test_search_methods_comparison_and_retention_policy() -> None:
    cmp_res = compare_search_methods_on_tasks()
    assert cmp_res["all_version_spaces_identical"] is True
    assert cmp_res["retained_where_benefit_justifies_cost"] is True
    assert (
        cmp_res["mean_backward_witness_candidate_executions"]
        < cmp_res["mean_enumeration_candidate_executions"] * 0.25
    )
    assert (
        cmp_res["trivial_1op_task_policy"]["selected_method_for_trivial_1op"]
        == "bounded_type_directed_enumeration"
    )


def test_active_disambiguation_and_honest_ambiguity_reporting() -> None:
    disamb = run_active_disambiguation_and_ambiguity_check("S2_endpoint_latency_grouped_summary")
    no_src = disamb["without_answer_source"]
    assert no_src["answer_source_available"] is False
    assert no_src["ambiguity_reported"] is True
    assert no_src["pretended_resolved"] is False
    assert no_src["evidence_status"] == "unknown"
    assert no_src["promoted_capsules_count"] == 0

    with_src = disamb["with_reference_answer_source"]
    assert with_src["answer_source_available"] is True
    assert with_src["heldout_accuracy"] == 1.0
    assert with_src["final_surviving_candidates"] == 1


def test_four_wall_breaking_pillars_execution() -> None:
    p1 = FunctorialCategoryBridge.run_three_algebraic_property_probes()
    assert p1["algebraic_probes_used"] == 3
    assert p1["total_blackbox_function_calls_during_probing"] > p1["algebraic_probes_used"]
    assert p1["associativity_verified_on_triples"] is True
    assert p1["composition_law_preserved"] is True
    assert p1["heldout_packet_routing_accuracy"] == 1.0

    p2_slice = AutodidactTracerSlicer.run_dynamic_backward_slice_and_repair()
    assert p2_slice["repair_matches_oracle"] is True
    assert p2_slice["code_pruned_fraction"] >= 0.85
    assert p2_slice["sliced_candidate_patch_executions"] < p2_slice["unsliced_candidate_patches"]
    tree = ast.parse(p2_slice["synthesized_patched_function_source"])
    assert not any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "abs"
        for n in ast.walk(tree)
    )

    p3_do = CausalInterventionAndLakatosEngine.discover_causal_graph_via_do_interventions()
    assert p3_do["exact_recovery"] is True
    assert len(p3_do["interventions_trace"]) == 2
    p3_lakatos = CausalInterventionAndLakatosEngine.run_lakatos_proofs_and_refutations_loop()
    assert p3_lakatos["monster_falsifies_initial_conjecture"] is True
    assert p3_lakatos["refined_conjecture_holds_across_all_heldout"] is True

    p4_pidgin = PidginBootstrapAndCounterfactualExplainer.bootstrap_unknown_verb_in_one_question()
    assert p4_pidgin["heldout_verified"] is True
    assert p4_pidgin["followup_questions_needed"] == 0
    assert len(p4_pidgin["teacher_subprocess_receipt"]) == 64


def test_unfamiliar_derived_composition_discovery_and_canonical_selection_rule() -> None:
    unfam = evaluate_unfamiliar_derived_composition_and_transfer()
    assert unfam["verified"] is True
    assert unfam["contains_compute_derived_field_op"] is True
    assert unfam["u1_heldout_accuracy"] == 1.0
    assert unfam["u2_heldout_accuracy"] == 1.0
    assert unfam["u2_execution_savings"] > 0

    passive_res = execute_method_on_task_sequence(
        "passive_fixed_library",
        ["S1_filter_and_normalize_error_logs", "S2_endpoint_latency_grouped_summary"],
    )
    active_res = execute_method_on_task_sequence(
        "active_growing_library",
        ["S1_filter_and_normalize_error_logs", "S2_endpoint_latency_grouped_summary"],
    )
    assert passive_res["selection_rule"] == "canonical_first_surviving_candidate"
    assert active_res["selection_rule"] == "canonical_first_surviving_candidate"
    assert active_res["mean_heldout_accuracy"] == 1.0
    assert active_res["mean_heldout_accuracy"] > passive_res["mean_heldout_accuracy"]


def test_three_way_local_model_benchmark_and_net_savings() -> None:
    model = GrammarConstrainedLocalIntentModel()
    assert model.GGUF_MODEL_PATH.name == "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    assert model.weight_memory_kb > 400000.0

    bench = run_three_way_local_model_benchmark(num_repeated_trials=5)
    assert bench["workload_size_N"] == 6
    assert bench["pretrained_model_verification"]["used_keyword_matching"] is False
    assert bench["pretrained_model_verification"]["grammar_constrained_decoding"] is True
    assert bench["pretrained_model_verification"]["real_model_tokenizer_counts"] is True
    assert (
        bench["repeated_trials_uncertainty"]["paired_solver_latency_savings_vs_ordinary_caching_ms"]["ci95_low"]
        > 0.0
    )
    assert bench["inappropriate_reuse_rejected_on_row_level_task"] is True
    assert bench["ambiguous_revenue_eur_disambiguated"] is True
    assert bench["net_savings_vs_ordinary_program_caching"]["net_compute_cost_savings"] > 0.0
    assert bench["net_savings_vs_ordinary_program_caching"]["net_candidate_execution_savings"] > 0
    assert bench["net_savings_vs_model_plus_tools"]["net_compute_cost_savings"] > 0.0


def test_full_real_data_adapter_learning_artifact_and_tamper_verifier() -> None:
    assert DEFAULT_ARTIFACT_PATH.exists(), "Expected seed_real_data_adapter_learning_v1.json to exist"
    report = json.loads(DEFAULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    assert report["schema"] == "seed_real_data_adapter_learning_v1"
    assert report["all_gates_passed"] is True
    assert all(report["gates"].values())

    # Verify standalone verifier script passes and rejects all 14 tamper modes
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "verify_seed_real_data_adapter_learning.py")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    out = json.loads(proc.stdout)
    assert out["status"] == "VERIFIED"
    assert out["all_gates_passed"] is True
    assert len(out["tamper_cases_rejected"]) == 14
