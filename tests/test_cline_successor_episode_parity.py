"""Offline episode-parity guards. No environments, checkpoints or training."""
import json
from pathlib import Path
import re
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path("scripts").resolve()))
try:
    import cline_successor_episode_parity as parity
finally:
    sys.path.pop(0)


def test_locked_configuration_and_budget():
    cfg = parity.load_config()
    assert cfg["reset_base"] == 61000000 and cfg["step_seed_base"] == 61100000
    assert parity.budget(cfg) == dict(env_steps=24000,
        imagined_transitions=18504000, model_calls=816000)


def test_seed_groups_are_sized_coupled_and_above_every_registered_block():
    cfg = parity.load_config()
    groups = parity.seed_groups(cfg)
    assert [len(g) for g in groups] == [30, 6000]
    assert min(groups[0]) >= 61000000 and min(groups[1]) >= 61100000
    # No implementation/context/visitor factor: coupled across all arms.
    assert len({parity.step_seed(cfg, d, t, k) for d in range(10)
                for t in range(3) for k in range(200)}) == 6000


def test_seeds_are_disjoint_from_all_closed_registries_and_config_bases():
    cfg = parity.load_config()
    blocked = parity.check_seeds(cfg)
    assert not (set().union(*parity.seed_groups(cfg)) & blocked)
    assert max(blocked) < cfg["reset_base"]
    # Catch-all: every committed seed base in configs/ is below this block.
    for path in Path("configs").glob("*.yaml"):
        if path.name == "cline_successor_episode_parity.yaml":
            continue
        for value in re.findall(r"[a-z_]*base:\s*(\d+)", path.read_text()):
            assert int(value) < cfg["reset_base"], (path, value)


def test_allocation_blocks_collection_until_authorized():
    cfg = parity.load_config()
    with pytest.raises(PermissionError):
        parity.require_allocation(cfg)
    record = parity.load_allocation()
    assert record["authorized"] is False and record["runs"] == 1


def test_allocation_drift_fails(monkeypatch, tmp_path):
    parity.load_config()
    record = json.loads(parity.ALLOCATION.read_text())
    bad = {**record, "env_cap": 24001}
    monkeypatch.setattr(parity, "ALLOCATION", tmp_path / "allocation.json")
    (tmp_path / "allocation.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        parity.load_allocation()


def test_execute_refuses_repeated_run_and_dirty_tree(monkeypatch, tmp_path):
    parity.load_config()
    monkeypatch.setattr(parity, "require_allocation", lambda cfg: None)
    used = tmp_path / "used.json"; used.write_text("{}")
    monkeypatch.setattr(parity, "OUTPUT", used)
    with pytest.raises(RuntimeError, match="refusing"):
        parity.execute(tmp_path)
    monkeypatch.setattr(parity, "OUTPUT", tmp_path / "unused.json")
    monkeypatch.setattr(parity.subprocess, "check_output", lambda *a, **k: " M file\n")
    with pytest.raises(RuntimeError, match="commit clean"):
        parity.execute(tmp_path)


def test_meter_caps_stop_before_excess_work(monkeypatch):
    clock = [0.]
    monkeypatch.setattr(parity.time, "perf_counter", lambda: clock[0])
    meter = parity.Meter(dict(time_cap_s=1, imagined_cap=2, env_cap=1))

    class Model:
        def step(self, o, a):
            return o, np.zeros(len(a))
    model = Model()
    meter.score(model, lambda: model.step(np.zeros((2, 3)), np.array([0, 1])))
    assert (meter.calls, meter.transitions) == (1, 2)
    meter.env_step()
    with pytest.raises(RuntimeError, match="env-step"):
        meter.env_step()
    with pytest.raises(RuntimeError, match="imagined"):
        meter.score(model, lambda: model.step(np.zeros((2, 3)), np.array([0, 1])))
    clock[0] = 2.
    with pytest.raises(TimeoutError):
        meter.check()


def _trace(actions, rewards, q=(1., 2., 3.)):
    return [dict(obs=[0., 0., 0.], candidate_seed=1000 + k, action=a,
                 q=[v + 1e-6 * k for v in q], reward=r)
            for k, (a, r) in enumerate(zip(actions, rewards))]


def _cell(serial_actions, batched_actions, reward_delta=0.):
    rewards = [-1.0] * 200
    return dict(implementations=dict(
        serial=_trace(serial_actions, rewards),
        batched=_trace(batched_actions, [r + reward_delta for r in rewards])))


def test_cell_metrics_and_first_divergence():
    cfg = parity.load_config()
    cell = _cell([1] * 200, [1] * 200)
    m = parity.cell_metrics(cell, cfg)
    assert m["actions_identical"] is True and m["first_divergence"] == 200
    assert m["q_within_tolerance"] is True and m["rewards_within_tolerance"] is True
    assert m["max_reward_deviation"] == 0.0 and m["return_deviation"] == 0.0
    cell = _cell([1] * 200, [1] * 99 + [2] + [1] * 100)
    m = parity.cell_metrics(cell, cfg)
    assert m["actions_identical"] is False and m["first_divergence"] == 99
    cell = _cell([1] * 200, [1] * 200, reward_delta=1e-6)
    m = parity.cell_metrics(cell, cfg)
    assert m["actions_identical"] is True
    assert m["rewards_within_tolerance"] is False


def test_summarize_label_rules():
    cfg = parity.load_config()
    cells = []
    for d in range(10):
        for t in range(3):
            for name in ("student", "zero"):
                c = _cell([1] * 200, [1] * 200)
                c.update(decoder=d, task=t, context=name)
                c["metrics"] = parity.cell_metrics(c, cfg)
                cells.append(c)
    assert len(cells) == 60
    result = parity.summarize(cells, cfg)
    assert result["label"] == "episode_implementation_parity_established_on_tested_grid"
    assert result["pooled"]["identical_action_cells"] == 60
    cells[0] = _cell([1] * 200, [1] * 50 + [2] + [1] * 149)
    cells[0].update(decoder=0, task=0, context="student")
    cells[0]["metrics"] = parity.cell_metrics(cells[0], cfg)
    result = parity.summarize(cells, cfg)
    assert result["label"] == "episode_implementation_parity_not_established"
    assert result["pooled"]["divergent_cells"][0]["first_divergence"] == 50
    cells = [c for c in cells if c["decoder"] != 0]
    with pytest.raises(ValueError):
        parity.summarize(cells, cfg)
