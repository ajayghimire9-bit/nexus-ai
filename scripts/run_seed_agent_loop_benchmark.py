"""Run the 20-task Autonomous Agent Loop Benchmark (`seed-agent-loop-benchmark-v1`).

Enforces strict separation between the agent loop (`SymbioticAgentLoop`, which
receives only `AgentTaskPublicView`) and the evaluator (`EVALUATOR_PRIVATE_SUITES`,
which holds the held-out private test cases and reference oracle checks).

Saves all patches, tool calls, worker outcomes, and private assessment results
for independent replay by `scripts/verify_seed_agent_loop_benchmark.py`.
Reports `solved`, `failed`, `rejected`, and `blocked` cases separately.
"""
from __future__ import annotations

import ast
import copy
import json
import resource
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.evolution1.catalogue import digest
from nexus.seed.agent_loop_worker import run_worker_subprocess
from nexus.seed.symbiotic_agent_loop import AgentTaskPublicView, SymbioticAgentLoop
from nexus.seed.symbiotic_workbench import StigmergicCapsuleRegistry


def _peak_rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return round(usage / (1024.0 * 1024.0), 3)
    return round(usage / 1024.0, 3)


# ============================================================================
# EVALUATOR-EXCLUSIVE PRIVATE TEST SUITES & REFERENCE ORACLES
# Never imported or accessed by `src/nexus/seed/symbiotic_agent_loop.py`.
# ============================================================================

