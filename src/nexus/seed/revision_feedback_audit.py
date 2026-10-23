"""Read-only audit of whether historical revisions used public feedback."""
from __future__ import annotations

from typing import Any


def _body(trace: dict[str, Any]) -> str:
    preview = trace.get("preview") or {}
    return str(preview.get("new_excerpt") or trace.get("raw_excerpt") or "")


def _return_line(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("return "):
            return stripped
    return body.strip()


def audit_revision_use(row: dict[str, Any]) -> dict[str, Any]:
    traces = list(row.get("traces") or [])
    first = traces[0] if traces else {}
    revision = next((trace for trace in traces if trace.get("revision_of") == "public_failure"), None)
    failed = (revision or {}).get("failed_cases") or []
    exceptions = [str(case.get("exception") or "") for case in failed if case.get("exception")]
    mismatches = [
        case for case in failed
        if case.get("actual") is not None and case.get("expected") is not None
    ]
    first_body = _body(first)
    rev_body = _body(revision) if revision else ""
    public = row.get("public") or {}
    compile_reason = public.get("reason") if not public.get("compilation_passed", True) else None
    return {
        "id": row.get("id"),
        "origin": row.get("contract_origin"),
        "first_body": first_body[:240],
        "revision_body": rev_body[:240],
        "first_return": _return_line(first_body),
        "revision_return": _return_line(rev_body) if revision else None,
        "revision_attempted": revision is not None,
        "body_changed": bool(revision) and first_body != rev_body,
        "return_changed": bool(revision) and _return_line(first_body) != _return_line(rev_body),
        "failed_case_count": len(failed),
        "exceptions_in_feedback": exceptions,
        "mismatches_in_feedback": [
            {"input": case.get("input"), "expected": case.get("expected"), "actual": case.get("actual")}
            for case in mismatches
        ],
        "saw_exception": bool(exceptions),
        "saw_mismatch": bool(mismatches),
        "compilation_reason": compile_reason,
        "feedback_omitted_compile_reason": bool(compile_reason and not exceptions),
        "same_failing_expression": bool(revision) and first_body == rev_body,
        "still_sums_row_dicts": bool(revision) and "sum(" in first_body and "sum(" in rev_body
            and "amount" not in first_body and "amount" not in rev_body,
        "still_uses_fstring": bool(revision) and (
            ("f'" in first_body or 'f"' in first_body)
            and ("f'" in rev_body or 'f"' in rev_body)
        ),
        "public_passed": bool(row.get("public_passed")),
        "semantic_correct": bool(row.get("semantic_correct")),
    }


def audit_saved_harder_revisions(records: list[dict[str, Any]], task_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    out = []
    for task_id in task_ids:
        row = next(
            (
                item for item in records
                if item.get("category") == "supplied" and item.get("id") == task_id
            ),
            None,
        )
        if row is None:
            out.append({"id": task_id, "missing": True})
            continue
        out.append(audit_revision_use(row))
    return out
