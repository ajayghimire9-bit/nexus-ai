from __future__ import annotations

import torch


def compute_gae(
    rewards: torch.Tensor,
    values: torch.Tensor,
    dones: torch.Tensor,
    next_value: torch.Tensor,
    *,
    gamma: float,
    gae_lambda: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Generalized Advantage Estimation.

    Args:
        rewards: (T, N)
        values: (T, N) value predictions at sampled states
        dones: (T, N) true terminals (not truncations); 1.0 ends bootstrap
        next_value: (N,) bootstrap value after the last step
        gamma: discount
        gae_lambda: GAE lambda

    Returns:
        advantages (T, N), returns (T, N)
    """
    t_steps, num_envs = rewards.shape
    advantages = torch.zeros_like(rewards)
    last_gae = torch.zeros(num_envs, device=rewards.device, dtype=rewards.dtype)
    next_val = next_value
    for t in reversed(range(t_steps)):
        mask = 1.0 - dones[t]
        delta = rewards[t] + gamma * next_val * mask - values[t]
        last_gae = delta + gamma * gae_lambda * mask * last_gae
        advantages[t] = last_gae
        next_val = values[t]
    returns = advantages + values
    return advantages, returns
