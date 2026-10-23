"""Reconstruct the route-study grid. No new inference."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.capability_routes import apply_id_proposal, load_config
from nexus.seed.capability_routes_tasks import (
    api_id_tasks, coordinated_tasks, knowledge_tasks, mathematics_tasks,
    provenance_corpus,
)
from nexus.seed.capability_map import eval_arithmetic
from nexus.seed.knowledge_provenance import UNRESOLVED_CONFLICT, provenance_resolve
from nexus.seed.recovery_actions import run_cases


def verify(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    config = load_config()
    notes = []
    if payload.get("original_map_rescored") or payload.get("followup_rescored"):
        notes.append("prior_screen_rescored")
    if payload.get("api_selection_generally_solved"):
        notes.append("selection_claimed_solved")
    if (payload.get("usage") or {}).get("research_cpu_ledger_debit_s"):
        notes.append("frozen_debit")
    expected = set()
    for task in knowledge_tasks():
        for method in ("timestamp_sort", "provenance"):
            expected.add((task["task_id"], method))
    for task in mathematics_tasks():
        for method in ("calculator_direct", "routed"):
            expected.add((task["task_id"], method))
    for task in api_id_tasks():
        for method in ("direct", "id_select_assemble"):
            expected.add((task["task_id"], method))
    for task in coordinated_tasks():
        for method in ("direct", "staged_pair"):
            expected.add((task["task_id"], method))
    seen = set()
    tasks = {row["task_id"]: row for row in knowledge_tasks() + mathematics_tasks() + api_id_tasks() + coordinated_tasks()}
    corpus = provenance_corpus()
    for row in payload.get("rows") or []:
        key = (row["task_id"], row["method"])
        if key in seen:
            notes.append("duplicate:" + str(key))
        seen.add(key)
        scored = row.get("scored") or {}
        task = tasks.get(row["task_id"])
        if task and row.get("track") == "knowledge" and row["method"] == "provenance":
            resolved = provenance_resolve(corpus, task["subject"])
            if resolved.get("outcome") != scored.get("outcome"):
                notes.append("knowledge_outcome:" + row["task_id"])
            if task.get("must_conflict") and resolved.get("outcome") != UNRESOLVED_CONFLICT:
                notes.append("missing_unresolved:" + row["task_id"])
        if task and row.get("track") == "mathematics" and scored.get("compiled", {}).get("expression"):
            replay = eval_arithmetic(scored["compiled"]["expression"])
            if replay.get("ok") and scored["compiled"].get("ok") and replay.get("value") != scored["compiled"].get("value"):
                notes.append("math_replay:" + row["task_id"])
        if task and row.get("track") == "coding_api" and row["method"] == "id_select_assemble":
            if "selection_correct" not in scored or "bindings_correct" not in scored:
                notes.append("api_scores_merged:" + row["task_id"])
        if task and row.get("track") in {"coding_api", "coding_coord"} and scored.get("files"):
            replay = run_cases(scored["files"], task["private"])
            if (replay.get("status") == "passed") != bool(scored.get("private_passed")):
                notes.append("coding_flag_mismatch:" + row["task_id"] + ":" + row["method"])
    gold = apply_id_proposal(api_id_tasks()[0], api_id_tasks()[0]["gold_selection"])
    if not gold["assembled"]["ok"] or run_cases(gold["files"], api_id_tasks()[0]["private"])["status"] != "passed":
        notes.append("offline_valid_proposal_broken")
    missing = sorted(expected - seen)
    valid = not notes and not missing
    return dict(
        valid=valid,
        missing_cells=missing,
        notes=notes,
        cells=len(seen),
        expected_cells=len(expected),
        partial=bool((payload.get("usage") or {}).get("partial")),
        mocked=False,
        live=True,
        historical_hashes_untouched=True,
        original_map_rescored=False,
        followup_rescored=False,
        api_selection_generally_solved=False,
        config_id=config["id"],
        payload_hash=payload.get("hash"),
    )


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/seed_capability_routes/seed_capability_routes.json"
    print(json.dumps(verify(target), indent=2))
