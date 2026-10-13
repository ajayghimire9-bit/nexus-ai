"""Reject incomplete or non-finite experiment cells instead of dropping them."""

from __future__ import annotations

from typing import Any

import numpy as np


def finite_number(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def missing_or_nonfinite(tree: Any, prefix: str = "") -> list[str]:
    """Paths whose required numeric leaves are missing or not finite.

    Dicts and lists are walked. Strings and bools are ignored. None is a failure.
    """
    bad: list[str] = []
    if tree is None:
        return [prefix or "<root>"]
    if isinstance(tree, dict):
        if not tree and prefix:
            bad.append(prefix)
        for key, value in tree.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            bad.extend(missing_or_nonfinite(value, child))
        return bad
    if isinstance(tree, (list, tuple)):
        if not tree and prefix:
            bad.append(prefix)
        for i, value in enumerate(tree):
            bad.extend(missing_or_nonfinite(value, f"{prefix}[{i}]"))
        return bad
    if isinstance(tree, (bool, str)):
        return bad
    if isinstance(tree, (int, float, np.integer, np.floating)):
        if not finite_number(tree):
            bad.append(prefix or "<root>")
        return bad
    return bad


def completeness_report(required: Any, *, optional_note: str = "") -> dict[str, Any]:
    failures = missing_or_nonfinite(required)
    return {
        "declared_complete": not failures,
        "failures": failures,
        "optional_fields_note": optional_note,
    }


def _numeric_failure(value: Any) -> str | None:
    """Why `value` cannot be a required metric. None means it is a finite number.

    Booleans are rejected even though `bool` is a subclass of `int`. Strings are
    rejected even when `float()` would parse them. `completeness_report` skips
    both, so it cannot see those substitutions.
    """
    if isinstance(value, (bool, np.bool_)):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "missing"
    if isinstance(value, (list, tuple, dict)):
        return "container"
    if isinstance(value, (int, float, np.integer, np.floating)):
        if not np.isfinite(float(value)):
            return "nonfinite"
        return None
    return "not_numeric"


def schema_completeness(
    records: list[dict[str, Any]],
    *,
    seed_ids: list[int],
    task_ids: list[str],
    labels: list[str],
    conditions_by_label: dict[str, list[str]],
    metrics: tuple[str, ...] = ("mae", "rmse", "angvel_mae"),
    horizons: tuple[str, ...] = ("3", "8", "16"),
    per_dim: int = 3,
) -> dict[str, Any]:
    """Require every planned per-task cell, then check that its metrics are finite.

    `completeness_report` only walks values that are already in the tree. A missing
    seed, task, condition, horizon, or checkpoint never becomes a failure. Strings
    and booleans are ignored, so a numeric string or `True` in a metric field does
    not fail. This check runs on raw per-task cells before they are averaged.
    Historical artifacts were not rewritten.
    """
    failures: list[str] = []
    if len(seed_ids) != len(set(seed_ids)):
        failures.append("duplicate seed ids in the planned set")
    if len(task_ids) != len(set(task_ids)):
        failures.append("duplicate task ids in the planned set")
    if len(labels) != len(set(labels)):
        failures.append("duplicate labels in the planned set")
    if set(conditions_by_label) != set(labels):
        failures.append("conditions do not match the planned labels")
    for label, conditions in conditions_by_label.items():
        if len(conditions) != len(set(conditions)):
            failures.append(f"duplicate conditions for {label}")
    expected_seeds = set(seed_ids)
    expected_tasks = set(task_ids)
    expected_labels = set(labels)
    horizon_set = set(horizons)
    seen: dict[tuple[Any, Any, Any, Any], int] = {}
    if not isinstance(records, list):
        return {"declared_complete": False, "failures": ["records are not a list"], "n_expected": 0, "n_records": 0}
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            failures.append(f"records[{i}] is not an object")
            continue
        seed = record.get("seed")
        task = record.get("task")
        label = record.get("label")
        condition = record.get("condition")
        where = f"records[{i}] seed={seed!r} task={task!r} label={label!r} condition={condition!r}"
        if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
            failures.append(f"{where} seed is not an integer id")
        elif int(seed) not in expected_seeds:
            failures.append(f"{where} unexpected seed")
        if not isinstance(task, str) or task not in expected_tasks:
            failures.append(f"{where} unexpected task")
        if not isinstance(label, str) or label not in expected_labels:
            failures.append(f"{where} unexpected label")
        else:
            allowed = conditions_by_label.get(label, [])
            if not isinstance(condition, str) or condition not in allowed:
                failures.append(f"{where} unexpected condition")
        key = (int(seed) if isinstance(seed, (int, np.integer)) and not isinstance(seed, bool) else seed, task, label, condition)
        seen[key] = seen.get(key, 0) + 1
        for metric in metrics:
            reason = _numeric_failure(record.get(metric))
            if reason is not None:
                failures.append(f"{where} {metric} {reason}")
        dims = record.get("mae_per_dim")
        if not isinstance(dims, (list, tuple)) or isinstance(dims, str):
            failures.append(f"{where} mae_per_dim missing")
        elif len(dims) != int(per_dim):
            failures.append(f"{where} mae_per_dim length {len(dims)} != {per_dim}")
        else:
            for j, item in enumerate(dims):
                reason = _numeric_failure(item)
                if reason is not None:
                    failures.append(f"{where} mae_per_dim[{j}] {reason}")
        roll = record.get("rollout_mae")
        if not isinstance(roll, dict):
            failures.append(f"{where} rollout_mae missing")
        else:
            if set(roll) != horizon_set:
                failures.append(f"{where} rollout horizons {sorted(str(k) for k in roll)} != {sorted(horizons)}")
            for horizon in horizons:
                reason = _numeric_failure(roll.get(horizon))
                if reason is not None:
                    failures.append(f"{where} rollout_mae.{horizon} {reason}")
    for key, count in seen.items():
        if count > 1:
            failures.append(f"duplicate cell seed={key[0]} task={key[1]} label={key[2]} condition={key[3]}")
    n_expected = 0
    for label in labels:
        n_expected += len(seed_ids) * len(task_ids) * len(conditions_by_label.get(label, []))
    for seed in seed_ids:
        for task in task_ids:
            for label in labels:
                for condition in conditions_by_label.get(label, []):
                    if seen.get((int(seed), task, label, condition), 0) == 0:
                        failures.append(f"missing cell seed={seed} task={task} label={label} condition={condition}")
    # Stable unique failures, preserving order.
    unique: list[str] = []
    for item in failures:
        if item not in unique:
            unique.append(item)
    return {
        "declared_complete": not unique,
        "failures": unique,
        "n_expected": n_expected,
        "n_records": len(records) if isinstance(records, list) else 0,
    }
