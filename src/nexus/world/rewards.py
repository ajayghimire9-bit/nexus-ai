"""Task-published step rewards for planning. Not learned. Not CartPole +1 on Pendulum."""

from __future__ import annotations

import numpy as np


PENDULUM_TORQUES = (-2.0, 0.0, 2.0)
PENDULUM_THETA_COST = 1.0
PENDULUM_THDOT_COST = 0.1
PENDULUM_U_COST = 0.001


def pendulum_step_reward(
    obs: np.ndarray,
    action: np.ndarray | int,
    next_obs: np.ndarray,
    *,
    torques: tuple[float, ...] = PENDULUM_TORQUES,
) -> np.ndarray:
    """Gymnasium Pendulum-v1: cost on the *current* (theta, thdot, u) then the physics step."""
    del next_obs
    cur = np.asarray(obs, dtype=np.float64)
    if cur.ndim == 1:
        cur = cur.reshape(1, -1)
    theta = np.arctan2(cur[:, 1], cur[:, 0])
    thdot = cur[:, 2]
    act = np.asarray(action).reshape(-1).astype(np.int64)
    tq = np.asarray(torques, dtype=np.float64)
    u = tq[np.clip(act, 0, len(tq) - 1)]
    return -(PENDULUM_THETA_COST * theta**2 + PENDULUM_THDOT_COST * thdot**2 + PENDULUM_U_COST * (u**2))


def acrobot_height(obs: np.ndarray) -> np.ndarray:
    """Gymnasium tip-height proxy: -cos(theta1) - cos(theta1+theta2). Hang-down is -2."""
    cur = np.asarray(obs, dtype=np.float64)
    if cur.ndim == 1:
        cur = cur.reshape(1, -1)
    c1, s1, c2, s2 = cur[:, 0], cur[:, 1], cur[:, 2], cur[:, 3]
    return -c1 - (c1 * c2 - s1 * s2)


def acrobot_step_reward(obs: np.ndarray, action: np.ndarray | int, next_obs: np.ndarray) -> np.ndarray:
    """Frozen dense upright height of the successor. Not Gymnasium -1/step. Not Pendulum cost."""
    del obs, action
    return acrobot_height(next_obs)


def mountaincar_height(obs: np.ndarray) -> np.ndarray:
    """Frozen valley height: sin(3 * position). Bottom of the valley is -1."""
    cur = np.asarray(obs, dtype=np.float64)
    if cur.ndim == 1:
        cur = cur.reshape(1, -1)
    return np.sin(3.0 * cur[:, 0])


def mountaincar_step_reward(obs: np.ndarray, action: np.ndarray | int, next_obs: np.ndarray) -> np.ndarray:
    """Frozen dense valley height of the successor. Not Gymnasium -1/step."""
    del obs, action
    return mountaincar_height(next_obs)


def cartpole_unit_reward(obs: np.ndarray, action: np.ndarray | int, next_obs: np.ndarray) -> np.ndarray:
    n = np.asarray(next_obs).reshape(-1, next_obs.shape[-1] if np.ndim(next_obs) > 1 else 1).shape[0]
    del obs, action
    return np.ones(n, dtype=np.float64)
