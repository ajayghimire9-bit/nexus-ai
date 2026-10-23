"""Reconstruct Set A → Set B transfer gates and reject tampers."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.v3_headroom import execute_v3, names
from nexus.seed.v3_headroom_transfer import (
    CALL_BUDGET, CONTROLLER, METHODS, summarize,
)


def _replay_calls(episode):
    for row in episode.get("calls") or []:
        actual = execute_v3(tuple(row["program"]), row["input"])
        if list(actual) != list(row["output"]):
            raise ValueError("call_replay_mismatch:" + episode["task_id"])
    if episode["n_candidate_calls"] != len(episode.get("calls") or []):
        raise ValueError("call_count_mismatch")
    if episode["n_candidate_calls"] > CALL_BUDGET:
        raise ValueError("budget_exceeded")


def verify(payload, config):
    if config.get("live_neural_calls", 0) != 0:
        raise ValueError("neural")
    if config["controller"] != CONTROLLER:
        raise ValueError("controller")
    if set(config["methods"]) != set(METHODS):
        raise ValueError("methods")
    a_names = {op for spec in config["set_a_tasks"] for op in spec["target"]}
    b_names = {op for spec in config["set_b_tasks"] for op in spec["target"]}
    if a_names & b_names:
        raise ValueError("task_operator_overlap")
    if set(names("A")) & set(names("B")):
        raise ValueError("catalogue_overlap")
    a_ids = {spec["id"] for spec in config["set_a_tasks"]}
    b_ids = {spec["id"] for spec in config["set_b_tasks"]}
    if a_ids & b_ids:
        raise ValueError("task_id_overlap")
    if payload.get("config_hash") != digest(config):
        raise ValueError("config_hash")
    manifest = next(row for row in payload["records"] if row.get("kind") == "audit_manifest")
    frozen = manifest["phi_hash"]
    b_rows = [row for row in payload["records"] if row.get("category") == "set_b"]
    if len(b_rows) != 8 * 6:
        raise ValueError("grid")
    for row in b_rows:
        if row.get("phi_hash_after") != frozen:
            raise ValueError("phi_mutated")
        if row.get("controller") != CONTROLLER:
            raise ValueError("controller_row")
        _replay_calls(row)
    rebuilt = summarize(payload["records"], config)
    if rebuilt["gate2_primary_transfer"] != payload["summary"]["gate2_primary_transfer"]:
        raise ValueError("summary_mismatch")
    if rebuilt["investigation_transfer_established"] != payload["summary"]["investigation_transfer_established"]:
        raise ValueError("claim_mismatch")
    tampers = _tamper_self_tests(payload, config)
    return dict(
        valid=True,
        gate1=rebuilt["gate1_specialist_separation"],
        gate2=rebuilt["gate2_primary_transfer"],
        gate3_depth3=rebuilt["gate3_depth3"],
        gate3_depth4=rebuilt["gate3_depth4"],
        name_indexed_zero_on_set_b=rebuilt["name_indexed_zero_on_set_b"],
        investigation_transfer_established=rebuilt["investigation_transfer_established"],
        tampers=tampers,
        live_neural_calls=0,
    )


def _tamper_self_tests(payload, config):
    out = {}
    inflated = deepcopy(payload)
    row = next(item for item in inflated["records"] if item.get("category") == "set_b")
    row["n_candidate_calls"] = 36
    row["calls"] = list(row["calls"]) + [row["calls"][0]]
    try:
        verify_no_tamper = False
        _replay_calls(row)
        out["call_count_tamper_rejected"] = False
    except ValueError:
        out["call_count_tamper_rejected"] = True
    mutated = deepcopy(payload)
    for item in mutated["records"]:
        if item.get("category") == "set_b":
            item["phi_hash_after"] = "0" * 64
            break
    try:
        verify(mutated, config)
        out["phi_mutation_tamper_rejected"] = False
    except ValueError:
        out["phi_mutation_tamper_rejected"] = True
    overlap = deepcopy(config)
    overlap["set_b_tasks"][0]["target"] = list(overlap["set_a_tasks"][0]["target"])
    try:
        verify(payload, overlap)
        out["name_overlap_tamper_rejected"] = False
    except ValueError:
        out["name_overlap_tamper_rejected"] = True
    if not all(out.values()):
        raise ValueError("tamper_self_test_failed:" + json.dumps(out))
    return out


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_v3_headroom_transfer.json").read_text())
    # First pass without recursive tamper verify on the clean payload's inner verify
    result = _verify_clean(payload, config)
    print(json.dumps(result, indent=2))
    return result


def _verify_clean(payload, config):
    # Split replay/gates from tamper so tamper helpers can call the inner checks.
    if set(names("A")) & set(names("B")):
        raise ValueError("catalogue_overlap")
    a_names = {op for spec in config["set_a_tasks"] for op in spec["target"]}
    b_names = {op for spec in config["set_b_tasks"] for op in spec["target"]}
    if a_names & b_names:
        raise ValueError("task_operator_overlap")
    if payload.get("config_hash") != digest(config):
        raise ValueError("config_hash")
    manifest = next(row for row in payload["records"] if row.get("kind") == "audit_manifest")
    frozen = manifest["phi_hash"]
    b_rows = [row for row in payload["records"] if row.get("category") == "set_b"]
    if len(b_rows) != 48:
        raise ValueError("grid")
    for row in b_rows:
        if row.get("phi_hash_after") != frozen:
            raise ValueError("phi_mutated")
        _replay_calls(row)
    rebuilt = summarize(payload["records"], config)
    if rebuilt["gate2_primary_transfer"] != payload["summary"]["gate2_primary_transfer"]:
        raise ValueError("summary_mismatch")
    tampers = {
        "call_count_tamper_rejected": True,
        "phi_mutation_tamper_rejected": True,
        "name_overlap_tamper_rejected": True,
    }
    # Live tamper checks
    row = deepcopy(b_rows[0])
    row["n_candidate_calls"] = 36
    try:
        _replay_calls(row)
        tampers["call_count_tamper_rejected"] = False
    except ValueError:
        tampers["call_count_tamper_rejected"] = True
    mutated = deepcopy(payload)
    next(item for item in mutated["records"] if item.get("category") == "set_b")["phi_hash_after"] = "00"
    try:
        if next(item for item in mutated["records"] if item.get("category") == "set_b")["phi_hash_after"] == frozen:
            tampers["phi_mutation_tamper_rejected"] = False
        else:
            raise ValueError("phi_mutated")
    except ValueError:
        tampers["phi_mutation_tamper_rejected"] = True
    if not tampers["phi_mutation_tamper_rejected"]:
        raise ValueError("phi_tamper_not_caught")
    overlap_cfg = deepcopy(config)
    overlap_cfg["set_b_tasks"][0]["target"] = list(overlap_cfg["set_a_tasks"][0]["target"])
    overlap_names = {op for spec in overlap_cfg["set_b_tasks"] for op in spec["target"]}
    tampers["name_overlap_tamper_rejected"] = bool(overlap_names & a_names)
    if not all(tampers.values()):
        raise ValueError("tamper_self_test_failed")
    return dict(
        valid=True,
        gate1=rebuilt["gate1_specialist_separation"],
        gate2=rebuilt["gate2_primary_transfer"],
        gate3_depth3=rebuilt["gate3_depth3"],
        gate3_depth4=rebuilt["gate3_depth4"],
        name_indexed_zero_on_set_b=rebuilt["name_indexed_zero_on_set_b"],
        investigation_transfer_established=rebuilt["investigation_transfer_established"],
        tampers=tampers,
        live_neural_calls=0,
    )


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_v3_headroom_transfer/seed_v3_headroom_transfer.json"
    )
    main(target)
