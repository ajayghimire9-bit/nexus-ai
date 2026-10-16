"""Observation-noise and action-delay wrappers. Obs/action dims are unchanged."""

from __future__ import annotations

import gymnasium as gym
import numpy as np

# Not Gymnasium CartPoleEnv attributes. Applied after native physics setattr.
WRAPPER_PARAM_KEYS = frozenset({"obs_noise_std", "action_delay", "torque_neg", "torque_zero", "torque_pos"})


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


class DiscreteTorqueWrapper(gym.ActionWrapper):
    """Map a discrete index to a 1-D torque. Pendulum published reward still uses the real u."""

    def __init__(self, env: gym.Env, torques: tuple[float, ...] | list[float]) -> None:
        super().__init__(env)
        self.torques = np.asarray(list(torques), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(int(self.torques.size))

    def action(self, action):  # type: ignore[no-untyped-def]
        u = float(self.torques[int(action)])
        return np.asarray([u], dtype=np.float32)


class AcrobotDenseRewardWrapper(gym.Wrapper):
    """Replace Gymnasium -1/step with frozen upright height. Goal does not terminate."""

    def step(self, action):  # type: ignore[no-untyped-def]
        obs, gym_r, terminated, truncated, info = self.env.step(action)
        arr = np.asarray(obs, dtype=np.float64).reshape(-1)
        height = float(-arr[0] - (arr[0] * arr[2] - arr[1] * arr[3]))
        info = dict(info or {})
        info["gym_reward"] = float(gym_r)
        info["gym_terminated"] = bool(terminated)
        return obs, height, False, truncated, info


class ContinuousMountainCarGravityPatch(gym.Wrapper):
    """Replace hardcoded 0.0025 gravity in MountainCarContinuous-v0.

    Native ``step`` is patched on the unwrapped env so TimeLimit still counts.
    Discrete torque mapping and dense height are applied by outer wrappers.
    """

    def __init__(self, env: gym.Env, gravity: float) -> None:
        super().__init__(env)
        inner = env.unwrapped
        inner.gravity = float(gravity)
        if getattr(inner, "_nexus_mcc_gravity_patched", False):
            return
        import math

        def step(action):  # type: ignore[no-untyped-def]
            position = inner.state[0]
            velocity = inner.state[1]
            force = min(max(float(np.asarray(action).reshape(-1)[0]), inner.min_action), inner.max_action)
            velocity += force * inner.power - float(inner.gravity) * math.cos(3 * position)
            if velocity > inner.max_speed:
                velocity = inner.max_speed
            if velocity < -inner.max_speed:
                velocity = -inner.max_speed
            position += velocity
            if position > inner.max_position:
                position = inner.max_position
            if position < inner.min_position:
                position = inner.min_position
            if position == inner.min_position and velocity < 0:
                velocity = 0
            terminated = bool(position >= inner.goal_position and velocity >= inner.goal_velocity)
            reward = 0.0
            if terminated:
                reward = 100.0
            reward -= float(force) ** 2 * 0.1
            inner.state = np.array([position, velocity], dtype=np.float32)
            if inner.render_mode == "human":
                inner.render()
            return inner.state, reward, terminated, False, {}

        inner.step = step  # type: ignore[method-assign]
        inner._nexus_mcc_gravity_patched = True


class MountainCarDenseRewardWrapper(gym.Wrapper):
    """Replace Gymnasium -1/step with frozen valley height. Goal does not terminate."""

    def step(self, action):  # type: ignore[no-untyped-def]
        obs, gym_r, terminated, truncated, info = self.env.step(action)
        arr = np.asarray(obs, dtype=np.float64).reshape(-1)
        height = float(np.sin(3.0 * arr[0]))
        info = dict(info or {})
        info["gym_reward"] = float(gym_r)
        info["gym_terminated"] = bool(terminated)
        return obs, height, False, truncated, info
