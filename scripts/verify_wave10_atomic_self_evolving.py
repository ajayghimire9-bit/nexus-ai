"""Reconstructing I/O, SHA-256 Freeze & AST Verifier for Wave-10 Atomic Self-Evolving Operators.

Enforces:
1. Prior learner files ``deconfounded_equal_capability.py`` and
   ``wave9_learned_abstraction_meta_control.py`` remain untouched via SHA-256.
2. AST-audits ``src/nexus/seed/wave10_atomic_self_evolving_learner.py`` for
   strict label-blindness (``solve_unfamiliar_task(self, env, public_budget)``
   and zero forbidden stage/split/task_id labels).
3. Independently reconstructs and executes ``row["program_ast"]`` on all saved
   public and private I/O pairs across all 288 cells (3 seeds x 6 methods x 16 tasks).
4. Verifies Gate 1 (equal atomic starting catalog & label blindness), Gate 2
   (fixes all 3 ``d0a8bb1`` overhead bottlenecks), and Gate 3 (genuine
   self-evolving Pareto win on both ``codegen_plus_synthesis`` and ``total_work``).
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

from nexus.seed.cross_domain_analogy import as_seq
from nexus.seed.mechanism_wave10_atomic_evolution import (
    COST_KEYS,
    OPENED_IDS,
    evaluate_gates,
)
from nexus.seed.wave10_atomic_self_evolving_learner import (
    WAVE10_METHODS,
    execute_wave10_program_ast,
)

FROZEN_DECONFOUNDED_LEARNER_SHA256 = (
    "ef0bceb9e10d9f14febdb0df75a6516a9413878f3aa2d63177dda212de37fe1e"
)
FROZEN_WAVE9_LEARNER_SHA256 = (
    "3be126c6470fc45d29a35863aea9d68ca30497756f9ef4ebbdd02c1662677143"
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
        "w9f_g1_analogous",
        "w9f_g2_lookalike",
        "w9f_l1_invention_reuse",
        "w9f_l2_composition_reuse",
        "w9f_delayed_post_prune",
        "w9f_ambiguous",
        "w9f_oog",
        "w9f_retain_domain_a",
        "w10a_g1_base",
        "w10a_g2_lookalike",
        "w10a_step_predicate_evolution",
        "w10a_step_transform_evolution",
        "w10a_deep_compositional",
        "w10a_spurious_once_used",
        "w10a_delayed_post_prune",
        "w10a_ambiguous",
        "w10a_oog",
    }
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_learner_ast(learner_path: Path) -> Dict[str, Any]:
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
    notes: List[str] = []
    for step in row.get("trace") or []:
        if step.get("phase") == "private" and step.get("before_lock"):
            notes.append("private_before_lock_in_trace")

    rebuilt_work = sum(int(row.get(k) or 0) for k in COST_KEYS)
    if rebuilt_work != int(row.get("total_work") or 0):
        notes.append(f"work_mismatch:{rebuilt_work}!={row.get('total_work')}")

    rebuilt_code_syn = (
        int(row.get("synthesis_evals") or 0)
        + int(row.get("micro_codegen_evals") or 0)
        + int(row.get("archive_lookup_evals") or 0)
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
            pred = execute_wave10_program_ast(prog_ast, inp)
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
                replayed = execute_wave10_program_ast(prog_ast, inp)
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


def verify_wave10_artifact(
    artifact_path: Path,
    w8_learner_path: Path,
    w9_learner_path: Path,
    w10_learner_path: Path,
) -> Dict[str, Any]:
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    notes: List[str] = []
    ok = True

    w8_sha = sha256_file(w8_learner_path)
    w9_sha = sha256_file(w9_learner_path)
    if w8_sha != FROZEN_DECONFOUNDED_LEARNER_SHA256:
        ok = False
        notes.append(f"w8_learner_modified:{w8_sha}")
    if w9_sha != FROZEN_WAVE9_LEARNER_SHA256:
        ok = False
        notes.append(f"w9_learner_modified:{w9_sha}")

    w10_ast_audit = audit_learner_ast(w10_learner_path)
    if not w10_ast_audit["ast_clean"]:
        ok = False
        notes.extend(w10_ast_audit["violations"])

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
    if len(rows) != 288:
        ok = False
        notes.append(f"expected_288_rows_got_{len(rows)}")

    if any(r["task_id"] in OPENED_IDS for r in rows):
        ok = False
        notes.append("rescored_prior_opened_id")

    catalog_audits = {
        json.dumps(r.get("catalog_audit") or {}, sort_keys=True) for r in rows
    }
    if len(catalog_audits) != 1:
        ok = False
        notes.append(f"unequal_catalog_audits:{len(catalog_audits)}")

    orders = payload.get("task_orders_by_seed") or {}
    unique_orders = {tuple(v) for v in orders.values()}
    if len(unique_orders) != 3:
        ok = False
        notes.append("task_orders_not_distinct_across_3_seeds")

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

    saved_suite = (payload.get("totals") or {}).get("suite") or {}
    for method in WAVE10_METHODS:
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
        "w8_learner_sha256_verified": w8_sha == FROZEN_DECONFOUNDED_LEARNER_SHA256,
        "w9_learner_sha256_verified": w9_sha == FROZEN_WAVE9_LEARNER_SHA256,
        "wave10_ast_audit": w10_ast_audit,
        "gates": rebuilt_gates,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    artifact_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else root / "artifacts" / "seed_wave10_atomic_self_evolving_operators.json"
    )
    w8_path = root / "src" / "nexus" / "seed" / "deconfounded_equal_capability.py"
    w9_path = (
        root / "src" / "nexus" / "seed" / "wave9_learned_abstraction_meta_control.py"
    )
    w10_path = (
        root / "src" / "nexus" / "seed" / "wave10_atomic_self_evolving_learner.py"
    )
    result = verify_wave10_artifact(artifact_path, w8_path, w9_path, w10_path)
    print(json.dumps(result, indent=2))
    if not result["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
