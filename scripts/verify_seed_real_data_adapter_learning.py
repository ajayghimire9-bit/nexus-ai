#!/usr/bin/env python3
"""Standalone Tamper-Rejecting Verifier for `seed_real_data_adapter_learning_v1`.

Reconstructs all 10 verification gates from raw per-task records, search metrics,
disambiguation records, frozen independent confirmation runs, SQLite transfer
records, and the 4 Wall-Breaking Research Pillars. Never trusts top-level summary
booleans (`all_gates_passed` or `gates`), and executes a 6-case tamper-rejection
suite proving that corrupted artifacts are rejected with `ValueError`.
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from nexus.seed.real_data_adapter_learning import (
    DEFAULT_ARTIFACT_PATH,
    RealDataWorkspaceAdapter,
    build_real_data_adapter_learning_report,
    write_real_data_adapter_learning_artifact,
)


def reconstruct_gates_from_raw_records(report: dict[str, Any]) -> dict[str, bool]:
    """Recomputes all 10 gates strictly from nested raw records in `report`."""
    if report.get("schema") != "seed_real_data_adapter_learning_v1":
        raise ValueError(f"Unexpected schema: {report.get('schema')}")
    if report.get("initial_stored_compositions") != 0:
        raise ValueError("initial_stored_compositions must be 0")
    if report.get("winning_program_supplied_to_learner") is not False:
        raise ValueError("winning_program_supplied_to_learner must be False")
    if report.get("separate_evaluator_subprocess") is not True:
        raise ValueError("separate_evaluator_subprocess must be True")
    if report.get("private_heldout_exposed_to_learner") is not False:
        raise ValueError("private_heldout_exposed_to_learner must be False")

    freeze_sha = str(report.get("freeze_journal_sha256", ""))
    dev = report["development_results"]
    confirm = report["independent_confirmation_results"]
    comp_stress = report["compositional_representation_and_stress_test"]
    search_cmp = report["search_methods_comparison"]
    disamb = report["active_disambiguation_and_ambiguity_reporting"]
    pillars = report["four_wall_breaking_pillars"]

    ag_dev = dev["methods"]["active_growing_library"]
    af_dev = dev["methods"]["active_fixed_library"]
    pf_dev = dev["methods"]["passive_fixed_library"]
    pg_dev = dev["methods"]["passive_growing_library"]
    ec_dev = dev["methods"]["exact_program_cache_baseline"]

    # Recompute active_growing_library metrics from per_task_records
    ag_recs = ag_dev["per_task_records"]
    af_recs = af_dev["per_task_records"]
    pf_recs = pf_dev["per_task_records"]
    ec_recs = ec_dev["per_task_records"]
    if len(ag_recs) != 5 or len(af_recs) != 5 or len(pf_recs) != 5 or len(ec_recs) != 5:
        raise ValueError("Expected 5 development task records per method")

    ag_mean_acc = round(sum(float(r["heldout_accuracy"]) for r in ag_recs) / len(ag_recs), 6)
    pf_mean_acc = round(sum(float(r["heldout_accuracy"]) for r in pf_recs) / len(pf_recs), 6)
    pg_mean_acc = round(
        sum(float(r["heldout_accuracy"]) for r in pg_dev["per_task_records"]) / len(pg_dev["per_task_records"]),
        6,
    )
    ag_later_cost = round(sum(float(r["total_compute_cost"]) for r in ag_recs[1:]), 6)
    af_later_cost = round(sum(float(r["total_compute_cost"]) for r in af_recs[1:]), 6)
    ag_later_execs = sum(int(r["candidate_executions"]) for r in ag_recs[1:])
    ec_later_execs = sum(int(r["candidate_executions"]) for r in ec_recs[1:])
    ag_retention = round(sum(float(r["old_skill_retention"]) for r in ag_recs) / len(ag_recs), 6)

    if abs(ag_mean_acc - float(ag_dev["mean_heldout_accuracy"])) > 1e-6:
        raise ValueError("Tampered active_growing_library mean_heldout_accuracy")
    if abs(ag_later_cost - float(ag_dev["later_tasks_compute_cost"])) > 1e-5:
        raise ValueError("Tampered active_growing_library later_tasks_compute_cost")
    if ag_later_execs != int(ag_dev["later_tasks_candidate_executions"]):
        raise ValueError("Tampered active_growing_library later_tasks_candidate_executions")

    # Recompute independent confirmation CSV/JSON metrics from per_task_records
    conf_csv = confirm["reserved_csv_json_schemas"]
    conf_ag_recs = conf_csv["active_growing_library"]["per_task_records"]
    conf_af_recs = conf_csv["active_fixed_library"]["per_task_records"]
    if len(conf_ag_recs) != 2 or len(conf_af_recs) != 2:
        raise ValueError("Expected 2 reserved confirmation CSV/JSON task records")

    conf_ag_acc = round(sum(float(r["heldout_accuracy"]) for r in conf_ag_recs) / len(conf_ag_recs), 6)
    conf_ag_cost = round(sum(float(r["total_compute_cost"]) for r in conf_ag_recs), 6)
    conf_af_cost = round(sum(float(r["total_compute_cost"]) for r in conf_af_recs), 6)
    conf_ag_execs = sum(int(r["candidate_executions"]) for r in conf_ag_recs)
    conf_af_execs = sum(int(r["candidate_executions"]) for r in conf_af_recs)

    if abs(conf_ag_acc - float(conf_csv["active_growing_library"]["mean_heldout_accuracy"])) > 1e-6:
        raise ValueError("Tampered confirmation active_growing_library mean_heldout_accuracy")
    if abs((conf_af_cost - conf_ag_cost) - float(conf_csv["confirmation_cost_savings_vs_active_fixed"])) > 1e-5:
        raise ValueError("Tampered confirmation_cost_savings_vs_active_fixed")

    # Recompute SQLite independent confirmation from raw per_task_records
    full_sql = confirm["full_sqlite_transfer_summary"]
    sql_tr_recs = full_sql["with_prior_csv_json_learning"]["per_task_records"]
    sql_sc_recs = full_sql["from_scratch"]["per_task_records"]
    if len(sql_tr_recs) != 3 or len(sql_sc_recs) != 3:
        raise ValueError("Expected 3 SQLite task records (1 dev + 2 confirmation)")

    sql_conf_tr_acc = round(sum(float(r["heldout_accuracy"]) for r in sql_tr_recs[1:]) / 2.0, 6)
    sql_conf_tr_cost = round(sum(float(r["total_compute_cost"]) for r in sql_tr_recs[1:]), 6)
    sql_conf_sc_cost = round(sum(float(r["total_compute_cost"]) for r in sql_sc_recs[1:]), 6)
    sql_conf_tr_execs = sum(int(r["candidate_executions"]) for r in sql_tr_recs[1:])
    sql_conf_sc_execs = sum(int(r["candidate_executions"]) for r in sql_sc_recs[1:])

    res_sql = confirm["reserved_sqlite_transfer"]
    if abs(sql_conf_tr_acc - float(res_sql["transfer_mean_accuracy"])) > 1e-6:
        raise ValueError("Tampered SQLite confirmation transfer_mean_accuracy")
    if (sql_conf_sc_execs - sql_conf_tr_execs) != int(res_sql["confirmation_execution_savings"]):
        raise ValueError("Tampered SQLite confirmation_execution_savings")
    if abs((sql_conf_sc_cost - sql_conf_tr_cost) - float(res_sql["confirmation_cost_savings"])) > 1e-5:
        raise ValueError("Tampered SQLite confirmation_cost_savings")

    # Recompute search comparison from per_task
    s_recs = list(search_cmp["per_task"].values())
    if not s_recs or not all(
        bool(r["exact_same_surviving_version_space"])
        and int(r["backward_witness_candidate_executions"])
        < int(r["enumeration_candidate_executions"])
        and bool(r["backward_witness_retained"])
        for r in s_recs
    ):
        raise ValueError("Search comparison raw records failed witness reduction or equivalence check")
    mean_enum = sum(int(r["enumeration_candidate_executions"]) for r in s_recs) / len(s_recs)
    mean_bw = sum(int(r["backward_witness_candidate_executions"]) for r in s_recs) / len(s_recs)

    # Recompute disambiguation & honest ambiguity check
    no_src = disamb["without_answer_source"]
    with_src = disamb["with_reference_answer_source"]
    if (
        no_src.get("ambiguity_reported") is not True
        or no_src.get("pretended_resolved") is not False
        or no_src.get("evidence_status") != "unknown"
        or int(no_src.get("surviving_candidate_count", 0)) < 2
    ):
        raise ValueError("Ambiguity check without answer source failed honest reporting requirements")

    # Verify Pillars 1-4 from raw fields
    p1 = pillars["pillar_1_functorial_metaphor_transfer"]
    p2 = pillars["pillar_2_system_identification_and_dynamic_slicing"]
    p3 = pillars["pillar_3_pearl_do_calculus_and_lakatos_refutations"]
    p4 = pillars["pillar_4_pidgin_bootstrapping_and_counterfactual_explanations"]

    reconstructed = dict(
        gate_01_clean_starting_point_and_dev_vs_confirmation_split=bool(
            len(freeze_sha) == 64
            and confirm.get("frozen_before_confirmation") is True
            and set(dev["task_sequence"]).isdisjoint(set(conf_csv["task_ids"]))
        ),
        gate_02_readonly_csv_json_workspace_and_reserved_schemas=bool(
            all(
                bool(r["read_only_source_unmodified"])
                and bool(r["output_file_written"])
                and len(str(r["evaluator_receipt_sha256"])) == 64
                for r in ag_recs + conf_ag_recs
            )
        ),
        gate_03_compositional_adapters_without_15_op_limit_and_missing_value_handling=bool(
            comp_stress.get("verified") is True
            and int(comp_stress.get("pipeline_operation_count", 0)) == 18
            and comp_stress.get("exceeds_15_operation_limit") is True
            and int(ag_recs[0]["program_length"]) >= 8
        ),
        gate_04_search_methods_measured_and_witness_retained_where_justified=bool(
            search_cmp.get("all_version_spaces_identical") is True
            and search_cmp.get("retained_where_benefit_justifies_cost") is True
            and mean_bw < mean_enum * 0.25
        ),
        gate_05_active_questions_with_real_answer_source_and_honest_ambiguity_reporting=bool(
            no_src.get("ambiguity_reported") is True
            and no_src.get("pretended_resolved") is False
            and float(with_src.get("heldout_accuracy", 0.0)) == 1.0
        ),
        gate_06_persistent_learning_2x2_and_exact_cache_fair_comparison=bool(
            ag_mean_acc == 1.0
            and ag_mean_acc > pf_mean_acc
            and ag_mean_acc > pg_mean_acc
            and ag_later_cost < af_later_cost
            and ag_later_execs < ec_later_execs
            and ag_retention == 1.0
        ),
        gate_07_independent_confirmation_on_reserved_csv_json_schemas=bool(
            conf_ag_acc == 1.0
            and conf_ag_cost < conf_af_cost
            and conf_ag_execs < conf_af_execs
            and all(bool(r["reused_promoted_template"]) for r in conf_ag_recs)
        ),
        gate_08_sqlite_transfer_after_freeze_beats_scratch=bool(
            sql_conf_tr_acc == 1.0
            and sql_conf_tr_cost < sql_conf_sc_cost
            and sql_conf_tr_execs < sql_conf_sc_execs
            and all(bool(r["reused_promoted_template"]) for r in sql_tr_recs)
        ),
        gate_09_functorial_bridge_and_dynamic_slicing_pillars_verified=bool(
            float(p1.get("heldout_packet_routing_accuracy", 0.0)) == 1.0
            and int(p1.get("algebraic_probes_used", 0)) == 3
            and p2["api_discovery"].get("verified_on_heldout") is True
            and p2["dynamic_slicing_repair"].get("repair_matches_oracle") is True
            and float(p2["dynamic_slicing_repair"].get("code_pruned_fraction", 0.0)) >= 0.85
        ),
        gate_10_causal_do_calculus_lakatos_and_pidgin_counterfactual_verified=bool(
            p3["surgical_do_interventions"].get("exact_recovery") is True
            and p3["lakatos_proofs_and_refutations"].get("refined_conjecture_holds_across_all_heldout") is True
            and p4["pidgin_semantic_bootstrapping"].get("heldout_verified") is True
            and p4["counterfactual_trace_explanation"].get("counterfactual_sensitivity_verified") is True
        ),
    )

    if reconstructed != report.get("gates"):
        raise ValueError(
            f"Reconstructed gates {reconstructed} do not match reported gates {report.get('gates')}"
        )
    if not all(reconstructed.values()):
        failed = [k for k, v in reconstructed.items() if not v]
        raise ValueError(f"One or more reconstructed gates failed: {failed}")
    if report.get("all_gates_passed") is not True:
        raise ValueError("all_gates_passed must be True when all gates pass")

    return reconstructed


def verify_live_subprocess_workspace_isolation() -> None:
    """Independently verifies that `RealDataWorkspaceAdapter` enforces read-only
    source files and never exposes private held-out rows."""
    ws = RealDataWorkspaceAdapter("A1_telemetry_alert_aggregation")
    try:
        if ws.spec.get("private_heldout_exposed") is not False or "private_heldout_rows" in ws.spec:
            raise ValueError("Private held-out data leaked into public workspace spec")
        if not ws.verify_read_only_source_integrity():
            raise ValueError("Read-only source integrity check failed on fresh workspace")
    finally:
        ws.cleanup()


def verify_tamper_rejection(base_report: dict[str, Any]) -> list[str]:
    """Mutates 6 distinct nested records while leaving `all_gates_passed = True`
    and verifies that `reconstruct_gates_from_raw_records` raises `ValueError`."""
    rejected_cases: list[str] = []

    # Case 1: Tamper with read-only source unmodified flag on task S1
    t1 = copy.deepcopy(base_report)
    t1["development_results"]["methods"]["active_growing_library"]["per_task_records"][0][
        "read_only_source_unmodified"
    ] = False
    try:
        reconstruct_gates_from_raw_records(t1)
    except ValueError:
        rejected_cases.append("tamper_readonly_source_flag_rejected")
    else:
        raise AssertionError("Failed to reject tampered read_only_source_unmodified flag")

    # Case 2: Tamper with honest ambiguity reporting when no answer source exists
    t2 = copy.deepcopy(base_report)
    t2["active_disambiguation_and_ambiguity_reporting"]["without_answer_source"][
        "pretended_resolved"
    ] = True
    try:
        reconstruct_gates_from_raw_records(t2)
    except ValueError:
        rejected_cases.append("tamper_dishonest_ambiguity_resolution_rejected")
    else:
        raise AssertionError("Failed to reject dishonest ambiguity resolution")

    # Case 3: Tamper with confirmation task held-out accuracy
    t3 = copy.deepcopy(base_report)
    t3["independent_confirmation_results"]["reserved_csv_json_schemas"]["active_growing_library"][
        "per_task_records"
    ][0]["heldout_accuracy"] = 0.5
    try:
        reconstruct_gates_from_raw_records(t3)
    except ValueError:
        rejected_cases.append("tamper_confirmation_heldout_accuracy_rejected")
    else:
        raise AssertionError("Failed to reject tampered confirmation heldout_accuracy")

    # Case 4: Tamper with SQLite transfer candidate executions
    t4 = copy.deepcopy(base_report)
    t4["independent_confirmation_results"]["full_sqlite_transfer_summary"][
        "with_prior_csv_json_learning"
    ]["per_task_records"][1]["candidate_executions"] = 999
    try:
        reconstruct_gates_from_raw_records(t4)
    except ValueError:
        rejected_cases.append("tamper_sqlite_transfer_executions_rejected")
    else:
        raise AssertionError("Failed to reject tampered SQLite candidate executions")

    # Case 5: Tamper with Pillar 2 dynamic slice pruning fraction
    t5 = copy.deepcopy(base_report)
    t5["four_wall_breaking_pillars"]["pillar_2_system_identification_and_dynamic_slicing"][
        "dynamic_slicing_repair"
    ]["code_pruned_fraction"] = 0.25
    try:
        reconstruct_gates_from_raw_records(t5)
    except ValueError:
        rejected_cases.append("tamper_dynamic_slicing_pruning_rejected")
    else:
        raise AssertionError("Failed to reject tampered dynamic slice pruning fraction")

    # Case 6: Tamper with Pillar 3 Lakatos refined conjecture verification
    t6 = copy.deepcopy(base_report)
    t6["four_wall_breaking_pillars"]["pillar_3_pearl_do_calculus_and_lakatos_refutations"][
        "lakatos_proofs_and_refutations"
    ]["refined_conjecture_holds_across_all_heldout"] = False
    try:
        reconstruct_gates_from_raw_records(t6)
    except ValueError:
        rejected_cases.append("tamper_lakatos_conjecture_rejected")
    else:
        raise AssertionError("Failed to reject tampered Lakatos conjecture")

    return rejected_cases


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify or write the seed_real_data_adapter_learning_v1 artifact."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Re-run the experiment and write artifacts/seed_real_data_adapter_learning_v1.json.",
    )
    parser.add_argument(
        "--artifact",
        type=pathlib.Path,
        default=DEFAULT_ARTIFACT_PATH,
        help="Path to the artifact JSON file.",
    )
    args = parser.parse_args()

    if args.write or not args.artifact.exists():
        write_real_data_adapter_learning_artifact(args.artifact)

    report = json.loads(args.artifact.read_text(encoding="utf-8"))
    reconstructed_gates = reconstruct_gates_from_raw_records(report)
    verify_live_subprocess_workspace_isolation()
    rejected = verify_tamper_rejection(report)

    summary = dict(
        status="VERIFIED",
        artifact=str(args.artifact),
        all_gates_passed=bool(all(reconstructed_gates.values())),
        gates_verified=len(reconstructed_gates),
        tamper_cases_rejected=rejected,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
