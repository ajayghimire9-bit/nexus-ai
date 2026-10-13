#!/usr/bin/env python3
"""Pendulum adaptation/transfer. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.pendulum_transfer import CROSS_ENV_HASH, GENERALITY_HASH, run_pendulum_transfer, validate_prior_artifacts


def main() -> None:
    preserved = validate_prior_artifacts()
    assert preserved["cross_env_ok"] and preserved["generality_ok"], preserved
    assert Path("artifacts/cross_environment.json").exists()
    assert Path("artifacts/planning_generality.json").exists()
    out = run_pendulum_transfer(
        n_model_seeds=10,
        artifact_path="artifacts/pendulum_transfer.json",
        checkpoint_dir="checkpoints/pendulum_transfer",
    )
    assert out["audit"]["cross_env_hash"] == CROSS_ENV_HASH
    assert out["audit"]["generality_hash"] == GENERALITY_HASH
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("confirmation", json.dumps(out["confirmation"], indent=2, default=str)[:5000])
    print("curve", json.dumps(out["learning_curve"], indent=2, default=str)[:5000])
    print("transfer", json.dumps(out["transfer"], indent=2, default=str)[:4000])
    print("decision", json.dumps(out["decision"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
