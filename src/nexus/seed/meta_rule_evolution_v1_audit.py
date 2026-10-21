"""Adversarial saved-data and code audit of Meta-Rule Evolution v1.

Audits src/nexus/seed/meta_rule_evolution.py and artifacts/seed_meta_rule_evolution.json
across all 15 specified evaluator-leakage, guided-injection, isomorphism, Dream,
and Sleep confounds without modifying or deleting the historical v1 artifact.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from nexus.seed import meta_rule_evolution as v1


HONEST_V1_RETRACTION = (
    "Meta-Rule Evolution v1 passed its internal synthetic contract but does not "
    "establish bounded learning-to-learn because evaluator-derived hypothesis labels, "
    "isomorphic grammar families, guided rule injection and non-executed protected "
    "assessments confound the result."
)


def run_v1_adversarial_audit(repository: Path | str | None = None) -> dict[str, Any]:
    repo = Path(repository) if repository is not None else Path(__file__).resolve().parents[3]
    code_path = repo / "src/nexus/seed/meta_rule_evolution.py"
    cfg_path = repo / "configs/seed_meta_rule_evolution.json"
    artifact_path = repo / "artifacts/seed_meta_rule_evolution.json"
    source_text = code_path.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    saved_artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    # Inspect live task objects produced by v1.build_grammar_tasks
    sample_tasks_list = v1.build_grammar_tasks("list_transformations", 1751000001)
    sample_tasks_bool = v1.build_grammar_tasks("boolean_mechanisms", 1751000001)
    sample_tasks_graph = v1.build_grammar_tasks("relational_graphs", 1751000001)
    sample_tasks_sealed = v1.build_grammar_tasks("sealed_action_state_transitions", 1751000001)
    sample_task = sample_tasks_list[0]
    sample_profiles = sample_task["hypothesis_profiles"]

    # 1. hypothesis_profiles exposes exact_consistent
    exposes_exact_consistent = all("exact_consistent" in hp for hp in sample_profiles)
    # 2. hypothesis_profiles exposes coarse_consistent
    exposes_coarse_consistent = all("coarse_consistent" in hp for hp in sample_profiles)
    # 3. hypothesis_profiles exposes effect_distance and state_key
    exposes_effect_distance_and_state_key = all(
        "effect_distance" in hp and "state_key" in hp for hp in sample_profiles
    )
    # 4. execute_learning_rule receives target_ops
    receives_target_ops = "target_ops" in sample_task
    # 5. execute_learning_rule receives true_effect_state
    receives_true_effect_state = "true_effect_state" in sample_task
    # 6. macro_discount reads target_ops
    macro_discount_reads_target_ops = 'task["target_ops"]' in source_text and "macro_discount" in source_text

    # 7. heldout_accuracy is assigned from exact_consistent rather than executed protected examples
    heldout_assigned_from_exact_consistent = (
        'if accepted["exact_consistent"]:' in source_text
        and "heldout_accuracy = 1.0" in source_text
    )
    # Demonstrate empirically: mutate protected_assessment outputs to bogus values and run v1.execute_learning_rule
    tampered_task = copy.deepcopy(sample_task)
    for ex in tampered_task["protected_assessment"]:
        ex["output"] = ["TAMPERED_IMPOSSIBLE_OUTPUT_999999"]
    kernel = v1.ImmutableTrustedKernel(cfg)
    w_rule = {
        "rule_id": "audit_probe_winner",
        "origin": "evolved",
        "instructions": [
            "OBSERVE",
            "GENERATE_TYPED_HYPOTHESES",
            "PREDICT_EFFECTS",
            "MERGE_EQUIVALENT",
            "DISCARD_HYPOTHESIS",
            "FILTER_INCONSISTENT",
            "RANK_BY_MDL",
            "SELECT_QUERY_BY_INFORMATION_GAIN",
            "RUN_EXPERIMENT",
            "FILTER_INCONSISTENT",
            "ACCEPT_IF_IDENTIFIED",
            "CREATE_CAPSULE",
            "RUN_VALIDATION",
            "STOP",
        ],
        "stopping_threshold": 1,
        "tie_breaker": "effect_distance",
        "query_strategy": "effect_partition",
        "validation_tests_required": 1,
    }
    res_untampered = kernel.execute_learning_rule(w_rule, sample_task)
    res_tampered = kernel.execute_learning_rule(w_rule, tampered_task)
    heldout_ignores_protected_outputs = (
        res_untampered["task_success"] == 1.0
        and res_tampered["task_success"] == 1.0
    )

    # 8. protected_assessment outputs are present in the learner-facing object
    protected_outputs_in_learner_task = (
        "protected_assessment" in sample_task
        and all("output" in item for item in sample_task["protected_assessment"])
    )

    # 9. the structured winning rule is manually injected into the initial population
    init_pop = v1.build_initial_population(1751000001, 32)
    structured_winner_injected_in_init_pop = (
        init_pop[5]["instructions"] == [
            "OBSERVE",
            "GENERATE_TYPED_HYPOTHESES",
            "PREDICT_EFFECTS",
            "MERGE_EQUIVALENT",
            "FILTER_INCONSISTENT",
            "RANK_BY_MDL",
            "SELECT_QUERY_BY_INFORMATION_GAIN",
            "RUN_EXPERIMENT",
            "FILTER_INCONSISTENT",
            "ACCEPT_IF_IDENTIFIED",
            "CREATE_CAPSULE",
            "RUN_VALIDATION",
            "STOP",
        ]
        and "if idx == 0:" in source_text
    )

    # 10. a guided winning rule is manually injected in every generation
    guided_winner_injected_every_generation = (
        "if child_idx == 0:" in source_text
        and '"DISCARD_HYPOTHESIS"' in source_text
        and 'child["query_strategy"] = "effect_partition"' in source_text
    )

    # 11. random_evolution_control is overwritten after its evolution
    random_control_overwritten_after_evolution = (
        "random_control_rule = rand_pop[-1]" in source_text
        and 'random_control_rule["instructions"] = [' in source_text
        and 'random_control_rule["query_strategy"] = "random"' in source_text
    )

    # 12. the four grammars are isomorphic renamings of the same five behavioral transformations
    idx_by_grammar = {
        g: [
            tuple(v1.GRAMMAR_PRIMITIVES[g].index(op) for op in t["target_ops"])
            for t in tasks
        ]
        for g, tasks in (
            ("list_transformations", sample_tasks_list),
            ("boolean_mechanisms", sample_tasks_bool),
            ("relational_graphs", sample_tasks_graph),
            ("sealed_action_state_transitions", sample_tasks_sealed),
        )
    }
    decoded_out_by_grammar = {
        g: [
            v1.decode_grammar_magnitudes(g, t["initial_observation"]["output"])
            for t in tasks
        ]
        for g, tasks in (
            ("list_transformations", sample_tasks_list),
            ("boolean_mechanisms", sample_tasks_bool),
            ("relational_graphs", sample_tasks_graph),
            ("sealed_action_state_transitions", sample_tasks_sealed),
        )
    }
    grammars_isomorphic_renamings = (
        idx_by_grammar["list_transformations"] == idx_by_grammar["boolean_mechanisms"]
        and idx_by_grammar["list_transformations"] == idx_by_grammar["relational_graphs"]
        and idx_by_grammar["list_transformations"] == idx_by_grammar["sealed_action_state_transitions"]
        and decoded_out_by_grammar["list_transformations"] == decoded_out_by_grammar["boolean_mechanisms"]
        and decoded_out_by_grammar["list_transformations"] == decoded_out_by_grammar["relational_graphs"]
        and decoded_out_by_grammar["list_transformations"] == decoded_out_by_grammar["sealed_action_state_transitions"]
        and "_base_structured_ints" in source_text
    )

    # 13. Dream tasks do not influence the evolution loop
    for_gen_loop_sources = [
        ast.unparse(stmt)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_single_seed_evolution"
        for stmt in node.body
        if isinstance(stmt, ast.For) and "generations" in ast.unparse(stmt.iter)
    ]
    dream_not_in_evolution_loop = (
        len(for_gen_loop_sources) >= 1
        and all("run_dream_adversarial_phase" not in src for src in for_gen_loop_sources)
        and 'sem_sha = digest(dict(grammar=t["grammar"], effect=t["true_effect_state"], seed=seed))' in source_text
    )

    # 14. Sleep validation reads stored passed booleans instead of rerunning tests
    sleep_reads_stored_passed_booleans = 'if t_item.get("passed", False):' in source_text

    # 15. DistilledChoicePolicy is a stub rather than a fitted policy
    distilled_policy_is_stub = (
        "distilled_agreement = 1.0 if distilled_examples > 0 else 0.0" in source_text
        and "top1_choice_agreement=distilled_agreement" in source_text
    )

    findings = {
        "1_hypothesis_profiles_exposes_exact_consistent": {
            "confirmed": bool(exposes_exact_consistent),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:766-776",
            "evidence": "Each entry in task['hypothesis_profiles'] includes precomputed 'exact_consistent': (h_pred_eff == true_eff).",
        },
        "2_hypothesis_profiles_exposes_coarse_consistent": {
            "confirmed": bool(exposes_coarse_consistent),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:765-775",
            "evidence": "Each entry in task['hypothesis_profiles'] includes precomputed 'coarse_consistent'.",
        },
        "3_hypothesis_profiles_exposes_effect_distance_and_state_key": {
            "confirmed": bool(exposes_effect_distance_and_state_key),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:758-777",
            "evidence": "Each entry in task['hypothesis_profiles'] exposes 'effect_distance' and 'state_key'.",
        },
        "4_execute_learning_rule_receives_target_ops": {
            "confirmed": bool(receives_target_ops),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:785",
            "evidence": "task dict passed to execute_learning_rule contains 'target_ops': list(target_ops).",
        },
        "5_execute_learning_rule_receives_true_effect_state": {
            "confirmed": bool(receives_true_effect_state),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:789",
            "evidence": "task dict passed to execute_learning_rule contains 'true_effect_state': true_eff.",
        },
        "6_macro_discount_reads_target_ops": {
            "confirmed": bool(macro_discount_reads_target_ops),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:926-933",
            "evidence": "execute_learning_rule computes macro_discount by matching macros against task['target_ops'].",
        },
        "7_heldout_accuracy_assigned_from_exact_consistent": {
            "confirmed": bool(heldout_assigned_from_exact_consistent and heldout_ignores_protected_outputs),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:1137-1142",
            "evidence": "heldout_accuracy is assigned from accepted['exact_consistent'] (1.0) or accepted['coarse_consistent'] (0.25); tampering with protected_assessment outputs leaves task_success == 1.0.",
        },
        "8_protected_assessment_outputs_in_learner_object": {
            "confirmed": bool(protected_outputs_in_learner_task),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:792",
            "evidence": "task['protected_assessment'] with ground-truth 'output' fields is inside the learner-facing task dict.",
        },
        "9_structured_winning_rule_injected_in_initial_population": {
            "confirmed": bool(structured_winner_injected_in_init_pop),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:1376-1395",
            "evidence": "build_initial_population manually inserts the 13-instruction compositional candidate at idx == 0 (population index 5).",
        },
        "10_guided_winning_rule_injected_every_generation": {
            "confirmed": bool(guided_winner_injected_every_generation),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:1813-1834",
            "evidence": "run_single_seed_evolution overwrites child_idx == 0 in every generation with the 14-instruction guided winner.",
        },
        "11_random_evolution_control_overwritten_after_evolution": {
            "confirmed": bool(random_control_overwritten_after_evolution),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:1855-1871",
            "evidence": "After the 20-generation random loop, random_control_rule is overwritten with a fixed 10-instruction rule with stopping_threshold=2.",
        },
        "12_four_grammars_are_isomorphic_renamings": {
            "confirmed": bool(grammars_isomorphic_renamings),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:210-370",
            "evidence": "All four grammars decode to _base_structured_ints and apply identical target_ops sequences over reverse/sort/unique/increment/decrement/even.",
        },
        "13_dream_tasks_do_not_influence_evolution_loop": {
            "confirmed": bool(dream_not_in_evolution_loop),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:1565, 2020",
            "evidence": "run_dream_adversarial_phase is only called at line 2020 after the 20-generation loop and after rule freezing, and includes seed in its semantic novelty hash.",
        },
        "14_sleep_validation_reads_stored_passed_booleans": {
            "confirmed": bool(sleep_reads_stored_passed_booleans),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:1681-1684",
            "evidence": "run_sleep_compression_and_distillation checks t_item.get('passed', False) without re-executing capsule programs.",
        },
        "15_distilled_choice_policy_is_stub": {
            "confirmed": bool(distilled_policy_is_stub),
            "code_location": "src/nexus/seed/meta_rule_evolution.py:1687-1704",
            "evidence": "distilled_policy sets top1_choice_agreement = 1.0 if len(capsules) > 0 else 0.0 without fitting or evaluating a policy.",
        },
    }

    all_confirmed = all(item["confirmed"] for item in findings.values())
    raw_v1_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()

    return {
        "schema": "seed_meta_rule_evolution_v1_adversarial_audit_v1",
        "audited_artifact_path": "artifacts/seed_meta_rule_evolution.json",
        "audited_artifact_sha256": raw_v1_sha256,
        "audited_code_path": "src/nexus/seed/meta_rule_evolution.py",
        "audited_code_sha256": hashlib.sha256(code_path.read_bytes()).hexdigest(),
        "original_artifact_preserved_unchanged": raw_v1_sha256 == "818300f5100bccf5fcbb461b03aee86742b2173847bbd09d1f52dbd811ec8292",
        "original_v1_verdict_recorded": saved_artifact["evaluation"]["verdict"],
        "confounds_checked": len(findings),
        "confounds_confirmed": sum(1 for item in findings.values() if item["confirmed"]),
        "all_15_confounds_confirmed": all_confirmed,
        "findings": findings,
        "retraction_statement": HONEST_V1_RETRACTION,
    }


def write_v1_adversarial_audit(repository: Path | str | None = None) -> dict[str, Any]:
    repo = Path(repository) if repository is not None else Path(__file__).resolve().parents[3]
    report = run_v1_adversarial_audit(repo)
    out_path = repo / "artifacts/seed_meta_rule_evolution_v1_audit.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
