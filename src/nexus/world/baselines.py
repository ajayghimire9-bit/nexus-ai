"""Control baselines and episode evaluation. Env steps are counted."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from nexus.tasks.spec import TaskSpec, make_task_env


def heuristic_cartpole(obs: np.ndarray) -> int:
    o = np.asarray(obs, dtype=np.float64).reshape(-1)
    return 1 if (o[2] + 0.25 * o[3]) > 0.0 else 0


def random_cartpole(obs: np.ndarray, rng: np.random.Generator) -> int:
    del obs
    return int(rng.integers(0, 2))


def run_episodes(
    spec: TaskSpec,
    *,
    act_fn: Callable[[np.ndarray], int],
    episodes: int,
    seed: int,
    max_steps: int = 500,
) -> dict[str, Any]:
    returns = []
    lengths = []
    interactions = 0
    env = make_task_env(spec, seed=seed)
    for ep in range(episodes):
        obs, _ = env.reset(seed=seed + ep)
        done = False
        total = 0.0
        steps = 0
        while not done and steps < max_steps:
            a = int(act_fn(np.asarray(obs, dtype=np.float32)))
            obs, rew, term, trunc, _ = env.step(a)
            total += float(rew)
            steps += 1
            interactions += 1
            done = bool(term or trunc)
        returns.append(total)
        lengths.append(steps)
    env.close()
    arr = np.asarray(returns, dtype=np.float64)
    return {
        "mean_return": float(arr.mean()) if arr.size else 0.0,
        "std_return": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
        "returns": [float(x) for x in arr],
        "mean_length": float(np.mean(lengths)) if lengths else 0.0,
        "env_interactions": interactions,
        "episodes": episodes,
        "eval_seed": seed,
        "task_id": spec.task_id,
    }
