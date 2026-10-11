from __future__ import annotations

from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec

# All members wrap CartPole-v1: obs_dim=4, n_actions=2. Physics knobs change
# the *same* state representation. This is not Acrobot and is not cross-family.


def _cartpole(task_id: str, split: str, notes: str, **params: float) -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        family="cartpole",
        gym_id="CartPole-v1",
        obs_dim=4,
        n_actions=2,
        params=params,
        reward_scale=1.0 / 500.0,
        train_split=split,
        notes=notes,
    )


CARTPOLE_FAMILY: dict[str, TaskSpec] = {
    "cartpole_default": _cartpole(
        "cartpole_default", "source", "Source training task.", gravity=9.8, length=0.5, masspole=0.1
    ),
    "cartpole_long": _cartpole(
        "cartpole_long", "source", "V0.6 sequential source variant.", gravity=9.8, length=0.8, masspole=0.1
    ),
    "cartpole_heavy": _cartpole(
        "cartpole_heavy", "source", "V0.6 sequential source variant.", gravity=9.8, length=0.5, masspole=0.3
    ),
    "cartpole_lowg": _cartpole(
        "cartpole_lowg",
        "dev",
        "Development held-out (used in V0.6.2). Selector may use val here; not a V0.6.3 final test.",
        gravity=4.9,
        length=0.5,
        masspole=0.1,
    ),
    "cartpole_short": _cartpole(
        "cartpole_short", "test", "Untouched final test: shorter pole.", gravity=9.8, length=0.3, masspole=0.1
    ),
    "cartpole_highg": _cartpole(
        "cartpole_highg", "test", "Untouched final test: higher gravity.", gravity=14.7, length=0.5, masspole=0.1
    ),
    "cartpole_longheavy": _cartpole(
        "cartpole_longheavy",
        "test",
        "Untouched final test: long and heavy pole.",
        gravity=9.8,
        length=0.8,
        masspole=0.3,
    ),
}


def source_tasks() -> tuple[TaskSpec, TaskSpec, TaskSpec]:
    return (
        CARTPOLE_FAMILY["cartpole_default"],
        CARTPOLE_FAMILY["cartpole_long"],
        CARTPOLE_FAMILY["cartpole_heavy"],
    )


def heldout_task() -> TaskSpec:
    return CARTPOLE_FAMILY["cartpole_lowg"]


def source_policy_task() -> TaskSpec:
    return CARTPOLE_FAMILY["cartpole_default"]


def development_targets() -> tuple[TaskSpec, ...]:
    return (CARTPOLE_FAMILY["cartpole_lowg"],)


def final_test_targets() -> tuple[TaskSpec, ...]:
    """V0.6.3 finals. V0.6.4 treats these as development (already examined)."""
    return (
        CARTPOLE_FAMILY["cartpole_short"],
        CARTPOLE_FAMILY["cartpole_highg"],
        CARTPOLE_FAMILY["cartpole_longheavy"],
    )


def v064_development_targets() -> tuple[TaskSpec, ...]:
    return (CARTPOLE_FAMILY["cartpole_lowg"],) + final_test_targets()


# Frozen 2026-10-11. Do not edit after inspecting confirmation outcomes.
_CONFIRMATION_RULE = {
    "generator": "base_plus_frozen_offsets",
    "physics_version": CARTPOLE_PHYSICS_VERSION,
    "base": {"gravity": 9.8, "length": 0.5, "masspole": 0.1},
    "offsets": (
        {"gravity": -2.3, "length": 0.15, "masspole": 0.08},
        {"gravity": 3.2, "length": -0.12, "masspole": 0.12},
        {"gravity": 0.0, "length": 0.22, "masspole": -0.04},
    ),
}


def confirmation_generation_rule() -> dict:
    return {
        "generator": _CONFIRMATION_RULE["generator"],
        "physics_version": _CONFIRMATION_RULE["physics_version"],
        "base": dict(_CONFIRMATION_RULE["base"]),
        "offsets": [dict(o) for o in _CONFIRMATION_RULE["offsets"]],
    }


def confirmation_targets() -> tuple[TaskSpec, ...]:
    """Pre-registered V0.6.4 confirmation suite. Not used to tune the selector."""
    out: list[TaskSpec] = []
    base = _CONFIRMATION_RULE["base"]
    for i, off in enumerate(_CONFIRMATION_RULE["offsets"]):
        params = {k: float(base[k]) + float(off[k]) for k in base}
        tid = f"cartpole_confirm_{i}"
        out.append(
            _cartpole(
                tid,
                "confirm",
                f"Frozen confirmation offset {i}; physics {CARTPOLE_PHYSICS_VERSION}.",
                **params,
            )
        )
    return tuple(out)
