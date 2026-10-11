#!/usr/bin/env python3
"""V0.7 final confirmation. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v073 import run_v073_benchmark


def main() -> None:
    for name in ("v072_world_model.json", "v071_world_model.json", "v07_world_model.json", "v066_transfer.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v073_benchmark(
        n_model_seeds=10,
        eval_seeds=2,
        eval_episodes=2,
        artifact_path="artifacts/v073_world_model.json",
        checkpoint_dir="checkpoints/v073",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("source", json.dumps(out["source"], indent=2, default=str))
    print("confirm", json.dumps(out["confirmation_mean"], indent=2, default=str))
    print("paired_confirm", json.dumps({k: v["across_seeds"] for k, v in out["paired_confirmation"].items()}, indent=2, default=str))
    print("paired_source", json.dumps(out["paired_source"]["h3_minus_greedy"]["across_seeds"], indent=2, default=str))
    print("by_task", json.dumps(out["confirmation_by_task"], indent=2, default=str)[:2500])
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
