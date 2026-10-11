from __future__ import annotations

import json

import numpy as np
import pytest

from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v082_confirmation_targets,
    v083_confirmation_targets,
    v083_development_target,
)
from nexus.world.adapt import WindowThresholdDetector
from nexus.world.agent import BudgetExceededError, InteractionLedger, collect_planned_belief
from nexus.world.belief import IdentityBelief
from nexus.world.dynamics import WorldModel
from nexus.world.online import run_online_learning
from nexus.world.protocol import V082_CONFIRM_EVAL_SEED, V083_CONFIRM_EVAL_SEED, V083_DEV_EVAL_SEED
from nexus.world.v083 import run_v083_benchmark


def test_ledger_no_double_count_or_silent_omit() -> None:
    led = InteractionLedger(target_cap=20)
    led.charge(5, "pretrain")
    led.charge(4, "detect")
    led.charge(6, "adapt_collect")
    led.charge(3, "online_val")
    led.charge(11, "eval_only")
    snap = led.snapshot()
    assert snap["target_used"] == 13
    assert snap["bucket_sum"] == 13
    assert snap["no_double_count"] is True
    assert snap["pretrain"] == 5
    assert snap["eval_only"] == 11
    assert snap["within_cap"] is True
    with pytest.raises(BudgetExceededError):
        led.charge(8, "detect")
    with pytest.raises(ValueError):
        led.charge(1, "mystery")


def test_zero_collect_does_not_touch_env() -> None:
    spec = source_policy_task()
    wm = WorldModel.create(4, 2, kind="residual", seed=0)
    ds = collect_planned_belief(spec, wm, IdentityBelief(), 0, env_seeds=(1,), base_seed=0)
    assert ds.env_interactions == 0
    assert len(ds) == 0


def test_v083_confirm_is_new() -> None:
    assert V083_CONFIRM_EVAL_SEED != V082_CONFIRM_EVAL_SEED
    assert V083_CONFIRM_EVAL_SEED != V083_DEV_EVAL_SEED
    prior = {(float(t.params["gravity"]), float(t.params["length"]), float(t.params["masspole"])) for t in v082_confirmation_targets()}
    for spec in v083_confirmation_targets() + (v083_development_target(),):
        tup = (float(spec.params["gravity"]), float(spec.params["length"]), float(spec.params["masspole"]))
        assert tup not in prior
    noisy = [t for t in v083_confirmation_targets() if "noisy" in t.task_id]
    clean = [t for t in v083_confirmation_targets() if "clean" in t.task_id]
    assert noisy and clean


def test_online_never_respects_cap(tmp_path) -> None:  # type: ignore[no-untyped-def]
    del tmp_path
    spec = source_policy_task()
    from nexus.world.data import collect_transitions
    from nexus.world.train import train_world_model

    tr = collect_transitions(spec, n_transitions=32, env_seeds=(1, 2), base_seed=0, mix=("random",))
    va = collect_transitions(spec, n_transitions=16, env_seeds=(8, 9), base_seed=1, mix=("random",))
    wm, _ = train_world_model(tr, va, kind="residual", epochs=1, seed=0)
    det = WindowThresholdDetector()
    det.fit(np.random.default_rng(0).normal(0.01, 0.002, size=40))
    out = run_online_learning(spec, wm, tr, IdentityBelief(), target_cap=12, policy="never", epochs=1, seed=0, detector=det)
    assert out["ledger"]["target_used"] == 12
    assert out["ledger"]["no_double_count"] is True
    assert out["ledger"]["buckets"]["adapt_collect"] == 0
    assert out["gru_in_mpc"] is False
    assert out["n_commit"] == 0


def test_v083_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = run_v083_benchmark(n_model_seeds=1, artifact_path=tmp_path / "v083.json", checkpoint_dir=tmp_path / "ck", quick=True)
    dumps_strict(out)
    json.loads((tmp_path / "v083.json").read_text())
    assert out["protocol"]["gru_in_mpc"] is False
    assert out["protocol"]["retuned_on_confirmation"] is False
    assert out["protocol"]["target_budget_enforced"] is True
    row = next(iter(out["per_seed"][0]["confirmation"].values()))["by_budget"]["24"]["never"]
    assert row["ledger"]["no_double_count"] is True
    assert row["ledger"]["eval_only"] >= 0
