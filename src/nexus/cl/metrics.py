from __future__ import annotations

import math
from typing import Any

import numpy as np


def _ci95(xs: list[float] | np.ndarray) -> dict[str, float]:
    arr = np.asarray(list(xs), dtype=np.float64)
    if arr.size == 0:
        return {"n": 0, "mean": float("nan"), "lo": float("nan"), "hi": float("nan")}
    mean = float(arr.mean())
    if arr.size < 2:
        return {"n": int(arr.size), "mean": mean, "lo": mean, "hi": mean}
    half = 1.96 * float(arr.std(ddof=1)) / math.sqrt(arr.size)
    return {"n": int(arr.size), "mean": mean, "lo": mean - half, "hi": mean + half}


def transfer_metrics(
    *,
    peak_during_task: dict[str, float],
    final_matrix: dict[str, dict[str, float]],
    independent: dict[str, float],
    steps_to_threshold: dict[str, float] | None = None,
    independent_scratch: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Forgetting / forward / backward transfer from a task-eval matrix.

    `final_matrix[trained_through][eval_task]` is return after that training phase.
    `independent[task]` is from-scratch performance with the same step budget.
    """
    tasks = list(independent.keys())
    forgetting = {}
    for t in tasks:
        peak = peak_during_task.get(t)
        last = None
        if tasks[-1] in final_matrix:
            last = final_matrix[tasks[-1]].get(t)
        if peak is None or last is None:
            forgetting[t] = None
        else:
            forgetting[t] = float(peak) - float(last)
    fwd = {}
    for i, t in enumerate(tasks):
        if i == 0:
            continue
        prev = tasks[i - 1]
        after_prev = final_matrix.get(prev, {}).get(t)
        scratch = independent.get(t)
        if after_prev is None or scratch is None:
            fwd[t] = None
        else:
            fwd[t] = float(after_prev) - float(scratch)
    bwd = {}
    if tasks:
        last = tasks[-1]
        for t in tasks[:-1]:
            after = final_matrix.get(last, {}).get(t)
            peak = peak_during_task.get(t)
            if after is None or peak is None:
                bwd[t] = None
            else:
                bwd[t] = float(after) - float(peak)
    return {
        "forgetting": forgetting,
        "mean_forgetting": float(np.mean([v for v in forgetting.values() if v is not None] or [0.0])),
        "forward_transfer": fwd,
        "backward_transfer": bwd,
        "steps_to_threshold": steps_to_threshold,
        "independent_scratch": independent_scratch or independent,
    }


def summarize_seeds(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    return _ci95(vals)
