"""Explicit field contracts and optional extract → transform → wrap generation.

Extraction is programmer-supplied. Optional and nullable fields are not
silently defaulted. The tested artifact is the wrapped item function.
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any

from .constrained_edit import preview_constrained_edit

PRESENCE = ("required", "optional", "nullable")


def field_spec(name: str, kind: str, presence: str = "required",
               path: list[str] | None = None) -> dict[str, Any]:
    if presence not in PRESENCE:
        raise ValueError("unknown_field_presence")
    route = list(path or [name])
    return dict(name=name, type=kind, presence=presence, path=route)


def make_contract(symbol: str, fields: list[dict[str, Any]], behavior: str,
                 output_type: str | None = None,
                 allowed_values: list[Any] | None = None) -> dict[str, Any]:
    rows = [field_spec(row["name"], row["type"], row.get("presence", "required"), row.get("path"))
            for row in fields]
    return dict(
        symbol=symbol,
        fields=rows,
        behavior=behavior,
        output_type=output_type,
        allowed_values=list(allowed_values) if allowed_values is not None else None,
        transform_symbol="_" + symbol + "_transform",
        programmer_supplied_extraction=True,
        learned_schema_understanding=False,
        contract_source="benchmark_supplied",
    )


def extraction_eligible(contract: dict[str, Any]) -> bool:
    fields = contract.get("fields") or []
    if not fields:
        return False
    return all(row.get("presence") == "required" for row in fields)


def select_generation_path(contract: dict[str, Any]) -> str:
    return "extract" if extraction_eligible(contract) else "direct"


FROZEN_ROUTE = "extract_if_required_and_list_or_nested"


def routed_path(contract: dict[str, Any]) -> str:
    """Frozen before generation. Uses only contract presence, types and paths."""
    if not extraction_eligible(contract):
        return "direct"
    if any(len(row.get("path") or [row["name"]]) > 1 for row in contract["fields"]):
        return "extract"
    if any(row.get("type") == "list" for row in contract["fields"]):
        return "extract"
    return "direct"


def describe_output_contract(contract: dict[str, Any]) -> str:
    kind = contract.get("output_type")
    allowed = contract.get("allowed_values")
    if kind is None and not allowed:
        return "Output contract: none specified."
    lines = [f"Output contract: return type {kind or 'unspecified'}."]
    if allowed:
        shown = ", ".join(json.dumps(value) for value in allowed)
        lines.append(f"Allowed values: {{{shown}}}.")
        if set(allowed) == {"yes", "no"}:
            lines.append("A Boolean is not accepted. Return the strings yes or no.")
    return " ".join(lines)


def boolean_output_feedback(actual: Any, contract: dict[str, Any]) -> str | None:
    allowed = contract.get("allowed_values")
    if not allowed or type(actual) is not bool:
        return None
    shown = ", ".join(json.dumps(value) for value in allowed)
    return (
        f"Output contract requires a string in {{{shown}}}; "
        f"received a Boolean {actual}. Do not return True or False."
    )


def apply_output_contract(public: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Reject contract mismatches. Does not convert Booleans to strings."""
    row = dict(public)
    results = []
    notes = []
    for item in list(public.get("results") or []):
        copy = dict(item)
        message = boolean_output_feedback(copy.get("actual"), contract)
        if message:
            copy["passed"] = False
            copy["output_contract_error"] = message
            notes.append(message)
        results.append(copy)
    row["results"] = results
    if results:
        row["status"] = "passed" if all(item.get("passed") for item in results) else "failed"
    row["output_contract_violations"] = notes
    return row


def mapping_item(row: dict[str, Any]) -> str:
    return "".join("[" + json.dumps(part) + "]" for part in row["path"])


def extraction_statements(contract: dict[str, Any]) -> list[str]:
    if not extraction_eligible(contract):
        raise ValueError("extraction_ineligible_missing_or_optional_fields")
    lines = []
    for row in contract["fields"]:
        if ".get(" in mapping_item(row):
            raise ValueError("silent_default_forbidden")
        lines.append(f"{row['name']} = item{mapping_item(row)}")
    return lines


def yes_no_otherwise_requirement(request: str) -> bool:
    """True when the public requirement is 'yes if …, no otherwise'."""
    text = " ".join((request or "").lower().split())
    return "yes if" in text and ("no otherwise" in text or "otherwise no" in text)


def yes_no_assembly_eligible(request: str, contract: dict[str, Any]) -> bool:
    allowed = contract.get("allowed_values")
    if list(allowed or []) != ["yes", "no"]:
        return False
    return yes_no_otherwise_requirement(request)


def helper_boolean_behavior(behavior: str) -> str:
    text = behavior or ""
    text = re.sub(r"\byes\b", "True", text, flags=re.I)
    text = re.sub(r"\bno\b", "False", text, flags=re.I)
    return text


def yes_no_to_bool(value: Any) -> bool:
    if value == "yes":
        return True
    if value == "no":
        return False
    raise ValueError("helper_expected_not_yes_no")