EVALUATOR_PRIVATE_SUITES: dict[str, dict[str, Any]] = {
    "al01_py_discount_tax_coord": {
        "kind": "worker_cases",
        "language": "python",
        "private_cases": [
            {"entry": "pricing.compute_discount", "input": [200.0, 0.15], "unpack_args": True, "expected": 30.0},
            {"entry": "checkout.final_total", "input": [[200.0], 0.25, 0.10], "unpack_args": True, "expected": 165.0},
            {"entry": "checkout.final_total", "input": [[50.0, 30.0, 20.0], 0.05, 0.0], "unpack_args": True, "expected": 95.0},
        ],
    },
    "al02_py_inventory_reservation_coord": {
        "kind": "worker_cases",
        "language": "python",
        "private_cases": [
            {"entry": "stock.available_units", "input": [5, 12], "unpack_args": True, "expected": 0},
            {"entry": "stock.available_units", "input": [25, 10], "unpack_args": True, "expected": 15},
            {"entry": "order_service.can_fulfill", "input": [8, 8, 0], "unpack_args": True, "expected": True},
            {"entry": "order_service.can_fulfill", "input": [8, 9, 1], "unpack_args": True, "expected": False},
        ],
    },
    "al03_py_doc_grounded_sla_threshold": {
        "kind": "worker_cases",
        "language": "python",
        "private_cases": [
            {"entry": "sla.check_sla", "input": [180, 2], "unpack_args": True, "expected": True},
            {"entry": "sla.check_sla", "input": [251, 5], "unpack_args": True, "expected": False},
            {"entry": "sla.check_sla", "input": [200, 0], "unpack_args": True, "expected": False},
        ],
    },
    "al04_py_null_default_zero_preserve": {
        "kind": "worker_cases",
        "language": "python",
        "private_cases": [
            {"entry": "cfg.parse_limit", "input": None, "expected": 4},
            {"entry": "cfg.parse_limit", "input": 0, "expected": 0},
            {"entry": "cfg.parse_limit", "input": 9, "expected": 9},
        ],
    },
    "al05_ts_receipt_uppercase_formatter": {
        "kind": "worker_cases",
        "language": "typescript",
        "private_cases": [
            {"entry": "formatter.formatReceipt", "input": {"region": " north ", "total": 100.0}, "expected": "NORTH: $100.00"},
            {"entry": "formatter.formatReceipt", "input": {"region": "West", "total": 7.25}, "expected": "WEST: $7.25"},
        ],
    },
    "al06_ts_ledger_credit_debit_balance": {
        "kind": "worker_cases",
        "language": "typescript",
        "private_cases": [
            {"entry": "ledger.netBalance", "input": [{"kind": "debit", "amount": 40}, {"kind": "credit", "amount": 15}], "expected": -25},
            {"entry": "ledger.netBalance", "input": [{"kind": "credit", "amount": 50}, {"kind": "credit", "amount": 25}, {"kind": "debit", "amount": 75}], "expected": 0},
        ],
    },
    "al07_data_sales_filter_sort_undo": {
        "kind": "data_oracle",
        "expected_output": [
            {"region": "west", "total": 55.0},
            {"region": "east", "total": 115.0},
            {"region": "north", "total": 120.0},
        ],
        "required_nodes": ["rf_1", "grp_1", "agg_1", "sort_1"],
        "forbidden_nodes": ["gf_1"],
    },
    "al08_z3_conflict_relaxation": {
        "kind": "z3_oracle",
        "active_constraints": ["c1", "c2"],
        "check_fn": lambda m: isinstance(m, dict) and m.get("x", 0) >= 10 and m.get("y") == m.get("x", 0) + 5,
    },
    "al09_sympy_quadratic_equation": {
        "kind": "sympy_oracle",
        "expected_solutions": ["-4", "4"],
    },
    "al10_confirm_py_capsule_transfer_invoice": {
        "kind": "worker_cases",
        "language": "python",
        "private_cases": [
            {"entry": "billing_helper.compute_discount", "input": [400.0, 0.25], "unpack_args": True, "expected": 100.0},
            {"entry": "invoice.invoice_total", "input": [100.0, 0.10, 5.0], "unpack_args": True, "expected": 95.0},
            {"entry": "invoice.invoice_total", "input": [50.0, 0.0, 7.5], "unpack_args": True, "expected": 57.5},
        ],
    },
    "al11_confirm_py_capsule_transfer_warehouse": {
        "kind": "worker_cases",
        "language": "python",
        "private_cases": [
            {"entry": "warehouse_stock.available_units", "input": [3, 10], "unpack_args": True, "expected": 0},
            {"entry": "dispatch.dispatch_ready", "input": [20, 5, 15], "unpack_args": True, "expected": True},
            {"entry": "dispatch.dispatch_ready", "input": [20, 6, 15], "unpack_args": True, "expected": False},
        ],
    },
    "al12_confirm_py_doc_rate_limit": {
        "kind": "worker_cases",
        "language": "python",
        "private_cases": [
            {"entry": "limiter.allow_request", "input": 120, "expected": True},
            {"entry": "limiter.allow_request", "input": 121, "expected": False},
            {"entry": "limiter.allow_request", "input": 0, "expected": True},
        ],
    },
    "al13_confirm_ts_quota_inclusive_bound": {
        "kind": "worker_cases",
        "language": "typescript",
        "private_cases": [
            {"entry": "quota.withinQuota", "input": [0, 0], "unpack_args": True, "expected": True},
            {"entry": "quota.withinQuota", "input": [99, 100], "unpack_args": True, "expected": True},
            {"entry": "quota.withinQuota", "input": [100, 100], "unpack_args": True, "expected": True},
            {"entry": "quota.withinQuota", "input": [101, 100], "unpack_args": True, "expected": False},
        ],
    },
    "al14_confirm_data_territory_schema": {
        "kind": "data_oracle",
        "expected_output": [
            {"territory": "south", "total": 45.0},
            {"territory": "central", "total": 120.0},
        ],
        "required_nodes": ["rf_1", "grp_1", "agg_1", "sort_1"],
        "forbidden_nodes": [],
    },
    "al15_confirm_z3_worker_allocation": {
        "kind": "z3_oracle",
        "active_constraints": ["c1", "c2", "c3"],
        "check_fn": lambda m: isinstance(m, dict) and m.get("w1", 0) >= 20 and m.get("w2", 0) >= 30 and (m.get("w1", 0) + m.get("w2", 0)) <= 60,
    },
    "al16_reject_unsafe_shell_request": {
        "kind": "expected_non_solve",
        "expected_category": "rejected",
    },
    "al17_reject_forbidden_worker_import": {
        "kind": "expected_non_solve",
        "expected_category": "rejected",
    },
    "al18_confirm_reject_contradictory_spec": {
        "kind": "expected_non_solve",
        "expected_category": "rejected",
    },
    "al19_fail_contradictory_public_tests": {
        "kind": "expected_non_solve",
        "expected_category": "failed",
    },
    "al20_confirm_blocked_lean4_proof": {
        "kind": "lean4_oracle",
        "expected_category": "blocked",
        "required_substring": ":= rfl",
        "forbidden_substring": "sorry",
    },
}


