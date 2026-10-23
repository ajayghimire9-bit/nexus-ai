"""Independent reconstruction of the contract / two-stage grid."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.contract_revision_study import CLOSED_TASK_IDS, FORMAT, summarize
from nexus.seed.input_contract import MAX_COMPLETIONS, PROMPT_VARIANTS, choose_best_variant
from nexus.seed.public_failure import operator_hint_present


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
    if len(inspect) != 1:
        raise ValueError("inspect")
    if inspect[0].get("contract_has_signature") is not True:
        raise ValueError("contract_signature")
    if inspect[0].get("existing_has_signature") is not True:
        raise ValueError("existing_gained_signature")
    if inspect[0].get("max_completions") != MAX_COMPLETIONS:
        raise ValueError("max_completions")
    grid = config["expected_grid"]
    contract = [row for row in records if row.get("category") == "contract"]
    e2e = [row for row in records if row.get("category") == "e2e"]
    if payload.get("blocked_step") is None:
        if len(contract) != grid["contract_cells"]:
            raise ValueError("contract_count")
        if len(e2e) != grid["e2e_cells"]:
            raise ValueError("e2e_count")
        if {row.get("prompt_variant") for row in contract} != set(PROMPT_VARIANTS):
            raise ValueError("variants_missing")
        if any(row.get("wire_discovery") for row in contract):
            raise ValueError("contract_wired")
        if any(not row.get("wire_discovery") for row in e2e):
            raise ValueError("e2e_not_wired")
        if any(row.get("format") != FORMAT for row in contract + e2e):
            raise ValueError("not_json_body")
        if any(int(row.get("calls_charged") or 0) > MAX_COMPLETIONS for row in contract + e2e):
            raise ValueError("over_budget")
        half = [row for row in contract if row.get("model") == "qwen05"]
        choice = next(row for row in records if row.get("category") == "choice")
        rebuilt = choose_best_variant(half)
        if choice.get("best_variant") != rebuilt:
            raise ValueError("best_variant_mismatch")
        if any(row.get("prompt_variant") != rebuilt for row in e2e):
            raise ValueError("e2e_not_best_variant")
        if any(row.get("operator_hint_in_revision") for row in contract + e2e):
            raise ValueError("operator_hint")
        for row in contract + e2e:
            for trace in row.get("traces") or []:
                if operator_hint_present(trace.get("user_prompt") or ""):
                    raise ValueError("operator_in_prompt")
    rebuilt = summarize(records, config)
    if rebuilt["learned_ranking_promoted"] or rebuilt["learning_research_resumed"]:
        raise ValueError("learned_promoted_in_summary")
    if rebuilt["contract_rows"] != payload["summary"]["contract_rows"]:
        raise ValueError("summary_mismatch")
    if payload.get("historical_fingerprints") != historical_artifact_fingerprints(root):
        raise ValueError("historical_artifact_changed")
    return dict(
        valid=True, events=len(events),
        operations=dict(Counter(event.get("operation") for event in events)),
        grid=grid, best_variant=rebuilt.get("best_variant"),
        learned_ranking_promoted=False, learning_research_resumed=False,
    )


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_contract_two_stage.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_contract_two_stage/seed_contract_two_stage.json"
    )
    main(target)
