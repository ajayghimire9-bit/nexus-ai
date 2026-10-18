"""Development tests for observation-aware strategy memory. No collection."""
from __future__ import annotations

import json

import numpy as np

from nexus.core.strategy_memory import compose_descriptor, describe_planning_obs, describe_support
from nexus.core.strategy_memory_obs_bench import descriptor_diagnosis, write_artifact
from nexus.core.strategy_memory_decide_bench import make_tasks
from nexus.evolution2 import persist_reset_grant as grant


def test_planning_obs_sketch_is_fixed_and_family_safe():
    tasks = {task.task_id: task for task in make_tasks()}
    stored = tasks["acro_store_0"]
    zero = tasks["acro_zero_0"]
    pend = tasks["pend_store_0"]
    a = describe_planning_obs(stored.obs, stored.context)
    b = describe_planning_obs(zero.obs, zero.context)
    c = describe_planning_obs(pend.obs, pend.context)
    assert a.shape == b.shape == c.shape == (8,)
    assert float(np.linalg.norm(a - b)) > 0.5
    assert a[3] != 0.0 or a[2] != 0.0
    assert c[3] == 0.0 and c[4] == 0.0 and c[5] == 0.0
    again = describe_planning_obs(stored.obs, stored.context)
    assert np.allclose(a, again)


def test_support_collides_and_combined_separates_zero_obs():
    focus = descriptor_diagnosis()["focus"]
    assert focus["collision_vs_stored_support"]["distance"] < 0.2
    assert focus["collision_vs_stored_support"]["kernel_weight"] > 0.9
    assert focus["collision_vs_stored_obs"]["distance"] > focus["collision_vs_zero_obs"]["distance"]
    assert focus["collision_vs_stored_combined"]["distance"] > focus["collision_vs_stored_support"]["distance"]
    stored = next(task for task in make_tasks() if task.task_id == "acro_store_0")
    write = compose_descriptor(stored.support, stored.context, stored.obs, mode="combined")
    query = compose_descriptor(stored.support, stored.context, stored.obs, mode="combined")
    assert np.allclose(write, query)


def test_obs_bench_stays_development_only_and_equal_budget():
    payload = write_artifact(7)
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["env_steps"] == 0
    assert payload["free_slots"] == 4
    assert payload["heldout_separate"] is True
    assert grant.grant_unused() is False
    assert len(set(payload["lookups"].values())) == 1
    assert "memory_combined" in payload["summary"]
    assert "persistent_adaptive" in payload["summary"]
    assert payload["causal_observation_intervention"]["support"]["choice_changes_with_zero_obs"] is False
    assert payload["decision"]["observation_information_separates"] is True
    assert payload["decision"]["failure_source"] == "strategy_value_prediction"
    assert payload["decision"]["development_success"] is False
    assert json.loads(open("artifacts/evolution2_persist_reset_science.json").read())["primary_label"] == "inconclusive"
