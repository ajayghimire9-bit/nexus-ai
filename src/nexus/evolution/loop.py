from __future__ import annotations

import copy
import math
import random
import shutil
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import torch

from nexus.config import ArchitectureConfig, EvolutionConfig, NexusConfig, PPOConfig
from nexus.eval.evaluate import evaluate_policy, random_policy_baseline
from nexus.evolution.mutate import crossover_spec, mutate_spec, random_spec
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


def _count_params(module: torch.nn.Module) -> int:
    return int(sum(p.numel() for p in module.parameters()))


def _evaluate_candidate(
    spec: ArchitectureSpec,
    ppo_cfg: PPOConfig,
    evo: EvolutionConfig,
    generation: int,
    train_seeds: list[int],
    holdout_eval_seed: int,
    store: ExperimentStore,
    champion_dir: Path,
) -> dict[str, Any]:
    """Train on a matched seed set; evaluate every seed on the same holdout eval seed."""
    arch = _arch_cfg_from_spec(spec)
    seed_returns: list[float] = []
    seed_stds: list[float] = []
    wall_times: list[float] = []
    timesteps_used = 0
    n_params = 0
    last_ckpt: Path | None = None

    for seed in train_seeds:
        train_cfg = replace(ppo_cfg, seed=seed, total_timesteps=evo.train_timesteps, env_id=evo.env_id)
        trainer = PPOTrainer(train_cfg, arch)
        try:
            t0 = time.perf_counter()
            train_result = trainer.train(evo.train_timesteps)
            wall = time.perf_counter() - t0
            n_params = _count_params(trainer.agent)
            eval_stats = evaluate_policy(
                trainer.agent,
                evo.env_id,
                episodes=evo.eval_episodes,
                seed=holdout_eval_seed,
                device=trainer.device,
                deterministic=True,
                obs_rms=trainer.obs_rms if train_cfg.normalize_obs else None,
            )
            ckpt = champion_dir / f"cand_gen{generation}_seed{seed}_{id(spec) & 0xFFFF:x}.pt"
            trainer.save(ckpt)
            last_ckpt = ckpt
        finally:
            trainer.close()
        seed_returns.append(float(eval_stats["mean_return"]))
        seed_stds.append(float(eval_stats["std_return"]))
        wall_times.append(float(wall))
        timesteps_used = int(train_result["timesteps"])

    returns_arr = np.asarray(seed_returns, dtype=np.float64)
    mean_return = float(returns_arr.mean())
    variance = float(returns_arr.var(ddof=1)) if len(returns_arr) > 1 else 0.0
    std_across_seeds = float(returns_arr.std(ddof=1)) if len(returns_arr) > 1 else 0.0
    n = max(1, len(returns_arr))
    stderr = std_across_seeds / math.sqrt(n) if len(returns_arr) > 1 else 0.0
    wall_mean = float(np.mean(wall_times)) if wall_times else 0.0
    sample_efficiency = mean_return / max(1, timesteps_used)

    record = store.add(
        env_id=evo.env_id,
        generation=generation,
        architecture=spec.to_dict(),
        train_config={
            "train_seeds": train_seeds,
            "holdout_eval_seed": holdout_eval_seed,
            "timesteps": evo.train_timesteps,
            "lr": ppo_cfg.learning_rate,
            "n_params": n_params,
        },
        mean_return=mean_return,
        std_return=std_across_seeds,
        timesteps=timesteps_used,
        seed=train_seeds[0],
        notes=(
            "evolution candidate; matched train seeds; holdout eval seed; "
            "compare only at matched timesteps and env_id"
        ),
    )
    return {
        "spec": spec,
        "mean_return": mean_return,
        "variance": variance,
        "std_across_seeds": std_across_seeds,
        "stderr": stderr,
        "seed_returns": seed_returns,
        "eval_episode_std_mean": float(np.mean(seed_stds)) if seed_stds else 0.0,
        "n_params": n_params,
        "wall_clock_s": wall_mean,
        "timesteps": timesteps_used,
        "sample_efficiency": sample_efficiency,
        "checkpoint": str(last_ckpt) if last_ckpt else None,
        "id": record.id,
    }


