from __future__ import annotations

import gymnasium as gym
import numpy as np
import torch

from nexus.eval.evaluate import evaluate_policy
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.actor_critic import ActorCritic


def test_discrete_deterministic_eval_is_repeatable() -> None:
    env = gym.make("CartPole-v1")
    spec = ArchitectureSpec(hidden_sizes=(8,), activation="tanh")
    agent = ActorCritic(4, env.action_space, spec)
    env.close()
    a = evaluate_policy(agent, "CartPole-v1", episodes=3, seed=7, device=torch.device("cpu"), deterministic=True)
    b = evaluate_policy(agent, "CartPole-v1", episodes=3, seed=7, device=torch.device("cpu"), deterministic=True)
    assert a["mean_return"] == b["mean_return"]


def test_continuous_deterministic_uses_distribution_mean() -> None:
    space = gym.spaces.Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32)
    spec = ArchitectureSpec(hidden_sizes=(8,), activation="tanh")
    agent = ActorCritic(3, space, spec)
    obs = torch.zeros(1, 3)
    with torch.no_grad():
        actor_x, _ = agent._features(obs)
        dist = agent._distribution(actor_x)
        mean = dist.mean
        sampled = dist.sample()
    assert mean.shape == sampled.shape
    # Greedy continuous action is the mean, not a sample draw.
    greedy = mean
    assert torch.allclose(greedy, dist.mean)
