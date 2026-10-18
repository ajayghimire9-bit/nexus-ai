"""Development tests for residual decide() strategy-memory bench. No collection."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.core.strategy_memory_residual_bench import DISPOSABLE, SCIENCE_FITS, write_artifact
from nexus.evolution2 import persist_reset_grant as grant


def test_residual_bench_uses_disposable_fits_not_e217():
    payload = write_artifact(7)
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["env_steps"] == 0
    assert payload["decision"]["used_e217_science_arrays"] is False
    assert payload["decision"]["used_e217_science_fits"] is False
    assert payload["decision"]["source"] == "evolution2_fit_clock_disposable"
    assert payload["score_source"] == "decide_disposable_residual"
    assert grant.grant_unused() is False
    assert len(set(payload["lookups"].values())) == 1
    assert DISPOSABLE.is_dir()
    assert not any(Path(payload["decision"]["source"]).parts) or "science" not in payload["decision"]["source"]
    if SCIENCE_FITS.is_dir():
        assert "persist_reset_science" not in payload["decision"]["source"]
    assert json.loads(open("artifacts/evolution2_persist_reset_science.json").read())["primary_label"] == "inconclusive"
