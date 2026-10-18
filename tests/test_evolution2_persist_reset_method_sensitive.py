"""E2.20 method-sensitive next-screen lock. No collection. E2.17 stays inconclusive."""
from __future__ import annotations

import json

import pytest

from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_method_sensitive as nxt
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_science as science


def test_consumed_caps_and_continue_stay_refused():
    with pytest.raises(RuntimeError, match="occupied_default_persist_not_fresh_physics"):
        nxt.execute_scientific(7680, "continue")
    with pytest.raises(RuntimeError, match="consumed_e217_env_cap_17280"):
        nxt.execute_scientific(17280, grant.HUMAN_APPROVAL)
    with pytest.raises(Exception, match="unnamed|holdout|unauthorized|insufficient|continue"):
        nxt.execute_scientific(24480, "continue please")
    with pytest.raises(RuntimeError, match="e217_development_is_not_confirmation"):
        nxt.execute_scientific(24480, grant.HUMAN_APPROVAL.replace("17280", "24480"))
    with pytest.raises(Exception, match="unnamed|holdout"):
        nxt.dispatch(24480)
    with pytest.raises(Exception, match="unnamed|holdout|already_consumed"):
        grant.require_unused_grant(17280, grant.HUMAN_APPROVAL)
    assert grant.grant_unused() is False
    assert json.loads(science.RESULTS.read_text())["primary_label"] == "inconclusive"
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG
    assert lock.allocation_record()["authorized"] is False


def test_method_sensitive_scoring_follows_selected_planner():
    nxt.persist_reset_crn(1)

    def produce(variant, seed_key):
        slot = int(seed_key[-1])
        base = 1.0 if variant.rule.value == "flat" else 5.0
        return base * (1 + slot)

    report = nxt.score_saved_bundle(1, produce)
    assert report["historical_label_preserved"] == "inconclusive"
    assert report["hidden_loop"] == "corrected_hidden_scores"
    assert report["persist_reset_scores_differ"] is True
    logical = [report["charges"]["per_method"][name]["logical"] for name in science.METHODS]
    assert logical == [4, 4, 4, 4]
    assert report["charges"]["physical"] + report["charges"]["cached"] == 16
    persist = [item["fingerprint"] for item in report["selections"]["persist"]]
    reset = [item["fingerprint"] for item in report["selections"]["reset"]]
    assert persist != reset


def test_lock_status_does_not_collect_or_name_a_holdout():
    payload = nxt.write_artifact()
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["env_steps"] == 0
    assert payload["fresh_total_upper"] == 24480
    assert payload["fresh_total_if_identical_selections"] == 17280
    assert payload["grant_consumed"] is True
    assert payload["unused_24480_grant"] is False
    assert payload["hold_named"] is False
    assert payload["historical_run_bundle_forbidden"] is True
    assert payload["next_hidden_loop"] == "corrected_hidden_scores"
    assert payload["continue_is_not_approval"] is True
    assert payload["e217_roles_not_confirmation"] is True
    assert "Do not reuse" in science.run_bundle.__doc__
