from __future__ import annotations

import json
import math

from nexus.cl.metrics import hierarchical_bootstrap_ci, seed_level_ci
from nexus.cl.serialize import dumps_strict, json_sanitize


def test_empty_ci_is_strict_json_null() -> None:
    blob = dumps_strict({"ci": seed_level_ci([]), "boot": hierarchical_bootstrap_ci([])})
    json.loads(blob)
    json.dumps(json.loads(blob), allow_nan=False)
    payload = json.loads(blob)
    assert payload["ci"]["n"] == 0
    assert payload["ci"]["mean"] is None
    assert payload["ci"]["lo"] is None
    assert payload["boot"]["mean"] is None


def test_sanitize_rejects_nan_inf() -> None:
    out = json_sanitize({"a": float("nan"), "b": float("inf"), "c": -float("inf"), "d": 1.5})
    assert out == {"a": None, "b": None, "c": None, "d": 1.5}
    json.dumps(out, allow_nan=False)
    assert math.isnan(float("nan"))
