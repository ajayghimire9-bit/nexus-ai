"""Lifecycle of a local-model patch: inference, parse, validate, queue."""
from __future__ import annotations


def proposal_lifecycle(proposed: dict, *, queued: bool) -> dict:
    status = proposed.get("status")
    reason = str(proposed.get("reason") or "")
    parse_fail = any(token in reason for token in (
        "model_patch_not_json", "empty_model_patch", "model_patch_schema", "JSONDecodeError",
    ))
    if queued:
        verdict = "usable_and_queued"
    elif status == "proposed":
        verdict = "usable_but_discarded"
    elif status == "invalid_proposal":
        verdict = "no_usable_edit"
    elif status == "BLOCKED":
        verdict = "inference_not_called_or_blocked"
    else:
        verdict = str(status or "unknown")
    return {
        "inference_called": proposed.get("telemetry") is not None or bool(proposed.get("inference_ran")),
        "inference_ran": bool(proposed.get("inference_ran")),
        "raw_excerpt": (proposed.get("raw_content") or "")[:400],
        "parse_ok": status in {"proposed", "invalid_proposal"} and not parse_fail,
        "validation_ok": status == "proposed",
        "queued": queued,
        "status": status,
        "reason": proposed.get("reason"),
        "verdict": verdict,
    }
