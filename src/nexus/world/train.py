"""Train dynamics on collected transitions. Val only for model selection."""

from __future__ import annotations

from typing import Any

from nexus.rl.running_stats import RunningMeanStd

import numpy as np
import torch
from torch import nn

from nexus.world.data import TransitionDataset
from nexus.world.dynamics import HeadKind, WorldModel


def _batches(n: int, batch: int, rng: np.random.Generator) -> list[np.ndarray]:
    idx = rng.permutation(n)
    return [idx[i : i + batch] for i in range(0, n, batch)]


def train_world_model(
    train: TransitionDataset,
    val: TransitionDataset,
    *,
    kind: HeadKind,
    epochs: int = 40,
    batch_size: int = 128,
    lr: float = 1e-3,
    seed: int = 0,
    hidden: tuple[int, ...] = (64, 64),
    n_actions: int | None = None,
    term_weight: float = 0.25,
    obs_rms: RunningMeanStd | None = None,
    freeze_rms: bool = False,
) -> tuple[WorldModel, dict[str, Any]]:
    obs_dim = int(train.obs.shape[-1])
    inferred = int(max(int(train.action.max()) + 1 if train.action.size else 2, 2))
    n_act = int(n_actions) if n_actions is not None else inferred
    wm = WorldModel.create(obs_dim, n_act, kind=kind, hidden=hidden, seed=seed)
    if obs_rms is not None:
        wm.copy_rms(obs_rms)
    else:
        wm.fit_rms(train.obs)
    if freeze_rms:
        pass
    opt = torch.optim.Adam(wm.net.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    bce = nn.BCEWithLogitsLoss()
    rng = np.random.default_rng(seed)
    history: list[dict[str, float]] = []
    best_val = 1e18
    best_state = {k: v.detach().cpu().clone() for k, v in wm.net.state_dict().items()}

    def _tensors(ds: TransitionDataset, idx: np.ndarray | None = None) -> tuple[torch.Tensor, ...]:
        sl = slice(None) if idx is None else idx
        obs = torch.as_tensor(wm.normalize(ds.obs[sl]), dtype=torch.float32)
        nxt = torch.as_tensor(wm.normalize(ds.next_obs[sl]), dtype=torch.float32)
        act = torch.as_tensor(ds.action[sl], dtype=torch.int64)
        term = torch.as_tensor(ds.terminated[sl].astype(np.float32))
        return obs, nxt, act, term

    for epoch in range(int(epochs)):
        wm.net.train()
        tr_loss = 0.0
        n_b = 0
        for idx in _batches(len(train), batch_size, rng):
            obs, nxt, act, term = _tensors(train, idx)
            pred, logit = wm.net(obs, act)
            target = nxt - obs if kind == "residual" else nxt
            loss = loss_fn(pred, target) + term_weight * bce(logit, term)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(wm.net.parameters(), 1.0)
            opt.step()
            tr_loss += float(loss.item())
            n_b += 1
        wm.net.eval()
        with torch.no_grad():
            obs, nxt, act, term = _tensors(val)
            pred, logit = wm.net(obs, act)
            target = nxt - obs if kind == "residual" else nxt
            v_state = float(loss_fn(pred, target).item())
            v_term = float(bce(logit, term).item())
            v = v_state + term_weight * v_term
        history.append({"epoch": epoch, "train": tr_loss / max(n_b, 1), "val_state": v_state, "val_term": v_term, "val": v})
        if v < best_val:
            best_val = v
            best_state = {k: t.detach().cpu().clone() for k, t in wm.net.state_dict().items()}
    wm.net.load_state_dict(best_state)
    wm.net.eval()
    return wm, {"best_val": best_val, "history": history, "kind": kind, "epochs": epochs, "train_n": len(train), "val_n": len(val)}


def one_step_errors(wm: Any, ds: TransitionDataset) -> dict[str, Any]:
    pred, p_term = wm.step(ds.obs, ds.action)
    err = pred - ds.next_obs
    mae = np.mean(np.abs(err), axis=0)
    rmse = np.sqrt(np.mean(err**2, axis=0))
    term_acc = float(((p_term >= 0.5) == ds.terminated).mean())
    return {
        "mae_per_dim": mae.astype(float).tolist(),
        "rmse_per_dim": rmse.astype(float).tolist(),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "term_brier": float(np.mean((p_term - ds.terminated.astype(np.float64)) ** 2)),
        "term_accuracy": term_acc,
        "n": len(ds),
    }
