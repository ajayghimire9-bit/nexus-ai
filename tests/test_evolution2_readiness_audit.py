"""Read-only evidence tests; no imports of model/environment execution code."""
import copy
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("e228_audit", ROOT / "scripts/audit_evolution2_28_readiness.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def evidence():
    return json.loads((ROOT / "artifacts/evolution2_persist_reset_science.json").read_text())


def test_existing_evidence_has_exact_raw_and_unit_grid():
    audit.validate_historical_grid(evidence())


def test_prior_integration_manifest_and_execution_python_unchanged(tmp_path):
    p = json.loads((ROOT / "artifacts/evolution2_27_feedback_integration.json").read_text())
    # Authenticate historical execution, not today's deliberately evolving code.
    for name in p["source_sha256"]:
        if name.endswith(".py"):
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(subprocess.check_output(["git", "show", p["execution_sha"] + ":" + name], cwd=ROOT))
    audit.validate_integration_provenance(tmp_path, p)
    p["manifest"]["query_slots"].append(999)
    with pytest.raises(ValueError, match="manifest_digest"):
        audit.validate_integration_provenance(tmp_path, p)


@pytest.mark.parametrize("mutation", ["bundle", "duplicate", "family", "method", "array", "fit"])
def test_missing_or_duplicate_historical_cells_rejected(mutation):
    p = evidence()
    if mutation == "bundle": p["bundles"].pop()
    if mutation == "duplicate": p["bundles"][2] = copy.deepcopy(p["bundles"][0])
    if mutation == "family": p["bundles"][0]["families"].pop()
    if mutation == "method": del p["bundles"][0]["raw_scores"]["reset"]
    if mutation == "array": p["arrays"].pop()
    if mutation == "fit": p["fits"].pop()
    with pytest.raises(ValueError): audit.validate_historical_grid(p)


@pytest.mark.parametrize("value", [True, "1.0", float("nan"), float("inf"), -float("inf")])
def test_invalid_raw_scores_rejected(value):
    p = evidence()
    p["bundles"][0]["raw_scores"]["persist"] = value
    with pytest.raises(ValueError, match="nonnumeric"):
        audit.validate_historical_grid(p)


def test_audit_parses_source_without_importing_or_running_it():
    text = 'raise RuntimeError("must never execute")\ndef example():\n    return simulator.step()\n'
    assert audit.calls(audit.function(text, "example")) == {"simulator.step"}
    with pytest.raises(ValueError): audit.function(text, "missing")


def test_review_detects_legacy_wiring_not_a_new_execution_path():
    science = (ROOT / audit.SOURCE / "persist_reset_science.py").read_text()
    corrected = audit.calls(audit.function(science, "corrected_hidden_scores"))
    assert "MethodSensitiveHiddenEval" in corrected
    assert "prospective_hidden_evaluator" not in corrected
    assert "run_bundle" in audit.calls(audit.function(science, "run_authorized"))
    assert "max" in audit.calls(audit.function(science, "fixture_hidden_return"))


def test_existing_n10_budget_is_arithmetic_prior_not_measured_fit_clock():
    screens = json.loads((ROOT / "artifacts/evolution2_persist_reset_scoring.json").read_text())["screens"]
    for n, upper in ((3, 24480), (10, 81600)):
        p = screens[f"n{n}"]
        assert p["source"] + p["revealed"] + p["hidden_physical_upper"] == upper
        assert p["fits"] == 2 * n
    assert screens["n10"]["twenty_fit_clock_s"] is None
    assert screens["n10"]["planning_only"] is True
