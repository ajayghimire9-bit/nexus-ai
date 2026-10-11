from __future__ import annotations

import json
import math
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
from nexus.meta.checkpoint import restore_rng, select_representative_checkpoint, serialize_rng
from nexus.meta.controller import (
    ResearchController,
    _fill_action,
    build_controller_state,
    make_controller,
)
from nexus.meta.reward import research_reward, task_normalized_score
from nexus.meta.schedule import champion_exists, enumerate_candidates
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
        "explore_timesteps": int(meta.explore_timesteps or max(int(meta.train_timesteps) // 4, 1)),
    }


def _load_champion_agent(ckpt: Path, env_id: str, device: str):
    from nexus.rl.actor_critic import ActorCritic
    import gymnasium as gym

    payload = torch.load(ckpt, map_location=device, weights_only=False)
    env = gym.make(env_id)
    obs_dim = int(np.prod(env.observation_space.shape))
    ckpt_spec = ArchitectureSpec.from_dict(
        {**payload["architecture"], "hidden_sizes": tuple(payload["architecture"]["hidden_sizes"])}
    )
    agent = ActorCritic(obs_dim, env.action_space, ckpt_spec)
    agent.load_state_dict(payload["model"])
    env.close()
    return agent, payload


def _run_action(
    cfg: NexusConfig,
    action: ExperimentAction,
    store: ExperimentStore,
    champion_dir: Path,
    *,
    in_flight: dict[str, Any] | None = None,
    interrupt_after_iters: int | None = None,
    on_progress: Any | None = None,
    remaining_step_budget: int | None = None,
) -> dict[str, Any]:
    spec = ArchitectureSpec.from_dict(action.architecture)
    failed = False
    seed_returns: list[float] = []
    n_params = 0
    wall = 0.0
    timesteps_used = 0
    seed_ckpts: list[dict[str, Any]] = []
    holdout_stats: dict[str, float] = {}
    assessment: dict[str, Any] | None = None
    controller_updated = action.kind != "extra_evaluation"

    if action.kind == "extra_evaluation":
        # Independent assessment only. Never used as LinUCB / ε-greedy feedback.
        ckpt = champion_dir / "champion_current.pt"
        if not ckpt.exists():
            failed = True
            assessment = {"mean_return": 0.0, "std_return": 0.0, "eval_seed": action.assessment_eval_seed}
        else:
            agent, _payload = _load_champion_agent(ckpt, action.env_id, cfg.ppo.device)
            assessment = evaluate_policy(
                agent,
                action.env_id,
                episodes=cfg.meta.eval_episodes,
                seed=action.assessment_eval_seed,
                device=torch.device(cfg.ppo.device),
            )
            assessment["eval_seed"] = action.assessment_eval_seed
            n_params = int(sum(p.numel() for p in agent.parameters()))
        mean_return = 0.0
        std = 0.0
        stderr = 0.0
    else:
        done_seeds = set(int(s) for s in (in_flight or {}).get("completed_seeds") or [])
        seed_returns = list((in_flight or {}).get("seed_returns") or [])
        timesteps_used = int((in_flight or {}).get("timesteps_used") or 0)
        wall = float((in_flight or {}).get("wall") or 0.0)
        seed_ckpts = list((in_flight or {}).get("seed_checkpoints") or [])
        for seed in action.train_seeds:
            left = None if remaining_step_budget is None else max(int(remaining_step_budget) - timesteps_used, 0)
            seed_ts = int(action.train_timesteps) if left is None else min(int(action.train_timesteps), left)
            if seed_ts <= 0:
                break
            ppo = replace(
                cfg.ppo,
                seed=int(seed),
                total_timesteps=seed_ts,
                env_id=action.env_id,
                learning_rate=action.learning_rate,
            )
            if int(seed) in done_seeds:
                continue
            trainer = PPOTrainer(ppo, _arch_cfg(spec))
            train_result: dict[str, Any] = {"timesteps": 0}
            progress = champion_dir / f"inflight_{action.fingerprint()}_s{seed}.pt"
            inflight_ckpt = (in_flight or {}).get("trainer_ckpt")
            if inflight_ckpt and int((in_flight or {}).get("current_seed") or -1) == int(seed) and Path(str(inflight_ckpt)).exists():
                trainer.load_training_state(inflight_ckpt)
            try:
                t0 = time.perf_counter()
                train_result = trainer.train(
                    seed_ts,
                    interrupt_after_iters=interrupt_after_iters,
                    progress_path=progress,
                )
                wall += time.perf_counter() - t0
                if train_result.get("interrupted"):
                    trainer.save(progress)
                    inflight_payload = {
                        "action": action.to_dict(),
                        "completed_seeds": [int(s) for s in done_seeds],
                        "seed_returns": seed_returns,
                        "timesteps_used": timesteps_used,
                        "wall": wall,
                        "seed_checkpoints": seed_ckpts,
                        "current_seed": int(seed),
                        "trainer_ckpt": str(progress),
                    }
                    if on_progress is not None:
                        on_progress(inflight_payload)
                    return {
                        "interrupted": True,
                        "in_flight": inflight_payload,
                        "failed": False,
                        "mean_return": 0.0,
                        "stderr": 0.0,
                        "std_return": 0.0,
                        "seed_returns": seed_returns,
                        "n_params": int(sum(p.numel() for p in trainer.agent.parameters())),
                        "wall_clock_s": wall,
                        "timesteps": timesteps_used + int(train_result["timesteps"]),
                        "env_steps": timesteps_used + int(train_result["timesteps"]),
                        "checkpoint": None,
                        "controller_updated": False,
                        "feedback_eval_seed": action.holdout_eval_seed,
                        "independent_assessment": None,
                        "action": action.to_dict(),
                    }
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
                seed_ckpts.append(
                    {
                        "seed": int(seed),
                        "mean_return": float(holdout_stats["mean_return"]),
                        "path": str(ckpt),
                    }
                )
            except Exception:  # noqa: BLE001
                failed = True
                holdout_stats = {"mean_return": 0.0, "std_return": 0.0}
            finally:
                trainer.close()
            seed_returns.append(float(holdout_stats.get("mean_return", 0.0)))
            timesteps_used += int(train_result["timesteps"])
            done_seeds.add(int(seed))
            interrupt_after_iters = None
            if progress.exists():
                progress.unlink()

        arr = np.asarray(seed_returns, dtype=np.float64) if seed_returns else np.zeros(1)
        mean_return = float(arr.mean())
        std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
        stderr = std / max(len(arr), 1) ** 0.5 if len(arr) > 1 else 0.0

    chosen = select_representative_checkpoint(seed_ckpts)
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
            "feedback_eval_seed": action.holdout_eval_seed,
            "n_params": n_params,
            "wall_clock_s": wall,
            "env_steps": timesteps_used,
            "seed_checkpoints": seed_ckpts,
            "representative_checkpoint": chosen,
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
        "env_steps": timesteps_used,
        "checkpoint": None if chosen is None else chosen.get("path"),
        "representative_seed": None if chosen is None else chosen.get("seed"),
        "seed_checkpoints": seed_ckpts,
        "controller_updated": controller_updated,
        "feedback_eval_seed": action.holdout_eval_seed,
        "independent_assessment": assessment,
        "action": action.to_dict(),
    }


