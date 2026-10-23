"""Explicit function input contract versus the existing shared task block."""
from __future__ import annotations

import ast
import json
from typing import Any

from .constrained_edit import ConstrainedPlan
from .function_format import prompt_for_format

PROMPT_VARIANTS = ("existing", "contract")
TIE_BREAK = ("contract", "existing")
MAX_COMPLETIONS = 3
FORMAT_REPAIR_SLOT = 1
BEHAVIOR_SLOT = 1


def input_structure(public_tests: list[dict[str, Any]] | None) -> dict[str, str]:
    fields: dict[str, str] = {}
    for case in public_tests or []:
        inp = case.get("input")
        if type(inp) is not dict:
            continue
        for key, value in inp.items():
            fields.setdefault(str(key), type(value).__name__)
    return fields


def representative_inputs(public_tests: list[dict[str, Any]] | None, limit: int = 3) -> list[Any]:
    out = []
    for case in (public_tests or [])[:limit]:
        out.append(case.get("input"))
    return out


def describe_input_contract(plan: ConstrainedPlan, public_tests: list[dict[str, Any]] | None) -> str:
    fields = input_structure(public_tests)
    examples = representative_inputs(public_tests)
    arg = plan.args or "item"
    typed = "{" + ", ".join(f"{json.dumps(key)}: {kind}" for key, kind in fields.items()) + "}"
    example = json.dumps(examples[0], allow_nan=False) if examples else "{}"
    return (
        f"Signature: def {plan.symbol}({arg})\n"
        f"Input contract: {arg}: {typed}\n"
        f"Example: {arg}: {example}\n"
        f"Representative public inputs: {json.dumps(examples, allow_nan=False)}\n"
        f"{arg} is a dictionary. Read fields by name. Do not treat {arg} as a string.\n"
    )


def build_user_prompt(
    variant: str,
    task,
    plan: ConstrainedPlan,
    public_feedback: dict[str, Any] | None = None,
) -> str:
    if variant not in PROMPT_VARIANTS:
        raise ValueError("unknown_prompt_variant")
    base = prompt_for_format("json_body", task, plan, None)
    if variant == "contract":
        tests = list(getattr(task, "public_tests", []) or [])
        base = describe_input_contract(plan, tests) + base
    if public_feedback:
        payload = json.dumps(public_feedback, allow_nan=False)
        if len(payload) > 2400:
            payload = payload[:2400]
        base += "Public execution feedback:\n" + payload + "\n"
    return base


def uses_dict_fields(function_text: str, keys: list[str] | None = None) -> bool:
    if not (function_text or "").strip():
        return False
    try:
        tree = ast.parse(function_text)
    except SyntaxError:
        return False
    wanted = set(keys or [])
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        value = node.value
        slc = node.slice
        if isinstance(value, ast.Name) and isinstance(slc, ast.Constant) and isinstance(slc.value, str):
            if not wanted or slc.value in wanted:
                return True
    return False


def variant_score(row: dict[str, Any]) -> int:
    return (
        int(bool(row.get("syntax_valid")))
        + int(not row.get("placeholder"))
        + int(bool(row.get("executed")))
        + int(bool(row.get("public_passed")))
        + int(bool(row.get("semantic_correct")))
    )


def choose_best_variant(rows: list[dict[str, Any]]) -> str:
    totals = {
        variant: sum(variant_score(row) for row in rows if row.get("prompt_variant") == variant)
        for variant in PROMPT_VARIANTS
    }
    best = max(totals.values()) if totals else 0
    for variant in TIE_BREAK:
        if totals.get(variant) == best:
            return variant
    return TIE_BREAK[0]
