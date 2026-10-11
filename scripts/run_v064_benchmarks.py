#!/usr/bin/env python3
"""V0.6.4 confirmation benchmark. Does not overwrite V0.6–V0.6.3 artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.cl.v064 import run_v064_benchmark
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION_LEGACY


def main() -> None:
    for name in ("v06_continual.json", "v061_continual.json", "v062_continual.json", "v063_adaptation.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v064_benchmark(
        n_seeds=10,
        source_budgets=(8_192, 32_768),
        transfer_steps=8_192,
        eval_episodes=8,
        artifact_path="artifacts/v064_adaptation.json",
        checkpoint_dir="checkpoints/v064",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print(json.dumps(out["summary"]["all_seeds"], indent=2, default=str))
    print("paired risk vs scratch", json.dumps(out["summary"]["paired_seed_deltas"]["risk_selector_minus_scratch"]["across_seeds"], indent=2))
    print("physics_legacy", CARTPOLE_PHYSICS_VERSION_LEGACY)
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