def run_research_loop(
    cfg: NexusConfig,
    *,
    controller: ResearchController | None = None,
    resume: bool = True,
    stop_after: int | None = None,
    interrupt_train_after_iters: int | None = None,
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

    if meta.holdout_eval_seed == meta.assessment_eval_seed:
        raise ValueError("holdout_eval_seed must differ from assessment_eval_seed")

    remaining_exp = meta.max_experiments
    remaining_steps = meta.max_timesteps
    env_steps_consumed = 0
    history: list[dict[str, Any]] = []
    seen: set[str] = set()
    best_by_env: dict[str, float] = {}
    default_arch = {
        "hidden_sizes": list(cfg.architecture.hidden_sizes),
        "activation": cfg.architecture.activation,
        "use_residual": cfg.architecture.use_residual,
        "dropout": cfg.architecture.dropout,
        "layer_norm": cfg.architecture.layer_norm,
        "shared_backbone": cfg.architecture.shared_backbone,
        "init": cfg.architecture.init,
    }
    elites: list[ArchitectureSpec] = [ArchitectureSpec.from_dict(default_arch)]
    champion_history: list[str] = []
    n_fail = 0
    last_reward = 0.0
    best_score = 0.0
    n_params = 1
    extra_recent = 0.0
    baselines: dict[str, float] = {}
    in_flight: dict[str, Any] | None = None
    rejected: list[dict[str, Any]] = []
    n_rejected = 0
    wall_clock_s = 0.0
    t_loop = time.perf_counter()

    def _dump_state() -> None:
        state_path.write_text(
            json.dumps(
                {
                    "remaining_experiments": remaining_exp,
                    "remaining_timesteps": remaining_steps,
                    "env_steps_consumed": env_steps_consumed,
                    "history": history,
                    "seen": list(seen),
                    "n_fail": n_fail,
                    "controller": ctrl.state_dict(),
                    "champion_history": champion_history,
                    "elites": [e.to_dict() for e in elites],
                    "best_by_env": best_by_env,
                    "best_score": best_score,
                    "n_params": n_params,
                    "last_reward": last_reward,
                    "extra_recent": extra_recent,
                    "baselines": baselines,
                    "rng": serialize_rng(rng),
                    "in_flight": in_flight,
                    "n_rejected": n_rejected,
                    "note": "Limits are frozen. Controller cannot edit max_experiments or eval rules.",
                },
                indent=2,
                default=str,
            )
        )

    if resume and state_path.exists():
        saved = json.loads(state_path.read_text())
        remaining_exp = int(saved.get("remaining_experiments", remaining_exp))
        remaining_steps = int(saved.get("remaining_timesteps", remaining_steps))
        env_steps_consumed = int(saved.get("env_steps_consumed", env_steps_consumed))
        history = list(saved.get("history", []))
        seen = set(saved.get("seen", []))
        n_fail = int(saved.get("n_fail", 0))
        ctrl.load_state_dict(saved.get("controller", {}))
        champion_history = list(saved.get("champion_history", []))
        if saved.get("elites"):
            elites = [ArchitectureSpec.from_dict(e) for e in saved["elites"]]
        best_by_env = {k: float(v) for k, v in dict(saved.get("best_by_env") or {}).items()}
        best_score = float(saved.get("best_score", best_score))
        n_params = int(saved.get("n_params", n_params))
        last_reward = float(saved.get("last_reward", last_reward))
        extra_recent = float(saved.get("extra_recent", extra_recent))
        baselines = {k: float(v) for k, v in dict(saved.get("baselines") or {}).items()}
        if saved.get("rng"):
            restore_rng(rng, saved["rng"])
        if saved.get("in_flight"):
            in_flight = saved["in_flight"]
        n_rejected = int(saved.get("n_rejected", n_rejected))

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
            if in_flight:
                action = ExperimentAction.from_dict(in_flight["action"])
                proposal = Proposal(
                    action=action,
                    predicted_value=0.0,
                    estimated_cost=action.estimated_timesteps(),
                    reason="resume in-flight experiment",
                    controller=ctrl.name,
                    is_meta_rl=False,
                )
            else:
                valid, filtered = enumerate_candidates(
                    fill=_fill_action,
                    state=obs_state,
                    limits=limits,
                    rng=rng,
                    seen=seen,
                    remaining_steps=remaining_steps,
                    has_champion=champion_exists(champion_dir),
                )
                n_rejected += len(filtered)
                rejected.extend(filtered)
                proposal = ctrl.select_from_candidates(valid, obs_state, limits, rng)
                action = None if proposal is None else proposal.action
                if proposal is None or action is None:
                    history.append(
                        {
                            "stopped": "no_valid_candidates",
                            "n_invalid_avoided": n_rejected,
                            "n_valid_candidates": 0,
                        }
                    )
                    break
                if action.estimated_timesteps() > remaining_steps and action.kind != "extra_evaluation":
                    history.append(
                        {
                            "stopped": "unaffordable_after_rank",
                            "kind": action.kind,
                            "estimated_timesteps": action.estimated_timesteps(),
                            "remaining_timesteps": remaining_steps,
                        }
                    )
                    break
            if action.holdout_eval_seed == action.assessment_eval_seed:
                raise ValueError("assessment seed must not equal holdout feedback seed")
            if (
                meta.independent_eval_seed == meta.holdout_eval_seed
                or meta.independent_eval_seed == meta.assessment_eval_seed
            ):
                raise ValueError("independent_eval_seed must be unused in selection and feedback")
            if not in_flight:
                seen.add(action.fingerprint())
                in_flight = {"action": action.to_dict(), "completed_seeds": []}
                _dump_state()
            result = _run_action(
                cfg,
                action,
                store,
                champion_dir,
                in_flight=in_flight,
                interrupt_after_iters=interrupt_train_after_iters,
                remaining_step_budget=remaining_steps,
            )
            if result.get("interrupted"):
                in_flight = result["in_flight"]
                _dump_state()
                break
            in_flight = None
            interrupt_train_after_iters = None
            actual = int(result["env_steps"])
            env_id = action.env_id
            rw: dict[str, Any] | None = None
            if result["controller_updated"]:
                if env_id not in baselines:
                    baselines[env_id] = float(
                        random_policy_baseline(
                            env_id, episodes=meta.eval_episodes, seed=meta.holdout_eval_seed + 7
                        )["mean_return"]
                    )
                rw = research_reward(
                    env_id=env_id,
                    mean_return=result["mean_return"],
                    stderr=result["stderr"],
                    random_baseline=baselines[env_id],
                    best_score_same_env=best_by_env.get(env_id),
                    n_params=max(int(result["n_params"]), 2),
                    wall_clock_s=float(result["wall_clock_s"]),
                    timesteps=max(actual, 1),
                    failed=bool(result["failed"]),
                )
                rw["eval_seed"] = result["feedback_eval_seed"]
                if int(rw["eval_seed"]) == int(action.assessment_eval_seed):
                    raise RuntimeError("controller feedback used the assessment seed")
                ctrl.update(obs_state["context"], action.kind, float(rw["reward"]))
                last_reward = float(rw["reward"])
            extra_recent = 1.0 if action.kind == "extra_evaluation" else 0.0
            if result["failed"]:
                n_fail += 1
            elif result["controller_updated"]:
                score = float(rw["score"])  # type: ignore[index]
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
            env_steps_consumed += actual
            remaining_steps = max(0, remaining_steps - actual)
            if env_steps_consumed > meta.max_timesteps:
                remaining_steps = 0
            history.append(
                {
                    "proposal": proposal.to_dict(),
                    "result": {k: v for k, v in result.items() if k != "action"},
                    "controller_reward": rw,
                    "controller_updated": result["controller_updated"],
                    "remaining_experiments": remaining_exp,
                    "remaining_timesteps": remaining_steps,
                    "env_steps_consumed": env_steps_consumed,
                }
            )
            _dump_state()
            if remaining_steps <= 0:
                break
            if stop_after is not None and len([h for h in history if "result" in h or "skipped_duplicate" in h]) >= stop_after:
                break
    finally:
        store.close()

    independent: dict[str, Any] | None = None
    champ = Path(meta.champion_dir) / "champion_current.pt"
    if champ.exists() and in_flight is None:
        agent, payload = _load_champion_agent(champ, meta.env_id, cfg.ppo.device)
        independent = evaluate_policy(
            agent,
            meta.env_id,
            episodes=meta.eval_episodes,
            seed=meta.independent_eval_seed,
            device=torch.device(cfg.ppo.device),
        )
        independent["eval_seed"] = meta.independent_eval_seed
        independent["env_id"] = meta.env_id
        used = {meta.holdout_eval_seed, meta.assessment_eval_seed, meta.holdout_eval_seed + 7}
        if meta.independent_eval_seed in used:
            raise RuntimeError("independent eval seed collided with selection/feedback seeds")

    wall_clock_s = time.perf_counter() - t_loop
    n_done = len([h for h in history if "result" in h])
    gain = float(best_score)
    gain_per_1k = gain / max(env_steps_consumed / 1000.0, 1e-9)
    gain_per_s = gain / max(wall_clock_s, 1e-9)
    return {
        "controller": ctrl.name,
        "is_meta_rl": ctrl.is_meta_rl,
        "history": history,
        "n_experiments": n_done,
        "n_fail": n_fail,
        "n_skipped": len([h for h in history if "skipped_duplicate" in h]),
        "n_rejected_proposals": n_rejected,
        "n_invalid_avoided": n_rejected,
        "n_useful_experiments": max(n_done - n_fail, 0),
        "efficiency": {
            "best_task_normalized_score": gain,
            "gain_per_1k_env_steps": gain_per_1k,
            "gain_per_wall_s": gain_per_s,
            "env_steps_consumed": env_steps_consumed,
            "wall_clock_s": wall_clock_s,
            "budget_exceeded": env_steps_consumed > meta.max_timesteps,
        },
        "best_score_by_env": best_by_env,
        "champion_history": champion_history,
        "remaining_experiments": remaining_exp,
        "remaining_timesteps": remaining_steps,
        "env_steps_consumed": env_steps_consumed,
        "max_timesteps": meta.max_timesteps,
        "independent_eval": independent,
        "interrupted": in_flight is not None,
        "wall_clock_s": wall_clock_s,
        "caveat": (
            "Controller reward uses holdout eval seeds only. Independent eval uses "
            "independent_eval_seed, never selection or bandit feedback. LinUCB is not meta-RL."
        ),
    }


def _arm_trace(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for i, h in enumerate(history):
        if "proposal" not in h:
            continue
        prop = h["proposal"]
        action = prop.get("action") or {}
        rows.append(
            {
                "t": i,
                "kind": action.get("kind"),
                "budget_tier": action.get("budget_tier"),
                "ucb_scores": prop.get("ucb_scores"),
                "research_value": prop.get("research_value"),
                "controller_updated": h.get("controller_updated"),
            }
        )
    return rows


def compare_controllers(
    cfg: NexusConfig,
    names: tuple[str, ...] = ("random", "epsilon_greedy", "linucb", "linucb_frozen"),
    controller_seeds: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Paired equal-budget comparison on a predefined controller-seed set.

    Every controller sees the same seed (same train-seed formula, same holdout
    and assessment split). Replicates are the seed list, not offset-per-method RNGs.
    """
    seeds = controller_seeds if controller_seeds is not None else (int(cfg.meta.seed), int(cfg.meta.seed) + 1)
    rand_bl = float(
        random_policy_baseline(
            cfg.meta.env_id, episodes=cfg.meta.eval_episodes, seed=cfg.meta.holdout_eval_seed + 7
        )["mean_return"]
    )
    paired: list[dict[str, Any]] = []
    for s in seeds:
        runs: dict[str, Any] = {}
        train_seeds_seen: list[list[int]] | None = None
        for name in names:
            local = replace(
                cfg.meta,
                controller=name,
                seed=int(s),
                db_path=str(Path(cfg.meta.db_path).with_name(f"meta_{name}_s{s}.sqlite")),
                state_path=str(Path(cfg.meta.state_path).with_name(f"state_{name}_s{s}.json")),
                champion_dir=str(Path(cfg.meta.champion_dir) / f"{name}_s{s}"),
            )
            cfg_i = replace(cfg, meta=local)
            ctrl = make_controller(name, epsilon=cfg.meta.epsilon, alpha=cfg.meta.linucb_alpha)
            result = run_research_loop(cfg_i, controller=ctrl, resume=False)
            rewards = [
                h["controller_reward"]["reward"]
                for h in result["history"]
                if h.get("controller_reward")
            ]
            expected_train = [int(s) + 1000 + i for i in range(max(1, cfg.meta.n_train_seeds))]
            if train_seeds_seen is None:
                train_seeds_seen = [expected_train]
            elif expected_train not in train_seeds_seen:
                train_seeds_seen.append(expected_train)
            ind = dict(result.get("independent_eval") or {})
            if ind.get("mean_return") is not None:
                ind["task_normalized"] = task_normalized_score(
                    cfg.meta.env_id, float(ind["mean_return"]), rand_bl
                )
                ind["random_baseline"] = rand_bl
            runs[name] = {
                "n_experiments": result["n_experiments"],
                "n_fail": result["n_fail"],
                "n_skipped": result["n_skipped"],
                "n_rejected_proposals": result.get("n_rejected_proposals", 0),
                "n_invalid_avoided": result.get("n_invalid_avoided", 0),
                "n_useful_experiments": result.get("n_useful_experiments", result["n_experiments"]),
                "mean_controller_reward": float(np.mean(rewards)) if rewards else 0.0,
                "best_score_by_env": result["best_score_by_env"],
                "env_steps_consumed": result["env_steps_consumed"],
                "remaining_timesteps": result["remaining_timesteps"],
                "wall_clock_s": result.get("wall_clock_s"),
                "efficiency": result.get("efficiency"),
                "independent_eval": ind,
                "arm_trace": _arm_trace(result["history"]),
                "is_meta_rl": False,
                "train_seeds": expected_train,
            }
        if len({tuple(t) for t in train_seeds_seen or []}) != 1:
            raise RuntimeError("paired comparison used mismatched train seeds")
        paired.append({"controller_seed": int(s), "train_seeds": (train_seeds_seen or [[]])[0], "runs": runs})

    summary = []
    for name in names:
        rewards = [p["runs"][name]["mean_controller_reward"] for p in paired]
        steps = [p["runs"][name]["env_steps_consumed"] for p in paired]
        fails = [p["runs"][name]["n_fail"] for p in paired]
        skips = [p["runs"][name]["n_skipped"] for p in paired]
        rejected = [p["runs"][name]["n_rejected_proposals"] for p in paired]
        walls = [p["runs"][name]["wall_clock_s"] or 0.0 for p in paired]
        useful = [p["runs"][name]["n_useful_experiments"] for p in paired]
        avoided = [p["runs"][name].get("n_invalid_avoided", 0) for p in paired]
        indep = [
            p["runs"][name]["independent_eval"].get("mean_return")
            for p in paired
            if p["runs"][name].get("independent_eval")
        ]
        normed = [
            p["runs"][name]["independent_eval"].get("task_normalized")
            for p in paired
            if p["runs"][name].get("independent_eval")
            and p["runs"][name]["independent_eval"].get("task_normalized") is not None
        ]
        gains = [
            (p["runs"][name].get("efficiency") or {}).get("gain_per_1k_env_steps")
            for p in paired
            if (p["runs"][name].get("efficiency") or {}).get("gain_per_1k_env_steps") is not None
        ]
        summary.append(
            {
                "controller": name,
                "n_replicates": len(seeds),
                "mean_controller_reward": float(np.mean(rewards)),
                "std_controller_reward": float(np.std(rewards, ddof=1)) if len(rewards) > 1 else 0.0,
                "mean_independent_return": float(np.mean(indep)) if indep else None,
                "std_independent_return": float(np.std(indep, ddof=1)) if len(indep) > 1 else (0.0 if indep else None),
                "mean_independent_normalized": float(np.mean(normed)) if normed else None,
                "mean_env_steps": float(np.mean(steps)),
                "total_env_steps": int(np.sum(steps)),
                "mean_wall_clock_s": float(np.mean(walls)),
                "mean_fail": float(np.mean(fails)),
                "mean_skipped": float(np.mean(skips)),
                "mean_rejected_proposals": float(np.mean(rejected)),
                "mean_invalid_avoided": float(np.mean(avoided)),
                "mean_useful_experiments": float(np.mean(useful)),
                "mean_gain_per_1k_env_steps": float(np.mean(gains)) if gains else None,
                "is_meta_rl": False,
            }
        )
    return {
        "equal_budget": {
            "max_experiments": cfg.meta.max_experiments,
            "max_timesteps": cfg.meta.max_timesteps,
            "train_timesteps": cfg.meta.train_timesteps,
            "explore_timesteps": cfg.meta.explore_timesteps,
            "n_train_seeds": cfg.meta.n_train_seeds,
            "controller_seeds": list(seeds),
            "env_id": cfg.meta.env_id,
            "holdout_eval_seed": cfg.meta.holdout_eval_seed,
            "assessment_eval_seed": cfg.meta.assessment_eval_seed,
            "independent_eval_seed": cfg.meta.independent_eval_seed,
        },
        "paired": paired,
        "summary": summary,
        "paired_deltas_vs_random": _paired_deltas_vs_baseline(paired, names, baseline="random"),
        "caveat": (
            "Paired comparison: identical controller seeds and train-seed sets. "
            "Independent champion eval uses independent_eval_seed. "
            "linucb_frozen never updates A,b. LinUCB is a contextual bandit, not meta-RL. "
            "V0.5.2 ranks only pre-filtered valid candidates."
        ),
    }


def _ci95(xs: list[float] | np.ndarray) -> dict[str, float]:
    arr = np.asarray(list(xs), dtype=np.float64)
    if arr.size == 0:
        return {"n": 0, "mean": float("nan"), "lo": float("nan"), "hi": float("nan")}
    mean = float(arr.mean())
    if arr.size < 2:
        return {"n": int(arr.size), "mean": mean, "lo": mean, "hi": mean}
    half = 1.96 * float(arr.std(ddof=1)) / math.sqrt(arr.size)
    return {"n": int(arr.size), "mean": mean, "lo": mean - half, "hi": mean + half}


def _paired_deltas_vs_baseline(
    paired: list[dict[str, Any]],
    names: tuple[str, ...],
    baseline: str,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in names:
        if name == baseline:
            continue
        indep: list[float] = []
        normed: list[float] = []
        steps: list[float] = []
        for p in paired:
            a = p["runs"][name]
            b = p["runs"][baseline]
            ia = (a.get("independent_eval") or {}).get("mean_return")
            ib = (b.get("independent_eval") or {}).get("mean_return")
            if ia is not None and ib is not None:
                indep.append(float(ia) - float(ib))
            na = (a.get("independent_eval") or {}).get("task_normalized")
            nb = (b.get("independent_eval") or {}).get("task_normalized")
            if na is not None and nb is not None:
                normed.append(float(na) - float(nb))
            steps.append(float(a["env_steps_consumed"]) - float(b["env_steps_consumed"]))
        out[f"{name}_minus_{baseline}"] = {
            "independent_return": _ci95(indep),
            "independent_normalized": _ci95(normed),
            "env_steps": _ci95(steps),
        }
    return out