def run_evolution(cfg: NexusConfig) -> dict[str, Any]:
    """Train, independently evaluate, store, and select architecture candidates.

    Ranking uses the mean over a matched training-seed set. A single lucky seed
    cannot become champion. This is a measured search loop, not open-ended
    self-improvement.
    """
    evo = cfg.evolution
    rng = random.Random(evo.seed)
    store = ExperimentStore(evo.db_path)
    champion_dir = Path(evo.champion_dir)
    champion_dir.mkdir(parents=True, exist_ok=True)
    baseline = random_policy_baseline(evo.env_id, episodes=evo.eval_episodes, seed=evo.seed + 50_000)

    train_seeds = [evo.seed + 1000 + k for k in range(max(1, evo.n_train_seeds))]
    holdout_eval_seed = evo.holdout_eval_seed

    population: list[ArchitectureSpec] = [spec_from_arch_config(cfg.architecture)]
    while len(population) < evo.population_size:
        population.append(random_spec(rng))

    history: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    champion_history: list[str] = []

    try:
        for gen in range(evo.generations):
            results: list[dict[str, Any]] = []
            for spec in population:
                results.append(
                    _evaluate_candidate(
                        spec,
                        cfg.ppo,
                        evo,
                        gen,
                        train_seeds,
                        holdout_eval_seed,
                        store,
                        champion_dir,
                    )
                )
            results.sort(key=lambda r: (r["mean_return"], -r["stderr"]), reverse=True)
            elites = results[: evo.elite_count]
            leader = elites[0]
            if best is None or leader["mean_return"] > best["mean_return"]:
                hist_path = champion_dir / f"champion_gen{gen}_id{leader['id']}.pt"
                if leader.get("checkpoint"):
                    src = Path(str(leader["checkpoint"]))
                    if src.exists():
                        shutil.copy2(src, hist_path)
                        shutil.copy2(src, champion_dir / "champion_current.pt")
                        champion_history.append(str(hist_path))
                best = {
                    "mean_return": leader["mean_return"],
                    "variance": leader["variance"],
                    "stderr": leader["stderr"],
                    "seed_returns": leader["seed_returns"],
                    "n_params": leader["n_params"],
                    "wall_clock_s": leader["wall_clock_s"],
                    "sample_efficiency": leader["sample_efficiency"],
                    "spec": leader["spec"].to_dict(),
                    "generation": gen,
                    "id": leader["id"],
                    "checkpoint": str(hist_path),
                }
            history.append(
                {
                    "generation": gen,
                    "train_seeds": train_seeds,
                    "holdout_eval_seed": holdout_eval_seed,
                    "ranked": [
                        {
                            "mean_return": r["mean_return"],
                            "variance": r["variance"],
                            "stderr": r["stderr"],
                            "seed_returns": r["seed_returns"],
                            "n_params": r["n_params"],
                            "wall_clock_s": r["wall_clock_s"],
                            "sample_efficiency": r["sample_efficiency"],
                            "spec": r["spec"].to_dict(),
                            "id": r["id"],
                        }
                        for r in results
                    ],
                }
            )
            next_pop = [copy.deepcopy(r["spec"]) for r in elites]
            while len(next_pop) < evo.population_size:
                if len(elites) >= 2 and rng.random() < 0.4:
                    left, right = rng.sample([e["spec"] for e in elites], 2)
                    next_pop.append(crossover_spec(left, right, rng))
                else:
                    parent = rng.choice(elites)["spec"]
                    next_pop.append(mutate_spec(parent, rng))
            population = next_pop
    finally:
        store.close()

    return {
        "baseline_random": baseline,
        "best": best,
        "history": history,
        "champion_history": champion_history,
        "train_seeds": train_seeds,
        "holdout_eval_seed": holdout_eval_seed,
        "db_path": evo.db_path,
        "caveat": (
            "Candidates share a matched training-seed set and a separate holdout "
            "eval seed. Ranking uses mean return, not a single lucky seed. "
            "Higher return here is not proof of a generally better architecture."
        ),
    }
