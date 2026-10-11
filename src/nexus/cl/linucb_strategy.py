"""Disjoint LinUCB over adaptation arms. Not meta-RL."""

from __future__ import annotations

from typing import Any

import numpy as np

ARMS = (
    "reuse",
    "conservative_low_lr",
    "encoder_new_heads_finetune",
    "frozen_encoder_new_heads",
    "scratch",
)


class StrategyLinUCB:
    def __init__(self, dim: int = 5, alpha: float = 0.75, arms: tuple[str, ...] = ARMS) -> None:
        self.dim = dim
        self.alpha = alpha
        self.arms = arms
        self.A = {a: np.eye(dim, dtype=np.float64) for a in arms}
        self.b = {a: np.zeros(dim, dtype=np.float64) for a in arms}

    def features(
        self,
        *,
        source_val: float,
        zero_shot_val: float,
        zero_shot_std: float,
        rms_shift: float,
        budget_frac: float,
    ) -> np.ndarray:
        return np.array(
            [
                float(source_val) / 500.0,
                float(zero_shot_val) / 500.0,
                min(1.0, float(zero_shot_std) / 150.0),
                min(1.0, abs(float(rms_shift)) / 5.0),
                float(budget_frac),
            ],
            dtype=np.float64,
        )[: self.dim]

    def choose(self, x: np.ndarray) -> str:
        x = np.asarray(x, dtype=np.float64).reshape(-1)
        best_arm = self.arms[0]
        best_ucb = -1e18
        for a in self.arms:
            ainv = np.linalg.inv(self.A[a])
            theta = ainv @ self.b[a]
            ucb = float(theta @ x + self.alpha * np.sqrt(x @ ainv @ x))
            if ucb > best_ucb:
                best_ucb = ucb
                best_arm = a
        return best_arm

    def update(self, arm: str, x: np.ndarray, reward: float) -> None:
        x = np.asarray(x, dtype=np.float64).reshape(-1)
        r = float(np.clip(reward, 0.0, 1.0))
        self.A[arm] = self.A[arm] + np.outer(x, x)
        self.b[arm] = self.b[arm] + r * x

    def state_dict(self) -> dict[str, Any]:
        return {
            "A": {k: v.tolist() for k, v in self.A.items()},
            "b": {k: v.tolist() for k, v in self.b.items()},
            "alpha": self.alpha,
            "dim": self.dim,
            "arms": list(self.arms),
        }
