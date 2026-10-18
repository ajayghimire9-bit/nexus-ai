"""E2.17 methodological diagnosis. No collection. Historical label stays inconclusive."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexus.evolution2 import persist_reset_diagnosis as diag
from nexus.evolution2 import persist_reset_executor as exe
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_science as science


def test_historical_label_stays_inconclusive_and_grant_stays_consumed():
    historical = diag.load_historical()
    assert historical["primary_label"] == "inconclusive"
    assert historical["analysis"]["label"] == "inconclusive"
    assert historical["analysis"]["contrasts"]["persist_minus_reset"]["mean"] == 0.0
    assert grant.grant_unused() is False
    assert grant.grant_record()["consumed"] is True
    with pytest.raises(Exception, match="unnamed|holdout|already_consumed"):
        grant.require_unused_grant(17280, grant.HUMAN_APPROVAL)
    with pytest.raises(Exception, match="unnamed|holdout"):
        exe.execute_scientific(17280)
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.dispatch(17280)
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG


def test_diagnosis_recovers_choices_and_causal_sensitivity():
    payload = diag.write_artifact()
    assert payload["historical_label_preserved"] == "inconclusive"
    assert "same locked hidden" in payload["root_cause"]
    choices = payload["proposer_choices"]
    assert len(choices["bundles"]) == 3
    first = choices["bundles"][0]["families"]["pendulum"]
    assert len(first["persist"]) == 4
    assert len(first["reset"]) == 4
    assert choices["persist_reset_differed_in_any_bundle"] is False
    assert choices["evolution_differed_from_persist"] is True
    sensitivity = payload["causal_sensitivity"]
    assert sensitivity["different_selections_differ"] is True
    assert sensitivity["scores_follow_swapped_selections"] is True
    assert sensitivity["identical_selection_and_seed_match"] is True
    assert sensitivity["hidden_blocked_from_training"] is True
    assert sensitivity["before_historical_hidden_was_method_independent"] is True
    budget = payload["corrected_design"]["budget"]
    assert budget["fresh_source"] == 7680
    assert budget["revealed"] == 7200
    assert budget["hidden_logical_evaluations"] == 48
    assert budget["hidden_physical_steps_upper"] == 9600
    assert budget["fresh_total_upper"] == 24480
    assert budget["cannot_reuse_e217_development_as_confirmation"] is True
    assert payload["collection"] is False
    assert json.loads(science.RESULTS.read_text())["primary_label"] == "inconclusive"


def test_corrected_hidden_eval_equal_logical_budget_and_cache():
    replayed = science.replay_training(
        0,
        {"pendulum": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6], "acrobot": [0.6, 0.5, 0.4, 0.3, 0.2, 0.1]},
        shared_persist_seed=True,
    )
    known = {variant: float(i) for i, variant in enumerate(science.locked_split()["revealed"])}

    def produce(variant, seed_key):
        return known[variant]

    report = science.corrected_hidden_scores(replayed["methods"], 0, produce)
    logical = [report["charges"]["per_method"][name]["logical"] for name in science.METHODS]
    assert logical == [4, 4, 4, 4]
    assert report["charges"]["logical"] == 16
    assert report["charges"]["physical"] + report["charges"]["cached"] == 16
    assert report["charges"]["physical"] >= 1
