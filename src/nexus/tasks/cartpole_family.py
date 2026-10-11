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


def v065_development_targets() -> tuple[TaskSpec, ...]:
    """V0.6.4 confirmation tasks: inspected, now development-only."""
    return confirmation_targets()


# Frozen 2026-10-11 for V0.6.5. Do not edit after inspecting confirmation outcomes.
_V065_CONFIRMATION_RULE = {
    "generator": "base_plus_frozen_offsets_v065",
    "physics_version": CARTPOLE_PHYSICS_VERSION,
    "base": {"gravity": 9.8, "length": 0.5, "masspole": 0.1},
    "offsets": (
        {"gravity": 1.7, "length": -0.18, "masspole": 0.05},
        {"gravity": -3.1, "length": 0.08, "masspole": -0.03},
        {"gravity": 4.4, "length": 0.25, "masspole": 0.14},
    ),
}


def v065_confirmation_rule() -> dict:
    return {
        "generator": _V065_CONFIRMATION_RULE["generator"],
        "physics_version": _V065_CONFIRMATION_RULE["physics_version"],
        "base": dict(_V065_CONFIRMATION_RULE["base"]),
        "offsets": [dict(o) for o in _V065_CONFIRMATION_RULE["offsets"]],
    }


def v065_confirmation_targets() -> tuple[TaskSpec, ...]:
    out: list[TaskSpec] = []
    base = _V065_CONFIRMATION_RULE["base"]
    for i, off in enumerate(_V065_CONFIRMATION_RULE["offsets"]):
        params = {k: float(base[k]) + float(off[k]) for k in base}
        out.append(
            _cartpole(
                f"cartpole_v065_{i}",
                "confirm_v065",
                f"V0.6.5 frozen confirmation offset {i}.",
                **params,
            )
        )
    return tuple(out)


def v066_development_targets() -> tuple[TaskSpec, ...]:
    """Previously inspected V0.6.5 confirmation tasks."""
    return v065_confirmation_targets()


_V066_CONFIRMATION_RULE = {
    "generator": "base_plus_frozen_offsets_v066",
    "physics_version": CARTPOLE_PHYSICS_VERSION,
    "base": {"gravity": 9.8, "length": 0.5, "masspole": 0.1},
    "offsets": (
        {"gravity": -1.4, "length": 0.11, "masspole": 0.07},
        {"gravity": 2.6, "length": -0.09, "masspole": 0.11},
        {"gravity": -4.0, "length": 0.28, "masspole": -0.02},
    ),
}


def v066_confirmation_rule() -> dict:
    return {
        "generator": _V066_CONFIRMATION_RULE["generator"],
        "physics_version": _V066_CONFIRMATION_RULE["physics_version"],
        "base": dict(_V066_CONFIRMATION_RULE["base"]),
        "offsets": [dict(o) for o in _V066_CONFIRMATION_RULE["offsets"]],
    }


def v066_confirmation_targets() -> tuple[TaskSpec, ...]:
    out: list[TaskSpec] = []
    base = _V066_CONFIRMATION_RULE["base"]
    for i, off in enumerate(_V066_CONFIRMATION_RULE["offsets"]):
        params = {k: float(base[k]) + float(off[k]) for k in base}
        out.append(
            _cartpole(
                f"cartpole_v066_{i}",
                "confirm_v066",
                f"V0.6.6 frozen confirmation offset {i}.",
                **params,
            )
        )
    return tuple(out)


def v08_sequence_tasks() -> tuple[TaskSpec, TaskSpec, TaskSpec]:
    """Continual A→B→C with A = source default. B/C unused in V0.6/V0.7."""
    a = CARTPOLE_FAMILY["cartpole_default"]
    b = _cartpole(
        "cartpole_v08_B",
        "dev_v08",
        "V0.8 sequence B. Unused prior physics.",
        gravity=8.05,
        length=0.54,
        masspole=0.21,
    )
    c = _cartpole(
        "cartpole_v08_C",
        "dev_v08",
        "V0.8 sequence C. Unused prior physics.",
        gravity=12.15,
        length=0.66,
        masspole=0.04,
    )
    return a, b, c


