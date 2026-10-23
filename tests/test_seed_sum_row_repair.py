"""Offline compile, TypeError shape feedback, and unprojected-sum reject."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.agent_loop_worker import compile_check, evaluate_python_payload
from nexus.seed.sum_row_repair import (
    UNPROJECTED_SUM_MESSAGE,
    compact_behavioral_feedback,
    compact_revision_prompt,
    normalized_expr_dump,
    reject_unprojected_sum,
    sum_lacks_element_projection,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECTED = "return sum((r.get('amount') or 0) for r in (item.get('rows') or []))"
BARE = "return sum(item['rows'] or [0])"
GUARD_ONLY = "return sum(item['rows'] if item.get('rows') else [0])"
BAG_PUBLIC = [
    {"entry": "bag.total", "input": {"rows": [{"amount": 4}, {"amount": 6}]}, "expected": 10},
    {"entry": "bag.total", "input": {"rows": []}, "expected": 0},
    {"entry": "bag.total", "input": {"rows": [{"amount": 2}, {}]}, "expected": 2},
]
BAG_PRIVATE = [
    {"entry": "bag.total", "input": {"rows": [{"amount": 7}]}, "expected": 7},
    {"entry": "bag.total", "input": {"rows": [{}, {}]}, "expected": 0},
    {"entry": "bag.total", "input": {"rows": [{"amount": 1}, {"amount": 1}, {}]}, "expected": 2},
]
TYPEERROR_PUBLIC = {
    "results": [
        {"passed": False, "error": "TypeError: unsupported operand type(s) for +: 'int' and 'dict'"},
        {"passed": True, "actual": 0},
        {"passed": False, "error": "TypeError: unsupported operand type(s) for +: 'int' and 'dict'"},
    ]
}


def test_compile_check_allows_generator_projection_and_passes_bag_cases():
    files = {"bag.py": "def total(item):\n    " + PROJECTED + "\n"}
    loaded = compile_check(files)
    assert "total" in loaded["bag"]
    public = evaluate_python_payload({"language": "python", "files": files, "cases": BAG_PUBLIC})
    private = evaluate_python_payload({"language": "python", "files": files, "cases": BAG_PRIVATE})
    assert public["compilation_passed"] is True
    assert public["all_passed"] is True
    assert private["all_passed"] is True
    listcomp = {"bag.py": "def total(item):\n    return sum([(r.get('amount') or 0) for r in (item.get('rows') or [])])\n"}
    compile_check(listcomp)
    mapped = {
        "bag.py": (
            "def total(item):\n"
            "    return sum(map(lambda r: (r.get('amount') or 0), item.get('rows') or []))\n"
        )
    }
    compile_check(mapped)
    mapped_eval = evaluate_python_payload({"language": "python", "files": mapped, "cases": BAG_PUBLIC})
    assert mapped_eval["all_passed"] is True


def test_compact_feedback_names_dict_element_keys():
    feedback = compact_behavioral_feedback(TYPEERROR_PUBLIC, BAG_PUBLIC, BARE)
    assert "dicts" in feedback["instruction"]
    assert "amount" in feedback["instruction"]
    assert "sum(" in feedback["instruction"]
    assert "0" in feedback["instruction"]
    assert feedback["failed_expression"] == BARE
    assert len(feedback["failed_cases"]) == 2
    assert all(case.get("exception") for case in feedback["failed_cases"])
    prompt = compact_revision_prompt(type("P", (), {"symbol": "total", "args": "item"})(), BARE, feedback)
    assert BARE in prompt
    assert "Representative" not in prompt
    assert "all_cases" not in prompt


def test_reject_noop_and_unprojected_sum_revisions():
    assert sum_lacks_element_projection(BARE) is True
    assert sum_lacks_element_projection(GUARD_ONLY) is True
    assert sum_lacks_element_projection(PROJECTED) is False
    assert normalized_expr_dump(BARE) == normalized_expr_dump("return sum(item['rows'] or [0])\n")
    assert reject_unprojected_sum(BARE, BARE, TYPEERROR_PUBLIC) == UNPROJECTED_SUM_MESSAGE
    assert reject_unprojected_sum(BARE, GUARD_ONLY, TYPEERROR_PUBLIC) == UNPROJECTED_SUM_MESSAGE
    assert reject_unprojected_sum(BARE, PROJECTED, TYPEERROR_PUBLIC) is None
    ok_public = {"results": [{"passed": False, "error": "AssertionError"}]}
    assert reject_unprojected_sum(BARE, BARE, ok_public) is None


def test_fresh_confirm_ids_are_closed_against_prior_families():
    config = json.loads((ROOT / "configs/seed_sum_row_repair_confirm.json").read_text())
    from nexus.seed.sum_row_repair_study import CLOSED_TASK_IDS

    ids = {row["id"] for row in config["tasks"]}
    assert not ids & CLOSED_TASK_IDS
    assert ids == {"py_kit_sum", "py_mark_empty", "py_share_div", "py_pass_both"}
    assert "py_bag_total" in CLOSED_TASK_IDS
    assert "py_flag_absent" in CLOSED_TASK_IDS
    assert "py_rate_div" in CLOSED_TASK_IDS
    assert "py_enter_both" in CLOSED_TASK_IDS
    kit = next(row for row in config["tasks"] if row["id"] == "py_kit_sum")
    assert any(case["input"]["rows"] == [] for case in kit["public"])
    assert any(
        any("amount" not in row for row in case["input"]["rows"])
        for case in kit["public"]
    )
