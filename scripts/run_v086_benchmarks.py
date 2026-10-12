#!/usr/bin/env python3
"""V0.8.6 safer candidate generation. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v086 import run_v086_benchmark


def main() -> None:
    for name in ("v085_verification.json", "v084_verification.json", "v083_learning.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v086_benchmark(
        n_model_seeds=10,
        artifact_path="artifacts/v086_candidates.json",
        checkpoint_dir="checkpoints/v086",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("dev", json.dumps(out["dev_method_stats"], indent=2, default=str)[:4000])
    print("noisy", json.dumps(out["noisy_method_stats"], indent=2, default=str)[:6000])
    print("primary", json.dumps(out["primary"], indent=2, default=str))
    print("continual", json.dumps(out["continual_return_to_A"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
