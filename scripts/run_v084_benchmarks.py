#!/usr/bin/env python3
"""V0.8.4 fair adaptation verification. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v084 import run_v084_benchmark


def main() -> None:
    for name in ("v083_learning.json", "v082_belief.json", "v081_adaptation.json", "v08_adaptation.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v084_benchmark(
        n_model_seeds=10,
        artifact_path="artifacts/v084_verification.json",
        checkpoint_dir="checkpoints/v084",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("noisy", json.dumps(out["noisy_confirmation"], indent=2, default=str)[:6000])
    print("paired", json.dumps({k: v.get("across_seeds") for k, v in out["paired_noisy"].items()}, indent=2, default=str))
    print("harm", json.dumps(out["conditional_harm_noisy"], indent=2, default=str)[:3000])
    print("continual", json.dumps(out["continual_return_to_A"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
