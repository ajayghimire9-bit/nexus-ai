from __future__ import annotations

import torch

from nexus.rl.gae import compute_gae


def test_gae_terminal_zero_bootstrap() -> None:
    rewards = torch.tensor([[1.0], [1.0]])
    values = torch.tensor([[0.0], [0.0]])
    dones = torch.tensor([[0.0], [1.0]])
    next_value = torch.tensor([99.0])
    adv, ret = compute_gae(rewards, values, dones, next_value, gamma=1.0, gae_lambda=1.0)
    # Last step terminates: advantage = 1 - 0, no bootstrap of 99.
    assert torch.allclose(adv[1], torch.tensor([1.0]))
    assert torch.allclose(ret[1], torch.tensor([1.0]))
    assert torch.allclose(adv[0], torch.tensor([2.0]))


def test_gae_shapes() -> None:
    t, n = 5, 3
    rewards = torch.ones(t, n)
    values = torch.zeros(t, n)
    dones = torch.zeros(t, n)
    next_value = torch.zeros(n)
    adv, ret = compute_gae(rewards, values, dones, next_value, gamma=0.99, gae_lambda=0.95)
    assert adv.shape == (t, n)
    assert ret.shape == (t, n)
    assert torch.isfinite(adv).all()
