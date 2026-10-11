from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import gymnasium as gym
import numpy as np


@dataclass(frozen=True)
class TaskSpec:
    """Reusable task identity. Compatible tasks share obs/action semantics.

    CartPole-v1 and Acrobot-v1 are *not* compatible: 4 vs 6 observations,
    2 vs 3 discrete actions, different dynamics. Do not transfer their states.
    """

    task_id: str
    family: str
    gym_id: str
    obs_dim: int
    n_actions: int
    params: dict[str, float] = field(default_factory=dict)
    reward_scale: float = 1.0
    reward_offset: float = 0.0
    train_split: str = "train"
    notes: str = ""

    def normalized_reward(self, raw: float) -> float:
        return (float(raw) + self.reward_offset) * self.reward_scale

    def compatible_with(self, other: "TaskSpec") -> bool:
        return (
            self.family == other.family
            and self.obs_dim == other.obs_dim
            and self.n_actions == other.n_actions
            and self.gym_id == other.gym_id
        )


# Gymnasium 1.4 CartPoleEnv caches these at __init__. Changing mass/length
# without recomputing them leaves the Euler step on the default pole.
CARTPOLE_PHYSICS_VERSION = "cartpole_derived_v1"
CARTPOLE_PHYSICS_VERSION_LEGACY = "cartpole_setattr_only"


def sync_cartpole_derived(inner: Any) -> None:
    """Recompute CartPole quantities that Gymnasium derives in ``__init__``."""
    if hasattr(inner, "masscart") and hasattr(inner, "masspole"):
        inner.total_mass = inner.masscart + inner.masspole
    if hasattr(inner, "masspole") and hasattr(inner, "length"):
        inner.polemass_length = inner.masspole * inner.length


def apply_params(env: gym.Env, spec: TaskSpec) -> gym.Env:
    inner = env.unwrapped
    for key, value in spec.params.items():
        if not hasattr(inner, key):
            raise AttributeError(f"{spec.gym_id} has no attribute {key}")
        setattr(inner, key, value)
    if spec.family == "cartpole" or str(spec.gym_id).startswith("CartPole"):
        sync_cartpole_derived(inner)
    return env


def make_task_env(spec: TaskSpec, *, seed: int | None = None, render_mode: str | None = None) -> gym.Env:
    env = gym.make(spec.gym_id, render_mode=render_mode)
    apply_params(env, spec)
    if seed is not None:
        env.reset(seed=seed)
        env.action_space.seed(seed)
    return env


def task_env_fns(spec: TaskSpec, n_envs: int, seed: int) -> list[Callable[[], gym.Env]]:
    def _make(i: int) -> Callable[[], gym.Env]:
        def thunk() -> gym.Env:
            return make_task_env(spec, seed=seed + i)

        return thunk

    return [_make(i) for i in range(n_envs)]


def encode_obs(obs: np.ndarray, spec: TaskSpec) -> np.ndarray:
    """Identity encoder for Box observations in a compatible family."""
    arr = np.asarray(obs, dtype=np.float32).reshape(-1)
    if arr.size != spec.obs_dim:
        raise ValueError(f"obs dim {arr.size} != {spec.obs_dim} for {spec.task_id}")
    return arr
