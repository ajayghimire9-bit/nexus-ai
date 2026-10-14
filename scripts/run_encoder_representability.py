#!/usr/bin/env python3
"""Representability of the saved teacher codes. No confirmation and no control."""

from __future__ import annotations

import json

from nexus.world.encoder_representability import run_encoder_representability


def main() -> None:
    out = run_encoder_representability()
    print(json.dumps({
        "decision_recorded": out.get("decision_recorded"),
        "representable": out.get("representable"),
        "threshold_met": out.get("threshold_met"),
        "chosen_learning_rate": out.get("chosen_learning_rate"),
        "rate_mean_l2": out.get("rate_mean_l2"),
        "ambiguous_decoders": out.get("ambiguous_decoders"),
        "recommendation": out.get("recommendation"),
        "confirmation_evaluated": False,
        "control_evaluated": False,
        "wall_clock_s": out.get("wall_clock_s"),
        "is_agi": False,
    }, indent=2))


if __name__ == "__main__":
    main()
