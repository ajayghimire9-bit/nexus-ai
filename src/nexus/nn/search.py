from __future__ import annotations

import random
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from nexus.config import NexusConfig
from nexus.eval.evaluate import evaluate_policy, random_policy_baseline
from nexus.memory.store import ExperimentStore
from nexus.nn.activations import BASELINE_ACTIVATIONS, SEARCH_ACTIVATIONS, get_activation
from nexus.nn.expr import (
    canonical_key,
    crossover_expr,
    expr_to_str,
    mutate_expr,
    population_exprs,
    register_expr,
)
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


def run_expr_search(cfg: NexusConfig, *, n_candidates: int = 8, expr_seed: int = 0) -> dict[str, Any]:
    """Generate expression-tree activations, screen, then train survivors vs tanh.

    Trees are interpreted with approved torch ops. Generated Python is never exec'd.
    """
    rng = random.Random(expr_seed)
    generated: list[dict[str, Any]] = []
    seen: set[str] = set()
    nodes = population_exprs(rng, n_candidates)
    if len(nodes) >= 2:
        nodes.append(mutate_expr(nodes[0], rng))
        nodes.append(crossover_expr(nodes[0], nodes[1], rng))
    for node in nodes:
        key = canonical_key(node)
        if key in seen:
            continue
        seen.add(key)
        name = register_expr(node)
        report = validate_activation(get_activation(name))
        generated.append({"name": name, "expr": expr_to_str(node), "n_nodes": None, **report})
        if len(generated) >= n_candidates:
            break

    survivors = [g for g in generated if g["passed"]]
    names_to_train = ["tanh"] + [g["name"] for g in survivors[:5]]
    # Deduplicate tanh if a generated expr somehow aliases.
    ordered: list[str] = []
    for n in names_to_train:
        if n not in ordered:
            ordered.append(n)

    evo = cfg.evolution
    store = ExperimentStore(evo.db_path)
    results: list[dict[str, Any]] = []
    baseline = random_policy_baseline(cfg.ppo.env_id, episodes=evo.eval_episodes, seed=evo.seed + 9_000)
    try:
        for i, name in enumerate(ordered):
            arch = replace(cfg.architecture, activation=name, hidden_sizes=tuple(cfg.architecture.hidden_sizes))
            ppo = replace(cfg.ppo, total_timesteps=evo.train_timesteps, seed=evo.seed + 100 + i)
            trainer = PPOTrainer(ppo, arch)
            try:
                train_result = trainer.train(evo.train_timesteps)
                eval_stats = evaluate_policy(
                    trainer.agent,
                    ppo.env_id,
                    episodes=evo.eval_episodes,
                    seed=evo.seed + 30_000,
                    device=trainer.device,
                    obs_rms=trainer.obs_rms if ppo.normalize_obs else None,
                )
            finally:
                trainer.close()
            rec = store.add(
                env_id=ppo.env_id,
                generation=0,
                architecture={"activation": name, "hidden_sizes": list(arch.hidden_sizes)},
                train_config={"timesteps": train_result["timesteps"], "kind": "expr_search"},
                mean_return=eval_stats["mean_return"],
                std_return=eval_stats["std_return"],
                timesteps=int(train_result["timesteps"]),
                seed=ppo.seed,
                notes=f"expr search {name}",
            )
            results.append(
                {
                    "name": name,
                    "is_baseline": name in BASELINE_ACTIVATIONS,
                    "mean_return": eval_stats["mean_return"],
                    "id": rec.id,
                    "eval": eval_stats,
                }
            )
    finally:
        store.close()
    results.sort(key=lambda r: r["mean_return"], reverse=True)
    return {
        "generated": generated,
        "rejected": [g["name"] for g in generated if not g["passed"]],
        "ranked": results,
        "random_baseline": baseline,
        "caveat": "Expression search uses a short matched budget. Beating tanh here is not a published activation discovery.",
    }
