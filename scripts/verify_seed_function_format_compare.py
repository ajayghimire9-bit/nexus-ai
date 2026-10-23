"""Independent reconstruction of the function-format comparison."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.function_format import FORMATS, choose_best_format
from nexus.seed.function_format_study import CLOSED_TASK_IDS, summarize


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
    if len(inspect) != 1 or inspect[0].get("chat_template") is not None:
        raise ValueError("inspect")
    if inspect[0].get("function_described_as") != "executable_python_source":
        raise ValueError("function_not_described")
    grid = config["expected_grid"]
    half = [row for row in records if row.get("category") == "format" and row.get("model") == "qwen05"]
    coder = [row for row in records if row.get("category") == "format" and row.get("model") == "coder15"]
    if len(half) != grid["format_cells"]:
        raise ValueError("format_count")
    if {row.get("format") for row in half} != set(FORMATS):
        raise ValueError("formats_missing")
    choice = next(row for row in records if row.get("category") == "choice")
    rebuilt_best = choose_best_format(half)
    if choice.get("best_format") != rebuilt_best:
        raise ValueError("best_format_mismatch")
    if payload.get("blocked_step") is None and len(coder) != grid["coder_cells"]:
        raise ValueError("coder_count")
    if any(row.get("format") != rebuilt_best for row in coder):
        raise ValueError("coder_not_best_format")
    rebuilt = summarize(records, config)
    if rebuilt["learned_ranking_promoted"] or rebuilt["learning_research_resumed"]:
        raise ValueError("learned_promoted_in_summary")
    if rebuilt["format_rows"] != payload["summary"]["format_rows"]:
        raise ValueError("summary_mismatch")
    if payload.get("historical_fingerprints") != historical_artifact_fingerprints(root):
        raise ValueError("historical_artifact_changed")
    return dict(
        valid=True, events=len(events),
        operations=dict(Counter(event.get("operation") for event in events)),
        grid=grid, best_format=rebuilt_best,
        learned_ranking_promoted=False, learning_research_resumed=False,
    )


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_function_format_compare.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else ROOT / "artifacts/seed_function_format_compare/seed_function_format_compare.json"
    )
    main(target)
