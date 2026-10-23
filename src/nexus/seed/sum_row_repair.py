"""Compact sum-over-row-dicts repair: shape feedback and no-op rejection."""
from __future__ import annotations

import ast
import json
from typing import Any

UNPROJECTED_SUM_MESSAGE = (
    "sum() requires per-row numeric extraction over dict elements"
)


def _parse(source: str) -> ast.AST | None:
    if not (source or "").strip():
        return None
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def normalized_expr_dump(source: str) -> str:
    tree = _parse(source)
    if tree is None:
        return (source or "").strip()
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and node.value is not None:
            return ast.dump(node.value, include_attributes=False)
    return ast.dump(tree, include_attributes=False)


def _sum_args(tree: ast.AST) -> list[ast.AST]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sum" and node.args:
            out.append(node.args[0])
    return out


def _is_bare_container(node: ast.AST) -> bool:
    if isinstance(node, (ast.Subscript, ast.Name, ast.Attribute, ast.BoolOp, ast.IfExp, ast.List, ast.Tuple)):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
        return True
    if isinstance(node, ast.BinOp) and _is_bare_container(node.left):
        return True
    return False


def sum_lacks_element_projection(source: str) -> bool:
    tree = _parse(source)
    if tree is None:
        return False
    for arg in _sum_args(tree):
        if isinstance(arg, (ast.GeneratorExp, ast.ListComp)):
            continue
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == "map":
            continue
        if _is_bare_container(arg):
            return True
    return False


def is_int_dict_sum_failure(public: dict[str, Any] | None) -> bool:
    for row in list((public or {}).get("results") or []):
        error = str(row.get("error") or "")
        if "TypeError" in error and "int" in error and "dict" in error:
            return True
    return False


def _row_keys(inp: Any) -> list[str]:
    if type(inp) is not dict:
        return []
    for value in inp.values():
        if type(value) is list:
            for row in value:
                if type(row) is dict:
                    return [str(key) for key in row.keys()]
    return []


def compact_failed_cases(
    public: dict[str, Any] | None,
    public_tests: list[dict[str, Any]] | None,
    limit: int = 2,
) -> list[dict[str, Any]]:
    results = list((public or {}).get("results") or [])
    out = []
    for index, case in enumerate(public_tests or []):
        row = results[index] if index < len(results) else {}
        if row.get("passed"):
            continue
        out.append({
            "input": case.get("input"),
            "expected": case.get("expected"),
            "actual": None if row.get("error") else row.get("actual"),
            "exception": row.get("error") or (public or {}).get("reason"),
        })
        if len(out) >= limit:
            break
    return out


def int_dict_sum_instruction(public_tests: list[dict[str, Any]] | None, failed_cases: list[dict[str, Any]]) -> str:
    keys = []
    for case in failed_cases + list(public_tests or []):
        keys = _row_keys(case.get("input"))
        if keys:
            break
    shown = json.dumps(keys or ["amount"], allow_nan=False)
    return (
        f"TypeError: sum() added int and dict. List elements are dicts "
        f"(keys {shown}); extract a numeric field per element inside "
        f"sum(...), default missing to 0."
    )


def compact_behavioral_feedback(
    public: dict[str, Any] | None,
    public_tests: list[dict[str, Any]] | None,
    failed_expression: str = "",
    spec_text: str = "",
) -> dict[str, Any]:
    from .execution_feedback import layered_public_feedback

    return layered_public_feedback(public, public_tests, spec_text, failed_expression)


def compact_supplied_contract(plan, public_tests: list[dict[str, Any]] | None) -> str:
    """Short contract: field types only. No representative-input dump."""
    from .input_contract import _type_name

    fields: dict[str, str] = {}
    for case in public_tests or []:
        inp = case.get("input")
        if type(inp) is not dict:
            continue
        for key, value in inp.items():
            fields.setdefault(str(key), _type_name(value))
    arg = getattr(plan, "args", None) or "item"
    symbol = getattr(plan, "symbol", "fn")
    typed = "{" + ", ".join(f"{json.dumps(key)}: {kind}" for key, kind in fields.items()) + "}"
    return (
        f"Signature: def {symbol}({arg})\n"
        f"Input contract: {arg}: {typed}\n"
        f"{arg} is a dictionary. Read fields by name.\n"
    )


def compact_initial_prompt(plan, spec: dict[str, Any]) -> str:
    contract = compact_supplied_contract(plan, spec.get("public") or [])
    symbol = getattr(plan, "symbol", "fn")
    return (
        contract
        + f'Return JSON {{"body": "..."}} for {symbol}. Include return. No def line.\n'
        + f'Request: {spec.get("request") or ""}\n'
    )


def compact_revision_prompt(plan, failed_expression: str, feedback: dict[str, Any]) -> str:
    symbol = getattr(plan, "symbol", "fn")
    args = getattr(plan, "args", None) or "item"
    body = (failed_expression or "").replace("\n", " ").strip()[:200]
    return (
        f"Signature: def {symbol}({args})\n"
        'Return JSON {"body": "..."}. Include return. No def line.\n'
        f"Failed body: {body}\n"
        f"{feedback.get('instruction')}\n"
        f"Failed cases: {json.dumps(feedback.get('failed_cases') or [], allow_nan=False)}\n"
    )


def needs_compact_sum_repair(public: dict[str, Any] | None, body: str) -> bool:
    """Compact revision for int+dict TypeError or any unprojected sum(...) body."""
    if is_int_dict_sum_failure(public):
        return True
    return "sum(" in (body or "") and sum_lacks_element_projection(body)


def reject_unprojected_sum(
    prior_body: str,
    new_body: str,
    public: dict[str, Any] | None,
) -> str | None:
    if not needs_compact_sum_repair(public, prior_body):
        return None
    if "sum(" not in (prior_body or ""):
        return None
    if not (new_body or "").strip():
        return UNPROJECTED_SUM_MESSAGE
    if normalized_expr_dump(prior_body) == normalized_expr_dump(new_body):
        return UNPROJECTED_SUM_MESSAGE
    if sum_lacks_element_projection(new_body):
        return UNPROJECTED_SUM_MESSAGE
    return None
