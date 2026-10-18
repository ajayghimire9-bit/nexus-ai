"""E2.19 policy-state diagnostic. No collection. E2.17 label stays inconclusive."""
from __future__ import annotations

import json

import pytest

from nexus.evolution2 import persist_reset_executor as exe
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_policy_state as state
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_science as science
from nexus.evolution2.methods import PersistentAdaptive, ResetAdaptive


def test_historical_label_and_consumed_grant_stay_closed():
    payload = state.diagnose()
    assert payload["historical_label_preserved"] == "inconclusive"
    assert json.loads(science.RESULTS.read_text())["primary_label"] == "inconclusive"
    assert grant.grant_unused() is False
    assert grant.grant_record()["consumed"] is True
    with pytest.raises(Exception, match="unnamed|holdout|already_consumed"):
        grant.require_unused_grant(17280, grant.HUMAN_APPROVAL)
    with pytest.raises(Exception, match="unnamed|holdout"):
        exe.execute_scientific(17280)
    with pytest.raises(Exception, match="unnamed|holdout"):
        lock.dispatch(17280)
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG
    assert payload["collection"] is False
    assert payload["env_steps"] == 0


def test_reset_clears_only_learned_weights_and_keeps_crn():
    persist, reset = state.paired_adaptive(7)
    assert persist.inner._tie_rank == reset.inner._tie_rank
    assert persist.inner._rng.getstate() == reset.inner._rng.getstate()
    persist.inner._weights = (0.2, 0.1, 0.0, 0.3, 0.0, 0.05)
    persist.inner._updates = 4
    reset.inner._weights = (0.2, 0.1, 0.0, 0.3, 0.0, 0.05)
    reset.inner._updates = 4
    report = state.apply_reset_intervention(reset)
    assert report["weights_after"] == [0.0] * 6
    assert reset.learned_state()["updates"] == 0
    assert persist.inner._weights == (0.2, 0.1, 0.0, 0.3, 0.0, 0.05)
    assert persist.inner._tie_rank == reset.inner._tie_rank
    other = PersistentAdaptive(seed=8)
    assert other.inner._tie_rank != persist.inner._tie_rank


def test_historical_counterfactual_and_synthetic_mechanism():
    payload = state.write_artifact()
    historical = payload["historical_counterfactual"]
    assert historical["historical_label_preserved"] == "inconclusive"
    assert historical["pre_current_choice_differs_any"] is True
    assert historical["protocol_training_differs_any"] is False
    assert historical["hidden_differs_any"] is True
    assert historical["bundles"][1]["hidden_differs"] is True
    assert all(row["first_family_weights_equal"] for row in historical["bundles"])
    assert all(row["ties_identical"] for row in historical["bundles"])
    assert payload["outcomes"]["weights_change_and_planner_selections_change"] is True
    assert payload["outcomes"]["weights_change_but_rankings_selections_identical"] is True
    assert payload["outcomes"]["weights_do_not_meaningfully_change"] is False
    assert payload["outcomes"]["earlier_task_state_not_accessible_to_target_selection"] is False
    synthetic = payload["synthetic_mechanism_tests"]
    assert synthetic["transfer_evidence"] is False
    assert synthetic["successor_then_flat"]["training_differs"] is True
    assert synthetic["control_training_identical"] is True
    assert synthetic["policy_can_translate_memory_into_choice"] is True
    assert synthetic["prior_only"]["pre_current_differs"] is True
    sensitivity = payload["evaluator_sensitivity"]
    assert sensitivity["selections_differ"] is True
    assert sensitivity["scores_follow_selected_planner"] is True
    assert sensitivity["hidden_blocked_from_training"] is True
    assert sensitivity["logical_equal"] == {"persist": 4, "reset": 4, "random": 4, "evolution": 4}
    assert sensitivity["physical"] + sensitivity["cached"] == sensitivity["logical"]
    decision = payload["decision"]
    assert decision["verdict"] == "GO"
    assert decision["fresh_budget_upper"] == 24480
    assert decision["reuse_e217_grant"] is False
    assert decision["reuse_e217_holdout_as_confirmation"] is False
    assert "24480" in decision["next_action"]
    assert payload["code_mechanism"]["not_replaced"].startswith("AdaptiveProposer")


def test_reset_adaptive_contract_still_preserves_ties():
    method = ResetAdaptive(seed=11)
    ties = dict(method.inner._tie_rank)
    method.inner._weights = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    method.reset_task()
    assert method.inner._tie_rank == ties
    assert method.learned_state()["weights"] == (0.0,) * 6
