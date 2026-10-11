from __future__ import annotations

import math
from typing import Any

import numpy as np


# Two-sided 95% Student-t critical values by df. df>=30 uses 1.96.
_T_CRIT_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    15: 2.131,
    20: 2.086,
    29: 2.045,
}


def _t_crit_95(df: int) -> float:
    if df < 1:
        return float("nan")
    if df >= 30:
        return 1.96
    if df in _T_CRIT_95:
        return _T_CRIT_95[df]
    keys = sorted(k for k in _T_CRIT_95 if k <= df)
    return _T_CRIT_95[keys[-1]]


def _ci95(xs: list[float] | np.ndarray, *, student_t: bool = False) -> dict[str, float]:
    arr = np.asarray(list(xs), dtype=np.float64)
    if arr.size == 0:
        return {"n": 0, "mean": float("nan"), "lo": float("nan"), "hi": float("nan")}
    mean = float(arr.mean())
    if arr.size < 2:
        return {"n": int(arr.size), "mean": mean, "lo": mean, "hi": mean}
    se = float(arr.std(ddof=1)) / math.sqrt(arr.size)
    crit = _t_crit_95(int(arr.size) - 1) if student_t else 1.96
    half = crit * se
    out = {"n": int(arr.size), "mean": mean, "lo": mean - half, "hi": mean + half, "se": se}
    if student_t:
        out["interval"] = "student_t_95"
        out["df"] = int(arr.size) - 1
    else:
        out["interval"] = "normal_95"
    return out


def seed_level_ci(per_seed: list[float]) -> dict[str, float]:
    """95% Student-t interval. ``n`` is independent source-training seeds, not tasks."""
    return _ci95(per_seed, student_t=True)


def paired_seed_deltas(
    *,
    per_seed_task: dict[int, dict[str, float]],
    treatment: str,
    baseline: str,
) -> dict[str, Any]:
    """Each source seed contributes one mean (treatment−baseline) across its targets."""
    deltas: list[float] = []
    by_task: dict[str, list[float]] = {}
    for _seed, tasks in sorted(per_seed_task.items()):
        diffs = []
        for task_id, row in tasks.items():
            if not isinstance(row, dict):
                continue
            t = row.get(treatment)
            b = row.get(baseline)
            if t is None or b is None:
                continue
            d = float(t) - float(b)
            diffs.append(d)
            by_task.setdefault(task_id, []).append(d)
        if diffs:
            deltas.append(float(np.mean(diffs)))
    return {
        "per_seed_mean_delta": deltas,
        "across_seeds": seed_level_ci(deltas),
        "by_task": {k: seed_level_ci(v) for k, v in by_task.items()},
        "replication_unit": "source_training_seed",
        "n_seeds": len(deltas),
    }


def hierarchical_bootstrap_ci(
    per_seed_means: list[float],
    *,
    n_boot: int = 2000,
    seed: int = 0,
) -> dict[str, float]:
    """Resample source seeds, then percentile interval of the mean."""
    arr = np.asarray(per_seed_means, dtype=np.float64)
    if arr.size == 0:
        return {"n": 0, "mean": float("nan"), "lo": float("nan"), "hi": float("nan")}
    rng = np.random.default_rng(seed)
    boots = [float(arr[rng.integers(0, arr.size, size=arr.size)].mean()) for _ in range(n_boot)]
    b = np.asarray(boots)
    return {
        "n": int(arr.size),
        "mean": float(arr.mean()),
        "lo": float(np.quantile(b, 0.025)),
        "hi": float(np.quantile(b, 0.975)),
        "interval": "hierarchical_bootstrap_seed_95",
        "n_boot": n_boot,
    }


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


def cl_evaluation_metrics(
    *,
    matrix: dict[str, dict[str, float]],
    task_order: list[str] | tuple[str, ...],
    untrained: dict[str, float],
    independent: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Continual-learning metrics from R[trained_through][eval_task].

    Distinguishes quantities that V0.6/V0.6.1 mixed together:

    - ``average_return``: (1/T) Σ_i R_{T,i}
    - ``forgetting``: R_{i,i} − R_{T,i} for i < T
    - ``backward_transfer``: R_{T,i} − R_{i,i} (negative BWT is forgetting)
    - ``zero_shot_forward_transfer``: R_{i−1,i} − untrained_i
      (untrained / random-init return on task i, **not** a fully trained specialist)
    - ``forward_adaptation``: R_{i,i} − independent_i after matched on-task steps
      (sample-efficiency / sequential vs specialist; only if ``independent`` given)
    """
    order = list(task_order)
    empty: dict[str, Any] = {
        "average_return": 0.0,
        "acc": 0.0,
        "forgetting": {},
        "mean_forgetting": 0.0,
        "backward_transfer": {},
        "mean_backward_transfer": 0.0,
        "zero_shot_forward_transfer": {},
        "mean_zero_shot_forward_transfer": 0.0,
        "forward_adaptation": {},
        "mean_forward_adaptation": 0.0,
        "task_order": order,
    }
    if not order:
        return empty
    last = order[-1]

    def _mean(xs: list[float | None]) -> float:
        vals = [float(v) for v in xs if v is not None]
        return float(np.mean(vals)) if vals else 0.0

    acc_vals = [float(matrix[last][t]) for t in order if last in matrix and t in matrix[last]]
    forgetting: dict[str, float | None] = {}
    bwd: dict[str, float | None] = {}
    for t in order[:-1]:
        r_ii = matrix.get(t, {}).get(t)
        r_ti = matrix.get(last, {}).get(t)
        if r_ii is None or r_ti is None:
            forgetting[t] = None
            bwd[t] = None
        else:
            forgetting[t] = float(r_ii) - float(r_ti)
            bwd[t] = float(r_ti) - float(r_ii)
    zs: dict[str, float | None] = {}
    for i, t in enumerate(order):
        if i == 0:
            continue
        prev = order[i - 1]
        r_prev = matrix.get(prev, {}).get(t)
        base = untrained.get(t)
        if r_prev is None or base is None:
            zs[t] = None
        else:
            zs[t] = float(r_prev) - float(base)
    adapt: dict[str, float | None] = {}
    if independent:
        for t in order:
            r_ii = matrix.get(t, {}).get(t)
            spec = independent.get(t)
            if r_ii is None or spec is None:
                adapt[t] = None
            else:
                adapt[t] = float(r_ii) - float(spec)
    return {
        "average_return": float(np.mean(acc_vals)) if acc_vals else 0.0,
        "acc": float(np.mean(acc_vals)) if acc_vals else 0.0,
        "forgetting": forgetting,
        "mean_forgetting": _mean(list(forgetting.values())),
        "backward_transfer": bwd,
        "mean_backward_transfer": _mean(list(bwd.values())),
        "zero_shot_forward_transfer": zs,
        "mean_zero_shot_forward_transfer": _mean(list(zs.values())),
        "forward_adaptation": adapt,
        "mean_forward_adaptation": _mean(list(adapt.values())),
        "task_order": order,
        "untrained": dict(untrained),
        "independent": dict(independent or {}),
    }


def continual_metrics(
    *,
    matrix: dict[str, dict[str, float]],
    task_order: list[str] | tuple[str, ...],
    scratch: dict[str, float],
) -> dict[str, Any]:
    """Legacy V0.6.1 helper. FWT here uses ``scratch`` specialists — prefer ``cl_evaluation_metrics``."""
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
