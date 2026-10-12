#!/usr/bin/env python3
"""Pendulum-v1 cross-environment test. Does not overwrite V0.8.x artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.cross_env import run_cross_environment_benchmark


def main() -> None:
    assert Path("artifacts/v089_learning.json").exists()
    out = run_cross_environment_benchmark(
        n_model_seeds=10,
        artifact_path="artifacts/cross_environment.json",
        checkpoint_dir="checkpoints/cross_env",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("returns", json.dumps(out["returns"], indent=2, default=str))
    print("paired", json.dumps(out["paired"], indent=2, default=str))
    print("prediction", json.dumps(out["prediction"], indent=2, default=str))
    print("h1_mpc_beats_random", out["h1_mpc_beats_random"])
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
