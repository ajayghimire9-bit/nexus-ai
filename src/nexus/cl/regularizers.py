from __future__ import annotations

from collections import defaultdict

import torch
from torch import nn


class ReplayBuffer:
    """Per-task replay. Sampling is balanced across tasks, not a single FIFO."""

    def __init__(self, capacity_per_task: int = 2048) -> None:
        self.capacity_per_task = capacity_per_task
        self.by_task: dict[str, list[tuple[torch.Tensor, torch.Tensor]]] = defaultdict(list)

    def add_batch(self, obs: torch.Tensor, actions: torch.Tensor, task_id: str | None = None) -> None:
        key = task_id or "_unknown"
        o = obs.detach().cpu()
        a = actions.detach().cpu()
        bucket = self.by_task[key]
        for i in range(o.shape[0]):
            bucket.append((o[i], a[i]))
        overflow = len(bucket) - self.capacity_per_task
        if overflow > 0:
            del bucket[:overflow]

    def __len__(self) -> int:
        return sum(len(v) for v in self.by_task.values())

    def task_sizes(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.by_task.items()}

    def bc_loss(self, agent: nn.Module, batch_size: int = 64) -> torch.Tensor:
        tasks = [k for k, v in self.by_task.items() if v]
        if not tasks:
            return torch.zeros((), device=next(agent.parameters()).device)
        per = max(1, batch_size // len(tasks))
        obs_list: list[torch.Tensor] = []
        act_list: list[torch.Tensor] = []
        for key in tasks:
            bucket = self.by_task[key]
            n = min(per, len(bucket))
            idx = torch.randint(0, len(bucket), (n,))
            for i in idx.tolist():
                obs_list.append(bucket[int(i)][0])
                act_list.append(bucket[int(i)][1])
        if len(obs_list) < 2:
            return torch.zeros((), device=next(agent.parameters()).device)
        device = next(agent.parameters()).device
        obs = torch.stack(obs_list).to(device)
        act = torch.stack(act_list).to(device)
        logp, _, _ = agent.evaluate_actions(obs, act)
        return -logp.mean()


class EWCPenalty:
    """Diagonal Fisher accumulated across tasks from representative batches."""

    def __init__(self, lam: float = 10.0) -> None:
        self.lam = lam
        self.params: dict[str, torch.Tensor] = {}
        self.fisher: dict[str, torch.Tensor] = {}
        self.n_tasks = 0

    def consolidate(self, agent: nn.Module, obs: torch.Tensor, actions: torch.Tensor) -> None:
        agent.zero_grad(set_to_none=True)
        logp, value, _ = agent.evaluate_actions(obs, actions)
        (logp.mean() + 0.5 * value.mean()).backward()
        new_fisher: dict[str, torch.Tensor] = {}
        params: dict[str, torch.Tensor] = {}
        for name, p in agent.named_parameters():
            params[name] = p.detach().clone()
            g = torch.zeros_like(p) if p.grad is None else p.grad.detach() ** 2
            new_fisher[name] = g
        if not self.fisher:
            self.fisher = new_fisher
        else:
            for name, f in new_fisher.items():
                if name in self.fisher:
                    self.fisher[name] = self.fisher[name] + f
                else:
                    self.fisher[name] = f
        self.params = params
        self.n_tasks += 1
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
