"""Termination heads for planning. Geometric oracle never steps the simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from nexus.world.data import TransitionDataset
from nexus.world.planning import StepModel
from nexus.world.term_metrics import termination_report

TermMode = Literal["learned", "always_live", "calibrated", "geometric"]

THETA_THRESHOLD = 12.0 * np.pi / 180.0
X_THRESHOLD = 2.4


def geometric_terminate(next_obs: np.ndarray) -> np.ndarray:
    """CartPole fail-set on predicted state. Not a simulator query."""
    o = np.asarray(next_obs, dtype=np.float64)
    o = o.reshape(1, -1) if o.ndim == 1 else o
    done = (np.abs(o[:, 0]) > X_THRESHOLD) | (np.abs(o[:, 2]) > THETA_THRESHOLD)
    return done.astype(np.float64)


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=np.float64), 1e-6, 1.0 - 1e-6)
    return np.log(p) - np.log(1.0 - p)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-z))


def fit_temperature(model: StepModel, val: TransitionDataset) -> float:
    """Val-only temperature for Brier. Not tuned on test or control returns."""
    _, p = model.step(val.obs, val.action)
    y = val.terminated.astype(np.float64)
    best_t, best_b = 1.0, 1e9
    for t in (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0):
        pc = _sigmoid(_logit(p) / t)
        b = float(np.mean((pc - y) ** 2))
        if b < best_b:
            best_b = b
            best_t = float(t)
    return best_t


@dataclass
class TermOverride:
    """Replace p_term while keeping the wrapped model's state prediction."""

    model: StepModel
    mode: TermMode
    temperature: float = 1.0
    diagnostic_oracle: bool = False

    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        nxt, p = self.model.step(obs, action)
        arr = np.asarray(nxt)
        n = 1 if arr.ndim == 1 else int(arr.shape[0])
        p = np.asarray(p, dtype=np.float64).reshape(-1)
        if p.size == 1 and n > 1:
            p = np.full(n, float(p.flat[0]))
        if self.mode == "always_live":
            p = np.zeros(n, dtype=np.float64)
        elif self.mode == "geometric":
            p = geometric_terminate(nxt)
        elif self.mode == "calibrated":
            p = _sigmoid(_logit(p) / max(self.temperature, 1e-6))
        elif self.mode == "learned":
            p = p
        else:
            raise ValueError(self.mode)
        return nxt, p


def term_metrics_for_mode(model: StepModel, ds: TransitionDataset, mode: TermMode, temperature: float = 1.0) -> dict[str, Any]:
    wrapped = TermOverride(model, mode, temperature=temperature, diagnostic_oracle=mode == "geometric")
    _, p = wrapped.step(ds.obs, ds.action)
    return {"mode": mode, "temperature": temperature, **termination_report(p, ds.terminated)}