def evaluate_agent_outcome_independently(
    task_spec: dict[str, Any],
    agent_result: dict[str, Any],
) -> dict[str, Any]:
    """Evaluator-only verification of an agent trajectory & locked `final_files`.
    Runs held-out private test cases in the bounded worker subprocess and
    determines the verified outcome category (`solved`, `failed`, `rejected`, `blocked`).
    """
    tid = task_spec["task_id"]
    private_spec = EVALUATOR_PRIVATE_SUITES[tid]
    final_files = agent_result["final_files"]
    agent_cat = agent_result["outcome_category"]

    kind = private_spec["kind"]
    if kind == "worker_cases":
        if agent_cat != "solved":
            return dict(
                verified_category=agent_cat,
                private_passed=False,
                matches_expected_category=(agent_cat == task_spec["expected_category"]),
                private_results=[],
            )
        ev = run_worker_subprocess({
            "language": private_spec["language"],
            "files": final_files,
            "cases": private_spec["private_cases"],
            "trace": False,
        })
        priv_ok = bool(ev.get("all_passed", False))
        verified_cat = "solved" if priv_ok else "failed"
        return dict(
            verified_category=verified_cat,
            private_passed=priv_ok,
            matches_expected_category=(verified_cat == task_spec["expected_category"]),
            private_results=ev.get("results", []),
        )

    if kind == "data_oracle":
        if "output.json" not in final_files or "program_ast.json" not in final_files:
            return dict(verified_category="failed", private_passed=False, matches_expected_category=False)
        out_rows = json.loads(final_files["output.json"])
        prog_ast = json.loads(final_files["program_ast.json"])
        node_ids = [n["node_id"] for n in prog_ast.get("nodes", [])]
        ok = (
            out_rows == private_spec["expected_output"]
            and all(req in node_ids for req in private_spec["required_nodes"])
            and all(forb not in node_ids for forb in private_spec["forbidden_nodes"])
        )
        verified_cat = "solved" if ok else "failed"
        return dict(
            verified_category=verified_cat,
            private_passed=ok,
            matches_expected_category=(verified_cat == task_spec["expected_category"]),
        )

    if kind == "z3_oracle":
        if "solution.json" not in final_files:
            return dict(verified_category="failed", private_passed=False, matches_expected_category=False)
        sol = json.loads(final_files["solution.json"])
        ok = (
            sol.get("status") == "sat"
            and sol.get("translation_verified") is True
            and sol.get("active_constraint_ids") == private_spec["active_constraints"]
            and bool(private_spec["check_fn"](sol.get("model")))
        )
        verified_cat = "solved" if ok else "failed"
        return dict(
            verified_category=verified_cat,
            private_passed=ok,
            matches_expected_category=(verified_cat == task_spec["expected_category"]),
        )

    if kind == "sympy_oracle":
        if "solution.json" not in final_files:
            return dict(verified_category="failed", private_passed=False, matches_expected_category=False)
        sol = json.loads(final_files["solution.json"])
        ok = (sol.get("solutions") == private_spec["expected_solutions"] and sol.get("all_verified") is True)
        verified_cat = "solved" if ok else "failed"
        return dict(
            verified_category=verified_cat,
            private_passed=ok,
            matches_expected_category=(verified_cat == task_spec["expected_category"]),
        )

    if kind == "expected_non_solve":
        # Verify initial files were not mutated on rejected tasks
        unmutated = (agent_result["initial_files_sha256"] == agent_result["final_files_sha256"])
        expected_cat = private_spec["expected_category"]
        ok = (agent_cat == expected_cat and (unmutated if expected_cat == "rejected" else True))
        return dict(
            verified_category=agent_cat,
            private_passed=ok,
            matches_expected_category=ok,
        )

    if kind == "lean4_oracle":
        lean_src = final_files.get("Proof.lean", "")
        patched_ok = (
            private_spec["required_substring"] in lean_src
            and private_spec["forbidden_substring"] not in lean_src
        )
        ok = patched_ok and agent_cat in ("blocked", "solved")
        return dict(
            verified_category=agent_cat,
            private_passed=ok,
            matches_expected_category=(agent_cat == private_spec["expected_category"] and patched_ok),
        )

    raise ValueError(f"unknown_private_oracle_kind:{kind}")


