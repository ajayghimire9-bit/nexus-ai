"""Validation-only architecture selection. Test data must not be an argument."""

from __future__ import annotations

from typing import Any, Mapping

from nexus.world.data import TransitionDataset
from nexus.world.train import one_step_errors


def choose_kind_by_val(val_mae: Mapping[str, float]) -> str:
    if not val_mae:
        raise ValueError("empty val_mae")
    return min(val_mae.items(), key=lambda kv: (float(kv[1]), kv[0]))[0]


def val_errors(models: Mapping[str, Any], val: TransitionDataset) -> dict[str, float]:
    """MAE on the validation split only."""
    return {name: float(one_step_errors(model, val)["mae"]) for name, model in models.items()}


def select_winner(models: Mapping[str, Any], val: TransitionDataset, test: Any | None = None) -> tuple[str, dict[str, float]]:
    """Select a dynamics kind from validation MAE. A test split argument is rejected."""
    if test is not None:
        raise RuntimeError("test metrics must not be accessed during selection")
    scores = val_errors(models, val)
    return choose_kind_by_val(scores), scores
