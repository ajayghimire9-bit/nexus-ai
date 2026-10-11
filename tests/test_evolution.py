from __future__ import annotations

import random

from nexus.config import load_config
from nexus.evolution.mutate import mutate_spec, random_spec
from nexus.evolution.loop import run_evolution
from nexus.nn.spec import ArchitectureSpec


def test_mutate_returns_valid_spec() -> None:
    rng = random.Random(0)
    parent = ArchitectureSpec(hidden_sizes=(32, 32), activation="relu")
    child = mutate_spec(parent, rng)
    assert isinstance(child, ArchitectureSpec)
    assert child.hidden_sizes


def test_random_spec_valid() -> None:
    spec = random_spec(random.Random(1))
    assert spec.hidden_sizes


def test_evolution_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = load_config("configs/smoke.yaml")
    cfg.evolution.db_path = str(tmp_path / "exp.sqlite")
    cfg.evolution.generations = 1
    cfg.evolution.population_size = 2
    cfg.evolution.elite_count = 1
    cfg.evolution.train_timesteps = 256
    cfg.evolution.eval_episodes = 2
    cfg.evolution.n_train_seeds = 1
    cfg.evolution.champion_dir = str(tmp_path / "champs")
    cfg.ppo.num_envs = 2
    cfg.ppo.num_steps = 64
    cfg.ppo.num_minibatches = 2
    result = run_evolution(cfg)
    assert result["best"] is not None
    assert "mean_return" in result["best"]
    assert "stderr" in result["best"]
    assert "n_params" in result["best"]
    assert result["train_seeds"] == [cfg.evolution.seed + 1000]
    assert result["baseline_random"]["episodes"] == 2
