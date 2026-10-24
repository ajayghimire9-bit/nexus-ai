"""Varied-probe tests. No language-model inference. Do not rescore opened cells."""
from __future__ import annotations

import random
from pathlib import Path
import tempfile

from nexus.seed.mechanism_investigate import (
    choose_cost_aware_ig, choose_diagnostic, choose_diagnostic_measure,
    choose_information_gain, filter_language, run_episode,
)
from nexus.seed.mechanism_tasks import catalogue, varied_tasks
from nexus.seed.mechanism_varied import (
    OPENED_IDS, run_varied, score_columns, verify_payload,
)
from nexus.seed.mechanism_world import LANGUAGE, ORACLE_COST, apply_hidden, blank_state


def _diag(ctx):
    return choose_diagnostic(ctx["remaining"], ctx["transcript"], ctx["available"])


def _diag_m(ctx):
    return choose_diagnostic_measure(ctx["remaining"], ctx["transcript"], ctx["available"])


def test_id_exact0_is_identity_until_measure():
    state = blank_state(1)
    cheap = apply_hidden("id_exact0", state, "ACT_1")
    assert cheap["observation"] == 1
    assert cheap["oracle"] == 1
    measured = apply_hidden("id_exact0", cheap["state"], "MEASURE")
    assert measured["observation"] == 0
    assert measured["oracle"] == ORACLE_COST["MEASURE"] == 3


def test_measure_empties_id_exact0_after_noisy_leftover():
    leftover = [
        dict(action="ACT_1", observation=1),
        dict(action="ACT_0", observation=0),
        dict(action="ACT_2", observation=2),
    ]
    assert filter_language(leftover) == ["noisy_add1"]
    emptied = leftover + [dict(action="MEASURE", observation=0)]
    assert filter_language(emptied) == []


def test_diagnostic_false_ids_id_exact0_without_measure():
    episode = run_episode(
        next(row for row in catalogue() if row["task_id"] == "vp_id0"),
        _diag, random.Random(1),
    )
    assert episode["wrong_id"] is True
    assert episode["identified"] == "noisy_add1"
    assert episode["measured"] is False


def test_diagnostic_measure_charges_measure_and_falsifies_id_exact0():
    episode = run_episode(
        next(row for row in catalogue() if row["task_id"] == "vp_id0"),
        _diag_m, random.Random(1),
    )
    assert episode["measured"] is True
    assert episode["oracle"] >= 3
    assert episode["demonstrated_inconsistency"] is True
    assert episode["wrong_id"] is False
    acts = [step["action"] for step in episode["transcript"]]
    assert "MEASURE" in acts
    assert acts[acts.index("MEASURE") + 1] == "STOP_UNRESOLVED" or episode["remaining"] == []


def test_mod2_survives_measure_but_sequence_empties():
    assert filter_language([dict(action="MEASURE", observation=0)]) == ["mul2", "neg", "sum"]
    path = [
        dict(action="ACT_1", observation=1),
        dict(action="ACT_0", observation=0),
        dict(action="ACT_2", observation=0),
    ]
    assert filter_language(path) == []
    episode = run_episode(
        next(row for row in catalogue() if row["task_id"] == "vp_mod2"),
        _diag, random.Random(2),
    )
    assert episode["measured"] is False
    assert episode["demonstrated_inconsistency"] is False
    assert episode["wrong_id"] is True
    assert episode["identified"] == "noisy_add1"


def test_plus_prev_survives_measure_then_sequence_empties():
    after_measure = filter_language([dict(action="MEASURE", observation=0)])
    assert after_measure != []
    assert "sum" in after_measure or "neg" in after_measure or "mul2" in after_measure
    episode = run_episode(
        next(row for row in catalogue() if row["task_id"] == "vp_plus"),
        _diag, random.Random(3),
    )
    assert episode["demonstrated_inconsistency"] is True


def test_add1_twin_is_indistinguishable_and_identity_is_false():
    path = [
        dict(action="ACT_1", observation=2),
        dict(action="ACT_0", observation=1),
        dict(action="MEASURE", observation=1),
    ]
    assert filter_language(path) == ["add1"]
    episode = run_episode(
        next(row for row in catalogue() if row["task_id"] == "vp_twin"),
        _diag_m, random.Random(4),
    )
    assert episode["wrong_id"] is True
    assert episode["identified"] == "add1"
    assert episode["demonstrated_inconsistency"] is False
    assert episode["remaining"] == ["add1"]


