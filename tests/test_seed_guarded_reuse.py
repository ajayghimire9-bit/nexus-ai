"""Development checks for equally guarded template reuse on fresh cases."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.guarded_reuse import CLOSED_TASK_IDS
from nexus.seed.repair_schema_memory import (
    RepairSchema, propose_guarded_template, propose_retrieved_repair,
)


ROOT = Path(__file__).resolve().parents[1]


def _schema():
    return RepairSchema(
        schema_id="cmp",
        family="comparison_boundary",
        trigger="Allow n equal to the cap.",
        transformation="compare_op_swap",
        applicability={"from_op": "Lt", "to_op": "LtE", "require_unique_matching_compare": True},
        bindings={"from_op": "Lt", "to_op": "LtE"},
        preconditions={"require_unique_matching_compare": True},
    )


def test_fresh_config_excludes_closed_ids_and_keeps_fixed_policy():
    config = json.loads((ROOT / "configs/seed_guarded_template_reuse.json").read_text())
    assert config["default_investigation_policy"] == "fixed_boundary"
    assert config["learned_policy_promoted"] is False
    assert config["equally_guarded_template"] is True
    ids = {config["transfer"]["source"]["id"], *(row["id"] for row in config["transfer"]["later"])}
    assert not ids & CLOSED_TASK_IDS
    roles = {row["id"]: row["reuse_role"] for row in config["transfer"]["later"]}
    assert roles["py_span_ok"] == "same_repair"
    assert roles["py_floor_ok"] == "same_repair"
    assert roles["py_reject_floor"] == "opposite"
    assert roles["py_note_join"] == "unrelated"
    assert roles["py_threshold_fix"] == "clarification"
    assert config["expected_grid"]["transfer_cells"] == 15


def test_memory_rebounds_inclusive_polarity_template_does_not():
    schema = _schema()
    files = {"floor.py": "def ok(item):\n    return item['score'] > item['floor']\n"}
    public = [{"entry": "floor.ok", "input": {"score": 3, "floor": 3}, "expected": True}]
    request = "Allow score equal to the floor."
    memory = propose_retrieved_repair(schema, request, files, public)
    template = propose_guarded_template("comparison_boundary", request, files, public)
    assert memory.decision == "apply"
    assert memory.files is not None and ">=" in memory.files["floor.py"]
    assert template.decision == "abstain"
    assert template.reason == "transform_not_applicable"
    assert template.files is None


def test_same_gate_refuses_exclusive_and_asks_when_ambiguous():
    schema = _schema()
    exclusive_req = "Reject values equal to the floor; only strictly greater values pass."
    exclusive_files = {"rej.py": "def pass_(item):\n    return item['score'] > item['floor']\n"}
    exclusive_public = [{"entry": "rej.pass_", "input": {"score": 3, "floor": 3}, "expected": False}]
    mem_ex = propose_retrieved_repair(schema, exclusive_req, exclusive_files, exclusive_public)
    tpl_ex = propose_guarded_template("comparison_boundary", exclusive_req, exclusive_files, exclusive_public)
    assert mem_ex.decision == tpl_ex.decision == "refuse"
    ask_req = "Adjust the threshold check."
    ask_files = {"thr.py": "def keep(item):\n    return item['n'] < item['max']\n"}
    ask_public = [{"entry": "thr.keep", "input": {"n": 1, "max": 4}, "expected": True}]
    mem_ask = propose_retrieved_repair(schema, ask_req, ask_files, ask_public)
    tpl_ask = propose_guarded_template("comparison_boundary", ask_req, ask_files, ask_public)
    assert mem_ask.decision == tpl_ask.decision == "ask"
    assert mem_ask.used_private_tests is False
    assert tpl_ask.used_private_tests is False
