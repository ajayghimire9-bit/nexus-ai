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


def continual_metrics(
    *,
    matrix: dict[str, dict[str, float]],
    task_order: list[str] | tuple[str, ...],
    scratch: dict[str, float],
) -> dict[str, Any]:
    """Lopez-Paz-style ACC / FWT / BWT from R[trained_through][eval_task]."""
    order = list(task_order)
    if not order:
        return {"acc": 0.0, "forgetting": {}, "mean_forgetting": 0.0, "forward_transfer": {}, "backward_transfer": {}}
    last = order[-1]
    acc_vals = [float(matrix[last][t]) for t in order if last in matrix and t in matrix[last]]
    forgetting = {}
    bwd = {}
    for t in order[:-1]:
        r_ii = matrix.get(t, {}).get(t)
        r_ti = matrix.get(last, {}).get(t)
        if r_ii is None or r_ti is None:
            forgetting[t] = None
            bwd[t] = None
        else:
            forgetting[t] = float(r_ii) - float(r_ti)
            bwd[t] = float(r_ti) - float(r_ii)
    fwd = {}
    for i, t in enumerate(order):
        if i == 0:
            continue
        prev = order[i - 1]
        r_prev = matrix.get(prev, {}).get(t)
        base = scratch.get(t)
        if r_prev is None or base is None:
            fwd[t] = None
        else:
            fwd[t] = float(r_prev) - float(base)
    def _mean(xs: list[float | None]) -> float:
        vals = [float(v) for v in xs if v is not None]
        return float(np.mean(vals)) if vals else 0.0

    return {
        "acc": float(np.mean(acc_vals)) if acc_vals else 0.0,
        "forgetting": forgetting,
        "mean_forgetting": _mean(list(forgetting.values())),
        "forward_transfer": fwd,
        "mean_forward_transfer": _mean(list(fwd.values())),
        "backward_transfer": bwd,
        "mean_backward_transfer": _mean(list(bwd.values())),
        "task_order": order,
    }
