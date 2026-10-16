"""Audit-schema safety, no saved binaries or environments required."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("efficiency_audit", "scripts/audit_successor_search_efficiency.py")
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def grid():
    cfg = audit.load_config()
    return [dict(family=f, seed=s, context=z, case=c,
                 reference_q=[1., 2., 3.], batched_q=[1., 2., 3.],
                 reference_action=2, batched_action=2,
                 reference_counts=dict(step_calls=51, forward_calls=51, imagined_transitions=771),
                 batched_counts=dict(step_calls=17, forward_calls=17, imagined_transitions=771),
                 fingerprint_before="unchanged", fingerprint_after="unchanged")
            for f in cfg["families"] for s in cfg["model_seeds"]
            for z in (cfg["pendulum_contexts"] if f == "pendulum" else ["none"])
            for c in range(cfg["synthetic_cases_per_context"])]


@pytest.mark.parametrize("omit", ["seed", "family", "context", "case"])
def test_expected_grid_comes_from_config_not_produced_rows(omit):
    rows = grid()
    value = rows[0][omit]
    rows = [r for r in rows if r[omit] != value]
    with pytest.raises(ValueError, match="incomplete"):
        audit.validate_grid(rows, audit.load_config())


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "2", True])
def test_required_metrics_reject_nonfinite_strings_and_booleans(bad):
    rows = grid()
    rows[0]["reference_q"] = [bad, bad, bad]
    with pytest.raises(ValueError):
        audit.validate_grid(rows, audit.load_config())


def test_full_grid_counts_argmax_fingerprint_and_duplicates():
    rows = grid()
    assert len(rows) == 160
    audit.validate_grid(rows, audit.load_config())
    for key, value in [("batched_action", 0), ("batched_counts", dict(step_calls=17, forward_calls=17, imagined_transitions=770)),
                       ("fingerprint_after", "modified")]:
        bad = deepcopy(rows)
        bad[0][key] = value
        with pytest.raises(ValueError): audit.validate_grid(bad, audit.load_config())
    with pytest.raises(ValueError): audit.validate_grid(rows + [rows[0]], audit.load_config())


def test_explicit_checkpoint_audit_fails_when_files_missing(tmp_path):
    # Failure happens before a model is loaded or any synthetic scoring starts.
    with pytest.raises(RuntimeError, match="required source checkpoint missing or wrong"):
        audit.run(tmp_path, audit.load_config())


def test_locked_config_rejects_silent_grid_or_tolerance_reduction(tmp_path, monkeypatch):
    text = Path(audit.CONFIG).read_text()
    path = tmp_path / "config.yaml"
    path.write_text(text.replace("q_atol: 0.0002", "q_atol: 0.02"))
    monkeypatch.setattr(audit, "CONFIG", path)
    with pytest.raises(ValueError, match="locked"):
        audit.load_config()
