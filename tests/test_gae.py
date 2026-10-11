from __future__ import annotations

import torch

from nexus.rl.gae import compute_gae


def test_gae_terminal_zero_bootstrap() -> None:
    rewards = torch.tensor([[1.0], [1.0]])
    values = torch.tensor([[0.0], [0.0]])
    terminated = torch.tensor([[0.0], [1.0]])
    next_values = torch.tensor([[0.0], [99.0]])
    adv, ret = compute_gae(
        rewards, values, terminated, next_values, gamma=1.0, gae_lambda=1.0
    )
    # Last step terminates: advantage = 1 - 0, no bootstrap of 99.
    assert torch.allclose(adv[1], torch.tensor([1.0]))
    assert torch.allclose(ret[1], torch.tensor([1.0]))
    assert torch.allclose(adv[0], torch.tensor([2.0]))


def test_gae_truncation_bootstraps_but_does_not_cross_reset() -> None:
    rewards = torch.tensor([[1.0], [1.0], [0.0]])
    values = torch.tensor([[0.0], [0.0], [3.0]])
    terminated = torch.tensor([[0.0], [0.0], [0.0]])
    truncated = torch.tensor([[0.0], [1.0], [0.0]])
    reset_steps = torch.tensor([[0.0], [0.0], [1.0]])
    next_values = torch.tensor([[0.0], [5.0], [7.0]])
    adv, _ = compute_gae(
        rewards,
        values,
        terminated,
        next_values,
        gamma=1.0,
        gae_lambda=1.0,
        truncated=truncated,
        reset_steps=reset_steps,
    )
    # Truncation bootstraps V(timeout)=5: A_1 = 1+5.
    assert torch.allclose(adv[1], torch.tensor([6.0]))
    # Dummy autoreset step has zeroed advantage (not a real transition).
    assert torch.allclose(adv[2], torch.tensor([0.0]))
    # Same-episode step 0 still includes truncated-step advantage.
    assert torch.allclose(adv[0], torch.tensor([7.0]))


def test_gae_does_not_propagate_across_true_terminal_boundary() -> None:
    rewards = torch.tensor([[1.0], [1.0], [10.0]])
    values = torch.zeros(3, 1)
    terminated = torch.tensor([[0.0], [1.0], [0.0]])
    truncated = torch.zeros(3, 1)
    next_values = torch.tensor([[0.0], [99.0], [0.0]])
    adv, _ = compute_gae(
        rewards,
        values,
        terminated,
        next_values,
        gamma=1.0,
        gae_lambda=1.0,
        truncated=truncated,
    )
    assert torch.allclose(adv[1], torch.tensor([1.0]))
    # New episode after reset is independent of the terminal bootstrap-99.
    assert torch.allclose(adv[2], torch.tensor([10.0]))
    assert torch.allclose(adv[0], torch.tensor([2.0]))


def test_gae_vector_envs_independent() -> None:
    rewards = torch.tensor([[1.0, 1.0], [1.0, 1.0]])
    values = torch.zeros(2, 2)
    terminated = torch.tensor([[0.0, 0.0], [1.0, 0.0]])
    truncated = torch.tensor([[0.0, 0.0], [0.0, 1.0]])
    next_values = torch.tensor([[0.0, 0.0], [50.0, 4.0]])
    adv, _ = compute_gae(
        rewards,
        values,
        terminated,
        next_values,
        gamma=1.0,
        gae_lambda=1.0,
        truncated=truncated,
    )
    assert torch.allclose(adv[1, 0], torch.tensor(1.0))  # terminal, no 50
    assert torch.allclose(adv[1, 1], torch.tensor(5.0))  # trunc, bootstrap 4


def test_gae_shapes() -> None:
    t, n = 5, 3
    rewards = torch.ones(t, n)
    values = torch.zeros(t, n)
    terminated = torch.zeros(t, n)
    next_values = torch.zeros(t, n)
    adv, ret = compute_gae(
        rewards, values, terminated, next_values, gamma=0.99, gae_lambda=0.95
    )
    assert adv.shape == (t, n)
    assert ret.shape == (t, n)
    assert torch.isfinite(adv).all()
