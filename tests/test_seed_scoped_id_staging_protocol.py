"""Development checks for the registered scoped-id config and stronger verifier."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from nexus.seed.capability_widening_coding import historical_artifact_fingerprints
from nexus.seed.scoped_id_staging import summarize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_seed_scoped_id_staging import digest, verify  # noqa: E402


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
    assert config["repair_transfer"]
    assert all(row["family"] in config["predeclared_families"] for row in config["repair_transfer"])
    assert "py_new_midpoint" not in {row["id"] for row in config["coding"]}


def test_verifier_rejects_relabeled_identification(tmp_path):
    config = json.loads((ROOT / "configs/seed_scoped_id_staging.json").read_text())
    records = [
        dict(kind="audit_manifest", config_hash=digest(config), gemini="NOT_RUN",
             result_label="authored_source_development_pilot_not_confirmation",
             historical_replay_is_not_confirmation=True,
             catalogue_hash="0", identified_only_if="identified_within_catalogue"),
        dict(kind="choice", scope="s", selected="p", identification_status="unique_among_checked"),
        dict(kind="episode", scope="s", seed=1, method="ranked_widening", task="t",
             family="in_grammar", identified=True, identification_status="unique_among_checked",
             halt_cause="candidate_check_limit", unchecked_remaining=10,
             assessment_match=True, certainty_claimed=False, false_certainty=False,
             stopping_reason="unique_among_checked", n_candidate_calls=1, n_questions=0,
             wall_s=0.0, widening_expansions=0),
    ]
    payload = dict(records=records, summary=summarize(records, config),
                   historical_fingerprints=historical_artifact_fingerprints(ROOT))
    try:
        verify(payload, config, root=ROOT)
        raise AssertionError("relabeled identified accepted")
    except ValueError as exc:
        assert "identified" in str(exc)
