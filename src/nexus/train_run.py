from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from nexus.config import NexusConfig
from nexus.eval.evaluate import evaluate_policy, random_policy_baseline
from nexus.memory.store import ExperimentStore
from nexus.rl.ppo import PPOTrainer, spec_from_arch_config


def train_and_eval(
    cfg: NexusConfig,
    *,
    seed: int | None = None,
    checkpoint: Path | None = None,
    store_path: Path | None = None,
    notes: str = "train_and_eval",
) -> dict[str, Any]:
    ppo = cfg.ppo if seed is None else replace(cfg.ppo, seed=seed)
    used_seed = ppo.seed
    trainer = PPOTrainer(ppo, cfg.architecture)
    try:
        result = trainer.train()
        ckpt = checkpoint or (Path(ppo.checkpoint_dir) / f"ppo_seed{used_seed}.pt")
        trainer.save(ckpt)
        baseline = random_policy_baseline(
            ppo.env_id, episodes=cfg.evaluation.episodes, seed=cfg.evaluation.seed
        )
        eval_stats = evaluate_policy(
            trainer.agent,
            ppo.env_id,
            episodes=cfg.evaluation.episodes,
            seed=cfg.evaluation.seed,
            device=trainer.device,
            obs_rms=trainer.obs_rms,
        )
    finally:
        trainer.close()

    payload = {
        "seed": used_seed,
        "train": {k: v for k, v in result.items() if k != "history"},
        "eval": eval_stats,
        "random_baseline": baseline,
        "checkpoint": str(ckpt),
        "architecture": spec_from_arch_config(cfg.architecture).to_dict(),
        "note": "Metrics are from this run only. No AGI or trading claim.",
    }
    db = store_path or Path("runs") / "experiments.sqlite"
    store = ExperimentStore(db)
    try:
        store.add(
            env_id=ppo.env_id,
            generation=0,
            architecture=payload["architecture"],
            train_config={"timesteps": result["timesteps"], "lr": ppo.learning_rate, "seed": used_seed},
            mean_return=eval_stats["mean_return"],
            std_return=eval_stats["std_return"],
            timesteps=int(result["timesteps"]),
            seed=used_seed,
            notes=notes,
        )
    finally:
        store.close()
    return payload


def run_multiseed(cfg: NexusConfig, seeds: list[int]) -> dict[str, Any]:
    rows = [train_and_eval(cfg, seed=s, notes=f"multiseed seed={s}") for s in seeds]
    means = [r["eval"]["mean_return"] for r in rows]
    import numpy as np

    return {
        "seeds": seeds,
        "runs": rows,
        "eval_mean_across_seeds": float(np.mean(means)),
        "eval_std_across_seeds": float(np.std(means, ddof=0)),
        "solved_cartpole": all(m >= 475.0 for m in means) if cfg.ppo.env_id == "CartPole-v1" else None,
        "caveat": "Each seed is an independent training run with the same architecture and timestep budget.",
    }
