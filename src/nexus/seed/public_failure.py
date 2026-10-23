"""Concrete public-test revision text. Does not name a replacement operator."""
from __future__ import annotations

import ast
from typing import Any

EQUALITY_FAILURE = "For value equal to limit, expected True, received False."
OPERATOR_HINTS = (
    "<=", ">=", "less than or equal", "greater than or equal",
    "less-than-or-equal", "change the operator", "use <=", "use >=",
    "LtE", "replace < with",
)


def _numeric_values_equal(inp: Any) -> bool:
    if type(inp) is not dict:
        return False
    nums = [value for value in inp.values() if type(value) in (int, float)]
    return any(
        nums[i] == nums[j]
        for i in range(len(nums))
        for j in range(i + 1, len(nums))
    )


def equality_mismatch(public: dict[str, Any] | None, public_tests: list[dict[str, Any]] | None) -> bool:
    results = list((public or {}).get("results") or [])
    cases = list(public_tests or [])
    for index, case in enumerate(cases):
        row = results[index] if index < len(results) else {}
        actual = row.get("actual")
        expected = case.get("expected")
        if _numeric_values_equal(case.get("input")) and expected is True and actual is False:
            return True
    return False


def operator_hint_present(text: str) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in OPERATOR_HINTS)


def public_revision_feedback(
    public: dict[str, Any] | None,
    public_tests: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    results = list((public or {}).get("results") or [])[:6]
    cases = list(public_tests or [])[:6]
    paired = []
    for index, case in enumerate(cases):
        row = results[index] if index < len(results) else {}
        paired.append({
            "input": case.get("input"),
            "expected": case.get("expected"),
            "actual": row.get("actual"),
            "passed": row.get("passed"),
        })
    use_equality = equality_mismatch(public, public_tests)
    instruction = (
        EQUALITY_FAILURE + " The public tests failed. Write a corrected function body."
        if use_equality else
        "The public tests failed. Write a corrected function body."
    )
    if operator_hint_present(instruction):
        raise ValueError("operator_hint_in_revision_instruction")
    return {
        "validation_error": "public_tests_failed",
        "placeholder_rejected": False,
        "concrete_failure": EQUALITY_FAILURE if use_equality else None,
        "instruction": instruction,
        "public_results": paired,
        "operator_supplied": False,
    }


VALUE_FIELDS = ("score", "weight", "mass", "n", "value", "level", "hold")
LIMIT_FIELDS = ("limit", "cap", "hi", "max", "floor")


def _pair(inp: Any) -> tuple[Any, Any] | None:
    if type(inp) is not dict:
        return None
    value = next((inp[key] for key in VALUE_FIELDS if key in inp), None)
    limit = next((inp[key] for key in LIMIT_FIELDS if key in inp), None)
    if value is None or limit is None:
        nums = [item for item in inp.values() if type(item) in (int, float)]
        if len(nums) >= 2:
            return nums[0], nums[1]
        return None
    return value, limit


def comparison_band(inp: Any) -> str | None:
    pair = _pair(inp)
    if pair is None:
        return None
    value, limit = pair
    if type(value) not in (int, float) or type(limit) not in (int, float):
        return None
    if value < limit:
        return "below"
    if value == limit:
        return "equal"
    return "above"


def case_report(case: dict[str, Any], row: dict[str, Any] | None) -> dict[str, Any]:
    row = row or {}
    error = row.get("error")
    return {
        "input": case.get("input"),
        "expected": case.get("expected"),
        "actual": None if error else row.get("actual"),
        "exception": error,
        "passed": row.get("passed"),
        "band": comparison_band(case.get("input")),
    }


def behavioral_feedback(
    public: dict[str, Any] | None,
    public_tests: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    results = list((public or {}).get("results") or [])
    cases = list(public_tests or [])
    reports = []
    for index, case in enumerate(cases[:6]):
        row = results[index] if index < len(results) else {}
        reports.append(case_report(case, row))
    failed = [row for row in reports if not row.get("passed")]
    bands = {row["band"] for row in reports if row.get("band")}
    three_point = bands >= {"below", "equal", "above"}
    instruction = (
        "Public tests failed. Each case lists input, expected, and actual or exception."
    )
    if three_point:
        instruction += (
            " Below, equal and above the limit are included. Use that evidence; "
            "do not assume one failed case is enough."
        )
    if operator_hint_present(instruction):
        raise ValueError("operator_hint_in_revision_instruction")
    return {
        "validation_error": "public_tests_failed",
        "placeholder_rejected": False,
        "stage": "behavior",
        "instruction": instruction,
        "failed_cases": failed,
        "all_cases": reports,
        "three_point_evidence": three_point,
        "bands_present": sorted(band for band in bands if band),
        "operator_supplied": False,
    }


def comparison_ops(function_text: str) -> list[str]:
    if not (function_text or "").strip():
        return []
    try:
        tree = ast.parse(function_text)
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            names.extend(type(op).__name__ for op in node.ops)
    return names
