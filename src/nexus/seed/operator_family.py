"""Explicit operator-family labels, outcome updates, and reconstructed ranking."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


FAMILY_MARKERS = (
    ("insert_function", "insert_function"),
    ("or_to_explicit_none", "or_to_explicit_none"),
    ("lt_to_lte", "compare_op_swap"),
    ("gt_to_gte", "compare_op_swap"),
    ("lte_to_lt", "compare_op_swap"),
    ("gte_to_gt", "compare_op_swap"),
    ("lt_to_gte", "compare_op_swap"),
    ("gt_to_lte", "compare_op_swap"),
    ("bind_doc", "bind_doc"),
    ("local_model", "local_model"),
    ("repair_schema", "repair_schema"),
    ("add_to", "arithmetic_swap"),
    ("sub_to", "arithmetic_swap"),
    ("mult_to", "arithmetic_swap"),
    ("div_to", "arithmetic_swap"),
)


def operator_family(operator_name: str) -> str:
    text = str(operator_name or "").lower()
    for marker, family in FAMILY_MARKERS:
        if marker in text:
            return family
    return "other"


@dataclass
class FamilyStats:
    successes: int = 0
    failures: int = 0

    @property
    def attempts(self) -> int:
        return self.successes + self.failures

    @property
    def rate(self) -> float:
        if not self.attempts:
            return 0.0
        return self.successes / self.attempts


@dataclass
class OperatorFamilyLedger:
    """Update labels from observed public-test outcomes only."""

    stats: dict[str, FamilyStats] = field(default_factory=lambda: defaultdict(FamilyStats))
    events: list[dict[str, Any]] = field(default_factory=list)

    def update_from_attempts(self, attempts: list[dict[str, Any]], source: str) -> None:
        for attempt in attempts or []:
            family = operator_family(attempt.get("operator_name") or "")
            passed = bool(attempt.get("public_passed"))
            row = self.stats[family]
            if passed:
                row.successes += 1
            else:
                row.failures += 1
            self.events.append({
                "source": source,
                "operator_name": attempt.get("operator_name"),
                "family": family,
                "public_passed": passed,
                "used_private_tests": False,
            })

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        return {
            family: {
                "successes": row.successes,
                "failures": row.failures,
                "attempts": row.attempts,
                "rate": row.rate,
            }
            for family, row in self.stats.items()
        }


def reconstruct_family_scores(attempts: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    """Rebuild scores from execution records, not a stored summary."""
    ledger = OperatorFamilyLedger()
    ledger.update_from_attempts(attempts, "reconstruct")
    return ledger.snapshot()


def rank_source_frequency(
    candidates: list[tuple[str, dict[str, str]]],
    ledger: OperatorFamilyLedger,
) -> list[tuple[str, dict[str, str]]]:
    return sorted(
        candidates,
        key=lambda item: (-ledger.stats[operator_family(item[0])].successes, item[0]),
    )


def rank_learned(
    candidates: list[tuple[str, dict[str, str]]],
    ledger: OperatorFamilyLedger,
) -> list[tuple[str, dict[str, str]]]:
    return sorted(
        candidates,
        key=lambda item: (
            -ledger.stats[operator_family(item[0])].rate,
            -ledger.stats[operator_family(item[0])].successes,
            item[0],
        ),
    )


def rank_fixed_diagnostic(
    candidates: list[tuple[str, dict[str, str]]],
    request: str,
    public_tests: list[dict[str, Any]],
    docs: list[dict[str, Any]] | None = None,
) -> list[tuple[str, dict[str, str]]]:
    """Strong baseline: public tests beat request/doc cues when they conflict."""
    from .repair_schema_memory import classify_boundary_requirement, infer_family

    wanted: list[str] = []
    requirement = classify_boundary_requirement(request, public_tests)
    family = infer_family(request, public_tests)
    if requirement == "inclusive" or family == "comparison_boundary":
        wanted.append("compare_op_swap")
    if family == "missing_function" or any(
        word in (request or "").lower() for word in ("create function", "add function")
    ):
        wanted.append("insert_function")
    if family == "null_default":
        wanted.append("or_to_explicit_none")
    doc_text = " ".join(str(doc.get("content") or "") for doc in docs or []).lower()
    if requirement == "inclusive" and ("exclusive" in doc_text or "strictly" in doc_text):
        wanted = [item for item in wanted if item != "or_to_explicit_none"]
        if "compare_op_swap" not in wanted:
            wanted.insert(0, "compare_op_swap")

    def score(name: str) -> tuple[int, str]:
        fam = operator_family(name)
        if fam in wanted:
            return wanted.index(fam), name
        return 100, name

    return sorted(candidates, key=lambda item: score(item[0]))


def make_ranker(kind: str, ledger: OperatorFamilyLedger):
    def rank(candidates, task):
        pool = list(candidates)
        if kind == "source_frequency":
            return rank_source_frequency(pool, ledger)
        if kind == "learned":
            return rank_learned(pool, ledger)
        return rank_fixed_diagnostic(
            pool, getattr(task, "request", ""), getattr(task, "public_tests", []) or [],
            getattr(task, "docs", []) or [],
        )

    return rank


def attribution_from_trace(tool_calls: list[dict[str, Any]], attempts: list[dict[str, Any]]) -> dict[str, str]:
    tools = {row.get("tool_name") for row in tool_calls or []}
    ops = [row.get("operator_name") or "" for row in attempts or []]
    model_ops = [name for name in ops if str(name).startswith("local_model")]
    ast_ops = [name for name in ops if not str(name).startswith("local_model")]
    return {
        "file_discovery": "index_repository" if "index_repository" in tools else "missing",
        "new_function": (
            "local_model" if any("insert_function" in operator_family(name) or "insert_function" in name
                                 for name in model_ops)
            else ("existing_operator" if any(operator_family(name) == "insert_function" for name in ast_ops)
                  else "unsupplied")
        ),
        "coordinated_edits": (
            "local_model_per_file" if "local_model_per_file" in tools
            else ("existing_operator" if ast_ops else "unsupplied")
        ),
        "public_test_revision": (
            "local_model" if any(str(name).startswith("local_model_revise") for name in ops)
            else "unsupplied"
        ),
        "independent_checks": "assessment_worker",
        "applied_operator": next((name for name, passed in
                                  ((row.get("operator_name"), row.get("public_passed"))
                                   for row in attempts or []) if passed), None) or "none",
        "model_generated_ops": model_ops[:8],
        "existing_operator_ops": ast_ops[:8],
    }


def copy_ledger(ledger: OperatorFamilyLedger) -> OperatorFamilyLedger:
    out = OperatorFamilyLedger()
    out.stats = defaultdict(FamilyStats, {
        family: FamilyStats(row.successes, row.failures) for family, row in ledger.stats.items()
    })
    out.events = deepcopy(ledger.events)
    return out
