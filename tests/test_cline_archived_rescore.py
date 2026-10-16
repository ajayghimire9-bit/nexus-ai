"""Read-only Cline rescore guards. No environments, saved weights or training."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path("scripts").resolve()))
try:
    import cline_verify_successor_archived_rescore as rescore
    import audit_successor_archived_parity as audit
finally:
    sys.path.pop(0)


def test_locked_configuration_values():
    cfg = rescore.load_config()
    assert cfg["decoders"] == list(range(10)) and cfg["phases"] == [0, 16, 50, 100, 150, 199]
    assert cfg["cross_atol"] == 1e-9 and cfg["time_cap_s"] == 120
    assert cfg["parents"]["artifacts/successor_archived_parity.json"] == rescore.RECORDED_SHA256


def test_locked_configuration_rejects_tampering(monkeypatch):
    cfg = rescore.load_config()
    monkeypatch.setattr(rescore.yaml, "safe_load", lambda text: {**cfg, "q_atol": .001})
    with pytest.raises(ValueError):
        rescore.load_config()


def test_recorded_artifact_grid_matches_locked_rescore_grid():
    cfg = rescore.load_config()
    recorded = json.loads(Path(rescore.RECORDED).read_text())
    keys = {(r["decoder"], r["task"], r["visitor"], r["phase"], r["context"])
            for r in recorded["rows"]}
    assert keys == audit.expected_grid(cfg)
    assert recorded["label"] == "archived_decision_parity_established_on_tested_inputs"


def _pair(dev_ref=0., dev_bat=0., action_mismatch=False):
    cfg = rescore.load_config()
    fresh = dict(reference_q=[1., 2., 3.], batched_q=[1., 2., 3.],
                 reference_action=2, batched_action=0 if action_mismatch else 2)
    recorded = dict(reference_q=[1., 2., 3. + dev_ref], batched_q=[1., 2., 3. + dev_bat],
                   reference_action=2, batched_action=2)
    fresh["metrics"] = audit.row_metrics(fresh, cfg)
    recorded["metrics"] = audit.row_metrics(recorded, cfg)
    return fresh, recorded, cfg


@pytest.mark.parametrize("dev_ref,dev_bat,within_cross,bitwise", [
    (0., 0., True, True), (5e-10, 5e-10, True, False), (1e-4, 0., False, False)])
def test_cross_check_classification(dev_ref, dev_bat, within_cross, bitwise):
    fresh, recorded, cfg = _pair(dev_ref, dev_bat)
    cross = rescore.cross_check(fresh, recorded, cfg)
    assert cross["within_cross_tolerance"] is within_cross
    assert cross["reference_bitwise"] is bitwise
    assert cross["metrics_equal"] is (dev_ref == 0. and dev_bat == 0.)
    assert cross["within_audit_tolerance"] is True


def _rows(dev_ref=0., action_mismatch=False):
    fresh, recorded, cfg = _pair(dev_ref, 0., action_mismatch)
    return [dict(metrics=fresh["metrics"], cross=rescore.cross_check(fresh, recorded, cfg))] * 2, cfg


def test_label_rules():
    rows, cfg = _rows()
    assert rescore.summarize(rows, cfg)["label"] == "independent_rescore_reproduced"
    rows, cfg = _rows(dev_ref=1e-5)
    assert rescore.summarize(rows, cfg)["label"] == \
        "independent_rescore_confirmed_within_tolerance_not_bitwise"
    rows, cfg = _rows(action_mismatch=True)
    assert rescore.summarize(rows, cfg)["label"] == "independent_rescore_disagrees"


def test_guard_stops_before_excess_model_work(monkeypatch):
    clock = [0.]
    monkeypatch.setattr(rescore.time, "perf_counter", lambda: clock[0])
    guard = rescore.Guard(dict(time_cap_s=1, imagined_transition_cap=2))

    class Model:
        def step(self, o, a):
            return o, np.zeros(len(a))
    model = Model(); guard.install(model)
    model.step(np.zeros((2, 3)), np.array([0, 1]))
    assert (guard.transitions, guard.calls) == (2, 1)
    with pytest.raises(RuntimeError, match="cap"):
        model.step(np.zeros((2, 3)), np.array([0, 1]))
    clock[0] = 2.
    with pytest.raises(TimeoutError):
        guard.check()


def test_run_refuses_repeated_rescore(monkeypatch, tmp_path):
    cfg = rescore.load_config()
    existing = tmp_path / "used.json"; existing.write_text("{}")
    monkeypatch.setattr(rescore, "OUTPUT", existing)
    with pytest.raises(RuntimeError, match="refusing"):
        rescore.run(tmp_path, cfg)


def test_run_requires_clean_committed_tree(monkeypatch, tmp_path):
    cfg = rescore.load_config()
    monkeypatch.setattr(rescore, "OUTPUT", tmp_path / "unused.json")
    monkeypatch.setattr(rescore.subprocess, "check_output", lambda *a, **k: " M file\n")
    with pytest.raises(RuntimeError, match="commit clean"):
        rescore.run(tmp_path, cfg)
