#!/usr/bin/env python3
"""V0.8.2 belief and gated adaptation. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v082 import run_v082_benchmark


def main() -> None:
    for name in ("v081_adaptation.json", "v08_adaptation.json", "v073_world_model.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v082_benchmark(
        n_model_seeds=10,
        artifact_path="artifacts/v082_belief.json",
        checkpoint_dir="checkpoints/v082",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("belief_dev", json.dumps(out["belief_dev_return"], indent=2, default=str))
    print("selected", json.dumps(out["selected_belief"], indent=2, default=str))
    print("noisy", json.dumps(out["noisy_confirmation"], indent=2, default=str)[:4500])
    print("clean", json.dumps(out["clean_confirmation"], indent=2, default=str)[:2500])
    print("paired", json.dumps({k: v.get("across_seeds") for k, v in out["paired_noisy"].items()}, indent=2, default=str)[:2500])
    print("continual", json.dumps(out["continual_return_to_A"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
