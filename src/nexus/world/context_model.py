"""Differentiable transition-context world model. FiLM conditioning. Not GRU. Not AGI.

z = mean_i encoder(obs_norm, action_one_hot, next_norm - obs_norm).
Query prediction loss trains the encoder. Evaluation freezes z.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from nexus.nn.factory import build_mlp
from nexus.rl.running_stats import RunningMeanStd
from nexus.world.data import TransitionDataset

CONTEXT_DIM = 8
ENCODER_HIDDEN = 32
TRUNK_HIDDEN = (48, 48)
MAX_CONTEXT = 128
EMPTY_CONTEXT_PROB = 0.2


class TransitionContextEncoder(nn.Module):
    def __init__(self, obs_dim: int, n_actions: int, *, hidden: int = ENCODER_HIDDEN, z_dim: int = CONTEXT_DIM) -> None:
        super().__init__()
        self.obs_dim = int(obs_dim)
        self.n_actions = int(n_actions)
        self.z_dim = int(z_dim)
        self.net = nn.Sequential(nn.Linear(obs_dim + n_actions + obs_dim, hidden), nn.Tanh(), nn.Linear(hidden, z_dim))

    def forward(self, obs_n: torch.Tensor, action: torch.Tensor, delta_n: torch.Tensor) -> torch.Tensor:
        oh = torch.nn.functional.one_hot(action.long(), num_classes=self.n_actions).float()
        h = self.net(torch.cat([obs_n, oh, delta_n], dim=-1))
        return h.mean(dim=0)


class ContextResidualDynamics(nn.Module):
    """Residual MLP. FiLM scale/shift from z. Chosen before any confirmation run."""

    def __init__(self, obs_dim: int, n_actions: int, *, hidden: tuple[int, ...] = TRUNK_HIDDEN, z_dim: int = CONTEXT_DIM) -> None:
        super().__init__()
        self.obs_dim = int(obs_dim)
        self.n_actions = int(n_actions)
        self.hidden = tuple(hidden)
        self.z_dim = int(z_dim)
        self.arch = "context_film"
        trunk, last = build_mlp(obs_dim + n_actions, hidden, "tanh", init="xavier")
        self.trunk = trunk
        self.film = nn.Linear(z_dim, 2 * last)
        # Zero FiLM weights make d(loss)/d(z) zero, so the encoder never learns.
        nn.init.normal_(self.film.weight, std=0.02)
        nn.init.zeros_(self.film.bias)
        self.state_head = nn.Linear(last, obs_dim)
        self.term_head = nn.Linear(last, 1)
        nn.init.zeros_(self.state_head.bias)
        nn.init.zeros_(self.term_head.bias)
        self.feat_dim = int(last)

    def forward(self, obs_n: torch.Tensor, action: torch.Tensor, z: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        oh = torch.nn.functional.one_hot(action.long(), num_classes=self.n_actions).float()
        feat = self.trunk(torch.cat([obs_n, oh], dim=-1))
        g, b = self.film(z).chunk(2, dim=-1)
        feat = feat * (1.0 + g) + b
        return self.state_head(feat), self.term_head(feat).squeeze(-1)


@dataclass
class ContextWorldModel:
    encoder: TransitionContextEncoder
    net: ContextResidualDynamics
    obs_rms: RunningMeanStd
    device: torch.device
    z: torch.Tensor
    n_encodes: int = 0
    random_encoder: bool = False

    @classmethod
    def create(cls, obs_dim: int, n_actions: int, *, seed: int = 0, random_encoder: bool = False) -> "ContextWorldModel":
        torch.manual_seed(int(seed))
        enc = TransitionContextEncoder(obs_dim, n_actions)
        net = ContextResidualDynamics(obs_dim, n_actions)
        if random_encoder:
            for p in enc.parameters():
                p.requires_grad_(False)
        z = torch.zeros(CONTEXT_DIM)
        return cls(encoder=enc, net=net, obs_rms=RunningMeanStd((obs_dim,)), device=torch.device("cpu"), z=z, random_encoder=bool(random_encoder))

    def n_parameters(self) -> int:
        return sum(int(p.numel()) for p in list(self.encoder.parameters()) + list(self.net.parameters()))

    def trainable_parameters(self) -> int:
        return sum(int(p.numel()) for p in list(self.encoder.parameters()) + list(self.net.parameters()) if p.requires_grad)

    def copy_rms(self, other: RunningMeanStd) -> None:
        self.obs_rms.load_state_dict(other.state_dict())

    def clear_context(self) -> None:
        self.z = torch.zeros(CONTEXT_DIM)

    def normalize(self, obs: np.ndarray) -> np.ndarray:
        return self.obs_rms.normalize(np.asarray(obs, dtype=np.float32).reshape(-1, self.net.obs_dim))

    def unnormalize(self, obs_norm: np.ndarray) -> np.ndarray:
        std = np.sqrt(self.obs_rms.var + self.obs_rms.epsilon)
        return (np.asarray(obs_norm, dtype=np.float64) * std + self.obs_rms.mean).astype(np.float32)

    def _tensors(self, obs: np.ndarray, action: np.ndarray, nxt: np.ndarray) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        o_n = torch.as_tensor(self.normalize(obs), dtype=torch.float32)
        n_n = torch.as_tensor(self.normalize(nxt), dtype=torch.float32)
        a = torch.as_tensor(np.asarray(action, dtype=np.int64).reshape(-1))
        return o_n, a, n_n - o_n

    def encode(self, obs: np.ndarray, action: np.ndarray, nxt: np.ndarray, *, differentiable: bool) -> torch.Tensor:
        """Mean-pool at most MAX_CONTEXT rows. differentiable=False detaches and stores z."""
        o = np.asarray(obs, dtype=np.float32)
        if o.shape[0] == 0:
            z = torch.zeros(CONTEXT_DIM)
            if not differentiable:
                self.z = z
                self.n_encodes += 1
            return z
        n = min(int(o.shape[0]), MAX_CONTEXT)
        obs_n, act, delta = self._tensors(o[:n], np.asarray(action)[:n], np.asarray(nxt)[:n])
        self.encoder.train(differentiable and not self.random_encoder)
        if differentiable and not self.random_encoder:
            z = self.encoder(obs_n, act, delta)
            return z
        with torch.no_grad():
            z = self.encoder(obs_n, act, delta).detach()
        self.z = z
        self.n_encodes += 1
        return z

    def set_context_from_dataset(self, ds: TransitionDataset, *, budget: int) -> torch.Tensor:
        """Inference context from the first `budget` rows, capped at MAX_CONTEXT. Does not train."""
        k = int(budget)
        if k <= 0 or len(ds) == 0:
            self.clear_context()
            self.n_encodes += 1
            return self.z
        sl = ds.slice(np.arange(min(k, len(ds), MAX_CONTEXT)))
        return self.encode(sl.obs, sl.action, sl.next_obs, differentiable=False)

    def begin_rollout(self, n: int) -> None:
        del n

    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Predict with the frozen z. Does not encode or change z."""
        self.net.eval()
        o = np.asarray(obs, dtype=np.float32).reshape(-1, self.net.obs_dim)
        a = np.asarray(action, dtype=np.int64).reshape(-1)
        if a.size == 1 and o.shape[0] > 1:
            a = np.full(o.shape[0], int(a.flat[0]), dtype=np.int64)
        z_before = self.z.detach().clone()
        with torch.no_grad():
            obs_n = torch.as_tensor(self.normalize(o))
            act_t = torch.as_tensor(a)
            pred, logit = self.net(obs_n, act_t, self.z)
            nxt = self.unnormalize((obs_n + pred).cpu().numpy())
            p = torch.sigmoid(logit).cpu().numpy().reshape(-1)
        if not torch.equal(self.z, z_before):
            raise RuntimeError("step updated context")
        return nxt.reshape(o.shape), p

    def query_loss(self, obs: np.ndarray, action: np.ndarray, nxt: np.ndarray, terminated: np.ndarray, z: torch.Tensor) -> torch.Tensor:
        obs_n, act, delta = self._tensors(obs, action, nxt)
        pred, logit = self.net(obs_n, act, z)
        term = torch.as_tensor(np.asarray(terminated, dtype=np.float32).reshape(-1))
        return nn.functional.mse_loss(pred, delta) + 0.25 * nn.functional.binary_cross_entropy_with_logits(logit, term)

    def clone_frozen(self) -> "ContextWorldModel":
        other = ContextWorldModel.create(self.net.obs_dim, self.net.n_actions, seed=0, random_encoder=self.random_encoder)
        other.encoder.load_state_dict({k: v.detach().cpu().clone() for k, v in self.encoder.state_dict().items()})
        other.net.load_state_dict({k: v.detach().cpu().clone() for k, v in self.net.state_dict().items()})
        other.copy_rms(self.obs_rms)
        other.clear_context()
        other.encoder.eval()
        other.net.eval()
        for p in list(other.encoder.parameters()) + list(other.net.parameters()):
            p.requires_grad_(False)
        return other

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "encoder": self.encoder.state_dict(),
                "net": self.net.state_dict(),
                "obs_rms": self.obs_rms.state_dict(),
                "obs_dim": self.net.obs_dim,
                "n_actions": self.net.n_actions,
                "arch": "context_film",
                "context_dim": CONTEXT_DIM,
                "trunk_hidden": TRUNK_HIDDEN,
                "random_encoder": self.random_encoder,
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "ContextWorldModel":
        payload = torch.load(path, map_location="cpu", weights_only=False)
        wm = cls.create(int(payload["obs_dim"]), int(payload["n_actions"]), seed=0, random_encoder=bool(payload.get("random_encoder")))
        wm.encoder.load_state_dict(payload["encoder"])
        wm.net.load_state_dict(payload["net"])
        wm.obs_rms.load_state_dict(payload["obs_rms"])
        wm.clear_context()
        return wm


