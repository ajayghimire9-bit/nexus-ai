"""Source-only persist plan. Does not collect."""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from nexus.evolution2 import source_persist_plan as plan
from nexus.evolution2 import source_persist_request as lock


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_seed_schedule_is_disjoint_and_twelve_files():
    rows = plan.seed_schedule(3)
    assert len(rows) == 12
    assert sum(row["n"] for row in rows) == 7680
    seeds = [seed for row in rows for seed in row["env_seeds"]]
    assert len(seeds) == len(set(seeds))
    trains = {seed for row in rows if row["split"] == "train" for seed in row["env_seeds"]}
    vals = {seed for row in rows if row["split"] == "val" for seed in row["env_seeds"]}
    assert trains.isdisjoint(vals)


def test_plan_rejects_closed_physics_and_v2_promotion():
    plan.refuse_closed_physics("pendulum", (10.0, 1.0, 1.0))
    plan.refuse_closed_physics("acrobot", (1.0, 1.0, 1.0))
    with pytest.raises(RuntimeError, match="closed_or_unlisted_physics"):
        plan.refuse_closed_physics("pendulum", (8.3, 1.0, 1.0))
    with pytest.raises(RuntimeError, match="closed_or_unlisted_physics"):
        plan.refuse_closed_physics("acrobot", (0.75, 0.6, 0.95))
    assert plan.scientific_status(7680) == "development_pilot_not_confirmation"
    with pytest.raises(RuntimeError, match="n3_pilot_is_not_v2_confirmation"):
        plan.refuse_promotion_to_v2(7680)


def test_atomic_write_and_duplicate_guard(tmp_path, monkeypatch):
    path = tmp_path / "bundle0_train.npz"
    arrays = {
        "obs": np.zeros((4, 3), dtype=np.float32),
        "action": np.zeros((4,), dtype=np.int64),
        "next_obs": np.zeros((4, 3), dtype=np.float32),
        "terminated": np.zeros((4,), dtype=np.bool_),
        "env_seeds": np.arange(4, dtype=np.int64),
    }
    digest = plan.atomic_write_npz(path, arrays)
    assert path.is_file()
    assert len(digest) == 64
    assert not path.with_name(path.stem + ".partial.npz").exists()
    monkeypatch.setattr(lock, "ROOT", tmp_path)
    target = tmp_path / "artifacts" / "evolution2_source_arrays"
    target.mkdir(parents=True)
    (target / "stale.npz").write_bytes(b"x")
    with pytest.raises(RuntimeError, match="duplicate_or_partial_persist"):
        plan.refuse_duplicate_or_partial(tmp_path)


def test_plan_stays_off_the_scientific_stack():
    imported = _imports(Path(plan.__file__))
    assert "gymnasium" not in imported
    assert "nexus.world.data" not in imported
    assert "nexus.tasks.spec" not in imported
    text = Path(plan.__file__).read_text()
    assert "collect_transitions" not in text
    assert "make_task_env" not in text
