"""Random-shooting MPC. Imagined rollouts use the world model only."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any, Literal, Protocol

import numpy as np

from nexus.world.dynamics import WorldModel

Objective = Literal["predicted_reward", "hand_stability", "both"]


class StepModel(Protocol):
    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]: ...


class InferenceCounter:
    """Wrap a step model and count batched state inferences."""

    def __init__(self, model: StepModel) -> None:
        self.model = model
        self.calls = 0
        self.states = 0

    @property
    def uses_simulator(self) -> bool:
        return bool(getattr(self.model, "uses_simulator", False))

    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        arr = np.asarray(obs, dtype=np.float32)
        o = arr.reshape(1, -1) if arr.ndim == 1 else arr.reshape(-1, arr.shape[-1])
        self.calls += 1
        self.states += int(o.shape[0])
        return self.model.step(obs, action)


class MeanEnsemble:
    def __init__(self, members: tuple[StepModel, ...] | list[StepModel]) -> None:
        self.members = tuple(members)
        self.last_disagreement: np.ndarray | None = None

    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        nxts, ps = [], []
        for m in self.members:
            n, p = m.step(obs, action)
            nxts.append(np.asarray(n, dtype=np.float32))
            ps.append(np.asarray(p, dtype=np.float64).reshape(-1))
        stack = np.stack(nxts, axis=0)
        self.last_disagreement = np.std(stack, axis=0).mean(axis=-1)
        return np.mean(stack, axis=0), np.mean(np.stack(ps, axis=0), axis=0)

    def disagreement(self, obs: np.ndarray, action: int | np.ndarray) -> np.ndarray:
        if self.last_disagreement is not None:
            return self.last_disagreement
        nxts = [np.asarray(m.step(obs, action)[0], dtype=np.float32) for m in self.members]
        return np.std(np.stack(nxts, axis=0), axis=0).mean(axis=-1)


@dataclass
class RandomShootingMPC:
    model: StepModel
    n_actions: int
    horizon: int = 10
    n_candidates: int = 48
    seed: int = 0
    uncertainty_penalty: float = 0.0
    ensemble: tuple[WorldModel, ...] | tuple[StepModel, ...] | None = None
    max_plan_ms: float = 50.0
    enforce_time_budget: bool = True
    chunk_size: int = 4
    objective: Objective = "predicted_reward"
    stability_weight: float = 1.0
    step_reward: Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray] | None = field(default=None, repr=False)
    inference: InferenceCounter | None = field(default=None, repr=False)
    _rng: np.random.Generator = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.reset_episode(int(self.seed))
        self.last_seqs: np.ndarray | None = None

    def reset_episode(self, seed: int | None = None) -> None:
        """Re-seed the persistent planner RNG (call at episode start)."""
        self._rng = np.random.default_rng(int(self.seed if seed is None else seed))
        self.last_seqs = None

    def _score_batch(self, obs: np.ndarray, seqs: np.ndarray) -> np.ndarray:
        """Cumulative survival: rewards after predicted termination are unreachable."""
        n, h = seqs.shape
        s = np.repeat(np.asarray(obs, dtype=np.float32).reshape(1, -1), n, axis=0)
        alive = np.ones(n, dtype=np.float64)
        score = np.zeros(n, dtype=np.float64)
        model = self.inference if self.inference is not None else self.model
        for t in range(h):
            nxt, p = model.step(s, seqs[:, t])
            p = np.clip(np.asarray(p, dtype=np.float64).reshape(n), 0.0, 1.0)
            if self.step_reward is not None:
                r = np.asarray(self.step_reward(s, seqs[:, t], nxt), dtype=np.float64).reshape(n)
                hand = 0.0
            else:
                predicted_env_reward = 1.0
                hand = 0.0
                if self.objective in ("hand_stability", "both"):
                    theta = nxt[:, 2]
                    omega = nxt[:, 3]
                    hand = -self.stability_weight * (np.abs(theta) + 0.25 * np.abs(omega))
                r = predicted_env_reward if self.objective in ("predicted_reward", "both") else 0.0
            score += alive * (r + hand)
            if self.uncertainty_penalty > 0:
                inner = self.model
                if isinstance(inner, InferenceCounter):
                    inner = inner.model
                cached = getattr(inner, "last_disagreement", None)
                if cached is not None:
                    dis = np.asarray(cached, dtype=np.float64).reshape(n)
                elif self.ensemble is not None:
                    members = []
                    for m in self.ensemble:
                        pn, _ = m.step(s, seqs[:, t])
                        members.append(np.asarray(pn, dtype=np.float32))
                        if self.inference is not None:
                            self.inference.calls += 1
                            self.inference.states += n
                    dis = np.std(np.stack(members, axis=0), axis=0).mean(axis=-1)
                else:
                    dis = np.zeros(n, dtype=np.float64)
                score -= self.uncertainty_penalty * alive * dis
            alive = alive * (1.0 - p)
            s = nxt
        return score

    def act(self, obs: np.ndarray) -> tuple[int, dict[str, Any]]:
        t0 = time.perf_counter()
        n_cand = int(self.n_candidates)
        seqs = self._rng.integers(0, self.n_actions, size=(n_cand, int(self.horizon)))
        self.last_seqs = np.asarray(seqs)
        chunk = max(1, int(self.chunk_size))
        scored_scores: list[np.ndarray] = []
        n_scored = 0
        budget_hit = False
        for i in range(0, n_cand, chunk):
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if self.enforce_time_budget and n_scored > 0 and elapsed_ms > self.max_plan_ms:
                budget_hit = True
                break
            batch = seqs[i : i + chunk]
            scored_scores.append(self._score_batch(obs, batch))
            n_scored += batch.shape[0]
        scores = np.concatenate(scored_scores, axis=0)
        best = int(np.argmax(scores))
        action = int(seqs[best, 0])
        ms = (time.perf_counter() - t0) * 1000.0
        inf = self.inference
        return action, {
            "plan_ms": ms,
            "n_candidates": n_cand,
            "n_scored": n_scored,
            "horizon": int(self.horizon),
            "best_score": float(scores[best]),
            "over_time_budget": bool(ms > self.max_plan_ms),
            "time_budget_enforced": bool(self.enforce_time_budget and budget_hit),
            "used_simulator": bool(
                getattr(self.model, "uses_simulator", False)
                or getattr(getattr(self.inference, "model", None), "uses_simulator", False)
            ),
            "objective": self.objective,
            "uncertainty_penalty": float(self.uncertainty_penalty),
            "model_calls": 0 if inf is None else inf.calls,
            "model_states": 0 if inf is None else inf.states,
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
