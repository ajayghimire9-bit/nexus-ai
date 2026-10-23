"""Independent reconstruction of the scoped-id / staging pilot. No new inference."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexus.seed.capability_evidence import digest

STATUSES = {
    "identified_within_catalogue", "unique_among_checked", "ambiguous",
    "no_checked_candidate_fits", "catalogue_inconsistent",
    "legacy_shortlist_stop", "legacy_empty_shortlist_fallback",
}


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
    return [
        (spec["id"], method)
        for spec in config["coding"]
        for method in config["coding_methods"]
        if method != "repair_schema_transfer"
    ]


def reconstruct_costs(records):
    coding = [r for r in records if r.get("kind") == "capability" and r.get("category") == "coding"]
    model_rows = [r for r in coding if r.get("method") in {"local_model_single", "local_model_per_file"}]
    generated = input_tokens = completions = 0
    wall = 0.0
    for row in model_rows:
        traces = row.get("model_trace") or []
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
    return dict(
        completions=completions,
        generated_tokens=generated,
        input_tokens=input_tokens,
        request_wall_s=round(wall, 6),
    )


def replay_final_patches(records, config):
    from nexus.seed.agent_loop_worker import run_worker_subprocess
    by_id = {spec["id"]: spec for spec in config["coding"]}
    replayed = 0
    for row in records:
        if row.get("kind") != "capability" or row.get("category") != "coding":
            continue
        if row.get("method") == "repair_schema_transfer":
            spec = by_id.get(row.get("assessment_id"))
        else:
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
        "id", "seeds", "source_tasks", "assessment_tasks", "methods",
        "controller", "coding", "repair_transfer", "predeclared_families",
        "identified_only_if", "carried_used_s", "wall_s", "expected_grid",
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
    coding_by_id = {spec["id"]: spec for spec in config["coding"]}
    for pair in config["repair_transfer"]:
        if "patched" in pair or "patched" in (pair.get("source") or {}):
            raise ValueError("handwritten_patched_forbidden")
        if pair.get("source_id") not in coding_by_id or pair.get("assessment_id") not in coding_by_id:
            raise ValueError("repair_pair_missing")
        if coding_by_id[pair["source_id"]].get("role") != "source":
            raise ValueError("repair_source_not_source_role")
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
    expected_eps = expected_episode_keys(config)
    got_eps = [(r["seed"], r["method"], r["task"]) for r in episodes]
    if sorted(got_eps) != sorted(expected_eps):
        raise ValueError("assessment_grid_mismatch")
    if len(episodes) != config["expected_grid"]["investigation_episodes"]:
        raise ValueError("investigation_episode_count")
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
    coding = [r for r in records if r.get("kind") == "capability" and r.get("category") == "coding"]
    coding_cells = [(r["id"], r.get("method")) for r in coding if r.get("method") != "repair_schema_transfer"]
    if sorted(coding_cells) != sorted(expected_coding_cells(config)):
        raise ValueError("coding_grid_mismatch")
    transfer = [r for r in coding if r.get("method") == "repair_schema_transfer"]
    if len(transfer) != config["expected_grid"]["repair_transfer_cells"]:
        raise ValueError("repair_transfer_count")
    language = [r for r in records if r.get("kind") == "capability" and r.get("category") == "language"]
    if len(language) != config["expected_grid"]["conversation_cells"]:
        raise ValueError("conversation_count")
    from nexus.seed.scoped_id_staging import summarize
    from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
    rebuilt = summarize(records, config)
    if rebuilt["methods"] != payload["summary"]["methods"]:
        raise ValueError("summary_table_mismatch")
    if rebuilt.get("repair_transfer") != payload["summary"].get("repair_transfer"):
        raise ValueError("repair_transfer_mismatch")
    costs = reconstruct_costs(records)
    if rebuilt.get("reconstructed_costs") != payload["summary"].get("reconstructed_costs"):
        raise ValueError("cost_summary_mismatch")
    if costs["completions"] != rebuilt["reconstructed_costs"]["completions"]:
        raise ValueError("reconstructed_completion_mismatch")
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
    for row in coding:
        if row.get("method") == "local_model_per_file":
            if row.get("model_generated_per_file") is not True:
                raise ValueError("per_file_not_generated:" + row["id"])
            spec = next(s for s in config["coding"] if s["id"] == row["id"])
            expected_n = len(spec["files"])
            traces = []
            for item in row.get("model_trace") or []:
                traces.extend(item.get("traces") or [])
            if traces and len(traces) != expected_n:
                raise ValueError("per_file_completion_count:" + row["id"])
            if traces and any(
                t.get("prompt_file_count") not in {None, expected_n}
                for t in traces
            ):
                raise ValueError("per_file_isolated_prompt:" + row["id"])
            later = traces[1:] if len(traces) > 1 else []
            if later and any(t.get("prior_staged") for t in later) and not any(
                t.get("used_prior_staged_context") for t in later
            ):
                raise ValueError("per_file_missing_prior_context:" + row["id"])
            for trace in traces:
                if not trace.get("used_prior_staged_context"):
                    continue
                excerpt = trace.get("prompt_excerpt") or ""
                for src in (trace.get("prior_staged_excerpts") or {}).values():
                    snippet = (src or "").strip()[:80]
                    if snippet and excerpt and snippet not in excerpt:
                        raise ValueError("per_file_prompt_missing_prior_content:" + row["id"])
        if row.get("method") == "repair_schema_transfer":
            if not row.get("acquisition_charged"):
                raise ValueError("repair_acquisition_uncharged:" + row["id"])
            if "template_private" not in row or "none_private" not in row:
                raise ValueError("repair_baselines_missing:" + row["id"])
        traces = row.get("model_trace") or []
        if any(trace.get("truncation_claimed_as_cause") for trace in traces):
            raise ValueError("truncation_blamed:" + row["id"])
    replayed = replay_final_patches(records, config) if replay else 0
    return dict(
        valid=True,
        episodes=len(episodes),
        events=len(events),
        historical_fingerprints=fingerprints,
        operations=dict(Counter(e.get("operation") for e in events)),
        identified_only_if="identified_within_catalogue",
        reconstructed_costs=costs,
        patches_replayed=replayed,
        grid=config["expected_grid"],
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
