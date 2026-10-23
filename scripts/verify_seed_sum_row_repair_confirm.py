"""Independent reconstruction of the sum-row-repair confirmation grid."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.input_contract import MAX_COMPLETIONS
from nexus.seed.sum_row_repair_study import (
    CLOSED_TASK_IDS, HISTORICAL_HARDER_SHA256, WORKER_PROMPT_FREEZE, summarize,
)
from nexus.seed.worker_div_confirm_study import public_covers_required_edges


def verify(payload, config, root=ROOT):
    if config.get("default_investigation_policy") != "fixed_boundary":
        raise ValueError("fixed_policy_not_default")
    if config.get("learned_ranking_promoted") or config.get("learning_research_resumed"):
        raise ValueError("learned_promoted")
    ids = {row["id"] for row in config["tasks"]}
    if ids & CLOSED_TASK_IDS:
        raise ValueError("closed_task_reused")
    hist = root / "artifacts/seed_harder_features/seed_harder_features.json"
    if hashlib.sha256(hist.read_bytes()).hexdigest() != HISTORICAL_HARDER_SHA256:
        raise ValueError("historical_harder_changed")
    if payload.get("historical_supplied_private_correct") != 1:
        raise ValueError("historical_1_of_5_lost")
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
    if len(inspect) != 1 or inspect[0].get("frozen_recipe") != WORKER_PROMPT_FREEZE:
        raise ValueError("inspect")
    if inspect[0].get("public_includes_missing_or_empty") is not True:
        raise ValueError("inspect_public_edges")
    audit = [row for row in records if row.get("category") == "audit"]
    if len(audit) != 1 or len(audit[0].get("tasks") or []) != 3:
        raise ValueError("audit")
    grid = config["expected_grid"]
    confirm = [row for row in records if row.get("category") == "confirm"]
    if not all(public_covers_required_edges(spec) for spec in config["tasks"]):
        raise ValueError("public_missing_not_present")
    if payload.get("blocked_step") is None:
        if len(confirm) != grid["confirm_cells"]:
            raise ValueError("confirm_count")
        if any(int(row.get("calls_charged") or 0) > MAX_COMPLETIONS for row in confirm):
            raise ValueError("over_budget")
    rebuilt = summarize(records, config)
    if rebuilt["historical_supplied_private_correct"] != 1:
        raise ValueError("summary_rewrote_history")
    if rebuilt["confirm_rows"] != payload["summary"]["confirm_rows"]:
        raise ValueError("summary_mismatch")
    if payload.get("historical_fingerprints") != historical_artifact_fingerprints(root):
        raise ValueError("historical_artifact_changed")
    return dict(
        valid=True, events=len(events),
        operations=dict(Counter(event.get("operation") for event in events)),
        grid=grid,
        historical_supplied_private_correct=1,
        learned_ranking_promoted=False, learning_research_resumed=False,
    )


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_sum_row_repair_confirm.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_sum_row_repair_confirm/seed_sum_row_repair_confirm.json"
    )
    main(target)