def v08_development_target() -> TaskSpec:
    """Held-out development physics for method/budget selection. Not confirmation."""
    return _cartpole(
        "cartpole_v08_dev",
        "dev_v08",
        "V0.8 development target. Selection may use this split only.",
        gravity=6.15,
        length=0.36,
        masspole=0.17,
    )


_V08_CONFIRMATION_RULE = {
    "generator": "base_plus_frozen_offsets_v08",
    "physics_version": CARTPOLE_PHYSICS_VERSION,
    "base": {"gravity": 9.8, "length": 0.5, "masspole": 0.1},
    "offsets": (
        {"gravity": -1.15, "length": -0.24, "masspole": 0.10},
        {"gravity": 1.95, "length": 0.19, "masspole": -0.045},
        {"gravity": -4.35, "length": -0.03, "masspole": 0.16},
    ),
}


def v08_confirmation_rule() -> dict:
    return {
        "generator": _V08_CONFIRMATION_RULE["generator"],
        "physics_version": _V08_CONFIRMATION_RULE["physics_version"],
        "base": dict(_V08_CONFIRMATION_RULE["base"]),
        "offsets": [dict(o) for o in _V08_CONFIRMATION_RULE["offsets"]],
    }


def v08_confirmation_targets() -> tuple[TaskSpec, ...]:
    out: list[TaskSpec] = []
    base = _V08_CONFIRMATION_RULE["base"]
    for i, off in enumerate(_V08_CONFIRMATION_RULE["offsets"]):
        params = {k: float(base[k]) + float(off[k]) for k in base}
        out.append(
            _cartpole(
                f"cartpole_v08_confirm_{i}",
                "confirm_v08",
                f"V0.8 frozen confirmation offset {i}. Not used to select methods.",
                **params,
            )
        )
    return tuple(out)


# V0.8.1 non-saturation rule (frozen before method ranking):
# compatible CartPole-v1; obs_noise_std=0.08; unused (g,L,m); length in [0.25,0.9],
# gravity in [5,16], masspole in [0.04,0.3]. Screening uses frozen H=3 only.
V081_OBS_NOISE = 0.08
V081_SCREEN_RETURN_CAP = 400.0


def v081_safety_ok(spec: TaskSpec) -> bool:
    p = spec.params
    g, length, m = float(p["gravity"]), float(p["length"]), float(p["masspole"])
    noise = float(p.get("obs_noise_std", 0.0) or 0.0)
    delay = int(p.get("action_delay", 0) or 0)
    return (
        spec.gym_id == "CartPole-v1"
        and spec.obs_dim == 4
        and spec.n_actions == 2
        and 5.0 <= g <= 16.0
        and 0.25 <= length <= 0.9
        and 0.04 <= m <= 0.3
        and 0.0 <= noise <= 0.1
        and delay in (0, 1)
    )


def v081_sequence_tasks() -> tuple[TaskSpec, TaskSpec, TaskSpec]:
    a = _cartpole(
        "cartpole_v081_A",
        "dev_v081",
        "V0.8.1 sequence A: default physics, observation noise.",
        gravity=9.8,
        length=0.5,
        masspole=0.1,
        obs_noise_std=V081_OBS_NOISE,
    )
    b = _cartpole(
        "cartpole_v081_B",
        "dev_v081",
        "V0.8.1 sequence B: unused physics, observation noise.",
        gravity=13.2,
        length=0.4,
        masspole=0.22,
        obs_noise_std=V081_OBS_NOISE,
    )
    c = _cartpole(
        "cartpole_v081_C",
        "dev_v081",
        "V0.8.1 sequence C: unused physics, observation noise.",
        gravity=7.2,
        length=0.75,
        masspole=0.08,
        obs_noise_std=V081_OBS_NOISE,
    )
    return a, b, c


