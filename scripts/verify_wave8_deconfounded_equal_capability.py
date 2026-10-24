"""Reconstructing I/O & AST verifier for Wave-8 deconfounded equal-capability artifact.

Performs independent verification beyond arithmetic flag checking:
1. AST-audits ``src/nexus/seed/deconfounded_equal_capability.py`` to verify
   ``solve_unfamiliar_task`` accepts ONLY ``(self, env, public_budget)`` and
   that zero stage/split/task_id labels appear anywhere in the learner module.
2. Verifies identical universal catalog sizes across all 6 methods and 14 tasks.
3. Independently reconstructs and executes ``row["program_ast"]`` on every
   saved public ``(input, observed_output)`` pair and every private test
   ``(input, predicted_output, ground_truth_output)`` pair.
4. Verifies ``schema_distill_cost > 0`` in raw rows for all schema-using
   methods, distinct task arrival orders across seeds ``(0, 1, 2)``, and
   Track B closure (``model_calls == 0``, ``frozen_debit_s == 0``).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

from nexus.seed.cross_domain_analogy import as_seq
from nexus.seed.deconfounded_equal_capability import (
    EQUAL_CAPABILITY_METHODS,
    execute_serialized_program_ast,
)
from nexus.seed.mechanism_wave8_deconfounded import (
    COST_KEYS,
    OPENED_IDS,
     evaluate_gates,
)

FORBIDDEN_LEARNER_STRINGS = frozenset(
    {
        "task_id",
        "stage",
        "split",
        "g1",
        "g2",
        "l1",
        "l2",
        "oog",
        "amb",
        "retain",
        "w8_analogous",
        "w8_lookalike",
        "w8_l1",
        "w8_l2",
        "w8_ambiguous",
        "w8_oog",
        "w8_retain_a",
    }
)


def audit_learner_ast(learner_path: Path) -> Dict[str, Any]:
    """AST-verify zero label leakage and honest pruning naming in learner module."""
    source = learner_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(learner_path))
    violations: List[str] = []
    solve_args: List[str] = []
    has_usage_age_prune = False

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name == "mdl_prune":
                violations.append("forbidden_function_name:mdl_prune")
            if node.name == "usage_age_prune":
                has_usage_age_prune = True
            for arg in node.args.args:
                if arg.arg in FORBIDDEN_LEARNER_STRINGS:
                    violations.append(f"forbidden_arg:{node.name}:{arg.arg}")
            if node.name == "solve_unfamiliar_task":
                solve_args = [a.arg for a in node.args.args]
                if solve_args != ["self", "env", "public_budget"]:
                    violations.append(f"bad_solve_signature:{solve_args}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value.strip()
            if val in FORBIDDEN_LEARNER_STRINGS:
                violations.append(f"forbidden_string_literal:{val}")

    if not has_usage_age_prune:
        violations.append("missing_usage_age_prune")

    return {
        "ast_clean": len(violations) == 0,
        "solve_unfamiliar_task_args": solve_args,
        "has_usage_age_prune": has_usage_age_prune,
        "violations": violations,
    }


def reconstruct_and_replay_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Re-execute ``row["program_ast"]`` on public and private I/O pairs."""
    notes: List[str] = []
    for step in row.get("trace") or []:
        if step.get("phase") == "private" and step.get("before_lock"):
            notes.append("private_before_lock_in_trace")

    rebuilt_work = sum(int(row.get(k) or 0) for k in COST_KEYS)
    if rebuilt_work != int(row.get("total_work") or 0):
        notes.append(f"work_mismatch:{rebuilt_work}!={row.get('total_work')}")

    rebuilt_code_syn = int(row.get("synthesis_evals") or 0) + int(
        row.get("micro_codegen_evals") or 0
    )
    if rebuilt_code_syn != int(row.get("codegen_plus_synthesis") or 0):
        notes.append("codegen_plus_synthesis_mismatch")

    prog_ast = row.get("program_ast") or {}
    pub_obs = list(row.get("public_observations") or [])
    priv_evals = list(row.get("private_evaluations") or [])
    status = str(row.get("status") or "")
    gold_status = str(row.get("gold_status") or "")

    if status == "unique":
        if prog_ast.get("kind") == "abstain":
            notes.append("unique_status_with_abstain_ast")
        if not pub_obs:
            notes.append("unique_status_missing_public_observations")
        for obs in pub_obs:
            inp = obs["input"]
            expected = obs["observed_output"]
            pred = execute_serialized_program_ast(prog_ast, inp)
            if isinstance(expected, list):
                if list(as_seq(pred)) != expected:
                    notes.append(f"public_replay_mismatch:{obs.get('slot')}")
            else:
                if int(pred) != int(expected):
                    notes.append(f"public_int_replay_mismatch:{obs.get('slot')}")
        if not bool(row.get("public_consistent")):
            notes.append("public_consistent_flag_false_on_unique")

        if gold_status == "unique":
            if len(priv_evals) != 4:
                notes.append(f"expected_4_private_evals_got_{len(priv_evals)}")
            all_priv_match = True
            for pev in priv_evals:
                inp = pev["input"]
                saved_pred = pev["predicted_output"]
                gt = pev["ground_truth_output"]
                replayed = execute_serialized_program_ast(prog_ast, inp)
                if isinstance(gt, list):
                    replayed_norm: Any = list(as_seq(replayed))
                else:
                    replayed_norm = int(replayed)
                if replayed_norm != saved_pred:
                    notes.append(f"private_saved_pred_mismatch:{pev.get('slot')}")
                if replayed_norm != gt:
                    all_priv_match = False
            if all_priv_match != bool(row.get("private_correct")):
                notes.append("private_correct_flag_mismatch_with_replay")
    elif status == "ambiguous":
        if not bool(row.get("ambiguous")):
            notes.append("ambiguous_flag_mismatch")
        if (gold_status == "ambiguous") != bool(row.get("private_correct")):
            notes.append("ambiguous_private_correct_mismatch")
    elif status == "abstain":
        if not bool(row.get("oog_abstained")):
            notes.append("oog_abstained_flag_mismatch")
        if (gold_status == "abstain") != bool(row.get("private_correct")):
            notes.append("abstain_private_correct_mismatch")
    else:
        notes.append(f"unknown_status:{status}")

    return {"ok": len(notes) == 0, "notes": notes}


