#!/usr/bin/env python3
"""V0.6.2 continual / transfer benchmark. Does not overwrite V0.6 or V0.6.1 artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.cl.v062 import run_v062_benchmark


def main() -> None:
    assert Path("artifacts/v06_continual.json").exists()
    assert Path("artifacts/v061_continual.json").exists()
    out = run_v062_benchmark(
        n_seeds=3,
        source_budgets=(8_192, 32_768),
        transfer_steps=8_192,
        cl_steps_per_task=2_048,
        eval_episodes=8,
        artifact_path="artifacts/v062_continual.json",
        checkpoint_dir="checkpoints/v062",
    )
    print(json.dumps(out["protocol"], indent=2))
    print(json.dumps(out["summary"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
