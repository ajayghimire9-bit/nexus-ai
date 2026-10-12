#!/usr/bin/env python3
"""V0.8.9 research checkpoint: validate artifact + MAE-rejection audit. Does not retune 0.97."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v089 import run_mae_rejection_audit, validate_v089_artifact


def main() -> None:
    v = validate_v089_artifact("artifacts/v089_learning.json")
    print("artifact", json.dumps(v, indent=2))
    assert v["ok"], v["issues"]
    out = run_mae_rejection_audit(
        n_model_seeds=10,
        artifact_path="artifacts/v089_mae_audit.json",
    )
    print("n_proposals", out["n_proposals"], "n_accept", out["n_accept"])
    print("mean_gate_ratio", out["mean_gate_ratio"])
    print("mean_control_delta", out["mean_control_delta"])
    print("n_gate_rejected_useful_control", out["n_gate_rejected_useful_control"])
    print("control_delta_ci", json.dumps(out["control_delta_ci"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
