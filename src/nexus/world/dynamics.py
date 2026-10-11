"""Compact MLP dynamics. Inference never reads the simulator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import torch
from torch import nn

from nexus.nn.factory import build_mlp
from nexus.rl.running_stats import RunningMeanStd

HeadKind = Literal["residual", "direct"]


class DynamicsMLP(nn.Module):
    def __init__(
        self,
        obs_dim: int,
        n_actions: int,
        *,
        hidden: tuple[int, ...] = (64, 64),
        kind: HeadKind = "residual",
    ) -> None:
        super().__init__()
        self.obs_dim = obs_dim
        self.n_actions = n_actions
        self.kind = kind
        trunk, last = build_mlp(obs_dim + n_actions, hidden, "tanh", init="xavier")
        self.trunk = trunk
        self.state_head = nn.Linear(last, obs_dim)
        self.term_head = nn.Linear(last, 1)
        nn.init.zeros_(self.state_head.bias)
        nn.init.zeros_(self.term_head.bias)

    def forward(self, obs_norm: torch.Tensor, action: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        oh = torch.nn.functional.one_hot(action.long(), num_classes=self.n_actions).float()
        h = self.trunk(torch.cat([obs_norm, oh], dim=-1))
        return self.state_head(h), self.term_head(h).squeeze(-1)


def _rms_from_array(x: np.ndarray) -> RunningMeanStd:
    rms = RunningMeanStd((x.shape[-1],))
    rms.update(x)
    return rms


@dataclass
class WorldModel:
    net: DynamicsMLP
    obs_rms: RunningMeanStd
    kind: HeadKind
    device: torch.device

    @classmethod
    def create(
        cls,
        obs_dim: int,
        n_actions: int,
        *,
        kind: HeadKind = "residual",
        hidden: tuple[int, ...] = (64, 64),
        device: str = "cpu",
        seed: int = 0,
    ) -> "WorldModel":
        torch.manual_seed(seed)
        net = DynamicsMLP(obs_dim, n_actions, hidden=hidden, kind=kind)
        return cls(net=net.to(device), obs_rms=RunningMeanStd((obs_dim,)), kind=kind, device=torch.device(device))

    def fit_rms(self, obs: np.ndarray) -> None:
        self.obs_rms = _rms_from_array(np.asarray(obs, dtype=np.float32))

    def copy_rms(self, other: RunningMeanStd) -> None:
        self.obs_rms.load_state_dict(other.state_dict())

    def clone(self) -> "WorldModel":
        """CPU snapshot. Does not share parameters with ``self``."""
        other = WorldModel.create(
            self.net.obs_dim,
            self.net.n_actions,
            kind=self.kind,
            hidden=(64, 64),
            device=str(self.device),
            seed=0,
        )
        other.net.load_state_dict({k: v.detach().cpu().clone() for k, v in self.net.state_dict().items()})
        other.copy_rms(self.obs_rms)
        other.net.eval()
        return other

    def normalize(self, obs: np.ndarray) -> np.ndarray:
        return self.obs_rms.normalize(np.asarray(obs, dtype=np.float32).reshape(-1, self.net.obs_dim))

    def unnormalize(self, obs_norm: np.ndarray) -> np.ndarray:
        std = np.sqrt(self.obs_rms.var + self.obs_rms.epsilon)
        return (np.asarray(obs_norm, dtype=np.float64) * std + self.obs_rms.mean).astype(np.float32)

    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Predict next raw state and terminate-prob. No environment access."""
        self.net.eval()
        o = np.asarray(obs, dtype=np.float32).reshape(-1, self.net.obs_dim)
        a = np.asarray(action, dtype=np.int64).reshape(-1)
        if a.size == 1 and o.shape[0] > 1:
            a = np.full(o.shape[0], int(a.flat[0]), dtype=np.int64)
        with torch.no_grad():
            obs_n = torch.as_tensor(self.normalize(o), device=self.device)
            act_t = torch.as_tensor(a, device=self.device)
            pred, logit = self.net(obs_n, act_t)
            if self.kind == "residual":
                next_n = obs_n + pred
            else:
                next_n = pred
            p = torch.sigmoid(logit)
        next_raw = self.unnormalize(next_n.cpu().numpy())
        return next_raw.reshape(o.shape), p.cpu().numpy().reshape(-1)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.net.state_dict(),
                "obs_rms": self.obs_rms.state_dict(),
                "kind": self.kind,
                "obs_dim": self.net.obs_dim,
                "n_actions": self.net.n_actions,
                "hidden": (64, 64),
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path, *, device: str = "cpu") -> "WorldModel":
        payload = torch.load(path, map_location=device, weights_only=False)
        hidden = payload.get("hidden") or (64, 64)
        # reconstruct hidden from first two linear layers of trunk if needed
        net = DynamicsMLP(int(payload["obs_dim"]), int(payload["n_actions"]), hidden=(64, 64), kind=payload["kind"])
        net.load_state_dict(payload["state_dict"])
        wm = cls(net=net.to(device), obs_rms=RunningMeanStd((int(payload["obs_dim"]),)), kind=payload["kind"], device=torch.device(device))
        wm.obs_rms.load_state_dict(payload["obs_rms"])
        del hidden
        return wm

    def state_meta(self) -> dict[str, Any]:
        return {"kind": self.kind, "obs_dim": self.net.obs_dim, "n_actions": self.net.n_actions}
