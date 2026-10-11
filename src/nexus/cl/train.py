from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any, Callable

import torch

from nexus.config import ArchitectureConfig, PPOConfig
from nexus.eval.evaluate import evaluate_policy
from nexus.cl.models import MultiHeadActorCritic, copy_encoder_into
from nexus.cl.regularizers import EWCPenalty, ReplayBuffer
from nexus.rl.actor_critic import ActorCritic
from nexus.rl.ppo import PPOTrainer
from nexus.tasks.spec import TaskSpec, task_env_fns


def _arch() -> ArchitectureConfig:
    return ArchitectureConfig(hidden_sizes=(32, 32), activation="tanh", shared_backbone=True)


def _ppo(seed: int, timesteps: int) -> PPOConfig:
    return PPOConfig(
        env_id="CartPole-v1",
        num_envs=2,
        num_steps=64,
        update_epochs=2,
        num_minibatches=2,
        total_timesteps=timesteps,
        seed=seed,
        device="cpu",
        log_interval=10_000,
        normalize_obs=True,
    )


def eval_task(agent: Any, spec: TaskSpec, *, episodes: int, seed: int, device: torch.device, obs_rms: Any) -> dict[str, float]:
    stats = evaluate_policy(
        agent,
        spec.gym_id,
        episodes=episodes,
        seed=seed,
        device=device,
        obs_rms=obs_rms,
        env_fn=lambda: task_env_fns(spec, 1, seed)[0](),
    )
    stats["task_id"] = spec.task_id  # type: ignore[assignment]
    stats["normalized"] = spec.normalized_reward(float(stats["mean_return"]))
    return stats


def train_on_task(
    trainer: PPOTrainer,
    spec: TaskSpec,
    *,
    timesteps: int,
    seed: int,
) -> dict[str, Any]:
    trainer.rebind_envs(task_env_fns(spec, trainer.ppo.num_envs, seed), seed=seed)
    trainer.ppo = replace(trainer.ppo, seed=seed, env_id=spec.gym_id)
    trainer.current_task_id = spec.task_id
    # Continue from the current PPO cursor so sequential tasks actually train.
    target = int(getattr(trainer, "_timesteps_done", 0)) + int(timesteps)
    result = trainer.train(target)
    return result


def make_trainer(
    *,
    seed: int,
    timesteps: int,
    spec: TaskSpec,
    agent: Any | None = None,
) -> PPOTrainer:
    ppo = _ppo(seed, timesteps)
    return PPOTrainer(ppo, _arch(), agent=agent, env_fns=task_env_fns(spec, ppo.num_envs, seed))
