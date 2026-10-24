"""Executable hidden mechanisms. Answers come from the hidden function, never from the learner's prediction.

Programmer-supplied: hypothesis language, adapters, and the excluded family.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from .capability_evidence import digest

ACTIONS = (
    "ACT_0",
    "ACT_1",
    "ACT_2",
    "ACT_NEG",
    "RESET",
    "MEASURE",
    "STOP_IDENTIFY",
    "STOP_UNRESOLVED",
)
ACT_INPUTS = {"ACT_0": 0, "ACT_1": 1, "ACT_2": 2, "ACT_NEG": -1}
ORACLE_COST = {
    "ACT_0": 1, "ACT_1": 1, "ACT_2": 1, "ACT_NEG": 1, "RESET": 0, "MEASURE": 3,
    "STOP_IDENTIFY": 0, "STOP_UNRESOLVED": 0,
}
ACTION_COST = {name: (0 if name.startswith("STOP") else 1) for name in ACTIONS}
MAX_STEPS = 8
LANGUAGE = (
    "add1", "add2", "add3", "add4", "mul2", "neg",
    "count", "count2", "sum", "toggle",
    "noisy_add1",
    "add1_then_mul2", "count_then_add1",
)
EXCLUDED = ("delay", "threshold")
# Outside the hypothesis language. Source/dev use identity/const0 to
# supervise STOP_UNRESOLVED. Assessment E stays delay/threshold.
OUTSIDE_LANGUAGE = (
    "const0", "const7", "delay", "threshold",
    "abs_val", "mod3", "clip0", "prev_plus",
    "id_exact0", "mod2", "plus_prev", "add1_twin",
)


def _stateless(fn: Callable[[int], int]) -> Callable[[dict[str, Any], int, bool], int]:
    def run(state: dict[str, Any], x: int, exact: bool) -> int:
        return int(fn(x))
    return run


def _noisy_add1(state: dict[str, Any], x: int, exact: bool) -> int:
    if exact:
        return x + 1
    return int(x)


def _count(state: dict[str, Any], x: int, exact: bool) -> int:
    state["s"] = int(state.get("s") or 0) + 1
    return int(state["s"])


def _count2(state: dict[str, Any], x: int, exact: bool) -> int:
    state["s"] = int(state.get("s") or 0) + 2
    return int(state["s"])


def _sum(state: dict[str, Any], x: int, exact: bool) -> int:
    state["s"] = int(state.get("s") or 0) + int(x)
    return int(state["s"])


def _toggle(state: dict[str, Any], x: int, exact: bool) -> int:
    state["s"] = 1 - int(state.get("s") or 0)
    return int(state["s"])


def _count_then_add1(state: dict[str, Any], x: int, exact: bool) -> int:
    return _count(state, x, exact) + 1


def _delay(state: dict[str, Any], x: int, exact: bool) -> int:
    prev = int(state.get("prev") or 0)
    state["prev"] = int(x)
    return prev


def _threshold(state: dict[str, Any], x: int, exact: bool) -> int:
    return int(int(x) > 1)


def _prev_plus(state: dict[str, Any], x: int, exact: bool) -> int:
    prev = int(state.get("prev") or 0)
    state["prev"] = int(x)
    return prev + 1


def _id_exact0(state: dict[str, Any], x: int, exact: bool) -> int:
    if exact:
        return 0
    return int(x)


def _mod2(state: dict[str, Any], x: int, exact: bool) -> int:
    return int(x) % 2


def _plus_prev(state: dict[str, Any], x: int, exact: bool) -> int:
    prev = int(state.get("prev") or 0)
    state["prev"] = int(x)
    return prev + int(x)


def _add1_twin(state: dict[str, Any], x: int, exact: bool) -> int:
    return int(x) + 1


EXECUTORS: dict[str, Callable[[dict[str, Any], int, bool], int]] = {
    "add1": _stateless(lambda x: x + 1),
    "add2": _stateless(lambda x: x + 2),
    "add3": _stateless(lambda x: x + 3),
    "add4": _stateless(lambda x: x + 4),
    "mul2": _stateless(lambda x: 2 * x),
    "neg": _stateless(lambda x: -x),
    "count": _count,
    "count2": _count2,
    "sum": _sum,
    "toggle": _toggle,
    "noisy_add1": _noisy_add1,
    "add1_then_mul2": _stateless(lambda x: 2 * (x + 1)),
    "count_then_add1": _count_then_add1,
    "delay": _delay,
    "threshold": _threshold,
    "const0": _stateless(lambda x: 0),
    "const7": _stateless(lambda x: 7),
    "abs_val": _stateless(lambda x: abs(x)),
    "mod3": _stateless(lambda x: int(x) % 3),
    "clip0": _stateless(lambda x: max(int(x), 0)),
    "prev_plus": _prev_plus,
    "id_exact0": _id_exact0,
    "mod2": _mod2,
    "plus_prev": _plus_prev,
    "add1_twin": _add1_twin,
}


def blank_state(seed: int) -> dict[str, Any]:
    import random
    return dict(s=0, prev=0, rng=random.Random(seed))


def apply_hidden(name: str, state: dict[str, Any], action: str) -> dict[str, Any]:
    """Execute the named mechanism. MEASURE is exact; ACT_* may be noisy."""
    if name not in EXECUTORS:
        raise ValueError("unknown_mechanism")
    nxt = deepcopy(state)
    if "rng" in state:
        nxt["rng"] = state["rng"]
    if action == "RESET":
        nxt["s"] = 0
        nxt["prev"] = 0
        return dict(state=nxt, observation=None, oracle=0)
    if action == "MEASURE":
        y = EXECUTORS[name](nxt, 0, True)
        return dict(state=nxt, observation=int(y), oracle=ORACLE_COST["MEASURE"], exact=True)
    if action in ACT_INPUTS:
        y = EXECUTORS[name](nxt, ACT_INPUTS[action], False)
        return dict(state=nxt, observation=int(y), oracle=1, exact=False)
    raise ValueError("not_an_environment_action")


def candidate_observation(name: str, state: dict[str, Any], action: str) -> set[int] | None:
    """Predicted observation set. noisy_add1 cheap acts are a 3-set; others are singleton."""
    if name not in LANGUAGE:
        raise ValueError("not_in_language")
    if action == "RESET":
        return None
    exact = action == "MEASURE"
    x = 0 if action == "MEASURE" else ACT_INPUTS[action]
    if name == "noisy_add1" and not exact:
        return {int(x)}
    shadow = dict(s=int(state.get("s") or 0), prev=int(state.get("prev") or 0),
                  rng=None)
    return {int(EXECUTORS[name](shadow, x, True))}


def advance_candidate(name: str, state: dict[str, Any], action: str) -> dict[str, Any]:
    nxt = dict(s=int(state.get("s") or 0), prev=int(state.get("prev") or 0))
    if action == "RESET":
        return dict(s=0, prev=0)
    x = 0 if action == "MEASURE" else ACT_INPUTS[action]
    EXECUTORS[name](nxt, x, True)
    return dict(s=int(nxt.get("s") or 0), prev=int(nxt.get("prev") or 0))


def language_hash() -> str:
    return digest(list(LANGUAGE))
