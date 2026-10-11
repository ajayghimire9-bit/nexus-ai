from __future__ import annotations

from typing import Any

import torch
from torch import nn
from torch.distributions import Categorical, Normal

from nexus.nn.factory import build_from_spec
from nexus.nn.spec import ArchitectureSpec


class ActorCritic(nn.Module):
    def __init__(
        self,
        obs_dim: int,
        action_space: Any,
        spec: ArchitectureSpec,
    ) -> None:
        super().__init__()
        self.spec = spec
        self.discrete = hasattr(action_space, "n")
        self.obs_dim = obs_dim

        if spec.shared_backbone:
            self.backbone, hidden = build_from_spec(obs_dim, spec)
            self.actor_trunk = nn.Identity()
            self.critic_trunk = nn.Identity()
            actor_in = hidden
            critic_in = hidden
        else:
            self.backbone = nn.Identity()
            self.actor_trunk, actor_in = build_from_spec(obs_dim, spec)
            self.critic_trunk, critic_in = build_from_spec(obs_dim, spec)
            hidden = actor_in

        if self.discrete:
            self.action_dim = int(action_space.n)
            self.policy_head = nn.Linear(actor_in, self.action_dim)
            self.log_std = None
        else:
            self.action_dim = int(action_space.shape[0])
            self.policy_head = nn.Linear(actor_in, self.action_dim)
            self.log_std = nn.Parameter(torch.zeros(self.action_dim))

        self.value_head = nn.Linear(critic_in, 1)
        self._init_heads(spec.init)

    def _init_heads(self, method: str) -> None:
        gain_policy = 0.01
        gain_value = 1.0
        if method == "orthogonal":
            nn.init.orthogonal_(self.policy_head.weight, gain=gain_policy)
            nn.init.orthogonal_(self.value_head.weight, gain=gain_value)
        else:
            nn.init.xavier_uniform_(self.policy_head.weight, gain=gain_policy)
            nn.init.xavier_uniform_(self.value_head.weight, gain=gain_value)
        nn.init.zeros_(self.policy_head.bias)
        nn.init.zeros_(self.value_head.bias)

    def _features(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        shared = self.backbone(obs)
        actor_x = self.actor_trunk(shared if self.spec.shared_backbone else obs)
        critic_x = self.critic_trunk(shared if self.spec.shared_backbone else obs)
        return actor_x, critic_x

    def _distribution(self, actor_x: torch.Tensor):
        logits_or_mean = self.policy_head(actor_x)
        if self.discrete:
            return Categorical(logits=logits_or_mean)
        std = torch.exp(self.log_std).expand_as(logits_or_mean)
        return Normal(logits_or_mean, std)

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        actor_x, critic_x = self._features(obs)
        dist = self._distribution(actor_x)
        value = self.value_head(critic_x).squeeze(-1)
        if self.discrete:
            action = dist.sample()
            log_prob = dist.log_prob(action)
        else:
            action = dist.sample()
            log_prob = dist.log_prob(action).sum(-1)
        return action, log_prob, value, dist.entropy() if self.discrete else dist.entropy().sum(-1)

    def evaluate_actions(
        self, obs: torch.Tensor, actions: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        actor_x, critic_x = self._features(obs)
        dist = self._distribution(actor_x)
        value = self.value_head(critic_x).squeeze(-1)
        if self.discrete:
            log_prob = dist.log_prob(actions.long())
            entropy = dist.entropy()
        else:
            log_prob = dist.log_prob(actions).sum(-1)
            entropy = dist.entropy().sum(-1)
        return log_prob, value, entropy

    def value(self, obs: torch.Tensor) -> torch.Tensor:
        _, critic_x = self._features(obs)
        return self.value_head(critic_x).squeeze(-1)
