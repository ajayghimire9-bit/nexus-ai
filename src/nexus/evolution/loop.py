from __future__ import annotations

import copy
import random
from dataclasses import asdict, replace
from typing import Any

from nexus.config import ArchitectureConfig, EvolutionConfig, NexusConfig, PPOConfig
from nexus.eval.evaluate import evaluate_policy, random_policy_baseline
from nexus.evolution.mutate import mutate_spec, random_spec
from nexus.memory.store import ExperimentStore
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.ppo import PPOTrainer, spec_from_arch_config


def _arch_cfg_from_spec(spec: ArchitectureSpec) -> ArchitectureConfig:
    return ArchitectureConfig(
        hidden_sizes=spec.hidden_sizes,
        activation=spec.activation,
        use_residual=spec.use_residual,
        dropout=spec.dropout,
        layer_norm=spec.layer_norm,
        shared_backbone=spec.shared_backbone,
        init=spec.init,
    )


def _evaluate_candidate(
    spec: ArchitectureSpec,
    ppo_cfg: PPOConfig,
    evo: EvolutionConfig,
    generation: int,
    seed: int,
    store: ExperimentStore,
) -> dict[str, Any]:
    arch = _arch_cfg_from_spec(spec)
    train_cfg = replace(ppo_cfg, seed=seed, total_timesteps=evo.train_timesteps, env_id=evo.env_id)
    trainer = PPOTrainer(train_cfg, arch)
    try:
        train_result = trainer.train(evo.train_timesteps)
        eval_stats = evaluate_policy(
            trainer.agent,
            evo.env_id,
            episodes=evo.eval_episodes,
            seed=seed + 10_000,
            device=trainer.device,
            deterministic=True,
            obs_rms=trainer.obs_rms if train_cfg.normalize_obs else None,
        )
    finally:
        trainer.close()

    record = store.add(
        env_id=evo.env_id,
        generation=generation,
        architecture=spec.to_dict(),
        train_config={"seed": seed, "timesteps": evo.train_timesteps, "lr": train_cfg.learning_rate},
        mean_return=eval_stats["mean_return"],
        std_return=eval_stats["std_return"],
        timesteps=int(train_result["timesteps"]),
        seed=seed,
        notes="evolution candidate; compare only at matched timesteps",
    )
    return {
        "spec": spec,
        "mean_return": eval_stats["mean_return"],
        "std_return": eval_stats["std_return"],
        "train": train_result,
        "eval": eval_stats,
        "id": record.id,
    }


def run_evolution(cfg: NexusConfig) -> dict[str, Any]:
    """Train, independently evaluate, store, and select architecture candidates.

    Selection uses evaluated mean return only. This is a measured search loop,
    not a claim of open-ended self-improvement.
    """
    evo = cfg.evolution
    rng = random.Random(evo.seed)
    store = ExperimentStore(evo.db_path)
    baseline = random_policy_baseline(evo.env_id, episodes=evo.eval_episodes, seed=evo.seed + 50_000)

    population: list[ArchitectureSpec] = [spec_from_arch_config(cfg.architecture)]
    while len(population) < evo.population_size:
        population.append(random_spec(rng))

    history: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None

    try:
        for gen in range(evo.generations):
            results: list[dict[str, Any]] = []
            for i, spec in enumerate(population):
                seed = evo.seed + gen * 100 + i
                results.append(_evaluate_candidate(spec, cfg.ppo, evo, gen, seed, store))
            results.sort(key=lambda r: r["mean_return"], reverse=True)
            elites = results[: evo.elite_count]
            if best is None or elites[0]["mean_return"] > best["mean_return"]:
                best = {
                    "mean_return": elites[0]["mean_return"],
                    "spec": elites[0]["spec"].to_dict(),
                    "generation": gen,
                    "id": elites[0]["id"],
                }
            history.append(
                {
                    "generation": gen,
                    "ranked": [
                        {"mean_return": r["mean_return"], "spec": r["spec"].to_dict(), "id": r["id"]}
                        for r in results
                    ],
                }
            )
            next_pop = [copy.deepcopy(r["spec"]) for r in elites]
            while len(next_pop) < evo.population_size:
                parent = rng.choice(elites)["spec"]
                next_pop.append(mutate_spec(parent, rng))
            population = next_pop
    finally:
        store.close()

    return {
        "baseline_random": baseline,
        "best": best,
        "history": history,
        "db_path": evo.db_path,
        "caveat": (
            "Candidates were trained for a small, matched timestep budget. "
            "Higher return here is not proof of a generally better architecture."
        ),
    }
