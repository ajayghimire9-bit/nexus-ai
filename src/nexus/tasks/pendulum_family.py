"""Pendulum-v1 family. Discrete torque interface frozen before confirmation."""

from __future__ import annotations

from nexus.tasks.spec import TaskSpec
from nexus.world.rewards import PENDULUM_TORQUES

PENDULUM_OBS_DIM = 3
PENDULUM_N_ACTIONS = 3
PENDULUM_MAX_STEPS = 200
# Frozen before any confirmation return. Gymnasium default max_torque is 2.0.
PENDULUM_TORQUE_NEG, PENDULUM_TORQUE_ZERO, PENDULUM_TORQUE_POS = PENDULUM_TORQUES


def pendulum_default() -> TaskSpec:
    return TaskSpec(
        task_id="pendulum_default",
        family="pendulum",
        gym_id="Pendulum-v1",
        obs_dim=PENDULUM_OBS_DIM,
        n_actions=PENDULUM_N_ACTIONS,
        params={
            "torque_neg": float(PENDULUM_TORQUE_NEG),
            "torque_zero": float(PENDULUM_TORQUE_ZERO),
            "torque_pos": float(PENDULUM_TORQUE_POS),
        },
        train_split="confirm_pendulum",
        notes=(
            "Pendulum-v1 with 3 fixed torques {-2,0,+2}. Uses Gymnasium published reward. "
            "Discretization frozen before confirmation. Not CartPole reward."
        ),
    )


def pendulum_development() -> TaskSpec:
    """Default Gymnasium physics. Horizon selection only. Not confirmation."""
    t = pendulum_default()
    return TaskSpec(
        task_id="pendulum_v089_dev",
        family=t.family,
        gym_id=t.gym_id,
        obs_dim=t.obs_dim,
        n_actions=t.n_actions,
        params=dict(t.params),
        train_split="dev_pendulum",
        notes="Development physics (default g=10). Horizon/search selection only.",
    )


def pendulum_confirmation_targets() -> tuple[TaskSpec, ...]:
    """Frozen before ranking. Unused in the H=3 cross-environment confirm."""
    return (
        TaskSpec(
            task_id="pendulum_v089g_c0",
            family="pendulum",
            gym_id="Pendulum-v1",
            obs_dim=PENDULUM_OBS_DIM,
            n_actions=PENDULUM_N_ACTIONS,
            params={
                "torque_neg": float(PENDULUM_TORQUE_NEG),
                "torque_zero": float(PENDULUM_TORQUE_ZERO),
                "torque_pos": float(PENDULUM_TORQUE_POS),
                "g": 8.3,
            },
            train_split="confirm_pendulum_g",
            notes="Confirmation g=8.3. Frozen before horizon ranking.",
        ),
        TaskSpec(
            task_id="pendulum_v089g_c1",
            family="pendulum",
            gym_id="Pendulum-v1",
            obs_dim=PENDULUM_OBS_DIM,
            n_actions=PENDULUM_N_ACTIONS,
            params={
                "torque_neg": float(PENDULUM_TORQUE_NEG),
                "torque_zero": float(PENDULUM_TORQUE_ZERO),
                "torque_pos": float(PENDULUM_TORQUE_POS),
                "g": 12.1,
            },
            train_split="confirm_pendulum_g",
            notes="Confirmation g=12.1. Frozen before horizon ranking.",
        ),
    )


# Gymnasium Pendulum-v1 defaults. Frozen before this transfer confirm.
PENDULUM_SOURCE_G = 10.0
PENDULUM_SOURCE_M = 1.0
PENDULUM_SOURCE_L = 1.0
PENDULUM_PLAN_HORIZON = 16
PENDULUM_PLAN_CANDIDATES = 16


def _pendulum(task_id: str, split: str, notes: str, *, g: float, m: float, l: float) -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        family="pendulum",
        gym_id="Pendulum-v1",
        obs_dim=PENDULUM_OBS_DIM,
        n_actions=PENDULUM_N_ACTIONS,
        params={
            "torque_neg": float(PENDULUM_TORQUE_NEG),
            "torque_zero": float(PENDULUM_TORQUE_ZERO),
            "torque_pos": float(PENDULUM_TORQUE_POS),
            "g": float(g),
            "m": float(m),
            "l": float(l),
        },
        train_split=split,
        notes=notes,
    )


def pendulum_source() -> TaskSpec:
    return _pendulum(
        "pendulum_source",
        "source_pendulum",
        "Default Gymnasium physics (g=10, m=1, l=1). Source pretrain only.",
        g=PENDULUM_SOURCE_G,
        m=PENDULUM_SOURCE_M,
        l=PENDULUM_SOURCE_L,
    )


def pendulum_transfer_development() -> TaskSpec:
    """Unseen vs source; unused as a confirmation ranking set."""
    return _pendulum(
        "pendulum_xfer_dev_g",
        "dev_pendulum_xfer",
        "Development gravity shift g=11.5. Detector/sanity only.",
        g=11.5,
        m=PENDULUM_SOURCE_M,
        l=PENDULUM_SOURCE_L,
    )


def pendulum_transfer_confirmation() -> tuple[TaskSpec, ...]:
    """Frozen before any confirm returns. Distinct from horizon-diagnostic g=8.3/12.1."""
    return (
        _pendulum("pendulum_xfer_c_g", "confirm_pendulum_xfer", "Confirm gravity g=6.5.", g=6.5, m=1.0, l=1.0),
        _pendulum("pendulum_xfer_c_m", "confirm_pendulum_xfer", "Confirm mass m=1.8.", g=10.0, m=1.8, l=1.0),
        _pendulum("pendulum_xfer_c_l", "confirm_pendulum_xfer", "Confirm length l=1.45.", g=10.0, m=1.0, l=1.45),
    )


def pendulum_transfer_sequence() -> tuple[TaskSpec, TaskSpec, TaskSpec, TaskSpec]:
    """A,B,C then held-out D. Frozen before confirmation. Not the confirm gravity/mass/length cells."""
    a = _pendulum("pendulum_xfer_A", "seq_pendulum_xfer", "Sequence A: g=9.0.", g=9.0, m=1.0, l=1.0)
    b = _pendulum("pendulum_xfer_B", "seq_pendulum_xfer", "Sequence B: m=0.55.", g=10.0, m=0.55, l=1.0)
    c = _pendulum("pendulum_xfer_C", "seq_pendulum_xfer", "Sequence C: l=0.65.", g=10.0, m=1.0, l=0.65)
    d = _pendulum("pendulum_xfer_D", "seq_pendulum_xfer", "Held-out D: g=13.5, m=1.35, l=1.25.", g=13.5, m=1.35, l=1.25)
    return a, b, c, d


def pendulum_physics_key(spec: TaskSpec) -> tuple[float, float, float]:
    p = spec.params
    return (float(p.get("g", PENDULUM_SOURCE_G)), float(p.get("m", PENDULUM_SOURCE_M)), float(p.get("l", PENDULUM_SOURCE_L)))


def tensors_compatible(a: TaskSpec, b: TaskSpec) -> bool:
    """Weight transfer requires matching obs/action tensor sizes. Not a claim of transfer."""
    return a.obs_dim == b.obs_dim and a.n_actions == b.n_actions and a.family == b.family
