"""Observation-noise and action-delay wrappers. Obs/action dims are unchanged."""

from __future__ import annotations

import gymnasium as gym
import numpy as np

# Not Gymnasium CartPoleEnv attributes. Applied after native physics setattr.
WRAPPER_PARAM_KEYS = frozenset({"obs_noise_std", "action_delay"})


class ObservationNoiseWrapper(gym.ObservationWrapper):
    def __init__(self, env: gym.Env, std: float, *, seed: int = 0) -> None:
        super().__init__(env)
        self.std = float(std)
        self._rng = np.random.default_rng(int(seed))

    def observation(self, observation):  # type: ignore[no-untyped-def]
        arr = np.asarray(observation, dtype=np.float32)
        if self.std <= 0:
            return arr
        return (arr + self._rng.normal(0.0, self.std, size=arr.shape)).astype(np.float32)


class ActionDelayWrapper(gym.Wrapper):
    """Delay 1 applies the previous action. Observation stays 4-D (POMDP)."""

    def __init__(self, env: gym.Env, delay: int) -> None:
        super().__init__(env)
        self.delay = int(delay)
        self._pending = 0

    def reset(self, **kwargs):  # type: ignore[no-untyped-def]
        self._pending = 0
        return self.env.reset(**kwargs)

    def step(self, action):  # type: ignore[no-untyped-def]
        if self.delay <= 0:
            return self.env.step(action)
        applied = int(self._pending)
        self._pending = int(action)
        return self.env.step(applied)
