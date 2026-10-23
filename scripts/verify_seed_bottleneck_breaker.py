"""Independent reconstruction and tamper-rejecting verifier for seed-bottleneck-breaker-1."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.bottleneck_breaker import summarize  # noqa: E402
from nexus.seed.capability_evidence import digest  # noqa: E402
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints  # noqa: E402


def verify(payload: dict, config: dict, root: Path = ROOT) -> dict:
    if config.get("default_investigation_policy") != "fixed_boundary":
        raise ValueError("fixed_policy_not_default")
    if config.get("learned_policy_promoted"):
        raise ValueError("learned_promoted_in_config")

    # 1. Verify disjointness from closed coding IDs and between source/assessment meta tasks
    closed_ids = set(config.get("closed_coding_ids_excluded") or [])
    coding_ids = {t["id"] for t in config.get("coding_tasks") or []}
    ttc_ids = {t["id"] for t in config.get("unseen_reasoning_tasks") or []}
    meta_src_ids = {t["id"] for t in config["meta_learning"]["source_tasks"]}
    meta_eval_ids = {t["id"] for t in config["meta_learning"]["assessment_tasks"]}
    all_new_ids = coding_ids | ttc_ids | meta_src_ids | meta_eval_ids
    if all_new_ids & closed_ids:
        raise ValueError("closed_task_id_overlap")
    if meta_src_ids & meta_eval_ids:
        raise ValueError("meta_source_assessment_overlap")

    # 2. Verify cryptographic SHA-256 EventMeter chain
    records = payload["records"]
    events = [row for row in records if row.get("kind") == "execution"]
    previous = "0" * 64
    for i, event in enumerate(events, 1):
        obj = dict(event)
        claimed = obj.pop("hash")
        if claimed != digest(obj) or event["index"] != i or event["previous"] != previous:
            raise ValueError("event_chain_tampered")
        previous = claimed

    # 3. Verify audit manifest
    manifest = [row for row in records if row.get("kind") == "audit_manifest"]
    if len(manifest) != 1 or manifest[0].get("config_hash") != digest(config):
        raise ValueError("config_manifest_mismatch")

    # 4. Verify expected grid counts
    grid = config["expected_grid"]
    ablation_rows = [r for r in records if r.get("category") == "coding_ablation"]
    ttc_rows = [r for r in records if r.get("category") == "unseen_ttc"]
    lang_rows = [r for r in records if r.get("category") == "language"]
    meta_src_rows = [r for r in records if r.get("kind") == "meta_train_episode"]
    meta_eval_rows = [r for r in records if r.get("kind") == "meta_eval_episode"]

    if len(ablation_rows) != grid["coding_ablation_cells"]:
        raise ValueError("coding_ablation_count_mismatch")
    if len(ttc_rows) != grid["unseen_ttc_cells"]:
        raise ValueError("unseen_ttc_count_mismatch")
    if len(lang_rows) != grid["language_cells"]:
        raise ValueError("language_count_mismatch")
    if len(meta_src_rows) != grid["meta_source_episodes"]:
        raise ValueError("meta_source_count_mismatch")
    if len(meta_eval_rows) != grid["meta_assessment_cells"]:
        raise ValueError("meta_assessment_count_mismatch")

    # 5. Reconstruct every meta_learning episode's worker_evaluations directly from metered events
    event_scopes = Counter(ev.get("scope", "").rsplit(":cand:", 1)[0] for ev in events if ":cand:" in str(ev.get("scope", "")))
    for row in meta_eval_rows:
        prefix = f"meta_eval:{row['condition']}:{row['id']}"
        metered_evals = int(event_scopes.get(prefix, 0))
        if int(row.get("worker_evaluations", -1)) != metered_evals:
            raise ValueError(f"unmetered_or_forged_worker_evaluations:{prefix}")

    # 6. Independently rebuild summary from raw records and compare
    rebuilt = summarize(records, config)
    claimed_summary = payload.get("summary") or {}
    for section in (
        "proposer_and_capacity_ablation",
        "unseen_test_time_compute",
        "grounded_conversation",
        "diagnostic_meta_learning",
        "reconstructed_costs",
    ):
        if rebuilt.get(section) != claimed_summary.get(section):
            raise ValueError(f"summary_mismatch:{section}")

    # 7. Verify historical fingerprints untouched
    if payload.get("historical_fingerprints") != historical_artifact_fingerprints(root):
        raise ValueError("historical_artifact_changed")

    return dict(
        valid=True,
        events=len(events),
        operations=dict(Counter(event.get("operation") for event in events)),
        grid=grid,
        learned_policy_promoted=False,
        process_level_learning_to_learn_established=rebuilt["diagnostic_meta_learning"][
            "process_level_learning_to_learn_established"
        ],
        diagnostic_meta_learning=rebuilt["diagnostic_meta_learning"],
    )


def main(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_bottleneck_breaker.json").read_text(encoding="utf-8"))
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "artifacts/seed_bottleneck_breaker/seed_bottleneck_breaker.json"
    )
    main(target)
