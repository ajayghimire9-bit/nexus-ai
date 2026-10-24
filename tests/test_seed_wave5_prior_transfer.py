"""Wave-5 prior and transfer tests. No language-model inference."""
from __future__ import annotations

from pathlib import Path
import tempfile

from nexus.seed.event_record_env import parse_record
from nexus.seed.mechanism_tasks import unfamiliar_policy_tasks
from nexus.seed.mechanism_wave5_prior_transfer import (
    A_FULL_STATIC, OPENED_IDS, run_wave5, verify_payload,
)


def test_wave5_ids_are_fresh_and_split():
    rows = []
    for split in (
        "w5_source", "w5_related", "w5_lookalike", "w5_unrelated", "w5_oog",
        "w5_retain", "w5_event_related", "w5_event_lookalike",
        "w5_event_unrelated", "w5_event_oog", "w5_event_retain",
    ):
        rows.extend(unfamiliar_policy_tasks(split))
    ids = {row["task_id"] for row in rows}
    assert ids.isdisjoint(OPENED_IDS)
    assert {row["split"] for row in rows if row["split"].startswith("w5_event")}


def test_generic_parser_does_not_name_the_output():
    parsed = parse_record(dict(kind="event", slot="alpha", payload=0, result=3, echo=0, stamp=1))
    assert "payload" in parsed and "result" in parsed and "echo" in parsed


def test_wave5_run_passes_safety_and_verifier():
    payload = run_wave5(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    assert payload["gates"]["safety_passed"] is True
    look = payload["totals"]["a_lookalike"]
    assert look[A_FULL_STATIC]["false_positive_parity_lock"] == 0
    oog = payload["totals"]["a_oog"]
    for name, cell in oog.items():
        assert cell["false_positive"] == 0
        assert cell["abstained_unknown"] == 6
    assert payload["usage"]["model_calls"] == 0
    assert payload["track_b_closed"] is True
    assert payload["learning_to_learn_established"] is False
    supplied = [r for r in payload["assessment"] if r.get("mapping_condition") == "supplied"]
    acquired = [r for r in payload["assessment"] if r.get("mapping_condition") == "acquired"]
    assert supplied and acquired
    assert all(r.get("mapping_supplied") is False for r in acquired)
