"""Strict JSON for research artifacts. NaN/Inf become null."""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np


def json_sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_sanitize(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_sanitize(value.tolist())
    if isinstance(value, (np.floating, float)):
        x = float(value)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def dumps_strict(payload: Any, *, indent: int = 2) -> str:
    return json.dumps(json_sanitize(payload), indent=indent, allow_nan=False)
