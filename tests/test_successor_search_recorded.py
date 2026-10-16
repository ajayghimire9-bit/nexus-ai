"""Recompute engineering evidence from Git-only JSON; no binary/model access."""
import hashlib
import json
from pathlib import Path
import statistics

import numpy as np


def test_saved_engineering_audit_is_complete_paired_and_reproducible():
    p = json.loads(Path("artifacts/successor_search_efficiency.json").read_text())
    assert p["complete"] is True and p["source_dirty"] is False
    assert p["decision_parity_passed"] is True
    expected = {(f, d, c, k) for f in ("pendulum", "acrobot", "mountaincar") for d in range(10)
                for c in (["zero", "synthetic_nonzero"] if f == "pendulum" else ["none"])
                for k in range(4)}
    observed = [(r["family"], r["seed"], r["context"], r["case"]) for r in p["rows"]]
    assert len(observed) == len(set(observed)) == 160 and set(observed) == expected
    for r in p["rows"]:
        old, new = np.array(r["reference_q"]), np.array(r["batched_q"])
        np.testing.assert_allclose(new, old, atol=2e-4, rtol=2e-5)
        assert r["reference_action"] == r["batched_action"] == int(np.argmax(old)) == int(np.argmax(new))
        assert np.array_equal(np.argsort(old, kind="stable"), np.argsort(new, kind="stable"))
        assert r["reference_counts"] == dict(step_calls=51, forward_calls=51, imagined_transitions=771)
        assert r["batched_counts"] == dict(step_calls=17, forward_calls=17, imagined_transitions=771)
        assert r["fingerprint_before"] == r["fingerprint_after"]
    assert p["actions_identical"] == p["rankings_identical"] == 160
    assert len(p["checkpoint_records"]) == 30
    assert len({(r["family"], r["seed"]) for r in p["checkpoint_records"]}) == 30
    assert p["new_environment_interactions"] == p["training_updates"] == 0
    assert p["reserved_outcomes_accessed"] is False
    for key, filename in (("config_sha256", "configs/successor_search_efficiency.yaml"),
                          ("protocol_sha256", "docs/NEXUS_SUCCESSOR_SEARCH_EFFICIENCY.md")):
        assert p[key] == hashlib.sha256(Path(filename).read_bytes()).hexdigest()
    for filename, digest in {**p["source_hashes"], **p["checkpoint_metadata_hashes"]}.items():
        assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == digest
    maximum = max(float(np.max(np.abs(np.array(r["reference_q"]) - r["batched_q"]))) for r in p["rows"])
    assert maximum == p["max_absolute_q_difference"]
    for t in p["timings"]:
        for name, samples in t["seconds_per_decision"].items():
            assert len(samples) == 7 and all(np.isfinite(v) and v > 0 for v in samples)
            assert statistics.median(samples) == t["medians"][name]
        assert t["speedup"] == t["medians"]["reference"] / t["medians"]["batched"]
