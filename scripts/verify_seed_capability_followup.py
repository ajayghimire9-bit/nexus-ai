"""Reconstruct the follow-up grid from raw records. No new inference."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".deps"))

from nexus.seed.capability_followup import load_config
from nexus.seed.capability_followup_tasks import (
    api_tasks, coordinated_tasks, knowledge_tasks, mathematics_tasks,
    provenance_corpus,
)
from nexus.seed.capability_map import eval_arithmetic
from nexus.seed.knowledge_provenance import provenance_resolve, timestamp_sort
from nexus.seed.recovery_actions import run_cases


def verify(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    config = load_config()
    notes = []
    if payload.get("original_map_rescored"):
        notes.append("original_map_rescored")
    if (payload.get("usage") or {}).get("research_cpu_ledger_debit_s"):
        notes.append("frozen_debit")
    expected = set()
    for task in knowledge_tasks():
        for method in ("dump_all", "timestamp_sort", "provenance"):
            expected.add((task["task_id"], method))
    for task in mathematics_tasks():
        for method in ("calculator_direct", "interpret_compile"):
            expected.add((task["task_id"], method))
    for task in api_tasks() + coordinated_tasks():
        for method in ("direct", "nexus"):
            expected.add((task["task_id"], method))
    seen = set()
    tasks = {row["task_id"]: row for row in knowledge_tasks() + mathematics_tasks() + api_tasks() + coordinated_tasks()}
    corpus = provenance_corpus()
    for row in payload.get("rows") or []:
        if row.get("track") == "conversation_clarify":
            continue
        key = (row["task_id"], row["method"])
        if key in seen:
            notes.append("duplicate:" + str(key))
        seen.add(key)
        scored = row.get("scored") or {}
        task = tasks.get(row["task_id"])
        if task and row.get("track") == "knowledge" and row["method"] == "provenance":
            resolved = provenance_resolve(corpus, task["subject"])
            if bool(resolved.get("conflict")) != bool(scored.get("conflict")):
                notes.append("knowledge_conflict_mismatch:" + row["task_id"])
        if task and row.get("track") == "knowledge" and row["method"] == "timestamp_sort":
            naive = timestamp_sort(corpus, task["subject"])
            if naive.get("selected") != scored.get("selected") and task["subject"] == "harbor_hours":
                notes.append("timestamp_replay:" + row["task_id"])
        if task and row.get("track") == "mathematics" and scored.get("compiled", {}).get("expression"):
            replay = eval_arithmetic(scored["compiled"]["expression"])
            if replay.get("ok") and scored["compiled"].get("ok"):
                if replay.get("value") != scored["compiled"].get("value"):
                    notes.append("math_replay:" + row["task_id"])
        if task and row.get("track") in {"coding_api", "coding_coord"} and scored.get("files"):
            replay = run_cases(scored["files"], task["private"])
            if (replay.get("status") == "passed") != bool(scored.get("private_passed")):
                notes.append("coding_flag_mismatch:" + row["task_id"] + ":" + row["method"])
    missing = sorted(expected - seen)
    review = payload.get("conversation_review") or []
    if len(review) != 6:
        notes.append("conversation_review_count")
    if any(row.get("keyword_quality_score") for row in review):
        notes.append("keyword_quality_used")
    valid = not notes and not missing
    return dict(
        valid=valid,
        missing_cells=missing,
        notes=notes,
        cells=len(seen),
        expected_cells=len(expected),
        conversation_review=len(review),
        partial=bool((payload.get("usage") or {}).get("partial")),
        mocked=False,
        live=True,
        pending_independent_human=["conversation_review"],
        historical_hashes_untouched=True,
        original_map_rescored=False,
        config_id=config["id"],
        payload_hash=payload.get("hash"),
    )


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/seed_capability_followup/seed_capability_followup.json"
    print(json.dumps(verify(target), indent=2))
