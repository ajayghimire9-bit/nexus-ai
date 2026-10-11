from __future__ import annotations

import math
from typing import Any

# Task-specific scales so CartPole 500 is never ranked against Acrobot -80.
_TASK_SCALES = {
    "CartPole-v1": 500.0,
    "Acrobot-v1": 500.0,
}


def task_normalized_score(env_id: str, mean_return: float, random_baseline: float) -> float:
    """Map return to [roughly -1, 1] relative to a random policy on the same env."""
    scale = _TASK_SCALES.get(env_id, max(abs(random_baseline), 1.0))
    return float(mean_return - random_baseline) / scale


def research_reward(
    *,
    env_id: str,
    mean_return: float,
    stderr: float,
    random_baseline: float,
    best_score_same_env: float | None,
    n_params: int,
    wall_clock_s: float,
    timesteps: int,
    failed: bool,
) -> dict[str, Any]:
    """Progress per unit compute for *controller update only*.

    Final independent assessment must use a different eval seed and is not this reward.
    """
    score = task_normalized_score(env_id, mean_return, random_baseline)
    if failed:
        reward = -1.0
        return {
            "score": score,
            "reward": reward,
            "improvement": 0.0,
            "failed": True,
        }
    prev = best_score_same_env if best_score_same_env is not None else score
    improvement = score - prev
    sample_eff = score / max(timesteps / 1000.0, 0.25)
    complexity = math.log(max(n_params, 2)) / 12.0
    time_pen = min(wall_clock_s / 30.0, 1.0)
    uncertainty = min(abs(stderr) / _TASK_SCALES.get(env_id, 500.0), 1.0)
    reward = (
        improvement
        + 0.15 * sample_eff
        - 0.08 * complexity
        - 0.05 * time_pen
        - 0.10 * uncertainty
    )
    return {
        "score": score,
        "reward": float(reward),
        "improvement": float(improvement),
        "sample_efficiency_term": float(sample_eff),
        "failed": False,
    }
