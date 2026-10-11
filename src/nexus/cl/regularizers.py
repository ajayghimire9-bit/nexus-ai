from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

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


def diagonal_empirical_fisher(
    agent: nn.Module,
    obs: torch.Tensor,
    actions: torch.Tensor,
    *,
    max_samples: int = 64,
) -> dict[str, torch.Tensor]:
    """Diagonal empirical Fisher of the policy log-likelihood.

    F_i = (1/N) Σ_n (∂ log π(a_n | s_n) / ∂θ_i)^2

    Gradients are taken **per sample**. Averaging log-probabilities and then
    squaring the batch gradient is not the empirical Fisher (it scales as 1/N^2
    and couples samples). The critic is not part of this likelihood.
    """
    n = min(int(obs.shape[0]), int(max_samples))
    if n < 1:
        raise ValueError("need at least one sample for Fisher estimation")
    named = [(name, p) for name, p in agent.named_parameters() if p.requires_grad]
    fisher = {name: torch.zeros_like(p, device="cpu") for name, p in named}
    for i in range(n):
        agent.zero_grad(set_to_none=True)
        logp, _, _ = agent.evaluate_actions(obs[i : i + 1], actions[i : i + 1])
        logp.reshape(()).backward()
        for name, p in named:
            if p.grad is None:
                continue
            fisher[name] += p.grad.detach().cpu() ** 2
    for name in fisher:
        fisher[name] /= float(n)
    agent.zero_grad(set_to_none=True)
    return fisher


@dataclass
class TaskFisher:
    task_id: str
    fisher: dict[str, torch.Tensor]
    params: dict[str, torch.Tensor]


class EWCPenalty:
    """Multi-task diagonal EWC (Kirkpatrick et al.).

    After each task k, store a **separate** snapshot (θ*_k, F_k). The penalty is

        (λ/2) Σ_k Σ_i F_{k,i} (θ_i − θ*_k,i)^2

    Earlier snapshots are never replaced. Fishers are not summed into one
    buffer that would then be paired only with the latest parameters (that mix
    is not EWC). This is not Online-EWC (which would decay a single F and move
    a single θ*).
    """

    def __init__(self, lam: float = 10.0, max_samples: int = 64) -> None:
        self.lam = lam
        self.max_samples = max_samples
        self.tasks: list[TaskFisher] = []

    @property
    def n_tasks(self) -> int:
        return len(self.tasks)

    def consolidate(
        self,
        agent: nn.Module,
        obs: torch.Tensor,
        actions: torch.Tensor,
        *,
        task_id: str | None = None,
    ) -> None:
        device = next(agent.parameters()).device
        fisher = diagonal_empirical_fisher(
            agent,
            obs.to(device),
            actions.to(device),
            max_samples=self.max_samples,
        )
        params = {name: p.detach().cpu().clone() for name, p in agent.named_parameters()}
        tid = task_id if task_id is not None else f"task_{self.n_tasks}"
        self.tasks.append(TaskFisher(task_id=tid, fisher=fisher, params=params))

    def loss(self, agent: nn.Module) -> torch.Tensor:
        device = next(agent.parameters()).device
        if not self.tasks:
            return torch.zeros((), device=device)
        total = torch.zeros((), device=device)
        for rec in self.tasks:
            for name, p in agent.named_parameters():
                if name not in rec.fisher:
                    continue
                f = rec.fisher[name].to(device=p.device, dtype=p.dtype)
                star = rec.params[name].to(device=p.device, dtype=p.dtype)
                total = total + (f * (p - star) ** 2).sum()
        return 0.5 * self.lam * total
