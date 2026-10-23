"""Conversation quality: facts, attribution and state — not keyword presence."""
from __future__ import annotations


def score_conversation_quality(
    text: str,
    state: dict,
    expected: dict,
) -> dict:
    reply = text or ""
    lowered = reply.lower()
    facts = [str(item) for item in expected.get("facts") or []]
    missing = [item for item in facts if item.lower() not in lowered]
    forbidden = [str(item) for item in expected.get("forbidden") or []]
    invented = [item for item in forbidden if item.lower() in lowered]
    attribution = expected.get("attribution")
    attributed = True if not attribution else str(attribution).lower() in lowered
    pending = state.get("pending_clarification") if isinstance(state, dict) else None
    want_pending = expected.get("pending_after", "unset")
    if want_pending == "unset":
        pending_ok = True
    elif want_pending is None:
        pending_ok = pending is None
    else:
        pending_ok = pending is not None
    selected = expected.get("selected")
    selected_state = None
    if isinstance(state, dict):
        selected_state = state.get("selected_file") or state.get("selected_coding_workspace")
    selected_ok = True if not selected else (
        selected_state is not None and str(selected) in str(selected_state)
    )
    last_tool = ""
    if isinstance(state, dict) and state.get("last_correction"):
        last_tool = str(state["last_correction"])
    last_ok = True
    if expected.get("must_use_last_tool"):
        last_ok = bool(last_tool) and any(
            token.lower() in lowered for token in expected.get("facts") or []
        )
    want_op = expected.get("last_op")
    last_intent = state.get("last_intent") if isinstance(state, dict) else None
    op_ok = True if not want_op else (
        isinstance(last_intent, dict) and last_intent.get("op") == want_op
    )
    passed = (
        not missing and not invented and attributed and pending_ok
        and selected_ok and last_ok and op_ok
    )
    return {
        "facts_ok": not missing,
        "missing_facts": missing,
        "invented_claim": bool(invented),
        "invented": invented,
        "attribution_ok": attributed,
        "state_ok": pending_ok and selected_ok,
        "pending_ok": pending_ok,
        "selected_ok": selected_ok,
        "last_tool_ok": last_ok,
        "op_ok": op_ok,
        "passed": passed,
        "scoring": "factual_content_attribution_and_state; not_keyword_presence",
    }
