"""Git-only verification of the recorded episode-parity result; no binaries."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path("scripts").resolve()))
try:
    import cline_successor_episode_parity as parity
finally:
    sys.path.pop(0)


def _recheck(p):
    cfg = parity.load_config()
    assert p["complete"] is True and p["source_dirty"] is False
    assert p["counts"] == dict(env_steps=24000, model_calls=816000,
        imagined_transitions=18504000)
    assert 0 < p["wall_clock_s"] <= cfg["time_cap_s"]
    assert p["allocation_sha256"] == parity.common.sha(parity.ALLOCATION)
    assert p["config_sha256"] == parity.common.sha(parity.CONFIG)
    assert p["protocol_sha256"] == parity.common.sha(parity.PROTOCOL)
    cells = p["cells"]
    keys = {(c["decoder"], c["task"], c["context"]) for c in cells}
    expected = {(d, t, n) for d in range(10) for t in range(3)
                for n in ("student", "zero")}
    assert keys == expected and len(cells) == 60
    for c in cells:
        serial = c["implementations"]["serial"]
        batched = c["implementations"]["batched"]
        assert len(serial) == len(batched) == 200
        assert c["reset_seed"] == parity.reset_seed(cfg, c["decoder"], c["task"])
        for k, (s, b) in enumerate(zip(serial, batched)):
            assert s["candidate_seed"] == b["candidate_seed"] == \
                parity.step_seed(cfg, c["decoder"], c["task"], k)
            assert s["action"] == s["q"].index(max(s["q"]))
            assert b["action"] == b["q"].index(max(b["q"]))
            if c["metrics"]["actions_identical"]:
                assert s["action"] == b["action"]
                assert s["obs"] == b["obs"] and s["reward"] == b["reward"]
        assert parity.cell_metrics(c, cfg) == c["metrics"]
    rebuilt = parity.summarize(cells, cfg)
    assert rebuilt["label"] == p["label"] == \
        "episode_implementation_parity_established_on_tested_grid"
    assert rebuilt["pooled"] == p["pooled"]
    assert p["checkpoint_after_verified"] == 60
    assert p["new_environment_interactions"] == 24000 and p["optimizer_updates"] == 0
    return p


def test_recorded_episode_parity_passed_on_the_complete_grid():
    p = _recheck(json.loads(Path(parity.OUTPUT).read_text()))
    assert p["pooled"]["identical_action_cells"] == 60
    assert p["pooled"]["divergent_cells"] == []
    assert p["pooled"]["max_reward_deviation"] == 0.0
    assert p["pooled"]["max_return_deviation"] == 0.0


@pytest.mark.parametrize("kind", ["action", "q", "reward", "seed", "metrics",
                                   "cell_removal", "counts", "label"])
def test_recorded_result_rejects_corruption(kind):
    p = json.loads(Path(parity.OUTPUT).read_text())
    if kind == "action":
        s = p["cells"][0]["implementations"]["serial"][3]
        s["action"] = (s["action"] + 1) % 3
    if kind == "q":
        p["cells"][0]["implementations"]["batched"][7]["q"][0] += 1
    if kind == "reward":
        p["cells"][0]["implementations"]["serial"][11]["reward"] += 1
    if kind == "seed":
        p["cells"][0]["implementations"]["serial"][5]["candidate_seed"] += 1
    if kind == "metrics":
        p["cells"][0]["metrics"]["max_q_deviation"] += 1
    if kind == "cell_removal":
        p["cells"] = [c for c in p["cells"] if c["decoder"] != 0]
    if kind == "counts":
        p["counts"]["env_steps"] += 1
    if kind == "label":
        p["label"] = "episode_implementation_parity_not_established"
    with pytest.raises((AssertionError, ValueError)):
        _recheck(p)
