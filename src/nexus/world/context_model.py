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
        self.hidden = int(hidden)
        self.z_dim = int(z_dim)
        self.net = nn.Sequential(nn.Linear(obs_dim + n_actions + obs_dim, self.hidden), nn.Tanh(), nn.Linear(self.hidden, self.z_dim))

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
        # Exact-zero FiLM weights make d(loss)/d(z) zero on that step, so the encoder
        # gets no gradient until those weights move. They can move: d(loss)/d(W) depends
        # on z, not on W. The old no_grad context path was the persistent blockage.
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
    def create(
        cls,
        obs_dim: int,
        n_actions: int,
        *,
        seed: int = 0,
        random_encoder: bool = False,
        encoder_hidden: int = ENCODER_HIDDEN,
        context_dim: int = CONTEXT_DIM,
        trunk_hidden: tuple[int, ...] = TRUNK_HIDDEN,
    ) -> "ContextWorldModel":
        torch.manual_seed(int(seed))
        enc = TransitionContextEncoder(obs_dim, n_actions, hidden=int(encoder_hidden), z_dim=int(context_dim))
        net = ContextResidualDynamics(obs_dim, n_actions, hidden=tuple(int(h) for h in trunk_hidden), z_dim=int(context_dim))
        if random_encoder:
            for p in enc.parameters():
                p.requires_grad_(False)
        z = torch.zeros(int(context_dim))
        return cls(encoder=enc, net=net, obs_rms=RunningMeanStd((obs_dim,)), device=torch.device("cpu"), z=z, random_encoder=bool(random_encoder))

    def n_parameters(self) -> int:
        return sum(int(p.numel()) for p in list(self.encoder.parameters()) + list(self.net.parameters()))

    def trainable_parameters(self) -> int:
        return sum(int(p.numel()) for p in list(self.encoder.parameters()) + list(self.net.parameters()) if p.requires_grad)

    def copy_rms(self, other: RunningMeanStd) -> None:
        self.obs_rms.load_state_dict(other.state_dict())

    def context_dim(self) -> int:
        return int(self.encoder.z_dim)

    def clear_context(self) -> None:
        """Drop the current task vector. A loaded checkpoint starts cleared on purpose."""
        self.z = torch.zeros(self.context_dim())

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
            z = torch.zeros(self.context_dim())
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

    def clone_trainable(self) -> "ContextWorldModel":
        other = ContextWorldModel.create(
            self.net.obs_dim,
            self.net.n_actions,
            seed=0,
            random_encoder=self.random_encoder,
            encoder_hidden=self.encoder.hidden,
            context_dim=self.context_dim(),
            trunk_hidden=self.net.hidden,
        )
        other.encoder.load_state_dict({k: v.detach().cpu().clone() for k, v in self.encoder.state_dict().items()})
        other.net.load_state_dict({k: v.detach().cpu().clone() for k, v in self.net.state_dict().items()})
        other.copy_rms(self.obs_rms)
        other.clear_context()
        for src, dst in zip(self.encoder.parameters(), other.encoder.parameters()):
            dst.requires_grad_(bool(src.requires_grad))
        return other

    def clone_frozen(self) -> "ContextWorldModel":
        other = self.clone_trainable()
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
                "obs_dim": int(self.net.obs_dim),
                "n_actions": int(self.net.n_actions),
                "arch": "context_film",
                "encoder_hidden": int(self.encoder.hidden),
                "context_dim": int(self.context_dim()),
                "trunk_hidden": tuple(int(h) for h in self.net.hidden),
                "random_encoder": bool(self.random_encoder),
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "ContextWorldModel":
        """Restore architecture from the payload. Target context is cleared on purpose.

        A reusable checkpoint must not keep the previous task's z. Defaults match the
        original pilot (encoder 32, context 8, trunk 48×48) when those keys are absent.
        Hidden sizes are also inferred from the encoder tensors when the key is missing.
        """
        payload = torch.load(path, map_location="cpu", weights_only=False)
        enc_state = payload["encoder"]
        inferred_hidden = int(enc_state["net.0.weight"].shape[0])
        inferred_z = int(enc_state["net.2.weight"].shape[0])
        trunk = payload.get("trunk_hidden") or TRUNK_HIDDEN
        wm = cls.create(
            int(payload["obs_dim"]),
            int(payload["n_actions"]),
            seed=0,
            random_encoder=bool(payload.get("random_encoder", False)),
            encoder_hidden=int(payload.get("encoder_hidden") or inferred_hidden),
            context_dim=int(payload.get("context_dim") or inferred_z),
            trunk_hidden=tuple(int(h) for h in trunk),
        )
        wm.encoder.load_state_dict(enc_state)
        wm.net.load_state_dict(payload["net"])
        wm.obs_rms.load_state_dict(payload["obs_rms"])
        if wm.random_encoder:
            for p in wm.encoder.parameters():
                p.requires_grad_(False)
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


LENGTH_SEED_OFFSET = 10_007
VARIABLE_SUPPORT_LENGTHS = (16, 32, 64, 128)


