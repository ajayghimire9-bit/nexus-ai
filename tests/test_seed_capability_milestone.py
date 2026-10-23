"""Development checks for labeled ranking, token cells and conversation quality."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.conversation_quality import score_conversation_quality
from nexus.seed.local_model_patch_proposer import validate_patch
from nexus.seed.operator_family import (
    OperatorFamilyLedger, operator_family, rank_fixed_diagnostic,
    reconstruct_family_scores,
)


ROOT = Path(__file__).resolve().parents[1]


def test_config_is_fresh_and_unconfounded():
    config = json.loads((ROOT / "configs/seed_capability_milestone.json").read_text())
    assert config["default_investigation_policy"] == "fixed_boundary"
    assert config["learned_policy_promoted"] is False
    from nexus.seed.capability_milestone import CLOSED_TASK_IDS
    ids = {config["token_task"]["id"], config["feature"]["id"]}
    ids.update(row["id"] for row in config["ranking"]["source"])
    ids.update(row["id"] for row in config["ranking"]["assessment"])
    assert not ids & CLOSED_TASK_IDS
    cues = {row["cue"] for row in config["ranking"]["assessment"]}
    assert cues == {"mixed", "misleading_doc", "multi_defect"}
    assert config["expected_grid"]["token_cells"] == 4
    assert config["feature"]["required_parts"] == [
        "file_discovery", "new_function", "coordinated_edits",
        "public_test_revision", "independent_checks",
    ]


def test_operator_family_and_reconstructed_scores():
    assert operator_family("cap.py:keep:lt_to_lte") == "compare_op_swap"
    assert operator_family("title.py:label:or_to_explicit_none") == "or_to_explicit_none"
    attempts = [
        {"operator_name": "a:lt_to_lte", "public_passed": True},
        {"operator_name": "b:lt_to_lte", "public_passed": False},
        {"operator_name": "c:insert_function:slug:return_none", "public_passed": False},
    ]
    scores = reconstruct_family_scores(attempts)
    assert scores["compare_op_swap"]["successes"] == 1
    assert scores["compare_op_swap"]["attempts"] == 2
    ledger = OperatorFamilyLedger()
    ledger.update_from_attempts(attempts, "src")
    assert ledger.snapshot()["compare_op_swap"]["rate"] == 0.5


def test_fixed_diagnostic_prefers_public_tests_over_misleading_doc():
    files = {"win.py": "x"}
    ranked = rank_fixed_diagnostic(
        [
            ("win.py:echo:insert_function:helper:return_none", files),
            ("win.py:inside:lt_to_lte", files),
        ],
        "Honor the documented window.",
        [{"entry": "win.inside", "input": {"n": 4, "max": 4}, "expected": True}],
        [{"title": "window", "content": "The window is exclusive. Values equal to max must fail."}],
    )
    assert operator_family(ranked[0][0]) == "compare_op_swap"


def test_raw_interface_rejects_symbol_action():
    files = {"m.py": "def echo(text):\n    return text\n"}
    try:
        validate_patch({"edits": [{
            "path": "m.py", "action": "insert_function",
            "new_text": "def mark(a, b):\n    return a\n",
        }]}, files, interface="raw")
        raise AssertionError("raw accepted symbol action")
    except ValueError as exc:
        assert "raw_interface_rejects_symbol_action" in str(exc)
    validated = validate_patch({"edits": [{
        "path": "m.py", "action": "insert_function",
        "new_text": "def mark(a, b):\n    return a\n",
    }]}, files, interface="symbol")
    assert validated["edits"][0]["action"] == "insert_function"


def test_conversation_quality_is_factual_not_keyword():
    state = {
        "selected_file": "/tmp/notes.csv",
        "pending_clarification": None,
        "last_correction": "Executed group_sum on notes.csv.",
    }
    good = score_conversation_quality(
        "I ran grouped totals on notes.csv.",
        state,
        {"facts": ["notes"], "forbidden": ["fees.csv"], "selected": "notes",
         "pending_after": None, "must_use_last_tool": True},
    )
    assert good["passed"] is True
    bad = score_conversation_quality(
        "I updated the workspace and booked a flight.",
        state,
        {"facts": ["notes"], "forbidden": ["booked a flight"], "selected": "notes"},
    )
    assert bad["passed"] is False
    assert bad["scoring"].startswith("factual_content")
