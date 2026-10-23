"""Offline checks for stepwise residual search. 0 neural calls. No Set B scoring."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.capability_evidence import EventMeter
from nexus.seed.v3_headroom import ALL_SPECS, CALL_BUDGET, automatic_signature, names
from nexus.seed.v3_headroom_transfer import CONTROLLER, pair
from nexus.seed.v3_stepwise_residual import (
    BEAM_WIDTH, METHODS, OPS_PER_STEP, StepwiseResidualInvestigator,
    begin, operator_probe_signature, residual_io_invariant, train_phi_step,
)


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "artifacts/seed_v3_headroom_transfer/seed_v3_headroom_transfer.json"


def test_config_locks_budget_beam_and_disjoint_sets():
    config = json.loads((ROOT / "configs/seed_v3_stepwise_residual.json").read_text())
    assert config["call_budget"] == CALL_BUDGET == 35
    assert config["controller"] == CONTROLLER
    assert config["methods"] == list(METHODS)
    assert config["live_neural_calls"] == 0
    assert config["ledger_debit_s"] == 0
    assert config["overwrite_9b4468b"] is False
    assert config["beam_width"] == BEAM_WIDTH
    assert config["ops_per_step"] == OPS_PER_STEP
    a = {op for spec in config["set_a_tasks"] for op in spec["target"]}
    b = {op for spec in config["set_b_tasks"] for op in spec["target"]}
    assert a <= set(names("A"))
    assert b <= set(names("B"))
    assert not a & b
    assert {spec["id"] for spec in config["set_a_tasks"]}.isdisjoint(
        {spec["id"] for spec in config["set_b_tasks"]}
    )


def test_probe_signatures_transfer_without_names():
    assert operator_probe_signature("keep_pos") == operator_probe_signature("keep_neg")
    assert operator_probe_signature("keep_even") == operator_probe_signature("keep_odd")
    assert operator_probe_signature("take_prefix_half") == operator_probe_signature("drop_suffix_half")
    assert operator_probe_signature("res_mod3") == operator_probe_signature("res_mod4")
    assert operator_probe_signature("add2_mod5") == operator_probe_signature("add3_mod8")
    assert operator_probe_signature("mul2_mod7") == operator_probe_signature("mul3_mod5")
    for op in list(names("A")) + list(names("B")):
        sig = operator_probe_signature(op)
        assert sig not in ALL_SPECS
        assert sig != op
        assert automatic_signature(op) in sig


def test_phi_step_trains_on_set_a_only_and_freezes():
    config = json.loads((ROOT / "configs/seed_v3_stepwise_residual.json").read_text())
    trained = train_phi_step(config)
    assert trained["frozen"]["freeze_weights"] is True
    assert all(key[1] not in set(names("A")) | set(names("B")) for key in trained["phi_step"])
    assert all(op not in str(key) for key in trained["phi_step"] for op in names("B"))
    records = []
    state = begin(config, records.append)
    assert records[0]["freeze_weights"] is True
    assert records[0]["live_neural_calls"] == 0
    assert records[0]["phi_step_hash"] == state["trained_step"]["frozen"]["hash"]
    assert set(records[0]["signatures_a"]).isdisjoint(records[0]["signatures_b"])


def test_observational_prune_and_budget_on_set_a_support():
    config = json.loads((ROOT / "configs/seed_v3_stepwise_residual.json").read_text())
    trained = train_phi_step(config)
    spec = next(row for row in config["set_a_tasks"] if row["id"] == "a_filter_d3")
    task = dict(
        id="offline_a_filter_d3",
        cluster="filter",
        depth=3,
        target=spec["target"],
        support=pair("filter", tuple(spec["target"]), config["support_payloads"]["filter"]),
        assessment=pair("filter", tuple(spec["target"]), config["assessment_payloads"]["filter"]),
    )
    residual = residual_io_invariant(task["support"][0], task["support"][1])
    assert residual == "length_contracting"
    events = []
    investigator = StepwiseResidualInvestigator(trained["phi_step"], EventMeter(events.append), set_id="A")
    episode = investigator.run(task, "offline:a_filter_d3")
    assert episode["n_candidate_calls"] <= CALL_BUDGET
    assert episode["n_candidate_calls"] == len(events)
    assert episode["n_candidate_calls"] == len(episode["calls"])
    assert episode["observational_pruned"] >= 0
    assert episode["search"] == "stepwise_residual"


def test_historical_9b4468b_artifact_is_untouched():
    payload = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    assert payload["study_id"] == "seed-v3-headroom-transfer-1"
    assert payload["summary"]["gate2_phi_mean"] == 31.625
    assert payload["summary"]["gate2_untrained_mean"] == 31.0
    assert payload["summary"]["gate2_primary_transfer"] is False
