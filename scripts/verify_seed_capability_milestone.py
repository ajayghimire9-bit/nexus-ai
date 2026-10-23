"""Independent reconstruction and patch replay for the capability milestone."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.agent_loop_worker import run_worker_subprocess
from nexus.seed.capability_evidence import digest
from nexus.seed.capability_milestone import CLOSED_TASK_IDS, summarize
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.operator_family import reconstruct_family_scores


def verify(payload, config, root=ROOT):
    if config.get("default_investigation_policy") != "fixed_boundary":
        raise ValueError("fixed_policy_not_default")
    if config.get("learned_policy_promoted"):
        raise ValueError("learned_promoted_in_config")
    ids = {config["token_task"]["id"], config["feature"]["id"]}
    ids.update(row["id"] for row in config["ranking"]["source"])
    ids.update(row["id"] for row in config["ranking"]["assessment"])
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
    grid = config["expected_grid"]
    if len([row for row in records if row.get("category") == "ranking_source"]) != grid["ranking_source_cells"]:
        raise ValueError("source_count")
    if len([row for row in records if row.get("category") == "ranking"]) != grid["ranking_cells"]:
        raise ValueError("ranking_count")
    if len([row for row in records if row.get("category") == "token"]) != grid["token_cells"]:
        raise ValueError("token_count")
    if len([row for row in records if row.get("category") == "feature"]) != grid["feature_cells"]:
        raise ValueError("feature_count")
    if len([row for row in records if row.get("category") == "language"]) != grid["language_cells"]:
        raise ValueError("language_count")
    budgets = {(row.get("interface"), row.get("max_tokens"), row.get("revision_budget"))
               for row in records if row.get("category") == "token"}
    if budgets != {("raw", 128, 2), ("raw", 512, 2), ("symbol", 128, 2), ("symbol", 512, 2)}:
        raise ValueError("token_cells_confounded")
    for row in records:
        if row.get("category") in {"ranking", "ranking_source"} and row.get("attempts") is not None:
            rebuilt_scores = reconstruct_family_scores(row["attempts"])
            if rebuilt_scores != row.get("reconstructed"):
                raise ValueError("reconstruct_mismatch:" + row["id"])
        if row.get("category") in {"ranking", "token", "feature"} and row.get("final_files") and row.get("id"):
            spec = None
            if row.get("category") == "feature":
                spec = config["feature"]
            elif row.get("category") == "token":
                spec = config["token_task"]
            else:
                spec = next((item for item in config["ranking"]["assessment"] if item["id"] == row["id"]), None)
            if spec and spec.get("assessment"):
                replayed = run_worker_subprocess({
                    "language": spec["language"],
                    "files": row["final_files"],
                    "cases": spec["assessment"],
                }, 10)
                saved = (row.get("replay") or {}).get("private") or {}
                if bool(replayed.get("all_passed")) != bool(saved.get("all_passed")):
                    raise ValueError("replay_mismatch:" + row["id"])
    rebuilt = summarize(records, config)
    if rebuilt["learned_policy_promoted"]:
        raise ValueError("learned_promoted_in_summary")
    if rebuilt["ranking"] != payload["summary"]["ranking"]:
        raise ValueError("summary_mismatch")
    if payload.get("historical_fingerprints") != historical_artifact_fingerprints(root):
        raise ValueError("historical_artifact_changed")
    if rebuilt.get("learning_to_learn_established"):
        raise ValueError("learning_to_learn_flag")
    return dict(
        valid=True, events=len(events),
        operations=dict(Counter(event.get("operation") for event in events)),
        grid=grid, learned_policy_promoted=False, ranking=rebuilt["ranking"],
    )


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_capability_milestone.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_capability_milestone/seed_capability_milestone.json"
    )
    main(target)
