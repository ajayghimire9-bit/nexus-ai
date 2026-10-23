"""Independent reconstruction of the chat-template repair grid."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.chat_template import PROMPT_STYLES, choose_best_style
from nexus.seed.chat_template_study import CLOSED_TASK_IDS, FORMAT, summarize
from nexus.seed.public_failure import EQUALITY_FAILURE, operator_hint_present
from nexus.seed.target_discovery import discover_edit_target, score_discovery


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
    if inspect[0].get("user_equals_raw") is not True:
        raise ValueError("user_not_equal_raw")
    if inspect[0].get("format") != FORMAT:
        raise ValueError("format")
    if inspect[0].get("equality_failure") != EQUALITY_FAILURE:
        raise ValueError("equality_sentence")
    if inspect[0].get("operator_supplied") is not False:
        raise ValueError("operator_supplied")
    if operator_hint_present(inspect[0].get("chatml_prompt") or ""):
        raise ValueError("operator_in_first_prompt")
    grid = config["expected_grid"]
    discovery = [row for row in records if row.get("category") == "discovery"]
    if len(discovery) != grid["discovery_cells"]:
        raise ValueError("discovery_count")
    for spec in config["tasks"]:
        rebuilt = score_discovery(
            discover_edit_target(spec["request"], spec["files"], spec.get("docs") or []),
            spec["gold_target"],
        )
        saved = next(row for row in discovery if row["id"] == spec["id"])
        if saved.get("target_correct") != rebuilt["target_correct"]:
            raise ValueError("discovery_mismatch:" + spec["id"])
        if saved.get("used_public_tests"):
            raise ValueError("discovery_used_public")
    template = [row for row in records if row.get("category") == "template"]
    fresh = [row for row in records if row.get("category") == "fresh"]
    if payload.get("blocked_step") is None:
        if len(template) != grid["template_cells"]:
            raise ValueError("template_count")
        if len(fresh) != grid["fresh_cells"]:
            raise ValueError("fresh_count")
        if {row.get("prompt_style") for row in template} != set(PROMPT_STYLES):
            raise ValueError("styles_missing")
        half = [row for row in template if row.get("model") == "qwen05"]
        choice = next(row for row in records if row.get("category") == "choice")
        rebuilt_best = choose_best_style(half)
        if choice.get("best_style") != rebuilt_best:
            raise ValueError("best_style_mismatch")
        if any(row.get("prompt_style") != rebuilt_best for row in fresh):
            raise ValueError("fresh_not_best_style")
        if any(row.get("format") != FORMAT for row in template + fresh):
            raise ValueError("not_json_body")
        replace = [row for row in template if row.get("id") == "py_score_three_point" and row.get("equality_failure_in_revision")]
        if replace and any(row.get("operator_hint_in_revision") for row in replace):
            raise ValueError("operator_hint_on_revision")
    rebuilt = summarize(records, config)
    if rebuilt["learned_ranking_promoted"] or rebuilt["learning_research_resumed"]:
        raise ValueError("learned_promoted_in_summary")
    if rebuilt["template_rows"] != payload["summary"]["template_rows"]:
        raise ValueError("summary_mismatch")
    if payload.get("historical_fingerprints") != historical_artifact_fingerprints(root):
        raise ValueError("historical_artifact_changed")
    return dict(
        valid=True, events=len(events),
        operations=dict(Counter(event.get("operation") for event in events)),
        grid=grid, best_style=rebuilt.get("best_style"),
        learned_ranking_promoted=False, learning_research_resumed=False,
    )


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_chat_template_repair.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_chat_template_repair/seed_chat_template_repair.json"
    )
    main(target)
