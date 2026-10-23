"""Independent reconstruction of the six-area comparison. No new inference."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest
from nexus.seed.six_area_comparison import summarize
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints


def expected_episode_keys(config):
    keys = []
    for seed in config["seeds"]:
        for i in range(config["assessment_tasks"]):
            for method in config["methods"]:
                keys.append((seed, method, f"{seed}:assessment:{i}"))
        if config.get("out_of_grammar_tasks"):
            for method in config["methods"]:
                keys.append((seed, method, f"{seed}:assessment:oog"))
    return keys


def expected_coding_cells(config):
    return [(spec["id"], cond) for spec in config["coding"] for cond in config["coding_conditions"]]


def reconstruct_costs(records):
    rows = [r for r in records if r.get("kind") == "capability"
            and r.get("category") in {"coding", "reuse"}]
    generated = input_tokens = completions = 0
    wall = 0.0
    for row in rows:
        traces = row.get("model_trace") or []
        if not traces:
            generated += int(row.get("generated_tokens") or 0)
            input_tokens += int(row.get("input_tokens") or 0)
            wall += float(row.get("request_wall_s") or 0)
            completions += int(row.get("completions") or 0)
            continue
        row_gen = row_in = row_comp = 0
        row_wall = 0.0
        for item in traces:
            tel = item.get("telemetry") or {}
            row_gen += int(tel.get("generated_tokens") or 0)
            row_in += int(tel.get("input_tokens") or 0)
            row_wall += float(tel.get("request_wall_s") or 0)
            if item.get("completions"):
                row_comp += int(item["completions"])
            elif item.get("traces"):
                row_comp += len(item["traces"])
            elif item.get("inference_ran"):
                row_comp += 1
        generated += row_gen
        input_tokens += row_in
        wall += row_wall
        completions += row_comp
        if int(row.get("completions") or 0) != row_comp:
            raise ValueError("completion_count_mismatch:" + str(row.get("id")))
        if int(row.get("generated_tokens") or 0) != row_gen:
            raise ValueError("generated_token_mismatch:" + str(row.get("id")))
    return dict(completions=completions, generated_tokens=generated,
                input_tokens=input_tokens, request_wall_s=round(wall, 6))


def replay_final_patches(records, config):
    from nexus.seed.agent_loop_worker import run_worker_subprocess
    by_id = {spec["id"]: spec for spec in config["coding"]}
    later = config["reuse"]["assessment"]
    by_id[later["id"]] = later
    replayed = 0
    for row in records:
        if row.get("kind") != "capability" or row.get("category") not in {"coding", "reuse"}:
            continue
        spec = by_id.get(row.get("id"))
        if spec is None or not row.get("final_files"):
            continue
        replayed_private = run_worker_subprocess({
            "language": spec["language"],
            "files": row["final_files"],
            "cases": spec["assessment"],
        })
        saved = bool((row.get("private") or {}).get("all_passed"))
        if bool(replayed_private.get("all_passed")) != saved:
            raise ValueError("replay_private_mismatch:" + row["id"] + ":" + str(row.get("method")))
        replayed += 1
    return replayed


def verify(payload, config, root=ROOT, replay=True):
    required = (
        "id", "seeds", "methods", "coding_conditions", "coding", "reuse",
        "reasoning", "conversation", "expected_grid", "identified_only_if",
        "closed_coding_ids_excluded", "separate_improvements",
    )
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError("config_missing:" + ",".join(missing))
    if config["identified_only_if"] != "identified_within_catalogue":
        raise ValueError("identified_rule")
    overlap = {spec["id"] for spec in config["coding"]} & set(config["closed_coding_ids_excluded"])
    if overlap:
        raise ValueError("closed_coding_id_reused:" + ",".join(sorted(overlap)))
    if "patched" in config["reuse"] or "patched" in config["reuse"].get("assessment", {}):
        raise ValueError("handwritten_patched_forbidden")
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
    got = [(r["seed"], r["method"], r["task"]) for r in episodes]
    if sorted(got) != sorted(expected_episode_keys(config)):
        raise ValueError("assessment_grid_mismatch")
    grid = config["expected_grid"]
    if len(episodes) != grid["investigation_episodes"]:
        raise ValueError("investigation_episode_count")
    for ep in episodes:
        if ep.get("identified") and ep.get("identification_status") != "identified_within_catalogue":
            raise ValueError("identified_without_catalogue_status:" + ep["scope"])
        lock = next((r for r in records if r.get("kind") == "choice" and r.get("scope") == ep["scope"]), None)
        if lock is None:
            raise ValueError("missing_choice_before_assessment:" + ep["scope"])
    coding = [r for r in records if r.get("kind") == "capability" and r.get("category") == "coding"]
    if sorted((r["id"], r["method"]) for r in coding) != sorted(expected_coding_cells(config)):
        raise ValueError("coding_grid_mismatch")
    reuse = [r for r in records if r.get("category") == "reuse"]
    if len(reuse) != grid["reuse_cells"]:
        raise ValueError("reuse_count")
    if len([r for r in records if r.get("category") == "retention"]) != grid["retention_cells"]:
        raise ValueError("retention_count")
    if len([r for r in records if r.get("category") == "reasoning"]) != grid["reasoning_cells"]:
        raise ValueError("reasoning_count")
    if len([r for r in records if r.get("category") == "language"]) != grid["language_cells"]:
        raise ValueError("language_count")
    rebuilt = summarize(records, config)
    if rebuilt["methods"] != payload["summary"]["methods"]:
        raise ValueError("summary_table_mismatch")
    if rebuilt["learning_to_learn"] != payload["summary"].get("learning_to_learn"):
        raise ValueError("learning_to_learn_summary_mismatch")
    if rebuilt["reconstructed_costs"] != payload["summary"].get("reconstructed_costs"):
        raise ValueError("cost_summary_mismatch")
    costs = reconstruct_costs(records)
    if costs["completions"] != rebuilt["reconstructed_costs"]["completions"]:
        raise ValueError("reconstructed_completion_mismatch")
    fingerprints = historical_artifact_fingerprints(root)
    if payload.get("historical_fingerprints") != fingerprints:
        raise ValueError("historical_artifact_changed")
    if rebuilt.get("learning_to_learn_established"):
        raise ValueError("learning_to_learn_must_remain_unestablished_flag")
    if rebuilt["learning_to_learn"].get("established") and not (
        rebuilt["learning_to_learn"]["advantage_vs_fixed"]
        and rebuilt["learning_to_learn"]["remains_after_capsule_reset"]
        and rebuilt["learning_to_learn"]["disappears_when_shuffled"]
    ):
        raise ValueError("learning_to_learn_claimed_without_controls")
    replayed = replay_final_patches(records, config) if replay else 0
    return dict(
        valid=True,
        episodes=len(episodes),
        events=len(events),
        historical_fingerprints=fingerprints,
        operations=dict(Counter(e.get("operation") for e in events)),
        reconstructed_costs=costs,
        patches_replayed=replayed,
        grid=grid,
    )


def main(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    config = json.loads((ROOT / "configs/seed_six_area_comparison.json").read_text())
    out = verify(payload, config)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/seed_six_area_comparison/seed_six_area_comparison.json"
    main(target)
