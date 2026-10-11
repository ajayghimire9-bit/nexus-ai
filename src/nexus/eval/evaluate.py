from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
import torch

from nexus.rl.actor_critic import ActorCritic
from nexus.rl.running_stats import RunningMeanStd


def evaluate_policy(
    agent: ActorCritic,
    env_id: str,
    *,
    episodes: int,
    seed: int,
    device: torch.device,
    deterministic: bool = True,
    obs_rms: RunningMeanStd | None = None,
) -> dict[str, float]:
    env = gym.make(env_id)
    returns: list[float] = []
    lengths: list[int] = []
    agent.eval()
    for ep in range(episodes):
        obs, _ = env.reset(seed=seed + ep)
        done = False
        total = 0.0
        steps = 0
        while not done:
            obs_np = np.asarray(obs, dtype=np.float32).reshape(1, -1)
            if obs_rms is not None:
                obs_np = obs_rms.normalize(obs_np)
            obs_t = torch.as_tensor(obs_np, dtype=torch.float32, device=device)
            with torch.no_grad():
                actor_x, _ = agent._features(obs_t)
                dist = agent._distribution(actor_x)
                if deterministic:
                    action = dist.probs.argmax(dim=-1) if agent.discrete else dist.mean
                else:
                    action = dist.sample()
            if agent.discrete:
                act = int(action.item())
            else:
                act = action.squeeze(0).cpu().numpy()
            obs, reward, terminated, truncated, _ = env.step(act)
            total += float(reward)
            steps += 1
            done = bool(terminated or truncated)
        returns.append(total)
        lengths.append(steps)
    env.close()
    agent.train()
    arr = np.asarray(returns, dtype=np.float64)
    return {
        "mean_return": float(arr.mean()),
        "std_return": float(arr.std(ddof=0)),
        "min_return": float(arr.min()),
        "max_return": float(arr.max()),
        "mean_length": float(np.mean(lengths)),
        "episodes": float(episodes),
    }


def random_policy_baseline(env_id: str, *, episodes: int, seed: int) -> dict[str, float]:
    env = gym.make(env_id)
    returns: list[float] = []
    for ep in range(episodes):
        obs, _ = env.reset(seed=seed + ep)
        done = False
        total = 0.0
        while not done:
            action = env.action_space.sample()
            obs, reward, terminated, truncated, _ = env.step(action)
            total += float(reward)
            done = bool(terminated or truncated)
        returns.append(total)
    env.close()
    arr = np.asarray(returns, dtype=np.float64)
    return {
        "mean_return": float(arr.mean()),
        "std_return": float(arr.std(ddof=0)),
        "episodes": float(episodes),
    }
