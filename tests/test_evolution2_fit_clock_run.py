"""Fit-clock runner contracts. Does not train the six residual models."""
from __future__ import annotations

import pytest

from nexus.evolution2 import fit_clock as lock
from nexus.evolution2 import fit_clock_run as run
from nexus.evolution2 import source_persist_plan as plan


def test_run_refuses_ungranted_ten_bundle_or_env_steps():
    with pytest.raises(RuntimeError, match="unauthorized"):
        run.run_clock(25600, 20)
    with pytest.raises(RuntimeError, match="fit_clock_forbids_env_steps"):
        lock.dispatch(7680, 6)


def test_recipe_and_source_are_locked_defaults():
    assert run.lock.RECIPE["module"] == "nexus.world.train.train_world_model"
    assert run.lock.RECIPE["kind"] == "residual"
    assert run.lock.RECIPE["hidden"] == [64, 64]
    assert run.lock.RECIPE["epochs"] == 20
    assert run.lock.RECIPE["n_train"] == 1024
    assert run.lock.RECIPE["n_val"] == 256
    with pytest.raises(RuntimeError, match="closed_or_unlisted_physics"):
        plan.refuse_closed_physics("pendulum", (12.1, 1.0, 1.0))