def split_support_query(ds: TransitionDataset, rng: np.random.Generator) -> tuple[TransitionDataset, TransitionDataset]:
    eids = np.unique(ds.episode_id)
    if eids.size < 2:
        raise ValueError("support/query split needs at least two episodes")
    perm = rng.permutation(eids)
    n_sup = max(1, int(eids.size) // 2)
    sup = {int(x) for x in perm[:n_sup]}
    qry = {int(x) for x in perm[n_sup:]}
    if not qry or sup & qry:
        raise ValueError("support/query episode overlap")
    s_idx = np.array([i for i, e in enumerate(ds.episode_id) if int(e) in sup], dtype=np.int64)
    q_idx = np.array([i for i, e in enumerate(ds.episode_id) if int(e) in qry], dtype=np.int64)
    return ds.slice(s_idx), ds.slice(q_idx)


def train_context_model(
    model: ContextWorldModel,
    tasks: list[TransitionDataset],
    *,
    updates: int,
    seed: int,
    batch: int = 64,
    empty_prob: float = EMPTY_CONTEXT_PROB,
) -> dict[str, Any]:
    """One task per update. Support and query are episode-disjoint. z is not detached."""
    rng = np.random.default_rng(int(seed))
    params = [p for p in list(model.encoder.parameters()) + list(model.net.parameters()) if p.requires_grad]
    opt = torch.optim.Adam(params, lr=1e-3)
    before = torch.cat([p.detach().flatten().clone() for p in model.encoder.parameters()])
    grad_norms: list[float] = []
    n_query = 0
    n_support = 0
    for step in range(int(updates)):
        ds = tasks[int(rng.integers(0, len(tasks)))]
        support, query = split_support_query(ds, rng)
        q_idx = rng.choice(len(query), size=min(int(batch), len(query)), replace=False)
        q = query.slice(np.asarray(q_idx, dtype=np.int64))
        use_empty = bool(rng.random() < float(empty_prob))
        model.net.train()
        if use_empty:
            z = torch.zeros(CONTEXT_DIM)
            n_support += 0
        else:
            s_n = min(len(support), MAX_CONTEXT)
            s = support.slice(np.arange(s_n))
            z = model.encode(s.obs, s.action, s.next_obs, differentiable=not model.random_encoder)
            n_support += int(s_n)
        loss = model.query_loss(q.obs, q.action, q.next_obs, q.terminated, z)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        g = 0.0
        for p in model.encoder.parameters():
            if p.grad is not None:
                g += float(p.grad.detach().norm().item())
        grad_norms.append(g)
        nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        n_query += len(q)
        del step
    after = torch.cat([p.detach().flatten() for p in model.encoder.parameters()])
    model.clear_context()
    model.encoder.eval()
    model.net.eval()
    return {
        "optimizer_updates": int(updates),
        "query_examples": int(n_query),
        "support_examples": int(n_support),
        "mean_encoder_grad_norm": float(np.mean(grad_norms)) if grad_norms else 0.0,
        "encoder_l2_delta": float(torch.linalg.vector_norm(after - before).item()),
        "random_encoder": bool(model.random_encoder),
    }
