"""Post-behavior structural repair. No task solution is planted."""
from __future__ import annotations

import ast
import json
from typing import Any

from .agent_loop_worker import WORKER_BUILTINS, compile_check

JSON_BODY_ASK = (
    "Return a JSON object with a string field named body. "
    "The body value must be executable Python statements including return. "
    "Do not include the def line. Do not use a placeholder or an ellipsis."
)

ALLOWED_EXTRA = {"float", "dict", "round", "bool", "int", "list"}


def _parse(source: str) -> ast.AST | None:
    if not (source or "").strip():
        return None
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def references_parameter(source: str, param: str) -> bool:
    tree = _parse(source)
    if tree is None:
        return False
    return any(
        isinstance(node, ast.Name) and node.id == param
        for node in ast.walk(tree)
    )


def unbound_names(source: str, param: str, symbol: str = "") -> list[str]:
    tree = _parse(source)
    if tree is None:
        return []
    allowed = set(WORKER_BUILTINS) | ALLOWED_EXTRA | {param, symbol}
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            bound.add(node.arg)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
            continue
        if node.id in allowed or node.id in bound:
            continue
        if node.id not in found:
            found.append(node.id)
    return found


def _excerpt(assembled: dict[str, Any]) -> str:
    preview = assembled.get("preview") or {}
    return str(preview.get("new_excerpt") or assembled.get("raw_excerpt") or assembled.get("extracted_text") or "")


def structural_reject_reason(assembled: dict[str, Any] | None, plan) -> str | None:
    """Return a structural reason only. Never name a correct implementation."""
    assembled = assembled or {}
    param = getattr(plan, "args", None) or "item"
    placeholder = assembled.get("placeholder")
    reason = assembled.get("raw_reason")
    if placeholder or reason in {"placeholder_after_unwrap", "empty_body"}:
        return (
            f"Previous revision was a placeholder; return complete Python "
            f"statements that use parameter '{param}'."
        )
    excerpt = _excerpt(assembled)
    if not assembled.get("syntax_valid"):
        return (
            f"Previous revision was not valid Python; return complete "
            f"statements that use parameter '{param}'."
        )
    files = assembled.get("patched_files")
    if files:
        try:
            compile_check(files)
        except Exception as exc:
            return (
                f"Previous revision failed compile_check ({type(exc).__name__}); "
                f"return statements that use parameter '{param}'."
            )
    names = unbound_names(excerpt, param, getattr(plan, "symbol", "") or "")
    if names:
        return (
            f"Previous revision used undefined name '{names[0]}'; "
            f"return statements that use parameter '{param}'."
        )
    if not references_parameter(excerpt, param):
        return (
            f"Previous revision did not reference '{param}'; "
            f"return statements that use parameter '{param}'."
        )
    return None


def slot3_revision_prompt(
    plan,
    attempt1_body: str,
    behavior_feedback: dict[str, Any],
    attempt2_body: str,
    structural_reason: str,
) -> str:
    symbol = getattr(plan, "symbol", "fn")
    args = getattr(plan, "args", None) or "item"
    first = (attempt1_body or "").replace("\n", " ").strip()[:200]
    second = (attempt2_body or "").replace("\n", " ").strip()[:200]
    text = (
        f"Signature: def {symbol}({args})\n"
        f"{JSON_BODY_ASK}\n"
        f"First body: {first}\n"
        f"{behavior_feedback.get('instruction') or ''}\n"
        f"Failed cases: {json.dumps(behavior_feedback.get('failed_cases') or [], allow_nan=False)}\n"
        f"Second body: {second}\n"
        f"Structural rejection: {structural_reason}\n"
    )
    if '{"body": "..."}' in text or "\"body\": \"...\"" in text:
        raise ValueError("ellipsis_hint_in_slot3_prompt")
    return text


def completion_identities(records: list[dict[str, Any]]) -> list[str]:
    return [
        str(row.get("identity") or "")
        for row in records
        if row.get("kind") == "execution" and row.get("operation") == "complete"
    ]
