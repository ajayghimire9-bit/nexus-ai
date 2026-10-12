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


def tensors_compatible(a: TaskSpec, b: TaskSpec) -> bool:
    """Weight transfer requires matching obs/action tensor sizes. Not a claim of transfer."""
    return a.obs_dim == b.obs_dim and a.n_actions == b.n_actions and a.family == b.family
