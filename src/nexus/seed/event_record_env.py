"""Bounded event-record environment for cross-interface transfer.

Observations are field bags, not integer y. Actions inspect slots or
fields. The hidden integer mechanism is the same apply_hidden target,
but the learner sees records. Generic parsing is shared. Task-specific
slot/field bindings are not supplied unless the mapping condition says so.
"""
from __future__ import annotations

from itertools import permutations
from typing import Any

from .mechanism_world import apply_hidden, blank_state

SLOTS = ("alpha", "beta", "gamma", "delta")
SLOT_X = {"alpha": 0, "beta": 1, "gamma": 2, "delta": -1}
FIELDS = ("payload", "result", "echo", "stamp")
READ_ACTIONS = {
    "READ_ALPHA": "alpha",
    "READ_BETA": "beta",
    "READ_GAMMA": "gamma",
    "READ_DELTA": "delta",
}
ASK_ACTIONS = {
    "ASK_PAYLOAD": "payload",
    "ASK_RESULT": "result",
    "ASK_ECHO": "echo",
    "ASK_STAMP": "stamp",
}
EVENT_ACTIONS = tuple(READ_ACTIONS) + tuple(ASK_ACTIONS) + ("RESET", "STOP_IDENTIFY", "STOP_UNRESOLVED")
TRUE_OUTPUT_FIELD = "result"
SUPPLIED_BINDING = dict(SLOT_X, output_field=TRUE_OUTPUT_FIELD)


def parse_record(observation: Any) -> dict[str, int]:
    """Generic numeric-field parser. Shared by every method."""
    if not isinstance(observation, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in observation.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            out[str(key)] = int(value)
    return out


def make_record(mechanism: str, slot: str, stamp: int, hidden: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    x = SLOT_X[slot]
    applied = apply_hidden(mechanism, hidden, "ACT_0" if x == 0 else {
        0: "ACT_0", 1: "ACT_1", 2: "ACT_2", -1: "ACT_NEG",
    }[x])
    y = int(applied["observation"])
    record = dict(
        kind="event",
        slot=slot,
        payload=x,
        result=y,
        echo=x,
        stamp=int(stamp),
    )
    return record, applied["state"]


def apply_event(mechanism: str, hidden: dict[str, Any], action: str,
                last_slot: str | None, stamp: int) -> dict[str, Any]:
    if action == "RESET":
        return dict(observation=None, hidden=blank_state(int(hidden.get("seed") or 0)), last_slot=None, stamp=0)
    if action in READ_ACTIONS:
        slot = READ_ACTIONS[action]
        record, state = make_record(mechanism, slot, stamp + 1, hidden)
        return dict(observation=record, hidden=state, last_slot=slot, stamp=stamp + 1)
    if action in ASK_ACTIONS:
        field = ASK_ACTIONS[action]
        slot = last_slot or "alpha"
        record, state = make_record(mechanism, slot, stamp + 1, hidden)
        return dict(observation={field: record[field]}, hidden=state, last_slot=slot, stamp=stamp + 1)
    return dict(observation=None, hidden=hidden, last_slot=last_slot, stamp=stamp)


def integer_transcript(records: list[dict[str, Any]], binding: dict[str, Any]) -> list[dict[str, Any]]:
    action_for = {0: "ACT_0", 1: "ACT_1", 2: "ACT_2", -1: "ACT_NEG"}
    field = str(binding.get("output_field") or TRUE_OUTPUT_FIELD)
    rows = []
    for rec in records:
        parsed = parse_record(rec)
        slot = rec.get("slot")
        if slot not in SLOT_X:
            continue
        x = int(binding.get(str(slot), SLOT_X[slot])) if str(slot) in binding else SLOT_X[slot]
        if field not in parsed:
            continue
        rows.append(dict(action=action_for.get(x, "ACT_0"), observation=int(parsed[field]), slot=slot))
    return rows


def candidate_bindings() -> list[dict[str, Any]]:
    bindings = []
    for perm in permutations((0, 1, 2, -1)):
        slot_map = dict(zip(SLOTS, perm))
        for field in FIELDS:
            bindings.append(dict(slot_map, output_field=field))
    return bindings


def score_binding(records: list[dict[str, Any]], binding: dict[str, Any],
                  consistent) -> bool:
    rows = integer_transcript(records, binding)
    if len(rows) < 2:
        return False
    return bool(consistent(rows))
