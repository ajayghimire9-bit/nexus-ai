#!/usr/bin/env python3
"""Retrain the locked encoder, then score the new confirmation split. No MPC."""

from __future__ import annotations

import json

from nexus.world.latent_generalization_confirmation import run_latent_generalization_confirmation


def main() -> None:
    out = run_latent_generalization_confirmation()
    print(json.dumps({
        "decision_recorded": out.get("decision_recorded"),
        "gate_pass": out.get("gate_pass"),
        "means": out.get("means"),
        "task_failures": out.get("task_failures"),
        "teacher_worse_than_zero": out.get("teacher_worse_than_zero"),
        "recovery_fraction": out.get("recovery_fraction"),
        "recommendation": out.get("recommendation"),
        "confirmation_evaluated": out.get("confirmation_evaluated"),
        "control_evaluated": False,
        "wall_clock_s": out.get("wall_clock_s"),
        "is_agi": False,
        "is_learning_to_learn": False,
    }, indent=2))


if __name__ == "__main__":
    main()
