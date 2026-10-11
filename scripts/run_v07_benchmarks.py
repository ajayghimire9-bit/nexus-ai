#!/usr/bin/env python3
"""V0.7 world-model benchmark. Does not overwrite V0.5/V0.6 artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.experiment import run_v07_benchmark


def main() -> None:
    for name in (
        "v06_continual.json",
        "v065_transfer.json",
        "v066_transfer.json",
    ):
        assert Path("artifacts", name).exists(), name
    out = run_v07_benchmark(
        n_train=4096,
        n_val=1024,
        n_test=1024,
        epochs=40,
        mpc_candidates=32,
        mpc_horizon=8,
        control_seeds=5,
        eval_episodes=8,
        ensemble_members=3,
        ensemble_epochs=12,
        transfer_n=256,
        artifact_path="artifacts/v07_world_model.json",
        checkpoint_dir="checkpoints/v07",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("prediction", json.dumps(out["prediction"]["residual"]["one_step"], indent=2, default=str))
    print("direct", json.dumps(out["prediction"]["direct"]["one_step"], indent=2, default=str))
    print("persist", json.dumps(out["prediction"]["persistence"], indent=2, default=str))
    print("multi", json.dumps(out["prediction"]["multi_step"], indent=2, default=str))
    print("control", json.dumps({k: v["returns"] for k, v in out["control"].items()}, indent=2, default=str))
    print("costs", json.dumps(out["costs"], indent=2, default=str))
    print("transfer_pred", json.dumps(out["transfer"]["prediction"], indent=2, default=str)[:2000])
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
