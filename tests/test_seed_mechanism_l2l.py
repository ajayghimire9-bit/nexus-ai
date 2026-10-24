"""Offline mechanism competence tests. No language-model inference."""
from __future__ import annotations

import random
from copy import deepcopy
from pathlib import Path
import tempfile

from nexus.seed.mechanism_investigate import (
    FEATURE_NAMES, HIDDEN, REDUNDANT_MASK_ORIGIN, available_actions, choose_information_gain,
    feature_vector, features, filter_language, is_redundant, public_view, run_episode,
)
from nexus.seed.mechanism_l2l import competence_gate, headroom_gate, run_study, summarize, verify_payload
from nexus.seed.mechanism_policy import (
    fit_source, policy_hash, reset_weights, select_action, shuffle_weights,
    training_rows, zero_weights,
)
from nexus.seed.mechanism_tasks import catalogue, tasks_for
from nexus.seed.mechanism_world import ACTIONS, LANGUAGE, apply_hidden, blank_state


def test_hidden_answers_come_from_execution():
    add1 = apply_hidden("add1", blank_state(3), "ACT_0")
    mul2 = apply_hidden("mul2", blank_state(3), "ACT_0")
    assert add1["observation"] == 1
    assert mul2["observation"] == 0


def test_public_view_hides_identity():
    view = public_view(tasks_for("source")[0])
    assert "mechanism" not in view
    assert "family" not in view
    assert "task_id" not in view
    assert view["redundant_mask"] == REDUNDANT_MASK_ORIGIN


def test_features_exclude_hidden_labels():
    feats = features([], list(LANGUAGE), 0, 8)["features"]
    assert set(feats) == set(FEATURE_NAMES)
    assert not (set(feats) & HIDDEN)


def test_features_distinguish_informative_from_known_query():
    start = features([], list(LANGUAGE), 0, 8)["features"]
    known_t = [
        dict(action="ACT_1", observation=2),
        dict(action="ACT_1", observation=2),
    ]
    remain = filter_language(known_t)
    assert "add1" in remain and "mul2" in remain
    known = features(known_t, remain, 0, 6)["features"]
    assert start["used_ACT_1"] == 0.0
    assert start["informative_ACT_1"] == 1.0
    assert known["used_ACT_1"] == 1.0
    assert known["informative_ACT_1"] == 0.0
    assert feature_vector(start) != feature_vector(known)


def test_redundant_mask_is_shared_and_allows_stateful_repeat():
    first = [
        dict(action="ACT_1", observation=2),
        dict(action="ACT_1", observation=2),
    ]
    remain = filter_language(first)
    assert "add1" in remain and "mul2" in remain
    stateless_repeat = is_redundant("ACT_1", first, remain)
    assert stateless_repeat["redundant"] is True
    toggle = [dict(action="ACT_0", observation=1)]
    after_toggle = filter_language(toggle)
    assert "toggle" in after_toggle
    stateful = is_redundant("ACT_0", toggle, after_toggle)
    assert stateful["redundant"] is False
    avail = available_actions({}, first, remain)
    assert avail["mask"] == REDUNDANT_MASK_ORIGIN
    assert "ACT_1" not in avail["actions"]
    assert "STOP_UNRESOLVED" in avail["actions"]
    assert "STOP_IDENTIFY" not in avail["actions"]


def test_version_space_singleton_is_not_a_shortlist():
    transcript = [
        dict(action="ACT_0", observation=1),
        dict(action="ACT_0", observation=1),
    ]
    assert filter_language(transcript) == ["add1"]


def test_excluded_family_can_empty_the_language():
    transcript = [
        dict(action="ACT_0", observation=0),
        dict(action="ACT_1", observation=0),
    ]
    assert filter_language(transcript) == []


def test_information_gain_query_choice_differs_from_diagnostic_first_act():
    rng = random.Random(0)
    choice = choose_information_gain(list(LANGUAGE), [], list(ACTIONS), rng)
    assert choice["action"] != "STOP_IDENTIFY"
    assert choice["score_work"] > 0


