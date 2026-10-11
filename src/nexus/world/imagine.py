"""Recursive imagined rollouts. The true simulator is not queried."""

from __future__ import annotations

from typing import Any

import numpy as np

from nexus.world.data import TransitionDataset, episodes_from
from nexus.world.dynamics import WorldModel


def imagine_actions(wm: WorldModel, obs0: np.ndarray, actions: np.ndarray) -> dict[str, np.ndarray]:
    """Open-loop imagination of an action sequence from ``obs0``."""
    s = np.asarray(obs0, dtype=np.float32).reshape(-1)
    pred_states = []
    pred_term = []
    for a in np.asarray(actions, dtype=np.int64).reshape(-1):
        s, p = wm.step(s, int(a))
        s = s.reshape(-1)
        pred_states.append(s.copy())
        pred_term.append(float(np.asarray(p).reshape(-1)[0]))
    return {"states": np.stack(pred_states, axis=0), "p_term": np.asarray(pred_term, dtype=np.float64)}


def multi_step_errors(wm: WorldModel, ds: TransitionDataset, horizons: tuple[int, ...]) -> dict[str, Any]:
    """Action-conditioned open-loop error vs recorded test trajectories (oracle env already collected)."""
    eps = episodes_from(ds)
    out: dict[str, Any] = {}
    for h in horizons:
        maes = []
        last_mae = []
        term_brier = []
        n_used = 0
        for ep in eps:
            t_max = int(ep["obs"].shape[0])
            if t_max < h:
                continue
            pred = imagine_actions(wm, ep["obs"][0], ep["action"][:h])
            true = ep["next_obs"][:h]
            err = np.abs(pred["states"] - true)
            maes.append(float(err.mean()))
            last_mae.append(float(err[-1].mean()))
            term_brier.append(float(np.mean((pred["p_term"] - ep["terminated"][:h].astype(np.float64)) ** 2)))
            n_used += 1
        out[str(h)] = {
            "mean_mae": float(np.mean(maes)) if maes else None,
            "horizon_end_mae": float(np.mean(last_mae)) if last_mae else None,
            "term_brier": float(np.mean(term_brier)) if term_brier else None,
            "n_episodes": n_used,
        }
    return out


def persistence_errors(ds: TransitionDataset) -> dict[str, float]:
    err = ds.next_obs - ds.obs
    return {"mae": float(np.mean(np.abs(err))), "rmse": float(np.sqrt(np.mean(err**2))), "n": len(ds)}


def action_sensitivity(wm: WorldModel, obs0: np.ndarray, n_actions: int) -> dict[str, Any]:
    """Different first actions should yield different predictions from the same start."""
    preds = []
    for a in range(n_actions):
        nxt, _ = wm.step(obs0, a)
        preds.append(nxt.reshape(-1))
    delta = float(np.linalg.norm(preds[0] - preds[1]))
    return {"l2_action_gap": delta, "distinct": bool(delta > 1e-6)}
