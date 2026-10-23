"""Inspectable mathematical interpretation before any calculation.

A syntactically valid expression can still solve the wrong problem.
The host validates a structured statement, then compiles. Compilation
uses only stated quantities. This adapter is programmer-supplied.
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any

from .capability_map import eval_arithmetic


STATEMENT_KEYS = ("quantities", "relationships", "unknown", "unit", "missing", "expression")
UNIT_FACTORS = {
    ("kg", "g"): 1000.0,
    ("g", "kg"): 0.001,
    ("l", "ml"): 1000.0,
    ("ml", "l"): 0.001,
    ("m", "cm"): 100.0,
    ("cm", "m"): 0.01,
}


def parse_statement(text: str) -> dict[str, Any] | None:
    raw = text or ""
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return {key: payload.get(key) for key in STATEMENT_KEYS}


def statement_numbers(statement: dict[str, Any]) -> list[float]:
    values = []
    for row in statement.get("quantities") or []:
        if not isinstance(row, dict):
            continue
        value = row.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def expression_constants(expr: str) -> list[float]:
    try:
        tree = ast.parse(str(expr or ""), mode="eval")
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            out.append(float(node.value))
    return out


def _missing_names(statement: dict[str, Any]) -> list[str]:
    raw = statement.get("missing")
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def validate_statement(statement: dict[str, Any] | None, task: dict[str, Any]) -> dict[str, Any]:
    if not statement:
        return dict(ok=False, clarify=False, errors=["missing_statement"])
    missing = _missing_names(statement)
    if missing or task.get("must_clarify"):
        return dict(ok=False, clarify=True, errors=["underspecified"], missing=missing)
    quantities = statement.get("quantities") or []
    errors = []
    if not quantities:
        errors.append("no_quantities")
    if task.get("has_unknown") and not statement.get("unknown"):
        errors.append("no_unknown")
    if not statement.get("relationships") and not statement.get("expression"):
        errors.append("no_relationship_or_expression")
    return dict(ok=not errors, clarify=False, errors=errors, missing=[])


def compile_statement(statement: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    """Compile only from the stated quantities. Do not peek at the gold answer."""
    expr = str(statement.get("expression") or "").strip()
    allowed = set(statement_numbers(statement))
    allowed.update({100.0, 1000.0, 2.0, 0.5})
    if expr:
        constants = expression_constants(expr)
        extra = [value for value in constants if value not in allowed]
        tool = eval_arithmetic(expr)
        represents = not extra
        if task.get("must_use_values"):
            needed = {float(value) for value in task["must_use_values"]}
            represents = represents and needed <= set(constants)
        return dict(
            ok=bool(tool.get("ok") and represents),
            error=None if tool.get("ok") else tool.get("error"),
            value=tool.get("value") if represents else None,
            expression=expr,
            extra_constants=extra,
            expression_represents_problem=represents,
            compiled_from="stated_expression",
            programmer_supplied_compiler=True,
        )
    quantities = [row for row in (statement.get("quantities") or []) if isinstance(row, dict)]
    if len(quantities) == 1 and statement.get("unit") and quantities[0].get("unit"):
        source = str(quantities[0].get("unit") or "").lower()
        target = str(statement.get("unit") or "").lower()
        factor = UNIT_FACTORS.get((source, target))
        if factor is not None and quantities[0].get("value") is not None:
            compiled = f"{quantities[0]['value']} * {factor}"
            tool = eval_arithmetic(compiled)
            return dict(
                ok=tool.get("ok"),
                error=tool.get("error"),
                value=tool.get("value"),
                expression=compiled,
                extra_constants=[],
                expression_represents_problem=True,
                compiled_from="unit_table",
                programmer_supplied_compiler=True,
            )
    return dict(
        ok=False, error="uncompiled", value=None, expression=None,
        extra_constants=[], expression_represents_problem=False,
        compiled_from="none", programmer_supplied_compiler=True,
    )


def extract_expression(text: str) -> str | None:
    raw = text or ""
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        try:
            payload = json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and payload.get("expression"):
            return str(payload["expression"])
    match = re.search(r"expression['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]", raw, re.I)
    if match:
        return match.group(1)
    return None


def score_interpreted(task: dict[str, Any], statement: dict[str, Any] | None,
                      compiled: dict[str, Any] | None, raw: str) -> dict[str, Any]:
    checked = validate_statement(statement, task)
    if task.get("must_clarify"):
        asked = bool(checked.get("clarify")) or "?" in (raw or "")
        return dict(
            passed=asked,
            clarification=asked,
            interpretation_ok=bool(checked.get("clarify")),
            execution_ok=False,
            answer_ok=False,
            statement=statement,
            validation=checked,
            compiled=compiled,
            inspectable=True,
        )
    tool = compiled or {}
    value = tool.get("value")
    interpretation_ok = bool(checked.get("ok"))
    execution_ok = bool(tool.get("ok"))
    answer_ok = (
        value is not None
        and task.get("answer") is not None
        and abs(float(value) - float(task["answer"])) < 1e-6
    )
    represents = bool(tool.get("expression_represents_problem"))
    unit_ok = True
    if task.get("unit"):
        unit = (statement or {}).get("unit") or raw
        unit_ok = task["unit"].lower() in str(unit).lower()
    return dict(
        passed=bool(interpretation_ok and execution_ok and answer_ok and represents and unit_ok),
        interpretation_ok=interpretation_ok,
        execution_ok=execution_ok,
        answer_ok=answer_ok,
        value=value,
        unit_ok=unit_ok,
        statement=statement,
        validation=checked,
        compiled=tool,
        expression_represents_problem=represents,
        inspectable=True,
        unaided_value=None,
        tool_assisted=True,
    )


def score_direct_calculator(task: dict[str, Any], text: str, expr: str | None) -> dict[str, Any]:
    if task.get("must_clarify"):
        asked = "?" in (text or "") or "need" in (text or "").lower()
        return dict(passed=asked, clarification=asked, expression=expr, inspectable=False)
    tool = eval_arithmetic(expr) if expr else dict(ok=False, error="no_expression", value=None)
    value = tool.get("value") if tool.get("ok") else None
    represents = False
    if expr and task.get("expression"):
        gold = eval_arithmetic(task["expression"])
        represents = bool(tool.get("ok") and gold.get("ok") and tool.get("value") == gold.get("value"))
    if expr and task.get("must_use_values"):
        constants = set(expression_constants(expr))
        needed = {float(value) for value in task["must_use_values"]}
        represents = represents and needed <= constants
    answer_ok = value is not None and abs(float(value) - float(task["answer"])) < 1e-6
    return dict(
        passed=bool(answer_ok and (represents if expr else False)),
        interpretation_ok=None,
        execution_ok=bool(tool.get("ok")),
        answer_ok=answer_ok,
        value=value,
        tool=tool,
        expression=expr,
        expression_represents_problem=represents,
        inspectable=False,
        tool_assisted=bool(tool.get("ok")),
        programmer_supplied_calculator=True,
    )
