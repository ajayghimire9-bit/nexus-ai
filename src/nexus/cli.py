from __future__ import annotations

import argparse
import json
from pathlib import Path

from nexus.config import load_config
from nexus.eval.evaluate import evaluate_policy, random_policy_baseline
from nexus.evolution.loop import run_evolution
from nexus.memory.store import ExperimentStore
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.actor_critic import ActorCritic
from nexus.rl.ppo import PPOTrainer, spec_from_arch_config
import torch
import gymnasium as gym
import numpy as np


def _cmd_train(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    if args.timesteps:
        cfg.ppo.total_timesteps = args.timesteps
    trainer = PPOTrainer(cfg.ppo, cfg.architecture)
    try:
        result = trainer.train()
        ckpt = Path(cfg.ppo.checkpoint_dir) / "ppo_latest.pt"
        trainer.save(ckpt)
        baseline = random_policy_baseline(
            cfg.ppo.env_id, episodes=cfg.evaluation.episodes, seed=cfg.evaluation.seed
        )
        eval_stats = evaluate_policy(
            trainer.agent,
            cfg.ppo.env_id,
            episodes=cfg.evaluation.episodes,
            seed=cfg.evaluation.seed,
            device=trainer.device,
        )
        payload = {
            "train": {k: v for k, v in result.items() if k != "history"},
            "eval": eval_stats,
            "random_baseline": baseline,
            "checkpoint": str(ckpt),
            "architecture": spec_from_arch_config(cfg.architecture).to_dict(),
            "note": "Metrics are from this run only. No AGI or trading claim.",
        }
        store = ExperimentStore(Path("runs") / "experiments.sqlite")
        try:
            store.add(
                env_id=cfg.ppo.env_id,
                generation=0,
                architecture=payload["architecture"],
                train_config={"timesteps": result["timesteps"], "lr": cfg.ppo.learning_rate, "seed": cfg.ppo.seed},
                mean_return=eval_stats["mean_return"],
                std_return=eval_stats["std_return"],
                timesteps=int(result["timesteps"]),
                seed=cfg.ppo.seed,
                notes="ppo train CLI; independent eval vs random baseline",
            )
        finally:
            store.close()
        out = Path(args.output) if args.output else Path(cfg.ppo.checkpoint_dir) / "train_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2))
        print(json.dumps(payload, indent=2))
    finally:
        trainer.close()


def _cmd_eval(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    ckpt = torch.load(args.checkpoint, map_location=cfg.ppo.device, weights_only=False)
    arch = ckpt["architecture"]
    spec = ArchitectureSpec.from_dict(arch)
    env = gym.make(cfg.ppo.env_id)
    obs_dim = int(np.prod(env.observation_space.shape))
    agent = ActorCritic(obs_dim, env.action_space, spec)
    agent.load_state_dict(ckpt["model"])
    env.close()
    device = torch.device(cfg.ppo.device)
    agent.to(device)
    stats = evaluate_policy(
        agent,
        cfg.ppo.env_id,
        episodes=cfg.evaluation.episodes,
        seed=cfg.evaluation.seed,
        device=device,
    )
    print(json.dumps(stats, indent=2))


def _cmd_evolve(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    result = run_evolution(cfg)
    out = Path(args.output) if args.output else Path("runs") / "evolution_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    serializable = json.loads(json.dumps(result, default=str))
    out.write_text(json.dumps(serializable, indent=2))
    print(json.dumps(serializable, indent=2))


def _cmd_remember(args: argparse.Namespace) -> None:
    store = ExperimentStore(args.db)
    rows = store.top(args.n)
    store.close()
    print(json.dumps([r.__dict__ for r in rows], indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(prog="nexus", description="NEXUS Research V0.1 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_train = sub.add_parser("train", help="Train PPO actor-critic")
    p_train.add_argument("--config", default="configs/ppo_cartpole.yaml")
    p_train.add_argument("--timesteps", type=int, default=None)
    p_train.add_argument("--output", default=None)
    p_train.set_defaults(func=_cmd_train)

    p_eval = sub.add_parser("eval", help="Evaluate a saved checkpoint")
    p_eval.add_argument("--checkpoint", required=True)
    p_eval.add_argument("--config", default="configs/ppo_cartpole.yaml")
    p_eval.set_defaults(func=_cmd_eval)

    p_evo = sub.add_parser("evolve", help="Architecture mutation loop")
    p_evo.add_argument("--config", default="configs/evolution.yaml")
    p_evo.add_argument("--output", default=None)
    p_evo.set_defaults(func=_cmd_evolve)

    p_mem = sub.add_parser("remember", help="Show top stored experiments")
    p_mem.add_argument("--db", default="runs/experiments.sqlite")
    p_mem.add_argument("-n", type=int, default=5)
    p_mem.set_defaults(func=_cmd_remember)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