EXPECTED_BOOLEAN = "expected Boolean"


def assemble_output(result: Any, contract: dict[str, Any]) -> Any:
    """Map a Boolean helper result to labels. No Python truthiness."""
    if type(result) is not bool:
        raise TypeError(EXPECTED_BOOLEAN)
    labels = list(contract.get("allowed_values") or ["yes", "no"])
    if result is True:
        return labels[0]
    if result is False:
        return labels[1]
    raise TypeError(EXPECTED_BOOLEAN)


def trusted_assemble_result(actual: Any, contract: dict[str, Any]) -> dict[str, Any]:
    """Host-side type check. Outside generated-code AST restrictions."""
    if type(actual) is not bool:
        return dict(ok=False, label=None, error=EXPECTED_BOOLEAN, helper_actual=actual)
    return dict(
        ok=True,
        label=assemble_output(actual, contract),
        error=None,
        helper_actual=actual,
    )


def apply_trusted_assembly(report: dict[str, Any], cases: list[dict[str, Any]],
                           contract: dict[str, Any]) -> dict[str, Any]:
    """Apply trusted yes/no labels after the wrapped function returns."""
    row = dict(report)
    results = []
    notes = []
    cases = list(cases or [])
    for index, item in enumerate(list(report.get("results") or [])):
        copy = dict(item)
        verdict = trusted_assemble_result(copy.get("actual"), contract)
        copy["helper_actual"] = verdict["helper_actual"]
        if not verdict["ok"]:
            copy["passed"] = False
            copy["output_assembly_error"] = verdict["error"]
            notes.append(verdict["error"])
        else:
            copy["actual"] = verdict["label"]
            expected = cases[index]["expected"] if index < len(cases) else copy.get("expected")
            copy["passed"] = verdict["label"] == expected
            copy["output_assembly_error"] = None
        results.append(copy)
    row["results"] = results
    if results:
        row["status"] = "passed" if all(item.get("passed") for item in results) else "failed"
    row["output_assembly_errors"] = notes
    return row


def describe_helper_output_contract() -> str:
    return (
        "Output contract: return type bool. Return True or False only. "
        "Do not return the strings yes or no. Do not return 1 or 0."
    )


def boolean_helper_public(contract: dict[str, Any],
                          cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in scalar_public(contract, cases):
        copy = dict(row)
        copy["expected"] = yes_no_to_bool(row["expected"])
        rows.append(copy)
    return rows


def wrap_transform_assemble(contract: dict[str, Any], transform_source: str) -> str:
    """Extract and return the Boolean helper. Labels are applied by the host."""
    return wrap_transform(contract, transform_source)


def wrap_transform(contract: dict[str, Any], transform_source: str) -> str:
    args = ", ".join(row["name"] for row in contract["fields"])
    extract = "\n    ".join(extraction_statements(contract))
    symbol = contract["symbol"]
    helper = contract["transform_symbol"]
    body = transform_source.rstrip() + "\n"
    return (
        f"{body}"
        f"def {symbol}(item):\n"
        f"    {extract}\n"
        f"    return {helper}({args})\n"
    )


def preview_extraction(plan, transform_source: str, contract: dict[str, Any],
                       wrapper_source: str) -> dict[str, Any]:
    preview = preview_constrained_edit(plan, transform_source)
    preview["extraction"] = dict(
        programmer_supplied=True,
        learned_schema_understanding=False,
        path=select_generation_path(contract),
        mapping=[dict(
            source="item" + mapping_item(row),
            argument=row["name"],
            type=row["type"],
            presence=row["presence"],
        ) for row in contract["fields"]],
        tested_symbol=contract["symbol"],
        transform_symbol=contract["transform_symbol"],
        wrapper_excerpt=wrapper_source[:800],
    )
    preview["new_excerpt"] = wrapper_source[:400]
    return preview


def wrapper_uses_silent_default(source: str) -> bool:
    if ".get(" in source:
        return True
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            return True
    return False


def extract_case_input(contract: dict[str, Any], item: dict[str, Any]) -> Any:
    """Read required paths only. Absent required fields raise KeyError."""
    values = []
    for row in contract["fields"]:
        if row["presence"] != "required":
            raise ValueError("extract_case_requires_required_fields")
        cursor: Any = item
        for part in row["path"]:
            cursor = cursor[part]
        values.append(cursor)
    if len(values) == 1:
        return values[0]
    return {row["name"]: values[i] for i, row in enumerate(contract["fields"])}


def scalar_public(contract: dict[str, Any], cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entry = cases[0]["entry"].rsplit(".", 1)[0] + "." + contract["transform_symbol"]
    out = []
    for case in cases:
        inp = extract_case_input(contract, case["input"])
        row = dict(entry=entry, input=inp, expected=case["expected"])
        if type(inp) is dict:
            row["kwargs_input"] = True
        out.append(row)
    return out
