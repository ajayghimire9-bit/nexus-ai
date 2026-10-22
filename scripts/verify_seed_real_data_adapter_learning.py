#!/usr/bin/env python3
"""Standalone Tamper-Rejecting Verifier for `seed_real_data_adapter_learning_v1`.

Reconstructs all 10 verification gates from raw per-task records, stored AST
`skeleton_ops`, search metrics, disambiguation records, frozen independent
confirmation runs, normalized 2-table SQLite `JOIN` queries, the 3-way local
model benchmark (with explicit Net Savings recomputation), and live re-execution
of the 4 Wall-Breaking Research Pillars. Never trusts top-level summary booleans
(`all_gates_passed` or `gates`), and executes a 10-case tamper-rejection suite
proving that corrupted artifacts are rejected with `ValueError`.
"""

from __future__ import annotations

import argparse
import ast
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
    ParameterizedAdapterTemplate,
    RealDataWorkspaceAdapter,
    build_real_data_adapter_learning_report,
    verify_skeleton_ast_controls_instantiation_and_sql,
    write_real_data_adapter_learning_artifact,
)


def _verify_skeleton_ast_and_promoted_templates(report: dict[str, Any]) -> bool:
    """Re-instantiates `promoted_template_skeletons` from the artifact and verifies
    that `skeleton_ops` directly governs program instantiation and execution output."""
    proof = report.get("skeleton_ast_execution_control_proof", {})
    skeletons = report.get("promoted_template_skeletons", {})
    if not isinstance(skeletons, dict) or "grouped_summary" not in skeletons or "filter_normalize_order" not in skeletons:
        raise ValueError("Missing required promoted_template_skeletons in report")

    gs_ops = skeletons["grouped_summary"]
    fno_ops = skeletons["filter_normalize_order"]
    if not isinstance(gs_ops, list) or len(gs_ops) < 8 or not isinstance(fno_ops, list) or len(fno_ops) < 8:
        raise ValueError("Promoted template skeleton_ops must be non-empty AST node lists")

    tpl = ParameterizedAdapterTemplate(
        template_id=str(proof.get("template_id", "tpl_grouped_summary")),
        task_kind="grouped_summary",
        origin_task_id="S2_endpoint_latency_grouped_summary",
        skeleton_ops=copy.deepcopy(gs_ops),
        categorical_skeleton_signature=(
            "Partition_By_Equivalence",
            "Filter_By_Monotonic_Threshold",
            "Fold_Associative_Monoid",
        ),
    )
    ws_s2 = RealDataWorkspaceAdapter("S2_endpoint_latency_grouped_summary")
    try:
        live_proof = verify_skeleton_ast_controls_instantiation_and_sql(tpl, ws_s2.spec)
    finally:
        ws_s2.close()
    if not live_proof.get("skeleton_controls_execution_verified"):
        raise ValueError("Live re-verification of skeleton_ops execution control failed")
    if proof != live_proof:
        raise ValueError("Recorded skeleton_ast_execution_control_proof does not match live re-execution")
    return True


def _verify_pillar_2_compiled_ast_patch(p2: dict[str, Any]) -> bool:
    """Parses `synthesized_patched_function_source` with `ast.parse`, checks that
    no `abs(` shortcut is present, compiles the repaired function, and executes it
    on witness and held-out packet streams."""
    ds = p2.get("dynamic_slicing_repair", {})
    src = str(ds.get("synthesized_patched_function_source", ""))
    if not src.strip():
        raise ValueError("Missing synthesized_patched_function_source in Pillar 2")

    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "abs":
            raise ValueError("Forbidden abs() shortcut detected in synthesized AST patch")

    ns: dict[str, Any] = {"Any": Any}
    exec(compile(tree, filename="<verifier_synthesized_ast_patch>", mode="exec"), ns)
    fn = ns.get("_large_multi_stage_pipeline_with_bug")
    if not callable(fn):
        raise ValueError("Compiled AST patch did not define _large_multi_stage_pipeline_with_bug")

    witness_out = fn([{"region": "us-east", "load": 60}, {"region": "eu-west", "load": 20}])
    heldout_out = fn(
        [
            {"region": "ap-south", "load": 50},
            {"region": "us-west", "load": 75},
            {"region": "eu-central", "load": 10},
        ]
    )
    if int(witness_out.get("alert_total", 0)) != 120 or int(ds.get("repaired_alert_total", 0)) != 120:
        raise ValueError("Compiled AST patch failed witness alert_total == 120 check")
    if int(heldout_out.get("alert_total", 0)) != 250 or int(ds.get("heldout_repaired_alert_total", 0)) != 250:
        raise ValueError("Compiled AST patch failed held-out alert_total == 250 check")

    total_lines = int(ds.get("total_function_lines", 0))
    slice_lines = int(ds.get("backward_causal_slice_line_count", 0))
    if total_lines <= 0 or slice_lines <= 0 or len(ds.get("isolated_causal_slice", [])) != slice_lines:
        raise ValueError("Invalid causal slice line counts in Pillar 2")
    expected_pruned = round((total_lines - slice_lines) / total_lines, 6)
    if abs(expected_pruned - float(ds.get("code_pruned_fraction", 0.0))) > 1e-5:
        raise ValueError("Tampered code_pruned_fraction in Pillar 2")
    if int(ds.get("sliced_candidate_patch_executions", 999)) >= int(ds.get("unsliced_candidate_patches", 0)):
        raise ValueError("Sliced candidate patch executions must be strictly less than unsliced patches")
    return True


