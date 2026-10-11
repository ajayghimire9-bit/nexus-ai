from __future__ import annotations

import math
import random
from dataclasses import replace
from typing import Any

import numpy as np

from nexus.config import ArchitectureConfig, NexusConfig
from nexus.eval.evaluate import evaluate_policy, random_policy_baseline
from nexus.evolution.mutate import random_spec
from nexus.memory.store import ExperimentStore
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.ppo import PPOTrainer


def _train_spec_matched(
    cfg: NexusConfig,
    spec: ArchitectureSpec,
    train_seeds: list[int],
    holdout_eval_seed: int,
    timesteps: int,
    notes: str,
) -> dict[str, Any]:
    arch = ArchitectureConfig(
        hidden_sizes=spec.hidden_sizes,
        activation=spec.activation,
        use_residual=spec.use_residual,
        dropout=spec.dropout,
        layer_norm=spec.layer_norm,
        shared_backbone=spec.shared_backbone,
        init=spec.init,
    )
    seed_returns: list[float] = []
    n_params = 0
    last_timesteps = 0
    last_std = 0.0
    for seed in train_seeds:
        ppo = replace(cfg.ppo, seed=seed, total_timesteps=timesteps, env_id=cfg.evolution.env_id)
        trainer = PPOTrainer(ppo, arch)
        try:
            train_result = trainer.train(timesteps)
            eval_stats = evaluate_policy(
                trainer.agent,
                ppo.env_id,
                episodes=cfg.evolution.eval_episodes,
                seed=holdout_eval_seed,
                device=trainer.device,
                obs_rms=trainer.obs_rms if ppo.normalize_obs else None,
            )
            n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
        finally:
            trainer.close()
        seed_returns.append(float(eval_stats["mean_return"]))
        last_std = float(eval_stats["std_return"])
        last_timesteps = int(train_result["timesteps"])
    arr = np.asarray(seed_returns, dtype=np.float64)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    stderr = std / math.sqrt(max(1, len(arr))) if len(arr) > 1 else 0.0
    return {
        "spec": spec.to_dict(),
        "mean_return": mean,
        "std_return": std,
        "stderr": stderr,
        "seed_returns": seed_returns,
        "eval_episode_std": last_std,
        "n_params": n_params,
        "timesteps": last_timesteps,
        "notes": notes,
        "train_seeds": train_seeds,
        "holdout_eval_seed": holdout_eval_seed,
    }


def run_architecture_transfer(cfg: NexusConfig, source: ArchitectureSpec) -> dict[str, Any]:
    """Reuse a genome on a new env vs random genomes at a matched seed set.

    Weights are not copied. A win is a hypothesis about design reuse, not proof of transfer.
    """
    evo = cfg.evolution
    rng = random.Random(evo.seed)
    n_seeds = max(1, evo.n_train_seeds)
    train_seeds = [evo.seed + 1000 + k for k in range(n_seeds)]
    holdout = evo.holdout_eval_seed
    baseline = random_policy_baseline(evo.env_id, episodes=evo.eval_episodes, seed=holdout + 1)
    transferred = _train_spec_matched(
        cfg, source, train_seeds, holdout, evo.train_timesteps, "transferred_architecture"
    )
    randoms = [
        _train_spec_matched(
            cfg, random_spec(rng), train_seeds, holdout, evo.train_timesteps, "random_architecture"
        )
        for _ in range(2)
    ]
    store = ExperimentStore(evo.db_path)
    try:
        for row in [transferred, *randoms]:
            store.add(
                env_id=evo.env_id,
                generation=0,
                architecture=row["spec"],
                train_config={
                    "kind": row["notes"],
                    "timesteps": row["timesteps"],
                    "train_seeds": train_seeds,
                    "holdout_eval_seed": holdout,
                },
                mean_return=row["mean_return"],
                std_return=row["std_return"],
                timesteps=int(row["timesteps"]),
                seed=int(train_seeds[0]),
                notes=row["notes"],
            )
    finally:
        store.close()
    best_random = max(randoms, key=lambda r: r["mean_return"])
    return {
        "target_env": evo.env_id,
        "source_spec": source.to_dict(),
        "train_seeds": train_seeds,
        "holdout_eval_seed": holdout,
        "transferred": transferred,
        "random_architectures": randoms,
        "random_policy": baseline,
        "transfer_beats_best_random": transferred["mean_return"] > best_random["mean_return"],
        "caveat": (
            "Matched-seed architecture transfer, not weight transfer. "
            "A win here is a hypothesis about design reuse, not proof of transfer."
        ),
    }
