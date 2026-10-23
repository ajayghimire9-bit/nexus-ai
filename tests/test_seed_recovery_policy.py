"""Offline recovery-policy tests. No language-model inference."""
from __future__ import annotations

from pathlib import Path

from nexus.seed.recovery_actions import (
    available_actions, blank_evidence, execute_action, feature_vector,
    public_observation, run_cases,
)
from nexus.seed.recovery_evaluate import METHODS, initial_failure, run_episode, run_offline, summarize
from nexus.seed.recovery_policy import fit_source, policy_hash, reset_weights, shuffle_weights, zero_weights
from nexus.seed.recovery_tasks import public_task_view, tasks_for


def test_initial_authored_failures_fail_public():
    for task in tasks_for("source") + tasks_for("development"):
        public = initial_failure(task)
        assert public["status"] != "passed"
        assert task["origin"] == "authored_fixture"


def test_controller_view_hides_private_and_family():
    task = tasks_for("source")[0]
    view = public_task_view(task)
    assert "family" not in view
    assert "private" not in view
    assert "reference" not in view
    assert "task_id" not in view
    feats = public_observation(view, task["files"], run_cases(task["files"], task["public"]),
                               blank_evidence(task["files"], {}), 4)
    assert "family" not in feats and "task_id" not in feats
    assert len(feature_vector(feats)) == len(feats)


def test_teacher_unavailable_is_recorded(tmp_path):
    task = next(row for row in tasks_for("source") if not row["teacher_available"])
    result = execute_action("REQUEST_DISTINGUISHING_EXAMPLE", task, task["files"],
                            blank_evidence(task["files"], {}), tmp_path)
    assert result["available"] is False
    assert result["teacher_queries"] == 0
    assert result["reason"] == "teacher_unavailable"


def test_source_fit_uses_tried_actions_only():
    from nexus.seed.recovery_actions import FEATURE_NAMES
    feats = {name: 0.0 for name in FEATURE_NAMES}
    feats["mismatch_rate"] = 1.0
    rows = [dict(action="REVISE", features=feats, label=1.0, first_action=True)]
    weights = fit_source(rows)
    assert any(v != 0 for v in weights["REVISE"])
    assert all(v == 0 for v in weights["INSPECT_SCHEMA"])
    assert policy_hash(weights) != policy_hash(zero_weights())


def test_reset_and_shuffle_are_controls():
    from nexus.seed.recovery_actions import FEATURE_NAMES
    rows = [dict(action="INSPECT_SCHEMA",
                 features={name: float(i == 0) for i, name in enumerate(FEATURE_NAMES)},
                 label=1.0, first_action=True)]
    weights = fit_source(rows)
    assert reset_weights(weights) == zero_weights()
    shuffled = shuffle_weights(weights, 7)
    assert policy_hash(shuffled) != policy_hash(weights)


def test_immediate_revise_does_not_inspect(tmp_path):
    task = next(row for row in tasks_for("source") if row["task_id"] == "src_immediate_a")
    episode = run_episode(task, "immediate_revise", zero_weights(), [], tmp_path)
    assert episode["actions"][0] == "REVISE"
    assert episode["private_passed"] is True
    assert episode["model_calls"] == 0


def test_offline_grid_and_no_live_inference(tmp_path):
    payload = run_offline(tmp_path)
    assert payload["live_inference"] is False
    assert payload["cpu_ledger_debit_s"] == 0
    assert payload["assessment"] == []
    assert payload["live"]["status"] == "BLOCKED_BUDGET"
    assert len(payload["development"]) == 6 * len(METHODS)
    assert len(payload["retention"]) == 2 * len(METHODS)
    assert payload["authored_fixtures_are_not_model_competence"] is True
    assert payload["learning_to_learn_established"] is False
    summary = summarize(payload["development"])
    assert summary["immediate_revise"]["model_calls"] == 0
    assert payload["acceptance"]["reset_or_shuffle_not_sufficient"] is True
