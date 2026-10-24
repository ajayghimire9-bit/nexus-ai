#!/usr/bin/env python3
"""Independent verifier for Wave-11 typed program enumerator & Wave-10 forensic recovery."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.wave11_typed_program_enumerator import (
    ALLOWED_PRIM_OPCODES,
    execute_wave11_program_ast,
)

EXPECTED_WAVE8_LEARNER_SHA256 = (
    "ef0bceb9e10d9f14febdb0df75a6516a9413878f3aa2d63177dda212de37fe1e"
)
EXPECTED_WAVE9_LEARNER_SHA256 = (
    "3be126c6470fc45d29a35863aea9d68ca30497756f9ef4ebbdd02c1662677143"
)
EXPECTED_WAVE10_LEARNER_SHA256 = (
    "3ee0a80e757f00b00bc7b73edbb2c665ac83109a59543b5a6b6b5646e62389d0"
)
EXPECTED_WAVE11_LEARNER_SHA256 = (
    "70076ef08dc310399878372710387da9833ba295d0374a2a031249e2987ae86a"
)
EXPECTED_WAVE11_SUITE_SHA256 = (
    "ec99f31b07f01f4aa0dedf92584e1354a6ddf34b59984b8641b9462d015411a7"
)
EXPECTED_WAVE10_PRE_AMEND_HASH = (
    "6a8493a609fd7480f45deaf9061334f81442a5de5d49aa59ac6f5fa830761562"
)

FORBIDDEN_SPLIT_LITERALS = {
    "l1",
    "l2",
    "l3",
    "oog",
    "warmup",
    "compositional_2",
    "compositional_3",
    "deep_macro_reuse",
    "holdout",
    "w8d_",
    "w9f_",
    "w10f_",
    "w11f_",
}


def _canonical_hash(payload: Dict[str, Any]) -> str:
    copy_payload = dict(payload)
    copy_payload.pop("hash", None)
    raw = json.dumps(copy_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_wave11_learner_ast(learner_path: Path) -> Dict[str, Any]:
    source = learner_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(learner_path))
    violations: List[str] = []

    lambda_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.Lambda)]
    if lambda_nodes:
        violations.append(f"lambda_nodes_found:{len(lambda_nodes)}")

    found_solve = False
    solve_args: List[str] = []
    found_eval_expr_ast = False

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "eval_expr_ast":
            found_eval_expr_ast = True
        if isinstance(node, ast.FunctionDef) and node.name == "solve_unfamiliar_task":
            found_solve = True
            solve_args = [arg.arg for arg in node.args.args]
            if solve_args != ["self", "env", "public_budget"]:
                violations.append(f"invalid_signature:{solve_args}")
        if isinstance(node, ast.Attribute) and node.attr in {
            "stage",
            "split",
            "task_id",
            "family",
            "_private_pairs",
        }:
            violations.append(f"forbidden_attribute:{node.attr}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value.lower()
            for token in FORBIDDEN_SPLIT_LITERALS:
                if val == token or (token.endswith("_") and val.startswith(token)):
                    violations.append(f"forbidden_string_literal:{node.value}")

    if not found_solve:
        violations.append("missing_solve_unfamiliar_task")
    if not found_eval_expr_ast:
        violations.append("missing_eval_expr_ast")
    if len(ALLOWED_PRIM_OPCODES) != 14:
        violations.append(f"unexpected_prim_opcode_count:{len(ALLOWED_PRIM_OPCODES)}")

    return {
        "valid": len(violations) == 0,
        "lambda_count": len(lambda_nodes),
        "prim_opcode_count": len(ALLOWED_PRIM_OPCODES),
        "solve_signature": solve_args,
        "violations": violations,
    }


def verify_wave10_pre_amend_artifact(root: Path = ROOT) -> Dict[str, Any]:
    pre_amend_path = root / "artifacts" / "seed_wave10_pre_amend_failed_run.json"
    if not pre_amend_path.exists():
        return {"valid": False, "reason": "missing_wave10_pre_amend_failed_run_artifact"}
    payload = json.loads(pre_amend_path.read_text(encoding="utf-8"))
    recomputed = digest(
        {key: payload[key] for key in ("kind", "assessment", "totals", "gates")}
    )
    reasons: List[str] = []
    if payload.get("hash") != recomputed:
        reasons.append("wave10_pre_amend_hash_mismatch")
    if recomputed != EXPECTED_WAVE10_PRE_AMEND_HASH:
        reasons.append(f"unexpected_wave10_pre_amend_hash:{recomputed}")
    gates = payload.get("gates", {})
    if gates.get("passed") is not False:
        reasons.append("expected_wave10_pre_amend_gates_passed_false")
    if gates.get("gate2_fixes_all_three_d0a8bb1_overheads") is not False:
        reasons.append("expected_wave10_pre_amend_gate2_passed_false")
    return {
        "valid": len(reasons) == 0,
        "hash": recomputed,
        "gates": gates,
        "reasons": reasons,
    }


def verify_wave11_artifact(root: Path = ROOT) -> Dict[str, Any]:
    artifact_path = root / "artifacts" / "seed_wave11_typed_enumerator.json"
    wave8_path = root / "src" / "nexus" / "seed" / "deconfounded_equal_capability.py"
    wave9_path = root / "src" / "nexus" / "seed" / "wave9_learned_abstraction_meta_control.py"
    wave10_path = root / "src" / "nexus" / "seed" / "wave10_atomic_self_evolving_learner.py"
    wave11_path = root / "src" / "nexus" / "seed" / "wave11_typed_program_enumerator.py"
    suite_path = root / "src" / "nexus" / "seed" / "mechanism_wave11_fresh_assessment.py"

    if not artifact_path.exists():
        return {"valid": False, "reason": "missing_wave11_artifact"}

    reasons: List[str] = []

    w8_sha = _sha256_file(wave8_path)
    w9_sha = _sha256_file(wave9_path)
    w10_sha = _sha256_file(wave10_path)
    w11_sha = _sha256_file(wave11_path)
    suite_sha = _sha256_file(suite_path)

    if w8_sha != EXPECTED_WAVE8_LEARNER_SHA256:
        reasons.append(f"wave8_learner_modified:{w8_sha}")
    if w9_sha != EXPECTED_WAVE9_LEARNER_SHA256:
        reasons.append(f"wave9_learner_modified:{w9_sha}")
    if w10_sha != EXPECTED_WAVE10_LEARNER_SHA256:
        reasons.append(f"wave10_learner_modified:{w10_sha}")
    if w11_sha != EXPECTED_WAVE11_LEARNER_SHA256:
        reasons.append(f"wave11_learner_modified:{w11_sha}")
    if suite_sha != EXPECTED_WAVE11_SUITE_SHA256:
        reasons.append(f"wave11_suite_modified:{suite_sha}")

    ast_check = inspect_wave11_learner_ast(wave11_path)
    if not ast_check["valid"]:
        reasons.extend(ast_check["violations"])

    w10_forensic_check = verify_wave10_pre_amend_artifact(root)
    if not w10_forensic_check["valid"]:
        reasons.extend(w10_forensic_check["reasons"])

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if _canonical_hash(payload) != payload.get("hash"):
        reasons.append("hash_mismatch")

    if int(payload.get("model_calls", -1)) != 0:
        reasons.append("nonzero_model_calls")
    if float(payload.get("frozen_clock_Send", -1.0)) != 0.0:
        reasons.append("nonzero_frozen_clock")
    if not payload.get("gates", {}).get("passed", False):
        reasons.append("gates_not_passed")

    replayed_rows = 0
    for seed_str, seed_data in payload.get("seeds", {}).items():
        for method, mdata in seed_data.get("methods", {}).items():
            sum_cand = 0
            sum_op_steps = 0
            sum_ast_nodes = 0
            sum_pub = 0
            sum_comp = 0
            for row in mdata.get("rows", []):
                replayed_rows += 1
                sum_cand += int(row["candidate_programs_evaluated"])
                sum_op_steps += int(row["atomic_op_executions"])
                sum_ast_nodes += int(row["ast_nodes_constructed"])
                sum_pub += int(row["public_test_executions"])
                sum_comp += int(row["compression_work"])

                if int(row["total_work"]) != (
                    int(row["candidate_programs_evaluated"])
                    + int(row["atomic_op_executions"])
                    + int(row["ast_nodes_constructed"])
                    + int(row["public_test_executions"])
                    + int(row["compression_work"])
                ):
                    reasons.append(f"row_total_work_mismatch:{seed_str}:{method}:{row['task_id']}")

                program_ast = row.get("program_ast")
                if not program_ast:
                    reasons.append(f"missing_program_ast:{seed_str}:{method}:{row['task_id']}")
                    continue

                for inp, expected in row.get("public_pairs", []):
                    got = execute_wave11_program_ast(program_ast, tuple(inp))
                    if list(got) != list(expected):
                        reasons.append(
                            f"public_replay_mismatch:{seed_str}:{method}:{row['task_id']}"
                        )

                priv_ok = True
                for inp, expected in row.get("private_pairs", []):
                    got = execute_wave11_program_ast(program_ast, tuple(inp))
                    if list(got) != list(expected):
                        priv_ok = False
                        break
                if priv_ok != bool(row.get("private_correct")):
                    reasons.append(
                        f"private_replay_mismatch:{seed_str}:{method}:{row['task_id']}"
                    )

            agg = mdata.get("aggregate", {})
            if (
                int(agg.get("candidate_programs_evaluated", -1)) != sum_cand
                or int(agg.get("atomic_op_executions", -1)) != sum_op_steps
                or int(agg.get("ast_nodes_constructed", -1)) != sum_ast_nodes
                or int(agg.get("public_test_executions", -1)) != sum_pub
                or int(agg.get("compression_work", -1)) != sum_comp
            ):
                reasons.append(f"aggregate_ledger_mismatch:{seed_str}:{method}")

    if replayed_rows != 192:
        reasons.append(f"unexpected_row_count:{replayed_rows}")

    return {
        "valid": len(reasons) == 0,
        "replayed_rows": replayed_rows,
        "frozen_file_sha256": {
            "wave8_learner": w8_sha,
            "wave9_learner": w9_sha,
            "wave10_learner": w10_sha,
            "wave11_learner": w11_sha,
            "wave11_suite": suite_sha,
        },
        "ast_check": ast_check,
        "wave10_forensic_check": w10_forensic_check,
        "gates": payload.get("gates", {}),
        "suite_totals": payload.get("suite_totals", {}),
        "hash": payload.get("hash"),
        "reasons": reasons,
    }


def main() -> int:
    report = verify_wave11_artifact(ROOT)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
