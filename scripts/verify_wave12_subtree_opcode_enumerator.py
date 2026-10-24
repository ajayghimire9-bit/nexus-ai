#!/usr/bin/env python3
"""Standalone replaying verifier for Wave-12 subtree invention and opcode accounting."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.wave12_subtree_opcode_learner import (
    ALLOWED_PRIM_OPCODES,
    PRIMITIVE_KEYS,
    STATIC_INT_CONSTANTS,
    STATIC_TOK_CONSTANTS,
    WORK_KEYS,
    OpCounter,
    execute_wave12_program_ast,
    format_runner_summary,
    reconstruct_primitive_steps,
    reconstruct_total_work,
)

LEARNER_REL = "src/nexus/seed/wave12_subtree_opcode_learner.py"
RUNNER_REL = "scripts/run_wave12_subtree_opcode_assessment.py"
VERIFIER_REL = "scripts/verify_wave12_subtree_opcode_enumerator.py"
TESTS_REL = "tests/test_seed_wave12_subtree_opcode.py"
ASSESSMENT_NAME = "mechanism_wave12_fresh_assessment.py"
PARENT_SHA = "5777ea288851c775daeefca69be2d6250bbf8b74"
COMMIT1_SUBJECT = "Pre-assessment freeze for Wave 12 subtree invention and opcode accounting"
FORBIDDEN_STATIC_TOKS = ("#", "?", "!")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_wave12_learner_ast(learner_path: Path) -> Dict[str, Any]:
    source = learner_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(learner_path))
    violations: List[str] = []
    lambdas = [node for node in ast.walk(tree) if isinstance(node, ast.Lambda)]
    if lambdas:
        violations.append("lambda_nodes_found:{0}".format(len(lambdas)))
    found_solve = False
    solve_args: List[str] = []
    found_eval = False
    found_extract = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "eval_expr_ast":
            found_eval = True
            arg_names = [arg.arg for arg in node.args.args]
            if "op_counter" not in arg_names:
                violations.append("eval_expr_ast_missing_op_counter")
        if isinstance(node, ast.FunctionDef) and node.name == "extract_task_constants":
            found_extract = True
        if isinstance(node, ast.FunctionDef) and node.name == "solve_unfamiliar_task":
            found_solve = True
            solve_args = [arg.arg for arg in node.args.args]
            if solve_args != ["self", "env", "public_budget"]:
                violations.append("invalid_signature:{0}".format(solve_args))
        if isinstance(node, ast.Attribute) and node.attr in {
            "stage",
            "split",
            "task_id",
            "family",
            "_private_pairs",
        }:
            violations.append("forbidden_attribute:{0}".format(node.attr))
    if not found_solve:
        violations.append("missing_solve_unfamiliar_task")
    if not found_eval:
        violations.append("missing_eval_expr_ast")
    if not found_extract:
        violations.append("missing_extract_task_constants")
    if STATIC_TOK_CONSTANTS:
        violations.append("static_tok_constants_not_empty")
    if tuple(STATIC_INT_CONSTANTS) != (0, 1, 2):
        violations.append("static_int_constants_not_universal")
    if any(value >= 3 for value in STATIC_INT_CONSTANTS):
        violations.append("static_int_threshold_literal")
    assign_map = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "STATIC_TOK_CONSTANTS",
                    "STATIC_INT_CONSTANTS",
                    "BASE_TOKEN_CONSTANTS",
                    "BASE_INT_CONSTANTS",
                }:
                    assign_map[target.id] = node.value
    tok_assign = assign_map.get("STATIC_TOK_CONSTANTS")
    if isinstance(tok_assign, ast.Tuple):
        for elt in tok_assign.elts:
            if isinstance(elt, ast.Constant) and elt.value in FORBIDDEN_STATIC_TOKS:
                violations.append("static_task_token:{0}".format(elt.value))
    int_assign = assign_map.get("STATIC_INT_CONSTANTS") or assign_map.get("BASE_INT_CONSTANTS")
    if isinstance(int_assign, ast.Tuple):
        for elt in int_assign.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, int) and elt.value >= 3:
                violations.append("static_int_ge3:{0}".format(elt.value))
    return {
        "valid": len(violations) == 0,
        "lambda_count": len(lambdas),
        "prim_opcode_count": len(ALLOWED_PRIM_OPCODES),
        "solve_signature": solve_args,
        "violations": violations,
    }


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=str(ROOT), text=True).strip()


def find_commit1_sha() -> Optional[str]:
    try:
        log = _git("log", "--format=%H %s", "{0}..HEAD".format(PARENT_SHA))
    except subprocess.CalledProcessError:
        return None
    for line in log.splitlines():
        if COMMIT1_SUBJECT in line:
            return line.split(" ", 1)[0]
    return None


def verify_commit1_blindness(commit1: Optional[str]) -> Dict[str, Any]:
    reasons: List[str] = []
    def is_assessment_path(line: str) -> bool:
        name = line.strip().split()[-1] if line.strip() else ""
        return ASSESSMENT_NAME in name or "mechanism_wave12" in name and "assessment" in name

    if commit1 is None:
        status = _git("status", "--ignored", "--porcelain")
        if any(is_assessment_path(line) for line in status.splitlines()):
            reasons.append("working_tree_has_wave12_assessment_before_commit1")
        tree = _git("ls-tree", "-r", "--name-only", "HEAD")
        if any(is_assessment_path(line) for line in tree.splitlines()):
            reasons.append("head_tree_has_wave12_assessment")
        return {"checked": False, "valid": len(reasons) == 0, "reasons": reasons}
    names = _git("ls-tree", "-r", "--name-only", commit1)
    if any(is_assessment_path(line) for line in names.splitlines()):
        reasons.append("commit1_contains_assessment")
    try:
        diff = _git(
            "diff",
            commit1,
            "HEAD",
            "--",
            LEARNER_REL,
            RUNNER_REL,
            VERIFIER_REL,
        )
    except subprocess.CalledProcessError:
        diff = "diff_failed"
    if diff:
        reasons.append("frozen_files_changed_after_commit1")
    return {"checked": True, "commit1": commit1, "valid": len(reasons) == 0, "reasons": reasons}


def replay_row(row: Mapping[str, Any], label: str) -> List[str]:
    reasons: List[str] = []
    tid = "{0}:{1}:{2}:{3}".format(
        label, row.get("source_seed"), row.get("method"), row.get("task_id")
    )
    if int(row.get("total_work", -1)) != reconstruct_total_work(row):
        reasons.append("{0}:total_work_mismatch".format(tid))
    if int(row.get("total_primitive_op_steps", -1)) != reconstruct_primitive_steps(row):
        reasons.append("{0}:primitive_identity_mismatch".format(tid))
    program_ast = row.get("program_ast")
    if not isinstance(program_ast, Mapping):
        reasons.append("{0}:missing_program_ast".format(tid))
        return reasons
    status = row.get("status")
    if status == "unique":
        for obs in row.get("public_observations") or []:
            if "observed_output" not in obs:
                reasons.append("{0}:missing_observed_output_key".format(tid))
                continue
            got = execute_wave12_program_ast(program_ast, tuple(obs["input"]))
            if tuple(got) != tuple(obs["observed_output"]):
                reasons.append("{0}:public_replay_mismatch".format(tid))
        priv_ok = True
        verify_steps = 0
        for pev in row.get("private_evaluations") or []:
            counter = OpCounter()
            got = execute_wave12_program_ast(program_ast, tuple(pev["input"]), counter)
            verify_steps += counter.steps
            if tuple(got) != tuple(pev.get("predicted_output") or ()):
                reasons.append("{0}:private_predicted_mismatch".format(tid))
            if tuple(got) != tuple(pev.get("ground_truth_output") or ()):
                priv_ok = False
        if row.get("private_evaluations") and "private_correct" in row:
            if priv_ok != bool(row.get("private_correct")):
                reasons.append("{0}:private_correct_flag_mismatch".format(tid))
        recorded_final = row.get("final_verify_primitive_op_steps")
        if recorded_final is not None and int(recorded_final) != verify_steps:
            reasons.append("{0}:final_verify_primitive_mismatch".format(tid))
    return reasons


def verify_payload(payload: Mapping[str, Any], label: str = "wave12") -> Dict[str, Any]:
    reasons: List[str] = []
    if payload.get("kind") and payload.get("assessment") is not None:
        recomputed = digest(
            {key: payload[key] for key in ("kind", "assessment", "totals", "gates")}
        )
        if payload.get("hash") and recomputed != payload.get("hash"):
            reasons.append("{0}:hash_mismatch".format(label))
    usage = payload.get("usage") or {}
    if int(usage.get("model_calls", 0)) != 0:
        reasons.append("{0}:nonzero_model_calls".format(label))
    if float(usage.get("frozen_debit_s", 0.0)) != 0.0:
        reasons.append("{0}:nonzero_frozen_debit_s".format(label))
    summary = format_runner_summary(payload)
    if "suite_totals" not in summary:
        reasons.append("{0}:runner_summary_missing_suite_totals".format(label))
    if summary.get("suite_totals") is None and (payload.get("totals") or {}).get("suite") is not None:
        reasons.append("{0}:suite_totals_key_mismatch".format(label))
    rows = list(payload.get("assessment") or [])
    for row in rows:
        reasons.extend(replay_row(row, label))
    return {
        "valid": len(reasons) == 0,
        "replayed_rows": len(rows),
        "reasons": reasons,
        "work_keys": list(WORK_KEYS),
        "primitive_keys": list(PRIMITIVE_KEYS),
    }


def verify_wave12_artifact(root: Path = ROOT) -> Dict[str, Any]:
    learner_path = root / LEARNER_REL
    artifact_path = root / "artifacts" / "seed_wave12_subtree_opcode_enumerator.json"
    reasons: List[str] = []
    ast_check = inspect_wave12_learner_ast(learner_path)
    if not ast_check["valid"]:
        reasons.extend(ast_check["violations"])
    blindness = verify_commit1_blindness(find_commit1_sha())
    if not blindness["valid"]:
        reasons.extend(blindness["reasons"])
    replayed = 0
    payload_report: Dict[str, Any] = {}
    if artifact_path.exists():
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        payload_report = verify_payload(payload, "wave12")
        replayed = int(payload_report.get("replayed_rows") or 0)
        reasons.extend(payload_report.get("reasons") or [])
        if not payload.get("gates", {}).get("passed", False):
            reasons.append("gates_not_passed")
    return {
        "valid": len(reasons) == 0,
        "replayed_rows": replayed,
        "ast_check": ast_check,
        "commit1_blindness": blindness,
        "file_sha256": {
            "learner": _sha256_file(learner_path),
            "runner": _sha256_file(root / RUNNER_REL),
            "verifier": _sha256_file(root / VERIFIER_REL),
            "tests": _sha256_file(root / TESTS_REL),
        },
        "payload": payload_report,
        "reasons": reasons,
    }


def main() -> int:
    report = verify_wave12_artifact(ROOT)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
