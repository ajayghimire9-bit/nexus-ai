"""Blinded review of frozen capability-map conversation replies.

Dimensions are separate: relevance, factual accuracy, clarification,
correction handling and naturalness. Keyword presence is not a quality
score. This is an agent review of frozen transcripts, not a second
independent human. Methods were identical on that screen.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .unresolved_referent import unresolved_referent

DIMENSIONS = (
    "relevance",
    "factual_accuracy",
    "clarification",
    "correction_handling",
    "naturalness",
)


def load_frozen_conversation(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    seen = set()
    for row in payload.get("rows") or []:
        if row.get("area") != "conversation":
            continue
        task_id = row["task_id"]
        if task_id in seen:
            continue
        seen.add(task_id)
        scored = row.get("scored") or {}
        rows.append(dict(
            review_id=f"R{len(seen):02d}",
            task_id=task_id,
            family=row.get("family"),
            turns=_turns_for(task_id),
            replies=list(scored.get("replies") or []),
            automatic_passed=bool(scored.get("passed")),
            method_hidden=True,
        ))
    return rows


def _turns_for(task_id: str) -> list[str]:
    from .capability_map_tasks import conversation_tasks
    for task in conversation_tasks():
        if task["task_id"] == task_id:
            return list(task["turns"])
    return []


def agent_review_packet(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Judgments on frozen replies. Not an independent human rater."""
    by_id = {
        "conv_follow": dict(
            relevance=1, factual_accuracy=0, clarification=None,
            correction_handling=None, naturalness=1,
            notes=(
                "Both turns stay on tide/rock pools. The high-tide versus "
                "low-tide split is not a reliable fact, so factual accuracy fails."
            ),
        ),
        "conv_paraphrase": dict(
            relevance=1, factual_accuracy=1, clarification=None,
            correction_handling=None, naturalness=0,
            notes=(
                "Keeps river meeting a large body of water. Automatic fail "
                "wanted the word sea; ocean is an acceptable paraphrase. "
                "Copied 'A estuary', so naturalness fails."
            ),
        ),
        "conv_correct": dict(
            relevance=1, factual_accuracy=1, clarification=None,
            correction_handling=1, naturalness=1,
            notes="Uses south after the correction and does not keep north.",
        ),
        "conv_return": dict(
            relevance=1, factual_accuracy=0, clarification=None,
            correction_handling=None, naturalness=1,
            notes=(
                "Returns to the bird after 2+2. 'Harbor pigeon' is invented, "
                "so factual accuracy fails."
            ),
        ),
        "conv_beginner": dict(
            relevance=1, factual_accuracy=1, clarification=None,
            correction_handling=None, naturalness=1,
            notes="Names dissolved salt. A bit textbook, still usable for a beginner.",
        ),
        "conv_clarify": dict(
            relevance=0, factual_accuracy=None, clarification=0,
            correction_handling=None, naturalness=0,
            notes=(
                "Refuses instead of asking which item is later. A booking "
                "keyword is not present and would not have been enough."
            ),
        ),
    }
    reviewed = []
    for row in rows:
        judgment = dict(by_id[row["task_id"]])
        notes = judgment.pop("notes")
        applicable = {key: judgment[key] for key in DIMENSIONS if judgment[key] is not None}
        reviewed.append(dict(
            review_id=row["review_id"],
            task_id=row["task_id"],
            family=row["family"],
            turns=row["turns"],
            replies=row["replies"],
            dimensions=judgment,
            applicable_passed=sum(1 for value in applicable.values() if value == 1),
            applicable_n=len(applicable),
            notes=notes,
            reviewer="agent_on_frozen_transcripts",
            independent_human=False,
            blinded_method=True,
            keyword_quality_score=False,
        ))
    return reviewed


def score_clarify_case(text: str, history: list[str] | None = None) -> dict[str, Any]:
    checked = unresolved_referent(text, history)
    reply = checked["question"] if checked["needed"] else ""
    asked = "?" in reply
    booked = any(word in reply.lower() for word in ("booked", "reservation confirmed", "i have booked"))
    return dict(
        passed=bool(checked["needed"] and asked and not booked),
        clarification=asked,
        booking_keyword_sufficient=False,
        detector=checked,
        reply=reply,
    )


def summarize_review(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {key: dict(passed=0, n=0) for key in DIMENSIONS}
    for row in rows:
        for key in DIMENSIONS:
            value = row["dimensions"][key]
            if value is None:
                continue
            totals[key]["n"] += 1
            totals[key]["passed"] += int(value == 1)
    return dict(
        dimensions=totals,
        tasks=len(rows),
        independent_human=False,
        pending_independent_human=True,
        keyword_quality_score=False,
    )
