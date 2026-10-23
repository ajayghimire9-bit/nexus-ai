"""Independent reconstruction of the harder-feature grid."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.harder_feature_study import (
    CLOSED_TASK_IDS, REQUIRED_SUPPLIED_PASSES, SUPPLIED_GATE, gate_passed, summarize,
)
from nexus.seed.input_contract import FROZEN_RECIPE, MAX_COMPLETIONS


def verify(payload, config, root=ROOT):
    if config.get("default_investigation_policy") != "fixed_boundary":
        raise ValueError("fixed_policy_not_default")
    if config.get("learned_ranking_promoted") or config.get("learning_research_resumed"):
        raise ValueError("learned_promoted")
    ids = {row["id"] for row in config["tasks"]}
    if ids & CLOSED_TASK_IDS:
        raise ValueError("closed_task_reused")
    records = payload["records"]
    events = [row for row in records if row.get("kind") == "execution"]
    previous = "0" * 64
    for i, event in enumerate(events, 1):
        obj = dict(event)
        claimed = obj.pop("hash")
        if claimed != digest(obj) or event["index"] != i or event["previous"] != previous:
            raise ValueError("event_chain")
        previous = claimed
    manifest = [row for row in records if row.get("kind") == "audit_manifest"]
    if len(manifest) != 1 or manifest[0]["config_hash"] != digest(config):
        raise ValueError("config_manifest")
    inspect = [row for row in records if row.get("category") == "inspect"]
    if len(inspect) != 1 or inspect[0].get("frozen_recipe") != FROZEN_RECIPE:
        raise ValueError("inspect")
    if inspect[0].get("max_completions") != MAX_COMPLETIONS:
        raise ValueError("max_completions")
    grid = config["expected_grid"]
    supplied = [row for row in records if row.get("category") == "supplied"]
    acquire = [row for row in records if row.get("category") == "acquire"]
    if payload.get("blocked_step") is None:
        if len(supplied) != grid["supplied_cells"]:
            raise ValueError("supplied_count")
        if len(acquire) != grid["acquire_cells"]:
            raise ValueError("acquire_count")
        if any(row.get("model") != "coder15" for row in supplied + acquire):
            raise ValueError("not_frozen_model")
        if any(int(row.get("calls_charged") or 0) > MAX_COMPLETIONS for row in supplied + acquire):
            raise ValueError("over_budget")
        if {row.get("contract_origin") for row in supplied} != {"supplied"}:
            raise ValueError("supplied_origin")
        origins = {row.get("contract_origin") for row in acquire}
        if not origins <= {"inferred", "asked"}:
            raise ValueError("acquire_origin")
        gate = next(row for row in records if row.get("category") == "gate")
        rebuilt = gate_passed(supplied)
        if bool(gate.get("passed")) != rebuilt:
            raise ValueError("gate_mismatch")
        transfer = [row for row in records if row.get("category") in {"experience", "scratch"}]
        if rebuilt and len(transfer) != grid["transfer_cells_if_gate"]:
            raise ValueError("transfer_missing")
        if not rebuilt and transfer:
            raise ValueError("transfer_without_gate")
        required = {row["id"] for row in config["tasks"] if row.get("phase") == "harder"}
        if not set(REQUIRED_SUPPLIED_PASSES) <= required:
            raise ValueError("required_ids")
        if SUPPLIED_GATE != 4:
            raise ValueError("gate_constant")
    rebuilt = summarize(records, config)
    if rebuilt["learned_ranking_promoted"] or rebuilt["learning_research_resumed"]:
        raise ValueError("learned_promoted_in_summary")
    if rebuilt["supplied_rows"] != payload["summary"]["supplied_rows"]:
        raise ValueError("summary_mismatch")
    if payload.get("historical_fingerprints") != historical_artifact_fingerprints(root):
        raise ValueError("historical_artifact_changed")
    return dict(
        valid=True, events=len(events),
        operations=dict(Counter(event.get("operation") for event in events)),
        grid=grid, gate=rebuilt.get("gate"),
        learned_ranking_promoted=False, learning_research_resumed=False,
    )


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_harder_features.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_harder_features/seed_harder_features.json"
    )
    main(target)
