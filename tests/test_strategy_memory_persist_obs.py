"""Development tests for persist+obs. No collection."""
from __future__ import annotations

import json

from nexus.core.persist_obs import FEATURE_DIM, PersistentAdaptiveObs, persist_obs_features
from nexus.core.strategy_memory_decide_bench import make_tasks
from nexus.core.strategy_memory_persist_obs_bench import write_artifact
from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2.methods import PersistentAdaptive


def test_historical_persist_stays_six_weights():
    persist = PersistentAdaptive(seed=7)
    assert len(persist.learned_state()["weights"]) == 6
    assert persist.name == "persistent_adaptive"


def test_persist_obs_features_are_variant_dependent():
    tasks = {task.task_id: task for task in make_tasks()}
    stored = tasks["acro_store_0"]
    zero = tasks["acro_zero_0"]
    method = PersistentAdaptiveObs(seed=3)
    method.observe_planning_obs(stored.obs, stored.context)
    from nexus.evolution1.toy_loop import VARIANTS

    flat = persist_obs_features(VARIANTS[0], stored.context, method._sketch)
    succ = persist_obs_features(VARIANTS[8], stored.context, method._sketch)
    assert len(flat) == FEATURE_DIM == 22
    assert flat != succ
    method.observe_planning_obs(zero.obs, zero.context)
    succ_zero = persist_obs_features(VARIANTS[8], zero.context, method._sketch)
    assert succ != succ_zero


def test_persist_obs_bench_is_development_only(tmp_path,monkeypatch):
    monkeypatch.setattr(f'{write_artifact.__module__}.RESULTS',tmp_path/'fixture.json')
    payload = write_artifact(7)
    assert payload["scientific"] is False
    assert payload["collection"] is False
    assert payload["env_steps"] == 0
    assert payload["decision"]["historical_persist_weights"] == 6
    assert payload["decision"]["causal_persist_stable"] is True
    assert grant.grant_unused() is False
    assert len(set(payload["lookups"].values())) == 1
    assert json.loads(open("artifacts/evolution2_persist_reset_science.json").read())["primary_label"] == "inconclusive"
