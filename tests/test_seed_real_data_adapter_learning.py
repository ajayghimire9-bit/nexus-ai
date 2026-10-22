"""Comprehensive test suite for `seed_real_data_adapter_learning_v1`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from nexus.seed.real_data_adapter_learning import (
    DEFAULT_ARTIFACT_PATH,
    AutodidactTracerSlicer,
    CausalInterventionAndLakatosEngine,
    FunctorialCategoryBridge,
    PidginBootstrapAndCounterfactualExplainer,
    RealDataWorkspaceAdapter,
    build_real_data_adapter_learning_report,
    compare_search_methods_on_tasks,
    run_active_disambiguation_and_ambiguity_check,
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
    assert p1["heldout_packet_routing_accuracy"] == 1.0

    p2_slice = AutodidactTracerSlicer.run_dynamic_backward_slice_and_repair()
    assert p2_slice["repair_matches_oracle"] is True
    assert p2_slice["code_pruned_fraction"] >= 0.85

    p3_do = CausalInterventionAndLakatosEngine.discover_causal_graph_via_do_interventions()
    assert p3_do["exact_recovery"] is True
    p3_lakatos = CausalInterventionAndLakatosEngine.run_lakatos_proofs_and_refutations_loop()
    assert p3_lakatos["monster_falsifies_initial_conjecture"] is True
    assert p3_lakatos["refined_conjecture_holds_across_all_heldout"] is True

    p4_pidgin = PidginBootstrapAndCounterfactualExplainer.bootstrap_unknown_verb_in_one_question()
    assert p4_pidgin["heldout_verified"] is True


def test_full_real_data_adapter_learning_artifact_and_tamper_verifier() -> None:
    assert DEFAULT_ARTIFACT_PATH.exists(), "Expected seed_real_data_adapter_learning_v1.json to exist"
    report = json.loads(DEFAULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    assert report["schema"] == "seed_real_data_adapter_learning_v1"
    assert report["all_gates_passed"] is True
    assert all(report["gates"].values())

    # Verify standalone verifier script passes and rejects all 6 tamper modes
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
    assert len(out["tamper_cases_rejected"]) == 6