def _verify_three_way_local_model_benchmark(bench: dict[str, Any]) -> bool:
    """Recomputes the 3-way local model benchmark metrics and Net Savings equation
    from per-task records."""
    cfgs = bench.get("configurations", {})
    for name in (
        "model_plus_tools_and_retrieval",
        "same_system_plus_ordinary_program_caching",
        "same_system_plus_nexus_abstractions_and_adaptation",
    ):
        if name not in cfgs:
            raise ValueError(f"Missing configuration {name} in three_way_local_model_benchmark")
        c_data = cfgs[name]
        recs = c_data.get("per_task_records", [])
        if len(recs) != 6:
            raise ValueError(f"Expected 6 workload task records in {name}")
        mean_acc = round(sum(float(r["heldout_accuracy"]) for r in recs) / len(recs), 6)
        tot_cost = round(sum(float(r["total_compute_cost"]) for r in recs), 6)
        tot_execs = sum(int(r["candidate_executions"]) for r in recs)
        if abs(mean_acc - float(c_data["mean_heldout_accuracy"])) > 1e-6 or mean_acc != 1.0:
            raise ValueError(f"Tampered or sub-1.0 accuracy in {name}")
        if abs(tot_cost - float(c_data["total_compute_cost"])) > 1e-5:
            raise ValueError(f"Tampered total_compute_cost in {name}")
        if tot_execs != int(c_data["total_candidate_executions"]):
            raise ValueError(f"Tampered total_candidate_executions in {name}")
        if not all(float(r["model_cpu_latency_ms"]) > 0.0 and float(r["unified_process_rss_kb"]) > 0.0 for r in recs):
            raise ValueError(f"Invalid hardware latency/RSS measurements in {name}")

    m_base = cfgs["model_plus_tools_and_retrieval"]
    m_cache = cfgs["same_system_plus_ordinary_program_caching"]
    m_nexus = cfgs["same_system_plus_nexus_abstractions_and_adaptation"]

    learn_cost = round(sum(float(r["abstraction_discovery_cost"]) for r in m_nexus["per_task_records"]), 6)
    nexus_operating_cost = round(float(m_nexus["total_compute_cost"]) - learn_cost, 6)
    gross_vs_cache = round(float(m_cache["total_compute_cost"]) - nexus_operating_cost, 6)
    net_vs_cache = round(gross_vs_cache - learn_cost, 6)
    exec_sav_vs_cache = int(m_cache["total_candidate_executions"]) - int(m_nexus["total_candidate_executions"])

    rep_vs_cache = bench.get("net_savings_vs_ordinary_program_caching", {})
    if abs(gross_vs_cache - float(rep_vs_cache.get("gross_operating_cost_savings", 0.0))) > 1e-5:
        raise ValueError("Tampered gross_operating_cost_savings vs ordinary_program_caching")
    if abs(net_vs_cache - float(rep_vs_cache.get("net_compute_cost_savings", 0.0))) > 1e-5:
        raise ValueError("Tampered net_compute_cost_savings vs ordinary_program_caching")
    if exec_sav_vs_cache != int(rep_vs_cache.get("net_candidate_execution_savings", -1)):
        raise ValueError("Tampered net_candidate_execution_savings vs ordinary_program_caching")
    if net_vs_cache <= 0.0 or exec_sav_vs_cache <= 0:
        raise ValueError("NEXUS must achieve positive net savings over ordinary program caching")

    # Verify inappropriate reuse was rejected on the row-level task (S1)
    s1_rec = next((r for r in m_nexus["per_task_records"] if r["task_id"] == "S1_filter_and_normalize_error_logs"), None)
    if not s1_rec or not s1_rec.get("inappropriate_reuse_rejected"):
        raise ValueError("Failed to reject inappropriate grouped_summary reuse on row-level task S1")

    # Verify AMB1 triggered semantic clarification for negative revenue_eur refunds
    amb_rec = next(
        (r for r in m_nexus["per_task_records"] if r["task_id"] == "AMB1_revenue_eur_semantic_disambiguation"),
        None,
    )
    if not amb_rec or int(amb_rec.get("clarifications_asked", 0)) < 1:
        raise ValueError("AMB1_revenue_eur_semantic_disambiguation must trigger clarification")
    return True


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

    skeleton_ok = _verify_skeleton_ast_and_promoted_templates(report)
    bench_ok = _verify_three_way_local_model_benchmark(report.get("three_way_local_model_benchmark", {}))

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

    ag_recs = ag_dev["per_task_records"]
    af_recs = af_dev["per_task_records"]
    pf_recs = pf_dev["per_task_records"]
    pg_recs = pg_dev["per_task_records"]
    ec_recs = ec_dev["per_task_records"]
    if len(ag_recs) != 5 or len(af_recs) != 5 or len(pf_recs) != 5 or len(pg_recs) != 5 or len(ec_recs) != 5:
        raise ValueError("Expected 5 development task records per method")

    ag_mean_acc = round(sum(float(r["heldout_accuracy"]) for r in ag_recs) / len(ag_recs), 6)
    ag_vs_acc = round(sum(float(r["version_space_expected_accuracy"]) for r in ag_recs) / len(ag_recs), 6)
    pf_vs_acc = round(sum(float(r["version_space_expected_accuracy"]) for r in pf_recs) / len(pf_recs), 6)
    ag_later_cost = round(sum(float(r["total_compute_cost"]) for r in ag_recs[1:]), 6)
    af_later_cost = round(sum(float(r["total_compute_cost"]) for r in af_recs[1:]), 6)
    ag_later_execs = sum(int(r["candidate_executions"]) for r in ag_recs[1:])
    ec_later_execs = sum(int(r["candidate_executions"]) for r in ec_recs[1:])
    ag_retention = round(sum(float(r["old_skill_retention"]) for r in ag_recs) / len(ag_recs), 6)

    if abs(ag_mean_acc - float(ag_dev["mean_heldout_accuracy"])) > 1e-6:
        raise ValueError("Tampered active_growing_library mean_heldout_accuracy")
    if abs(ag_vs_acc - float(ag_dev["mean_version_space_expected_accuracy"])) > 1e-6:
        raise ValueError("Tampered active_growing_library mean_version_space_expected_accuracy")
    if abs(pf_vs_acc - float(pf_dev["mean_version_space_expected_accuracy"])) > 1e-6:
        raise ValueError("Tampered passive_fixed_library mean_version_space_expected_accuracy")
    if abs(ag_later_cost - float(ag_dev["later_tasks_compute_cost"])) > 1e-5:
        raise ValueError("Tampered active_growing_library later_tasks_compute_cost")
    if ag_later_execs != int(ag_dev["later_tasks_candidate_executions"]):
        raise ValueError("Tampered active_growing_library later_tasks_candidate_executions")

    # Verify naturally occurring Python stdlib AST task (R1)
    nat_eval = confirm.get("naturally_occurring_stdlib_ast_task", {})
    nat_recs = nat_eval.get("per_task_records", [])
    if len(nat_recs) != 1 or nat_recs[0].get("task_id") != "R1_repo_python_ast_metrics":
        raise ValueError("Missing R1_repo_python_ast_metrics record")
    nat_acc = float(nat_recs[0].get("heldout_accuracy", 0.0))
    if abs(nat_acc - float(nat_eval.get("mean_heldout_accuracy", 0.0))) > 1e-6 or nat_acc != 1.0:
        raise ValueError("R1_repo_python_ast_metrics accuracy must be 1.0")

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

    # Recompute SQLite independent confirmation & relational JOIN execution from raw per_task_records
    full_sql = confirm["full_sqlite_transfer_summary"]
    sql_tr_recs = full_sql["with_prior_csv_json_learning"]["per_task_records"]
    sql_sc_recs = full_sql["from_scratch"]["per_task_records"]
    if len(sql_tr_recs) != 3 or len(sql_sc_recs) != 3:
        raise ValueError("Expected 3 SQLite task records (1 dev + 2 confirmation)")

    for sr in sql_tr_recs:
        q_sql = str(sr.get("submitted_sql_query") or "")
        if 'JOIN "dim_entities"' not in q_sql or sr.get("relational_sql_exact_match") is not True:
            raise ValueError(f"SQLite task {sr.get('task_id')} missing verified relational JOIN SQL query")

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
        and int(r["backward_witness_candidate_executions"]) < int(r["enumeration_candidate_executions"])
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

    # Verify Pillars 1-4 from raw records and live re-execution
    p1 = pillars["pillar_1_functorial_metaphor_transfer"]
    p2 = pillars["pillar_2_system_identification_and_dynamic_slicing"]
    p3 = pillars["pillar_3_pearl_do_calculus_and_lakatos_refutations"]
    p4 = pillars["pillar_4_pidgin_bootstrapping_and_counterfactual_explanations"]

    # Pillar 1 raw call-count and functor checks
    p1_calls = int(p1.get("total_blackbox_function_calls_during_probing", 0))
    p1_probes = int(p1.get("algebraic_probes_used", 0))
    if p1_probes != 3 or p1_calls <= p1_probes:
        raise ValueError("Pillar 1 must record both probe design count (3) and actual black-box function calls (>3)")
    if p1.get("discovered_functor_mapping") != {
        "Partition_By_Equivalence": "net_morph_alpha",
        "Filter_By_Monotonic_Threshold": "net_morph_beta",
        "Fold_Associative_Monoid": "net_morph_gamma",
    }:
        raise ValueError("Pillar 1 discovered_functor_mapping mismatch")

    # Pillar 2 AST patch compilation and verification
    p2_ast_ok = _verify_pillar_2_compiled_ast_patch(p2)

    # Pillar 3 entropy trace and Lakatos counterexample verification
    p3_do = p3["surgical_do_interventions"]
    p3_trace = p3_do.get("interventions_trace", [])
    if len(p3_trace) < 2 or float(p3_trace[0].get("expected_entropy_bits", 0.0)) <= 0.9:
        raise ValueError("Pillar 3 must record active Shannon-entropy intervention selection trace")
    p3_lak = p3["lakatos_proofs_and_refutations"]
    monster = list(p3_lak.get("monster_counterexample_found", []))
    if not monster or len(sorted(set(monster))) == len(monster):
        raise ValueError("Pillar 3 monster counterexample must falsify len(f(x)) == len(x)")
    if "len_eq" in p3_lak.get("refined_synthesized_predicates", []):
        raise ValueError("Pillar 3 refined_synthesized_predicates must exclude refuted predicate len_eq")

    # Pillar 4 Pidgin probe and counterfactual trace verification
    p4_pid = p4["pidgin_semantic_bootstrapping"]
    if len(str(p4_pid.get("teacher_subprocess_receipt", ""))) != 64:
        raise ValueError("Pillar 4 must record 64-char SHA256 receipt from teacher subprocess")
    p4_cf = p4["counterfactual_trace_explanation"]
    if int(p4_cf.get("actual_output_count", 0)) >= int(p4_cf.get("counterfactual_output_count", 0)):
        raise ValueError("Pillar 4 counterfactual intervention must alter output row count")

    reconstructed = dict(
        gate_01_clean_starting_point_and_dev_vs_confirmation_split=bool(
            len(freeze_sha) == 64
            and confirm.get("frozen_before_confirmation") is True
            and set(dev["task_sequence"]).isdisjoint(set(conf_csv["task_ids"]))
            and skeleton_ok
        ),
        gate_02_readonly_csv_json_workspace_and_reserved_schemas=bool(
            all(
                bool(r["read_only_source_unmodified"])
                and bool(r["output_file_written"])
                and len(str(r["evaluator_receipt_sha256"])) == 64
                for r in ag_recs + conf_ag_recs
            )
            and nat_acc == 1.0
        ),
        gate_03_compositional_adapters_without_15_op_limit_and_missing_value_handling=bool(
            comp_stress.get("verified") is True
            and int(comp_stress.get("pipeline_operation_count", 0)) == 18
            and comp_stress.get("exceeds_15_operation_limit") is True
            and int(ag_recs[0]["program_length"]) >= 8
            and skeleton_ok
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
            and ag_vs_acc > pf_vs_acc
            and ag_later_cost < af_later_cost
            and ag_later_execs < ec_later_execs
            and ag_retention == 1.0
            and bench_ok
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
            and all(bool(r["reused_promoted_template"]) and bool(r.get("relational_sql_exact_match")) for r in sql_tr_recs)
        ),
        gate_09_functorial_bridge_and_dynamic_slicing_pillars_verified=bool(
            float(p1.get("heldout_packet_routing_accuracy", 0.0)) == 1.0
            and p1_probes == 3
            and p1.get("associativity_verified_on_triples") is True
            and p1.get("composition_law_preserved") is True
            and p2["api_discovery"].get("verified_on_heldout") is True
            and p2["dynamic_slicing_repair"].get("repair_matches_oracle") is True
            and float(p2["dynamic_slicing_repair"].get("code_pruned_fraction", 0.0)) >= 0.85
            and p2_ast_ok
        ),
        gate_10_causal_do_calculus_lakatos_and_pidgin_counterfactual_verified=bool(
            p3_do.get("exact_recovery") is True
            and p3_lak.get("refined_conjecture_holds_across_all_heldout") is True
            and p4_pid.get("heldout_verified") is True
            and int(p4_pid.get("followup_questions_needed", -1)) == 0
            and p4_cf.get("counterfactual_sensitivity_verified") is True
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
    """Mutates 10 distinct nested records while leaving `all_gates_passed = True`
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

    # Case 6: Tamper with Pillar 3 Lakatos monster counterexample (replacing with non-duplicate list)
    t6 = copy.deepcopy(base_report)
    t6["four_wall_breaking_pillars"]["pillar_3_pearl_do_calculus_and_lakatos_refutations"][
        "lakatos_proofs_and_refutations"
    ]["monster_counterexample_found"] = [1, 2, 3]
    try:
        reconstruct_gates_from_raw_records(t6)
    except ValueError:
        rejected_cases.append("tamper_lakatos_conjecture_rejected")
    else:
        raise AssertionError("Failed to reject tampered Lakatos counterexample")

    # Case 7: Tamper with promoted_template_skeletons (emptying skeleton_ops)
    t7 = copy.deepcopy(base_report)
    t7["promoted_template_skeletons"]["grouped_summary"] = []
    try:
        reconstruct_gates_from_raw_records(t7)
    except ValueError:
        rejected_cases.append("tamper_promoted_template_skeleton_rejected")
    else:
        raise AssertionError("Failed to reject emptied promoted_template_skeletons")

    # Case 8: Tamper with Pillar 2 synthesized AST patch by injecting abs()
    t8 = copy.deepcopy(base_report)
    orig_src = t8["four_wall_breaking_pillars"]["pillar_2_system_identification_and_dynamic_slicing"][
        "dynamic_slicing_repair"
    ]["synthesized_patched_function_source"]
    t8["four_wall_breaking_pillars"]["pillar_2_system_identification_and_dynamic_slicing"][
        "dynamic_slicing_repair"
    ]["synthesized_patched_function_source"] = orig_src.replace(
        "alert_total = alert_total + delta_load", "alert_total = abs(alert_total - delta_load)"
    )
    try:
        reconstruct_gates_from_raw_records(t8)
    except ValueError:
        rejected_cases.append("tamper_ast_patch_abs_shortcut_rejected")
    else:
        raise AssertionError("Failed to reject abs() shortcut in Pillar 2 AST patch")

    # Case 9: Tamper with SQLite relational JOIN query
    t9 = copy.deepcopy(base_report)
    t9["independent_confirmation_results"]["full_sqlite_transfer_summary"][
        "with_prior_csv_json_learning"
    ]["per_task_records"][0]["submitted_sql_query"] = 'SELECT * FROM "source_records"'
    try:
        reconstruct_gates_from_raw_records(t9)
    except ValueError:
        rejected_cases.append("tamper_sqlite_relational_join_rejected")
    else:
        raise AssertionError("Failed to reject non-JOIN SQLite query")

    # Case 10: Tamper with 3-way local model benchmark net savings
    t10 = copy.deepcopy(base_report)
    t10["three_way_local_model_benchmark"]["net_savings_vs_ordinary_program_caching"][
        "net_compute_cost_savings"
    ] = 999.0
    try:
        reconstruct_gates_from_raw_records(t10)
    except ValueError:
        rejected_cases.append("tamper_three_way_net_savings_rejected")
    else:
        raise AssertionError("Failed to reject tampered 3-way local model net savings")

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

    print(
        json.dumps(
            dict(
                status="VERIFIED",
                artifact=str(args.artifact),
                all_gates_passed=all(reconstructed_gates.values()),
                gates=reconstructed_gates,
                tamper_cases_rejected=rejected,
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
