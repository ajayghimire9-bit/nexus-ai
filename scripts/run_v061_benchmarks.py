#!/usr/bin/env python3
"""V0.6.1 continual / transfer benchmark. Does not overwrite V0.6 artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.cl.v061 import run_v061_benchmark


def main() -> None:
    assert Path("artifacts/v06_continual.json").exists()
    out = run_v061_benchmark(
        n_seeds=3,
        steps_per_task=8192,
        specialist_budgets=(2048, 8192, 16384),
        eval_episodes=8,
        artifact_path="artifacts/v061_continual.json",
        checkpoint_dir="checkpoints/v061",
    )
    print(json.dumps(out["protocol"], indent=2))
    print(json.dumps(out["summary"], indent=2, default=str))


if __name__ == "__main__":
    main()
