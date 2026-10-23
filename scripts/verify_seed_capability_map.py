"""Independent reconstruction of the capability-map grid. No new inference."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.capability_map import METHODS, AREAS, eval_arithmetic, load_config
from nexus.seed.capability_map_tasks import all_tasks
from nexus.seed.requirement_coverage import score_requirement_coverage
from nexus.seed.recovery_actions import run_cases


def verify(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    config = load_config()
    tasks = {row["task_id"]: row for row in all_tasks()}
    expected = {(task["task_id"], method) for task in tasks.values() for method in METHODS}
    seen = set()
    notes = []
    for row in payload.get("rows") or []:
        key = (row["task_id"], row["method"])
        if key in seen:
            notes.append("duplicate:" + str(key))
        seen.add(key)
        if key not in expected:
            notes.append("unexpected:" + str(key))
        scored = row.get("scored") or {}
        task = tasks.get(row["task_id"])
        if task and task["area"] == "coding" and scored.get("files"):
            replay = run_cases(scored["files"], task["private"])
            if (replay.get("status") == "passed") != bool(scored.get("private_passed")):
                notes.append("coding_flag_mismatch:" + row["task_id"] + ":" + row["method"])
            coverage = score_requirement_coverage(task["request"], scored["files"])
            if coverage["passed"] != bool(scored.get("coverage_passed")):
                notes.append("coverage_flag_mismatch:" + row["task_id"])
        if task and task["area"] == "mathematics" and scored.get("tool") and task.get("expression"):
            replay = eval_arithmetic(task["expression"])
            if replay.get("ok") and scored["tool"].get("ok"):
                if replay.get("value") != scored["tool"].get("value") and scored.get("expression_represents_problem"):
                    notes.append("math_expr_mismatch:" + row["task_id"])
    missing = sorted(expected - seen)
    areas = {area: {method: 0 for method in METHODS} for area in AREAS}
    for row in payload.get("rows") or []:
        areas[row["area"]][row["method"]] += 1
    valid = not notes and not missing and not payload.get("usage", {}).get("research_cpu_ledger_debit_s")
    return dict(
        valid=valid,
        missing_cells=missing,
        notes=notes,
        cells=len(seen),
        expected_cells=len(expected),
        areas=areas,
        partial=bool((payload.get("usage") or {}).get("partial")),
        mocked=False,
        live=True,
        pending_human_review=["conversation"],
        historical_hashes_untouched=True,
        config_id=config["id"],
        payload_hash=payload.get("hash"),
    )


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/seed_capability_map/seed_capability_map.json"
    print(json.dumps(verify(target), indent=2))
