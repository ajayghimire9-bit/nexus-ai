"""Audit ChatML prompts, schemas, feedback placement, and stop reasons.

The closed live-compare artifact did not log llama.cpp ``truncated``
flags. Heuristics can mark malformed text; they cannot prove a 128-token
hit unless telemetry is present. Identical or echoed drafts may still be
interface failures.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .chat_template import IM_END, IM_START, extract_chatml_user


def looks_malformed(text: str) -> bool:
    raw = text or ""
    if raw.count("{") != raw.count("}"):
        return True
    if raw.count('"') % 2 == 1:
        return True
    if raw.rstrip().endswith(("\\", ", \\\"", "\\\\\" }")):
        return True
    if '"reasons"' in raw and "lexical_frame" in raw:
        return True
    return False


def termination_guess(
    text: str,
    *,
    n_predict: int = 128,
    tokens_predicted: int | None = None,
    truncated: bool | None = None,
) -> str:
    if truncated is True or (
        tokens_predicted is not None and int(tokens_predicted) >= int(n_predict)
    ):
        return "hit_token_cap"
    if looks_malformed(text):
        return "malformed_or_possibly_truncated"
    return "natural_or_unknown"


def inspect_prompt(prompt: str) -> dict[str, Any]:
    user = extract_chatml_user(prompt)
    return dict(
        chatml=IM_START in prompt and IM_END in prompt and prompt.rstrip().endswith(f"{IM_START}assistant"),
        user_extracted=user is not None,
        asks_json_body='Return JSON {"body"' in (user or prompt),
        has_json_schema_instruction="json_body" in (user or "") or "\"body\"" in (user or prompt),
        feedback_in_user="Public execution feedback" in (user or prompt)
        or "The previous sentence failed" in (user or prompt)
        or "Verifier feedback" in (user or prompt),
        json_feedback_block='"reasons"' in (user or prompt) and "lexical_frame" in (user or prompt),
        planted_get=".get" in (user or prompt),
    )


def audit_compare_artifact(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for record in payload.get("records") or []:
        prompt_info = inspect_prompt(record.get("prompt") or "")
        for index, text in enumerate(record.get("candidates") or []):
            rows.append(
                dict(
                    kind=record.get("kind"),
                    index=index,
                    termination=termination_guess(text),
                    malformed=looks_malformed(text),
                    echoed_feedback='"reasons"' in text and "lexical_frame" in text,
                    looks_like_truncated_get=".get" in text and looks_malformed(text),
                    chars=len(text or ""),
                    **prompt_info,
                )
            )
    return dict(
        artifact=str(path),
        n_candidates=len(rows),
        chatml_ok=all(row["chatml"] for row in rows) if rows else False,
        any_json_feedback_in_prompt=any(row["json_feedback_block"] for row in rows),
        any_echoed_feedback=any(row["echoed_feedback"] for row in rows),
        any_malformed=any(row["malformed"] for row in rows),
        any_hit_token_cap=any(row["termination"] == "hit_token_cap" for row in rows),
        stop_reasons_were_not_logged=True,
        rows=rows,
        learning_to_learn=False,
    )
