#!/usr/bin/env python3
"""Amortized latent-inference pilot. No MPC. No retune of the locked teacher."""

from __future__ import annotations

import json

from nexus.world.amortized_latent import run_amortized_latent


def main() -> None:
    out = run_amortized_latent()
    dev = out["development"]
    confirm = out["confirmation"] or {}
    print(json.dumps({
        "selection_recorded": dev.get("selection_recorded"),
        "gate_pass": dev.get("gate_pass"),
        "chosen_lambda": dev.get("chosen_lambda"),
        "chosen_epoch": dev.get("chosen_epoch"),
        "chosen_budget": dev.get("chosen_budget"),
        "means": dev.get("means"),
        "recovery_fraction": dev.get("recovery_fraction"),
        "confirm_evaluated": dev.get("confirm_evaluated"),
        "confirm_means": confirm.get("means"),
        "confirm_beats_zero": confirm.get("beats_zero"),
        "confirm_beats_encoder": confirm.get("beats_encoder"),
        "control_evaluated": False,
        "wall_clock_s": dev.get("wall_clock_s"),
        "is_agi": False,
    }, indent=2))


if __name__ == "__main__":
    main()
