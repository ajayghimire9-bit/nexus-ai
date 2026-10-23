"""Independent verifier for `seed-symbiotic-workbench-v1` without model inference.

Reconstructs expected correctness directly from `configs/seed_symbiotic_workbench_v1.json`,
saved input fixtures (`artifacts/seed_symbiotic_workbench_v1/files/*`), and raw trial outputs;
verifies summary tables and resource ledgers; and runs a built-in corruption/tamper check
to confirm that altered outputs or summaries are rejected.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.run_seed_symbiotic_workbench import build_summary, prepare_fixtures, score_trial_independently


def verify(artifact_path: Path, config_path: Path | None = None, run_tamper_self_test: bool = True) -> dict:
    artifact_path = Path(artifact_path)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    manifest_path = Path(config_path) if config_path else (ROOT / "configs/seed_symbiotic_workbench_v1.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if payload.get("study_id") != manifest["study_id"]:
        raise ValueError("study_id_mismatch")
    if payload.get("aggregate_score") is not None or payload.get("learning_to_learn") is not False:
        raise ValueError("claim_discipline_violation")

    files_dir = artifact_path.parent / "files"
    if not files_dir.is_dir():
        from tempfile import TemporaryDirectory
        tmp = TemporaryDirectory()
        fixtures = prepare_fixtures(Path(tmp.name))
    else:
        fixtures = {
            "sales_q1": files_dir / "sales_q1.csv",
            "territory_rev": files_dir / "territory_rev.csv",
            "confirm_bookings": files_dir / "confirm_bookings.csv",
            "regional_orders_json": files_dir / "regional_orders.json",
            "warehouse_sqlite": files_dir / "warehouse.sqlite",
        }

    task_map = {t["id"]: t for t in manifest["tasks"]}
    mismatches: list[str] = []
    trials = [r for r in payload.get("records", []) if r.get("kind") == "workbench_trial"]

    expected_main_trials = len(manifest["tasks"]) * len(manifest["configurations"])
    main_trials = [r for r in trials if r["configuration"] in manifest["configurations"]]
    if len(main_trials) != expected_main_trials:
        mismatches.append(f"trial_count_mismatch:{len(main_trials)}!={expected_main_trials}")

    for row in trials:
        tid = row.get("task_id")
        if tid not in task_map:
            mismatches.append(f"unknown_task_id:{tid}")
            continue
        re_scored = score_trial_independently(row, fixtures)
        saved_scored = row.get("scored", {})
        if bool(re_scored["correct"]) != bool(saved_scored.get("correct")):
            mismatches.append(f"{tid}:{row['configuration']}:correctness_mismatch")
        if bool(re_scored["blocked_external_runtime"]) != bool(saved_scored.get("blocked_external_runtime")):
            mismatches.append(f"{tid}:{row['configuration']}:blocked_flag_mismatch")

    rebuilt_summary = build_summary(
        payload["records"],
        manifest,
        payload["summary"]["resources"]["total_wall_s"],
        payload["summary"]["resources"]["total_cpu_s"],
    )
    summary_matches = (
        rebuilt_summary["by_configuration"] == payload["summary"]["by_configuration"]
        and rebuilt_summary["by_category"] == payload["summary"]["by_category"]
        and rebuilt_summary["by_cohort"] == payload["summary"]["by_cohort"]
    )
    if not summary_matches:
        mismatches.append("summary_aggregation_mismatch")

    tamper_test_passed = True
    if run_tamper_self_test and not mismatches:
        tampered = copy.deepcopy(payload)
        for r in tampered["records"]:
            if r.get("kind") == "workbench_trial" and r["task_id"] == "t01_data_sales_6step":
                r["output"]["step5_rows"] = [{"region": "forged", "total": 99999.0}]
                break
        from tempfile import NamedTemporaryFile
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
            mismatches.append("tamper_self_test_failed_to_reject_forged_output")

    valid = (len(mismatches) == 0 and summary_matches and tamper_test_passed)
    report = dict(
        valid=valid,
        mismatches=mismatches,
        total_trials_verified=len(trials),
        independent_reference_reconstructed=True,
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
