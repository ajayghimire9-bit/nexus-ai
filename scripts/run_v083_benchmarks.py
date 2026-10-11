#!/usr/bin/env python3
"""V0.8.3 decision-aware online learning. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v083 import run_v083_benchmark


def main() -> None:
    for name in ("v082_belief.json", "v081_adaptation.json", "v08_adaptation.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v083_benchmark(
        n_model_seeds=10,
        artifact_path="artifacts/v083_learning.json",
        checkpoint_dir="checkpoints/v083",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("dev_sel", json.dumps(out["dev_selection"], indent=2, default=str))
    print("noisy", json.dumps(out["noisy_confirmation"], indent=2, default=str)[:5000])
    print("paired", json.dumps({k: v.get("across_seeds") for k, v in out["paired_noisy"].items()}, indent=2, default=str))
    print("harmful", json.dumps(out["harmful_commit_rate_noisy"], indent=2, default=str)[:2000])
    print("continual", json.dumps(out["continual_return_to_A"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
