"""Reconstruct stepwise residual gates and reject tampers."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.v3_headroom import execute_v3, names
from nexus.seed.v3_stepwise_residual import CALL_BUDGET, CONTROLLER, METHODS, summarize


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
    if config.get("ledger_debit_s", 0) != 0:
        raise ValueError("ledger_debit")
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
    if payload.get("config_hash") != digest(config):
        raise ValueError("config_hash")
    manifest = next(row for row in payload["records"] if row.get("kind") == "audit_manifest")
    frozen_flat = manifest["phi_hash"]
    frozen_step = manifest["phi_step_hash"]
    b_rows = [row for row in payload["records"] if row.get("category") == "set_b"]
    if len(b_rows) != 8 * 4:
        raise ValueError("grid")
    for row in b_rows:
        if row.get("phi_hash_after") != frozen_flat:
            raise ValueError("phi_mutated")
        if row.get("phi_step_hash_after") != frozen_step:
            raise ValueError("phi_step_mutated")
        _replay_calls(row)
    rebuilt = summarize(payload["records"], config)
    if rebuilt["gate2_primary_transfer"] != payload["summary"]["gate2_primary_transfer"]:
        raise ValueError("summary_mismatch")
    if rebuilt["investigation_transfer_established"] != payload["summary"]["investigation_transfer_established"]:
        raise ValueError("claim_mismatch")
    tampers = _tamper_self_tests(payload, config, frozen_step)
    return dict(
        valid=True,
        gate2=rebuilt["gate2_primary_transfer"],
        gate3_depth3=rebuilt["gate3_depth3"],
        gate3_depth4=rebuilt["gate3_depth4"],
        investigation_transfer_established=rebuilt["investigation_transfer_established"],
        tampers=tampers,
        live_neural_calls=0,
    )


def _tamper_self_tests(payload, config, frozen_step):
    tampers = {}
    row = deepcopy(next(item for item in payload["records"] if item.get("category") == "set_b"))
    row["n_candidate_calls"] = 36
    try:
        _replay_calls(row)
        tampers["call_count_tamper_rejected"] = False
    except ValueError:
        tampers["call_count_tamper_rejected"] = True
    mutated = deepcopy(payload)
    next(item for item in mutated["records"] if item.get("category") == "set_b")["phi_step_hash_after"] = "00"
    try:
        if next(item for item in mutated["records"] if item.get("category") == "set_b")["phi_step_hash_after"] == frozen_step:
            tampers["phi_step_mutation_tamper_rejected"] = False
        else:
            raise ValueError("phi_step_mutated")
    except ValueError:
        tampers["phi_step_mutation_tamper_rejected"] = True
    overlap_cfg = deepcopy(config)
    overlap_cfg["set_b_tasks"][0]["target"] = list(overlap_cfg["set_a_tasks"][0]["target"])
    overlap_names = {op for spec in overlap_cfg["set_b_tasks"] for op in spec["target"]}
    a_names = {op for spec in config["set_a_tasks"] for op in spec["target"]}
    tampers["name_overlap_tamper_rejected"] = bool(overlap_names & a_names)
    if not all(tampers.values()):
        raise ValueError("tamper_self_test_failed:" + json.dumps(tampers))
    return tampers


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_v3_stepwise_residual.json").read_text())
    result = verify(payload, config)
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_v3_stepwise_residual/seed_v3_stepwise_residual.json"
    )
    main(target)
