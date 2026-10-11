from __future__ import annotations

import json
import random
import shutil
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import torch

from nexus.config import ArchitectureConfig, NexusConfig
from nexus.eval.evaluate import evaluate_policy, random_policy_baseline
from nexus.memory.store import ExperimentStore
from nexus.meta.controller import (
    ResearchController,
    build_controller_state,
    make_controller,
)
from nexus.meta.reward import research_reward, task_normalized_score
from nexus.meta.schema import ExperimentAction, Proposal
from nexus.nn.spec import ArchitectureSpec
from nexus.rl.ppo import PPOTrainer


def _arch_cfg(spec: ArchitectureSpec) -> ArchitectureConfig:
    return ArchitectureConfig(
        hidden_sizes=spec.hidden_sizes,
        activation=spec.activation,
        use_residual=spec.use_residual,
        dropout=spec.dropout,
        layer_norm=spec.layer_norm,
        shared_backbone=spec.shared_backbone,
        init=spec.init,
    )


def _limits_from_cfg(cfg: NexusConfig, remaining_timesteps: int) -> dict[str, Any]:
    meta = cfg.meta
    return {
        "env_id": meta.env_id,
        "transfer_env_id": meta.transfer_env_id,
        "train_timesteps": meta.train_timesteps,
        "train_seeds": [meta.seed + 1000 + i for i in range(max(1, meta.n_train_seeds))],
        "holdout_eval_seed": meta.holdout_eval_seed,
        "assessment_eval_seed": meta.assessment_eval_seed,
        "learning_rate": cfg.ppo.learning_rate,
        "remaining_timesteps": remaining_timesteps,
        "max_experiments": meta.max_experiments,
        "max_timesteps": meta.max_timesteps,
    }


def _run_action(
    cfg: NexusConfig,
    action: ExperimentAction,
    store: ExperimentStore,
    champion_dir: Path,
) -> dict[str, Any]:
    spec = ArchitectureSpec.from_dict(action.architecture)
    failed = False
    seed_returns: list[float] = []
    n_params = 0
    wall = 0.0
    timesteps_used = 0
    last_ckpt: Path | None = None
    holdout_stats: dict[str, float] = {}
    if action.kind == "extra_evaluation":
        ckpt = champion_dir / "champion_current.pt"
        if not ckpt.exists():
            failed = True
            holdout_stats = {"mean_return": 0.0, "std_return": 0.0}
        else:
            payload = torch.load(ckpt, map_location=cfg.ppo.device, weights_only=False)
            from nexus.rl.actor_critic import ActorCritic
            import gymnasium as gym

            env = gym.make(action.env_id)
            obs_dim = int(np.prod(env.observation_space.shape))
            ckpt_spec = ArchitectureSpec.from_dict(
                {**payload["architecture"], "hidden_sizes": tuple(payload["architecture"]["hidden_sizes"])}
            )
            agent = ActorCritic(obs_dim, env.action_space, ckpt_spec)
            agent.load_state_dict(payload["model"])
            env.close()
            holdout_stats = evaluate_policy(
                agent,
                action.env_id,
                episodes=cfg.meta.eval_episodes,
                seed=action.assessment_eval_seed,
                device=torch.device(cfg.ppo.device),
            )
            seed_returns = [float(holdout_stats["mean_return"])]
            n_params = int(sum(p.numel() for p in agent.parameters()))
    else:
        for seed in action.train_seeds:
            ppo = replace(
                cfg.ppo,
                seed=int(seed),
                total_timesteps=action.train_timesteps,
                env_id=action.env_id,
                learning_rate=action.learning_rate,
            )
            trainer = PPOTrainer(ppo, _arch_cfg(spec))
            train_result: dict[str, Any] = {"timesteps": 0}
            try:
                t0 = time.perf_counter()
                train_result = trainer.train(action.train_timesteps)
                wall += time.perf_counter() - t0
                n_params = int(sum(p.numel() for p in trainer.agent.parameters()))
                if not torch.isfinite(torch.nn.utils.parameters_to_vector(trainer.agent.parameters())).all():
                    failed = True
                holdout_stats = evaluate_policy(
                    trainer.agent,
                    action.env_id,
                    episodes=cfg.meta.eval_episodes,
                    seed=action.holdout_eval_seed,
                    device=trainer.device,
                    obs_rms=trainer.obs_rms if ppo.normalize_obs else None,
                )
                ckpt = champion_dir / f"exp_{action.fingerprint()}_s{seed}.pt"
                trainer.save(ckpt)
                last_ckpt = ckpt
            except Exception:  # noqa: BLE001
                failed = True
                holdout_stats = {"mean_return": 0.0, "std_return": 0.0}
            finally:
                trainer.close()
            seed_returns.append(float(holdout_stats.get("mean_return", 0.0)))
            timesteps_used = int(train_result["timesteps"]) if not failed else timesteps_used

    arr = np.asarray(seed_returns, dtype=np.float64) if seed_returns else np.zeros(1)
    mean_return = float(arr.mean())
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    stderr = std / max(len(arr), 1) ** 0.5 if len(arr) > 1 else 0.0
    rec = store.add(
        env_id=action.env_id,
        generation=0,
        architecture=action.architecture,
        train_config={
            "fingerprint": action.fingerprint(),
            "kind": action.kind,
            "lr": action.learning_rate,
            "train_seeds": list(action.train_seeds),
            "holdout_eval_seed": action.holdout_eval_seed,
            "assessment_eval_seed": action.assessment_eval_seed,
            "n_params": n_params,
            "wall_clock_s": wall,
        },
        mean_return=mean_return,
        std_return=std,
        timesteps=timesteps_used,
        seed=int(action.train_seeds[0]),
        status="failed" if failed else "evaluated",
        notes=action.notes,
    )
    return {
        "id": rec.id,
        "failed": failed,
        "mean_return": mean_return,
        "stderr": stderr,
        "std_return": std,
        "seed_returns": seed_returns,
        "n_params": n_params,
        "wall_clock_s": wall,
        "timesteps": timesteps_used,
        "checkpoint": str(last_ckpt) if last_ckpt else None,
        "action": action.to_dict(),
    }


