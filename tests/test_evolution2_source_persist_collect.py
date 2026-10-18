"""Collect-module contracts. Does not run the 7680 persist."""
from __future__ import annotations

import pytest

from nexus.evolution2 import source_persist_collect as c
from nexus.evolution2 import source_persist_plan as plan


def test_collect_refuses_ungranted_ten_bundle_cap():
    with pytest.raises(RuntimeError, match="unauthorized"):
        c.run_persist(25600)


def test_authorized_7680_refuses_a_second_write():
    with pytest.raises(RuntimeError, match="duplicate_or_partial_persist"):
        c.run_persist(7680)


def test_source_spec_is_occupied_default_only():
    spec, key = c.source_spec("pendulum")
    assert spec.task_id == "pendulum_default"
    assert key == (10.0, 1.0, 1.0)
    spec, key = c.source_spec("acrobot")
    assert spec.task_id == "acrobot_default"
    assert key == (1.0, 1.0, 1.0)
    with pytest.raises(RuntimeError, match="closed_or_unlisted_physics"):
        plan.refuse_closed_physics("pendulum", (12.1, 1.0, 1.0))
