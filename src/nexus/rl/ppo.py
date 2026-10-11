from __future__ import annotations

import json
import random
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import torch
from gymnasium.vector import SyncVectorEnv
from torch.nn.utils import clip_grad_norm_

from nexus.config import ArchitectureConfig, PPOConfig
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.actor_critic import ActorCritic
from nexus.rl.gae import compute_gae


def _make_env(env_id: str, seed: int) -> callable:
    def thunk() -> gym.Env:
        env = gym.make(env_id)
        env.reset(seed=seed)
        env.action_space.seed(seed)
        return env

    return thunk


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def spec_from_arch_config(arch: ArchitectureConfig) -> ArchitectureSpec:
    return ArchitectureSpec(
        hidden_sizes=tuple(arch.hidden_sizes),
        activation=arch.activation,
        use_residual=arch.use_residual,
        dropout=arch.dropout,
        layer_norm=arch.layer_norm,
        shared_backbone=arch.shared_backbone,
        init=arch.init,
    )


class PPOTrainer:
    def __init__(
        self,
        ppo: PPOConfig,
        architecture: ArchitectureConfig,
        *,
        agent: ActorCritic | None = None,
    ) -> None:
        self.ppo = ppo
        self.architecture = architecture
        set_seed(ppo.seed)
        self.device = torch.device(ppo.device)
        self.envs = SyncVectorEnv(
            [_make_env(ppo.env_id, ppo.seed + i) for i in range(ppo.num_envs)]
        )
        obs_space = self.envs.single_observation_space
        act_space = self.envs.single_action_space
        if not isinstance(obs_space, gym.spaces.Box):
            raise TypeError("V0.1 PPO expects a Box observation space")
        obs_dim = int(np.prod(obs_space.shape))
        spec = spec_from_arch_config(architecture)
        self.agent = agent.to(self.device) if agent is not None else ActorCritic(obs_dim, act_space, spec).to(self.device)
        self.optimizer = torch.optim.Adam(self.agent.parameters(), lr=ppo.learning_rate, eps=1e-5)
        self.obs_dim = obs_dim
        self.discrete = hasattr(act_space, "n")
        obs, _ = self.envs.reset(seed=ppo.seed)
        self._obs = self._obs_tensor(obs)
        self._episode_return = np.zeros(ppo.num_envs, dtype=np.float64)

    def close(self) -> None:
        self.envs.close()

    def _obs_tensor(self, obs: np.ndarray) -> torch.Tensor:
        return torch.as_tensor(obs, dtype=torch.float32, device=self.device).view(obs.shape[0], -1)

    def collect(self) -> tuple[dict[str, torch.Tensor], dict[str, float]]:
        cfg = self.ppo
        n_steps, n_envs = cfg.num_steps, cfg.num_envs
        obs_buf = torch.zeros(n_steps, n_envs, self.obs_dim, device=self.device)
        if self.discrete:
            act_buf = torch.zeros(n_steps, n_envs, device=self.device)
        else:
            act_dim = int(self.envs.single_action_space.shape[0])
            act_buf = torch.zeros(n_steps, n_envs, act_dim, device=self.device)
        logp_buf = torch.zeros(n_steps, n_envs, device=self.device)
        rew_buf = torch.zeros(n_steps, n_envs, device=self.device)
        term_buf = torch.zeros(n_steps, n_envs, device=self.device)
        val_buf = torch.zeros(n_steps, n_envs, device=self.device)

        obs_t = self._obs
        episode_returns: list[float] = []
        cumulative = self._episode_return

        for step in range(n_steps):
            with torch.no_grad():
                action, log_prob, value, _ = self.agent(obs_t)
            env_action = action.detach().cpu().numpy()
            if self.discrete:
                env_action = env_action.astype(np.int64)
            next_obs, reward, terminated, truncated, infos = self.envs.step(env_action)
            done = np.logical_or(terminated, truncated)
            cumulative += reward
            for i, finished in enumerate(done):
                if finished:
                    episode_returns.append(float(cumulative[i]))
                    cumulative[i] = 0.0

            obs_buf[step] = obs_t
            act_buf[step] = action
            logp_buf[step] = log_prob
            rew_buf[step] = torch.as_tensor(reward, dtype=torch.float32, device=self.device)
            # Terminate bootstrap only on true terminals, not time-limit truncations.
            term_buf[step] = torch.as_tensor(terminated, dtype=torch.float32, device=self.device)
            val_buf[step] = value
            obs_t = self._obs_tensor(next_obs)

        self._obs = obs_t
        self._episode_return = cumulative

        with torch.no_grad():
            next_value = self.agent.value(obs_t)
            # If truncated, bootstrap from the true next observation when provided.
            finals = infos.get("final_observation") if isinstance(infos, dict) else None
            if finals is not None:
                for i, trunc in enumerate(truncated):
                    final_obs = finals[i]
                    if trunc and final_obs is not None:
                        fo = torch.as_tensor(final_obs, dtype=torch.float32, device=self.device).view(1, -1)
                        next_value[i] = self.agent.value(fo).reshape(())

            advantages, returns = compute_gae(
                rew_buf, val_buf, term_buf, next_value, gamma=cfg.gamma, gae_lambda=cfg.gae_lambda
            )

        batch = {
            "obs": obs_buf.reshape(-1, self.obs_dim),
            "actions": act_buf.reshape(n_steps * n_envs, *act_buf.shape[2:]),
            "log_probs": logp_buf.reshape(-1),
            "advantages": advantages.reshape(-1),
            "returns": returns.reshape(-1),
            "values": val_buf.reshape(-1),
        }
        metrics = {
            "rollout_episodes": float(len(episode_returns)),
            "rollout_mean_return": float(np.mean(episode_returns)) if episode_returns else 0.0,
        }
        return batch, metrics

    def update(self, batch: dict[str, torch.Tensor]) -> dict[str, float]:
        cfg = self.ppo
        bsz = batch["obs"].shape[0]
        minibatch_size = bsz // cfg.num_minibatches
        if minibatch_size < 1:
            raise ValueError("num_minibatches too large for batch size")

        advantages = batch["advantages"]
        if cfg.normalize_advantages:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        clipfracs: list[float] = []
        entropies: list[float] = []
        pg_losses: list[float] = []
        vf_losses: list[float] = []

        inds = np.arange(bsz)
        for _ in range(cfg.update_epochs):
            np.random.shuffle(inds)
            for start in range(0, bsz, minibatch_size):
                mb = inds[start : start + minibatch_size]
                obs = batch["obs"][mb]
                actions = batch["actions"][mb]
                old_logp = batch["log_probs"][mb]
                adv = advantages[mb]
                ret = batch["returns"][mb]
                old_v = batch["values"][mb]

                logp, value, entropy = self.agent.evaluate_actions(obs, actions)
                ratio = torch.exp(logp - old_logp)
                pg_loss1 = -adv * ratio
                pg_loss2 = -adv * torch.clamp(ratio, 1.0 - cfg.clip_coef, 1.0 + cfg.clip_coef)
                pg_loss = torch.max(pg_loss1, pg_loss2).mean()

                if cfg.clip_vloss:
                    v_clipped = old_v + torch.clamp(value - old_v, -cfg.clip_coef, cfg.clip_coef)
                    vf_loss = 0.5 * torch.max((value - ret) ** 2, (v_clipped - ret) ** 2).mean()
                else:
                    vf_loss = 0.5 * ((value - ret) ** 2).mean()

                loss = pg_loss + cfg.vf_coef * vf_loss - cfg.ent_coef * entropy.mean()
                self.optimizer.zero_grad()
                loss.backward()
                clip_grad_norm_(self.agent.parameters(), cfg.max_grad_norm)
                self.optimizer.step()

                with torch.no_grad():
                    clipfracs.append(float(((ratio - 1.0).abs() > cfg.clip_coef).float().mean().item()))
                    entropies.append(float(entropy.mean().item()))
                    pg_losses.append(float(pg_loss.item()))
                    vf_losses.append(float(vf_loss.item()))

        return {
            "policy_loss": float(np.mean(pg_losses)),
            "value_loss": float(np.mean(vf_losses)),
            "entropy": float(np.mean(entropies)),
            "clipfrac": float(np.mean(clipfracs)),
        }

    def train(self, total_timesteps: int | None = None) -> dict[str, Any]:
        cfg = self.ppo
        target = total_timesteps if total_timesteps is not None else cfg.total_timesteps
        steps_per_iter = cfg.num_steps * cfg.num_envs
        iterations = max(1, target // steps_per_iter)
        history: list[dict[str, float]] = []
        start = time.time()
        timesteps = 0
        for it in range(iterations):
            batch, roll_metrics = self.collect()
            update_metrics = self.update(batch)
            timesteps += steps_per_iter
            row = {"iteration": float(it), "timesteps": float(timesteps), **roll_metrics, **update_metrics}
            history.append(row)
            print(
                f"iter={it} steps={timesteps} "
                f"rollout_return={row['rollout_mean_return']:.1f} "
                f"policy_loss={row['policy_loss']:.4f} value_loss={row['value_loss']:.4f}",
                flush=True,
            )
        elapsed = time.time() - start
        result = {
            "timesteps": timesteps,
            "seconds": elapsed,
            "final_rollout_mean_return": history[-1]["rollout_mean_return"] if history else 0.0,
            "history": history,
        }
        return result

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.agent.state_dict(),
            "architecture": asdict(self.architecture),
            "ppo": asdict(self.ppo),
        }
        torch.save(payload, path)
        meta = path.with_suffix(".json")
        meta.write_text(
            json.dumps({"architecture": asdict(self.architecture), "ppo": asdict(self.ppo)}, indent=2)
        )