def run_research_loop(
    cfg: NexusConfig,
    *,
    controller: ResearchController | None = None,
    resume: bool = True,
) -> dict[str, Any]:
    """OBSERVE → PROPOSE → VALIDATE → TRAIN → EVALUATE → STORE → UPDATE → REPEAT.

    Resource limits, evaluation seeds, and permissions are frozen in config.
    The controller cannot change them.
    """
    meta = cfg.meta
    rng = random.Random(meta.seed)
    ctrl = controller or make_controller(meta.controller, epsilon=meta.epsilon, alpha=meta.linucb_alpha)
    store = ExperimentStore(meta.db_path)
    champion_dir = Path(meta.champion_dir)
    champion_dir.mkdir(parents=True, exist_ok=True)
    state_path = Path(meta.state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    remaining_exp = meta.max_experiments
    remaining_steps = meta.max_timesteps
    history: list[dict[str, Any]] = []
    seen: set[str] = set()
    best_by_env: dict[str, float] = {}
    elites: list[ArchitectureSpec] = [ArchitectureSpec.from_dict({
        **{"hidden_sizes": list(cfg.architecture.hidden_sizes)},
        "activation": cfg.architecture.activation,
        "use_residual": cfg.architecture.use_residual,
        "dropout": cfg.architecture.dropout,
        "layer_norm": cfg.architecture.layer_norm,
        "shared_backbone": cfg.architecture.shared_backbone,
        "init": cfg.architecture.init,
    })]
    champion_history: list[str] = []
    n_fail = 0
    last_reward = 0.0
    best_score = 0.0
    n_params = 1
    extra_recent = 0.0
    baselines: dict[str, float] = {}

    if resume and state_path.exists():
        saved = json.loads(state_path.read_text())
        remaining_exp = int(saved.get("remaining_experiments", remaining_exp))
        remaining_steps = int(saved.get("remaining_timesteps", remaining_steps))
        history = list(saved.get("history", []))
        seen = set(saved.get("seen", []))
        n_fail = int(saved.get("n_fail", 0))
        ctrl.load_state_dict(saved.get("controller", {}))
        champion_history = list(saved.get("champion_history", []))

    try:
        while remaining_exp > 0:
            limits = _limits_from_cfg(cfg, remaining_steps)
            n_prior = len(history)
            fail_rate = n_fail / max(n_prior, 1)
            budget_used = 1.0 - (remaining_steps / max(meta.max_timesteps, 1))
            obs_state = build_controller_state(
                remaining_frac=remaining_exp / max(meta.max_experiments, 1),
                n_prior=n_prior,
                fail_rate=fail_rate,
                best_score=best_score,
                last_reward=last_reward,
                n_params=n_params,
                budget_used_frac=budget_used,
                extra_eval_recent=extra_recent,
                elites=elites,
                default_architecture=elites[0].to_dict(),
                best_expr=None,
            )
            proposal: Proposal = ctrl.propose(obs_state, limits, rng)
            action = proposal.action
            cost = action.estimated_timesteps()
            if cost > remaining_steps and action.kind != "extra_evaluation":
                break
            if action.fingerprint() in seen:
                n_fail += 1
                remaining_exp -= 1
                history.append({"skipped_duplicate": action.fingerprint(), "kind": action.kind})
                continue
            seen.add(action.fingerprint())
            result = _run_action(cfg, action, store, champion_dir)
            env_id = action.env_id
            if env_id not in baselines:
                baselines[env_id] = float(
                    random_policy_baseline(env_id, episodes=meta.eval_episodes, seed=meta.holdout_eval_seed + 7)[
                        "mean_return"
                    ]
                )
            rw = research_reward(
                env_id=env_id,
                mean_return=result["mean_return"],
                stderr=result["stderr"],
                random_baseline=baselines[env_id],
                best_score_same_env=best_by_env.get(env_id),
                n_params=max(int(result["n_params"]), 2),
                wall_clock_s=float(result["wall_clock_s"]),
                timesteps=max(int(result["timesteps"]), 1),
                failed=bool(result["failed"]),
            )
            ctrl.update(obs_state["context"], action.kind, float(rw["reward"]))
            last_reward = float(rw["reward"])
            extra_recent = 1.0 if action.kind == "extra_evaluation" else 0.0
            if result["failed"]:
                n_fail += 1
            else:
                score = float(rw["score"])
                if env_id not in best_by_env or score > best_by_env[env_id]:
                    best_by_env[env_id] = score
                    if action.env_id == meta.env_id:
                        best_score = score
                        elites = [ArchitectureSpec.from_dict(action.architecture), *elites][:3]
                        n_params = max(int(result["n_params"]), 2)
                        if result.get("checkpoint"):
                            hist = champion_dir / f"champion_{result['id']}.pt"
                            shutil.copy2(result["checkpoint"], hist)
                            shutil.copy2(result["checkpoint"], champion_dir / "champion_current.pt")
                            champion_history.append(str(hist))
            remaining_exp -= 1
            remaining_steps -= cost
            history.append(
                {
                    "proposal": proposal.to_dict(),
                    "result": {k: v for k, v in result.items() if k != "action"},
                    "controller_reward": rw,
                    "remaining_experiments": remaining_exp,
                    "remaining_timesteps": remaining_steps,
                }
            )
            state_path.write_text(
                json.dumps(
                    {
                        "remaining_experiments": remaining_exp,
                        "remaining_timesteps": remaining_steps,
                        "history": history,
                        "seen": list(seen),
                        "n_fail": n_fail,
                        "controller": ctrl.state_dict(),
                        "champion_history": champion_history,
                        "note": "Limits are frozen. Controller cannot edit max_experiments or eval rules.",
                    },
                    indent=2,
                    default=str,
                )
            )
            if remaining_steps <= 0:
                break
    finally:
        store.close()

    return {
        "controller": ctrl.name,
        "is_meta_rl": ctrl.is_meta_rl,
        "history": history,
        "n_experiments": len([h for h in history if "result" in h]),
        "n_fail": n_fail,
        "n_skipped": len([h for h in history if "skipped_duplicate" in h]),
        "best_score_by_env": best_by_env,
        "champion_history": champion_history,
        "remaining_experiments": remaining_exp,
        "remaining_timesteps": remaining_steps,
        "caveat": (
            "Controller reward uses holdout eval seeds. Do not treat it as the "
            "final independent assessment (assessment_eval_seed is separate)."
        ),
    }


def compare_controllers(cfg: NexusConfig, names: tuple[str, ...] = ("random", "epsilon_greedy", "linucb")) -> dict[str, Any]:
    """Equal-budget comparison. Hold-out controller seeds are not the train seeds of LinUCB."""
    rows = []
    for i, name in enumerate(names):
        local = replace(
            cfg.meta,
            controller=name,
            seed=cfg.meta.seed + 17 * i,
            db_path=str(Path(cfg.meta.db_path).with_name(f"meta_{name}.sqlite")),
            state_path=str(Path(cfg.meta.state_path).with_name(f"state_{name}.json")),
            champion_dir=str(Path(cfg.meta.champion_dir) / name),
        )
        cfg_i = replace(cfg, meta=local)
        ctrl = make_controller(name, epsilon=cfg.meta.epsilon, alpha=cfg.meta.linucb_alpha)
        result = run_research_loop(cfg_i, controller=ctrl, resume=False)
        rewards = [h["controller_reward"]["reward"] for h in result["history"] if "controller_reward" in h]
        rows.append(
            {
                "controller": name,
                "n_experiments": result["n_experiments"],
                "n_fail": result["n_fail"],
                "mean_controller_reward": float(np.mean(rewards)) if rewards else 0.0,
                "best_score_by_env": result["best_score_by_env"],
                "is_meta_rl": False,
            }
        )
    return {
        "equal_budget": {
            "max_experiments": cfg.meta.max_experiments,
            "max_timesteps": cfg.meta.max_timesteps,
            "train_timesteps": cfg.meta.train_timesteps,
        },
        "controllers": rows,
        "caveat": (
            "Comparison uses the same frozen timestep/experiment budget. "
            "LinUCB is a contextual bandit, not meta-RL. Superiority is not claimed without these numbers."
        ),
    }