def test_ties_are_randomized_not_alphabetical():
    weights = zero_weights()
    feats = features([], list(LANGUAGE), 0, 8)["features"]
    picks = {select_action(weights, feats, ["MEASURE", "ACT_0", "RESET"],
                           random.Random(seed))["selected"] for seed in range(40)}
    assert len(picks) > 1


def test_source_fit_updates_and_reset_clears():
    feats = features([], list(LANGUAGE), 0, 8)["features"]
    rows = [dict(action="ACT_0", features=feats, label=1.0, first_query=True)]
    weights = fit_source(rows)
    assert policy_hash(weights) != policy_hash(zero_weights())
    assert reset_weights(weights) == zero_weights()
    assert policy_hash(shuffle_weights(weights, 4)) != policy_hash(weights)


def test_gold_episode_identify_or_unresolved():
    add1 = next(row for row in catalogue() if row["mechanism"] == "add1")
    ident = next(row for row in catalogue() if row["mechanism"] == "const7")

    def ig(ctx):
        return choose_information_gain(ctx["remaining"], ctx["transcript"], ctx["available"], ctx["rng"])

    found = run_episode(add1, ig, random.Random(1))
    assert found["success"] is True
    assert found["identified"] == "add1"
    missed = run_episode(ident, ig, random.Random(2))
    assert missed["correct_unresolved"] is True
    assert missed["correct_id"] is False


def test_training_rows_include_stops_and_off_actions():
    add1 = next(row for row in catalogue() if row["mechanism"] == "add1")
    ident = next(row for row in catalogue() if row["mechanism"] == "const7")

    def ig(ctx):
        return choose_information_gain(ctx["remaining"], ctx["transcript"], ctx["available"], ctx["rng"])

    found = training_rows(run_episode(add1, ig, random.Random(3)))
    missed = training_rows(run_episode(ident, ig, random.Random(4)))
    assert {row["chosen"] for row in found} & {"STOP_IDENTIFY"}
    assert {row["chosen"] for row in missed} & {"STOP_UNRESOLVED"}
    assert any(row["label"] == 0.0 for row in found)
    assert any(row["label"] == 1.0 and row["action"] == "STOP_IDENTIFY" for row in found)


def test_headroom_gate_uses_environment_cost():
    tight = {
        name: dict(success=6, oracle=12, action_steps=12)
        for name in ("information_gain", "fixed_diagnostic", "source_frequency", "random")
    }
    assert headroom_gate(tight)["exists"] is False
    wide = dict(tight)
    wide["random"] = dict(success=6, oracle=40, action_steps=20)
    assert headroom_gate(wide)["exists"] is True


def test_competence_gate_requires_completion_and_no_repeats():
    good = [dict(success=True, correct_id=True, correct_unresolved=False,
                 gold_in_language=True, premature=False, stopped="STOP_IDENTIFY",
                 redundant_taken=0)]
    assert competence_gate(good)["passed"] is True
    bad = [dict(good[0], stopped="budget", success=False, correct_id=False)]
    assert competence_gate(bad)["passed"] is False


def test_catalogue_splits_are_mechanism_separated():
    source = {row["mechanism"] for row in tasks_for("source")}
    within = {row["mechanism"] for row in tasks_for("within_family")}
    excluded = {row["mechanism"] for row in tasks_for("excluded_family")}
    assert not (source & within)
    assert "const7" in source
    assert "add4" in within
    assert "delay" in excluded


def test_study_keeps_assessment_closed_on_training_failure():
    payload = run_study(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    if not payload["competence"]["passed"]:
        assert payload["assessment_closed"] is True
        assert payload["assessment"] == []
        assert payload["verdict"] == "training_failure"
    flipped = deepcopy(payload)
    if flipped["development"]:
        flipped["development"][0]["success"] = not flipped["development"][0]["success"]
        flipped["development"][0]["remaining"] = ["forged"]
        assert verify_payload(flipped)["valid"] is False
