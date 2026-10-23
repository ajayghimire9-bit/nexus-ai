"""Independent reconstruction of the interrupt/transfer pilot."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.interrupt_transfer import summarize


def verify(payload, config, root=ROOT):
    if config.get("default_investigation_policy") != "fixed_boundary":
        raise ValueError("fixed_policy_not_default")
    if config.get("learned_policy_promoted"):
        raise ValueError("learned_promoted_in_config")
    records = payload["records"]
    events = [r for r in records if r.get("kind") == "execution"]
    previous = "0" * 64
    for i, event in enumerate(events, 1):
        obj = dict(event)
        claimed = obj.pop("hash")
        if claimed != digest(obj) or event["index"] != i or event["previous"] != previous:
            raise ValueError("event_chain")
        previous = claimed
    manifest = [r for r in records if r.get("kind") == "audit_manifest"]
    if len(manifest) != 1 or manifest[0]["config_hash"] != digest(config):
        raise ValueError("config_manifest")
    if manifest[0].get("learned_policy_promoted"):
        raise ValueError("learned_promoted_in_manifest")
    grid = config["expected_grid"]
    episodes = [r for r in records if r.get("kind") == "episode"]
    if len(episodes) != grid["investigation_episodes"]:
        raise ValueError("investigation_count")
    if len([r for r in records if r.get("category") == "coding"]) != grid["coding_cells"]:
        raise ValueError("coding_count")
    if len([r for r in records if r.get("category") == "transfer"]) != grid["transfer_cells"]:
        raise ValueError("transfer_count")
    if len([r for r in records if r.get("category") == "language"]) != grid["language_cells"]:
        raise ValueError("language_count")
    rebuilt = summarize(records, config)
    if rebuilt["learned_policy_promoted"]:
        raise ValueError("learned_promoted_in_summary")
    if rebuilt["methods"] != payload["summary"]["methods"]:
        raise ValueError("summary_mismatch")
    if payload.get("historical_fingerprints") != historical_artifact_fingerprints(root):
        raise ValueError("historical_artifact_changed")
    if rebuilt.get("learning_to_learn_established"):
        raise ValueError("learning_to_learn_flag")
    return dict(valid=True, episodes=len(episodes), events=len(events),
                operations=dict(Counter(e.get("operation") for e in events)),
                grid=grid, learned_policy_promoted=False)


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_interrupt_transfer.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/seed_interrupt_transfer/seed_interrupt_transfer.json"
    main(target)
