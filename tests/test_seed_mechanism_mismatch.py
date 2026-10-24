"""Mismatch-challenge tests. No language-model inference. Do not rescore opened E."""
from __future__ import annotations

import json
import random
from pathlib import Path
import tempfile

from nexus.seed.mechanism_investigate import (
    available_actions, choose_information_gain, filter_language,
    identification_supported, run_episode,
)
from nexus.seed.mechanism_mismatch import (
    OPENED_IDS, diagnose_excluded, run_mismatch, score_columns, verify_payload,
)
from nexus.seed.mechanism_tasks import catalogue, mismatch_tasks
from nexus.seed.mechanism_world import LANGUAGE, apply_hidden, blank_state


def test_threshold_still_executes_as_one_if_input_exceeds_one():
    assert apply_hidden("threshold", blank_state(1), "ACT_1")["observation"] == 0
    assert apply_hidden("threshold", blank_state(1), "ACT_2")["observation"] == 1


def test_catalogue_singleton_is_not_supported_identification():
    path = [
        dict(action="ACT_2", observation=1),
        dict(action="ACT_0", observation=0),
    ]
    remain = filter_language(path)
    assert remain == ["toggle"]
    assert identification_supported(remain, path) is False
    avail = available_actions({}, path, remain)
    assert "STOP_IDENTIFY" not in avail["actions"]
    assert "STOP_UNRESOLVED" in avail["actions"]


def test_post_singleton_probe_supports_identification():
    path = [
        dict(action="ACT_2", observation=5),
        dict(action="ACT_0", observation=3),
    ]
    remain = filter_language(path)
    assert remain == ["add3"]
    assert identification_supported(remain, path) is True
    assert "STOP_IDENTIFY" in available_actions({}, path, remain)["actions"]


def test_ig_must_falsify_or_report_uncertainty_on_threshold_path():
    task = next(row for row in catalogue() if row["task_id"] == "e_threshold")

    def ig(ctx):
        return choose_information_gain(ctx["remaining"], ctx["transcript"], ctx["available"], ctx["rng"])

    episode = run_episode(task, ig, random.Random(20))
    assert episode["wrong_id"] is False
    assert episode["identified"] is None
    assert episode["correct_unresolved"] is True or episode["remaining"] != ["toggle"]


def test_saved_records_show_diagnostic_evidence_gap():
    path = Path("artifacts/seed_mechanism_competence/seed_mechanism_competence.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    diagnosed = diagnose_excluded(payload)
    threshold = next(row for row in diagnosed["cases"] if row["task_id"] == "e_threshold")
    assert threshold["diagnostic_queries"][0] == ("ACT_1", 0)
    assert threshold["trained_queries"][0] != ("ACT_1", 0)
    assert threshold["trained_identified"] == "toggle"
    assert threshold["first_evidence_gap"]["step"] == 0


def test_mismatch_tasks_are_outside_language_and_fresh():
    rows = mismatch_tasks()
    ids = {row["task_id"] for row in rows}
    assert ids.isdisjoint(OPENED_IDS)
    outside = [row for row in rows if row["split"] == "mismatch"]
    assert {row["mechanism"] for row in outside}.isdisjoint(set(LANGUAGE))
    assert len(outside) >= 4


def test_mismatch_run_does_not_rescore_opened_cells():
    payload = run_mismatch(
        Path(tempfile.mkdtemp()),
        Path("artifacts/seed_mechanism_competence/seed_mechanism_competence.json"),
    )
    checked = verify_payload(payload)
    assert checked["valid"] is True
    assert {row["task_id"] for row in payload.get("assessment") or []}.isdisjoint(OPENED_IDS)
    if payload["assessment"]:
        cols = score_columns(payload["assessment"])
        assert set(cols["trained"]) >= {
            "correct_solutions", "false_identification", "unresolved", "total_work",
        }
