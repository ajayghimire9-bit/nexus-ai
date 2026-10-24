"""Continual Wave-3 assimilation tests. No language-model inference."""
from __future__ import annotations

from pathlib import Path
import tempfile

from nexus.seed.mechanism_continual_wave3 import (
    OPENED_IDS, run_continual_wave3, verify_payload,
)
from nexus.seed.mechanism_tasks import unfamiliar_policy_tasks


def test_wave3_suite_is_new_and_split():
    wave2 = unfamiliar_policy_tasks("w2_holdout")
    express = unfamiliar_policy_tasks("w3_expressible")
    oog = unfamiliar_policy_tasks("w3_oog")
    retain = unfamiliar_policy_tasks("w3_retain")
    ids = {row["task_id"] for row in wave2 + express + oog + retain}
    assert ids.isdisjoint(OPENED_IDS)
    assert {row["unknown_kind"] for row in express} == {"type_a"}
    assert {row["unknown_kind"] for row in oog} == {"oog"}
    assert {row["retain_wave"] for row in retain} == {"wave1", "wave2"}
    assert len(express) == 3
    assert len(oog) == 2
    assert len(retain) == 4


def test_continual_run_passes_verifier_and_gates():
    payload = run_continual_wave3(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    express = payload["totals"]["wave3_expressible"]
    oog = payload["totals"]["wave3_oog"]
    retain = payload["totals"]["retain"]
    cont = express["continual_assimilating_nexus"]
    assert cont["useful_acquisition"] == 9
    assert cont["total_acquisition_work"] < express["wave1_frozen_abductive"]["total_acquisition_work"]
    assert cont["total_acquisition_work"] < express["learned_policy_open_grammar_cleared"]["total_acquisition_work"]
    assert cont["total_acquisition_work"] < express["untrained_open_grammar"]["total_acquisition_work"]
    assert cont["env_plus_synth"] < express["wave1_frozen_abductive"]["env_plus_synth"]
    for name in express:
        assert oog[name]["false_positive"] == 0
        assert oog[name]["abstained_unknown"] == 6
        assert oog[name]["useful_acquisition"] == 0
        assert retain[name]["useful_acquisition"] == 12
    assert payload["usage"]["model_calls"] == 0
    assert payload["track_b_closed"] is True
    assert payload["learning_to_learn_established"] is False
