"""Git-only verification of the recorded Cline rescore artifact; no binaries."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path("scripts").resolve()))
try:
    import cline_verify_successor_archived_rescore as rescore
    import audit_successor_archived_parity as audit
finally:
    sys.path.pop(0)


def _recheck(p):
    cfg = rescore.load_config()
    assert p["complete"] is True and p["source_dirty"] is False
    recorded = json.loads(Path(rescore.RECORDED).read_text())
    rec = {(r["decoder"], r["task"], r["visitor"], r["phase"], r["context"]): r
           for r in recorded["rows"]}
    rows = p["rows"]
    keys = {(r["decoder"], r["task"], r["visitor"], r["phase"], r["context"]) for r in rows}
    assert keys == audit.expected_grid(cfg) == set(rec)
    assert p["counts"] == dict(model_calls=len(rows) * 68,
        imagined_transitions=len(rows) * 1542)
    for r in rows:
        rr = rec[(r["decoder"], r["task"], r["visitor"], r["phase"], r["context"])]
        assert r["observation"] == rr["observation"]
        assert r["candidate_seed"] == rr["candidate_seed"]
        assert r["reference_action"] == r["reference_q"].index(max(r["reference_q"]))
        assert r["batched_action"] == r["batched_q"].index(max(r["batched_q"]))
        assert r["fingerprint_before"] == r["fingerprint_after"]
        for counts, step_calls in ((r["reference_counts"], 51), (r["batched_counts"], 17)):
            assert counts == dict(step_calls=step_calls,
                forward_calls=step_calls, imagined_transitions=771)
        fresh = dict(reference_q=r["reference_q"], batched_q=r["batched_q"],
            reference_action=r["reference_action"], batched_action=r["batched_action"],
            metrics=r["metrics"])
        assert rescore.cross_check(fresh, rr, cfg) == r["cross"]
    assert rescore.summarize(rows, cfg) == dict(pooled=p["pooled"], label=p["label"])
    assert p["checkpoint_after_verified"] == 60
    assert 0 < p["wall_clock_s"] <= cfg["time_cap_s"]
    assert p["new_environment_interactions"] == 0 and p["optimizer_updates"] == 0
    return p


def test_recorded_rescore_reproduced_the_archived_parity_grid():
    p = _recheck(json.loads(Path(rescore.OUTPUT).read_text()))
    assert p["label"] == "independent_rescore_reproduced"
    assert p["pooled"]["cases"] == 2160
    assert p["pooled"]["bitwise_reference_cells"] == 2160
    assert p["pooled"]["bitwise_batched_cells"] == 2160
    assert p["pooled"]["max_reference_deviation"] == 0.0
    assert p["pooled"]["max_batched_deviation"] == 0.0
    assert p["pooled"]["fresh_action_matches"] == 2160
    assert p["pooled"]["recorded_metrics_agreement"] == 2160


@pytest.mark.parametrize("kind", ["q", "action", "cross", "summary",
                                  "row_removal", "counts", "fingerprint"])
def test_recorded_rescore_rejects_corruption(kind):
    p = json.loads(Path(rescore.OUTPUT).read_text())
    if kind == "q": p["rows"][0]["reference_q"][0] += 1
    if kind == "action":
        p["rows"][0]["batched_action"] = (p["rows"][0]["batched_action"] + 1) % 3
    if kind == "cross": p["rows"][0]["cross"]["within_cross_tolerance"] = False
    if kind == "summary": p["pooled"]["bitwise_reference_cells"] -= 1
    if kind == "row_removal": p["rows"] = [r for r in p["rows"] if r["decoder"] != 0]
    if kind == "counts": p["counts"]["model_calls"] += 1
    if kind == "fingerprint": p["rows"][0]["fingerprint_after"] = "changed"
    with pytest.raises((AssertionError, ValueError)):
        _recheck(p)
