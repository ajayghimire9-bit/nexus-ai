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
CONTRACT_SOURCES = ("supplied", "inferred", "asked")
FROZEN_RECIPE = dict(
    model="coder15",
    prompt_style="chatml",
    format="json_body",
    prompt_variant="contract",
    wire_discovery=True,
    max_completions=MAX_COMPLETIONS,
    two_stage_revision=True,
)


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


def _type_name(value: Any) -> str:
    if type(value) is list:
        if value and type(value[0]) is dict:
            inner = ",".join(
                f"{key}:{type(item).__name__}" for key, item in value[0].items()
            )
            return "list[dict:" + inner + "]"
        return "list"
    return type(value).__name__


def fields_from_source(source: str) -> list[str]:
    if not (source or "").strip():
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    keys: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        value, slc = node.value, node.slice
        if isinstance(value, ast.Name) and isinstance(slc, ast.Constant) and isinstance(slc.value, str):
            if slc.value not in keys:
                keys.append(slc.value)
    return keys


def infer_input_contract(
    plan: ConstrainedPlan,
    files: dict[str, str],
    public_tests: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    fields: dict[str, str] = {}
    source = plan.existing_source or files.get(plan.path, "")
    for key in fields_from_source(source):
        fields[key] = "unknown"
    examples = []
    public_keys: set[str] = set()
    for case in public_tests or []:
        inp = case.get("input")
        if type(inp) is not dict:
            continue
        examples.append(inp)
        public_keys.update(str(key) for key in inp)
        for key, value in inp.items():
            fields[str(key)] = _type_name(value)
    top = {key for key in fields if "[]." not in key}
    complete = bool(public_keys) and public_keys <= top
    return {
        "fields": fields,
        "examples": examples,
        "public_keys": sorted(public_keys),
        "complete": complete,
        "from_source": fields_from_source(source),
        "used_public_examples": bool(examples),
    }


def format_inferred_contract(plan: ConstrainedPlan, inferred: dict[str, Any]) -> str:
    arg = plan.args or "item"
    fields = inferred.get("fields") or {}
    typed = "{" + ", ".join(f"{json.dumps(key)}: {kind}" for key, kind in fields.items()) + "}"
    examples = inferred.get("examples") or []
    example = json.dumps(examples[0], allow_nan=False) if examples else "{}"
    return (
        f"Signature: def {plan.symbol}({arg})\n"
        f"Input contract: {arg}: {typed}\n"
        f"Example: {arg}: {example}\n"
        f"Representative public inputs: {json.dumps(examples, allow_nan=False)}\n"
        f"{arg} is a dictionary. Read fields by name. Do not treat {arg} as a string.\n"
    )


def acquire_contract(
    source: str,
    plan: ConstrainedPlan,
    files: dict[str, str],
    public_tests: list[dict[str, Any]] | None,
    *,
    hide_examples: bool = False,
) -> dict[str, Any]:
    if source == "supplied":
        return {
            "origin": "supplied",
            "asked": False,
            "question": None,
            "complete": True,
            "block": describe_input_contract(plan, public_tests),
            "inferred": None,
        }
    tests = [] if hide_examples else public_tests
    inferred = infer_input_contract(plan, files, tests)
    if inferred["complete"]:
        return {
            "origin": "inferred",
            "asked": False,
            "question": None,
            "complete": True,
            "block": format_inferred_contract(plan, inferred),
            "inferred": inferred,
        }
    question = (
        f"What fields does {plan.args or 'item'} contain and what are their types? "
        f"I need this to implement {plan.symbol}."
    )
    return {
        "origin": "asked",
        "asked": True,
        "question": question,
        "complete": True,
        "block": describe_input_contract(plan, public_tests),
        "inferred": inferred,
        "teacher": "benchmark_public_fields",
    }


def build_user_prompt(
    variant: str,
    task,
    plan: ConstrainedPlan,
    public_feedback: dict[str, Any] | None = None,
    contract_block: str | None = None,
) -> str:
    if variant not in PROMPT_VARIANTS:
        raise ValueError("unknown_prompt_variant")
    base = prompt_for_format("json_body", task, plan, None)
    block = contract_block
    if block is None and variant == "contract":
        tests = list(getattr(task, "public_tests", []) or [])
        block = describe_input_contract(plan, tests)
    if block:
        base = block + base
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
