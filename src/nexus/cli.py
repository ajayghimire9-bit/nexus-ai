from __future__ import annotations

import argparse
import json
from pathlib import Path

from nexus.config import load_config
from nexus.eval.evaluate import evaluate_policy
from nexus.evolution.loop import run_evolution
from nexus.memory.store import ExperimentStore
from nexus.meta.loop import compare_controllers, run_research_loop
from nexus.meta.select import propose_next_experiment
from nexus.eval.transfer import run_architecture_transfer
from nexus.nn.search import run_activation_search, run_expr_search
from nexus.rl.ppo import spec_from_arch_config
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.actor_critic import ActorCritic
from nexus.rl.running_stats import RunningMeanStd
from nexus.train_run import run_multiseed, train_and_eval
import torch
import gymnasium as gym
import numpy as np


def _cmd_train(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    if args.timesteps:
        cfg.ppo.total_timesteps = args.timesteps
    if args.seeds:
        seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
        payload = run_multiseed(cfg, seeds)
        out = Path(args.output) if args.output else Path("runs") / "multiseed.json"
    else:
        payload = train_and_eval(
            cfg,
            checkpoint=Path(cfg.ppo.checkpoint_dir) / "ppo_latest.pt",
            notes="ppo train CLI; independent eval vs random baseline",
        )
        out = Path(args.output) if args.output else Path(cfg.ppo.checkpoint_dir) / "train_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


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
    obs_rms = None
    if ckpt.get("obs_rms"):
        obs_rms = RunningMeanStd((obs_dim,))
        obs_rms.load_state_dict(ckpt["obs_rms"])
    stats = evaluate_policy(
        agent,
        cfg.ppo.env_id,
        episodes=cfg.evaluation.episodes,
        seed=cfg.evaluation.seed,
        device=device,
        obs_rms=obs_rms,
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


def _cmd_activations(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    result = run_expr_search(cfg, n_candidates=args.n) if args.expr else run_activation_search(cfg)
    default = "runs/expr_report.json" if args.expr else "runs/activation_report.json"
    out = Path(args.output) if args.output else Path(default)
    out.parent.mkdir(parents=True, exist_ok=True)
    serializable = json.loads(json.dumps(result, default=str))
    out.write_text(json.dumps(serializable, indent=2))
    print(json.dumps(serializable, indent=2))


def _cmd_transfer(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    source = spec_from_arch_config(cfg.architecture)
    result = run_architecture_transfer(cfg, source)
    out = Path(args.output) if args.output else Path("runs") / "transfer_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    serializable = json.loads(json.dumps(result, default=str))
    out.write_text(json.dumps(serializable, indent=2))
    print(json.dumps(serializable, indent=2))


def _cmd_select(args: argparse.Namespace) -> None:
    result = propose_next_experiment(args.db, epsilon=args.epsilon, seed=args.seed, env_id=args.env)
    print(json.dumps(result, indent=2))


def _cmd_research(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    result = run_research_loop(cfg, resume=not args.no_resume)
    out = Path(args.output) if args.output else Path("runs") / "research_loop.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    serializable = json.loads(json.dumps(result, default=str))
    out.write_text(json.dumps(serializable, indent=2))
    print(json.dumps(serializable, indent=2))


def _cmd_compare(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    result = compare_controllers(cfg)
    out = Path(args.output) if args.output else Path("runs") / "controller_compare.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    serializable = json.loads(json.dumps(result, default=str))
    out.write_text(json.dumps(serializable, indent=2))
    print(json.dumps(serializable, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="nexus", description="NEXUS Research V0.5 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_train = sub.add_parser("train", help="Train PPO actor-critic")
    p_train.add_argument("--config", default="configs/ppo_cartpole.yaml")
    p_train.add_argument("--timesteps", type=int, default=None)
    p_train.add_argument("--seeds", default=None, help="Comma-separated independent training seeds")
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

    p_act = sub.add_parser("activations", help="Screen and train candidate activations")
    p_act.add_argument("--config", default="configs/activations.yaml")
    p_act.add_argument("--output", default=None)
    p_act.add_argument("--expr", action="store_true", help="Restricted expression-tree search (no exec)")
    p_act.add_argument("-n", type=int, default=8)
    p_act.set_defaults(func=_cmd_activations)

    p_tr = sub.add_parser("transfer", help="Architecture-genome transfer to another env (not weight copy)")
    p_tr.add_argument("--config", default="configs/evolution_acrobot.yaml")
    p_tr.add_argument("--output", default=None)
    p_tr.set_defaults(func=_cmd_transfer)

    p_res = sub.add_parser("research", help="Budgeted meta-controller research loop")
    p_res.add_argument("--config", default="configs/meta.yaml")
    p_res.add_argument("--output", default=None)
    p_res.add_argument("--no-resume", action="store_true")
    p_res.set_defaults(func=_cmd_research)

    p_cmp = sub.add_parser("compare-controllers", help="Equal-budget random vs ε-greedy vs LinUCB")
    p_cmp.add_argument("--config", default="configs/meta.yaml")
    p_cmp.add_argument("--output", default=None)
    p_cmp.set_defaults(func=_cmd_compare)

    p_sel = sub.add_parser("select", help="Propose next experiment from stored results (ε-greedy)")
    p_sel.add_argument("--db", default="runs/experiments.sqlite")
    p_sel.add_argument("--epsilon", type=float, default=0.2)
    p_sel.add_argument("--seed", type=int, default=0)
    p_sel.add_argument("--env", default=None)
    p_sel.set_defaults(func=_cmd_select)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
