"""Regularized linear recovery scoring. Source-only updates. No LM fine-tune.

Does not feed task IDs, hidden families, reference operators or answers.
Untried actions are not labeled failures. Reset/shuffle are controls.
"""
from __future__ import annotations

import random
from typing import Any

import numpy as np

from .capability_evidence import digest
from .recovery_actions import ACTIONS, FEATURE_NAMES, available_actions, feature_vector

L2 = 1.0


def zero_weights() -> dict[str, list[float]]:
    return {action: [0.0] * len(FEATURE_NAMES) for action in ACTIONS}


def score_action(weights: dict[str, list[float]], action: str, feats: dict[str, float]) -> float:
    vec = feature_vector(feats)
    w = weights[action]
    return float(sum(a * b for a, b in zip(w, vec)))


def select_action(weights: dict[str, list[float]], feats: dict[str, float],
                  available: list[str], *, rng: random.Random | None = None,
                  explore: float = 0.0) -> dict[str, Any]:
    scores = {action: score_action(weights, action, feats) for action in available}
    if rng is not None and explore > 0 and rng.random() < explore:
        chosen = rng.choice(available)
        reason = "explore"
    else:
        best = max(scores.values())
        tied = [action for action, value in scores.items() if value == best]
        chosen = sorted(tied)[0] if rng is None else rng.choice(tied)
        reason = "greedy"
    return dict(
        selected=chosen,
        scores=scores,
        available=list(available),
        reason=reason,
        features=dict(feats),
    )


def fit_source(rows: list[dict[str, Any]], *, l2: float = L2) -> dict[str, list[float]]:
    """Fit one linear scorer per action from tried source rows only."""
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
        if row.get("first_action") and row.get("label"):
            counts[row["action"]] += 1
    return sorted(ACTIONS, key=lambda action: (-counts[action], ACTIONS.index(action)))


def fixed_diagnostic(feats: dict[str, float], available: list[str]) -> str:
    if feats.get("exc_type_error") or feats.get("exc_key_error") or feats.get("exc_attr_error"):
        if "INSPECT_SCHEMA" in available:
            return "INSPECT_SCHEMA"
    if feats.get("docs_available") and "RETRIEVE_DOCS" in available:
        return "RETRIEVE_DOCS"
    if feats.get("teacher_available") and feats.get("mismatch_rate", 0) > 0 and "REQUEST_DISTINGUISHING_EXAMPLE" in available:
        return "REQUEST_DISTINGUISHING_EXAMPLE"
    if "REVISE" in available:
        return "REVISE"
    return "STOP_UNRESOLVED"


def all_cheap_first(feats: dict[str, float], available: list[str]) -> str:
    for action in ("INSPECT_SCHEMA", "RETRIEVE_DOCS", "REQUEST_DISTINGUISHING_EXAMPLE"):
        if action in available:
            return action
    if "REVISE" in available:
        return "REVISE"
    return "STOP_UNRESOLVED"


def immediate_revise(available: list[str]) -> str:
    if "REVISE" in available:
        return "REVISE"
    return "STOP_UNRESOLVED"


def source_frequency(order: list[str], available: list[str]) -> str:
    for action in order:
        if action in available:
            return action
    return "STOP_UNRESOLVED"


def choose(method: str, feats: dict[str, float], available: list[str],
           weights: dict[str, list[float]], freq: list[str]) -> dict[str, Any]:
    if method == "immediate_revise":
        selected = immediate_revise(available)
    elif method == "fixed_diagnostic":
        selected = fixed_diagnostic(feats, available)
    elif method == "source_frequency":
        selected = source_frequency(freq, available)
    elif method == "all_cheap_first":
        selected = all_cheap_first(feats, available)
    elif method in ("learned", "reset_policy", "shuffled_policy"):
        return select_action(weights, feats, available)
    else:
        raise ValueError("unknown_method")
    scores = {action: float(action == selected) for action in available}
    return dict(selected=selected, scores=scores, available=list(available),
                reason="rule", features=dict(feats))
