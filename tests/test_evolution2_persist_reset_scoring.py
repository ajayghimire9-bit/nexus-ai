"""E2.21 executable scoring. No collection. Isolation is provenance, not fingerprint."""
from __future__ import annotations

import json

import pytest

from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_method_sensitive as nxt
from nexus.evolution2 import persist_reset_request as lock
from nexus.evolution2 import persist_reset_science as science
from nexus.evolution2 import persist_reset_scoring as scoring


def test_hidden_isolation_allows_fingerprint_overlap_not_hidden_returns():
    variants = science.locked_split()["revealed"]
    high = variants[0]

    def produce(variant, seed_key):
        return -12.0 if variant is high else -3.0

    scale = science.FrozenRevealedScale({high: -8.0, variants[1]: -2.0})
    evaluator = science.MethodSensitiveHiddenEval(produce, scale=scale)
    unit = evaluator.evaluate("persist", high, seed_key=science.matched_hidden_seed(0, "pendulum", 0))
    assert unit == scale.unit(-12.0)
    evaluator.training_must_not_see(
        [{"fingerprint": high.fingerprint, "score": 0.4, "provenance": "revealed"}]
    )
    with pytest.raises(RuntimeError, match="hidden_development_leaked_into_training"):
        evaluator.training_must_not_see(
            [
                {
                    "fingerprint": high.fingerprint,
                    "score": unit,
                    "provenance": science.HIDDEN_PROVENANCE,
                    "outcome_id": evaluator._hidden_outcomes[0]["outcome_id"],
                }
            ]
        )


def test_executable_path_and_screen_comparison():
    payload = scoring.write_artifact()
    path = payload["path"]
    assert path["controller_is_method_selected_planner"] is True
    assert path["scale_frozen_before_hidden"] is True
    assert path["forced_swap_scores_differ"] is True
    assert path["identical_selection_scores_equal"] is True
    assert path["identical_cached"] >= 1
    assert path["logical_equal"] == [4, 4, 4, 4]
    assert path["fingerprint_overlap_allowed"] is True
    assert path["hidden_return_blocked_from_training"] is True
    assert path["matched_initial_rng"] is True
    assert path["only_intended_difference"] == "retained_cross_task_weights"
    screens = payload["screens"]
    assert screens["n3"]["fresh_total_upper"] == 24480
    assert screens["n10"]["fresh_total_upper"] == 81600
    assert screens["n10"]["fits"] == 20
    assert screens["n10"]["twenty_fit_unmeasured"] is True
    assert screens["does_not_rewrite_locked_protocols"] is True
    assert payload["decision"]["reuse_e217_grant"] is False
    assert payload["collection"] is False
    assert json.loads(science.RESULTS.read_text())["primary_label"] == "inconclusive"
    with pytest.raises(Exception, match="unnamed|holdout|unauthorized|consumed"):
        nxt.execute_scientific(24480, "continue")
    assert lock.file_sha256(lock.CONFIG) == lock.LOCKED_CONFIG
    assert grant.grant_unused() is False


def test_persist_reset_crn_and_separate_controls():
    matched = scoring.persist_reset_matched(11)
    assert matched["matched_tie_order"] is True
    assert matched["random_and_evolution_separate_controls"] is True
    seeds = nxt.persist_reset_crn(2)
    assert seeds["matched"] is True
    methods = {short: __import__("nexus.evolution2.methods", fromlist=["make_methods"]).make_methods(11)[inner] for short, inner in science.METHOD_KEYS.items()}
    assert methods["random"].name == "random"
    assert methods["evolution"].name == "evolutionary"
    assert methods["persist"].name == "persistent_adaptive"
    assert methods["reset"].name == "reset_adaptive"
