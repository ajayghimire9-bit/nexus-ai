#!/usr/bin/env python3
"""V0.6.3 adaptation-selector benchmark. Does not overwrite V0.6–V0.6.2 artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.cl.v063 import run_v063_benchmark


def main() -> None:
    for name in ("v06_continual.json", "v061_continual.json", "v062_continual.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v063_benchmark(
        n_seeds=3,
        source_budgets=(8_192, 32_768),
        transfer_steps=4_096,
        eval_episodes=8,
        artifact_path="artifacts/v063_adaptation.json",
        checkpoint_dir="checkpoints/v063",
    )
    print(json.dumps(out["protocol"], indent=2))
    print(json.dumps(out["summary"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
