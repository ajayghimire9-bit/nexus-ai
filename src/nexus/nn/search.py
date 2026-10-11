from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from nexus.config import ArchitectureConfig, NexusConfig, PPOConfig
from nexus.eval.evaluate import evaluate_policy, random_policy_baseline
from nexus.memory.store import ExperimentStore
from nexus.nn.activations import BASELINE_ACTIVATIONS, SEARCH_ACTIVATIONS, get_activation
from nexus.nn.validate import validate_activation
from nexus.rl.ppo import PPOTrainer


def screen_activations(names: tuple[str, ...] = SEARCH_ACTIVATIONS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in names:
        report = validate_activation(get_activation(name))
        rows.append({"name": name, **report})
    return rows


def run_activation_search(cfg: NexusConfig) -> dict[str, Any]:
    """Validate candidates, train survivors, compare to ReLU/GELU/SiLU/tanh.

    Short matched budgets. A higher score here is not a general activation discovery.
    """
    evo = cfg.evolution
    screens = screen_activations()
    survivors = [r["name"] for r in screens if r["passed"]]
    store = ExperimentStore(evo.db_path)
    results: list[dict[str, Any]] = []
    baseline = random_policy_baseline(cfg.ppo.env_id, episodes=evo.eval_episodes, seed=evo.seed + 7_000)
    try:
        for i, name in enumerate(survivors):
            arch = replace(cfg.architecture, activation=name, hidden_sizes=tuple(cfg.architecture.hidden_sizes))
            ppo = replace(cfg.ppo, total_timesteps=evo.train_timesteps, seed=evo.seed + i)
            trainer = PPOTrainer(ppo, arch)
            try:
                train_result = trainer.train(evo.train_timesteps)
                eval_stats = evaluate_policy(
                    trainer.agent,
                    ppo.env_id,
                    episodes=evo.eval_episodes,
                    seed=evo.seed + 20_000,
                    device=trainer.device,
                    obs_rms=trainer.obs_rms if ppo.normalize_obs else None,
                )
            finally:
                trainer.close()
            arch_payload = asdict(arch)
            arch_payload["hidden_sizes"] = list(arch_payload["hidden_sizes"])
            rec = store.add(
                env_id=ppo.env_id,
                generation=0,
                architecture=arch_payload,
                train_config={"timesteps": train_result["timesteps"], "activation": name},
                mean_return=eval_stats["mean_return"],
                std_return=eval_stats["std_return"],
                timesteps=int(train_result["timesteps"]),
                seed=ppo.seed,
                notes="activation search; matched timestep budget",
            )
            results.append(
                {
                    "name": name,
                    "mean_return": eval_stats["mean_return"],
                    "std_return": eval_stats["std_return"],
                    "is_baseline": name in BASELINE_ACTIVATIONS,
                    "id": rec.id,
                    "eval": eval_stats,
                }
            )
    finally:
        store.close()

    results.sort(key=lambda r: r["mean_return"], reverse=True)
    Path("runs").mkdir(parents=True, exist_ok=True)
    return {
        "screens": screens,
        "rejected": [r["name"] for r in screens if not r["passed"]],
        "ranked": results,
        "random_baseline": baseline,
        "caveat": (
            "Candidates trained for a short matched budget after stability/grad checks. "
            "Do not treat a single ranking as a new SOTA activation."
        ),
    }
