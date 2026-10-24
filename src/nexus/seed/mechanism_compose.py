"""Compose supplied primitives into previously unstored hypotheses.

Programmer-supplied primitives and a length cap. The fixed synthesizer
and any learned search see the same primitive set.
"""
from __future__ import annotations

from itertools import product
from typing import Any

from .mechanism_world import (
    ACT_INPUTS, EXECUTORS, LANGUAGE, ORACLE_COST, apply_hidden, blank_state,
)

PRIMITIVES = ("add1", "add2", "mul2", "neg")
MAX_COMPOSE = 2
PROBE_SET = ("ACT_0", "ACT_1", "ACT_2", "ACT_NEG", "MEASURE")
HOLDOUT_PROBES = ("ACT_0", "ACT_1", "ACT_2", "ACT_NEG", "MEASURE")
PRIMITIVE_ORIGIN = "programmer_supplied"


def compositions(max_len: int = MAX_COMPOSE) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for length in range(1, max_len + 1):
        rows.extend(product(PRIMITIVES, repeat=length))
    return rows


def pipe_name(parts: tuple[str, ...]) -> str:
    return "|".join(parts)


def apply_pipeline(parts: tuple[str, ...], state: dict[str, Any], action: str) -> dict[str, Any]:
    nxt = dict(s=int(state.get("s") or 0), prev=int(state.get("prev") or 0))
    if action == "RESET":
        return dict(state=dict(s=0, prev=0), observation=None, oracle=0)
    if action not in ACT_INPUTS and action != "MEASURE":
        raise ValueError("not_an_environment_action")
    x = 0 if action == "MEASURE" else ACT_INPUTS[action]
    exact = action == "MEASURE"
    y = int(x)
    for part in parts:
        if part not in EXECUTORS:
            raise ValueError("unknown_primitive:" + part)
        y = int(EXECUTORS[part](nxt, y, exact))
    return dict(
        state=nxt, observation=int(y), oracle=int(ORACLE_COST[action]), exact=exact,
    )


def signature(parts: tuple[str, ...]) -> tuple[tuple[str, int | None], ...]:
    rows = []
    for action in PROBE_SET:
        rows.append((action, apply_pipeline(parts, dict(s=0, prev=0), action)["observation"]))
    return tuple(rows)


def hidden_signature(name: str) -> tuple[tuple[str, int | None], ...]:
    rows = []
    for action in PROBE_SET:
        rows.append((action, apply_hidden(name, blank_state(0), action)["observation"]))
    return tuple(rows)


def filter_compositions(transcript: list[dict[str, Any]]) -> list[tuple[str, ...]]:
    kept = []
    for parts in compositions():
        state = dict(s=0, prev=0)
        ok = True
        for row in transcript:
            action = row["action"]
            if str(action).startswith("STOP"):
                continue
            predicted = apply_pipeline(parts, state, action)
            state = predicted["state"]
            if predicted["observation"] is None:
                continue
            if int(row["observation"]) != int(predicted["observation"]):
                ok = False
                break
        if ok:
            kept.append(parts)
    return kept


def observational_class(members: list[tuple[str, ...]]) -> list[list[str]]:
    groups: dict[tuple[tuple[str, int | None], ...], list[str]] = {}
    for parts in members:
        groups.setdefault(signature(parts), []).append(pipe_name(parts))
    return [sorted(group) for group in groups.values()]


def class_for_hidden(name: str) -> list[str]:
    target = hidden_signature(name)
    found = []
    for parts in compositions():
        if signature(parts) == target:
            found.append(pipe_name(parts))
    return sorted(found)


def synthesize(transcript: list[dict[str, Any]]) -> dict[str, Any]:
    remaining = filter_compositions(transcript)
    classes = observational_class(remaining)
    work = len(compositions())
    representative = remaining[0] if remaining else None
    return dict(
        remaining=[pipe_name(parts) for parts in remaining],
        classes=classes,
        representative=pipe_name(representative) if representative else None,
        n_remaining=len(remaining),
        n_classes=len(classes),
        score_work=work,
        primitives=list(PRIMITIVES),
        primitive_origin=PRIMITIVE_ORIGIN,
        stored_language=list(LANGUAGE),
    )


def score_compose_gain(remaining: list[tuple[str, ...]], transcript: list[dict[str, Any]],
                       action: str) -> dict[str, Any]:
    if action.startswith("STOP") or not remaining:
        return dict(score=float(len(remaining)), work=0, groups={})
    groups: dict[str, list[tuple[str, ...]]] = {}
    work = 0
    for parts in remaining:
        state = dict(s=0, prev=0)
        for row in transcript:
            if str(row["action"]).startswith("STOP"):
                continue
            state = apply_pipeline(parts, state, row["action"])["state"]
        predicted = apply_pipeline(parts, state, action)
        work += 1
        key = "none" if predicted["observation"] is None else str(predicted["observation"])
        groups.setdefault(key, []).append(parts)
    expected = sum(len(group) ** 2 for group in groups.values()) / float(max(len(remaining), 1))
    return dict(score=float(expected), work=work, groups=groups)


def predict_with(parts: tuple[str, ...] | None, action: str) -> int | None:
    if parts is None:
        return None
    return apply_pipeline(parts, dict(s=0, prev=0), action)["observation"]
