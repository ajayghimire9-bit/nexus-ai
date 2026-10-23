"""Development checks for frozen recipe, harder requirements, and acquisition."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.constrained_edit import plan_constrained_edit
from nexus.seed.harder_feature_study import CLOSED_TASK_IDS, REQUIRED_SUPPLIED_PASSES, gate_passed
from nexus.seed.input_contract import FROZEN_RECIPE, acquire_contract, infer_input_contract
from nexus.seed.target_discovery import discover_edit_target, score_discovery


ROOT = Path(__file__).resolve().parents[1]


def test_config_locks_harder_requirements_and_fresh_ids():
    config = json.loads((ROOT / "configs/seed_harder_features.json").read_text())
    assert not {row["id"] for row in config["tasks"]} & CLOSED_TASK_IDS
    assert config["learning_research_resumed"] is False
    harder = [row for row in config["tasks"] if row["phase"] == "harder"]
    assert {row["family"] for row in harder} >= {
        "list_records", "missing_fields", "interacting_predicates", "two_file",
        "comparison_boundary",
    }
    for row in harder:
        assert row["requirement"]
    assert set(REQUIRED_SUPPLIED_PASSES) <= {row["id"] for row in harder}
    assert FROZEN_RECIPE["model"] == "coder15"
    assert FROZEN_RECIPE["prompt_style"] == "chatml"


def test_infer_complete_from_examples_and_ask_when_hidden():
    files = {"sheet.py": "def echo(text):\n    return text\n"}
    request = "Create function total(item) that sums amount on each row."
    public = [{"entry": "sheet.total", "input": {"rows": [{"amount": 2}]}, "expected": 2}]
    plan = plan_constrained_edit(request, files, public)
    inferred = infer_input_contract(plan, files, public)
    assert inferred["complete"] is True
    assert "rows" in inferred["fields"]
    acquired = acquire_contract("inferred", plan, files, public)
    assert acquired["origin"] == "inferred"
    hidden = acquire_contract("inferred", plan, files, public, hide_examples=True)
    assert hidden["origin"] == "asked"
    assert hidden["asked"] is True
    assert "fields" in (hidden["question"] or "")
    supplied = acquire_contract("supplied", plan, files, public)
    assert supplied["origin"] == "supplied"
    assert 'item: {"rows":' in supplied["block"]


def test_two_file_discovery_selects_quote():
    files = {
        "prices.py": "def fee(item):\n    return item['cents']\n",
        "quote.py": "def echo(text):\n    return text\n",
    }
    discovered = discover_edit_target(
        "Create function due(item) on quote.py that returns cents divided by 100.",
        files,
    )
    gold = {"path": "quote.py", "symbol": "due", "action": "insert_function"}
    assert score_discovery(discovered, gold)["target_correct"] is True


def test_gate_requires_list_and_two_file_passes():
    rows = [
        dict(category="supplied", id="py_rows_sum", semantic_correct=True),
        dict(category="supplied", id="py_mark_absent", semantic_correct=True),
        dict(category="supplied", id="py_admit_pair", semantic_correct=True),
        dict(category="supplied", id="py_due_quote", semantic_correct=False),
        dict(category="supplied", id="py_inside_span", semantic_correct=True),
    ]
    assert gate_passed(rows) is False
    rows[-2]["semantic_correct"] = True
    assert gate_passed(rows) is True