def test_ordinary_add2_does_not_need_measure_for_identification():
    episode = run_episode(
        next(row for row in catalogue() if row["task_id"] == "vp_add2"),
        _diag, random.Random(5),
    )
    assert episode["correct_id"] is True
    assert episode["measured"] is False
    charged = run_episode(
        next(row for row in catalogue() if row["task_id"] == "vp_add2"),
        _diag_m, random.Random(5),
    )
    assert charged["correct_id"] is True
    assert charged["measured"] is True
    assert charged["oracle"] == episode["oracle"] - 1 + 3


def test_cost_aware_ig_avoids_zero_gain_measure_on_ordinary():
    def cost_ig(ctx):
        return choose_cost_aware_ig(
            ctx["remaining"], ctx["transcript"], ctx["available"], ctx["rng"],
        )

    episode = run_episode(
        next(row for row in catalogue() if row["task_id"] == "vp_add2"),
        cost_ig, random.Random(6),
    )
    assert episode["correct_id"] is True
    assert episode["measured"] is False


def test_varied_tasks_are_fresh_and_cover_four_roles():
    rows = varied_tasks()
    ids = {row["task_id"] for row in rows}
    assert ids.isdisjoint(OPENED_IDS)
    by = {row["split"] for row in rows}
    assert by == {
        "varied_measure", "varied_sequence", "varied_indistinct", "varied_ordinary",
    }
    outside = [row for row in rows if row["split"] != "varied_ordinary"]
    assert {row["mechanism"] for row in outside}.isdisjoint(set(LANGUAGE))
    ordinary = [row for row in rows if row["split"] == "varied_ordinary"]
    assert {row["mechanism"] for row in ordinary} <= set(LANGUAGE)
    assert len(ordinary) >= 3


def test_score_columns_separate_inconsistency_uncertainty_and_cost():
    rows = [
        dict(method="trained", correct_id=True, wrong_id=False,
             demonstrated_inconsistency=False, unresolved_uncertainty=False,
             unresolved=False, correct_unresolved=False, gold_in_language=True,
             total_work=10, oracle=1, measured=False, split="varied_ordinary"),
        dict(method="trained", correct_id=False, wrong_id=False,
             demonstrated_inconsistency=True, unresolved_uncertainty=False,
             unresolved=True, correct_unresolved=True, gold_in_language=False,
             total_work=20, oracle=5, measured=True, split="varied_measure"),
        dict(method="trained", correct_id=False, wrong_id=False,
             demonstrated_inconsistency=False, unresolved_uncertainty=True,
             unresolved=True, correct_unresolved=True, gold_in_language=False,
             total_work=8, oracle=2, measured=False, split="varied_indistinct"),
    ]
    cols = score_columns(rows)["trained"]
    assert cols["correct_solutions"] == 1
    assert cols["false_identification"] == 0
    assert cols["demonstrated_inconsistency"] == 1
    assert cols["unresolved_uncertainty"] == 1
    assert cols["oracle"] == 8
    assert cols["ordinary_measured"] == 0


def test_varied_run_does_not_rescore_opened_cells():
    payload = run_varied(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    assert {row["task_id"] for row in payload.get("assessment") or []}.isdisjoint(OPENED_IDS)
    if payload["assessment"]:
        cols = score_columns(payload["assessment"])
        assert set(cols["trained"]) >= {
            "correct_solutions", "false_identification",
            "demonstrated_inconsistency", "unresolved_uncertainty", "oracle",
        }
        assert "fixed_diagnostic_measure" in cols
        assert "cost_aware_ig" in cols
        methods = {row["method"] for row in payload["assessment"]}
        assert "fixed_diagnostic_measure" in methods
        assert "cost_aware_ig" in methods


def test_vanilla_ig_is_available_for_comparison():
    def ig(ctx):
        return choose_information_gain(
            ctx["remaining"], ctx["transcript"], ctx["available"], ctx["rng"],
        )

    episode = run_episode(
        next(row for row in catalogue() if row["task_id"] == "vp_neg"),
        ig, random.Random(7),
    )
    assert episode["correct_id"] is True or episode["unresolved"] is True