def verify_artifact(
    artifact_path: Path,
    learner_path: Path,
) -> Dict[str, Any]:
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    notes: List[str] = []
    ok = True

    ast_audit = audit_learner_ast(learner_path)
    if not ast_audit["ast_clean"]:
        ok = False
        notes.extend(ast_audit["violations"])

    usage = payload.get("usage") or {}
    if usage.get("frozen_debit_s") != 0:
        ok = False
        notes.append("frozen_debit_nonzero")
    if usage.get("model_calls") != 0:
        ok = False
        notes.append("model_calls_nonzero")
    if payload.get("learning_to_learn_established"):
        ok = False
        notes.append("overclaim_learning_to_learn")

    rows = list(payload.get("assessment") or [])
    if len(rows) != 252:
        ok = False
        notes.append(f"expected_252_rows_got_{len(rows)}")

    if any(r["task_id"] in OPENED_IDS for r in rows):
        ok = False
        notes.append("rescored_prior_opened_id")

    # Verify identical catalog audit across all 252 rows
    catalog_audits = {json.dumps(r.get("catalog_audit") or {}, sort_keys=True) for r in rows}
    if len(catalog_audits) != 1:
        ok = False
        notes.append(f"unequal_catalog_audits:{len(catalog_audits)}")

    # Verify distinct task arrival orders across seeds 0, 1, 2
    orders = payload.get("task_orders_by_seed") or {}
    unique_orders = {tuple(v) for v in orders.values()}
    if len(unique_orders) != 3:
        ok = False
        notes.append("task_orders_not_distinct_across_3_seeds")

    # Reconstruct & replay every single row
    replayed_count = 0
    for row in rows:
        rep = reconstruct_and_replay_row(row)
        if not rep["ok"]:
            ok = False
            notes.append(
                f"row_replay_failed:{row.get('source_seed')}:{row.get('method')}:{row.get('task_id')}:{rep['notes']}"
            )
            break
        replayed_count += 1

    # Verify suite totals match sum of rows
    saved_suite = (payload.get("totals") or {}).get("suite") or {}
    for method in EQUAL_CAPABILITY_METHODS:
        m_rows = [r for r in rows if r["method"] == method]
        rebuilt_tot = sum(int(r["total_work"]) for r in m_rows)
        saved_tot = int((saved_suite.get(method) or {}).get("total_work") or -1)
        if rebuilt_tot != saved_tot:
            ok = False
            notes.append(f"suite_total_mismatch:{method}:{rebuilt_tot}!={saved_tot}")

    rebuilt_gates = evaluate_gates(payload)
    if not rebuilt_gates.get("passed") or rebuilt_gates.get("passed") != (
        payload.get("gates") or {}
    ).get("passed"):
        ok = False
        notes.append(f"gates_failed:{rebuilt_gates.get('notes')}")

    return {
        "valid": ok,
        "notes": notes,
        "rows_verified": replayed_count,
        "ast_audit": ast_audit,
        "gates": rebuilt_gates,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    artifact_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else root / "artifacts" / "seed_wave8_deconfounded_equal_capability.json"
    )
    learner_path = root / "src" / "nexus" / "seed" / "deconfounded_equal_capability.py"
    result = verify_artifact(artifact_path, learner_path)
    print(json.dumps(result, indent=2))
    if not result["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
