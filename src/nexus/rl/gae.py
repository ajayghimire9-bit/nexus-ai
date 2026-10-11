from __future__ import annotations

import torch


def compute_gae(
    rewards: torch.Tensor,
    values: torch.Tensor,
    terminated: torch.Tensor,
    next_values: torch.Tensor,
    *,
    gamma: float,
    gae_lambda: float,
    truncated: torch.Tensor | None = None,
    reset_steps: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """GAE with separate termination, truncation, and dummy-reset masks.

    ``terminated``: true env end; do not bootstrap.
    ``truncated``: time-limit; bootstrap from ``next_values`` (timeout state) but
        do not carry GAE into the following episode.
    ``reset_steps``: Gymnasium next-step autoreset dummy transitions (action ignored);
        excluded from the advantage chain.
    ``next_values``: (T, N) value of the true successor at each step.
    """
    if truncated is None:
        truncated = torch.zeros_like(terminated)
    if reset_steps is None:
        reset_steps = torch.zeros_like(terminated)

    t_steps, num_envs = rewards.shape
    advantages = torch.zeros_like(rewards)
    last_gae = torch.zeros(num_envs, device=rewards.device, dtype=rewards.dtype)
    for t in reversed(range(t_steps)):
        bootstrap = (1.0 - terminated[t]) * (1.0 - reset_steps[t])
        # Episode continues after this step only if it neither ended nor was a dummy reset.
        continue_gae = bootstrap * (1.0 - truncated[t])
        delta = rewards[t] + gamma * next_values[t] * bootstrap - values[t]
        last_gae = delta + gamma * gae_lambda * continue_gae * last_gae
        advantages[t] = last_gae
    advantages = torch.where(reset_steps.bool(), torch.zeros_like(advantages), advantages)
    returns = advantages + values
    return advantages, returns
