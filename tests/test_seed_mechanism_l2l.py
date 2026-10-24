"""Offline mechanism investigation tests. No language-model inference."""
from __future__ import annotations

import random

from nexus.seed.mechanism_investigate import (
    FEATURE_NAMES, HIDDEN, choose_information_gain, features, filter_language,
    public_view, run_episode,
)
from nexus.seed.mechanism_l2l import headroom_gate, summarize, verify_payload
from nexus.seed.mechanism_policy import (
    fit_source, policy_hash, reset_weights, select_action, shuffle_weights,
    training_rows, zero_weights,
)
from nexus.seed.mechanism_tasks import catalogue, tasks_for
from nexus.seed.mechanism_world import LANGUAGE, apply_hidden, blank_state


def test_hidden_answers_come_from_execution():
    state = blank_state(3)
    add1 = apply_hidden("add1", state, "ACT_0")
    mul2 = apply_hidden("mul2", blank_state(3), "ACT_0")
    assert add1["observation"] == 1
    assert mul2["observation"] == 0


def test_public_view_hides_identity():
    task = tasks_for("source")[0]
    view = public_view(task)
    assert "mechanism" not in view
    assert "family" not in view
    assert "task_id" not in view
    assert "gold" not in view


def test_features_exclude_hidden_labels():
    feats = features([], list(LANGUAGE), 0, 8)
    assert set(feats) == set(FEATURE_NAMES)
    assert not (set(feats) & HIDDEN)


def test_version_space_singleton_is_not_a_shortlist():
    transcript = [
        dict(action="ACT_0", observation=1),
        dict(action="ACT_0", observation=1),
    ]
    remain = filter_language(transcript)
    assert remain == ["add1"]


def test_excluded_family_can_empty_the_language():
    transcript = [
        dict(action="ACT_0", observation=0),
        dict(action="ACT_1", observation=0),
    ]
    assert filter_language(transcript) == []


def test_information_gain_query_choice_differs_from_diagnostic_first_act():
    rng = random.Random(0)
    choice = choose_information_gain(list(LANGUAGE), [], list(
        ("ACT_0", "ACT_1", "ACT_2", "ACT_NEG", "RESET", "MEASURE",
         "STOP_IDENTIFY", "STOP_UNRESOLVED")
    ), rng)
    assert choice["action"] != "STOP_IDENTIFY"
    assert choice["score_work"] > 0


def test_ties_are_randomized_not_alphabetical():
    weights = zero_weights()
    feats = features([], list(LANGUAGE), 0, 8)
    picks = {select_action(weights, feats, ["MEASURE", "ACT_0", "RESET"],
                           random.Random(seed))["selected"] for seed in range(40)}
    assert len(picks) > 1


def test_source_fit_updates_and_reset_clears():
    feats = features([], list(LANGUAGE), 0, 8)
    rows = [dict(action="ACT_0", features=feats, label=1.0, first_query=True)]
    weights = fit_source(rows)
    assert policy_hash(weights) != policy_hash(zero_weights())
    assert reset_weights(weights) == zero_weights()
    assert policy_hash(shuffle_weights(weights, 4)) != policy_hash(weights)


def test_gold_episode_identify_or_unresolved():
    add1 = next(row for row in catalogue() if row["mechanism"] == "add1")
    delay = next(row for row in catalogue() if row["mechanism"] == "delay")

    def ig(ctx):
        return choose_information_gain(ctx["remaining"], ctx["transcript"], ctx["available"], ctx["rng"])

    found = run_episode(add1, ig, random.Random(1))
    assert found["success"] is True
    assert found["identified"] == "add1"
    missed = run_episode(delay, ig, random.Random(2))
    assert missed["correct_unresolved"] is True
    assert missed["correct_id"] is False


def test_training_rows_are_labeled_supervision():
    add1 = next(row for row in catalogue() if row["mechanism"] == "add1")

    def ig(ctx):
        return choose_information_gain(ctx["remaining"], ctx["transcript"], ctx["available"], ctx["rng"])

    rows = training_rows(run_episode(add1, ig, random.Random(3)))
    assert rows
    assert all(row["supervision"] == "information_gain" for row in rows)


def test_headroom_gate_requires_a_spread():
    tight = {
        name: dict(success=6, mean_work=10.0)
        for name in ("information_gain", "fixed_diagnostic", "source_frequency", "random")
    }
    assert headroom_gate(tight)["exists"] is False
    wide = dict(tight)
    wide["random"] = dict(success=6, mean_work=20.0)
    assert headroom_gate(wide)["exists"] is True


def test_catalogue_splits_are_mechanism_separated():
    source = {row["mechanism"] for row in tasks_for("source")}
    within = {row["mechanism"] for row in tasks_for("within_family")}
    excluded = {row["mechanism"] for row in tasks_for("excluded_family")}
    assert not (source & within)
    assert not (within & excluded)
    assert "add4" in within
    assert "count2" in within
    assert "delay" in excluded


def test_verifier_rejects_flipped_success():
    from nexus.seed.mechanism_l2l import run_study
    import tempfile
    from pathlib import Path
    from copy import deepcopy
    payload = run_study(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    flipped = deepcopy(payload)
    if flipped["development"]:
        flipped["development"][0]["success"] = not flipped["development"][0]["success"]
        flipped["development"][0]["remaining"] = ["forged"]
        assert verify_payload(flipped)["valid"] is False
