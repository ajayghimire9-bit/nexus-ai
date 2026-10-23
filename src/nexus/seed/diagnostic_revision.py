"""Diagnostic-only revision prompts. The failed source is never pasted."""
from __future__ import annotations

import ast
import json
from typing import Any

from .structural_revision import JSON_BODY_ASK, _parse, keyerror_keys


ITEM_ANCHOR = (
    "Write a single Python expression using parameter '{param}' that "
    "evaluates both fields in lowercase joined by '/', treating any "
    "omitted key in '{param}' as an empty string ''. "
    "Do not return a constant string literal."
)
GENERIC_ANCHOR = (
    "Write a single Python expression using parameter '{param}'. "
    "Do not return a constant string literal."
)


def failed_source_fragments(source: str) -> list[str]:
    """Distinctive fragments of a failed body. Short tokens are ignored."""
    raw = (source or "").strip()
    out: list[str] = []
    if not raw:
        return out
    candidates = [raw, raw.replace("\n", " ").strip()]
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("def "):
            continue
        candidates.append(line)
        if line.startswith("return "):
            candidates.append(line[7:].strip())
    for item in candidates:
        if item and len(item) >= 12 and item not in out:
            out.append(item)
    return out


def accessed_item_keys(source: str, param: str) -> list[str]:
    tree = _parse(source)
    if tree is None:
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        key = None
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == param:
            slc = node.slice
            if isinstance(slc, ast.Constant) and isinstance(slc.value, str):
                key = slc.value
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "get"
                and isinstance(func.value, ast.Name)
                and func.value.id == param
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                key = node.args[0].value
        if key and key not in found:
            found.append(key)
    return found


def source_features(source: str, param: str) -> dict[str, Any]:
    tree = _parse(source)
    lower = False
    slash = False
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "lower":
                lower = True
            if isinstance(node, ast.Constant) and node.value == "/":
                slash = True
    return {"keys": accessed_item_keys(source, param), "lower": lower, "slash": slash}


def ast_attempt_summary(
    source: str,
    param: str,
    public: dict[str, Any] | None = None,
) -> str:
    features = source_features(source, param)
    keys = features["keys"]
    bits = []
    if features["lower"]:
        bits.append("lowercase formatting")
    if features["slash"]:
        bits.append("'/' separator")
    extra = (" with " + " and ".join(bits)) if bits else ""
    missed = keyerror_keys(public)
    miss = missed[0] if missed else (keys[0] if keys else "a named field")
    shown = json.dumps(keys or missed, allow_nan=False)
    return (
        f"Attempt 1 accessed keys {shown} on '{param}'{extra}, "
        f"but raised KeyError: '{miss}' when a key was omitted from '{param}'."
    )


def keyerror_diagnosis(public: dict[str, Any] | None, feedback: dict[str, Any] | None) -> str:
    keys = list(keyerror_keys(public))
    for row in list((feedback or {}).get("failed_cases") or []):
        text = str(row.get("exception") or "")
        if "KeyError" in text and not keys:
            keys = keyerror_keys({"results": [{"error": text}]})
    if not keys and not any(
        "KeyError" in str(row.get("exception") or "")
        for row in list((feedback or {}).get("failed_cases") or [])
    ):
        if not keyerror_keys(public):
            return ""
    return (
        "Direct subscript access raised KeyError on a missing key. "
        "Handle missing keys safely without assuming every named field is present."
    )


def failed_case_diagnostics(cases: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Keep input and exception. Omit string expected values so they cannot be echoed."""
    out = []
    for row in cases or []:
        item = {"input": row.get("input"), "exception": row.get("exception")}
        expected = row.get("expected")
        if type(expected) is str:
            item["expected_kind"] = "str"
        elif expected is not None:
            item["expected"] = expected
        out.append(item)
    return out


def item_anchor_instruction(plan, spec: dict[str, Any], source: str = "") -> str:
    param = getattr(plan, "args", None) or "item"
    req = " ".join([spec.get("requirement") or "", spec.get("request") or ""]).lower()
    features = source_features(source, param)
    if features.get("slash") or features.get("lower") or "slash" in req or "joined" in req:
        return ITEM_ANCHOR.format(param=param)
    return GENERIC_ANCHOR.format(param=param)


def omit_failed_source(text: str, source: str) -> str:
    cleaned = text
    for fragment in failed_source_fragments(source):
        if fragment in cleaned:
            cleaned = cleaned.replace(fragment, "")
    return cleaned


def is_constant_string_literal(source: str, param: str = "item") -> bool:
    """True when the body is a string constant and does not name the parameter."""
    tree = _parse(source)
    if tree is None:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == param:
            return False
    stmts = []
    defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if defs:
        stmts = list(defs[0].body)
    else:
        stmts = list(tree.body)
    if stmts and isinstance(stmts[0], ast.Expr) and isinstance(stmts[0].value, ast.Constant):
        if isinstance(stmts[0].value.value, str) and len(stmts) > 1:
            stmts = stmts[1:]
    if len(stmts) != 1:
        return False
    stmt = stmts[0]
    value = None
    if isinstance(stmt, ast.Return):
        value = stmt.value
    elif isinstance(stmt, ast.Expr):
        value = stmt.value
    return isinstance(value, ast.Constant) and isinstance(value.value, str)


def looks_like_output_literal(text: str) -> bool:
    """Unquoted or quoted constant results such as /lab/ or '/lab/'."""
    stripped = (text or "").strip()
    if not stripped or "item" in stripped:
        return False
    if is_constant_string_literal(stripped):
        return True
    if len(stripped) >= 2 and stripped[0] in {"'", '"'} and stripped[-1] == stripped[0]:
        return True
    return stripped.startswith("/") and "\n" not in stripped and len(stripped) < 40


def diagnostic_revision_prompt(
    plan,
    spec: dict[str, Any],
    feedback: dict[str, Any],
    *,
    omitted_source: str = "",
    public: dict[str, Any] | None = None,
) -> str:
    """Diagnostics first, item-anchor last. Never paste the failed implementation."""
    symbol = getattr(plan, "symbol", "fn")
    args = getattr(plan, "args", None) or "item"
    request = spec.get("request") or spec.get("requirement") or ""
    diagnosis = keyerror_diagnosis(public, feedback)
    cases = json.dumps(failed_case_diagnostics(feedback.get("failed_cases") or []), allow_nan=False)
    summary = ""
    if diagnosis or keyerror_keys(public):
        summary = ast_attempt_summary(omitted_source, args, public)
    text = (
        f"Failed cases: {cases}\n"
        f"{summary}\n"
        f"{diagnosis}\n"
        f"Signature: def {symbol}({args})\n"
        f"{JSON_BODY_ASK}\n"
        f"Request: {request}\n"
        f"{feedback.get('instruction') or ''}\n"
        f"{item_anchor_instruction(plan, spec, omitted_source)}\n"
    )
    text = omit_failed_source(text, omitted_source)
    if '{"body": "..."}' in text or "\"body\": \"...\"" in text:
        raise ValueError("ellipsis_hint_in_revision_prompt")
    if ".get(" in text:
        raise ValueError("planted_get_in_revision_prompt")
    for fragment in failed_source_fragments(omitted_source):
        if fragment in text:
            raise ValueError("failed_source_in_revision_prompt")
    return text
