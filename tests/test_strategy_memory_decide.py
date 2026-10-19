"""Development tests for decide()-owned strategy-memory scoring. No collection."""
from __future__ import annotations

import json

from nexus.core.strategy_memory_decide_bench import FREE_SLOTS, PROPOSALS, write_artifact
from nexus.evolution2 import persist_reset_grant as grant


def test_decide_benchmark_is_development_only_with_four_free_slots(tmp_path,monkeypatch):
    monkeypatch.setattr(f'{write_artifact.__module__}.RESULTS',tmp_path/'fixture.json')
    payload = write_artifact(7)
    assert FREE_SLOTS == 4
    assert payload["free_slots"] == 4
    assert payload["matched_proposals"] == PROPOSALS == 6
    assert payload["score_source"] == "decide_fake_step_model"
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["env_steps"] == 0
    assert payload["used_e217_science_arrays"] is False
    assert payload["claims_agi"] is False
    assert grant.grant_unused() is False
    assert len(set(payload["lookups"].values())) == 1
    assert payload["lookups"]["contextual_strategy_memory"] == 48
    assert payload["causal_memory_changes_choice"]["same_seed"] is True
    assert "acro_zero_collision" in payload["oracle_by_task"]
    assert json.loads(open("artifacts/evolution2_persist_reset_science.json").read())["primary_label"] == "inconclusive"
