#!/usr/bin/env python3
"""V0.8.7 online learning bridge. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v087 import run_v087_benchmark


def main() -> None:
    for name in ("v086_candidates.json", "v085_verification.json", "v084_verification.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v087_benchmark(
        n_model_seeds=10,
        artifact_path="artifacts/v087_online.json",
        checkpoint_dir="checkpoints/v087",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("ablation", json.dumps(out["ablation"], indent=2, default=str)[:5000])
    print("noisy", json.dumps(out["noisy_confirmation"], indent=2, default=str)[:8000])
    print("continual", json.dumps(out["continual_return_to_A"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
