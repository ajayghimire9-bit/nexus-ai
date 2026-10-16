"""Git-only verification: no checkpoint files or neural inference."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path("scripts").resolve()))
try:
    import verify_successor_archived_parity as verification
finally:
    sys.path.pop(0)


def test_saved_result_independent_arithmetic_and_archive_mapping():
    result = verification.verify()
    assert result["verified"] is True
    assert result["pooled"]["action_matches"] == 2160
    assert result["pooled"]["ranking_matches"] == 2160
    assert result["new_model_inference_calls"] == 0


@pytest.mark.parametrize("kind", ["observation", "seed", "q", "summary", "whole_seed", "checkpoint"])
def test_saved_result_rejects_corruption(kind):
    p = json.loads(Path("artifacts/successor_archived_parity.json").read_text())
    if kind == "observation": p["rows"][0]["observation"][0] += 1
    if kind == "seed": p["rows"][0]["candidate_seed"] += 1
    if kind == "q": p["rows"][0]["reference_q"][0] += 1
    if kind == "summary": p["groups"]["decoder_0"]["action_matches"] -= 1
    if kind == "whole_seed": p["rows"] = [r for r in p["rows"] if r["decoder"] != 0]
    if kind == "checkpoint": p["checkpoint_records"].pop()
    with pytest.raises(ValueError): verification.verify(p)
