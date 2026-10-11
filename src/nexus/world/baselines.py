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
    trans_obs: list[np.ndarray] = []
    trans_act: list[int] = []
    trans_next: list[np.ndarray] = []
    trans_term: list[bool] = []
    env = make_task_env(spec, seed=seed)
    for ep in range(episodes):
        obs, _ = env.reset(seed=seed + ep)
        done = False
        total = 0.0
        steps = 0
        while not done and steps < max_steps:
            o = np.asarray(obs, dtype=np.float32).reshape(-1)
            a = int(act_fn(o))
            nxt, rew, term, trunc, _ = env.step(a)
            trans_obs.append(o)
            trans_act.append(a)
            trans_next.append(np.asarray(nxt, dtype=np.float32).reshape(-1))
            trans_term.append(bool(term))
            obs = nxt
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
        "transitions": {
            "obs": np.stack(trans_obs, axis=0) if trans_obs else np.zeros((0, spec.obs_dim), dtype=np.float32),
            "action": np.asarray(trans_act, dtype=np.int64),
            "next_obs": np.stack(trans_next, axis=0) if trans_next else np.zeros((0, spec.obs_dim), dtype=np.float32),
            "terminated": np.asarray(trans_term, dtype=np.bool_),
        },
    }
