"""Development checks for the registered scoped-id config and stronger verifier."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.scoped_id_staging import summarize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_seed_scoped_id_staging import (  # noqa: E402
    digest, expected_coding_cells, expected_episode_keys, reconstruct_costs, verify,
)


def _load_config():
    return json.loads((ROOT / "configs/seed_scoped_id_staging.json").read_text())


def _dummy_records(config, *, identified_status="no_checked_candidate_fits", identified=False):
    records = [
        dict(kind="audit_manifest", config_hash=digest(config), gemini="NOT_RUN",
             result_label="authored_source_development_pilot_not_confirmation",
             historical_replay_is_not_confirmation=True,
             catalogue_hash="0", identified_only_if="identified_within_catalogue"),
    ]
    for seed, method, task in expected_episode_keys(config):
        scope = f"{seed}:{method}:{task}"
        records.append(dict(kind="choice", scope=scope, selected="p",
                            identification_status=identified_status))
        records.append(dict(
            kind="episode", scope=scope, seed=seed, method=method, task=task,
            family="oog" if task.endswith(":oog") else "in_grammar",
            identified=identified, identification_status=identified_status,
            halt_cause="candidate_check_limit", unchecked_remaining=10,
            assessment_match=identified, certainty_claimed=False, false_certainty=False,
            stopping_reason=identified_status, n_candidate_calls=1, n_questions=0,
            wall_s=0.0, widening_expansions=0,
        ))
    for spec_id, method in expected_coding_cells(config):
        records.append(dict(
            kind="capability", id=spec_id, method=method, category="coding",
            family="comparison_boundary", role="assessment",
            outcome="failed", public_passed=False, private={"all_passed": False},
            model_trace=[], attempts=0, revised=False,
            model_generated_per_file=method == "local_model_per_file",
            used_prior_staged_context=False, complete_correctness=False,
            completions=0, generated_tokens=0, input_tokens=0, request_wall_s=0.0,
        ))
    for pair in config["repair_transfer"]:
        records.append(dict(
            kind="capability", id=pair["id"], method="repair_schema_transfer",
            category="coding", family=pair["family"], role="transfer",
            source_id=pair["source_id"], assessment_id=pair["assessment_id"],
            genuine_source_acquisition=False, cache_hit=False, reused=False,
            private={"all_passed": False}, cache_private=None,
            template_private={"all_passed": False}, none_private={"all_passed": False},
            acquisition_charged=True, one_success_is_not_100_percent=True,
            complete_correctness=False,
        ))
    for spec in config["conversation"]:
        records.append(dict(
            kind="capability", id=spec["id"], category="language",
            conversation_kind=spec["kind"], rubric=spec["rubric"],
        ))
    return records


def test_registered_config_exists_and_declares_splits():
    path = ROOT / "configs" / "seed_scoped_id_staging.json"
    assert path.is_file()
    config = json.loads(path.read_text())
    assert config["id"] == "seed-scoped-id-staging-1"
    assert config["identified_only_if"] == "identified_within_catalogue"
    assert config["controller"]["max_candidates_checked"] == 24
    assert config["methods"] == ["no_widening", "ranked_widening", "stratified_widening"]
    assert config["predeclared_families"] == [
        "comparison_boundary", "missing_function", "null_default",
    ]
    assert config["expected_grid"] == {
        "investigation_episodes": 30,
        "coding_cells": 18,
        "repair_transfer_cells": 2,
        "conversation_cells": 3,
    }
    assert {row["id"] for row in config["coding"]} >= {
        "py_inclusive_window_src", "py_score_gate", "py_or_default_src", "py_or_floor",
    }
    assert "py_new_midpoint" not in {row["id"] for row in config["coding"]}
    assert all("patched" not in row and "source" not in row for row in config["repair_transfer"])
    assert all({"source_id", "assessment_id"} <= set(row) for row in config["repair_transfer"])
    roles = {row["id"]: row.get("role") for row in config["coding"]}
    for pair in config["repair_transfer"]:
        assert roles[pair["source_id"]] == "source"
        assert pair["family"] in config["predeclared_families"]


def test_verifier_rejects_incomplete_grid():
    config = _load_config()
    records = [
        dict(kind="audit_manifest", config_hash=digest(config), gemini="NOT_RUN",
             result_label="authored_source_development_pilot_not_confirmation",
             historical_replay_is_not_confirmation=True,
             catalogue_hash="0", identified_only_if="identified_within_catalogue"),
        dict(kind="choice", scope="s", selected="p", identification_status="no_checked_candidate_fits"),
        dict(kind="episode", scope="s", seed=1, method="ranked_widening", task="t",
             family="in_grammar", identified=False, identification_status="no_checked_candidate_fits",
             halt_cause="candidate_check_limit", unchecked_remaining=10,
             assessment_match=False, certainty_claimed=False, false_certainty=False,
             stopping_reason="no_checked_candidate_fits", n_candidate_calls=1, n_questions=0,
             wall_s=0.0, widening_expansions=0),
    ]
    payload = dict(records=records, summary=summarize(records, config),
                   historical_fingerprints=historical_artifact_fingerprints(ROOT))
    try:
        verify(payload, config, root=ROOT, replay=False)
        raise AssertionError("incomplete grid accepted")
    except ValueError as exc:
        assert "grid" in str(exc)


def test_verifier_rejects_relabeled_identification():
    config = _load_config()
    records = _dummy_records(config, identified_status="unique_among_checked", identified=True)
    payload = dict(records=records, summary=summarize(records, config),
                   historical_fingerprints=historical_artifact_fingerprints(ROOT))
    try:
        verify(payload, config, root=ROOT, replay=False)
        raise AssertionError("relabeled identified accepted")
    except ValueError as exc:
        assert "identified" in str(exc)


def test_reconstruct_costs_from_raw_traces():
    records = [
        dict(kind="capability", category="coding", method="local_model_single", id="a",
             completions=2, generated_tokens=10, input_tokens=6, request_wall_s=0.2,
             model_trace=[
                 {"inference_ran": True, "telemetry": {
                     "generated_tokens": 4, "input_tokens": 3, "request_wall_s": 0.1,
                 }},
                 {"inference_ran": True, "telemetry": {
                     "generated_tokens": 6, "input_tokens": 3, "request_wall_s": 0.1,
                 }},
             ]),
        dict(kind="capability", category="coding", method="local_model_per_file", id="b",
             completions=2, generated_tokens=8, input_tokens=4, request_wall_s=0.1,
             model_trace=[{"completions": 2, "traces": [{}, {}], "telemetry": {
                 "generated_tokens": 8, "input_tokens": 4, "request_wall_s": 0.1,
             }}]),
    ]
    costs = reconstruct_costs(records)
    assert costs["completions"] == 4
    assert costs["generated_tokens"] == 18
    assert costs["input_tokens"] == 10
