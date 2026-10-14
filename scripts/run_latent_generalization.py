#!/usr/bin/env python3
"""Latent-encoder generalization pilot. No confirmation and no control sweep."""

from __future__ import annotations

import json

from nexus.world.latent_generalization import run_latent_generalization


def main() -> None:
    out = run_latent_generalization()
    print(json.dumps({
        "decision_recorded": out.get("decision_recorded"),
        "gate_pass": out.get("gate_pass"),
        "val_gate_pass": out.get("val_gate_pass"),
        "chosen_epoch": out.get("chosen_epoch"),
        "means": out.get("means"),
        "dev_checkpoint_angvel": out.get("dev_checkpoint_angvel"),
        "train_latent_l2": out.get("train_latent_l2"),
        "history_latent_l2": out.get("history_latent_l2"),
        "teacher_pair_median_l2": out.get("teacher_pair_median_l2"),
        "recommendation": out.get("recommendation"),
        "confirmation_evaluated": False,
        "control_evaluated": False,
        "wall_clock_s": out.get("wall_clock_s"),
        "is_agi": False,
    }, indent=2))


if __name__ == "__main__":
    main()
