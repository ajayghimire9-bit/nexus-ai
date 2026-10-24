"""Acquire/synthesis tests. No language-model inference. Do not rescore opened cells."""
from __future__ import annotations

import random
from pathlib import Path
import tempfile

from nexus.seed.mechanism_acquire import (
    OPENED_IDS, run_acquire, run_acquire_study, score_columns, verify_payload,
    zero_acquire,
)
from nexus.seed.mechanism_claims import score_claims
from nexus.seed.mechanism_compose import (
    PRIMITIVES, class_for_hidden, compositions, filter_compositions, synthesize,
)
from nexus.seed.mechanism_investigate import filter_language
from nexus.seed.mechanism_tasks import (
    synthesis_gate_tasks, synthesis_holdout_tasks, synthesis_source_tasks,
)
from nexus.seed.mechanism_world import LANGUAGE, apply_hidden, blank_state


def test_three_claims_split_on_add1_twin():
    remaining = ["add1"]
    holdout = [
        dict(action="ACT_0", predicted=1, observed=1),
        dict(action="ACT_1", predicted=2, observed=2),
    ]
    claims = score_claims(
        dict(mechanism="add1_twin"), remaining,
        dict(remaining=["add1"], representative="add1"),
        "add1", "STOP_IDENTIFY", holdout,
    )
    assert claims["catalogue_identification"] is True
    assert claims["predictive_competence"] is True
    assert claims["exact_mechanism_identification"] is False
    assert claims["guessed_generator"] is False
    assert claims["useful_acquisition"] is True
    assert "exact identity unresolved" in claims["scoped_report"]


def test_guessing_hidden_generator_is_not_success():
    claims = score_claims(
        dict(mechanism="add1_twin"), ["add1"],
        dict(remaining=["add1_twin"], representative="add1_twin"),
        "add1_twin", "STOP_IDENTIFY",
        [dict(action="ACT_0", predicted=1, observed=1)],
    )
    assert claims["guessed_generator"] is True
    assert claims["useful_acquisition"] is False
    assert claims["exact_mechanism_identification"] is False


def test_unstored_compositions_are_outside_language():
    for task in synthesis_gate_tasks() + synthesis_holdout_tasks():
        assert task["mechanism"] not in LANGUAGE
        assert task["task_id"] not in OPENED_IDS


def test_mul2_then_add1_empties_catalogue_and_is_synthesizable():
    path = [
        dict(action="ACT_0", observation=1),
        dict(action="ACT_1", observation=3),
        dict(action="ACT_2", observation=5),
    ]
    assert filter_language(path) == []
    remain = filter_compositions(path)
    assert ("mul2", "add1") in remain
    assert class_for_hidden("mul2_then_add1") == ["mul2|add1"]


def test_fixed_synthesis_predicts_new_cases_without_naming_generator():
    task = next(row for row in synthesis_gate_tasks() if row["mechanism"] == "mul2_then_add1")
    episode = run_acquire(task, "fixed_synthesis", zero_acquire(), random.Random(1))
    assert episode["predictive_competence"] is True
    assert episode["useful_acquisition"] is True
    assert episode["exact_mechanism_identification"] is False
    assert episode["guessed_generator"] is False
    assert episode["identified"] is None
    assert apply_hidden("mul2_then_add1", blank_state(1), "ACT_2")["observation"] == 5


def test_catalogue_only_cannot_predict_unstored_composition():
    task = next(row for row in synthesis_gate_tasks() if row["mechanism"] == "mul2_then_add1")
    episode = run_acquire(task, "catalogue_only", zero_acquire(), random.Random(1))
    assert episode["predictive_competence"] is False
    assert episode["useful_acquisition"] is False
    assert episode["guessed_generator"] is False


def test_same_primitives_for_every_method():
    assert set(PRIMITIVES) <= set(LANGUAGE)
    assert len(compositions()) == 4 + 16


def test_source_primitives_are_in_language_and_fresh():
    ids = {row["task_id"] for row in synthesis_source_tasks()}
    assert ids.isdisjoint(OPENED_IDS)
    assert {row["mechanism"] for row in synthesis_source_tasks()} == set(PRIMITIVES)


def test_acquire_study_does_not_rescore_opened_cells():
    payload = run_acquire_study(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    seen = {row["task_id"] for row in (payload.get("assessment") or []) + (payload.get("gate_episodes") or [])}
    assert seen.isdisjoint(OPENED_IDS)
    assert payload["synthesis_gate"]["n"] == 3
    if payload["assessment"]:
        cols = score_columns(payload["assessment"])
        assert set(cols["fixed_synthesis"]) >= {
            "useful_acquisition", "predictive_competence", "interactions", "oracle",
        }
        assert "trained" in cols
