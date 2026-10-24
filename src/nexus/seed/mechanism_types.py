"""Type-directed synthesis and an affine fitter. Programmer-supplied.

The enumerator only builds legal type pairs. The fitter is a simple
model baseline, not a weakened syntax search.
"""
from __future__ import annotations

from itertools import product
from typing import Any

from .mechanism_world import ACT_INPUTS

STRUCTURAL_PRIMITIVES = ("add1", "add2", "mul2", "neg", "if_pos", "if_neg", "sat_inc", "sat_dec")
PRIMITIVE_TYPES = {
    "add1": "transform",
    "add2": "transform",
    "mul2": "transform",
    "neg": "transform",
    "if_pos": "gate",
    "if_neg": "gate",
    "sat_inc": "state",
    "sat_dec": "state",
}
LEGAL_PAIRS = {
    ("transform", "transform"),
    ("gate", "transform"),
    ("transform", "gate"),
    ("state", "transform"),
    ("gate", "state"),
    ("transform", "state"),
}
TYPE_ORIGIN = "programmer_supplied"


def typed_compositions() -> list[tuple[str, ...]]:
    singles = [(name,) for name in STRUCTURAL_PRIMITIVES]
    pairs = []
    for left, right in product(STRUCTURAL_PRIMITIVES, repeat=2):
        if (PRIMITIVE_TYPES[left], PRIMITIVE_TYPES[right]) in LEGAL_PAIRS:
            pairs.append((left, right))
    return singles + pairs


def type_tag(parts: tuple[str, ...]) -> str:
    return "|".join(PRIMITIVE_TYPES[name] for name in parts)


def fit_affine(transcript: list[dict[str, Any]]) -> dict[str, Any] | None:
    xs: list[int] = []
    ys: list[int] = []
    for row in transcript:
        action = row["action"]
        if action in ACT_INPUTS:
            xs.append(int(ACT_INPUTS[action]))
            ys.append(int(row["observation"]))
        elif action == "MEASURE":
            xs.append(0)
            ys.append(int(row["observation"]))
    if len(set(zip(xs, ys))) < 2:
        return None
    pairs = list(zip(xs, ys))
    if len({x for x, _y in pairs}) < 2:
        return None
    for a in range(-4, 5):
        for b in range(-8, 9):
            if all(a * x + b == y for x, y in pairs):
                return dict(kind="affine", a=a, b=b, origin="model_fit")
    return None


def affine_predict(model: dict[str, Any], action: str) -> int | None:
    if action == "RESET":
        return None
    x = 0 if action == "MEASURE" else ACT_INPUTS[action]
    return int(model["a"]) * int(x) + int(model["b"])
