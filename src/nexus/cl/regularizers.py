from __future__ import annotations

from typing import Any

import torch
from torch import nn


class ReplayBuffer:
    def __init__(self, capacity: int = 4096) -> None:
        self.capacity = capacity
        self.obs: list[torch.Tensor] = []
        self.actions: list[torch.Tensor] = []

    def add_batch(self, obs: torch.Tensor, actions: torch.Tensor) -> None:
        o = obs.detach().cpu()
        a = actions.detach().cpu()
        for i in range(o.shape[0]):
            self.obs.append(o[i])
            self.actions.append(a[i])
        overflow = len(self.obs) - self.capacity
        if overflow > 0:
            self.obs = self.obs[overflow:]
            self.actions = self.actions[overflow:]

    def __len__(self) -> int:
        return len(self.obs)

    def bc_loss(self, agent: nn.Module, batch_size: int = 64) -> torch.Tensor:
        if len(self.obs) < 2:
            return torch.zeros((), device=next(agent.parameters()).device)
        n = min(batch_size, len(self.obs))
        idx = torch.randint(0, len(self.obs), (n,))
        obs = torch.stack([self.obs[int(i)] for i in idx]).to(next(agent.parameters()).device)
        act = torch.stack([self.actions[int(i)] for i in idx]).to(next(agent.parameters()).device)
        logp, _, _ = agent.evaluate_actions(obs, act)
        return -logp.mean()


class EWCPenalty:
    def __init__(self, lam: float = 10.0) -> None:
        self.lam = lam
        self.params: dict[str, torch.Tensor] = {}
        self.fisher: dict[str, torch.Tensor] = {}

    def consolidate(self, agent: nn.Module, obs: torch.Tensor, actions: torch.Tensor) -> None:
        agent.zero_grad(set_to_none=True)
        logp, value, _ = agent.evaluate_actions(obs, actions)
        (logp.mean() + value.mean()).backward()
        fisher: dict[str, torch.Tensor] = {}
        params: dict[str, torch.Tensor] = {}
        for name, p in agent.named_parameters():
            params[name] = p.detach().clone()
            if p.grad is None:
                fisher[name] = torch.zeros_like(p)
            else:
                fisher[name] = p.grad.detach() ** 2
        self.params = params
        self.fisher = fisher
        agent.zero_grad(set_to_none=True)

    def loss(self, agent: nn.Module) -> torch.Tensor:
        if not self.fisher:
            return torch.zeros((), device=next(agent.parameters()).device)
        total = torch.zeros((), device=next(agent.parameters()).device)
        for name, p in agent.named_parameters():
            if name not in self.fisher:
                continue
            total = total + (self.fisher[name].to(p.device) * (p - self.params[name].to(p.device)) ** 2).sum()
        return 0.5 * self.lam * total
