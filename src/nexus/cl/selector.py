"""Bounded adaptation selector. Observes validation returns only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Strategy = Literal[
    "reuse",
    "scratch",
    "full_finetune",
    "encoder_new_heads_finetune",
    "frozen_encoder_new_heads",
    "conservative_low_lr",
]

# Frozen from V0.6.2 (low-g development). Not retuned on V0.6.3 final-test tasks.
REUSE_VAL_THRESHOLD = 350.0
CONSERVATIVE_VAL_THRESHOLD = 80.0
SOURCE_USELESS_VAL = 50.0

FROZEN_LIMIT_KEYS = ("val_seed", "independent_eval_seed", "eval_episodes", "max_target_steps")


@dataclass(frozen=True)
class AdaptationDecision:
    strategy: Strategy
    reason: str
    zero_shot_val: float
    source_val: float
    target_steps: int


class AdaptationSelector:
    """Choose reuse / conservative adapt / encoder-adapt / scratch from val probes.

    Cannot change eval seeds, episode counts, or the target-step cap.
    """

    name = "val_zero_shot_thresholds"

    def __init__(self, *, max_target_steps: int, limits: dict[str, Any]) -> None:
        self.max_target_steps = int(max_target_steps)
        self.limits = dict(limits)
        for key in FROZEN_LIMIT_KEYS:
            if key not in self.limits:
                raise ValueError(f"missing frozen limit {key}")

    def assert_limits(self, current: dict[str, Any]) -> None:
        for key in FROZEN_LIMIT_KEYS:
            if current.get(key) != self.limits[key]:
                raise RuntimeError(f"selector tried to change frozen limit {key}")

    def decide(
        self,
        *,
        zero_shot_val: float,
        source_val: float,
        current_limits: dict[str, Any],
    ) -> AdaptationDecision:
        self.assert_limits(current_limits)
        zs = float(zero_shot_val)
        src = float(source_val)
        if src < SOURCE_USELESS_VAL:
            return AdaptationDecision("scratch", "source_val_below_reuse_floor", zs, src, self.max_target_steps)
        if zs >= REUSE_VAL_THRESHOLD:
            return AdaptationDecision("reuse", "zero_shot_val_already_strong", zs, src, 0)
        if zs >= CONSERVATIVE_VAL_THRESHOLD:
            return AdaptationDecision(
                "conservative_low_lr", "zero_shot_has_signal_low_lr", zs, src, self.max_target_steps
            )
        return AdaptationDecision(
            "encoder_new_heads_finetune", "zero_shot_weak_encoder_adapt", zs, src, self.max_target_steps
        )
