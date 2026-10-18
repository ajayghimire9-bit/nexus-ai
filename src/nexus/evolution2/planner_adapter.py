"""Trusted catalogue-to-planner adapter.

Reuses ``RandomShootingMPC._score_batch``, family rewards, and the
Evolution-1 catalogue. Does not use ``mpc_for_model``. Does not change
historical lookahead modules. Not scientific dispatch.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from nexus.evolution1.catalogue import Generator, Rule, Variant, catalogue, plan_bound
from nexus.evolution2.bindings import reviewed_binding
from nexus.world.rewards import (
    acrobot_step_reward,
    mountaincar_step_reward,
    pendulum_step_reward,
)

SCIENTIFIC = False
HISTORICAL_HORIZON = 16
HISTORICAL_CANDIDATES = 16
REWARDS = {
    "pendulum_step_reward": pendulum_step_reward,
    "acrobot_step_reward": acrobot_step_reward,
    "mountaincar_step_reward": mountaincar_step_reward,
}


class AdapterError(ValueError):
    pass


class InferenceCounter:
    """Counts batched imagined states. Copied from ``planning.InferenceCounter``."""

    def __init__(self, model):
        self.model = model
        self.calls = 0
        self.states = 0

    def step(self, obs, action):
        arr = np.asarray(obs, dtype=np.float32)
        rows = arr.reshape(1, -1) if arr.ndim == 1 else arr.reshape(-1, arr.shape[-1])
        self.calls += 1
        self.states += int(rows.shape[0])
        return self.model.step(obs, action)


class FakeStepModel:
    """Deterministic linear step model. Not a world-model checkpoint."""

    def __init__(self, obs_dim: int, n_actions: int, *, scale: float = 0.01):
        if obs_dim < 1 or n_actions < 1:
            raise AdapterError("invalid_model_interface")
        self.obs_dim = int(obs_dim)
        self.n_actions = int(n_actions)
        self.scale = float(scale)
        self.uses_simulator = False

    def step(self, obs, action):
        arr = np.asarray(obs, dtype=np.float32)
        rows = arr.reshape(1, -1) if arr.ndim == 1 else arr.reshape(-1, arr.shape[-1])
        act = np.asarray(action).reshape(-1).astype(np.int64)
        if act.shape[0] == 1 and rows.shape[0] > 1:
            act = np.repeat(act, rows.shape[0])
        nxt = rows.copy()
        nxt[:, 0] = nxt[:, 0] + self.scale * (act.astype(np.float32) - (self.n_actions - 1) / 2.0)
        p = np.clip(np.abs(nxt[:, 0]) * 0.01, 0.0, 0.25)
        return nxt.astype(np.float32), p.astype(np.float64)


def iid_sequences(seed: int, n_candidates: int, horizon: int, n_actions: int) -> np.ndarray:
    """Same draw as ``prediction_control_gap.candidate_sequences``. No import of that module."""
    rng = np.random.default_rng(int(seed))
    return rng.integers(0, int(n_actions), size=(int(n_candidates), int(horizon)), dtype=np.int64)


def balanced_first_actions(n_candidates: int, n_actions: int) -> np.ndarray:
    base, rem = divmod(int(n_candidates), int(n_actions))
    first = []
    for action in range(int(n_actions)):
        first.extend([action] * (base + (1 if action < rem else 0)))
    return np.asarray(first, dtype=np.int64)


def generate_candidates(variant: Variant, n_candidates: int, n_actions: int, seed: int) -> np.ndarray:
    horizon = int(variant.horizon)
    if variant.generator is Generator.IID:
        return iid_sequences(seed, n_candidates, horizon, n_actions)
    first = balanced_first_actions(n_candidates, n_actions)
    tails = iid_sequences(seed + 1, n_candidates, max(horizon - 1, 0), n_actions)
    if horizon == 1:
        return first.reshape(-1, 1)
    return np.concatenate([first.reshape(-1, 1), tails], axis=1)


def _reward(binding):
    try:
        return REWARDS[binding.reward_symbol]
    except KeyError as exc:
        raise AdapterError("unknown_reward") from exc


def score_open_loop(model, obs, sequences, reward_fn) -> np.ndarray:
    """Cumulative-survival open-loop score. Same rule as ``RandomShootingMPC._score_batch``."""
    sequences = np.asarray(sequences, dtype=np.int64)
    n, horizon = sequences.shape
    state = np.repeat(np.asarray(obs, dtype=np.float32).reshape(1, -1), n, axis=0)
    alive = np.ones(n, dtype=np.float64)
    score = np.zeros(n, dtype=np.float64)
    begin = getattr(model, "begin_rollout", None) or getattr(getattr(model, "model", None), "begin_rollout", None)
    if begin is not None:
        begin(n)
    for t in range(horizon):
        nxt, p = model.step(state, sequences[:, t])
        p = np.clip(np.asarray(p, dtype=np.float64).reshape(n), 0.0, 1.0)
        reward = np.asarray(reward_fn(state, sequences[:, t], nxt), dtype=np.float64).reshape(n)
        score += alive * reward
        alive = alive * (1.0 - p)
        state = nxt
    return score


def successor_values(binding, model, obs, sequences, reward_fn):
    q = []
    obs = np.asarray(obs, dtype=np.float32).reshape(1, -1)
    for action in range(binding.n_actions):
        nxt, p = model.step(obs, np.asarray([action], dtype=np.int64))
        nxt = np.asarray(nxt, dtype=np.float32).reshape(1, -1)
        r = float(np.asarray(reward_fn(obs, action, nxt), dtype=np.float64).reshape(-1)[0])
        p = float(np.clip(np.asarray(p, dtype=np.float64).reshape(-1)[0], 0.0, 1.0))
        scores = score_open_loop(model, nxt, sequences, reward_fn)
        value = float(np.max(scores))
        if binding.root_survival == "ignore_root_probability":
            q.append(r + value)
        elif binding.root_survival == "multiply_root_survival":
            q.append(r + (1.0 - p) * value)
        else:
            raise AdapterError("unknown_root_survival")
    return q


@dataclass(frozen=True)
class AdapterDecision:
    action: int
    scores: tuple[float, ...]
    imagined: int
    sequences: np.ndarray
    status: str


def variant_status(family: str, variant: Variant) -> str:
    if family not in {"pendulum", "acrobot", "mountaincar", "mountaincar_continuous"}:
        return "BLOCKED_unknown_family"
    if variant.generator is Generator.BALANCED:
        return "IMPLEMENTED_adapter_DISPATCH_BLOCKED"
    return "IMPLEMENTED_catalogue_faithful"


def historical_semantics_match(variant: Variant, n_candidates: int) -> bool:
    return (
        variant.generator is Generator.IID
        and variant.horizon == HISTORICAL_HORIZON
        and int(n_candidates) == HISTORICAL_CANDIDATES
    )


def decide(family: str, variant: Variant, obs, model, *, seed: int, imagined_cap: int = 1536):
    if SCIENTIFIC:
        raise AdapterError("scientific_dispatch_blocked")
    binding = reviewed_binding(family)
    status = variant_status(family, variant)
    if status.startswith("BLOCKED"):
        raise AdapterError(status)
    bound = plan_bound(variant, binding.n_actions, imagined_cap)
    sequences = generate_candidates(variant, bound.candidates_per_root, binding.n_actions, seed)
    reward_fn = _reward(binding)
    counter = InferenceCounter(model)
    if variant.rule is Rule.FLAT:
        scores = score_open_loop(counter, obs, sequences, reward_fn)
        idx = int(np.argmax(scores))
        action = int(sequences[idx, 0])
        score_tuple = tuple(float(x) for x in scores)
    else:
        q = successor_values(binding, counter, obs, sequences, reward_fn)
        action = int(np.argmax(q))
        score_tuple = tuple(q)
    imagined = int(counter.states)
    if imagined > bound.imagined_per_decision:
        raise AdapterError("imagined_overflow")
    return AdapterDecision(action, score_tuple, imagined, sequences, status)


def compatibility_matrix(imagined_cap: int = 1536) -> list[dict]:
    rows = []
    for family in ("pendulum", "acrobot"):
        binding = reviewed_binding(family)
        for variant in catalogue():
            bound = plan_bound(variant, binding.n_actions, imagined_cap)
            rows.append(
                {
                    "family": family,
                    "rule": variant.rule.value,
                    "generator": variant.generator.value,
                    "horizon": variant.horizon,
                    "candidates": bound.candidates_per_root,
                    "declared_imagined": bound.imagined_per_decision,
                    "status": variant_status(family, variant),
                    "historical_parity": historical_semantics_match(
                        variant, HISTORICAL_CANDIDATES
                    ),
                    "root_survival": binding.root_survival,
                    "reward": binding.reward_symbol,
                    "scientific": False,
                }
            )
    return rows


def inference_microbenchmark(*, n_decisions: int = 8, seed: int = 0) -> dict:
    """Non-scientific fake-model timing. No Gymnasium, checkpoint, or ledger."""
    family = "pendulum"
    variant = Variant(Rule.SUCCESSOR, Generator.IID, 16)
    binding = reviewed_binding(family)
    model = FakeStepModel(binding.obs_dim, binding.n_actions)
    obs = np.zeros(binding.obs_dim, dtype=np.float32)
    imagined = 0
    t0 = time.perf_counter()
    for i in range(int(n_decisions)):
        decision = decide(family, variant, obs, model, seed=int(seed) + i)
        imagined += decision.imagined
    wall = time.perf_counter() - t0
    per = wall / imagined if imagined else None
    return {
        "scientific": False,
        "ledger": False,
        "gymnasium": False,
        "n_decisions": int(n_decisions),
        "imagined": imagined,
        "wall_s": wall,
        "seconds_per_imagined": per,
        "extrapolated_110592000_s": None if per is None else per * 110_592_000,
        "historical_pendulum_lookahead_s": 68.146,
        "historical_pendulum_imagined": 12_324_000,
        "historical_seconds_per_imagined": 68.146 / 12_324_000,
        "historical_extrapolated_110592000_s": 68.146 / 12_324_000 * 110_592_000,
    }
