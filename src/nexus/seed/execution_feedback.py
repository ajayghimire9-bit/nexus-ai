"""Layered public-failure feedback: schema, API diagnostics, and spec requirements."""
from __future__ import annotations

import ast
import json
from typing import Any

SUM_SIGNATURE = "sum(iterable, start=0)"


def _walk_lists(value: Any, path: str, found: list[dict[str, Any]]) -> None:
    if type(value) is dict:
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            _walk_lists(item, child, found)
        return
    if type(value) is list:
        keys: list[str] = []
        kinds: list[str] = []
        missing_varies = False
        seen_dicts = 0
        for item in value:
            kinds.append(type(item).__name__)
            if type(item) is dict:
                seen_dicts += 1
                item_keys = [str(key) for key in item.keys()]
                if keys and set(item_keys) != set(keys):
                    missing_varies = True
                for key in item_keys:
                    if key not in keys:
                        keys.append(key)
        found.append({
            "path": path or "$",
            "length": len(value),
            "element_types": sorted(set(kinds)),
            "element_keys": keys,
            "all_elements_dicts": bool(value) and seen_dicts == len(value),
            "empty": len(value) == 0,
            "heterogeneous_keys": missing_varies,
        })
        for index, item in enumerate(value[:4]):
            _walk_lists(item, f"{path}[{index}]", found)


def public_list_schema(public_tests: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Observed list/dict shape from public inputs only. No private data."""
    rows = []
    for case in public_tests or []:
        found: list[dict[str, Any]] = []
        _walk_lists(case.get("input"), "", found)
        rows.extend(found)
    dict_lists = [row for row in rows if row["all_elements_dicts"] or row["empty"]]
    return {
        "kind": "schema_observation",
        "list_paths": dict_lists,
        "has_list_of_dicts": any(row["all_elements_dicts"] for row in dict_lists),
        "has_empty_list": any(row["empty"] for row in dict_lists),
        "conservative": True,
    }


def format_schema_summary(schema: dict[str, Any]) -> str:
    if not schema.get("has_list_of_dicts") and not schema.get("has_empty_list"):
        return ""
    parts = []
    for row in schema.get("list_paths") or []:
        if row.get("empty"):
            parts.append(f"{row['path']}: empty list")
            continue
        if not row.get("all_elements_dicts"):
            continue
        keys = row.get("element_keys") or []
        extra = "; keys vary across elements" if row.get("heterogeneous_keys") else ""
        parts.append(f"{row['path']}: list of dicts, observed keys {json.dumps(keys)}{extra}")
    if not parts:
        return ""
    return "Schema observation (public inputs only): " + "; ".join(parts[:4]) + "."


def sum_api_diagnostic(error: str | None) -> str | None:
    text = str(error or "")
    if "sum()" in text and "unexpected keyword argument 'default'" in text:
        return f"API diagnostic: sum() does not accept default=. Signature: {SUM_SIGNATURE}."
    if "TypeError" in text and "int" in text and "dict" in text:
        return "API diagnostic: sum() received incompatible types (int and dict)."
    return None


def spec_missing_requirement(spec_text: str) -> str | None:
    lowered = (spec_text or "").lower()
    if "missing" not in lowered and "empty" not in lowered:
        return None
    bits = []
    if "missing" in lowered:
        bits.append("missing values follow the public specification")
    if "empty" in lowered:
        bits.append("empty collections follow the public specification")
    return "Requirement: " + "; ".join(bits) + "."


def collect_error_texts(public: dict[str, Any] | None) -> list[str]:
    out = []
    if (public or {}).get("reason"):
        out.append(str(public.get("reason")))
    for row in list((public or {}).get("results") or []):
        if row.get("error"):
            out.append(str(row.get("error")))
    return out


def layered_public_feedback(
    public: dict[str, Any] | None,
    public_tests: list[dict[str, Any]] | None,
    spec_text: str = "",
    failed_expression: str = "",
) -> dict[str, Any]:
    from .public_failure import case_report, operator_hint_present

    results = list((public or {}).get("results") or [])
    cases = list(public_tests or [])
    reports = []
    compile_reason = None
    if not results and (public or {}).get("reason"):
        compile_reason = str(public.get("reason"))
    for index, case in enumerate(cases[:6]):
        row = results[index] if index < len(results) else {}
        report = case_report(case, row)
        if compile_reason and not report.get("exception"):
            report["exception"] = compile_reason
            report["passed"] = False
        reports.append(report)
    failed = [row for row in reports if not row.get("passed")]
    schema = public_list_schema(public_tests)
    api = None
    for error in collect_error_texts(public) + [str(row.get("exception") or "") for row in failed]:
        api = sum_api_diagnostic(error) or api
        if api:
            break
    requirement = spec_missing_requirement(spec_text)
    parts = ["Public tests failed."]
    if api:
        parts.append(api)
    schema_text = format_schema_summary(schema)
    if schema_text:
        parts.append(schema_text)
    if requirement:
        parts.append(requirement)
    parts.append("Failed cases list input, expected, and actual or exception.")
    instruction = " ".join(parts)
    if operator_hint_present(instruction):
        raise ValueError("operator_hint_in_revision_instruction")
    return {
        "validation_error": "public_tests_failed",
        "placeholder_rejected": False,
        "stage": "behavior",
        "instruction": instruction,
        "failed_expression": (failed_expression or "").strip()[:240],
        "failed_cases": [
            {k: row[k] for k in ("input", "expected", "actual", "exception")}
            for row in failed[:2]
        ],
        "schema_observation": schema,
        "api_diagnostic": api,
        "task_requirement": requirement,
        "operator_supplied": False,
    }


def fstring_supported(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(isinstance(node, ast.JoinedStr) for node in ast.walk(tree))
