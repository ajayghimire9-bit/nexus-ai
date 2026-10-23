"""Bounded unwrap of accidentally nested code-response envelopes. Never eval."""
from __future__ import annotations

import ast
import json
from typing import Any

RECOGNIZED_KEYS = ("body", "expr", "expression", "code")
MAX_UNWRAP_DEPTH = 3
MAX_TEXT_CHARS = 4000
PLACEHOLDERS = frozenset({"", "...", "…", "pass", "None"})


def _as_mapping(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw or len(raw) > MAX_TEXT_CHARS or not raw.startswith("{"):
        return None
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        try:
            obj = ast.literal_eval(raw)
        except (ValueError, SyntaxError, TypeError, MemoryError):
            return None
    return obj if type(obj) is dict else None


def _single_recognized(mapping: dict[str, Any]) -> tuple[str, Any] | None:
    if len(mapping) != 1:
        return None
    key, value = next(iter(mapping.items()))
    if key not in RECOGNIZED_KEYS:
        return None
    return str(key), value


def unwrap_extracted(text: str) -> dict[str, Any]:
    """Unwrap nested {body|expr|expression|code: str} envelopes only.

    Legitimate dictionary-valued programs (return {"k": v} or {"total": 0})
    are left unchanged. Depth and size are bounded. No eval.
    """
    ops: list[str] = []
    current = (text or "")
    if len(current) > MAX_TEXT_CHARS:
        return {
            "text": current[:MAX_TEXT_CHARS],
            "ops": ops,
            "reject": "envelope_too_large",
            "extracted": text,
        }
    for depth in range(MAX_UNWRAP_DEPTH + 1):
        mapping = _as_mapping(current)
        if mapping is None:
            stripped = current.strip()
            if stripped in PLACEHOLDERS or stripped.strip("\"'") in PLACEHOLDERS:
                return {
                    "text": stripped,
                    "ops": ops,
                    "reject": "placeholder_after_unwrap",
                    "extracted": text,
                }
            return {"text": current, "ops": ops, "reject": None, "extracted": text}
        recognized = _single_recognized(mapping)
        if recognized is None:
            return {"text": current, "ops": ops, "reject": None, "extracted": text}
        if depth >= MAX_UNWRAP_DEPTH:
            return {
                "text": current,
                "ops": ops,
                "reject": "envelope_too_deep",
                "extracted": text,
            }
        key, value = recognized
        ops.append("unwrap_" + key)
        if type(value) is dict:
            current = json.dumps(value, allow_nan=False)
            continue
        if type(value) is not str:
            return {
                "text": current,
                "ops": ops,
                "reject": "envelope_value_not_string",
                "extracted": text,
            }
        current = value
    return {
        "text": current,
        "ops": ops,
        "reject": "envelope_too_deep",
        "extracted": text,
    }
