"""Independent reconstruction of the widening/coding pilot. No new inference."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False, default=str).encode()).hexdigest()


def verify(payload, config, root=ROOT):
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
    episodes = [r for r in records if r.get("kind") == "episode"]
    keys = [(r["seed"], r["method"], r["task"]) for r in episodes]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate_episodes")
    locks = [r for r in records if r.get("kind") == "choice"]
    for ep in episodes:
        lock = next((r for r in locks if r.get("scope") == ep["scope"]), None)
        if lock is None:
            raise ValueError("missing_choice_before_assessment:" + ep["scope"])
        lock_idx = records.index(lock)
        assess = [i for i, r in enumerate(records)
                  if r.get("scope") == ep["scope"] and r.get("kind") == "execution"
                  and r.get("operation", "").startswith("assessment")]
        if assess and min(assess) < lock_idx:
            raise ValueError("assessment_before_choice:" + ep["scope"])
    from nexus.seed.capability_widening_coding import summarize, historical_artifact_fingerprints
    rebuilt = summarize(records, config)
    if rebuilt["methods"] != payload["summary"]["methods"]:
        raise ValueError("summary_table_mismatch")
    fingerprints = historical_artifact_fingerprints(root)
    if payload.get("historical_fingerprints") != fingerprints:
        raise ValueError("historical_artifact_changed")
    forged = dict(payload["summary"])
    forged_methods = dict(forged["methods"])
    if forged_methods:
        first = next(iter(forged_methods))
        row = dict(forged_methods[first])
        row["identified"] = row.get("identified", 0) + 99
        forged_methods[first] = row
        forged["methods"] = forged_methods
        if summarize(records, config)["methods"] == forged["methods"]:
            raise ValueError("forged_summary_accepted")
    return dict(valid=True, episodes=len(episodes), events=len(events),
                historical_fingerprints=fingerprints,
                operations=dict(Counter(e.get("operation") for e in events)))


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_capability_widening_coding.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/seed_capability_widening_coding/seed_capability_widening_coding.json"
    main(target)
