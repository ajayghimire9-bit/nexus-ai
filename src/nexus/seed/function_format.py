"""Three function-output formats, placeholder rejection, and decoding records.

NEXUS still supplies path and symbol. Real repository discovery of the target
is out of scope; this study uses the public-test entry, as documented.
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any

from .constrained_edit import (
    ConstrainedPlan, extract_function_text, normalize_function, plan_constrained_edit,
    preview_constrained_edit, wrap_constrained_edit,
)
from .local_model_patch_proposer import apply_patch, validate_patch


FORMATS = ("plain_code", "json_function", "json_body")
TIE_BREAK = ("json_function", "plain_code", "json_body")

JSON_FUNCTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "function": {
            "type": "string",
            "minLength": 8,
            "maxLength": 4000,
            "description": (
                "Complete executable Python source of one function, including the "
                "def line, arguments, and body. Not a name, not a comment."
            ),
        },
    },
    "required": ["function"],
}

JSON_BODY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "body": {
            "type": "string",
            "minLength": 1,
            "maxLength": 4000,
            "description": (
                "Executable Python statements for the function body, including "
                "return. Do not include the def line. Not a single identifier."
            ),
        },
    },
    "required": ["body"],
}

DECODING_FIXED = dict(
    endpoint="/completion",
    chat_template=None,
    prompt_field="prompt",
    temperature=0,
    seed=42,
    stop=None,
    runtime_module="local_model_runtime.py",
    runtime_edited=False,
    target_from="public_test_entry_or_existing_symbol",
    target_discovery="not_implemented; appropriate_for_this_experiment_only",
)


def decoding_record(schema, max_tokens: int) -> dict[str, Any]:
    return dict(DECODING_FIXED, json_schema=schema, n_predict=max_tokens, max_tokens=max_tokens)


def shared_task_block(task, plan: ConstrainedPlan) -> str:
    tests = json.dumps(list(getattr(task, "public_tests", []) or [])[:6], allow_nan=False)[:1200]
    docs = []
    for doc in list(getattr(task, "docs", []) or [])[:4]:
        docs.append(f"{doc.get('title', '')}: {str(doc.get('content', ''))[:400]}")
    return (
        f"File: {plan.path}\n"
        f"Symbol: {plan.symbol}\n"
        f"Arguments: {plan.args}\n"
        f"Action: {plan.action}\n"
        f"source_sha256: {plan.source_sha256}\n"
        f"Request: {getattr(task, 'request', '')}\n"
        f"Docs: {' | '.join(docs) or 'none'}\n"
        f"Public tests: {tests}\n"
        f"Current function:\n```python\n{(plan.existing_source or '')[:1800]}\n```\n"
    )


def prompt_for_format(
    fmt: str,
    task,
    plan: ConstrainedPlan,
    public_feedback: dict[str, Any] | None = None,
) -> str:
    if fmt not in FORMATS:
        raise ValueError("unknown_function_format")
    feedback = json.dumps(public_feedback or {}, allow_nan=False)[:800]
    shared = shared_task_block(task, plan)
    if fmt == "plain_code":
        return (
            "Write the complete executable Python source of one function.\n"
            f"The function must be named {plan.symbol} and take ({plan.args}).\n"
            "Include the def line and a real body. Do not return JSON. "
            "Do not write only the function name.\n"
            f"{shared}"
            f"Public execution feedback: {feedback}\n"
        )
    if fmt == "json_function":
        return (
            "Return JSON {\"function\": \"...\"}. The value must be complete "
            "executable Python source of one function, including the def line "
            f"and body. Name it {plan.symbol}({plan.args}). "
            "Do not set function to a single word or identifier.\n"
            f"{shared}"
            f"Public execution feedback: {feedback}\n"
        )
    return (
        "Return JSON {\"body\": \"...\"}. The value must be executable Python "
        f"statements for the body of {plan.symbol}({plan.args}), including return. "
        "Do not include the def line. Do not set body to a single identifier.\n"
        f"{shared}"
        f"Public execution feedback: {feedback}\n"
    )


def schema_for_format(fmt: str):
    if fmt == "plain_code":
        return None
    if fmt == "json_function":
        return JSON_FUNCTION_SCHEMA
    if fmt == "json_body":
        return JSON_BODY_SCHEMA
    raise ValueError("unknown_function_format")


def _strip_fence(text: str) -> str:
    raw = (text or "").strip()
    fence = re.search(r"```(?:python)?\s*(.*?)```", raw, flags=re.S)
    if fence:
        return fence.group(1).strip()
    return raw


def extract_format_text(fmt: str, content: str) -> tuple[str, bool, str]:
    raw = _strip_fence(content)
    if fmt == "plain_code":
        if not raw:
            return "", False, "empty_function"
        try:
            tree = ast.parse(raw)
        except SyntaxError:
            return raw, False, "plain_not_python"
        defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if len(defs) == 1:
            return raw, True, "single_function"
        return raw, False, "plain_not_single_function"
    if "{" in raw:
        try:
            payload = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        except Exception:
            payload = None
        if type(payload) is dict:
            if fmt == "json_function" and payload.get("function"):
                return extract_function_text(json.dumps({"function": payload["function"]}))
            if fmt == "json_body" and payload.get("body") is not None:
                text = str(payload["body"]).strip()
                return text, bool(text), "body_field" if text else "empty_body"
    if fmt == "json_function":
        return extract_function_text(content)
    return raw, bool(raw), "body_unparsed"


def assemble_format_proposal(
    fmt: str,
    content: str,
    request: str,
    files: dict[str, str],
    public_tests: list[dict[str, Any]] | None = None,
    plan: ConstrainedPlan | None = None,
) -> dict[str, Any]:
    target_from = "discovery" if plan is not None else "public_test_entry_or_existing_symbol"
    plan = plan or plan_constrained_edit(request, files, public_tests)
    raw_text, raw_valid, raw_reason = extract_format_text(fmt, content)
    notes: list[str] = []
    function_text = ""
    if raw_valid:
        try:
            function_text, notes = normalize_function(raw_text, plan.symbol, plan.args)
            if fmt == "json_body" and "wrapped_body" not in notes:
                notes.append("wrapped_body")
        except (SyntaxError, ValueError) as exc:
            raw_valid = False
            raw_reason = type(exc).__name__ + ": " + str(exc)[:160]
            function_text = ""
    placeholder = placeholder_diagnostic(function_text, plan.symbol) if function_text else (
        "placeholder_body:empty" if not raw_valid else None
    )
    syntax_valid = False
    patched = None
    validated = None
    if function_text and placeholder is None:
        try:
            ast.parse(function_text)
            syntax_valid = True
            edit = wrap_constrained_edit(plan, function_text)
            validated = validate_patch({"edits": [edit], "assumptions": []}, files, interface="symbol")
            patched = apply_patch(files, validated)
        except Exception as exc:
            syntax_valid = False
            raw_reason = type(exc).__name__ + ": " + str(exc)[:160]
    return {
        "format": fmt,
        "plan": {
            **{k: getattr(plan, k) for k in (
                "action", "path", "symbol", "args", "source_sha256", "existing_source",
            )},
            "target_from": target_from,
        },
        "raw_valid": raw_valid,
        "raw_reason": raw_reason,
        "raw_excerpt": (raw_text or "")[:400],
        "normalized": notes,
        "placeholder": placeholder,
        "syntax_valid": syntax_valid,
        "preview": preview_constrained_edit(plan, function_text),
        "validated": validated,
        "patched_files": patched,
        "structurally_valid": bool(validated and validated.get("structurally_valid") and placeholder is None),
    }


def placeholder_diagnostic(function_text: str, symbol: str) -> str | None:
    """Reject name-only / empty / ellipsis bodies. `return None` is allowed."""
    if not (function_text or "").strip():
        return "placeholder_body:empty"
    try:
        tree = ast.parse(function_text)
    except SyntaxError:
        return None
    defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(defs) != 1:
        return None
    stmts = list(defs[0].body)
    if stmts and isinstance(stmts[0], ast.Expr) and isinstance(stmts[0].value, ast.Constant):
        if isinstance(stmts[0].value.value, str):
            stmts = stmts[1:]
    if not stmts:
        return "placeholder_body:empty"
    if len(stmts) > 1:
        return None
    stmt = stmts[0]
    if isinstance(stmt, ast.Pass):
        return "placeholder_body:pass"
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
        return "placeholder_body:ellipsis"
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Name):
        return "placeholder_body:bare_identifier:" + stmt.value.id
    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Name) and stmt.value.id == symbol:
        return "placeholder_body:returns_own_name:" + symbol
    return None


def revision_feedback(diagnostic: str, public_results: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "validation_error": diagnostic,
        "placeholder_rejected": True,
        "instruction": (
            "The last completion was rejected as a placeholder. "
            "Write executable Python that implements the request. "
            "A function that returns None is allowed only when that is the intended result."
        ),
        "public_results": (public_results or {}).get("results", [])[:6],
    }


def format_score(row: dict[str, Any]) -> int:
    return int(bool(row.get("syntax_valid"))) + int(not row.get("placeholder")) + int(
        bool(row.get("executed"))
    ) + int(bool(row.get("public_passed"))) + int(bool(row.get("semantic_correct")))


def choose_best_format(rows: list[dict[str, Any]]) -> str:
    by_fmt = {fmt: [row for row in rows if row.get("format") == fmt] for fmt in FORMATS}
    totals = {fmt: sum(format_score(row) for row in by_fmt[fmt]) for fmt in FORMATS}
    best = max(totals.values()) if totals else 0
    for fmt in TIE_BREAK:
        if totals.get(fmt) == best:
            return fmt
    return TIE_BREAK[0]
