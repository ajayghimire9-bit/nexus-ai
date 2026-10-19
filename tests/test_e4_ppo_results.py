"""Repository-only evidence tests; deliberately no local checkpoint dependency."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("e4_independent_summary", ROOT / "scripts/summarize_e4_ppo_benchmark.py")
summary = importlib.util.module_from_spec(spec); spec.loader.exec_module(summary)
check_spec = importlib.util.spec_from_file_location("e4_repeatable_integrity", ROOT / "scripts/verify_e4_ppo_checkpoints.py")
checker = importlib.util.module_from_spec(check_spec); check_spec.loader.exec_module(checker)


def evidence():
    return (json.loads((ROOT / "artifacts/e4_ppo_benchmark.json").read_text()),
            json.loads((ROOT / "configs/e4_ppo_benchmark.json").read_text()))


def test_independent_saved_results_grid_intervals_and_failed_screen():
    p, c = evidence()
    result = summary.replay(p, c)
    assert len(result) == 5 and not any(r["screen_passed"] for r in result.values())
    assert all(ci["interval"]["n"] == 3 and ci["interval"]["df"] == 2 for r in result.values() for ci in r["contrasts"].values())


@pytest.mark.parametrize("axis", ["family", "replicate", "method"])
def test_repository_arithmetic_rejects_missing_entire_axis(axis):
    p, c = evidence()
    value = p["rows"][0][axis]
    p["rows"] = [r for r in p["rows"] if r[axis] != value]
    with pytest.raises(ValueError): summary.replay(p, c)


def test_repository_arithmetic_rejects_changed_interval_and_boolean_returns():
    p, c = evidence(); p["analysis"]["families"]["cartpole"]["contrasts"]["random"]["interval"]["lo"] += 1
    with pytest.raises(ValueError): summary.replay(p, c)
    p, c = evidence(); p["rows"][0]["episodes"][0]["raw_return"] = True
    with pytest.raises(ValueError): summary.replay(p, c)


def test_protocol_config_and_validation_provenance_no_binaries_needed():
    p, c = evidence()
    a = json.loads((ROOT / "configs/e4_ppo_benchmark_allocation.json").read_text())
    v = json.loads((ROOT / "artifacts/e4_ppo_benchmark_validation.json").read_text())
    sha = lambda path:hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    assert sha("configs/e4_ppo_benchmark.json") == p["config_sha256"] == a["config_sha256"]
    assert sha("docs/NEXUS_E4_PPO_BENCHMARK_PROTOCOL.md") == p["protocol_sha256"] == a["protocol_sha256"]
    assert sha("artifacts/e4_ppo_benchmark.json") == v["result_sha256"]
    assert v["evaluation_episodes"] == 90 and v["checkpoint_files_verified"] == 15
    assert v["receipts"] == p["resources"]["completed"]["real_steps"] <= 84840
    assert v["combined_execution_audit_wall_s"] < 300
    assert len(p["models"]) == 15 and len(p["rows"]) == 45


def test_explicit_checkpoint_audit_fails_on_missing_required_file(tmp_path):
    p, c = evidence()
    with pytest.raises(FileNotFoundError, match="integrity audit failed, not skipped"):
        checker.verify_files(p, c, tmp_path)


def test_explicit_checkpoint_audit_fails_on_wrong_hash(tmp_path):
    p, c = evidence()
    first = tmp_path / p["models"][0]["checkpoint_path"]
    first.parent.mkdir(parents=True)
    first.write_bytes(b"changed weights fixture")
    with pytest.raises(ValueError, match="hash mismatch"):
        checker.verify_files(p, c, tmp_path)


def test_explicit_checkpoint_audit_rejects_shortened_model_grid(tmp_path):
    p, c = evidence(); p["models"].pop()
    with pytest.raises(ValueError, match="complete planned checkpoint grid"):
        checker.verify_files(p, c, tmp_path)
