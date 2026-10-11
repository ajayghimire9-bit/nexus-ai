#!/usr/bin/env python3
"""V0.8 adaptive world-model benchmark. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.adapt import run_v08_benchmark


def main() -> None:
    for name in (
        "v073_world_model.json",
        "v072_world_model.json",
        "v071_world_model.json",
        "v07_world_model.json",
        "v066_transfer.json",
    ):
        assert Path("artifacts", name).exists(), name
    out = run_v08_benchmark(
        n_model_seeds=5,
        artifact_path="artifacts/v08_adaptation.json",
        checkpoint_dir="checkpoints/v08",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("detection", json.dumps(out["detection"], indent=2, default=str))
    print("confirmation", json.dumps(out["confirmation_summary"], indent=2, default=str)[:4000])
    print("paired_128", json.dumps({k: v["across_seeds"] for k, v in out["paired_planning_vs_frozen"]["128"].items()}, indent=2, default=str))
    print("continual_A", json.dumps(out["continual_return_to_A"], indent=2, default=str))
    print("explore", json.dumps(out["explore"], indent=2, default=str))
    print("costs", json.dumps(out["costs"], indent=2, default=str))
    print("dev_selection", json.dumps(out["dev_selection"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
