from __future__ import annotations

import math

import torch

from nexus.config import ArchitectureConfig, PPOConfig
from nexus.rl.ppo import PPOTrainer


def test_ppo_one_iteration_finite() -> None:
    ppo = PPOConfig(
        env_id="CartPole-v1",
        num_envs=2,
        total_timesteps=256,
        num_steps=64,
        update_epochs=2,
        num_minibatches=2,
        seed=0,
        device="cpu",
    )
    arch = ArchitectureConfig(hidden_sizes=(32,), activation="tanh")
    trainer = PPOTrainer(ppo, arch)
    try:
        result = trainer.train(256)
        losses = result["history"][-1]
        assert math.isfinite(losses["policy_loss"])
        assert math.isfinite(losses["value_loss"])
        params = torch.nn.utils.parameters_to_vector(trainer.agent.parameters())
        assert torch.isfinite(params).all()
    finally:
        trainer.close()


def test_collect_does_not_reset_every_rollout() -> None:
    ppo = PPOConfig(
        env_id="CartPole-v1",
        num_envs=2,
        num_steps=8,
        update_epochs=1,
        num_minibatches=1,
        seed=0,
        device="cpu",
    )
    trainer = PPOTrainer(ppo, ArchitectureConfig(hidden_sizes=(16,), activation="tanh"))
    try:
        resets = {"n": 0}
        original = trainer.envs.reset

        def wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
            resets["n"] += 1
            return original(*args, **kwargs)

        trainer.envs.reset = wrapped  # type: ignore[method-assign]
        trainer.collect()
        trainer.collect()
        assert resets["n"] == 0
    finally:
        trainer.close()
