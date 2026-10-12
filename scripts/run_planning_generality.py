#!/usr/bin/env python3
"""Pendulum planning-generality diagnostic. Does not overwrite cross_environment.json."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.generality import CROSS_ENV_HASH, run_planning_generality, validate_cross_env_preserved


def main() -> None:
    preserved = validate_cross_env_preserved()
    assert preserved["ok"], preserved
    assert Path("artifacts/cross_environment.json").exists()
    out = run_planning_generality(
        n_model_seeds=10,
        n_dev_seeds=5,
        artifact_path="artifacts/planning_generality.json",
        checkpoint_dir="checkpoints/planning_generality",
    )
    assert out["audit"]["cross_env_preserved"]["protocol_hash"] == CROSS_ENV_HASH
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("dev ranked", json.dumps(out["development"]["ranked"], indent=2, default=str)[:4000])
    print("confirm", json.dumps(out["confirmation"], indent=2, default=str)[:6000])
    print("cartpole", json.dumps(out["cartpole_regression"], indent=2, default=str)[:2500])
    print("decision", json.dumps(out["decision"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
