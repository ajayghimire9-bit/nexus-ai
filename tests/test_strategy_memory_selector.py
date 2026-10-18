"""Development tests for retrieved-mean / gated selection. No collection."""
from __future__ import annotations

import json

from nexus.core.strategy_memory import ContextualStrategyMemory, KERNEL_LENGTH
from nexus.core.strategy_memory_decide_bench import make_tasks
from nexus.core.strategy_memory_selector_bench import write_artifact
from nexus.evolution1.toy_loop import TrainingFeedback, VARIANTS
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2.screen import feedback_event


def test_retrieved_mean_follows_neighbors_not_linucb():
    stored = next(task for task in make_tasks() if task.task_id == "acro_store_0")
    zero = next(task for task in make_tasks() if task.task_id == "acro_zero_0")
    ucb = ContextualStrategyMemory(seed=3, mode="combined", selector="ucb")
    mean = ContextualStrategyMemory(seed=3, mode="combined", selector="retrieved_mean")
    for memory in (ucb, mean):
        memory.observe_support(stored.support, stored.context, planning_obs=stored.obs)
        memory.update(
            TrainingFeedback(VARIANTS[3].fingerprint, 1.0, False, feedback_event(stored, 0, VARIANTS[3].fingerprint)),
            stored.context,
        )
        memory.observe_support(zero.support, zero.context, planning_obs=zero.obs)
        memory.update(
            TrainingFeedback(VARIANTS[8].fingerprint, 0.9, False, feedback_event(zero, 0, VARIANTS[8].fingerprint)),
            zero.context,
        )
    mean.observe_support(zero.support, zero.context, planning_obs=zero.obs)
    ucb.observe_support(zero.support, zero.context, planning_obs=zero.obs)
    available = list(VARIANTS)
    picked = mean.choose(tuple(available), zero.context)
    ranks = mean.rank_table(available, zero.context)
    assert picked.fingerprint == VARIANTS[8].fingerprint
    assert ranks[0]["uses_retrieved_mean"] is True
    assert ranks[0]["min_dist"] <= KERNEL_LENGTH


def test_selector_bench_is_development_only_and_equal_budget():
    payload = write_artifact(7)
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["env_steps"] == 0
    assert payload["free_slots"] == 4
    assert payload["heldout_separate"] is True
    assert grant.grant_unused() is False
    assert len(set(payload["lookups"].values())) == 1
    assert payload["causal_observation_intervention"]["ucb"]["choice_changes_with_zero_obs"] is False
    assert json.loads(open("artifacts/evolution2_persist_reset_science.json").read())["primary_label"] == "inconclusive"
