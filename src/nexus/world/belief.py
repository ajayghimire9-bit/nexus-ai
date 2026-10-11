"""Belief-state estimators. Inference never reads the simulator latent state.

Kalman assumptions (documented): independent scalar filters per CartPole coordinate,
A=I, H=I, random-walk process noise Q, isotropic observation noise R. This is not
the true CartPole linearization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import torch
from torch import nn

from nexus.world.data import TransitionDataset, episodes_from
from nexus.world.dynamics import WorldModel
from nexus.world.train import train_world_model


class BeliefEstimator(Protocol):
    name: str
    dim: int
    uses_privileged_state: bool

    def reset(self) -> None: ...
    def observe(self, obs: np.ndarray, action: int | None = None) -> np.ndarray: ...


class IdentityBelief:
    name = "identity"
    dim = 4
    uses_privileged_state = False

    def reset(self) -> None:
        return None

    def observe(self, obs: np.ndarray, action: int | None = None) -> np.ndarray:
        del action
        return np.asarray(obs, dtype=np.float32).reshape(-1)[:4]


class EMABelief:
    """b_t = alpha * b_{t-1} + (1-alpha) * o_t. Frozen alpha; not tuned on confirmation."""

    name = "ema"
    dim = 4
    uses_privileged_state = False

    def __init__(self, alpha: float = 0.6) -> None:
        self.alpha = float(alpha)
        self._b: np.ndarray | None = None

    def reset(self) -> None:
        self._b = None

    def observe(self, obs: np.ndarray, action: int | None = None) -> np.ndarray:
        del action
        o = np.asarray(obs, dtype=np.float32).reshape(-1)[:4]
        if self._b is None:
            self._b = o.copy()
        else:
            self._b = self.alpha * self._b + (1.0 - self.alpha) * o
        return self._b.astype(np.float32)


class ScalarKalmanBelief:
    """Independent 1-D Kalman filters. A=I, H=I, Q=q, R=r. Not CartPole physics."""

    name = "kalman"
    dim = 4
    uses_privileged_state = False

    def __init__(self, q: float = 1e-4, r: float = 0.01) -> None:
        self.q = float(q)
        self.r = float(r)
        self._x: np.ndarray | None = None
        self._p: np.ndarray | None = None

    def reset(self) -> None:
        self._x = None
        self._p = None

    def observe(self, obs: np.ndarray, action: int | None = None) -> np.ndarray:
        del action
        z = np.asarray(obs, dtype=np.float64).reshape(-1)[:4]
        if self._x is None:
            self._x = z.copy()
            self._p = np.ones(4, dtype=np.float64)
            return self._x.astype(np.float32)
        self._p = self._p + self.q
        k = self._p / (self._p + self.r)
        self._x = self._x + k * (z - self._x)
        self._p = (1.0 - k) * self._p
        return self._x.astype(np.float32)


class StackBelief:
    """Last ``k`` observations concatenated. Same raw sensors; no privileged state."""

    name = "stack"
    uses_privileged_state = False

    def __init__(self, k: int = 3, obs_dim: int = 4) -> None:
        self.k = int(k)
        self.obs_dim = int(obs_dim)
        self.dim = self.k * self.obs_dim
        self._buf: list[np.ndarray] = []

    def reset(self) -> None:
        self._buf = []

    def observe(self, obs: np.ndarray, action: int | None = None) -> np.ndarray:
        del action
        o = np.asarray(obs, dtype=np.float32).reshape(-1)[: self.obs_dim]
        self._buf.append(o)
        if len(self._buf) > self.k:
            self._buf = self._buf[-self.k :]
        pad = [self._buf[0]] * (self.k - len(self._buf))
        return np.concatenate(pad + self._buf, axis=0).astype(np.float32)


class GRUBelief(nn.Module):
    """Small GRU maps (obs, action) history to a 4-D belief. Hidden size 16."""

    name = "gru"
    dim = 4
    uses_privileged_state = False

    def __init__(self, obs_dim: int = 4, n_actions: int = 2, hidden: int = 16) -> None:
        super().__init__()
        self.obs_dim = obs_dim
        self.n_actions = n_actions
        self.hidden_size = hidden
        self.gru = nn.GRU(obs_dim + n_actions, hidden, batch_first=True)
        self.out = nn.Linear(hidden, obs_dim)
        self._h: torch.Tensor | None = None

    def reset(self) -> None:
        self._h = None

    def observe(self, obs: np.ndarray, action: int | None = None) -> np.ndarray:
        self.eval()
        o = torch.as_tensor(np.asarray(obs, dtype=np.float32).reshape(1, 1, -1)[..., : self.obs_dim])
        a = 0 if action is None else int(action)
        oh = torch.nn.functional.one_hot(torch.tensor([a]), num_classes=self.n_actions).float().view(1, 1, -1)
        with torch.no_grad():
            y, self._h = self.gru(torch.cat([o, oh], dim=-1), self._h)
            b = self.out(y.squeeze(1))
        return b.cpu().numpy().reshape(-1).astype(np.float32)


def train_gru_belief(
    train: TransitionDataset,
    val: TransitionDataset,
    *,
    epochs: int = 12,
    seed: int = 0,
) -> tuple[GRUBelief, dict[str, Any]]:
    torch.manual_seed(seed)
    net = GRUBelief()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    eps_tr = episodes_from(train)
    eps_va = episodes_from(val)
    best = 1e18
    best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
    for _ in range(int(epochs)):
        net.train()
        for ep in eps_tr:
            if ep["obs"].shape[0] < 2:
                continue
            obs = torch.as_tensor(ep["obs"][:-1])
            nxt = torch.as_tensor(ep["next_obs"][:-1])
            act = torch.as_tensor(ep["action"][:-1], dtype=torch.int64)
            oh = torch.nn.functional.one_hot(act, num_classes=2).float()
            x = torch.cat([obs, oh], dim=-1).unsqueeze(0)
            pred, _h = net.gru(x)
            pred_o = net.out(pred.squeeze(0))
            loss = loss_fn(pred_o, nxt)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            vs = []
            for ep in eps_va:
                if ep["obs"].shape[0] < 2:
                    continue
                obs = torch.as_tensor(ep["obs"][:-1])
                nxt = torch.as_tensor(ep["next_obs"][:-1])
                act = torch.as_tensor(ep["action"][:-1], dtype=torch.int64)
                oh = torch.nn.functional.one_hot(act, num_classes=2).float()
                pred, _h = net.gru(torch.cat([obs, oh], dim=-1).unsqueeze(0))
                vs.append(float(loss_fn(net.out(pred.squeeze(0)), nxt).item()))
            v = float(np.mean(vs)) if vs else 1e18
        if v < best:
            best = v
            best_state = {k: t.detach().cpu().clone() for k, t in net.state_dict().items()}
    net.load_state_dict(best_state)
    net.eval()
    return net, {"best_val": best, "epochs": epochs}


def make_estimator(name: str, *, gru: GRUBelief | None = None) -> BeliefEstimator:
    if name == "identity":
        return IdentityBelief()
    if name == "ema":
        return EMABelief(alpha=0.6)
    if name == "kalman":
        return ScalarKalmanBelief(q=1e-4, r=0.01)
    if name == "stack":
        return StackBelief(k=3)
    if name == "gru":
        if gru is None:
            raise ValueError("gru estimator requires a trained GRUBelief")
        gru.reset()
        return gru
    raise ValueError(name)


def beliefs_from_dataset(est: BeliefEstimator, ds: TransitionDataset) -> TransitionDataset:
    """Replay each episode through ``est``. No simulator access."""
    obs_l: list[np.ndarray] = []
    nxt_l: list[np.ndarray] = []
    act_keep: list[int] = []
    rew_keep: list[float] = []
    term_keep: list[bool] = []
    trunc_keep: list[bool] = []
    seed_keep: list[int] = []
    ep_keep: list[int] = []
    pol_keep: list[str] = []
    for eid in np.unique(ds.episode_id):
        idx = np.where(ds.episode_id == eid)[0]
        est.reset()
        seq: list[np.ndarray] = []
        for j, i in enumerate(idx):
            seq.append(est.observe(ds.obs[i], int(ds.action[i]) if j else None).copy())
        last_i = int(idx[-1])
        nb_last = est.observe(ds.next_obs[last_i], int(ds.action[last_i])).copy()
        for j, i in enumerate(idx):
            nb = seq[j + 1] if j + 1 < len(seq) else nb_last
            obs_l.append(seq[j])
            nxt_l.append(nb)
            act_keep.append(int(ds.action[i]))
            rew_keep.append(float(ds.reward[i]))
            term_keep.append(bool(ds.terminated[i]))
            trunc_keep.append(bool(ds.truncated[i]))
            seed_keep.append(int(ds.seed[i]))
            ep_keep.append(int(ds.episode_id[i]))
            pol_keep.append(str(ds.policy[i]))
    return TransitionDataset(
        obs=np.stack(obs_l, axis=0),
        action=np.asarray(act_keep, dtype=np.int64),
        next_obs=np.stack(nxt_l, axis=0),
        reward=np.asarray(rew_keep, dtype=np.float32),
        terminated=np.asarray(term_keep, dtype=np.bool_),
        truncated=np.asarray(trunc_keep, dtype=np.bool_),
        task_id=ds.task_id,
        seed=np.asarray(seed_keep, dtype=np.int64),
        episode_id=np.asarray(ep_keep, dtype=np.int64),
        policy=np.asarray(pol_keep),
        physics=dict(ds.physics),
        env_interactions=ds.env_interactions,
        notes={"belief": getattr(est, "name", "belief")},
    )


def train_belief_model(
    name: str,
    train: TransitionDataset,
    val: TransitionDataset,
    *,
    epochs: int,
    seed: int,
    gru: GRUBelief | None = None,
) -> tuple[BeliefEstimator, WorldModel, dict[str, Any]]:
    est = make_estimator(name, gru=gru)
    btr = beliefs_from_dataset(est, train)
    bva = beliefs_from_dataset(est, val)
    wm, log = train_world_model(btr, bva, kind="residual", epochs=epochs, seed=seed, hidden=(64, 64))  # type: ignore[arg-type]
    return est, wm, {"belief": name, "dim": est.dim, **{k: v for k, v in log.items() if k != "history"}}


@dataclass
class BeliefStepModel:
    """Planner interface: step(belief, action) -> next_belief. No env."""

    wm: WorldModel
    uses_simulator: bool = False
    uses_privileged_physics: bool = False

    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return self.wm.step(obs, action)
