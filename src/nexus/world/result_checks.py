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
