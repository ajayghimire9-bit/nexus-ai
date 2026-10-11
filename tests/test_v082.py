from __future__ import annotations

import json

import numpy as np
import pytest

from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    v081_confirmation_targets,
    v082_confirmation_targets,
    v082_development_target,
    v082_safety_ok,
    v082_sequence_tasks,
    source_policy_task,
)
from nexus.world.agent import BudgetExceededError, InteractionLedger
from nexus.world.belief import EMABelief, IdentityBelief, ScalarKalmanBelief, StackBelief, beliefs_from_dataset, make_estimator
from nexus.world.data import collect_transitions
from nexus.world.protocol import V081_CONFIRM_EVAL_SEED, V082_CONFIRM_EVAL_SEED, V082_DEV_EVAL_SEED
from nexus.world.v082 import run_v082_benchmark


def test_ledger_enforces_target_cap_not_eval() -> None:
    led = InteractionLedger(target_cap=10)
    led.charge(10, "pretrain")
    assert led.target_used == 0
    led.charge(6, "adapt_collect")
    led.charge(4, "online_val")
    assert led.target_used == 10
    led.charge(100, "eval_only")
    assert led.eval_only == 100
    assert led.snapshot()["within_cap"] is True
    with pytest.raises(BudgetExceededError):
        led.charge(1, "detect")


def test_belief_estimators_no_privileged_state() -> None:
    for est in (IdentityBelief(), EMABelief(), ScalarKalmanBelief(), StackBelief()):
        assert est.uses_privileged_state is False
        est.reset()
        b = est.observe(np.zeros(4, dtype=np.float32), 0)
        assert b.shape[-1] == est.dim
        assert "gravity" not in type(est).observe.__code__.co_varnames


def test_beliefs_from_dataset_episode_aligned() -> None:
    spec = source_policy_task()
    ds = collect_transitions(spec, n_transitions=40, env_seeds=(1, 2), base_seed=0, mix=("random",))
    out = beliefs_from_dataset(IdentityBelief(), ds)
    assert len(out) == len(ds)
    assert out.obs.shape[1] == 4
    stacked = beliefs_from_dataset(StackBelief(k=3), ds)
    assert stacked.obs.shape[1] == 12


def test_v082_confirm_seeds_and_physics_are_new() -> None:
    assert V082_CONFIRM_EVAL_SEED != V081_CONFIRM_EVAL_SEED
    assert V082_CONFIRM_EVAL_SEED != V082_DEV_EVAL_SEED
    prior = {(float(t.params["gravity"]), float(t.params["length"]), float(t.params["masspole"])) for t in v081_confirmation_targets()}
    for spec in (v082_development_target(),) + v082_sequence_tasks()[1:] + v082_confirmation_targets():
        assert v082_safety_ok(spec)
        tup = (float(spec.params["gravity"]), float(spec.params["length"]), float(spec.params["masspole"]))
        if spec.task_id != "cartpole_v082_A":
            assert tup not in prior
    noisy = [t for t in v082_confirmation_targets() if "noisy" in t.task_id]
    clean = [t for t in v082_confirmation_targets() if "clean" in t.task_id]
    assert noisy and clean
    assert all(float(t.params.get("obs_noise_std", 0)) == 0.10 for t in noisy)
    assert all(float(t.params.get("obs_noise_std", 0) or 0) == 0.0 for t in clean)


def test_make_estimator_kalman_documented() -> None:
    k = make_estimator("kalman")
    assert isinstance(k, ScalarKalmanBelief)


def test_v082_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = run_v082_benchmark(
        n_model_seeds=1,
        artifact_path=tmp_path / "v082.json",
        checkpoint_dir=tmp_path / "ck",
        quick=True,
    )
    dumps_strict(out)
    json.loads((tmp_path / "v082.json").read_text())
    assert out["protocol"]["retuned_on_confirmation"] is False
    assert out["protocol"]["inference_uses_privileged_state"] is False
    assert out["protocol"]["target_budget_enforced"] is True
    assert out["is_agi"] is False
    row = next(iter(out["per_seed"][0]["confirmation"].values()))["by_budget"]["24"]
    for v in row.values():
        assert v["within_cap"] is True
        assert v["eval_only"] >= 0
        assert v["pretrain"] > 0
