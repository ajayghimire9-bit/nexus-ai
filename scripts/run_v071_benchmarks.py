#!/usr/bin/env python3
"""V0.7.1 planning-validation benchmark. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v071 import run_v071_benchmark


def main() -> None:
    for name in ("v07_world_model.json", "v066_transfer.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v071_benchmark(
        n_model_seeds=10,
        n_train=2048,
        n_val=512,
        n_test=512,
        epochs=25,
        mpc_candidates=16,
        mpc_horizon=6,
        paired_eval_seeds=3,
        eval_episodes=2,
        ensemble_members=3,
        ensemble_epochs=8,
        transfer_n=256,
        ppo_short_seeds=5,
        ppo_strong_seeds=3,
        ppo_strong_steps=16_384,
        dagger_episodes=4,
        artifact_path="artifacts/v071_world_model.json",
        checkpoint_dir="checkpoints/v071",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("prediction", json.dumps(out["prediction"], indent=2, default=str)[:2500])
    print("control", json.dumps(out["control"], indent=2, default=str))
    print("paired", json.dumps({k: v["across_seeds"] for k, v in out["paired_control"].items()}, indent=2, default=str))
    print("ppo", json.dumps(out["ppo"], indent=2, default=str))
    print("transfer mpc", json.dumps(out["transfer"]["mpc_returns"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
