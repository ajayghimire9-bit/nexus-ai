from __future__ import annotations

import random
from dataclasses import replace
from typing import Any

from nexus.config import ArchitectureConfig, NexusConfig
from nexus.eval.evaluate import evaluate_policy, random_policy_baseline
from nexus.evolution.mutate import random_spec
from nexus.memory.store import ExperimentStore
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.ppo import PPOTrainer


def _train_spec(cfg: NexusConfig, spec: ArchitectureSpec, seed: int, timesteps: int, notes: str) -> dict[str, Any]:
    arch = ArchitectureConfig(
        hidden_sizes=spec.hidden_sizes,
        activation=spec.activation,
        use_residual=spec.use_residual,
        dropout=spec.dropout,
        layer_norm=spec.layer_norm,
        shared_backbone=spec.shared_backbone,
        init=spec.init,
    )
    ppo = replace(cfg.ppo, seed=seed, total_timesteps=timesteps, env_id=cfg.evolution.env_id)
    trainer = PPOTrainer(ppo, arch)
    try:
        train_result = trainer.train(timesteps)
        eval_stats = evaluate_policy(
            trainer.agent,
            ppo.env_id,
            episodes=cfg.evolution.eval_episodes,
            seed=seed + 50_000,
            device=trainer.device,
            obs_rms=trainer.obs_rms if ppo.normalize_obs else None,
        )
        n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
    finally:
        trainer.close()
    return {
        "spec": spec.to_dict(),
        "mean_return": eval_stats["mean_return"],
        "std_return": eval_stats["std_return"],
        "n_params": n_params,
        "timesteps": train_result["timesteps"],
        "eval": eval_stats,
        "notes": notes,
        "seed": seed,
    }


def run_architecture_transfer(cfg: NexusConfig, source: ArchitectureSpec) -> dict[str, Any]:
    """H5 (architecture transfer): reuse a genome on a new env vs random genomes.

    Weights are not copied (observation sizes differ). This tests whether a
    design that worked on the source task helps when trained from scratch on
    the target, versus training a fresh random design at the same budget.
    """
    evo = cfg.evolution
    rng = random.Random(evo.seed)
    baseline = random_policy_baseline(evo.env_id, episodes=evo.eval_episodes, seed=evo.seed + 1)
    transferred = _train_spec(cfg, source, evo.seed, evo.train_timesteps, "transferred_architecture")
    randoms = [
        _train_spec(cfg, random_spec(rng), evo.seed + 1 + i, evo.train_timesteps, "random_architecture")
        for i in range(2)
    ]
    store = ExperimentStore(evo.db_path)
    try:
        for row in [transferred, *randoms]:
            store.add(
                env_id=evo.env_id,
                generation=0,
                architecture=row["spec"],
                train_config={"kind": row["notes"], "timesteps": row["timesteps"]},
                mean_return=row["mean_return"],
                std_return=row["std_return"],
                timesteps=int(row["timesteps"]),
                seed=int(row["seed"]),
                notes=row["notes"],
            )
    finally:
        store.close()
    best_random = max(randoms, key=lambda r: r["mean_return"])
    return {
        "target_env": evo.env_id,
        "source_spec": source.to_dict(),
        "transferred": transferred,
        "random_architectures": randoms,
        "random_policy": baseline,
        "transfer_beats_best_random": transferred["mean_return"] > best_random["mean_return"],
        "caveat": (
            "Single-seed architecture transfer, not weight transfer. "
            "A win here is a hypothesis about design reuse, not proof of H5."
        ),
    }
