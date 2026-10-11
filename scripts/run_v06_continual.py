#!/usr/bin/env python3
"""V0.6 CartPole-family continual / transfer benchmark. Does not invent numbers."""

from __future__ import annotations

import json

from nexus.cl.experiment import run_continual_benchmark
from nexus.meta.synthetic import run_paired_synthetic_bandit


def main() -> None:
    # Reproducibility check: paired synthetic must match V0.5.2 within rounding.
    syn = run_paired_synthetic_bandit(n_seeds=20, horizon=200, n_holdout=200, artifact_path=None)
    prior = json.loads(open("artifacts/v052_synthetic_paired.json").read())
    for row, old in zip(syn["summary"], prior["summary"], strict=True):
        assert row["method"] == old["method"]
        assert abs(row["mean_last50_opt_rate"] - old["mean_last50_opt_rate"]) < 1e-9
    print("v052 synthetic artifact reproduced")
    out = run_continual_benchmark(
        n_seeds=3, steps_per_task=2048, eval_episodes=8, artifact_path="artifacts/v06_continual.json"
    )
    print(json.dumps(out["summary"], indent=2, default=str))
    print(json.dumps(out["protocol"], indent=2))


if __name__ == "__main__":
    main()
