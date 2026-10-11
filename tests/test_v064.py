from __future__ import annotations

import pytest

from nexus.cl.metrics import paired_seed_deltas, seed_level_ci
from nexus.cl.protocol import CONFIRM_EVAL_SEED, HOLDOUT_EVAL_SEED, INDEPENDENT_SEED, VAL_SEED
from nexus.cl.selector import FROZEN_LIMIT_KEYS, RiskAwareSelector
from nexus.cl.v064 import run_v064_benchmark
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION


def test_seed_level_ci_is_not_task_flattened() -> None:
    fake = {
        0: {"a": {"sel": 10.0, "scratch": 1.0}, "b": {"sel": 12.0, "scratch": 2.0}, "c": {"sel": 8.0, "scratch": 0.0}},
        1: {"a": {"sel": 20.0, "scratch": 10.0}, "b": {"sel": 22.0, "scratch": 11.0}, "c": {"sel": 18.0, "scratch": 9.0}},
    }
    out = paired_seed_deltas(per_seed_task=fake, treatment="sel", baseline="scratch")
    assert out["n_seeds"] == 2
    assert out["across_seeds"]["n"] == 2
    assert out["across_seeds"]["interval"] == "student_t_95"
    assert out["across_seeds"]["df"] == 1
    assert abs(out["per_seed_mean_delta"][0] - 9.0) < 1e-9
    assert abs(out["per_seed_mean_delta"][1] - 10.0) < 1e-9
    lo, hi = seed_level_ci([9.0, 10.0])["lo"], seed_level_ci([9.0, 10.0])["hi"]
    assert lo < 9.5 < hi


def test_confirm_seed_differs_from_val() -> None:
    assert len({VAL_SEED, INDEPENDENT_SEED, HOLDOUT_EVAL_SEED, CONFIRM_EVAL_SEED}) == 4


def test_risk_selector_frozen_limits() -> None:
    limits = {k: 1 for k in FROZEN_LIMIT_KEYS}
    limits.update({"val_seed": VAL_SEED, "independent_eval_seed": INDEPENDENT_SEED, "eval_episodes": 8, "max_target_steps": 4096})
    sel = RiskAwareSelector(max_target_steps=4096, limits=limits)
    with pytest.raises(RuntimeError):
        sel.decide(zero_shot_val=10.0, source_val=200.0, current_limits={**limits, "max_target_steps": 99})
    d = sel.decide(zero_shot_val=400.0, source_val=400.0, current_limits=limits)
    assert d.strategy == "reuse"
    d2 = sel.decide(zero_shot_val=10.0, source_val=10.0, current_limits=limits)
    assert d2.strategy == "scratch"


def test_v064_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = run_v064_benchmark(
        n_seeds=1,
        source_budgets=(256,),
        transfer_steps=256,
        eval_episodes=2,
        curve_points=(0, 256),
        artifact_path=tmp_path / "v064.json",
        checkpoint_dir=tmp_path / "ckpts",
    )
    assert out["protocol"]["physics_version"] == CARTPOLE_PHYSICS_VERSION
    assert out["protocol"]["selector_sees_confirm"] is False
    assert out["protocol"]["replication_unit"] == "source_training_seed"
    assert out["summary"]["all_seeds"]["scratch"]["n"] == 1
    assert "cartpole_confirm_0" in out["per_seed"][0]["targets"]
    ret = out["per_seed"][0]["targets"]["cartpole_confirm_0"]["fixed"]["encoder_new_heads_finetune"]["retention"]
    assert ret["retention_defined"] is False
    same = out["per_seed"][0]["targets"]["cartpole_confirm_0"]["fixed"]["conservative_low_lr"]["retention"]
    assert same["retention_defined"] is True
    assert (tmp_path / "v064.json").exists()
