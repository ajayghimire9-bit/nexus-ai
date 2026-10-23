"""Independent reconstruction of the interface-repair development grid."""
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
from nexus.seed.interface_repair_study import (
    CLOSED_TASK_IDS, HISTORICAL_HARDER_SHA256, WORKER_PROMPT_FREEZE,
    public_covers_varied, replay_final, summarize,
)


def verify(
    payload, config, root=ROOT, *,
    closed=CLOSED_TASK_IDS, freeze=WORKER_PROMPT_FREEZE,
    cover=public_covers_varied, summarize_fn=summarize, replay_fn=replay_final,
):
    if config.get("default_investigation_policy") != "fixed_boundary":
        raise ValueError("fixed_policy_not_default")
    if config.get("learned_ranking_promoted") or config.get("learning_research_resumed"):
        raise ValueError("learned_promoted")
    ids = [row["id"] for row in config["tasks"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_task")
    if set(ids) & closed:
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
    if len(inspect) != 1 or inspect[0].get("frozen_recipe") != freeze:
        raise ValueError("inspect")
    audit = [row for row in records if row.get("category") == "audit"]
    if len(audit) != 1 or len(audit[0].get("tasks") or []) != 3:
        raise ValueError("audit")
    grid = config["expected_grid"]
    confirm = [row for row in records if row.get("category") == "confirm"]
    methods = [row.get("method") for row in confirm]
    if methods and set(methods) != set(grid["methods"]):
        raise ValueError("method_coverage")
    if not all(cover(spec) for spec in config["tasks"]):
        raise ValueError("public_missing_not_present")
    if payload.get("blocked_step") is None:
        if len(confirm) != grid["confirm_cells"]:
            raise ValueError("confirm_count")
        if len({row["id"] for row in confirm}) != len(confirm):
            raise ValueError("duplicate_confirm")
        if {row["id"] for row in confirm} != set(ids):
            raise ValueError("task_coverage")
        if any(int(row.get("calls_charged") or 0) > MAX_COMPLETIONS for row in confirm):
            raise ValueError("over_budget")
        specs = {spec["id"]: spec for spec in config["tasks"]}
        completes = [row for row in events if row.get("operation") == "complete"]
        charged = sum(int(row.get("calls_charged") or 0) for row in confirm)
        if charged != len(completes):
            raise ValueError("completion_count_mismatch")
        for row in confirm:
            matched = [
                event for event in completes
                if str(event.get("identity") or "").startswith(row["id"] + ":")
            ]
            if len(matched) != int(row.get("calls_charged") or 0):
                raise ValueError("completion_chain_mismatch:" + row["id"])
        for row in confirm:
            replayed = replay_fn(row, specs[row["id"]])
            if bool(row.get("public_passed")) != replayed["public_all_passed"]:
                raise ValueError("public_replay_mismatch:" + row["id"])
            if bool(row.get("semantic_correct")) != replayed["private_all_passed"]:
                raise ValueError("private_replay_mismatch:" + row["id"])
    rebuilt = summarize_fn(records, config)
    if rebuilt["historical_supplied_private_correct"] != 1:
        raise ValueError("summary_rewrote_history")
    if rebuilt["confirm_rows"] != payload["summary"]["confirm_rows"]:
        raise ValueError("summary_mismatch")
    if payload.get("historical_fingerprints") != historical_artifact_fingerprints(root):
        raise ValueError("historical_artifact_changed")
    if payload.get("summary", {}).get("learning_to_learn_established"):
        raise ValueError("learning_flag")
    return dict(
        valid=True, events=len(events),
        operations=dict(Counter(event.get("operation") for event in events)),
        grid=grid,
        historical_supplied_private_correct=1,
        learned_ranking_promoted=False, learning_research_resumed=False,
    )


def _bundle(study_id):
    if study_id == "seed-slot3-copy-confirm-1":
        from nexus.seed.slot3_copy_study import (
            CLOSED_TASK_IDS as closed, WORKER_PROMPT_FREEZE as freeze,
            covers_varied as cover, replay_final as replay_fn, summarize as summarize_fn,
        )
        config = json.loads((ROOT / "configs/seed_slot3_copy_confirm.json").read_text())
        return config, dict(closed=closed, freeze=freeze, cover=cover, summarize_fn=summarize_fn, replay_fn=replay_fn)
    if study_id == "seed-slot3-repair-confirm-1":
        from nexus.seed.slot3_repair_study import (
            CLOSED_TASK_IDS as closed, WORKER_PROMPT_FREEZE as freeze,
            public_covers_varied as cover, replay_final as replay_fn, summarize as summarize_fn,
        )
        config = json.loads((ROOT / "configs/seed_slot3_repair_confirm.json").read_text())
        return config, dict(closed=closed, freeze=freeze, cover=cover, summarize_fn=summarize_fn, replay_fn=replay_fn)
    config = json.loads((ROOT / "configs/seed_interface_repair_confirm.json").read_text())
    return config, {}


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config, extras = _bundle(payload.get("study_id"))
    out = verify(payload, config, **extras)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_interface_repair_confirm/seed_interface_repair_confirm.json"
    )
    main(target)
