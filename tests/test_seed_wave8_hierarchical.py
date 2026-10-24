"""Wave-8 hierarchical gated evolution tests. No language-model inference."""
from __future__ import annotations

from pathlib import Path
import tempfile

from nexus.seed.hierarchical_gated_evolution import Wave8World
from nexus.seed.mechanism_wave8_hierarchical import (
    NEXUS, OPENED_IDS, SCRATCH, WAVE7, WAVE8_TASKS, run_wave8, verify_payload,
)


def test_wave8_ids_are_fresh():
    ids = {row["task_id"] for row in WAVE8_TASKS}
    assert ids.isdisjoint(OPENED_IDS)
    assert len(ids) == 12


def test_private_read_rejected_before_lock():
    world = Wave8World("seq_even_append", 1, "stamp_trap", ("w", "x"), {
        "alpha": ("c",), "beta": ("x", "y"), "gamma": (), "delta": ("p",),
    })
    world.public_read("alpha")
    try:
        world.private_read("alpha")
        raise AssertionError("private allowed")
    except RuntimeError as exc:
        assert "private_eval_before_lock" in str(exc)


def test_wave8_run_passes_verifier_and_gates():
    payload = run_wave8(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    assert payload["gates"]["passed"] is True
    g1 = payload["totals"]["g1"]
    assert g1[NEXUS]["total_work"] < g1[WAVE7]["total_work"]
    assert g1[NEXUS]["total_work"] <= g1[SCRATCH]["total_work"]
    assert payload["usage"]["model_calls"] == 0
