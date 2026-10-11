"""Random-shooting MPC. Imagined rollouts use the world model only."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from nexus.world.dynamics import WorldModel


class StepModel(Protocol):
    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]: ...


@dataclass
class RandomShootingMPC:
    model: StepModel
    n_actions: int
    horizon: int = 10
    n_candidates: int = 48
    seed: int = 0
    uncertainty_penalty: float = 0.0
    ensemble: tuple[WorldModel, ...] | None = None
    max_plan_ms: float = 50.0

    def _score_batch(self, obs: np.ndarray, seqs: np.ndarray) -> np.ndarray:
        """seqs: (N, H) int. Returns scores (N,). Never steps a Gym env."""
        n, h = seqs.shape
        s = np.repeat(np.asarray(obs, dtype=np.float32).reshape(1, -1), n, axis=0)
        score = np.zeros(n, dtype=np.float64)
        for t in range(h):
            nxt, p = self.model.step(s, seqs[:, t])
            p = np.asarray(p, dtype=np.float64).reshape(n)
            theta = nxt[:, 2]
            x = nxt[:, 0]
            survive = 1.0 - p
            score += survive * (1.0 - 0.1 * np.square(theta) - 0.01 * np.square(x))
            if self.ensemble and self.uncertainty_penalty > 0:
                members = []
                for m in self.ensemble:
                    pn, _ = m.step(s, seqs[:, t])
                    members.append(pn)
                dis = np.std(np.stack(members, axis=0), axis=0).mean(axis=-1)
                score -= self.uncertainty_penalty * dis
            s = nxt
            # if predicted dead, stop accumulating
            score -= 5.0 * p
        return score

    def act(self, obs: np.ndarray) -> tuple[int, dict[str, Any]]:
        t0 = time.perf_counter()
        rng = np.random.default_rng(self.seed + int(np.abs(obs).sum() * 1e6) % 10_000)
        n_cand = int(self.n_candidates)
        seqs = rng.integers(0, self.n_actions, size=(n_cand, int(self.horizon)))
        scores = self._score_batch(obs, seqs)
        best = int(np.argmax(scores))
        action = int(seqs[best, 0])
        ms = (time.perf_counter() - t0) * 1000.0
        if ms > self.max_plan_ms and n_cand > 8:
            # recorded over-budget; still return the computed action
            over = True
        else:
            over = False
        return action, {
            "plan_ms": ms,
            "n_candidates": n_cand,
            "horizon": int(self.horizon),
            "best_score": float(scores[best]),
            "over_time_budget": over,
            "used_simulator": False,
        }


def one_step_greedy(model: StepModel, obs: np.ndarray, n_actions: int) -> int:
    """No multi-step planning: pick the action with lowest predicted |theta'|."""
    best_a = 0
    best = 1e9
    o = np.asarray(obs, dtype=np.float32).reshape(-1)
    for a in range(n_actions):
        nxt, p = model.step(o, a)
        cost = float(np.abs(nxt.reshape(-1)[2]) + 0.25 * np.abs(nxt.reshape(-1)[3]) + 2.0 * float(np.asarray(p).reshape(-1)[0]))
        if cost < best:
            best = cost
            best_a = a
    return best_a
