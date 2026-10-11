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
from gymnasium.vector.vector_env import AutoresetMode
from torch.nn.utils import clip_grad_norm_

from nexus.config import ArchitectureConfig, PPOConfig
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.actor_critic import ActorCritic
from nexus.rl.gae import compute_gae
from nexus.nn.expr import dump_expr, maybe_restore_named
from nexus.rl.rng_state import capture_library_rng, capture_vector_env, restore_library_rng, restore_vector_env
from nexus.rl.running_stats import RunningMeanStd


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


def _final_obs_for_env(infos: dict[str, Any] | None, env_index: int) -> np.ndarray | None:
    """Gymnasium SameStep stores the timeout state under final_obs / final_observation."""
    if not isinstance(infos, dict):
        return None
    for key in ("final_observation", "final_obs"):
        block = infos.get(key)
        if block is None:
            continue
        try:
            item = block[env_index]
        except (TypeError, IndexError, KeyError):
            continue
        if item is not None:
            return np.asarray(item, dtype=np.float32)
    return None


def _bootstrap_from_final_obs(
    successor_value: torch.Tensor,
    infos: dict[str, Any] | None,
    truncated: np.ndarray,
    terminated: np.ndarray,
    pending_reset: np.ndarray,
    trainer: "PPOTrainer",
) -> torch.Tensor:
    """If SameStep autoreset replaced next_obs, bootstrap truncations from final_obs."""
    out = successor_value.clone()
    for i, (trunc, term, dummy) in enumerate(zip(truncated, terminated, pending_reset, strict=True)):
        if dummy or term or not trunc:
            continue
        final = _final_obs_for_env(infos, i)
        if final is None:
            continue
        fo = trainer._obs_tensor_no_update(final.reshape(1, -1))
        out[i] = trainer.agent.value(fo).reshape(())
    return out


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
        env_fns: list | None = None,
        autoreset_mode: AutoresetMode | str = AutoresetMode.NEXT_STEP,
    ) -> None:
        self.ppo = ppo
        self.architecture = architecture
        set_seed(ppo.seed)
        self.device = torch.device(ppo.device)
        fns = env_fns if env_fns is not None else [_make_env(ppo.env_id, ppo.seed + i) for i in range(ppo.num_envs)]
        self.envs = SyncVectorEnv(fns, autoreset_mode=autoreset_mode)
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
        self.obs_rms = RunningMeanStd((obs_dim,)) if ppo.normalize_obs else None
        self.freeze_obs_rms = False
        obs, _ = self.envs.reset(seed=ppo.seed)
        self._raw_obs = np.asarray(obs, dtype=np.float32).reshape(ppo.num_envs, obs_dim)
        self._episode_return = np.zeros(ppo.num_envs, dtype=np.float64)
        self._num_updates = 0
        self._timesteps_done = 0

    def close(self) -> None:
        self.envs.close()

    def _obs_tensor(self, obs: np.ndarray) -> torch.Tensor:
        arr = np.asarray(obs, dtype=np.float32).reshape(-1, self.obs_dim)
        if self.obs_rms is not None:
            if not getattr(self, "freeze_obs_rms", False):
                self.obs_rms.update(arr)
            arr = self.obs_rms.normalize(arr)
        return torch.as_tensor(arr, dtype=torch.float32, device=self.device)

    def _obs_tensor_no_update(self, obs: np.ndarray) -> torch.Tensor:
        arr = np.asarray(obs, dtype=np.float32).reshape(-1, self.obs_dim)
        if self.obs_rms is not None:
            arr = self.obs_rms.normalize(arr)
        return torch.as_tensor(arr, dtype=torch.float32, device=self.device)

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
        trunc_buf = torch.zeros(n_steps, n_envs, device=self.device)
        reset_buf = torch.zeros(n_steps, n_envs, device=self.device)
        next_val_buf = torch.zeros(n_steps, n_envs, device=self.device)
        val_buf = torch.zeros(n_steps, n_envs, device=self.device)

        if self.obs_rms is not None and not getattr(self, "freeze_obs_rms", False):
            self.obs_rms.update(self._raw_obs)
        obs_t = self._obs_tensor_no_update(self._raw_obs)
        episode_returns: list[float] = []
        cumulative = self._episode_return

        for step in range(n_steps):
            # NextStep: prior done → this step is a dummy reset. SameStep resets in-step (no dummy).
            mode = getattr(self.envs, "autoreset_mode", AutoresetMode.NEXT_STEP)
            if mode == AutoresetMode.NEXT_STEP:
                pending_reset = np.asarray(
                    getattr(self.envs, "_autoreset_envs", np.zeros(n_envs, dtype=bool)), dtype=bool
                )
            else:
                pending_reset = np.zeros(n_envs, dtype=bool)
            with torch.no_grad():
                action, log_prob, value, _ = self.agent(obs_t)
            env_action = action.detach().cpu().numpy()
            if self.discrete:
                env_action = env_action.astype(np.int64)
            next_obs, reward, terminated, truncated, infos = self.envs.step(env_action)
            done = np.logical_or(terminated, truncated)
            cumulative += reward
            for i, finished in enumerate(done):
                if finished and not pending_reset[i]:
                    episode_returns.append(float(cumulative[i]))
                    cumulative[i] = 0.0

            self._raw_obs = np.asarray(next_obs, dtype=np.float32).reshape(n_envs, self.obs_dim)
            next_obs_t = self._obs_tensor(self._raw_obs)
            with torch.no_grad():
                successor_value = self.agent.value(next_obs_t)
                successor_value = _bootstrap_from_final_obs(
                    successor_value, infos, truncated, terminated, pending_reset, self
                )

            obs_buf[step] = obs_t
            act_buf[step] = action
            logp_buf[step] = log_prob
            rew_buf[step] = torch.as_tensor(reward, dtype=torch.float32, device=self.device)
            term_buf[step] = torch.as_tensor(terminated, dtype=torch.float32, device=self.device)
            trunc_buf[step] = torch.as_tensor(truncated, dtype=torch.float32, device=self.device)
            reset_buf[step] = torch.as_tensor(pending_reset, dtype=torch.float32, device=self.device)
            val_buf[step] = value
            next_val_buf[step] = successor_value
            obs_t = next_obs_t

        self._episode_return = cumulative

        with torch.no_grad():
            advantages, returns = compute_gae(
                rew_buf,
                val_buf,
                term_buf,
                next_val_buf,
                gamma=cfg.gamma,
                gae_lambda=cfg.gae_lambda,
                truncated=trunc_buf,
                reset_steps=reset_buf,
            )

        self._last_collect = {
            "terminated": term_buf.detach().cpu(),
            "truncated": trunc_buf.detach().cpu(),
            "reset_steps": reset_buf.detach().cpu(),
            "next_values": next_val_buf.detach().cpu(),
            "advantages": advantages.detach().cpu(),
            "values": val_buf.detach().cpu(),
            "rewards": rew_buf.detach().cpu(),
        }

        valid = (1.0 - reset_buf).reshape(-1)
        batch = {
            "obs": obs_buf.reshape(-1, self.obs_dim),
            "actions": act_buf.reshape(n_steps * n_envs, *act_buf.shape[2:]),
            "log_probs": logp_buf.reshape(-1),
            "advantages": advantages.reshape(-1),
            "returns": returns.reshape(-1),
            "values": val_buf.reshape(-1),
            "valid": valid,
        }
        metrics = {
            "rollout_episodes": float(len(episode_returns)),
            "rollout_mean_return": float(np.mean(episode_returns)) if episode_returns else 0.0,
        }
        replay = getattr(self, "replay_buffer", None)
        if replay is not None:
            replay.add_batch(
                batch["obs"],
                batch["actions"],
                task_id=getattr(self, "current_task_id", None),
            )
        self._last_rl_batch = batch
        return batch, metrics

    def update(self, batch: dict[str, torch.Tensor]) -> dict[str, float]:
        cfg = self.ppo
        bsz = batch["obs"].shape[0]
        minibatch_size = bsz // cfg.num_minibatches
        if minibatch_size < 1:
            raise ValueError("num_minibatches too large for batch size")

        valid_all = batch.get("valid")
        if valid_all is None:
            valid_all = torch.ones(bsz, device=batch["obs"].device, dtype=batch["obs"].dtype)
        advantages = batch["advantages"]
        if cfg.normalize_advantages:
            mask = valid_all > 0.5
            if bool(mask.any()):
                sel = advantages[mask]
                advantages = (advantages - sel.mean()) / (sel.std() + 1e-8)
            advantages = advantages * valid_all

        clipfracs: list[float] = []
        entropies: list[float] = []
        pg_losses: list[float] = []
        vf_losses: list[float] = []

        inds = np.arange(bsz)
        for _ in range(cfg.update_epochs):
            np.random.shuffle(inds)
            for start in range(0, bsz, minibatch_size):
                mb = inds[start : start + minibatch_size]
                w = valid_all[mb]
                denom = w.sum().clamp_min(1.0)
                if float(w.sum()) < 1.0:
                    continue
                obs = batch["obs"][mb]
                actions = batch["actions"][mb]
                old_logp = batch["log_probs"][mb]
                adv = advantages[mb]
                ret = batch["returns"][mb]
                old_v = batch["values"][mb]

                logp, value, entropy = self.agent.evaluate_actions(obs, actions)
                ratio = torch.exp(logp - old_logp.detach())
                pg_loss1 = -adv * ratio
                pg_loss2 = -adv * torch.clamp(ratio, 1.0 - cfg.clip_coef, 1.0 + cfg.clip_coef)
                pg_loss = (torch.max(pg_loss1, pg_loss2) * w).sum() / denom

                if cfg.clip_vloss:
                    v_clipped = old_v + torch.clamp(value - old_v, -cfg.clip_coef, cfg.clip_coef)
                    vf_elem = 0.5 * torch.max((value - ret) ** 2, (v_clipped - ret) ** 2)
                else:
                    vf_elem = 0.5 * ((value - ret) ** 2)
                vf_loss = (vf_elem * w).sum() / denom
                ent = (entropy * w).sum() / denom

                loss = pg_loss + cfg.vf_coef * vf_loss - cfg.ent_coef * ent
                aux_fn = getattr(self, "aux_loss_fn", None)
                if aux_fn is not None:
                    loss = loss + aux_fn(self.agent)
                self.optimizer.zero_grad()
                loss.backward()
                clip_grad_norm_(self.agent.parameters(), cfg.max_grad_norm)
                self.optimizer.step()

                with torch.no_grad():
                    clipfracs.append(float((((ratio - 1.0).abs() > cfg.clip_coef).float() * w).sum().item() / float(denom)))
                    entropies.append(float(ent.item()))
                    pg_losses.append(float(pg_loss.item()))
                    vf_losses.append(float(vf_loss.item()))

        with torch.no_grad():
            mask = valid_all > 0.5
            y_true = batch["returns"][mask] if bool(mask.any()) else batch["returns"]
            y_pred = batch["values"][mask] if bool(mask.any()) else batch["values"]
            var_y = torch.var(y_true)
            explained = float("nan") if float(var_y) < 1e-8 else float(1.0 - torch.var(y_true - y_pred) / var_y)
        if not pg_losses:
            return {
                "policy_loss": float("nan"),
                "value_loss": float("nan"),
                "entropy": float("nan"),
                "clipfrac": float("nan"),
                "explained_variance": explained,
            }
        return {
            "policy_loss": float(np.mean(pg_losses)),
            "value_loss": float(np.mean(vf_losses)),
            "entropy": float(np.mean(entropies)),
            "clipfrac": float(np.mean(clipfracs)),
            "explained_variance": explained,
        }

    def train(
        self,
        total_timesteps: int | None = None,
        *,
        interrupt_after_iters: int | None = None,
        progress_path: str | Path | None = None,
    ) -> dict[str, Any]:
        cfg = self.ppo
        target = total_timesteps if total_timesteps is not None else cfg.total_timesteps
        steps_per_iter = cfg.num_steps * cfg.num_envs
        iterations = max(1, target // steps_per_iter)
        history: list[dict[str, float]] = []
        start = time.time()
        timesteps = int(getattr(self, "_timesteps_done", 0))
        start_it = int(self._num_updates)
        iters_this_call = 0
        interrupted = False
        for it in range(start_it, iterations):
            if cfg.anneal_lr:
                frac = 1.0 - (it / max(1, iterations))
                lrnow = frac * cfg.learning_rate
                for group in self.optimizer.param_groups:
                    group["lr"] = lrnow
            batch, roll_metrics = self.collect()
            update_metrics = self.update(batch)
            self._num_updates += 1
            timesteps += steps_per_iter
            self._timesteps_done = timesteps
            iters_this_call += 1
            row = {"iteration": float(it), "timesteps": float(timesteps), **roll_metrics, **update_metrics}
            history.append(row)
            if progress_path is not None:
                self.save(progress_path)
            interval = max(1, cfg.log_interval)
            if it % interval == 0 or it == iterations - 1:
                print(
                    f"iter={it} steps={timesteps} "
                    f"rollout_return={row['rollout_mean_return']:.1f} "
                    f"policy_loss={row['policy_loss']:.4f} value_loss={row['value_loss']:.4f} "
                    f"explained_var={row['explained_variance']:.3f} clipfrac={row['clipfrac']:.3f}",
                    flush=True,
                )
            if interrupt_after_iters is not None and iters_this_call >= interrupt_after_iters:
                interrupted = True
                break
        elapsed = time.time() - start
        result = {
            "timesteps": timesteps,
            "seconds": elapsed,
            "final_rollout_mean_return": history[-1]["rollout_mean_return"] if history else 0.0,
            "history": history,
            "interrupted": interrupted,
            "complete": timesteps >= target and not interrupted,
        }
        return result

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.agent.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "architecture": asdict(self.architecture),
            "ppo": asdict(self.ppo),
            "obs_rms": None if self.obs_rms is None else self.obs_rms.state_dict(),
            "num_updates": int(self._num_updates),
            "timesteps_done": int(getattr(self, "_timesteps_done", 0)),
            "freeze_obs_rms": bool(getattr(self, "freeze_obs_rms", False)),
            "raw_obs": self._raw_obs,
            "episode_return": self._episode_return,
            "autoreset_envs": np.asarray(getattr(self.envs, "_autoreset_envs", np.zeros(self.ppo.num_envs, dtype=bool))),
            "library_rng": capture_library_rng(),
            "vector_env": capture_vector_env(self.envs),
            "expr_tree": dump_expr(self.architecture.activation),
        }
        torch.save(payload, path)
        meta = path.with_suffix(".json")
        meta.write_text(
            json.dumps({"architecture": asdict(self.architecture), "ppo": asdict(self.ppo)}, indent=2)
        )

    def load_training_state(self, path: str | Path) -> None:
        payload = torch.load(path, map_location=self.device, weights_only=False)
        self.agent.load_state_dict(payload["model"])
        if payload.get("optimizer"):
            self.optimizer.load_state_dict(payload["optimizer"])
        if payload.get("obs_rms") is not None and self.obs_rms is not None:
            self.obs_rms.load_state_dict(payload["obs_rms"])
        self._num_updates = int(payload.get("num_updates", 0))
        self._timesteps_done = int(payload.get("timesteps_done", 0))
        self.freeze_obs_rms = bool(payload.get("freeze_obs_rms", getattr(self, "freeze_obs_rms", False)))
        if payload.get("raw_obs") is not None:
            self._raw_obs = np.asarray(payload["raw_obs"], dtype=np.float32)
        if payload.get("episode_return") is not None:
            self._episode_return = np.asarray(payload["episode_return"], dtype=np.float64)
        if payload.get("library_rng"):
            restore_library_rng(payload["library_rng"])
        env_snap = payload.get("vector_env")
        if env_snap:
            fidelity = restore_vector_env(self.envs, env_snap)
        else:
            fidelity = "approximate"
            if payload.get("autoreset_envs") is not None and hasattr(self.envs, "_autoreset_envs"):
                self.envs._autoreset_envs = np.asarray(payload["autoreset_envs"], dtype=bool)
        self._resume_fidelity = fidelity

    def rebind_envs(self, env_fns: list, *, seed: int | None = None) -> None:
        """Keep weights; replace the vector env (continual / transfer)."""
        self.envs.close()
        mode = getattr(self.envs, "autoreset_mode", AutoresetMode.NEXT_STEP)
        self.envs = SyncVectorEnv(env_fns, autoreset_mode=mode)
        use_seed = int(self.ppo.seed if seed is None else seed)
        obs, _ = self.envs.reset(seed=use_seed)
        self._raw_obs = np.asarray(obs, dtype=np.float32).reshape(self.ppo.num_envs, self.obs_dim)
        self._episode_return = np.zeros(self.ppo.num_envs, dtype=np.float64)

    @classmethod
    def from_checkpoint(
        cls,
        path: str | Path,
        *,
        ppo: PPOConfig | None = None,
        architecture: ArchitectureConfig | None = None,
        env_fns: list | None = None,
    ) -> "PPOTrainer":
        payload = torch.load(path, map_location="cpu", weights_only=False)
        if payload.get("expr_tree"):
            maybe_restore_named(
                payload["expr_tree"].get("name") or payload["architecture"]["activation"],
                payload["expr_tree"],
            )
        arch = architecture or ArchitectureConfig(**payload["architecture"])
        ppo_cfg = ppo or PPOConfig(**{k: v for k, v in payload["ppo"].items() if k in PPOConfig.__dataclass_fields__})
        trainer = cls(ppo_cfg, arch, env_fns=env_fns)
        trainer.load_training_state(path)
        return trainer