def v081_development_target() -> TaskSpec:
    return _cartpole(
        "cartpole_v081_dev",
        "dev_v081",
        "V0.8.1 development target for method selection. Observation noise.",
        gravity=6.4,
        length=0.58,
        masspole=0.24,
        obs_noise_std=V081_OBS_NOISE,
    )


def v081_noise_probe() -> TaskSpec:
    return _cartpole(
        "cartpole_v081_noise",
        "dev_v081",
        "Source physics plus observation noise. Detector noise probe.",
        gravity=9.8,
        length=0.5,
        masspole=0.1,
        obs_noise_std=V081_OBS_NOISE,
    )


_V081_CONFIRMATION_RULE = {
    "generator": "obs_noise_plus_frozen_offsets_v081",
    "physics_version": CARTPOLE_PHYSICS_VERSION,
    "obs_noise_std": V081_OBS_NOISE,
    "base": {"gravity": 9.8, "length": 0.5, "masspole": 0.1},
    "offsets": (
        {"gravity": -2.8, "length": 0.14, "masspole": 0.09},
        {"gravity": 3.6, "length": -0.16, "masspole": -0.03},
        {"gravity": -1.1, "length": 0.21, "masspole": 0.12},
    ),
}


def v081_confirmation_rule() -> dict:
    return {
        "generator": _V081_CONFIRMATION_RULE["generator"],
        "physics_version": _V081_CONFIRMATION_RULE["physics_version"],
        "obs_noise_std": _V081_CONFIRMATION_RULE["obs_noise_std"],
        "base": dict(_V081_CONFIRMATION_RULE["base"]),
        "offsets": [dict(o) for o in _V081_CONFIRMATION_RULE["offsets"]],
    }


def v081_confirmation_targets() -> tuple[TaskSpec, ...]:
    out: list[TaskSpec] = []
    base = _V081_CONFIRMATION_RULE["base"]
    noise = float(_V081_CONFIRMATION_RULE["obs_noise_std"])
    for i, off in enumerate(_V081_CONFIRMATION_RULE["offsets"]):
        params = {k: float(base[k]) + float(off[k]) for k in base}
        out.append(
            _cartpole(
                f"cartpole_v081_confirm_{i}",
                "confirm_v081",
                f"V0.8.1 frozen confirmation offset {i}. obs_noise={noise}. Not used to select methods.",
                obs_noise_std=noise,
                **params,
            )
        )
    return tuple(out)


V082_OBS_NOISE = 0.10


def v082_safety_ok(spec: TaskSpec) -> bool:
    p = spec.params
    g, length, m = float(p["gravity"]), float(p["length"]), float(p["masspole"])
    noise = float(p.get("obs_noise_std", 0.0) or 0.0)
    return (
        spec.gym_id == "CartPole-v1"
        and spec.obs_dim == 4
        and spec.n_actions == 2
        and 5.0 <= g <= 16.0
        and 0.25 <= length <= 0.9
        and 0.04 <= m <= 0.3
        and 0.0 <= noise <= 0.12
    )


def v082_development_target() -> TaskSpec:
    return _cartpole(
        "cartpole_v082_dev",
        "dev_v082",
        "V0.8.2 development. Noise 0.10, unused physics. Selection only.",
        gravity=10.4,
        length=0.37,
        masspole=0.23,
        obs_noise_std=V082_OBS_NOISE,
    )


def v082_sequence_tasks() -> tuple[TaskSpec, TaskSpec, TaskSpec]:
    a = _cartpole(
        "cartpole_v082_A",
        "dev_v082",
        "V0.8.2 sequence A.",
        gravity=9.8,
        length=0.5,
        masspole=0.1,
        obs_noise_std=V082_OBS_NOISE,
    )
    b = _cartpole(
        "cartpole_v082_B",
        "dev_v082",
        "V0.8.2 sequence B.",
        gravity=14.1,
        length=0.31,
        masspole=0.16,
        obs_noise_std=V082_OBS_NOISE,
    )
    c = _cartpole(
        "cartpole_v082_C",
        "dev_v082",
        "V0.8.2 sequence C.",
        gravity=6.1,
        length=0.73,
        masspole=0.21,
        obs_noise_std=V082_OBS_NOISE,
    )
    return a, b, c


