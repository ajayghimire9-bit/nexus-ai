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


def tensors_compatible(a: TaskSpec, b: TaskSpec) -> bool:
    """Weight transfer requires matching obs/action tensor sizes. Not a claim of transfer."""
    return a.obs_dim == b.obs_dim and a.n_actions == b.n_actions and a.family == b.family
