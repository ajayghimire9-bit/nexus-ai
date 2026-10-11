#!/usr/bin/env python3
"""V0.6.6 finalization benchmark. Does not overwrite prior artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.cl.v066 import run_v066_benchmark


def main() -> None:
    for name in (
        "v06_continual.json",
        "v061_continual.json",
        "v062_continual.json",
        "v063_adaptation.json",
        "v064_adaptation.json",
        "v065_transfer.json",
    ):
        assert Path("artifacts", name).exists(), name
    out = run_v066_benchmark(
        n_seeds=10,
        source_budgets=(8_192, 32_768),
        transfer_steps=1_024,
        probe_steps=256,
        calib_steps=128,
        eval_episodes=8,
        fit_seed_count=4,
        artifact_path="artifacts/v066_transfer.json",
        checkpoint_dir="checkpoints/v066",
    )
    print(json.dumps(out["protocol"], indent=2, default=str))
    print(json.dumps(out["summary"]["normalization"], indent=2, default=str))
    print("B_minus_A", json.dumps(out["summary"]["paired_norm"]["B_minus_A"]["across_seeds"], indent=2, default=str))
    print("D_minus_B", json.dumps(out["summary"]["paired_norm"]["D_minus_B"]["across_seeds"], indent=2, default=str))
    print("selectors", json.dumps(out["summary"]["selectors_heldout_seeds"], indent=2, default=str))
    print("stab", json.dumps(out["summary"]["stabilization_lr1e4_16k"], indent=2, default=str))
    print("wall_clock_s", round(out["wall_clock_s"], 2))


if __name__ == "__main__":
    main()
