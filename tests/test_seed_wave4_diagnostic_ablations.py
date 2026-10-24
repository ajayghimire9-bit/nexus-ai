"""Wave-4 diagnostic ablation tests. No language-model inference."""
from __future__ import annotations

from pathlib import Path
import tempfile

from nexus.seed.mechanism_wave4_diagnostic import (
    BOTH, OPENED_IDS, run_wave4_diagnostic, verify_payload,
)
from nexus.seed.mechanism_tasks import unfamiliar_policy_tasks


def test_wave4_suite_is_new_and_split():
    related = unfamiliar_policy_tasks("w4_related_parity")
    unrel = unfamiliar_policy_tasks("w4_unrelated_guard")
    look = unfamiliar_policy_tasks("w4_misleading_lookalike")
    oog = unfamiliar_policy_tasks("w4_oog")
    retain = unfamiliar_policy_tasks("w4_retain")
    ids = {row["task_id"] for row in related + unrel + look + oog + retain}
    assert ids.isdisjoint(OPENED_IDS)
    assert {row["w4_group"] for row in related} == {"related_parity"}
    assert {row["w4_group"] for row in unrel} == {"unrelated_guard"}
    assert {row["w4_group"] for row in look} == {"misleading_lookalike"}
    assert {row["unknown_kind"] for row in oog} == {"oog"}
    assert {row["retain_wave"] for row in retain} == {"wave1", "wave2", "wave3"}
    assert len(related) == 3
    assert len(unrel) == 2
    assert len(look) == 2
    assert len(oog) == 2
    assert len(retain) == 6


def test_wave4_run_passes_verifier_and_gates():
    payload = run_wave4_diagnostic(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    express = payload["totals"]["expressible"]
    oog = payload["totals"]["true_oog"]
    retain = payload["totals"]["retain"]
    look = payload["totals"]["misleading_lookalike"]
    cont = express[BOTH]
    assert cont["total_acquisition_work"] < express["wave1_frozen_neither"]["total_acquisition_work"]
    assert look[BOTH]["even_rejected_by_confirm"] >= 3
    assert look[BOTH]["false_positive_parity_lock"] == 0
    for name in express:
        assert oog[name]["false_positive"] == 0
        assert oog[name]["abstained_unknown"] == 6
        assert retain[name]["useful_acquisition"] == 18
    assert payload["usage"]["model_calls"] == 0
    assert payload["track_b_closed"] is True
    assert payload["learning_to_learn_established"] is False
