"""Development checks for three-point boundary evidence and file-switch state."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.boundary_evidence import competing_boundary_resolved
from nexus.seed.conversation_capability import send, write_files
from nexus.seed.lab import SeedWorkspace
from nexus.seed.proposal_trace import proposal_lifecycle


ROOT = Path(__file__).resolve().parents[1]


def test_config_pauses_ranking_and_uses_fresh_ids():
    config = json.loads((ROOT / "configs/seed_boundary_state_workflow.json").read_text())
    assert config["learned_ranking_promoted"] is False
    assert config["default_investigation_policy"] == "fixed_boundary"
    from nexus.seed.reliable_workflow import CLOSED_TASK_IDS
    ids = {row["id"] for row in config["boundary"]}
    ids.add(config["workflow"]["development"]["id"])
    ids.add(config["workflow"]["fresh"]["id"])
    assert not ids & CLOSED_TASK_IDS
    three = next(row for row in config["boundary"] if row["role"] == "complete_teacher_labels")
    assert len(three["public"]) == 3


def test_three_point_teacher_labels_reject_equality_only():
    request = "Allow span equal to the limit."
    complete = competing_boundary_resolved(request, [
        {"input": {"span": 4, "limit": 5}, "expected": True},
        {"input": {"span": 5, "limit": 5}, "expected": True},
        {"input": {"span": 6, "limit": 5}, "expected": False},
    ])
    assert complete["resolved"] is True
    assert complete["used_candidate_disagreement"] is False
    assert complete["used_private_tests"] is False
    incomplete = competing_boundary_resolved(request, [
        {"input": {"span": 5, "limit": 5}, "expected": True},
    ])
    assert incomplete["resolved"] is False
    assert incomplete["reason"] == "missing_below_equal_or_above"
    opposite = competing_boundary_resolved(request, [
        {"input": {"span": 4, "limit": 5}, "expected": False},
        {"input": {"span": 5, "limit": 5}, "expected": True},
        {"input": {"span": 6, "limit": 5}, "expected": True},
    ])
    assert opposite["resolved"] is False
    assert opposite["reason"] == "public_labels_disagree_with_requirement"
    assert opposite["used_candidate_disagreement"] is False


def test_use_fees_instead_updates_selected_file(tmp_path):
    paths = write_files(tmp_path, [
        {"id": "notes", "key": "region", "value": "amount", "rows": [["east", 1]]},
        {"id": "fees", "key": "region", "value": "amount", "rows": [["west", 2]]},
    ])
    ws = SeedWorkspace(tmp_path / "chat", attach_local_runtime=False)
    sid = ws.dispatch(dict(session_id=None, request={"op": "new"}))["session_id"]
    send(ws, sid, f'Use file "{paths["notes"]}".')
    send(ws, sid, f'Summarize totals grouped by region for "{paths["notes"]}".')
    switched = send(ws, sid, f'Not the notes file. Use file "{paths["fees"]}" instead.')
    selected = switched["chat"]["context"]["workspace"]["selected_file"]
    assert "fees" in str(selected)
    result = send(ws, sid, "What did the last tool result say, and which file did it use?")
    assert "Source file:" in result["text"]
    assert "fees" in result["text"]
    topic = send(ws, sid, "What file is selected?")
    assert "fees" in topic["text"]
    pending = topic["chat"]["context"]["workspace"].get("pending_clarification")
    assert pending is None


def test_loop_rejects_equality_only_and_accepts_three_point(tmp_path):
    from nexus.seed.capability_evidence import EventMeter
    from nexus.seed.reliable_workflow import _solve

    config = json.loads((ROOT / "configs/seed_boundary_state_workflow.json").read_text())
    three = next(row for row in config["boundary"] if row["role"] == "complete_teacher_labels")
    equal = next(row for row in config["boundary"] if row["role"] == "incomplete_public")
    meter = EventMeter(lambda _: None)
    accepted = _solve(three, tmp_path, meter, "three", sources=("ast",), budget=6)
    rejected = _solve(equal, tmp_path, meter, "equal", sources=("ast",), budget=6)
    assert accepted.get("public_tests_passed") is True
    assert accepted.get("applied_operator")
    assert rejected.get("public_tests_passed") is False
    assert any(row.get("incomplete_boundary_evidence") for row in rejected.get("patch_attempts") or [])


def test_proposal_lifecycle_separates_discard_from_unusable():
    discarded = proposal_lifecycle({"status": "proposed", "inference_ran": True, "raw_content": "{}"}, queued=False)
    assert discarded["verdict"] == "usable_but_discarded"
    invalid = proposal_lifecycle({
        "status": "invalid_proposal", "inference_ran": True,
        "reason": "ValueError: create_overwrites:mark.py", "raw_content": "{",
    }, queued=False)
    assert invalid["verdict"] == "no_usable_edit"
