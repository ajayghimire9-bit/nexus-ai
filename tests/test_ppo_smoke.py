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


class _ToyEnv:
    """Minimal env: terminate after 2 steps (true terminal, not time-limit)."""

    metadata = {"render_modes": []}

    def __init__(self) -> None:
        import gymnasium as gym
        import numpy as np

        self.observation_space = gym.spaces.Box(-10.0, 10.0, (2,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(2)
        self.render_mode = None
        self.t = 0
        np.random.seed(0)

    def reset(self, *, seed=None, options=None):  # type: ignore[no-untyped-def]
        import numpy as np

        if seed is not None:
            np.random.seed(seed)
        self.t = 0
        return np.zeros(2, dtype=np.float32), {}

    def step(self, action):  # type: ignore[no-untyped-def]
        import numpy as np

        self.t += 1
        obs = np.array([float(self.t), 0.0], dtype=np.float32)
        terminated = self.t >= 2
        return obs, 1.0, terminated, False, {}

    def close(self) -> None:
        return None


def _toy_fns(n: int):
    return [lambda: _ToyEnv() for _ in range(n)]


def test_collect_true_termination_vs_next_step_autoreset() -> None:
    ppo = PPOConfig(
        env_id="CartPole-v1",
        num_envs=2,
        num_steps=8,
        update_epochs=1,
        num_minibatches=1,
        seed=0,
        device="cpu",
    )
    trainer = PPOTrainer(ppo, ArchitectureConfig(hidden_sizes=(8,), activation="tanh"), env_fns=_toy_fns(2))
    try:
        trainer.collect()
        flags = trainer._last_collect
        term = flags["terminated"]
        trunc = flags["truncated"]
        reset = flags["reset_steps"]
        assert (trunc == 0).all()
        assert (term > 0).any()
        # After a true terminal, the next step on that env is a dummy autoreset.
        for env_i in range(2):
            term_steps = (term[:, env_i] > 0.5).nonzero(as_tuple=False).flatten()
            for t in term_steps.tolist():
                if t + 1 < term.shape[0]:
                    assert reset[t + 1, env_i] > 0.5
                    assert flags["advantages"][t + 1, env_i].item() == 0.0
        assert torch.isfinite(flags["advantages"]).all()
    finally:
        trainer.close()


def test_collect_time_limit_truncation_bootstraps() -> None:
    import gymnasium as gym

    def make() -> gym.Env:
        env = gym.make("CartPole-v1")
        env = gym.wrappers.TimeLimit(env, max_episode_steps=3)
        return env

    ppo = PPOConfig(
        env_id="CartPole-v1",
        num_envs=2,
        num_steps=12,
        update_epochs=1,
        num_minibatches=1,
        seed=1,
        device="cpu",
    )
    trainer = PPOTrainer(
        ppo,
        ArchitectureConfig(hidden_sizes=(8,), activation="tanh"),
        env_fns=[make, make],
    )
    try:
        trainer.collect()
        flags = trainer._last_collect
        trunc = flags["truncated"]
        term = flags["terminated"]
        assert (trunc > 0).any(), "TimeLimit(3) should truncate within 12 steps"
        # Truncation is not recorded as a true terminal.
        both = (trunc > 0.5) & (term > 0.5)
        assert not bool(both.any())
        # Dummy reset follows truncation; those advantages are zeroed.
        reset = flags["reset_steps"]
        for env_i in range(2):
            trunc_steps = (trunc[:, env_i] > 0.5).nonzero(as_tuple=False).flatten()
            for t in trunc_steps.tolist():
                if t + 1 < trunc.shape[0]:
                    assert reset[t + 1, env_i] > 0.5
        assert torch.isfinite(flags["next_values"]).all()
        assert torch.isfinite(flags["advantages"]).all()
    finally:
        trainer.close()


def test_update_excludes_dummy_reset_from_value_loss() -> None:
    ppo = PPOConfig(
        env_id="CartPole-v1",
        num_envs=2,
        num_steps=8,
        update_epochs=1,
        num_minibatches=1,
        seed=0,
        device="cpu",
        normalize_advantages=False,
    )
    trainer = PPOTrainer(ppo, ArchitectureConfig(hidden_sizes=(8,), activation="tanh"), env_fns=_toy_fns(2))
    try:
        batch, _ = trainer.collect()
        assert "valid" in batch
        dummy = batch["valid"] < 0.5
        assert bool(dummy.any())
        poisoned = dict(batch)
        poisoned["returns"] = batch["returns"].clone()
        poisoned["returns"][dummy] = 1.0e6
        metrics = trainer.update(poisoned)
        assert metrics["value_loss"] < 1.0e4
        assert math.isfinite(metrics["entropy"])
        assert math.isfinite(metrics["policy_loss"])
    finally:
        trainer.close()


def test_collect_same_step_autoreset_finite() -> None:
    from gymnasium.vector.vector_env import AutoresetMode

    ppo = PPOConfig(
        env_id="CartPole-v1",
        num_envs=2,
        num_steps=8,
        update_epochs=1,
        num_minibatches=1,
        seed=0,
        device="cpu",
    )
    trainer = PPOTrainer(
        ppo,
        ArchitectureConfig(hidden_sizes=(8,), activation="tanh"),
        env_fns=_toy_fns(2),
        autoreset_mode=AutoresetMode.SAME_STEP,
    )
    try:
        batch, _ = trainer.collect()
        assert torch.isfinite(batch["advantages"]).all()
        metrics = trainer.update(batch)
        assert math.isfinite(metrics["policy_loss"])
    finally:
        trainer.close()


def test_train_resume_does_not_double_count_steps() -> None:
    ppo = PPOConfig(
        env_id="CartPole-v1",
        num_envs=2,
        num_steps=64,
        total_timesteps=256,
        update_epochs=1,
        num_minibatches=2,
        seed=0,
        device="cpu",
    )
    trainer = PPOTrainer(ppo, ArchitectureConfig(hidden_sizes=(8,), activation="tanh"))
    try:
        first = trainer.train(256, interrupt_after_iters=1)
        assert first["interrupted"] is True
        assert first["timesteps"] == 128
        second = trainer.train(256)
        assert second["interrupted"] is False
        assert second["timesteps"] == 256
        assert second["complete"] is True
        assert trainer._num_updates == 2
    finally:
        trainer.close()


def test_train_resume_from_disk_does_not_double_count(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ppo = PPOConfig(
        env_id="CartPole-v1",
        num_envs=2,
        num_steps=64,
        total_timesteps=256,
        update_epochs=1,
        num_minibatches=2,
        seed=1,
        device="cpu",
    )
    arch = ArchitectureConfig(hidden_sizes=(8,), activation="tanh")
    ckpt = tmp_path / "mid.pt"
    first = PPOTrainer(ppo, arch)
    try:
        first.train(256, interrupt_after_iters=1, progress_path=ckpt)
        assert first._timesteps_done == 128
    finally:
        first.close()
    second = PPOTrainer(ppo, arch)
    try:
        second.load_training_state(ckpt)
        out = second.train(256)
        assert out["timesteps"] == 256
        assert second._num_updates == 2
    finally:
        second.close()

