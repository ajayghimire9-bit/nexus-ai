"""Diagnostic-only revision prompts. The failed source is never pasted."""
from __future__ import annotations

import json
from typing import Any

from .structural_revision import JSON_BODY_ASK, keyerror_keys


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


def omit_failed_source(text: str, source: str) -> str:
    cleaned = text
    for fragment in failed_source_fragments(source):
        if fragment in cleaned:
            cleaned = cleaned.replace(fragment, "")
    return cleaned


def diagnostic_revision_prompt(
    plan,
    spec: dict[str, Any],
    feedback: dict[str, Any],
    *,
    omitted_source: str = "",
    public: dict[str, Any] | None = None,
) -> str:
    """Signature + diagnostics only. Never paste the failed implementation."""
    symbol = getattr(plan, "symbol", "fn")
    args = getattr(plan, "args", None) or "item"
    request = spec.get("request") or spec.get("requirement") or ""
    diagnosis = keyerror_diagnosis(public, feedback)
    cases = json.dumps(feedback.get("failed_cases") or [], allow_nan=False)
    text = (
        f"Signature: def {symbol}({args})\n"
        f"{JSON_BODY_ASK}\n"
        f"Request: {request}\n"
        f"{feedback.get('instruction') or ''}\n"
        f"{diagnosis}\n"
        f"Failed cases: {cases}\n"
    )
    text = omit_failed_source(text, omitted_source)
    if '{"body": "..."}' in text or "\"body\": \"...\"" in text:
        raise ValueError("ellipsis_hint_in_revision_prompt")
    for fragment in failed_source_fragments(omitted_source):
        if fragment in text:
            raise ValueError("failed_source_in_revision_prompt")
    return text
