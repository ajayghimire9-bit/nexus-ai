"""Ask when an action names an unresolved referent.

Recognizing a booking keyword is not enough. "Book the later one"
has no prior options, so the host asks which item is meant.
Programmer-supplied. Not learned language understanding.
"""
from __future__ import annotations

import re
from typing import Any

ACTION = re.compile(
    r"\b(book|reserve|schedule|cancel|move|take|use|send|buy|order)\b",
    re.I,
)
REFERENT = re.compile(
    r"\b(the later one|the earlier one|the other one|that one|this one|the other)\b",
    re.I,
)
OPTION = re.compile(r"\b(first|second|dawn|dusk|morning|evening|option|slot|ferry|flight)\b", re.I)


def unresolved_referent(text: str, history: list[str] | None = None) -> dict[str, Any]:
    blob = text or ""
    prior = " ".join(history or [])
    has_action = bool(ACTION.search(blob))
    has_referent = bool(REFERENT.search(blob))
    prior_options = bool(OPTION.search(prior))
    needed = bool(has_action and has_referent and not prior_options)
    question = (
        "Which one do you mean? I do not have a later or earlier option from this conversation."
        if needed else ""
    )
    return dict(
        needed=needed,
        reason="unresolved_referent" if needed else "resolved_or_ordinary",
        has_action=has_action,
        has_referent=has_referent,
        prior_options=prior_options,
        question=question,
        booking_keyword_sufficient=False,
        programmer_supplied=True,
    )


def clarification_reply(text: str, history: list[str] | None = None) -> str | None:
    checked = unresolved_referent(text, history)
    if checked["needed"]:
        return checked["question"]
    return None