def make_context_schedule(
    tasks: list[TransitionDataset],
    *,
    updates: int,
    seed: int,
    batch: int = 64,
    empty_prob: float = EMPTY_CONTEXT_PROB,
) -> list[dict[str, Any]]:
    """Pair two learners on one schedule.

    `seed` chooses the task, the episode split, the query minibatch, and the empty draw.
    Support length uses `seed + LENGTH_SEED_OFFSET` and is drawn only on non-empty steps,
    so length sampling cannot change the rest of the schedule.
    """
    sched = np.random.default_rng(int(seed))
    length_rng = np.random.default_rng(int(seed) + LENGTH_SEED_OFFSET)
    rows: list[dict[str, Any]] = []
    for _step in range(int(updates)):
        task_index = int(sched.integers(0, len(tasks)))
        ds = tasks[task_index]
        eids = np.unique(ds.episode_id)
        if eids.size < 2:
            raise ValueError("support/query split needs at least two episodes")
        perm = sched.permutation(eids)
        n_sup = max(1, int(eids.size) // 2)
        sup = {int(x) for x in perm[:n_sup]}
        qry = {int(x) for x in perm[n_sup:]}
        if not qry or sup & qry:
            raise ValueError("support/query episode overlap")
        sup_idx = np.flatnonzero(np.isin(ds.episode_id, np.fromiter(sup, dtype=np.int64))).astype(np.int64)
        qry_idx = np.flatnonzero(np.isin(ds.episode_id, np.fromiter(qry, dtype=np.int64))).astype(np.int64)
        q_idx = np.asarray(sched.choice(qry_idx, size=min(int(batch), int(qry_idx.size)), replace=False), dtype=np.int64)
        empty = bool(sched.random() < float(empty_prob))
        variable_length = None if empty else int(length_rng.choice(np.asarray(VARIABLE_SUPPORT_LENGTHS, dtype=np.int64)))
        rows.append(
            {
                "task_index": task_index,
                "support_index": sup_idx,
                "query_index": q_idx,
                "empty": empty,
                "variable_length": variable_length,
            }
        )
    return rows


def support_take(row: dict[str, Any], mode: str) -> np.ndarray:
    """Prefix of the eligible support history. Variable length never sees rows the fixed run skips."""
    idx = np.asarray(row["support_index"], dtype=np.int64)
    if row["empty"]:
        return idx[:0]
    if mode == "fixed":
        n = min(int(idx.size), MAX_CONTEXT)
    elif mode == "variable":
        n = min(int(idx.size), int(row["variable_length"]), MAX_CONTEXT)
    else:
        raise ValueError(mode)
    return idx[:n]


def train_context_model(
    model: ContextWorldModel,
    tasks: list[TransitionDataset],
    *,
    updates: int,
    seed: int,
    batch: int = 64,
    empty_prob: float = EMPTY_CONTEXT_PROB,
    support_mode: str = "fixed",
    schedule: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One task per update. Support and query are episode-disjoint. z is not detached.

    `support_mode='fixed'` is the original pilot: empty with probability 0.2, otherwise 128 rows.
    `support_mode='variable'` uses the scheduled length in {16, 32, 64, 128} on the same rows.
    """
    if support_mode not in ("fixed", "variable"):
        raise ValueError(support_mode)
    rows = schedule if schedule is not None else make_context_schedule(
        tasks, updates=updates, seed=seed, batch=batch, empty_prob=empty_prob
    )
    if len(rows) != int(updates):
        raise ValueError("schedule length does not match the update budget")
    params = [p for p in list(model.encoder.parameters()) + list(model.net.parameters()) if p.requires_grad]
    opt = torch.optim.Adam(params, lr=1e-3)
    before = torch.cat([p.detach().flatten().clone() for p in model.encoder.parameters()])
    grad_norms: list[float] = []
    n_query = 0
    n_support = 0
    hist: dict[str, int] = {"empty": 0, "16": 0, "32": 0, "64": 0, "128": 0}
    for row in rows:
        ds = tasks[int(row["task_index"])]
        q = ds.slice(np.asarray(row["query_index"], dtype=np.int64))
        take = support_take(row, support_mode)
        model.net.train()
        if take.size == 0:
            z = torch.zeros(model.context_dim())
            hist["empty"] += 1
        else:
            s = ds.slice(take)
            if set(np.unique(s.episode_id).tolist()) & set(np.unique(q.episode_id).tolist()):
                raise RuntimeError("support and query episodes overlap")
            z = model.encode(s.obs, s.action, s.next_obs, differentiable=not model.random_encoder)
            n_support += int(take.size)
            hist[str(int(take.size) if int(take.size) in (16, 32, 64, 128) else "128")] += 1
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
    after = torch.cat([p.detach().flatten() for p in model.encoder.parameters()])
    model.clear_context()
    model.encoder.eval()
    model.net.eval()
    return {
        "optimizer_updates": int(updates),
        "query_examples": int(n_query),
        "support_examples": int(n_support),
        "support_mode": support_mode,
        "support_length_counts": hist,
        "mean_encoder_grad_norm": float(np.mean(grad_norms)) if grad_norms else 0.0,
        "encoder_l2_delta": float(torch.linalg.vector_norm(after - before).item()),
        "random_encoder": bool(model.random_encoder),
    }
