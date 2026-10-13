#!/usr/bin/env python3
"""Unseen-physics confirmation of the locked direct-latent rule. No retune. No control."""

from __future__ import annotations

import json

from nexus.world.direct_latent_confirmation import run_direct_latent_confirmation


def main() -> None:
    out = run_direct_latent_confirmation()
    screen = out["screen"]
    print(json.dumps({
        "confirm_evaluated": out["confirm_evaluated"],
        "control_evaluated": out["control_evaluated"],
        "declared_complete": out["declared_complete"],
        "learning_rate": out["learning_rate"],
        "updates": out["updates"],
        "screen_pass": screen.get("pass"),
        "angvel_task": screen.get("angvel_task"),
        "angvel_zero": screen.get("angvel_zero"),
        "angvel_global": screen.get("angvel_global"),
        "angvel_wrong": screen.get("angvel_wrong"),
        "angvel_encoder": screen.get("angvel_encoder"),
        "classification": out["classification"]["label"],
        "tasks_missing": out["classification"]["tasks_missing_the_point_screen"],
        "support_loss_before": out["support_loss_before"],
        "support_loss_after": out["support_loss_after"],
        "nonfinite_steps": out["nonfinite_steps"],
        "wall_clock_s": out["wall_clock_s"],
        "is_agi": False,
    }, indent=2))


if __name__ == "__main__":
    main()
