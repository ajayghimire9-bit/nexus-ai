"""Opt-in batched successor search; historical experiment runners stay unchanged.

Only row-independent, deterministic step models are supported. This is the same
771-transition computation, not a cheaper approximate successor value. Float32
batch-size changes need numerical parity checks before controller deployment.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from nexus.world.context_model import ContextWorldModel
from nexus.world.dynamics import WorldModel
from nexus.world.rewards import (
    acrobot_step_reward, mountaincar_step_reward, pendulum_step_reward,
)

Family = Literal["pendulum", "acrobot", "mountaincar"]
REWARDS = {"pendulum": pendulum_step_reward, "acrobot": acrobot_step_reward,
           "mountaincar": mountaincar_step_reward}
DIMS = {"pendulum": 3, "acrobot": 6, "mountaincar": 2}


def _check_model(model) -> None:
    # No automatic batching of GRU state, ensembles, batch statistics or wrappers
    # with unknown state semantics. Explicit capability is useful for toy models.
    if type(model) is WorldModel:
        supported = model.net.arch in ("mlp", "film") and model.net._h is None
    elif type(model) is ContextWorldModel:
        supported = True
    else:
        supported = getattr(model, "batch_independent", False) is True
    if not supported or getattr(model, "uses_simulator", False):
        raise TypeError("successor batching requires a deterministic row-independent model")


def _context(model):
    z = getattr(model, "z", None)
    if z is None:
        z = getattr(getattr(model, "net", None), "context", None)
    return None if z is None else z.detach().cpu().numpy().copy()


def _predict(model, state, actions, dim):
    nxt, p = model.step(state, actions)
    nxt = np.asarray(nxt)
    p = np.asarray(p, dtype=np.float64)
    if nxt.shape != (len(actions), dim) or p.size != len(actions):
        raise ValueError("model prediction shape changed")
    if nxt.dtype != np.float32 or not np.isfinite(nxt).all() or not np.isfinite(p).all():
        raise ValueError("finite float32 next states and finite probabilities required")
    return nxt, np.clip(p.reshape(len(actions)), 0., 1.)


@dataclass(frozen=True)
class SuccessorScores:
    q: np.ndarray
    tail_scores: np.ndarray
    successors: np.ndarray
    immediate_rewards: np.ndarray
    outer_survival: np.ndarray

    @property
    def action(self) -> int:
        # np.argmax preserves the original smallest-index tie rule.
        return int(np.argmax(self.q))


class PreparedSuccessorSearch:
    """Own immutable action-major candidates, reusable across context conditions.

    Three successor roots, sixteen candidates each. Candidate k is unchanged in
    every root. No RNG draw, prefix pruning, deduplication or warm-start cache.
    """

    def __init__(self, sequences: np.ndarray, *, family: Family):
        if family not in REWARDS:
            raise ValueError("unregistered reward/backup family")
        seq = np.asarray(sequences)
        if (seq.shape != (16, 16) or not np.issubdtype(seq.dtype, np.integer)
                or np.any((seq < 0) | (seq > 2))):
            raise ValueError("sixteen H=16 discrete three-action candidates required")
        self.family = family
        self._sequences = np.array(seq, dtype=np.int64, copy=True)
        # Time-major contiguous vectors avoid slicing/tile allocation each tick.
        self._tail_actions = np.ascontiguousarray(np.tile(self._sequences, (3, 1)).T)
        self._first_actions = np.arange(3, dtype=np.int64)
        for arr in (self._sequences, self._tail_actions, self._first_actions):
            arr.flags.writeable = False

    @property
    def sequences(self) -> np.ndarray:
        # Copy prevents a caller from re-enabling writes on owned candidate data.
        return self._sequences.copy()

    def score(self, model, obs: np.ndarray) -> SuccessorScores:
        _check_model(model)
        dim = DIMS[self.family]
        o = np.asarray(obs, dtype=np.float32)
        if o.shape not in ((dim,), (1, dim)) or not np.isfinite(o).all():
            raise ValueError("one finite observation of the registered family required")
        before = _context(model)
        roots = np.repeat(o.reshape(1, dim), 3, axis=0)
        # Writable working copies: torch.as_tensor warns on read-only NumPy input.
        # Keep these local so model adapters cannot mutate the cached candidates.
        first_actions = self._first_actions.copy()
        tail_actions = self._tail_actions.copy()
        successors, p = _predict(model, roots, first_actions, dim)
        reward = REWARDS[self.family]
        immediate = np.asarray(reward(roots, self._first_actions, successors), dtype=np.float64).reshape(3)
        # Preserve actual code, including Pendulum's ignored outer termination p.
        survival = np.ones(3) if self.family == "pendulum" else 1. - p
        state = np.repeat(successors, 16, axis=0)
        begin = getattr(model, "begin_rollout", None)
        if begin is not None:
            begin(48)
        alive = np.ones(48, dtype=np.float64)
        score = np.zeros(48, dtype=np.float64)
        for actions in tail_actions:
            nxt, term = _predict(model, state, actions, dim)
            rr = np.asarray(reward(state, actions, nxt), dtype=np.float64).reshape(48)
            score += alive * rr
            alive = alive * (1. - term)
            state = nxt
        tails = score.reshape(3, 16)
        q = immediate + survival * np.max(tails, axis=1)
        if not np.isfinite(q).all() or not np.isfinite(tails).all():
            raise ValueError("nonfinite successor scores")
        after = _context(model)
        if (before is None) != (after is None) or (before is not None and not np.array_equal(before, after)):
            raise RuntimeError("model context changed during successor scoring")
        return SuccessorScores(q, tails, successors, immediate, survival)
