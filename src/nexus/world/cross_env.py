"""Cross-environment test: frozen CartPole WM+MPC recipe on Pendulum-v1. Not AGI."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from nexus.cl.metrics import seed_level_ci
from nexus.cl.serialize import dumps_strict
from nexus.config import ArchitectureConfig, PPOConfig
from nexus.rl.ppo import PPOTrainer
from nexus.tasks.cartpole_family import source_policy_task
from nexus.tasks.pendulum_family import PENDULUM_MAX_STEPS, pendulum_default, tensors_compatible
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec, task_env_fns
from nexus.world.baselines import fixed_pendulum_action, heuristic_pendulum_pd, run_episodes
from nexus.world.data import assert_disjoint_seeds, collect_transitions
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_EPOCHS, FROZEN_HIDDEN, FROZEN_KIND, FROZEN_N_TRAIN, FROZEN_N_VAL, FROZEN_PRIMARY_HORIZON
from nexus.world.imagine import multi_step_errors
from nexus.world.planning import InferenceCounter, RandomShootingMPC
from nexus.world.protocol import V089X_EVAL_SEED, V089X_PPO_SEED, V089X_SOURCE_COLLECT_SEED, V089X_TRAIN_SEED, V089X_VAL_COLLECT_SEED
from nexus.world.rewards import pendulum_step_reward
from nexus.world.train import one_step_errors, train_world_model
from nexus.world.v085 import _git_meta

PPO_TIMESTEPS = 16_384
EVAL_EPISODES = 2
N_CAND = FROZEN_CANDIDATES[FROZEN_PRIMARY_HORIZON]  # 16


def architecture_compatibility(src: TaskSpec, tgt: TaskSpec) -> dict[str, Any]:
    ok = tensors_compatible(src, tgt)
    return {
        "source_obs_dim": src.obs_dim,
        "source_n_actions": src.n_actions,
        "target_obs_dim": tgt.obs_dim,
        "target_n_actions": tgt.n_actions,
        "tensors_compatible": ok,
        "weight_transfer_attempted": False,
        "reason": "obs/action ranks differ; CartPole checkpoint cannot load into Pendulum tensors" if not ok else "compatible",
    }


def _planner(wm: Any, inf: InferenceCounter | None = None) -> RandomShootingMPC:
    return RandomShootingMPC(
        model=inf if inf is not None else wm,
        n_actions=3,
        horizon=FROZEN_PRIMARY_HORIZON,
        n_candidates=int(N_CAND),
        seed=0,
        objective="predicted_reward",
        step_reward=pendulum_step_reward,
        inference=inf,
        enforce_time_budget=True,
    )


def eval_controller(spec: TaskSpec, act_fn: Any, *, seed: int, episodes: int = EVAL_EPISODES, planner: RandomShootingMPC | None = None) -> dict[str, Any]:
    return run_episodes(
        spec,
        act_fn=act_fn,
        episodes=episodes,
        seed=int(seed),
        max_steps=PENDULUM_MAX_STEPS,
        on_episode_start=(lambda ep, p=planner, s=seed: p.reset_episode(int(s) + 1000 * int(ep)) if p is not None else None),
    )


def greedy_ppo_actor(trainer: PPOTrainer) -> Any:
    agent = trainer.agent
    device = trainer.device

    def act(obs: np.ndarray) -> int:
        x = trainer._obs_tensor_no_update(np.asarray(obs, dtype=np.float32).reshape(1, -1))
        with torch.no_grad():
            actor_x, _ = agent._features(x)
            logits = agent.policy_head(actor_x)
            return int(logits.argmax(dim=-1).reshape(-1)[0].item())

    return act


def run_cross_environment_benchmark(
    *,
    n_model_seeds: int = 10,
    n_train: int = FROZEN_N_TRAIN,
    n_val: int = FROZEN_N_VAL,
    epochs: int = FROZEN_EPOCHS,
    eval_episodes: int = EVAL_EPISODES,
    ppo_timesteps: int = PPO_TIMESTEPS,
    artifact_path: str | Path | None = "artifacts/cross_environment.json",
    checkpoint_dir: str | Path = "checkpoints/cross_env",
    quick: bool = False,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    if quick:
        n_model_seeds = min(n_model_seeds, 1)
        n_train, n_val, epochs = 48, 24, 1
        eval_episodes = 1
        ppo_timesteps = 512
    spec = pendulum_default()
    cart = source_policy_task()
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    git = _git_meta()
    protocol = {
        "code_version": "v0.8.9-cross-env",
        "parent_commit": "ef6588c",
        "hypothesis": "H1_same_wm_mpc_algorithm_on_pendulum",
        "kind": FROZEN_KIND,
        "hidden": list(FROZEN_HIDDEN),
        "horizon": FROZEN_PRIMARY_HORIZON,
        "n_candidates": int(N_CAND),
        "n_train": n_train,
        "n_val": n_val,
        "epochs": epochs,
        "eval_episodes": eval_episodes,
        "eval_seed": V089X_EVAL_SEED,
        "n_model_seeds": n_model_seeds,
        "ppo_timesteps": ppo_timesteps,
        "pendulum_torques": [-2.0, 0.0, 2.0],
        "reward": "gymnasium_pendulum_published",
        "retuned_architecture": False,
        "cartpole_physics_version": CARTPOLE_PHYSICS_VERSION,
        "compatibility": architecture_compatibility(cart, spec),
        "is_agi": False,
        "claims_weight_transfer": False,
        "claims_learning_to_learn": False,
        "quick": quick,
        "git": git,
    }
    protocol["protocol_hash"] = hashlib.sha256(dumps_strict(protocol).encode()).hexdigest()[:16]

    per_seed: list[dict[str, Any]] = []
    for mseed in range(n_model_seeds):
        train = collect_transitions(
            spec, n_transitions=n_train, env_seeds=tuple(range(10 + 8 * mseed, 18 + 8 * mseed)),
            base_seed=V089X_SOURCE_COLLECT_SEED + 19 * mseed, mix=("random",),
        )
        val = collect_transitions(
            spec, n_transitions=n_val, env_seeds=tuple(range(400 + 8 * mseed, 408 + 8 * mseed)),
            base_seed=V089X_VAL_COLLECT_SEED + 19 * mseed, mix=("random",),
        )
        assert_disjoint_seeds(train, val)
        wm, slog = train_world_model(
            train, val, kind=FROZEN_KIND, epochs=epochs, seed=V089X_TRAIN_SEED + 13 * mseed, hidden=FROZEN_HIDDEN, n_actions=spec.n_actions,
        )  # type: ignore[arg-type]
        pred = one_step_errors(wm, val)
        ms = multi_step_errors(wm, val, (1, 3, 8))
        inf = InferenceCounter(wm)
        planner = _planner(wm, inf)
        rng = np.random.default_rng(V089X_EVAL_SEED)

        def _rand(o: np.ndarray, r=rng) -> int:
            return int(r.integers(0, 3))

        ev_rand = eval_controller(spec, _rand, seed=V089X_EVAL_SEED, episodes=eval_episodes)
        ev_zero = eval_controller(spec, fixed_pendulum_action(1), seed=V089X_EVAL_SEED, episodes=eval_episodes)
        ev_neg = eval_controller(spec, fixed_pendulum_action(0), seed=V089X_EVAL_SEED, episodes=eval_episodes)
        ev_pos = eval_controller(spec, fixed_pendulum_action(2), seed=V089X_EVAL_SEED, episodes=eval_episodes)
        ev_heu = eval_controller(spec, heuristic_pendulum_pd, seed=V089X_EVAL_SEED, episodes=eval_episodes)
        inf.calls = 0
        inf.states = 0
        ev_mpc = eval_controller(spec, lambda o, p=planner: int(p.act(o)[0]), seed=V089X_EVAL_SEED, episodes=eval_episodes, planner=planner)

        ppo_cfg = PPOConfig(env_id="Pendulum-v1", num_envs=4, total_timesteps=ppo_timesteps, num_steps=64, seed=V089X_PPO_SEED + mseed, log_interval=100)
        trainer = PPOTrainer(ppo_cfg, ArchitectureConfig(), env_fns=task_env_fns(spec, ppo_cfg.num_envs, V089X_PPO_SEED + mseed))
        ppo_log = trainer.train(ppo_timesteps)
        ev_ppo = eval_controller(spec, greedy_ppo_actor(trainer), seed=V089X_EVAL_SEED, episodes=eval_episodes)
        trainer.close()

        per_seed.append(
            {
                "model_seed": mseed,
                "pretrain_interactions": int(train.env_interactions + val.env_interactions),
                "source_val_mae": slog["best_val"],
                "val_one_step_mae": pred["mae"],
                "val_multi_step": {k: ms[k] for k in ms},
                "mean_pred_term_on_val": pred.get("term_brier"),
                "returns": {
                    "random": ev_rand["mean_return"],
                    "always_zero": ev_zero["mean_return"],
                    "always_neg": ev_neg["mean_return"],
                    "always_pos": ev_pos["mean_return"],
                    "heuristic_pd": ev_heu["mean_return"],
                    "mpc": ev_mpc["mean_return"],
                    "ppo": ev_ppo["mean_return"],
                },
                "eval_interactions": {
                    k: int(v["env_interactions"])
                    for k, v in {
                        "random": ev_rand, "always_zero": ev_zero, "heuristic_pd": ev_heu, "mpc": ev_mpc, "ppo": ev_ppo,
                    }.items()
                },
                "mpc_inferences": inf.states,
                "mpc_calls": inf.calls,
                "ppo_timesteps": int(ppo_log.get("timesteps", ppo_timesteps)),
            }
        )
        print(f"cross-env seed={mseed} mpc={ev_mpc['mean_return']:.1f} rand={ev_rand['mean_return']:.1f} heu={ev_heu['mean_return']:.1f}", flush=True)

    def _rets(name: str) -> list[float]:
        return [float(s["returns"][name]) for s in per_seed]

    def _delta(a: str, b: str) -> list[float]:
        return [float(s["returns"][a]) - float(s["returns"][b]) for s in per_seed]

    payload = {
        "protocol": protocol,
        "task": dict(spec.params) | {"task_id": spec.task_id, "obs_dim": spec.obs_dim, "n_actions": spec.n_actions},
        "returns": {k: seed_level_ci(_rets(k)) for k in ("random", "always_zero", "always_neg", "always_pos", "heuristic_pd", "mpc", "ppo")},
        "paired": {
            "mpc_minus_random": seed_level_ci(_delta("mpc", "random")),
            "mpc_minus_heuristic": seed_level_ci(_delta("mpc", "heuristic_pd")),
            "mpc_minus_zero": seed_level_ci(_delta("mpc", "always_zero")),
            "ppo_minus_random": seed_level_ci(_delta("ppo", "random")),
            "heuristic_minus_random": seed_level_ci(_delta("heuristic_pd", "random")),
        },
        "prediction": {
            "one_step_mae": seed_level_ci([float(s["val_one_step_mae"]) for s in per_seed]),
            "source_val_mae": seed_level_ci([float(s["source_val_mae"]) for s in per_seed]),
        },
        "costs": {
            "mean_pretrain": float(np.mean([s["pretrain_interactions"] for s in per_seed])) if per_seed else 0.0,
            "mean_mpc_inferences": float(np.mean([s["mpc_inferences"] for s in per_seed])) if per_seed else 0.0,
            "ppo_timesteps": ppo_timesteps,
        },
        "h1_mpc_beats_random": bool(per_seed) and float(seed_level_ci(_delta("mpc", "random"))["lo"]) > 0,
        "per_seed": per_seed,
        "wall_clock_s": time.perf_counter() - t0,
        "is_agi": False,
        "caveat": "Same algorithm, new family. Not CartPole weight transfer. Not learning-to-learn. Not AGI.",
    }
    if artifact_path is not None:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        Path(artifact_path).write_text(dumps_strict(payload))
    return payload
