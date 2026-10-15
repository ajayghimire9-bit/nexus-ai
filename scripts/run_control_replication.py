#!/usr/bin/env python3
"""Ten-decoder H=16 replication. No retune and no learning-to-learn claim."""

from __future__ import annotations

import json

from nexus.world.control_replication import run_control_replication


def main() -> None:
    out = run_control_replication()
    print(json.dumps({
        "decision_recorded": out.get("decision_recorded"),
        "objective_met": out.get("objective_met"),
        "gate_pass": out.get("gate_pass"),
        "replication_gate_pass": out.get("replication_gate_pass"),
        "fresh_gate_pass": out.get("fresh_gate_pass"),
        "independent_decoder_count": out.get("independent_decoder_count"),
        "means": out.get("means"),
        "recommendation": out.get("recommendation"),
        "exploratory": out.get("exploratory"),
        "wall_clock_s": out.get("wall_clock_s"),
        "is_agi": False,
        "is_learning_to_learn": False,
    }, indent=2))


if __name__ == "__main__":
    main()
