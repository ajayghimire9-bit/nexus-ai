from __future__ import annotations

import math
import random
from typing import Any

from nexus.tasks.spec import TaskSpec


class CurriculumSelector:
    """Bounded task selector. Cannot edit eval seeds, episode counts, or step caps."""

    name = "competence_uncertainty_forgetting"

    def __init__(self, tasks: tuple[TaskSpec, ...]) -> None:
        self.tasks = tasks
        self.peak: dict[str, float] = {t.task_id: float("-inf") for t in tasks}
        self.last: dict[str, float] = {t.task_id: 0.0 for t in tasks}
        self.std: dict[str, float] = {t.task_id: 1.0 for t in tasks}
        self.counts: dict[str, int] = {t.task_id: 0 for t in tasks}

    def observe(self, task_id: str, mean_return: float, std_return: float) -> None:
        self.last[task_id] = float(mean_return)
        self.std[task_id] = float(std_return)
        self.counts[task_id] += 1
        if mean_return > self.peak[task_id]:
            self.peak[task_id] = float(mean_return)

    def score(self, task_id: str) -> float:
        competence = max(0.0, min(1.0, self.last[task_id] / 500.0))
        uncertainty = min(1.0, self.std[task_id] / 150.0)
        forgetting = 0.0
        if self.peak[task_id] > float("-inf"):
            forgetting = max(0.0, (self.peak[task_id] - self.last[task_id]) / 500.0)
        explore = 1.0 / math.sqrt(self.counts[task_id] + 1.0)
        return (1.0 - competence) + 0.5 * uncertainty + forgetting + 0.15 * explore

    def select(self, rng: random.Random) -> TaskSpec:
        scored = [(self.score(t.task_id), t) for t in self.tasks]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]


def fixed_order(tasks: tuple[TaskSpec, ...], step: int) -> TaskSpec:
    return tasks[step % len(tasks)]


def random_order(tasks: tuple[TaskSpec, ...], rng: random.Random) -> TaskSpec:
    return rng.choice(list(tasks))


def assert_frozen_eval_rules(limits: dict[str, Any], current: dict[str, Any]) -> None:
    for key in ("independent_eval_seed", "eval_episodes", "max_timesteps_per_task"):
        if key in limits and current.get(key) != limits[key]:
            raise RuntimeError(f"curriculum tried to change frozen limit {key}")
