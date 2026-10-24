"""Out-of-bank beyond-catalog tests. No language-model inference."""
from __future__ import annotations

from pathlib import Path
import tempfile

from nexus.seed.mechanism_beyond_catalog import (
    OPENED_IDS, SUPPLIED_BANK, detect_catalog_exhaustion, run_beyond_catalog,
    synthesize_beyond_bank, verify_payload,
)
from nexus.seed.mechanism_beyond_catalog import BeyondMeter
from nexus.seed.mechanism_skills import SubMechanismLibrary
from nexus.seed.mechanism_tasks import unfamiliar_policy_tasks


def test_holdout_absent_from_supplied_bank():
    holdout = unfamiliar_policy_tasks("oob_holdout")
    retain = unfamiliar_policy_tasks("oob_retain")
    assert {row["task_id"] for row in holdout + retain}.isdisjoint(OPENED_IDS)
    assert {row["mechanism"] for row in holdout}.isdisjoint(set(SUPPLIED_BANK))
    kinds = {row["unknown_kind"] for row in holdout}
    assert kinds == {"type_a", "type_b"}
    assert sum(row["unknown_kind"] == "type_a" for row in holdout) == 3
    assert sum(row["unknown_kind"] == "type_b" for row in holdout) == 1


def test_detect_catalog_exhaustion_never_returns_eliminated():
    meter = BeyondMeter()
    detected = detect_catalog_exhaustion(
        [dict(action="ACT_1", observation=4)], meter,
    )
    assert detected["catalog_exhausted"] is True
    assert detected["surviving_bank_candidates"] == 0
    assert detected["remaining"] == []
    assert meter.hypothesis_evals > 0


def test_type_a_hits_guard_type_b_falls_back():
    library = SubMechanismLibrary()
    library.remember_subclause(dict(guard="pos", signature="1,0", clause="pos_guard"))
    library.remember_subclause(dict(guard="neg", signature="0,1", clause="neg_guard"))
    meter = BeyondMeter()
    type_a = synthesize_beyond_bank(
        [
            dict(action="ACT_2", observation=5),
            dict(action="ACT_NEG", observation=3),
            dict(action="ACT_1", observation=4),
        ],
        library, meter,
    )
    assert type_a["kind"] == "type_a"
    assert type_a["subclause_hits"] > 0
    type_b = synthesize_beyond_bank(
        [
            dict(action="ACT_2", observation=4),
            dict(action="ACT_NEG", observation=-1),
            dict(action="ACT_1", observation=1),
        ],
        library, BeyondMeter(),
    )
    assert type_b["kind"] == "type_b"
    assert type_b["subclause_hits"] == 0
    assert type_b["n_remaining"] > 0


def test_beyond_catalog_run_passes_verifier_and_gates():
    payload = run_beyond_catalog(Path(tempfile.mkdtemp()))
    checked = verify_payload(payload)
    assert checked["valid"] is True
    hold = payload["totals"]["holdout"]
    bank = hold["supplied_bank_only"]
    untrained = hold["untrained_open_grammar"]
    cleared = hold["learned_policy_open_grammar_cleared"]
    abduct = hold["nexus_abductive_beyond_bank"]
    assert bank["useful_acquisition"] == 0
    assert bank["catalog_exhausted"] == 12
    assert bank["false_positive"] == 0
    assert untrained["useful_acquisition"] == cleared["useful_acquisition"] == abduct["useful_acquisition"] == 12
    assert payload["totals"]["retain"]["untrained_open_grammar"]["useful_acquisition"] == 6
    assert payload["totals"]["retain"]["learned_policy_open_grammar_cleared"]["useful_acquisition"] == 6
    assert payload["totals"]["retain"]["nexus_abductive_beyond_bank"]["useful_acquisition"] == 6
    assert cleared["total_acquisition_work"] < untrained["total_acquisition_work"]
    assert abduct["total_acquisition_work"] < cleared["total_acquisition_work"]
    assert abduct["distill_cost"] > 0
    assert abduct["subclause_hits"] > 0
    assert cleared["subclause_hits"] == 0
    assert payload["usage"]["model_calls"] == 0
    assert payload["track_b_closed"] is True
    assert payload["learning_to_learn_established"] is False
    assert payload["bank_coverage"] == 0.0
