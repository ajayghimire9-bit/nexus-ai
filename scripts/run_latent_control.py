#!/usr/bin/env python3
"""H=16 MPC with the frozen epoch-200 encoder. No retune and no learning-to-learn claim."""

from __future__ import annotations

import json

from nexus.world.latent_control import run_latent_control


def main() -> None:
    out = run_latent_control()
    print(json.dumps({
        "decision_recorded": out.get("decision_recorded"),
        "gate_pass": out.get("gate_pass"),
        "inconclusive": out.get("inconclusive"),
        "means": out.get("means"),
        "gains_across_tasks": out.get("gains_across_tasks"),
        "gains_concentrated": out.get("gains_concentrated"),
        "recommendation": out.get("recommendation"),
        "control_evaluated": out.get("control_evaluated"),
        "wall_clock_s": out.get("wall_clock_s"),
        "is_agi": False,
        "is_learning_to_learn": False,
    }, indent=2))


if __name__ == "__main__":
    main()
