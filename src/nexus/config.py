from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ArchitectureConfig:
    hidden_sizes: tuple[int, ...] = (64, 64)
    activation: str = "tanh"
    use_residual: bool = False
    dropout: float = 0.0
    layer_norm: bool = False
    shared_backbone: bool = True
    init: str = "orthogonal"


@dataclass
class PPOConfig:
    env_id: str = "CartPole-v1"
    num_envs: int = 4
    total_timesteps: int = 200_000
    num_steps: int = 128
    update_epochs: int = 4
    num_minibatches: int = 4
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_coef: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    seed: int = 1
    device: str = "cpu"
    normalize_advantages: bool = True
    normalize_obs: bool = False
    anneal_lr: bool = False
    clip_vloss: bool = False
    log_interval: int = 20
    checkpoint_dir: str = "checkpoints"


@dataclass
class EvalConfig:
    episodes: int = 20
    seed: int = 10_000


@dataclass
class EvolutionConfig:
    generations: int = 2
    population_size: int = 4
    elite_count: int = 2
    train_timesteps: int = 8_192
    eval_episodes: int = 10
    env_id: str = "CartPole-v1"
    seed: int = 7
    db_path: str = "runs/experiments.sqlite"


@dataclass
class NexusConfig:
    architecture: ArchitectureConfig = field(default_factory=ArchitectureConfig)
    ppo: PPOConfig = field(default_factory=PPOConfig)
    evaluation: EvalConfig = field(default_factory=EvalConfig)
    evolution: EvolutionConfig = field(default_factory=EvolutionConfig)


def _filter_fields(cls: type, data: dict[str, Any]) -> dict[str, Any]:
    allowed = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in allowed}


def load_config(path: str | Path | None) -> NexusConfig:
    if path is None:
        return NexusConfig()
    raw = yaml.safe_load(Path(path).read_text()) or {}
    arch = ArchitectureConfig(**_filter_fields(ArchitectureConfig, raw.get("architecture", {})))
    ppo = PPOConfig(**_filter_fields(PPOConfig, raw.get("ppo", {})))
    evaluation = EvalConfig(**_filter_fields(EvalConfig, raw.get("evaluation", {})))
    evolution = EvolutionConfig(**_filter_fields(EvolutionConfig, raw.get("evolution", {})))
    if "hidden_sizes" in raw.get("architecture", {}):
        arch.hidden_sizes = tuple(raw["architecture"]["hidden_sizes"])
    return NexusConfig(architecture=arch, ppo=ppo, evaluation=evaluation, evolution=evolution)


def config_to_dict(cfg: NexusConfig) -> dict[str, Any]:
    return asdict(cfg)
