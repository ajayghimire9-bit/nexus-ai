#!/usr/bin/env python3
"""V0.8.5 candidate quality and verification. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.world.v085 import run_v085_benchmark


def main() -> None:
    for name in ("v084_verification.json", "v083_learning.json", "v082_belief.json"):
        assert Path("artifacts", name).exists(), name
    out = run_v085_benchmark(
        n_model_seeds=10,
        artifact_path="artifacts/v085_verification.json",
        checkpoint_dir="checkpoints/v085",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print("h1", json.dumps(out["h1_candidate_quality"], indent=2, default=str)[:4000])
    print("h2_sel", out["h2_verifier_quality"]["selected_verifier"], out["h2_verifier_quality"]["selection_reason"])
    print("h2_confirm", json.dumps(out["h2_verifier_quality"]["confirmation"], indent=2, default=str)[:8000])
    print("choice", json.dumps(out["h2_verifier_quality"]["choice_vs_never_per_seed"], indent=2, default=str)[:4000])
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