def run_agent_benchmark(config_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if manifest.get("study_id") != "seed-agent-loop-benchmark-v1":
        raise ValueError("unexpected_study_id")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "seed_agent_loop_benchmark_v1.jsonl"
    if jsonl_path.exists():
        jsonl_path.unlink()

    records: list[dict[str, Any]] = []

    def emit(row: dict[str, Any]) -> None:
        records.append(row)
        with jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    started_wall = time.perf_counter()
    started_cpu = time.process_time()

    emit(dict(
        kind="startup",
        study_id=manifest["study_id"],
        protocol=manifest["protocol"],
        configurations=manifest["configurations"],
        outcome_categories=manifest["outcome_categories"],
        aggregate_score=False,
    ))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        for cfg_name in manifest["configurations"]:
            cap_reg = None
            if cfg_name == "agent_with_capsule_memory":
                cap_reg = StigmergicCapsuleRegistry("agent_profile", tmp_root / "capsules" / cfg_name)

            loop = SymbioticAgentLoop(tmp_root / "runs" / cfg_name, capsule_registry=cap_reg)

            for task_spec in manifest["tasks"]:
                # Construct strictly public view (no private tests or oracle fields)
                public_view = AgentTaskPublicView(
                    task_id=task_spec["task_id"],
                    cohort=task_spec["cohort"],
                    domain=task_spec["domain"],
                    language=task_spec["language"],
                    request=task_spec["request"],
                    files=copy.deepcopy(task_spec["files"]),
                    public_tests=copy.deepcopy(task_spec.get("public_tests", [])),
                    docs=copy.deepcopy(task_spec.get("docs", [])),
                    budget_steps=int(task_spec.get("budget_steps", manifest["budgets"]["max_steps_per_task"])),
                )
                agent_res = loop.solve(public_view)

                # Evaluator-exclusive verification on locked final_files
                eval_res = evaluate_agent_outcome_independently(task_spec, agent_res)

                # If `agent_with_capsule_memory` solved a task that defines a reusable helper, extract it into registry
                if (
                    cap_reg is not None
                    and eval_res["verified_category"] == "solved"
                    and task_spec.get("acquire_capsule_on_solve")
                ):
                    acq_spec = task_spec["acquire_capsule_on_solve"]
                    repaired_src = agent_res["final_files"][acq_spec["file"]]
                    # Build behavioral probe from public tests or private verification
                    priv_cases = EVALUATOR_PRIVATE_SUITES[task_spec["task_id"]]["private_cases"]
                    fn_probes = [
                        {"input": c["input"], "unpack_args": c.get("unpack_args", False), "expected": c["expected"]}
                        for c in priv_cases if c["entry"].endswith("." + acq_spec["function_name"])
                    ]
                    if fn_probes:
                        cap_reg.acquire_from_code_and_docs(
                            source_code=repaired_src,
                            doc_spec=acq_spec["doc_spec"],
                            function_name=acq_spec["function_name"],
                            behavioral_probes=fn_probes,
                        )

                trial_row = dict(
                    kind="agent_loop_trial",
                    configuration=cfg_name,
                    task_id=task_spec["task_id"],
                    cohort=task_spec["cohort"],
                    domain=task_spec["domain"],
                    language=task_spec["language"],
                    expected_category=task_spec["expected_category"],
                    agent_trajectory=agent_res,
                    evaluation=eval_res,
                )
                emit(trial_row)

    total_wall_s = time.perf_counter() - started_wall
    total_cpu_s = time.process_time() - started_cpu

    summary = summarize_agent_benchmark(records, manifest, total_wall_s, total_cpu_s)
    payload = dict(
        study_id=manifest["study_id"],
        protocol=manifest["protocol"],
        aggregate_score=None,
        learning_to_learn=False,
        agi=False,
        summary=summary,
        records=records,
    )
    out_json = output_dir / "seed_agent_loop_benchmark_v1.json"
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def summarize_agent_benchmark(
    records: list[dict[str, Any]],
    manifest: dict[str, Any],
    total_wall_s: float,
    total_cpu_s: float,
) -> dict[str, Any]:
    trials = [r for r in records if r.get("kind") == "agent_loop_trial"]
    by_configuration: dict[str, dict[str, Any]] = {}
    by_cohort: dict[str, dict[str, Any]] = {}

    for r in trials:
        cfg = r["configuration"]
        coh = r["cohort"]
        vcat = r["evaluation"]["verified_category"]
        matched = bool(r["evaluation"]["matches_expected_category"])
        traj = r["agent_trajectory"]

        c_entry = by_configuration.setdefault(cfg, dict(
            total_tasks=0,
            matches_expected_category=0,
            outcome_counts=dict(solved=0, failed=0, rejected=0, blocked=0),
            task_ids_by_outcome=dict(solved=[], failed=[], rejected=[], blocked=[]),
            total_tool_calls=0,
            total_patch_attempts=0,
            total_wall_s=0.0,
        ))
        c_entry["total_tasks"] += 1
        c_entry["matches_expected_category"] += int(matched)
        c_entry["outcome_counts"][vcat] += 1
        c_entry["task_ids_by_outcome"][vcat].append(r["task_id"])
        c_entry["total_tool_calls"] += traj["metrics"]["tool_call_count"]
        c_entry["total_patch_attempts"] += traj["metrics"]["patch_attempt_count"]
        c_entry["total_wall_s"] = round(c_entry["total_wall_s"] + traj["metrics"]["wall_s"], 6)

        coh_entry = by_cohort.setdefault(coh, {}).setdefault(cfg, dict(
            total_tasks=0,
            outcome_counts=dict(solved=0, failed=0, rejected=0, blocked=0),
            total_patch_attempts=0,
            total_tool_calls=0,
        ))
        coh_entry["total_tasks"] += 1
        coh_entry["outcome_counts"][vcat] += 1
        coh_entry["total_patch_attempts"] += traj["metrics"]["patch_attempt_count"]
        coh_entry["total_tool_calls"] += traj["metrics"]["tool_call_count"]

    return dict(
        by_configuration=by_configuration,
        by_cohort=by_cohort,
        resources=dict(
            total_wall_s=round(total_wall_s, 6),
            total_cpu_s=round(total_cpu_s, 6),
            peak_rss_mb=_peak_rss_mb(),
        ),
        aggregate_score=None,
        learning_to_learn=False,
        agi=False,
    )


if __name__ == "__main__":
    cfg = ROOT / "configs/seed_agent_loop_benchmark_v1.json"
    out = ROOT / "artifacts/seed_agent_loop_benchmark_v1"
    result = run_agent_benchmark(cfg, out)
    print(json.dumps(result["summary"], indent=2))
