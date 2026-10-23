"""Independent reconstruction of the guarded-template reuse pilot."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.guarded_reuse import CLOSED_TASK_IDS, summarize


def verify(payload, config, root=ROOT):
    if config.get("default_investigation_policy") != "fixed_boundary":
        raise ValueError("fixed_policy_not_default")
    if config.get("learned_policy_promoted"):
        raise ValueError("learned_promoted_in_config")
    if not config.get("equally_guarded_template"):
        raise ValueError("template_not_guarded")
    later_ids = {row["id"] for row in config["transfer"]["later"]}
    if later_ids & CLOSED_TASK_IDS or config["transfer"]["source"]["id"] in CLOSED_TASK_IDS:
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
    if manifest[0].get("learned_policy_promoted"):
        raise ValueError("learned_promoted_in_manifest")
    grid = config["expected_grid"]
    if len([row for row in records if row.get("category") == "transfer_source"]) != grid["transfer_source_cells"]:
        raise ValueError("source_count")
    if len([row for row in records if row.get("category") == "transfer"]) != grid["transfer_cells"]:
        raise ValueError("transfer_count")
    roles = {row["reuse_role"] for row in config["transfer"]["later"]}
    if roles != {"same_repair", "opposite", "unrelated", "clarification"}:
        raise ValueError("reuse_roles")
    rebuilt = summarize(records, config)
    if rebuilt["learned_policy_promoted"]:
        raise ValueError("learned_promoted_in_summary")
    if rebuilt["memory_counts"] != payload["summary"]["memory_counts"]:
        raise ValueError("summary_mismatch")
    if payload.get("historical_fingerprints") != historical_artifact_fingerprints(root):
        raise ValueError("historical_artifact_changed")
    if rebuilt.get("learning_to_learn_established"):
        raise ValueError("learning_to_learn_flag")
    return dict(
        valid=True, events=len(events),
        operations=dict(Counter(event.get("operation") for event in events)),
        grid=grid, learned_policy_promoted=False,
        memory_counts=rebuilt["memory_counts"],
        template_counts=rebuilt["template_counts"],
        memory_advantage_correct_reuse=rebuilt["memory_advantage_correct_reuse"],
    )


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_guarded_template_reuse.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_guarded_template_reuse/seed_guarded_template_reuse.json"
    )
    main(target)
