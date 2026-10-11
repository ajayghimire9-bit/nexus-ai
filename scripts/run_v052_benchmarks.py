#!/usr/bin/env python3
"""V0.5.2 paired synthetic + PPO meta artifacts. Does not invent numbers."""

from __future__ import annotations

import json
from pathlib import Path

from nexus.config import load_config
from nexus.meta.loop import compare_controllers
from nexus.meta.synthetic import run_paired_synthetic_bandit


def _ppo_cfg(env_id: str, champion_dir: str, db_path: str, state_path: str):
    cfg = load_config("configs/smoke.yaml")
    cfg.ppo.num_envs = 4
    cfg.ppo.num_steps = 128
    cfg.ppo.num_minibatches = 4
    cfg.ppo.update_epochs = 2
    cfg.ppo.log_interval = 10_000
    cfg.ppo.env_id = env_id
    cfg.meta.env_id = env_id
    cfg.meta.transfer_env_id = "Acrobot-v1" if env_id == "CartPole-v1" else "CartPole-v1"
    cfg.meta.max_experiments = 4
    cfg.meta.max_timesteps = 24_576
    cfg.meta.train_timesteps = 8_192
    cfg.meta.explore_timesteps = 2_048
    cfg.meta.n_train_seeds = 1
    cfg.meta.eval_episodes = 8
    cfg.meta.holdout_eval_seed = 80_000
    cfg.meta.assessment_eval_seed = 81_000
    cfg.meta.independent_eval_seed = 92_000
    cfg.meta.epsilon = 0.2
    cfg.meta.champion_dir = champion_dir
    cfg.meta.db_path = db_path
    cfg.meta.state_path = state_path
    return cfg


def main() -> None:
    syn = run_paired_synthetic_bandit(
        n_seeds=20, horizon=200, n_holdout=200, artifact_path="artifacts/v052_synthetic_paired.json"
    )
    Path("artifacts/v052_synthetic_summary.json").write_text(
        json.dumps(
            {
                "summary": syn["summary"],
                "paired_deltas": syn["paired_deltas"],
                "n_seeds": syn["n_seeds"],
                "protocol": syn["protocol"],
            },
            indent=2,
        )
    )
    print(json.dumps({"synthetic_deltas": syn["paired_deltas"]}, indent=2, default=str))

    payload = {"envs": {}, "protocol": {
        "controller_seeds": [0, 1, 2],
        "max_experiments": 4,
        "max_timesteps": 24576,
        "confirm_timesteps": 8192,
        "explore_timesteps": 2048,
        "eval_episodes": 8,
        "independent_eval_seed": 92000,
        "holdout_eval_seed": 80000,
        "assessment_eval_seed": 81000,
    }}
    for env_id in ("CartPole-v1", "Acrobot-v1"):
        slug = env_id.split("-")[0].lower()
        cfg = _ppo_cfg(
            env_id,
            champion_dir=f"checkpoints/v052_{slug}",
            db_path=f"runs/v052_{slug}.sqlite",
            state_path=f"runs/v052_{slug}_state.json",
        )
        result = compare_controllers(
            cfg,
            names=("random", "epsilon_greedy", "linucb", "linucb_frozen"),
            controller_seeds=(0, 1, 2),
        )
        payload["envs"][env_id] = {
            "equal_budget": result["equal_budget"],
            "summary": result["summary"],
            "paired_deltas_vs_random": result["paired_deltas_vs_random"],
            "paired": result["paired"],
            "caveat": result["caveat"],
        }
        print(env_id, json.dumps(result["summary"], indent=2, default=str))
        print("deltas", json.dumps(result["paired_deltas_vs_random"], indent=2, default=str))
    Path("artifacts/v052_ppo_meta.json").write_text(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
