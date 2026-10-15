"""Consistency checks for the evidence consolidation. No training and no new episodes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifacts" / "nexus_evidence_manifest.json"
EVIDENCE = ROOT / "docs" / "NEXUS_RESEARCH_EVIDENCE.md"
QUESTIONS = ROOT / "docs" / "NEXUS_OPEN_QUESTIONS.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def _pt_records(payload: object, found: list[tuple[str, str]]) -> None:
    if isinstance(payload, dict):
        pairs = (
            ("path", "sha256"),
            ("model_path", "model_sha256"),
            ("global_path", "global_sha256"),
        )
        for path_key, hash_key in pairs:
            path = payload.get(path_key)
            digest = payload.get(hash_key)
            if isinstance(path, str) and path.endswith(".pt") and isinstance(digest, str):
                found.append((path, digest))
        for value in payload.values():
            _pt_records(value, found)
    elif isinstance(payload, list):
        for value in payload:
            _pt_records(value, found)


def _hashed_checkpoints() -> dict[str, str]:
    found: list[tuple[str, str]] = []
    _pt_records(_load("artifacts/latent_generalization_confirmation.json"), found)
    _pt_records(_load("artifacts/control_replication_checkpoints/manifest.json"), found)
    config = yaml.safe_load((ROOT / "configs" / "control_replication.yaml").read_text())
    for key in ("parent_checkpoints", "mlp_checkpoints"):
        for row in config[key]:
            found.append((row["path"], row["sha256"]))
    records: dict[str, str] = {}
    for path, digest in found:
        previous = records.get(path)
        if previous is not None and previous != digest:
            raise AssertionError(f"conflicting hashes for {path}")
        records[path] = digest
    return records


def test_evidence_files_exist_and_do_not_claim_agi() -> None:
    manifest = _load("artifacts/nexus_evidence_manifest.json")
    assert manifest["training_executed"] is False
    assert manifest["new_environment_data_collected"] is False
    assert manifest["previous_results_modified"] is False
    assert manifest["is_agi"] is False
    assert manifest["is_learning_to_learn"] is False
    assert manifest["general_control_claim"] is False
    assert manifest["base_sha"] == "f9468a5b233347135e3485fbae0fd25cdc981d61"
    text = EVIDENCE.read_text() + QUESTIONS.read_text()
    assert manifest["recommended_question"] in text
    for row in manifest["conclusions"]:
        assert row["statement"] in EVIDENCE.read_text()


def test_recorded_artifact_hashes_match_the_files() -> None:
    manifest = _load("artifacts/nexus_evidence_manifest.json")
    assert len(manifest["artifacts"]) == 11
    for row in manifest["artifacts"]:
        assert _sha256(ROOT / row["path"]) == row["sha256"]
    replication = _load("artifacts/control_replication.json")
    standalone = _load("artifacts/control_replication_checkpoints/manifest.json")
    assert replication["checkpoint_manifest"] == standalone
    gap = _load("artifacts/prediction_control_gap.json")
    assert gap["provenance"]["control_artifact_sha256"] == _sha256(ROOT / "artifacts/control_replication.json")
    assert gap["primary_decision"] == "evaluation_variance"
    horizon = _load("artifacts/receding_horizon_diagnostic.json")
    assert horizon["primary_decision"] == "inconclusive"
    assert horizon["reproduction_ok"] is True


def test_checkpoint_hashes_match_locally_and_weights_are_not_in_git() -> None:
    manifest = _load("artifacts/nexus_evidence_manifest.json")
    records = _hashed_checkpoints()
    audit = manifest["checkpoint_audit"]
    assert len(records) == audit["unique_hashed_files_verified"] == 120
    missing = [path for path in records if not (ROOT / path).is_file()]
    mismatches = [path for path, digest in records.items() if (ROOT / path).is_file() and _sha256(ROOT / path) != digest]
    assert missing == []
    assert mismatches == []
    assert audit["mismatches"] == 0
    assert audit["missing"] == 0
    assert audit["github_weight_files_available"] is False
    tracked = [path for path in (ROOT / "artifacts").rglob("*.pt") if path.is_file()]
    assert len(tracked) == audit["local_pt_files_observed"]
    import subprocess

    listed = subprocess.check_output(["git", "ls-files", "*.pt", "*.pth"], cwd=ROOT, text=True)
    assert listed.strip() == ""
    assert audit["git_tracked_pt_files"] == 0


def test_receding_horizon_pairs_are_the_same_contrast() -> None:
    manifest = _load("artifacts/nexus_evidence_manifest.json")
    cells = _load("artifacts/receding_horizon_diagnostic.json")["cells"]
    assert len(cells) == 640
    pairs = {row["id"]: row for row in manifest["dependent_metrics"]}
    checks = (
        ("receding_regret_equals_open_loop_return", "regret_improvement", "sequence_return_improvement"),
        ("receding_continuation_equals_action_regret", "continuation_improvement", "action_regret_improvement"),
    )
    for name, left, right in checks:
        gap = max(abs(float(cell[left]) - float(cell[right])) for cell in cells)
        assert gap < 1e-9
        assert gap == pairs[name]["max_abs_difference"]
        assert pairs[name]["cells"] == 640


def test_conclusion_flags_match_the_source_artifacts() -> None:
    confirmation = _load("artifacts/direct_latent_confirmation.json")
    prediction = _load("artifacts/latent_generalization_confirmation.json")
    replication = _load("artifacts/control_replication.json")
    gap = _load("artifacts/prediction_control_gap.json")
    horizon = _load("artifacts/receding_horizon_diagnostic.json")
    assert confirmation["screen"]["pass"] is True
    assert prediction["gate_pass"] is True
    assert replication["replication_gate_pass"] is True
    assert replication["fresh_gate_pass"] is False
    fresh_zero = replication["paired_student_minus_control"]["fresh"]["zero"]["interval"]
    assert fresh_zero["hi"] < 0
    assert gap["comparisons"]["fresh"]["regret"]["pass"] is True
    assert gap["comparisons"]["replication"]["regret"]["pass"] is True
    visited = horizon["comparisons"]["fresh"]["one_shot_regret"]
    assert visited["pass"] is False
    assert horizon["primary_decision"] == "inconclusive"
    control = _load("artifacts/latent_control.json")
    assert control["inconclusive"] is True
    assert control["gate_pass"] is False
