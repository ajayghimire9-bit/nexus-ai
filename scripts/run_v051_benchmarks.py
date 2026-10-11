#!/usr/bin/env python3
"""Write V0.5.1 machine-readable artifacts. Does not invent numbers."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.config import load_config
from nexus.meta.loop import compare_controllers
from nexus.meta.synthetic import run_synthetic_bandit


def main() -> None:
    syn = run_synthetic_bandit(
        n_seeds=20, horizon=200, artifact_path="artifacts/v051_synthetic_bandit.json"
    )
    print(json.dumps({"synthetic_summary": syn["summary"], "generalization": syn["generalization_shifted_context"]}, indent=2, default=str)[:4000])

    cfg = load_config("configs/smoke.yaml")
    cfg.ppo.num_envs = 2
    cfg.ppo.num_steps = 64
    cfg.ppo.num_minibatches = 2
    cfg.ppo.update_epochs = 2
    cfg.ppo.log_interval = 10_000
    cfg.meta.max_experiments = 4
    cfg.meta.max_timesteps = 1024
    cfg.meta.train_timesteps = 256
    cfg.meta.n_train_seeds = 1
    cfg.meta.eval_episodes = 4
    cfg.meta.holdout_eval_seed = 80_000
    cfg.meta.assessment_eval_seed = 81_000
    cfg.meta.independent_eval_seed = 92_000
    cfg.meta.epsilon = 0.2
    ppo = compare_controllers(
        cfg,
        names=("random", "epsilon_greedy", "linucb", "linucb_frozen"),
        controller_seeds=(0, 1),
    )
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/v051_ppo_meta.json").write_text(json.dumps(ppo, indent=2, default=str))
    print(json.dumps(ppo["summary"], indent=2, default=str))


if __name__ == "__main__":
    main()
