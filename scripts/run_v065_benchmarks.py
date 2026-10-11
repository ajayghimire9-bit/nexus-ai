#!/usr/bin/env python3
"""V0.6.5 causal-transfer benchmark. Does not overwrite V0.6–V0.6.4 artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.cl.v065 import run_v065_benchmark


def main() -> None:
    for name in (
        "v06_continual.json",
        "v061_continual.json",
        "v062_continual.json",
        "v063_adaptation.json",
        "v064_adaptation.json",
    ):
        assert Path("artifacts", name).exists(), name
    out = run_v065_benchmark(
        n_seeds=10,
        source_budgets=(8_192, 32_768),
        transfer_steps=2_048,
        probe_steps=256,
        eval_episodes=8,
        artifact_path="artifacts/v065_transfer.json",
        checkpoint_dir="checkpoints/v065",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print(json.dumps(out["summary"]["ablations"], indent=2, default=str))
    print("D_minus_B", json.dumps(out["summary"]["encoder_weights_beyond_source_rms"], indent=2, default=str))
    print("learned_minus_D", json.dumps(out["summary"]["paired_seed_deltas"]["learned_minus_D"]["across_seeds"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
