#!/usr/bin/env python3
"""V0.8.9 learning efficiency. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v089 import run_v089_benchmark


def main() -> None:
    for name in ("v088_online.json", "v087_online.json", "v086_candidates.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v089_benchmark(
        n_model_seeds=10,
        artifact_path="artifacts/v089_learning.json",
        checkpoint_dir="checkpoints/v089",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("detection", json.dumps(out["detection"], indent=2, default=str)[:4000])
    print("exploit", json.dumps(out["exploitation"], indent=2, default=str))
    print("curve", json.dumps(out["learning_curve"], indent=2, default=str)[:8000])
    print("transfer", json.dumps(out["transfer"], indent=2, default=str))
    print("failures", len(out["failures"]))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