_V082_NOISY_CONFIRM = (
    {"gravity": 1.4, "length": 0.11, "masspole": 0.04},
    {"gravity": -3.3, "length": -0.17, "masspole": 0.08},
)
_V082_CLEAN_CONFIRM = ({"gravity": 2.1, "length": -0.19, "masspole": 0.07},)


def v082_confirmation_targets() -> tuple[TaskSpec, ...]:
    """Frozen before method ranking. Mix of noisy (estimation) and clean (transfer)."""
    base = {"gravity": 9.8, "length": 0.5, "masspole": 0.1}
    out: list[TaskSpec] = []
    for i, off in enumerate(_V082_NOISY_CONFIRM):
        params = {k: float(base[k]) + float(off[k]) for k in base}
        out.append(
            _cartpole(
                f"cartpole_v082_noisy_{i}",
                "confirm_v082",
                f"V0.8.2 noisy confirmation {i}. Not used to select.",
                obs_noise_std=V082_OBS_NOISE,
                **params,
            )
        )
    for i, off in enumerate(_V082_CLEAN_CONFIRM):
        params = {k: float(base[k]) + float(off[k]) for k in base}
        out.append(
            _cartpole(
                f"cartpole_v082_clean_{i}",
                "confirm_v082",
                f"V0.8.2 clean confirmation {i}. Not used to select.",
                **params,
            )
        )
    return tuple(out)


V083_OBS_NOISE = 0.09


def v083_development_target() -> TaskSpec:
    return _cartpole(
        "cartpole_v083_dev",
        "dev_v083",
        "V0.8.3 development. Gate selection only.",
        gravity=12.6,
        length=0.44,
        masspole=0.09,
        obs_noise_std=V083_OBS_NOISE,
    )


def v083_sequence_tasks() -> tuple[TaskSpec, TaskSpec, TaskSpec]:
    a = _cartpole(
        "cartpole_v083_A",
        "dev_v083",
        "V0.8.3 sequence A.",
        gravity=9.8,
        length=0.5,
        masspole=0.1,
        obs_noise_std=V083_OBS_NOISE,
    )
    b = _cartpole(
        "cartpole_v083_B",
        "dev_v083",
        "V0.8.3 sequence B.",
        gravity=5.7,
        length=0.82,
        masspole=0.13,
        obs_noise_std=V083_OBS_NOISE,
    )
    c = _cartpole(
        "cartpole_v083_C",
        "dev_v083",
        "V0.8.3 sequence C.",
        gravity=11.6,
        length=0.27,
        masspole=0.19,
        obs_noise_std=V083_OBS_NOISE,
    )
    return a, b, c


def v083_confirmation_targets() -> tuple[TaskSpec, ...]:
    """Frozen before ranking. Noisy estimation vs clean transfer."""
    return (
        _cartpole(
            "cartpole_v083_noisy_0",
            "confirm_v083",
            "V0.8.3 noisy confirm 0.",
            gravity=8.3,
            length=0.29,
            masspole=0.25,
            obs_noise_std=V083_OBS_NOISE,
        ),
        _cartpole(
            "cartpole_v083_noisy_1",
            "confirm_v083",
            "V0.8.3 noisy confirm 1.",
            gravity=14.4,
            length=0.63,
            masspole=0.12,
            obs_noise_std=V083_OBS_NOISE,
        ),
        _cartpole(
            "cartpole_v083_clean_0",
            "confirm_v083",
            "V0.8.3 clean confirm 0.",
            gravity=7.4,
            length=0.41,
            masspole=0.28,
        ),
    )


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
