from __future__ import annotations

from typing import Any

import torch
from torch import nn
from torch.distributions import Categorical, Normal

from nexus.nn.factory import build_from_spec
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.actor_critic import ActorCritic


class MultiHeadActorCritic(nn.Module):
    """Shared encoder, task-specific policy/value heads. Not a new algorithm."""

    def __init__(self, obs_dim: int, action_space: Any, spec: ArchitectureSpec, task_ids: tuple[str, ...]) -> None:
        super().__init__()
        self.spec = spec
        self.discrete = hasattr(action_space, "n")
        self.obs_dim = obs_dim
        self.task_ids = task_ids
        self._task = task_ids[0]
        self.backbone, hidden = build_from_spec(obs_dim, spec)
        if self.discrete:
            self.action_dim = int(action_space.n)
            self.policy_heads = nn.ModuleDict({t: nn.Linear(hidden, self.action_dim) for t in task_ids})
            self.log_std = None
        else:
            self.action_dim = int(action_space.shape[0])
            self.policy_heads = nn.ModuleDict({t: nn.Linear(hidden, self.action_dim) for t in task_ids})
            self.log_std = nn.Parameter(torch.zeros(self.action_dim))
        self.value_heads = nn.ModuleDict({t: nn.Linear(hidden, 1) for t in task_ids})
        for head in list(self.policy_heads.values()) + list(self.value_heads.values()):
            nn.init.orthogonal_(head.weight, gain=0.01 if head in self.policy_heads.values() else 1.0)
            nn.init.zeros_(head.bias)

    def set_task(self, task_id: str) -> None:
        if task_id not in self.task_ids:
            raise KeyError(task_id)
        self._task = task_id

    def _features(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.backbone(obs)
        return h, h

    def _distribution(self, actor_x: torch.Tensor):
        logits_or_mean = self.policy_heads[self._task](actor_x)
        if self.discrete:
            return Categorical(logits=logits_or_mean)
        std = torch.exp(self.log_std).expand_as(logits_or_mean)
        return Normal(logits_or_mean, std)

    def forward(self, obs: torch.Tensor):
        actor_x, critic_x = self._features(obs)
        dist = self._distribution(actor_x)
        value = self.value_heads[self._task](critic_x).squeeze(-1)
        action = dist.sample()
        log_prob = dist.log_prob(action) if self.discrete else dist.log_prob(action).sum(-1)
        entropy = dist.entropy() if self.discrete else dist.entropy().sum(-1)
        return action, log_prob, value, entropy

    def evaluate_actions(self, obs: torch.Tensor, actions: torch.Tensor):
        actor_x, critic_x = self._features(obs)
        dist = self._distribution(actor_x)
        value = self.value_heads[self._task](critic_x).squeeze(-1)
        if self.discrete:
            return dist.log_prob(actions.long()), value, dist.entropy()
        return dist.log_prob(actions).sum(-1), value, dist.entropy().sum(-1)

    def value(self, obs: torch.Tensor) -> torch.Tensor:
        _, critic_x = self._features(obs)
        return self.value_heads[self._task](critic_x).squeeze(-1)


def copy_encoder_into(dst: ActorCritic | MultiHeadActorCritic, src: nn.Module) -> int:
    """Copy shared backbone / encoder weights. Heads are not copied. Returns tensors copied."""
    src_sd = src.state_dict()
    dst_sd = dst.state_dict()
    overlap = {
        k: v
        for k, v in src_sd.items()
        if k.startswith("backbone.") and k in dst_sd and dst_sd[k].shape == v.shape
    }
    dst_sd.update(overlap)
    dst.load_state_dict(dst_sd)
    return len(overlap)


def copy_full_policy(dst: nn.Module, src: nn.Module) -> int:
    """Copy every overlapping parameter used by the destination forward pass."""
    src_sd = src.state_dict()
    dst_sd = dst.state_dict()
    overlap = {k: v for k, v in src_sd.items() if k in dst_sd and dst_sd[k].shape == v.shape}
    if not overlap:
        raise RuntimeError("copy_full_policy copied 0 tensors; destination would ignore the source")
    dst_sd.update(overlap)
    dst.load_state_dict(dst_sd)
    return len(overlap)
