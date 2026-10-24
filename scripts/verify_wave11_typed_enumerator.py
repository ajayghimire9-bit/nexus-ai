#!/usr/bin/env python3
"""Independent verifier for Wave-11 typed program enumerator & Wave-10 forensic recovery."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.mechanism_wave11b_fresh_assessment import COST_KEYS
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
EXPECTED_WAVE11A_SUITE_SHA256 = (
    "ec99f31b07f01f4aa0dedf92584e1354a6ddf34b59984b8641b9462d015411a7"
)
EXPECTED_WAVE11B_SUITE_SHA256 = (
    "adc0d49581b2d81c1b464c6f4185e77f5e2ded6460d0ef9a24cdca5799d0738e"
)
EXPECTED_WAVE10_PRE_AMEND_HASH = (
    "6a8493a609fd7480f45deaf9061334f81442a5de5d49aa59ac6f5fa830761562"
)
EXPECTED_WAVE11A_CLOSED_HASH = (
    "3bd32ab59b10797fb76b13060a61a402e4fe44c547835f5db954626a15097f07"
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
    "w10a_",
    "w11f_",
    "w11b_",
}


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


def _replay_and_verify_payload(
    payload: Mapping[str, Any], label: str
) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    recomputed = digest(
        {key: payload[key] for key in ("kind", "assessment", "totals", "gates")}
    )
    if recomputed != payload.get("hash"):
        reasons.append(f"{label}:hash_mismatch")

    usage = payload.get("usage") or {}
    if int(usage.get("model_calls", -1)) != 0:
        reasons.append(f"{label}:nonzero_model_calls")
    if float(usage.get("frozen_debit_s", -1.0)) != 0.0:
        reasons.append(f"{label}:nonzero_frozen_debit_s")
    if not payload.get("gates", {}).get("passed", False):
        reasons.append(f"{label}:gates_not_passed")

    rows = list(payload.get("assessment") or [])
    if len(rows) != 192:
        reasons.append(f"{label}:unexpected_row_count:{len(rows)}")

    for row in rows:
        tid = f"{label}:{row.get('source_seed')}:{row.get('method')}:{row.get('task_id')}"
        expected_total_work = sum(int(row.get(k, 0)) for k in COST_KEYS)
        if int(row.get("total_work", -1)) != expected_total_work:
            reasons.append(f"{tid}:total_work_mismatch")

        expected_codegen = (
            int(row.get("gate_evals", 0))
            + int(row.get("archive_lookup_evals", 0))
            + int(row.get("synthesis_evals", 0))
        )
        if int(row.get("codegen_plus_synthesis", -1)) != expected_codegen:
            reasons.append(f"{tid}:codegen_plus_synthesis_mismatch")

        program_ast = row.get("program_ast")
        if not isinstance(program_ast, Mapping):
            reasons.append(f"{tid}:missing_program_ast")
            continue

        status = row.get("status")
        if status == "unique":
            for obs in row.get("public_observations", []):
                inp = tuple(obs["input"])
                expected_out = tuple(obs["output"])
                got = execute_wave11_program_ast(program_ast, inp)
                if tuple(got) != expected_out:
                    reasons.append(f"{tid}:public_replay_mismatch")

            priv_ok = True
            for pev in row.get("private_evaluations", []):
                inp = tuple(pev["input"])
                expected_pred = tuple(pev["predicted_output"])
                gt_out = tuple(pev["ground_truth_output"])
                got = execute_wave11_program_ast(program_ast, inp)
                if tuple(got) != expected_pred:
                    reasons.append(f"{tid}:private_predicted_mismatch")
                if tuple(got) != gt_out:
                    priv_ok = False
            if priv_ok != bool(row.get("private_correct")):
                reasons.append(f"{tid}:private_correct_flag_mismatch")

    return len(rows), reasons


def verify_wave11_artifact(root: Path = ROOT) -> Dict[str, Any]:
    artifact_b_path = root / "artifacts" / "seed_wave11b_typed_program_enumerator.json"
    artifact_a_path = root / "artifacts" / "seed_wave11_typed_program_enumerator.json"
    wave8_path = root / "src" / "nexus" / "seed" / "deconfounded_equal_capability.py"
    wave9_path = (
        root / "src" / "nexus" / "seed" / "wave9_learned_abstraction_meta_control.py"
    )
    wave10_path = (
        root / "src" / "nexus" / "seed" / "wave10_atomic_self_evolving_learner.py"
    )
    wave11_path = root / "src" / "nexus" / "seed" / "wave11_typed_program_enumerator.py"
    suite_a_path = (
        root / "src" / "nexus" / "seed" / "mechanism_wave11_fresh_assessment.py"
    )
    suite_b_path = (
        root / "src" / "nexus" / "seed" / "mechanism_wave11b_fresh_assessment.py"
    )

    if not artifact_b_path.exists():
        return {"valid": False, "reason": "missing_wave11b_artifact"}

    reasons: List[str] = []

    w8_sha = _sha256_file(wave8_path)
    w9_sha = _sha256_file(wave9_path)
    w10_sha = _sha256_file(wave10_path)
    w11_sha = _sha256_file(wave11_path)
    suite_a_sha = _sha256_file(suite_a_path)
    suite_b_sha = _sha256_file(suite_b_path)

    if w8_sha != EXPECTED_WAVE8_LEARNER_SHA256:
        reasons.append(f"wave8_learner_modified:{w8_sha}")
    if w9_sha != EXPECTED_WAVE9_LEARNER_SHA256:
        reasons.append(f"wave9_learner_modified:{w9_sha}")
    if w10_sha != EXPECTED_WAVE10_LEARNER_SHA256:
        reasons.append(f"wave10_learner_modified:{w10_sha}")
    if w11_sha != EXPECTED_WAVE11_LEARNER_SHA256:
        reasons.append(f"wave11_learner_modified:{w11_sha}")
    if suite_a_sha != EXPECTED_WAVE11A_SUITE_SHA256:
        reasons.append(f"wave11a_suite_modified:{suite_a_sha}")
    if suite_b_sha != EXPECTED_WAVE11B_SUITE_SHA256:
        reasons.append(f"wave11b_suite_modified:{suite_b_sha}")

    ast_check = inspect_wave11_learner_ast(wave11_path)
    if not ast_check["valid"]:
        reasons.extend(ast_check["violations"])

    w10_forensic_check = verify_wave10_pre_amend_artifact(root)
    if not w10_forensic_check["valid"]:
        reasons.extend(w10_forensic_check["reasons"])

    if not artifact_a_path.exists():
        reasons.append("missing_closed_wave11a_artifact")
    else:
        payload_a = json.loads(artifact_a_path.read_text(encoding="utf-8"))
        if payload_a.get("hash") != EXPECTED_WAVE11A_CLOSED_HASH:
            reasons.append(f"unexpected_wave11a_hash:{payload_a.get('hash')}")
        _, reasons_a = _replay_and_verify_payload(payload_a, "wave11a_closed")
        reasons.extend(reasons_a)

    payload_b = json.loads(artifact_b_path.read_text(encoding="utf-8"))
    replayed_rows, reasons_b = _replay_and_verify_payload(payload_b, "wave11b")
    reasons.extend(reasons_b)

    return {
        "valid": len(reasons) == 0,
        "replayed_rows": replayed_rows,
        "frozen_file_sha256": {
            "wave8_learner": w8_sha,
            "wave9_learner": w9_sha,
            "wave10_learner": w10_sha,
            "wave11_learner": w11_sha,
            "wave11a_suite": suite_a_sha,
            "wave11b_suite": suite_b_sha,
        },
        "ast_check": ast_check,
        "wave10_forensic_check": w10_forensic_check,
        "wave11a_closed_hash": EXPECTED_WAVE11A_CLOSED_HASH,
        "gates": payload_b.get("gates", {}),
        "suite_totals": (payload_b.get("totals") or {}).get("suite", {}),
        "hash": payload_b.get("hash"),
        "reasons": reasons,
    }


def main() -> int:
    report = verify_wave11_artifact(ROOT)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
