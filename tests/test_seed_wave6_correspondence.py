"""Wave-6 correspondence tests. No language-model inference."""
from __future__ import annotations

from pathlib import Path
import tempfile

from nexus.seed.correspondence_env import RecordWorld
from nexus.seed.mechanism_tasks import unfamiliar_policy_tasks
from nexus.seed.mechanism_wave6_correspondence import (
    CLAUSES, FIXED, GREEDY, OPENED_IDS, run_wave6, verify_payload,
)


def test_wave6_ids_are_fresh():
    ids = {
        row["task_id"]
        for split in ("w6_stamp", "w6_echo", "w6_ambiguous", "w6_oog", "w6_retain")
        for row in unfamiliar_policy_tasks(split)
    }
    assert ids.isdisjoint(OPENED_IDS)
    assert len(ids) == 8


def test_private_read_rejected_before_lock():
    world = RecordWorld("w5_even_add3", 1, "stamp_trap")
    world.public_read("alpha")
    try:
        world.private_read("alpha")
        raise AssertionError("private allowed")
    except RuntimeError as exc:
        assert "private_eval_before_lock" in str(exc)


def test_wave6_run_passes_verifier_and_gates():
    payload = run_wave6(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    assert payload["gates"]["passed"] is True
    ident = payload["totals"]["identifiable"]
    assert ident[GREEDY]["mapping_correct"] == 0
    assert ident[FIXED]["mapping_correct"] == ident[FIXED]["n"]
    assert ident[CLAUSES]["mapping_correct"] == ident[CLAUSES]["n"]
    amb = payload["totals"]["ambiguous"]
    assert amb[CLAUSES]["false_unique"] == 0
    assert amb[FIXED]["mapping_correct"] == amb[FIXED]["n"]
    assert payload["usage"]["model_calls"] == 0
    assert payload["grammar_prior_retrained"] is False
