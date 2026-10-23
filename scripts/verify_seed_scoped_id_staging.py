"""Independent reconstruction of the scoped-id / staging pilot. No new inference."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

STATUSES = {
    "identified_within_catalogue", "unique_among_checked", "ambiguous",
    "no_checked_candidate_fits", "catalogue_inconsistent",
    "legacy_shortlist_stop", "legacy_empty_shortlist_fallback",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False, default=str).encode()).hexdigest()


def verify(payload, config, root=ROOT):
    required = (
        "id", "seeds", "source_tasks", "assessment_tasks", "methods",
        "controller", "coding", "repair_transfer", "predeclared_families",
        "identified_only_if", "carried_used_s", "wall_s",
    )
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError("config_missing:" + ",".join(missing))
    if config["identified_only_if"] != "identified_within_catalogue":
        raise ValueError("identified_rule")
    if set(config["predeclared_families"]) != {
        "comparison_boundary", "missing_function", "null_default",
    }:
        raise ValueError("families_must_be_predeclared")
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
        if ep.get("identification_status") not in STATUSES:
            raise ValueError("unknown_identification_status:" + str(ep.get("identification_status")))
        if ep.get("identified") and ep.get("identification_status") != "identified_within_catalogue":
            raise ValueError("identified_without_catalogue_status:" + ep["scope"])
        if ep.get("identification_status") == "unique_among_checked" and ep.get("identified"):
            raise ValueError("unique_among_checked_counted_as_identified:" + ep["scope"])
        if ep.get("identification_status") == "catalogue_inconsistent" and ep.get("unchecked_remaining"):
            raise ValueError("inconsistent_with_remainder:" + ep["scope"])
        lock = next((r for r in locks if r.get("scope") == ep["scope"]), None)
        if lock is None:
            raise ValueError("missing_choice_before_assessment:" + ep["scope"])
        lock_idx = records.index(lock)
        assess = [i for i, r in enumerate(records)
                  if r.get("scope") == ep["scope"] and r.get("kind") == "execution"
                  and r.get("operation", "").startswith("assessment")]
        if assess and min(assess) < lock_idx:
            raise ValueError("assessment_before_choice:" + ep["scope"])
    from nexus.seed.scoped_id_staging import summarize
    from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
    rebuilt = summarize(records, config)
    if rebuilt["methods"] != payload["summary"]["methods"]:
        raise ValueError("summary_table_mismatch")
    if rebuilt.get("repair_transfer") != payload["summary"].get("repair_transfer"):
        raise ValueError("repair_transfer_mismatch")
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
    relabeled = [ep for ep in episodes if ep.get("identification_status") == "unique_among_checked"]
    if any(ep.get("identified") for ep in relabeled):
        raise ValueError("relabel_identified")
    coding = [r for r in records if r.get("kind") == "capability" and r.get("category") == "coding"]
    for row in coding:
        if row.get("method") == "local_model_per_file" and row.get("model_generated_per_file") is not True:
            raise ValueError("per_file_not_generated:" + row["id"])
        if row.get("method") == "repair_schema_transfer" and not row.get("acquisition_charged"):
            raise ValueError("repair_acquisition_uncharged:" + row["id"])
        traces = row.get("model_trace") or []
        if any(trace.get("truncation_claimed_as_cause") for trace in traces):
            raise ValueError("truncation_blamed:" + row["id"])
    return dict(
        valid=True,
        episodes=len(episodes),
        events=len(events),
        historical_fingerprints=fingerprints,
        operations=dict(Counter(e.get("operation") for e in events)),
        identified_only_if="identified_within_catalogue",
    )


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_scoped_id_staging.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/seed_scoped_id_staging/seed_scoped_id_staging.json"
    main(target)
