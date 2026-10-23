"""Development checks for interrupt, bottleneck classify and transfer pairing."""
from __future__ import annotations

import json
from pathlib import Path

from nexus.seed.interrupt_transfer import classify_coding_failure


ROOT = Path(__file__).resolve().parents[1]


def test_config_keeps_fixed_policy_and_wrong_reuse_cells():
    config = json.loads((ROOT / "configs/seed_interrupt_transfer.json").read_text())
    assert config["default_investigation_policy"] == "fixed_boundary"
    assert config["learned_policy_promoted"] is False
    later = {row["id"]: row for row in config["transfer"]["later"]}
    assert later["py_width_ok"]["reuse_appropriate"] is True
    assert later["py_keep_exclusive"]["reuse_appropriate"] is False
    assert later["py_pair_label"]["reuse_appropriate"] is False
    assert config["expected_grid"]["transfer_cells"] == 15


def test_classify_coding_failure_separates_bottlenecks():
    assert classify_coding_failure({"model_trace": [], "completions": 0, "public_passed": False}) == "missing_inference"
    assert classify_coding_failure({
        "model_trace": [{"status": "invalid_proposal", "reason": "ValueError: old_text_not_unique:levy.py"}],
        "public_passed": False,
    }) == "invalid_edits"
    assert classify_coding_failure({
        "model_trace": [{"status": "proposed"}],
        "public_passed": False, "revised": False,
    }) == "incorrect_implementation"
    assert classify_coding_failure({
        "model_trace": [{"status": "proposed"}],
        "public_passed": False, "revised": True,
    }) == "failed_revision"
