"""Small dynamics ensemble. Disagreement is not assumed calibrated."""

from __future__ import annotations

from typing import Any

import numpy as np

from nexus.world.data import TransitionDataset
from nexus.world.dynamics import WorldModel
from nexus.world.train import train_world_model


def train_ensemble(
    train: TransitionDataset,
    val: TransitionDataset,
    *,
    n_members: int = 3,
    kind: str = "residual",
    epochs: int = 20,
    seed: int = 0,
) -> tuple[list[WorldModel], dict[str, Any]]:
    members = []
    logs = []
    for i in range(n_members):
        wm, log = train_world_model(train, val, kind=kind, epochs=epochs, seed=seed + 17 * (i + 1))  # type: ignore[arg-type]
        members.append(wm)
        logs.append({"member": i, "best_val": log["best_val"]})
    return members, {"n": n_members, "members": logs}


def disagreement_and_error(members: list[WorldModel], ds: TransitionDataset) -> dict[str, Any]:
    preds = []
    for m in members:
        nxt, _ = m.step(ds.obs, ds.action)
        preds.append(nxt)
    stack = np.stack(preds, axis=0)
    mean = stack.mean(axis=0)
    std = stack.std(axis=0).mean(axis=-1)
    err = np.mean(np.abs(mean - ds.next_obs), axis=-1)
    if std.size < 3:
        corr = 0.0
    else:
        corr = float(np.corrcoef(std, err)[0, 1])
        if not np.isfinite(corr):
            corr = 0.0
    return {
        "mean_disagreement": float(std.mean()),
        "mean_mae": float(err.mean()),
        "error_vs_std_corr": corr,
        "calibrated_claim": False,
        "n": len(ds),
    }
