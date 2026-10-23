"""Pre-score checks for the Set A → Set B transfer contract."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.v3_headroom import automatic_signature, names
from nexus.seed.v3_headroom_transfer import (
    CALL_BUDGET, CONTROLLER, METHODS, begin, method_order, register_signatures,
    train_set_a,
)


ROOT = Path(__file__).resolve().parents[1]


def test_config_locks_equalized_budget_and_disjoint_sets():
    config = json.loads((ROOT / "configs/seed_v3_headroom_transfer.json").read_text())
    assert config["call_budget"] == CALL_BUDGET == 35
    assert config["controller"] == CONTROLLER
    assert config["methods"] == list(METHODS)
    assert config["live_neural_calls"] == 0
    assert config["freeze_weights"] is True
    a = {op for spec in config["set_a_tasks"] for op in spec["target"]}
    b = {op for spec in config["set_b_tasks"] for op in spec["target"]}
    assert a <= set(names("A"))
    assert b <= set(names("B"))
    assert not a & b
    assert {spec["id"] for spec in config["set_a_tasks"]}.isdisjoint(
        {spec["id"] for spec in config["set_b_tasks"]}
    )
    assert {spec["depth"] for spec in config["set_b_tasks"]} == {3, 4}


def test_set_b_signatures_come_from_specialist_probes_not_names():
    registered = register_signatures(names("B"))
    assert set(registered) == set(names("B"))
    assert "keep_neg" not in set(registered.values())
    assert registered["keep_neg"] == automatic_signature("keep_neg")
    assert registered["keep_neg"] == automatic_signature("keep_pos")


def test_name_index_is_zero_on_set_b_and_phi_keys_exclude_names():
    config = json.loads((ROOT / "configs/seed_v3_headroom_transfer.json").read_text())
    trained = train_set_a(config, register_signatures(names("A")))
    assert all(op not in trained["name_weights"] for op in names("B"))
    assert all(key[1] not in set(names("A")) | set(names("B")) for key in trained["phi"])
    order = method_order(
        "name_indexed_ranker", "length_contracting", trained, register_signatures(names("B")),
    )
    raw = method_order(
        "untrained_default", "length_contracting", trained, register_signatures(names("B")),
    )
    assert order == raw


def test_begin_freezes_phi_and_forbids_method_drift():
    config = json.loads((ROOT / "configs/seed_v3_headroom_transfer.json").read_text())
    records = []
    state = begin(config, records.append)
    assert records[0]["freeze_weights"] is True
    assert records[0]["live_neural_calls"] == 0
    assert records[0]["phi_hash"] == state["trained"]["frozen"]["hash"]
    assert records[0]["signatures_from"] == "specialist_probes_only"
