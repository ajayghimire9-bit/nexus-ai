"""Equalized event-record probes for correspondence learning.

Extends the Wave-5 record interface with repeat, shuffle, public
validation, and post-lock private evaluation. Grammar is unchanged.
"""
from __future__ import annotations

from typing import Any

from .event_record_env import SLOTS, SLOT_X, parse_record
from .mechanism_world import apply_hidden, blank_state

PUBLIC_SLOTS = SLOTS
FRESH_SLOT = "epsilon"
FRESH_X = 0
PRIVATE_SLOTS = SLOTS
TRUE_SLOT_X = dict(SLOT_X, epsilon=FRESH_X)
ACTION_FOR = {0: "ACT_0", 1: "ACT_1", 2: "ACT_2", -1: "ACT_NEG"}
CANDIDATE_SLOT_MAPS = (
    dict(alpha=0, beta=1, gamma=2, delta=-1),
    dict(alpha=-1, beta=0, gamma=1, delta=2),
    dict(alpha=-1, beta=2, gamma=1, delta=0),
    dict(alpha=1, beta=2, gamma=-1, delta=0),
    dict(alpha=1, beta=0, gamma=2, delta=-1),
    dict(alpha=0, beta=1, gamma=-1, delta=2),
)
BASE_FIELDS = ("payload", "result", "echo", "stamp")


def fields_for(records: list[dict[str, Any]]) -> tuple[str, ...]:
    from .event_record_env import parse_record
    found = set(BASE_FIELDS)
    for rec in records:
        found.update(parse_record(rec))
    return tuple(sorted(found))


def candidate_bindings(fields: tuple[str, ...] = BASE_FIELDS) -> list[dict[str, Any]]:
    rows = []
    for slot_map in CANDIDATE_SLOT_MAPS:
        for field in fields:
            rows.append(dict(slot_map, output_field=field))
    return rows


def slot_action(slot: str) -> str:
    return ACTION_FOR[TRUE_SLOT_X[slot]]


class RecordWorld:
    def __init__(self, mechanism: str, instance_seed: int, mode: str) -> None:
        self.mechanism = mechanism
        self.mode = mode
        self.public = blank_state(int(instance_seed))
        self.public["seed"] = int(instance_seed)
        self.private = blank_state(int(instance_seed) + 1009)
        self.private["seed"] = int(instance_seed) + 1009
        self.stamp = 0
        self.last_payload: int | None = None
        self.private_stamp = 0
        self.private_last: int | None = None
        self.private_opened = False
        self.locked = False

    def _compose(self, slot: str, hidden: dict[str, Any], stamp: int,
                 last: int | None) -> tuple[dict[str, Any], dict[str, Any], int | None]:
        applied = apply_hidden(self.mechanism, hidden, slot_action(slot))
        x = TRUE_SLOT_X[slot]
        y = int(applied["observation"])
        echo = x if self.mode != "echo_order" else (0 if last is None else int(last))
        record = dict(
            kind="event", slot=slot, payload=x, result=y, echo=echo, stamp=int(stamp) + 1,
        )
        if self.mode == "alias_ambiguous":
            record["alias"] = y
        return record, applied["state"], x

    def public_read(self, slot: str) -> dict[str, Any]:
        rec, self.public, self.last_payload = self._compose(
            slot, self.public, self.stamp, self.last_payload,
        )
        self.stamp += 1
        return rec

    def private_read(self, slot: str) -> dict[str, Any]:
        if not self.locked:
            raise RuntimeError("private_eval_before_lock")
        self.private_opened = True
        rec, self.private, self.private_last = self._compose(
            slot, self.private, self.private_stamp, self.private_last,
        )
        self.private_stamp += 1
        return rec

    def lock(self) -> None:
        self.locked = True


def integer_rows(records: list[dict[str, Any]], binding: dict[str, Any]) -> list[dict[str, Any]]:
    field = str(binding.get("output_field") or "result")
    rows = []
    for rec in records:
        parsed = parse_record(rec)
        slot = rec.get("slot")
        if slot not in TRUE_SLOT_X or field not in parsed:
            continue
        x = int(binding[str(slot)]) if str(slot) in binding else TRUE_SLOT_X[slot]
        action = ACTION_FOR.get(x)
        if action is None:
            continue
        rows.append(dict(action=action, observation=int(parsed[field]), slot=slot, x=x))
    return rows
