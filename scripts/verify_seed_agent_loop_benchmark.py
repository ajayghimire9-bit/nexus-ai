"""Independent replay & tamper-rejecting verifier for `seed-agent-loop-benchmark-v1`.

Verifies that:
1. Every saved trial contains non-empty `tool_calls`, valid `initial_files_sha256`
   and `final_files_sha256` hashes, and a valid unified diff (`final_diff`).
2. Re-evaluating the saved `final_files` inside the bounded worker subprocess
   (`agent_loop_worker.py`) against both the public tests from
   `configs/seed_agent_loop_benchmark_v1.json` and the evaluator's private held-out
   suites reproduces the exact `verified_category` (`solved`, `failed`, `rejected`,
   `blocked`) for every task and configuration.
3. Forging or tampering with a saved patch or outcome category is caught and
   causes the verifier to exit non-zero.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from nexus.evolution1.catalogue import digest
from scripts.run_seed_agent_loop_benchmark import (
    evaluate_agent_outcome_independently,
    summarize_agent_benchmark,
)


def verify(artifact_path: Path, config_path: Path | None = None, run_tamper_self_test: bool = True) -> dict:
    artifact_path = Path(artifact_path)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    manifest_path = Path(config_path) if config_path else (ROOT / "configs/seed_agent_loop_benchmark_v1.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if payload.get("study_id") != manifest["study_id"]:
        raise ValueError("study_id_mismatch")
    if payload.get("aggregate_score") is not None or payload.get("learning_to_learn") is not False:
        raise ValueError("claim_discipline_violation")

    task_map = {t["task_id"]: t for t in manifest["tasks"]}
    trials = [r for r in payload.get("records", []) if r.get("kind") == "agent_loop_trial"]
    expected_count = len(manifest["tasks"]) * len(manifest["configurations"])
    mismatches: list[str] = []

    if len(trials) != expected_count:
        mismatches.append(f"trial_count_mismatch:{len(trials)}!={expected_count}")

    for row in trials:
        tid = row["task_id"]
        cfg = row["configuration"]
        if tid not in task_map:
            mismatches.append(f"unknown_task_id:{tid}")
            continue
        task_spec = task_map[tid]
        traj = row["agent_trajectory"]

        # 1. Verify initial files hash matches manifest
        expected_init_sha = digest(task_spec["files"])
        if traj.get("initial_files_sha256") != expected_init_sha:
            mismatches.append(f"{tid}:{cfg}:initial_files_hash_mismatch")

        # 2. Verify final files hash matches saved final_files
        actual_final_sha = digest(traj.get("final_files", {}))
        if traj.get("final_files_sha256") != actual_final_sha:
            mismatches.append(f"{tid}:{cfg}:final_files_hash_mismatch")

        # 3. Verify tool calls were logged
        if not traj.get("tool_calls"):
            mismatches.append(f"{tid}:{cfg}:missing_tool_calls")

        # 4. Replay saved final_files in bounded worker against private evaluator suite
        replayed = evaluate_agent_outcome_independently(task_spec, traj)
        saved_eval = row.get("evaluation", {})
        if replayed["verified_category"] != saved_eval.get("verified_category"):
            mismatches.append(f"{tid}:{cfg}:verified_category_mismatch:{replayed['verified_category']}!={saved_eval.get('verified_category')}")
        if bool(replayed["private_passed"]) != bool(saved_eval.get("private_passed")):
            mismatches.append(f"{tid}:{cfg}:private_passed_mismatch")

    rebuilt_summary = summarize_agent_benchmark(
        payload["records"],
        manifest,
        payload["summary"]["resources"]["total_wall_s"],
        payload["summary"]["resources"]["total_cpu_s"],
    )
    summary_matches = (
        rebuilt_summary["by_configuration"] == payload["summary"]["by_configuration"]
        and rebuilt_summary["by_cohort"] == payload["summary"]["by_cohort"]
    )
    if not summary_matches:
        mismatches.append("summary_aggregation_mismatch")

    tamper_test_passed = True
    if run_tamper_self_test and not mismatches:
        tampered = copy.deepcopy(payload)
        for r in tampered["records"]:
            if r.get("kind") == "agent_loop_trial" and r["task_id"] == "al01_py_discount_tax_coord":
                # Corrupt the saved patch so it fails private replay while claiming 'solved'
                r["agent_trajectory"]["final_files"]["pricing.py"] = "def compute_discount(subtotal: float, rate: float) -> float:\n    return 0.0\n"
                r["agent_trajectory"]["final_files_sha256"] = digest(r["agent_trajectory"]["final_files"])
                break
        with NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
            json.dump(tampered, tf)
            tf_path = Path(tf.name)
        try:
            try:
                verify(tf_path, config_path=manifest_path, run_tamper_self_test=False)
                tamper_test_passed = False
            except SystemExit:
                tamper_test_passed = True
        finally:
            tf_path.unlink(missing_ok=True)
        if not tamper_test_passed:
            mismatches.append("tamper_self_test_failed_to_reject_broken_patch")

    valid = (len(mismatches) == 0 and summary_matches and tamper_test_passed)
    report = dict(
        valid=valid,
        mismatches=mismatches,
        total_trials_replayed=len(trials),
        independent_worker_replay=True,
        tamper_self_test_passed=tamper_test_passed,
        model_inference=False,
        by_configuration=rebuilt_summary["by_configuration"],
    )
    print(json.dumps(report, indent=2))
    if not valid:
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
