from __future__ import annotations

from pathlib import Path
from typing import Any

from nexus.meta.schema import ExperimentAction

MAX_PROPOSE_ATTEMPTS = 32


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
