"""Independent reconstruction of the boundary-state-workflow pilot."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.reliable_workflow import CLOSED_TASK_IDS, summarize


def verify(payload, config, root=ROOT):
    if config.get("default_investigation_policy") != "fixed_boundary":
        raise ValueError("fixed_policy_not_default")
    if config.get("learned_ranking_promoted") or config.get("learned_policy_promoted"):
        raise ValueError("learned_promoted_in_config")
    ids = {row["id"] for row in config["boundary"]}
    ids.add(config["workflow"]["development"]["id"])
    ids.add(config["workflow"]["fresh"]["id"])
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
    if manifest[0].get("learned_ranking_promoted"):
        raise ValueError("learned_promoted_in_manifest")
    grid = config["expected_grid"]
    if len([row for row in records if row.get("category") == "boundary"]) != grid["boundary_cells"]:
        raise ValueError("boundary_count")
    if len([row for row in records if row.get("category") == "workflow"]) != grid["workflow_cells"]:
        raise ValueError("workflow_count")
    if len([row for row in records if row.get("category") == "language"]) != grid["language_cells"]:
        raise ValueError("language_count")
    rebuilt = summarize(records, config)
    if rebuilt["learned_ranking_promoted"] or rebuilt["learned_policy_promoted"]:
        raise ValueError("learned_promoted_in_summary")
    if rebuilt["boundary"] != payload["summary"]["boundary"]:
        raise ValueError("summary_mismatch")
    if payload.get("historical_fingerprints") != historical_artifact_fingerprints(root):
        raise ValueError("historical_artifact_changed")
    if rebuilt.get("learning_to_learn_established"):
        raise ValueError("learning_to_learn_flag")
    return dict(
        valid=True, events=len(events),
        operations=dict(Counter(event.get("operation") for event in events)),
        grid=grid, learned_ranking_promoted=False,
    )


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_boundary_state_workflow.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_boundary_state_workflow/seed_boundary_state_workflow.json"
    )
    main(target)
