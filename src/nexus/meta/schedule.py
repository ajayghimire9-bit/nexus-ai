from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Callable

from nexus.meta.schema import ACTION_KINDS, ExperimentAction

MAX_PROPOSE_ATTEMPTS = 32

FillFn = Callable[[str, dict[str, Any], dict[str, Any], random.Random], ExperimentAction]


def reject_reason(
    action: ExperimentAction,
    *,
    seen: set[str],
    remaining_steps: int,
    champion_exists: bool,
) -> str | None:
    """Return a rejection code, or None if the action may run.

    Rejections must not consume an experiment slot.
    """
    try:
        fp = action.fingerprint()
    except Exception as exc:  # noqa: BLE001
        return f"invalid_schema:{exc}"
    if action.env_id not in {"CartPole-v1", "Acrobot-v1"}:
        return "unsupported"
    if fp in seen:
        return "duplicate"
    cost = action.estimated_timesteps()
    if cost > remaining_steps and action.kind != "extra_evaluation":
        return "unaffordable"
    if action.kind == "extra_evaluation" and not champion_exists:
        return "impossible_no_champion"
    if remaining_steps <= 0 and action.kind != "extra_evaluation":
        return "unaffordable"
    return None


def champion_exists(champion_dir: str | Path) -> bool:
    return (Path(champion_dir) / "champion_current.pt").exists()


def ranking_cost(action: ExperimentAction, *, confirm_timesteps: int) -> int:
    """Cost used for ranking. Extra-eval is not treated as free lunch."""
    raw = action.estimated_timesteps()
    if action.kind == "extra_evaluation" or raw <= 0:
        return max(int(confirm_timesteps), 1)
    return raw


def research_value(predicted: float, cost: int, *, confirm_timesteps: int) -> float:
    """Predicted research value per unit compute."""
    return float(predicted) / (1.0 + float(cost) / float(max(confirm_timesteps, 1)))


def enumerate_candidates(
    *,
    fill: FillFn,
    state: dict[str, Any],
    limits: dict[str, Any],
    rng: random.Random,
    seen: set[str],
    remaining_steps: int,
    has_champion: bool,
    n_per_kind: int = 2,
) -> tuple[list[ExperimentAction], list[dict[str, Any]]]:
    """Build unique feasible ExperimentActions. Invalid actions never enter the set."""
    confirm_ts = int(limits["train_timesteps"])
    explore_ts = int(limits.get("explore_timesteps") or max(confirm_ts // 4, 1))
    filtered: list[dict[str, Any]] = []
    valid: list[ExperimentAction] = []
    used: set[str] = set(seen)

    def _consider(kind: str, tier: str, timesteps: int) -> None:
        lim = dict(limits)
        lim["train_timesteps"] = int(timesteps)
        n_draw = 1 if kind in {"extra_evaluation", "transfer_architecture"} else n_per_kind
        if kind == "search_learning_rate":
            n_draw = min(n_per_kind, 3)
        for _ in range(n_draw):
            action = fill(kind, state, lim, rng)
            action = ExperimentAction(
                kind=action.kind,
                env_id=action.env_id,
                architecture=action.architecture,
                learning_rate=action.learning_rate,
                train_timesteps=action.train_timesteps,
                train_seeds=action.train_seeds,
                holdout_eval_seed=action.holdout_eval_seed,
                assessment_eval_seed=action.assessment_eval_seed,
                parent_ids=action.parent_ids,
                expr=action.expr,
                notes=action.notes,
                budget_tier=tier,
            )
            why = reject_reason(
                action,
                seen=used,
                remaining_steps=remaining_steps,
                champion_exists=has_champion,
            )
            if why is not None:
                filtered.append({"reason": why, "kind": kind, "budget_tier": tier})
                continue
            used.add(action.fingerprint())
            valid.append(action)

    for kind in ACTION_KINDS:
        if kind == "extra_evaluation":
            _consider(kind, "confirm", 0)
            continue
        _consider(kind, "explore", explore_ts)
        _consider(kind, "confirm", confirm_ts)
    return valid, filtered
