#!/usr/bin/env python3
"""V0.8.1 non-saturated adaptive control. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v081 import run_v081_benchmark


def main() -> None:
    for name in ("v08_adaptation.json", "v073_world_model.json", "v07_world_model.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v081_benchmark(
        n_model_seeds=10,
        artifact_path="artifacts/v081_adaptation.json",
        checkpoint_dir="checkpoints/v081",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("detection", json.dumps(out["detection"], indent=2, default=str))
    print("confirm", json.dumps(out["confirmation_summary"], indent=2, default=str)[:5000])
    print("paired_128", json.dumps({k: v["across_seeds"] for k, v in out["paired_planning_vs_frozen"]["128"].items()}, indent=2, default=str))
    print("continual", json.dumps(out["continual_return_to_A"], indent=2, default=str))
    print("costs", json.dumps(out["costs"], indent=2, default=str))
    print("dev_selection", json.dumps(out["dev_selection"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
