#!/usr/bin/env python3
"""V0.7.2 planning-reliability benchmark. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v072 import run_v072_benchmark


def main() -> None:
    for name in ("v071_world_model.json", "v07_world_model.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v072_benchmark(
        n_model_seeds=5,
        n_train=1024,
        n_val=256,
        n_test=256,
        epochs=20,
        paired_eval_seeds=2,
        eval_episodes=2,
        ensemble_members=3,
        ensemble_epochs=8,
        artifact_path="artifacts/v072_world_model.json",
        checkpoint_dir="checkpoints/v072",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("prediction", json.dumps(out["prediction"], indent=2, default=str))
    print("termination_h6", json.dumps(out["termination_h6"], indent=2, default=str))
    print("paired_term", json.dumps({k: v["across_seeds"] for k, v in out["paired_termination"].items()}, indent=2, default=str))
    print("greedy", json.dumps(out["greedy"], indent=2, default=str))
    print("uncertainty", json.dumps(out["uncertainty"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
