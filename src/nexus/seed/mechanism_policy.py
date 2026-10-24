"""Regularized linear investigation scoring. Source-only updates. Not the failed symbolic φ.

Ties are randomized. Alphabetical min is never used.
"""
from __future__ import annotations

import random
from typing import Any

import numpy as np

from .capability_evidence import digest
from .mechanism_investigate import FEATURE_NAMES, feature_vector
from .mechanism_world import ACTIONS

L2 = 1.0


def zero_weights() -> dict[str, list[float]]:
    return {action: [0.0] * len(FEATURE_NAMES) for action in ACTIONS}


def score_action(weights: dict[str, list[float]], action: str, feats: dict[str, float]) -> float:
    return float(sum(a * b for a, b in zip(weights[action], feature_vector(feats))))


def select_action(weights: dict[str, list[float]], feats: dict[str, float],
                  available: list[str], rng: random.Random) -> dict[str, Any]:
    scores = {action: score_action(weights, action, feats) for action in available}
    best = max(scores.values())
    tied = [action for action, value in scores.items() if value == best]
    chosen = rng.choice(tied)
    return dict(
        selected=chosen,
        scores=scores,
        available=list(available),
        reason="random_tie" if len(tied) > 1 else "greedy",
        features=dict(feats),
    )


def fit_source(rows: list[dict[str, Any]], *, l2: float = L2) -> dict[str, list[float]]:
    weights = zero_weights()
    for action in ACTIONS:
        xs = []
        ys = []
        for row in rows:
            if row["action"] != action:
                continue
            xs.append(feature_vector(row["features"]))
            ys.append(float(row["label"]))
        if not xs:
            continue
        x = np.asarray(xs, dtype=float)
        y = np.asarray(ys, dtype=float)
        xtx = x.T @ x + l2 * np.eye(x.shape[1])
        weights[action] = np.linalg.solve(xtx, x.T @ y).tolist()
    return weights


def policy_hash(weights: dict[str, list[float]]) -> str:
    return digest({action: [round(v, 8) for v in weights[action]] for action in ACTIONS})


def reset_weights(_weights: dict[str, list[float]] | None = None) -> dict[str, list[float]]:
    return zero_weights()


def shuffle_weights(weights: dict[str, list[float]], seed: int) -> dict[str, list[float]]:
    rng = random.Random(seed)
    order = list(ACTIONS)
    rng.shuffle(order)
    return {action: list(weights[order[i]]) for i, action in enumerate(ACTIONS)}


def frequency_order(rows: list[dict[str, Any]]) -> list[str]:
    counts = {action: 0 for action in ACTIONS}
    for row in rows:
        if row.get("first_query"):
            counts[row["action"]] += 1
    return sorted(ACTIONS, key=lambda action: (-counts[action], ACTIONS.index(action)))


def training_rows(episode: dict[str, Any]) -> list[dict[str, Any]]:
    """IG choices are training supervision, never assessment features."""
    rows = []
    first = True
    for step in episode.get("transcript") or []:
        action = step["action"]
        if action.startswith("STOP"):
            continue
        rows.append(dict(
            action=action,
            features=dict(step["features"]),
            label=1.0,
            first_query=first,
            supervision="information_gain",
        ))
        first = False
    return rows
