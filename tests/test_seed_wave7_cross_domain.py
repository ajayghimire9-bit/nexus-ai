"""Wave-7 cross-domain tests. No language-model inference."""
from __future__ import annotations

from pathlib import Path
import tempfile

from nexus.seed.cross_domain_analogy import (
    SequenceWorld, apply_integer_clause_to_sequence,
)
from nexus.seed.mechanism_wave7_cross_domain import (
    ANALOGY, FACTORED_SCRATCH, NEXUS, OPENED_IDS, WAVE7_TASKS,
    run_wave7, verify_payload,
)


def test_wave7_ids_are_fresh():
    ids = {row["task_id"] for row in WAVE7_TASKS}
    assert ids.isdisjoint(OPENED_IDS)
    assert len(ids) == 9


def test_integer_clause_cannot_run_on_sequences():
    try:
        apply_integer_clause_to_sequence(("even", "add3", "id"), ("a", "b"))
        raise AssertionError("integer clause ran")
    except TypeError as exc:
        assert "integer_clause_on_sequence" in str(exc)


def test_private_read_rejected_before_lock():
    world = SequenceWorld("seq_even_append", 1, "stamp_trap", ("w", "x"), {
        "alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p",),
    })
    world.public_read("alpha")
    try:
        world.private_read("alpha")
        raise AssertionError("private allowed")
    except RuntimeError as exc:
        assert "private_eval_before_lock" in str(exc)


def test_wave7_run_passes_verifier_and_gates():
    payload = run_wave7(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    assert payload["gates"]["passed"] is True
    suite = payload["totals"]["suite"]
    assert suite[FACTORED_SCRATCH]["total_work"] < suite["coupled_random_disambiguation_scratch"]["total_work"]
    assert suite[ANALOGY]["mapping_correct"] == suite[ANALOGY]["n"]
    assert suite[NEXUS]["mapping_correct"] == suite[NEXUS]["n"]
    assert payload["usage"]["model_calls"] == 0
    assert payload["grammar_prior_retrained"] is False
