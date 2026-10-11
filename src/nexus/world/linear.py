"""Ridge-regression dynamics. Same (s, a) → s′ interface as the MLP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from nexus.world.data import TransitionDataset


def _features(obs: np.ndarray, action: np.ndarray, n_actions: int) -> np.ndarray:
    o = np.asarray(obs, dtype=np.float64).reshape(-1, obs.shape[-1] if obs.ndim > 1 else 4)
    a = np.asarray(action, dtype=np.int64).reshape(-1)
    oh = np.zeros((o.shape[0], n_actions), dtype=np.float64)
    oh[np.arange(o.shape[0]), np.clip(a, 0, n_actions - 1)] = 1.0
    return np.concatenate([o, oh], axis=1)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -20, 20)
    return 1.0 / (1.0 + np.exp(-z))


@dataclass
class RidgeDynamics:
    W: np.ndarray
    w_term: np.ndarray
    n_actions: int
    residual: bool = True
    l2: float = 1e-2

    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        obs_dim = int(self.W.shape[0] - self.n_actions)
        o = np.asarray(obs, dtype=np.float64).reshape(-1, obs_dim)
        a = np.asarray(action, dtype=np.int64).reshape(-1)
        if a.size == 1 and o.shape[0] > 1:
            a = np.full(o.shape[0], int(a.flat[0]), dtype=np.int64)
        x = _features(o, a, self.n_actions)
        delta = x @ self.W
        nxt = (o + delta) if self.residual else delta
        p = _sigmoid(x @ self.w_term)
        return nxt.astype(np.float32), p.astype(np.float64)

    def state_meta(self) -> dict[str, Any]:
        return {"kind": "ridge_residual" if self.residual else "ridge_direct", "l2": self.l2}


def fit_ridge(train: TransitionDataset, *, l2: float = 1e-2, residual: bool = True, n_actions: int = 2) -> RidgeDynamics:
    x = _features(train.obs, train.action, n_actions)
    y_next = np.asarray(train.next_obs, dtype=np.float64)
    y = y_next - np.asarray(train.obs, dtype=np.float64) if residual else y_next
    xtx = x.T @ x + l2 * np.eye(x.shape[1])
    W = np.linalg.solve(xtx, x.T @ y)
    y_term = train.terminated.astype(np.float64) * 2.0 - 1.0
    w_term = np.linalg.solve(xtx, x.T @ y_term)
    return RidgeDynamics(W=W, w_term=w_term, n_actions=n_actions, residual=residual, l2=l2)
