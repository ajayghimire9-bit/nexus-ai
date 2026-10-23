"""Teacher-labeled boundary evidence. Candidate disagreement is not an answer."""
from __future__ import annotations

from typing import Any

from .repair_schema_memory import classify_boundary_requirement


def infer_bound_polarity(request: str) -> str:
    text = (request or "").lower()
    if any(word in text for word in ("floor", "at least", "minimum", "greater", "above the floor")):
        return "lower"
    return "upper"


def teacher_boundary_labels(requirement: str, polarity: str) -> dict[str, bool] | None:
    """Expected below/equal/above from an explicit inclusive or exclusive requirement."""
    if requirement not in {"inclusive", "exclusive"}:
        return None
    if polarity == "lower":
        if requirement == "inclusive":
            return {"below": False, "equal": True, "above": True}
        return {"below": False, "equal": False, "above": True}
    if requirement == "inclusive":
        return {"below": True, "equal": True, "above": False}
    return {"below": True, "equal": False, "above": False}


def classify_public_point(case: dict[str, Any]) -> str | None:
    inp = case.get("input")
    if type(inp) is not dict:
        return None
    nums = [
        value for value in inp.values()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if len(nums) < 2:
        return None
    left, right = nums[0], nums[1]
    if left == right:
        return "equal"
    if left < right:
        return "below"
    return "above"


def labeled_boundary_points(public_tests: list[dict[str, Any]]) -> dict[str, bool]:
    found: dict[str, bool] = {}
    for case in public_tests or []:
        point = classify_public_point(case)
        if point is None or "expected" not in case:
            continue
        if case["expected"] not in {True, False}:
            continue
        found[point] = bool(case["expected"])
    return found


def competing_boundary_resolved(
    request: str,
    public_tests: list[dict[str, Any]],
    private_tests: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Accept only when a teacher/requirement labels below, equal and above.

    Private tests are ignored. Disagreement among candidates is not used.
    """
    del private_tests
    requirement = classify_boundary_requirement(request, public_tests)
    polarity = infer_bound_polarity(request)
    expected = teacher_boundary_labels(requirement, polarity)
    observed = labeled_boundary_points(public_tests)
    if expected is None:
        return {
            "resolved": False,
            "reason": "requirement_not_explicit",
            "requirement": requirement,
            "used_candidate_disagreement": False,
            "used_private_tests": False,
        }
    missing = [name for name in ("below", "equal", "above") if name not in observed]
    if missing:
        return {
            "resolved": False,
            "reason": "missing_below_equal_or_above",
            "missing": missing,
            "requirement": requirement,
            "used_candidate_disagreement": False,
            "used_private_tests": False,
        }
    mismatch = [name for name, value in expected.items() if observed.get(name) != value]
    if mismatch:
        return {
            "resolved": False,
            "reason": "public_labels_disagree_with_requirement",
            "mismatch": mismatch,
            "requirement": requirement,
            "used_candidate_disagreement": False,
            "used_private_tests": False,
        }
    return {
        "resolved": True,
        "reason": "teacher_labeled_three_point",
        "requirement": requirement,
        "polarity": polarity,
        "labels": expected,
        "used_candidate_disagreement": False,
        "used_private_tests": False,
    }


def is_boundary_operator(operator_name: str) -> bool:
    text = str(operator_name or "").lower()
    return any(token in text for token in (
        "lt_to_lte", "gt_to_gte", "lte_to_lt", "gte_to_gt", "lt_to_gte", "gt_to_lte",
        "compare_op", "repair_schema",
    ))
