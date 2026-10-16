"""Read-only archived audit guards. No environments, saved weights or training."""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path("scripts").resolve()))
try:
    import audit_successor_archived_parity as audit
finally:
    sys.path.pop(0)


def grid():
    cfg = audit.load_config()
    rows = []
    for d, t, v, p, z in sorted(audit.expected_grid(cfg)):
        r = dict(decoder=d, task=t, visitor=v, phase=p, context=z,
                 reference_q=[1., 2., 3.], batched_q=[1., 2., 3.],
                 reference_action=2, batched_action=2,
                 reference_counts=dict(step_calls=51, forward_calls=51, imagined_transitions=771),
                 batched_counts=dict(step_calls=17, forward_calls=17, imagined_transitions=771),
                 fingerprint_before="same", fingerprint_after="same")
        r["metrics"] = audit.row_metrics(r, cfg)
        rows.append(r)
    return rows


@pytest.mark.parametrize("field", ["decoder", "task", "visitor", "phase", "context"])
def test_removing_entire_planned_dimension_fails(field):
    rows = grid()
    rows = [r for r in rows if r[field] != rows[0][field]]
    with pytest.raises(ValueError, match="incomplete"):
        audit.validate(rows, audit.load_config())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "1", True])
def test_invalid_numeric_required_metrics_rejected(value):
    rows = grid(); rows[0]["batched_q"][0] = value
    with pytest.raises(ValueError): audit.validate(rows, audit.load_config())


def test_grid_counter_argmax_fingerprint_and_duplicate_fail_closed():
    rows = grid(); cfg = audit.load_config()
    assert len(rows) == 2160
    good = audit.validate(rows, cfg)
    assert good["groups"]["pooled"]["cases"] == 2160
    for k, value in (("reference_action", False), ("batched_counts", dict(step_calls=17, forward_calls=17, imagined_transitions=770)),
                     ("fingerprint_after", "changed")):
        bad = deepcopy(rows); bad[0][k] = value
        with pytest.raises(ValueError): audit.validate(bad, cfg)
    with pytest.raises(ValueError): audit.validate(rows + [rows[0]], cfg)


def test_complete_numerical_or_action_mismatch_is_negative_not_incomplete():
    cfg = audit.load_config(); rows = grid()
    rows[0]["reference_q"] = [1., 1.00001, 0.]
    rows[0]["reference_action"] = 1
    rows[0]["batched_q"] = [1.00002, 1.00001, 0.]
    rows[0]["batched_action"] = 0
    rows[0]["metrics"] = audit.row_metrics(rows[0], cfg)
    assert rows[0]["metrics"]["near_tie"] is True
    assert rows[0]["metrics"]["q_within_tolerance"] is True
    result = audit.validate(rows, cfg)
    assert result["label"] == "archived_decision_parity_not_established"
    rows[0]["batched_q"] = [10., 2., 3.]
    rows[0]["metrics"] = audit.row_metrics(rows[0], cfg)
    assert audit.validate(rows, cfg)["groups"]["pooled"]["numerical_matches"] == 2159


def test_saved_context_prefix_and_both_visitors_must_agree():
    z = np.linspace(-.1, .1, 8, dtype=np.float32)
    digest = hashlib.sha256(z.tobytes()).hexdigest()
    x = np.tile(np.r_[np.zeros(3), z], (16, 1)).tolist()
    row = dict(scores={"0": dict(inputs=x)}, before={"0": ["network", digest]}, after={"0": ["network", digest]})
    cells = {(0, 0, v): deepcopy(row) for v in range(2)}
    got, _ = audit.saved_context(cells, 0, 0, "0")
    assert np.array_equal(got, z)
    cells[0, 0, 1]["scores"]["0"]["inputs"][5][3] += 1
    with pytest.raises(ValueError, match="varied"):
        audit.saved_context(cells, 0, 0, "0")


def test_observation_selection_does_not_read_rewards_returns_or_error_fields():
    class Trace(dict):
        def __getitem__(self, key):
            if key not in ("obs", "seeds"):
                raise AssertionError("outcomes must not enter archived parity selection")
            return super().__getitem__(key)
    trace = Trace(obs=[[1., 0., .1]] * 200, seeds=list(range(200)))
    obs, seed = audit.observation({"student": trace}, "student", 150)
    assert seed == 150 and np.array_equal(obs, np.array([1., 0., .1], np.float32))
    trace["seeds"] = [True] * 200
    with pytest.raises(ValueError): audit.observation({"student": trace}, "student", 0)


def test_explicit_binary_verification_rejects_absent_or_altered_file(tmp_path):
    record = dict(path="checkpoint.pt", sha256=hashlib.sha256(b"original").hexdigest())
    with pytest.raises(RuntimeError): audit.verify_records(tmp_path, [record])
    file = tmp_path / "checkpoint.pt"; file.write_bytes(b"original")
    audit.verify_records(tmp_path, [record])
    file.write_bytes(b"modified")
    with pytest.raises(RuntimeError): audit.verify_records(tmp_path, [record])
    with pytest.raises(ValueError): audit.verify_records(tmp_path, [])


def test_per_call_caps_stop_before_excess_model_work(monkeypatch):
    clock = [0.]
    monkeypatch.setattr(audit.time, "perf_counter", lambda: clock[0])
    meter = audit.Meter(dict(time_cap_s=1, imagined_transition_cap=2))
    class Model:
        def step(self, o, a): return o, np.zeros(len(a))
    model = Model(); meter.install(model)
    model.step(np.zeros((2, 3)), np.array([0, 1]))
    assert (meter.states, meter.calls) == (2, 1)
    with pytest.raises(RuntimeError, match="cap"):
        model.step(np.zeros((1, 3)), np.array([0]))
    clock[0] = 2.
    with pytest.raises(TimeoutError): model.step(np.zeros((1, 3)), np.array([0]))
    assert (meter.states, meter.calls) == (2, 1)


def test_underlying_entry_rejects_existing_output_before_loading_models(tmp_path, monkeypatch):
    path = tmp_path / "result.json"; path.write_text("existing")
    monkeypatch.setattr(audit, "OUTPUT", path)
    with pytest.raises(RuntimeError, match="overwrite"):
        audit.run(tmp_path, audit.load_config())


def test_locked_configuration_cannot_shrink_grid_or_relax_tolerance(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text(audit.CONFIG.read_text().replace("q_atol: 0.0002", "q_atol: 0.1"))
    monkeypatch.setattr(audit, "CONFIG", path)
    with pytest.raises(ValueError, match="configuration hash"):
        audit.load_config()
