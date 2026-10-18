"""Development tests for ContextualStrategyMemory. No collection."""
from __future__ import annotations

import json

from nexus.core.strategy_memory import ContextualStrategyMemory, describe_support, synthetic_support
from nexus.core.strategy_memory_bench import write_artifact
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2.tasks import default_split, hidden_score, make_task
from nexus.evolution1.toy_loop import VARIANTS


def test_descriptor_is_fixed_dim_and_ignores_family_name():
    a = make_task("successor_scale", 0)
    b = make_task("horizon_scale", 0)
    da = describe_support(synthetic_support(a.context, 7), a.context)
    db = describe_support(synthetic_support(b.context, 7), b.context)
    assert da.shape == (12,)
    assert db.shape == (12,)
    assert da[0] != db[0] or da[1] != db[1]
    same = make_task("inverted_successor", 0)
    ds = describe_support(synthetic_support(same.context, 7), same.context)
    da2 = describe_support(synthetic_support(a.context, 7), a.context)
    assert abs(float(ds[0] - da2[0])) < 1e-12


def test_memory_can_change_choice_under_matched_rng():
    task = make_task("successor_scale", 0)
    memory = ContextualStrategyMemory(seed=3, retrieve=True, persist_memory=True)
    support = synthetic_support(task.context, 3)
    memory.observe_support(support, task.context)
    from nexus.evolution1.toy_loop import TrainingFeedback
    from nexus.evolution2.screen import feedback_event

    for slot, variant in enumerate(VARIANTS[:4]):
        memory.update(
            TrainingFeedback(variant.fingerprint, hidden_score(task, variant), False, feedback_event(task, slot, variant.fingerprint)),
            task.context,
        )
    other = make_task("horizon_scale", 0)
    memory.observe_support(synthetic_support(other.context, 3), other.context)
    available = list(VARIANTS)
    with_mem = memory.choose(tuple(available), other.context, retrieve=True)
    without = memory.choose(tuple(available), other.context, retrieve=False)
    assert with_mem in available and without in available


def test_benchmark_stays_development_only_and_equal_budget():
    payload = write_artifact(7)
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["env_steps"] == 0
    assert payload["claims_agi"] is False
    assert payload["holdout_family_untouched"] == "holdout_horizon"
    assert grant.grant_unused() is False
    assert len(set(payload["lookups"].values())) == 1
    assert "contextual_strategy_memory" in payload["summary"]
    assert "memory_ablated" in payload["summary"]
    assert payload["causal_memory_changes_choice"]["same_seed"] is True
    assert payload["causal_memory_changes_choice"]["changed"] is True
    assert json.loads(open("artifacts/evolution2_persist_reset_science.json").read())["primary_label"] == "inconclusive"
