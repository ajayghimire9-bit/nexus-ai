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
ArchName = Literal["mlp", "film", "gru"]


class DynamicsMLP(nn.Module):
    def __init__(
        self,
        obs_dim: int,
        n_actions: int,
        *,
        hidden: tuple[int, ...] = (64, 64),
        kind: HeadKind = "residual",
        arch: ArchName = "mlp",
        context_dim: int = 16,
        gru_hidden: int = 36,
    ) -> None:
        super().__init__()
        self.obs_dim = obs_dim
        self.n_actions = n_actions
        self.kind = kind
        self.arch: ArchName = arch
        self.hidden = tuple(hidden)
        self.context_dim = int(context_dim)
        self.gru_hidden = int(gru_hidden)
        in_dim = obs_dim + n_actions
        if arch == "gru":
            self.gru = nn.GRUCell(in_dim, self.gru_hidden)
            last = self.gru_hidden
            self.trunk = None
            self.film = None
            self.ctx_enc = None
        else:
            trunk, last = build_mlp(in_dim, hidden, "tanh", init="xavier")
            self.trunk = trunk
            self.gru = None
            if arch == "film":
                self.ctx_enc = nn.Sequential(nn.Linear(in_dim, self.context_dim), nn.Tanh())
                self.film = nn.Linear(self.context_dim, 2 * last)
                nn.init.zeros_(self.film.weight)
                nn.init.zeros_(self.film.bias)
            else:
                self.ctx_enc = None
                self.film = None
        self.state_head = nn.Linear(last, obs_dim)
        self.term_head = nn.Linear(last, 1)
        nn.init.zeros_(self.state_head.bias)
        nn.init.zeros_(self.term_head.bias)
        self.register_buffer("context", torch.zeros(self.context_dim if arch == "film" else 1))
        self._h: torch.Tensor | None = None

    def n_parameters(self) -> int:
        return sum(int(p.numel()) for p in self.parameters())

    def set_context_from_obs_action(self, obs_norm: np.ndarray, action: np.ndarray) -> None:
        if self.arch != "film" or self.ctx_enc is None:
            return
        o = torch.as_tensor(np.asarray(obs_norm, dtype=np.float32).reshape(-1, self.obs_dim))
        a = torch.as_tensor(np.asarray(action, dtype=np.int64).reshape(-1))
        if o.shape[0] == 0:
            self.context.zero_()
            return
        oh = torch.nn.functional.one_hot(a.long(), num_classes=self.n_actions).float()
        with torch.no_grad():
            vec = self.ctx_enc(torch.cat([o, oh], dim=-1)).mean(dim=0)
        self.context.copy_(vec)

    def begin_rollout(self, n: int) -> None:
        if self.gru is None:
            self._h = None
            return
        self._h = torch.zeros(int(n), self.gru_hidden)

    def forward(self, obs_norm: torch.Tensor, action: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        oh = torch.nn.functional.one_hot(action.long(), num_classes=self.n_actions).float()
        x = torch.cat([obs_norm, oh], dim=-1)
        if self.gru is not None:
            h = self._h
            if h is None or h.shape[0] != x.shape[0]:
                h = torch.zeros(x.shape[0], self.gru_hidden, device=x.device)
            h = self.gru(x, h)
            self._h = h.detach()
            feat = h
        else:
            assert self.trunk is not None
            feat = self.trunk(x)
            if self.film is not None:
                gb = self.film(self.context.to(feat.dtype))
                g, b = gb.chunk(2, dim=-1)
                feat = feat * (1.0 + g) + b
        return self.state_head(feat), self.term_head(feat).squeeze(-1)


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
        arch: ArchName = "mlp",
    ) -> "WorldModel":
        torch.manual_seed(seed)
        net = DynamicsMLP(obs_dim, n_actions, hidden=hidden, kind=kind, arch=arch)
        return cls(net=net.to(device), obs_rms=RunningMeanStd((obs_dim,)), kind=kind, device=torch.device(device))

    def fit_rms(self, obs: np.ndarray) -> None:
        self.obs_rms = _rms_from_array(np.asarray(obs, dtype=np.float32))

    def copy_rms(self, other: RunningMeanStd) -> None:
        self.obs_rms.load_state_dict(other.state_dict())

    def clone(self) -> "WorldModel":
        """CPU snapshot. Does not share parameters with ``self``."""
        hidden = tuple(getattr(self.net, "hidden", (64, 64)))
        arch: ArchName = getattr(self.net, "arch", "mlp")
        other = WorldModel.create(
            self.net.obs_dim,
            self.net.n_actions,
            kind=self.kind,
            hidden=hidden,
            device=str(self.device),
            seed=0,
            arch=arch,
        )
        other.net.load_state_dict({k: v.detach().cpu().clone() for k, v in self.net.state_dict().items()})
        other.copy_rms(self.obs_rms)
        other.net.eval()
        return other

    def begin_rollout(self, n: int) -> None:
        fn = getattr(self.net, "begin_rollout", None)
        if fn is not None:
            fn(int(n))

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
            if getattr(self.net, "arch", "mlp") == "gru" and getattr(self.net, "_h", None) is None:
                self.net.begin_rollout(int(o.shape[0]))
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
                "hidden": tuple(getattr(self.net, "hidden", (64, 64))),
                "arch": getattr(self.net, "arch", "mlp"),
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
