"""Development checks for the six-area comparison protocol."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from nexus.seed.agent_loop_worker import run_worker_subprocess
from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.six_area_comparison import summarize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_seed_six_area_comparison import digest, expected_episode_keys, verify  # noqa: E402


def _config():
    return json.loads((ROOT / "configs/seed_six_area_comparison.json").read_text())


def test_registered_config_excludes_closed_ids_and_handwritten_patches():
    config = _config()
    assert config["id"] == "seed-six-area-comparison-1"
    assert config["identified_only_if"] == "identified_within_catalogue"
    assert config["methods"] == ["fixed_boundary", "learned", "capsules_reset", "shuffled"]
    assert config["coding_conditions"] == [
        "model_tools", "model_tools_cache", "nexus_repair_memory",
    ]
    ids = {row["id"] for row in config["coding"]}
    assert ids.isdisjoint(config["closed_coding_ids_excluded"])
    assert "patched" not in config["reuse"]
    later = config["reuse"]["assessment"]
    source = next(row for row in config["coding"] if row["id"] == config["reuse"]["source_id"])
    assert later["files"] != source["files"]
    assert later["request"] != source["request"]
    assert config["expected_grid"]["investigation_episodes"] == 12
    assert config["expected_grid"]["coding_cells"] == 12


def test_reasoning_cases_are_execution_backed():
    config = _config()
    for spec in config["reasoning"]:
        result = run_worker_subprocess({
            "language": spec["language"],
            "files": spec["files"],
            "cases": spec["cases"],
        })
        assert result["all_passed"] is True


def test_verifier_rejects_incomplete_grid():
    config = _config()
    records = [
        dict(kind="audit_manifest", config_hash=digest(config), gemini="NOT_RUN",
             result_label="authored_source_development_pilot_not_confirmation",
             catalogue_hash="0", identified_only_if="identified_within_catalogue",
             learning_to_learn_established=False),
        dict(kind="choice", scope="s", selected="p", identification_status="no_checked_candidate_fits"),
        dict(kind="episode", scope="s", seed=1, method="learned", task="t",
             family="in_grammar", identified=False, identification_status="no_checked_candidate_fits",
             assessment_match=False, certainty_claimed=False, false_certainty=False,
             stopping_reason="x", n_candidate_calls=1, n_questions=0, wall_s=0.0),
    ]
    payload = dict(records=records, summary=summarize(records, config),
                   historical_fingerprints=historical_artifact_fingerprints(ROOT))
    try:
        verify(payload, config, root=ROOT, replay=False)
        raise AssertionError("incomplete grid accepted")
    except ValueError as exc:
        assert "grid" in str(exc)


def test_expected_episode_keys_match_declared_grid():
    config = _config()
    keys = expected_episode_keys(config)
    assert len(keys) == config["expected_grid"]["investigation_episodes"]
    assert (86101, "shuffled", "86101:assessment:oog") in keys
