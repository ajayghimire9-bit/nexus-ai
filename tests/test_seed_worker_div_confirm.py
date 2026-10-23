"""Public missing-field cases, revision-feedback audit, and confirmation locks."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.harder_feature_study import CLOSED_TASK_IDS as HARDER_CLOSED
from nexus.seed.input_contract import FROZEN_RECIPE
from nexus.seed.public_failure import behavioral_feedback
from nexus.seed.revision_feedback_audit import audit_saved_harder_revisions
from nexus.seed.worker_div_confirm_study import (
    AUDIT_IDS, CLOSED_TASK_IDS, HISTORICAL_HARDER_SHA256, WORKER_PROMPT_FREEZE,
    begin, public_covers_required_edges, summarize,
)


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "artifacts/seed_harder_features/seed_harder_features.json"


def test_confirmation_config_has_public_missing_and_empty_cases():
    config = json.loads((ROOT / "configs/seed_worker_div_confirm.json").read_text())
    ids = {row["id"] for row in config["tasks"]}
    assert not ids & CLOSED_TASK_IDS
    assert not ids & HARDER_CLOSED
    assert ids == {"py_bag_total", "py_flag_absent", "py_rate_div", "py_enter_both"}
    assert config["historical_supplied_private_correct"] == 1
    assert config["historical_harder_sha256"] == HISTORICAL_HARDER_SHA256
    assert config["learning_research_resumed"] is False
    assert WORKER_PROMPT_FREEZE["worker_allows_div"] is True
    assert WORKER_PROMPT_FREEZE["format"] == FROZEN_RECIPE["format"]
    for spec in config["tasks"]:
        assert public_covers_required_edges(spec)
        private_inputs = [case["input"] for case in spec["assessment"]]
        public_inputs = [case["input"] for case in spec["public"]]
        assert private_inputs != public_inputs
    bag = next(row for row in config["tasks"] if row["id"] == "py_bag_total")
    assert any(case["input"]["rows"] == [] for case in bag["public"])
    assert any(
        any("amount" not in row for row in case["input"]["rows"])
        for case in bag["public"]
    )
    flag = next(row for row in config["tasks"] if row["id"] == "py_flag_absent")
    assert any("kind" not in case["input"] for case in flag["public"])
    assert any("name" not in case["input"] for case in flag["public"])


def test_behavioral_feedback_surfaces_compile_reason():
    public = {
        "compilation_passed": False,
        "reason": "ValueError:forbidden_ast_node:quote.py:Div",
        "results": [],
    }
    tests = [{"input": {"cents": 250}, "expected": 2.5}]
    feedback = behavioral_feedback(public, tests)
    assert feedback["failed_cases"][0]["exception"] == public["reason"]
    assert feedback["failed_cases"][0]["passed"] is False


def test_historical_revisions_use_of_feedback():
    payload = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    audits = {row["id"]: row for row in audit_saved_harder_revisions(payload["records"], AUDIT_IDS)}
    total = audits["py_rows_sum"]
    assert total["revision_attempted"] is True
    assert total["saw_exception"] is True
    assert any("TypeError" in text for text in total["exceptions_in_feedback"])
    assert total["return_changed"] is True
    assert total["still_sums_row_dicts"] is True
    assert "amount" not in total["revision_return"]
    tag = audits["py_mark_absent"]
    assert tag["revision_attempted"] is True
    assert tag["saw_exception"] is False
    assert tag["feedback_omitted_compile_reason"] is True
    assert "JoinedStr" in str(tag["compilation_reason"])
    assert tag["still_uses_fstring"] is True
    fit = audits["py_inside_span"]
    assert fit["revision_attempted"] is False
    assert fit["public_passed"] is True
    assert fit["semantic_correct"] is False


def test_begin_emits_inspect_and_audit_without_inference():
    config = json.loads((ROOT / "configs/seed_worker_div_confirm.json").read_text())
    records = []
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    begin(config, records.append, historical["records"])
    kinds = [row.get("kind") for row in records]
    assert kinds == ["audit_manifest", "request_inspect", "revision_audit"]
    inspect = records[1]
    assert inspect["frozen_recipe"] == WORKER_PROMPT_FREEZE
    assert inspect["public_includes_missing_or_empty"] is True
    assert inspect["worker_allows_div"] is True
    summary = summarize(records, config)
    assert summary["historical_supplied_private_correct"] == 1
    assert summary["historical_rescoring"] is False
    assert len(summary["revision_audit"]) == 3
    assert summary["learning_to_learn_established"] is False
