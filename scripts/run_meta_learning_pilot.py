#!/usr/bin/env python3
"""Reptile vs matched-data multitask on Pendulum. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.meta_learning import TRANSFER_HASH, run_meta_learning_pilot, validate_prior_artifacts


def main() -> None:
    preserved = validate_prior_artifacts()
    assert preserved["transfer_ok"] and preserved["cross_env_ok"] and preserved["generality_ok"], preserved
    for name in ("cross_environment.json", "planning_generality.json", "pendulum_transfer.json"):
        assert Path("artifacts", name).exists(), name
    out = run_meta_learning_pilot(
        n_model_seeds=10,
        n_arch_seeds=2,
        artifact_path="artifacts/meta_learning_pilot.json",
        checkpoint_dir="checkpoints/meta_learning_pilot",
    )
    assert out["audit"]["transfer_ok"]
    assert out["protocol"]
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("architecture", json.dumps(out["architecture"], indent=2, default=str)[:3000])
    print("confirmation", json.dumps(out["confirmation"], indent=2, default=str)[:6000])
    print("decision", json.dumps(out["decision"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))
    assert out["audit"]["transfer_ok"]
    assert TRANSFER_HASH == "7fde7c9c01fc8524"


if __name__ == "__main__":
    main()
