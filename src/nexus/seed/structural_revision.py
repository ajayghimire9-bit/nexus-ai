"""Post-behavior structural repair. No task solution is planted."""
from __future__ import annotations

import ast
import json
import re
from typing import Any

from .agent_loop_worker import WORKER_BUILTINS, compile_check
from .sum_row_repair import normalized_expr_dump

JSON_BODY_ASK = (
    "Return a JSON object with a string field named body. "
    "The body value must be executable Python statements including return. "
    "Do not include the def line. Do not use a placeholder or an ellipsis."
)

ALLOWED_EXTRA = {"float", "dict", "round", "bool", "int", "list"}
DUPLICATE_AST_REASON = (
    "Revision C2 is identical to failed attempt C1; "
    "modify the expression to resolve the reported error."
)
UNCHANGED_SUBSCRIPT_REASON = (
    "Revision still uses direct subscript item[...] which raises KeyError "
    "when a key is missing; handle missing keys safely."
)
KEYERROR_KEY = re.compile(r"KeyError:?\s*['\"]([^'\"]+)['\"]")


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


def ast_fingerprint(source: str) -> str | None:
    tree = _parse(source)
    if tree is None:
        return None
    return ast.dump(tree, include_attributes=False)


def is_duplicate_ast(first: str, second: str) -> bool:
    left = ast_fingerprint(first)
    right = ast_fingerprint(second)
    if left is not None and right is not None and left == right:
        return True
    if not (first or "").strip() or not (second or "").strip():
        return False
    return normalized_expr_dump(first) == normalized_expr_dump(second)


def keyerror_keys(public: dict[str, Any] | None) -> list[str]:
    found: list[str] = []
    texts = []
    if (public or {}).get("reason"):
        texts.append(str(public.get("reason")))
    for row in list((public or {}).get("results") or []):
        if row.get("error"):
            texts.append(str(row.get("error")))
    for text in texts:
        for match in KEYERROR_KEY.finditer(text):
            if match.group(1) not in found:
                found.append(match.group(1))
    return found


def bare_item_keys(source: str, param: str) -> list[str]:
    tree = _parse(source)
    if tree is None:
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        if not isinstance(node.value, ast.Name) or node.value.id != param:
            continue
        slc = node.slice
        if isinstance(slc, ast.Constant) and isinstance(slc.value, str) and slc.value not in found:
            found.append(slc.value)
    return found


def structural_reject_detail(
    assembled: dict[str, Any] | None,
    plan,
    *,
    prior_body: str = "",
    public: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return codes and a structural reason only. Never name a correct implementation."""
    assembled = assembled or {}
    param = getattr(plan, "args", None) or "item"
    placeholder = assembled.get("placeholder")
    reason = assembled.get("raw_reason")
    if placeholder or reason in {"placeholder_after_unwrap", "empty_body"}:
        text = (
            f"Previous revision was a placeholder; return complete Python "
            f"statements that use parameter '{param}'."
        )
        return {"code": "placeholder", "codes": ["placeholder"], "reason": text}
    excerpt = _excerpt(assembled)
    if not assembled.get("syntax_valid"):
        text = (
            f"Previous revision was not valid Python; return complete "
            f"statements that use parameter '{param}'."
        )
        return {"code": "invalid_python", "codes": ["invalid_python"], "reason": text}
    files = assembled.get("patched_files")
    if files:
        try:
            compile_check(files)
        except Exception as exc:
            text = (
                f"Previous revision failed compile_check ({type(exc).__name__}); "
                f"return statements that use parameter '{param}'."
            )
            return {"code": "compile_check", "codes": ["compile_check"], "reason": text}
    names = unbound_names(excerpt, param, getattr(plan, "symbol", "") or "")
    if names:
        text = (
            f"Previous revision used undefined name '{names[0]}'; "
            f"return statements that use parameter '{param}'."
        )
        return {"code": "unbound_name", "codes": ["unbound_name"], "reason": text}
    from .diagnostic_revision import is_constant_string_literal

    if is_constant_string_literal(excerpt, param):
        text = (
            f"Previous revision was a constant string literal that did not "
            f"reference '{param}'; return an expression that uses '{param}'."
        )
        return {"code": "constant_literal_no_item", "codes": ["constant_literal_no_item"], "reason": text}
    if not references_parameter(excerpt, param):
        text = (
            f"Previous revision did not reference '{param}'; "
            f"return statements that use parameter '{param}'."
        )
        return {"code": "no_param_ref", "codes": ["no_param_ref"], "reason": text}
    codes: list[str] = []
    reasons: list[str] = []
    public_failed = public is not None and not public.get("all_passed")
    if public_failed and prior_body and is_duplicate_ast(prior_body, excerpt):
        codes.append("duplicate_ast")
        reasons.append(DUPLICATE_AST_REASON)
    missed = keyerror_keys(public)
    still = [key for key in missed if key in bare_item_keys(excerpt, param)]
    if public_failed and still:
        codes.append("unchanged_subscript_on_keyerror")
        reasons.append(UNCHANGED_SUBSCRIPT_REASON)
    if not codes:
        return None
    return {"code": codes[0], "codes": codes, "reason": " ".join(reasons)}


def structural_reject_reason(
    assembled: dict[str, Any] | None,
    plan,
    *,
    prior_body: str = "",
    public: dict[str, Any] | None = None,
) -> str | None:
    detail = structural_reject_detail(
        assembled, plan, prior_body=prior_body, public=public,
    )
    return None if detail is None else str(detail["reason"])


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
