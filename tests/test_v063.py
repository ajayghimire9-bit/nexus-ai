from __future__ import annotations

import pytest

from nexus.cl.protocol import HOLDOUT_EVAL_SEED, INDEPENDENT_SEED, VAL_SEED
from nexus.cl.selector import (
    CONSERVATIVE_VAL_THRESHOLD,
    REUSE_VAL_THRESHOLD,
    AdaptationSelector,
)
from nexus.cl.v063 import run_v063_benchmark
from nexus.tasks.cartpole_family import (
    development_targets,
    final_test_targets,
    source_policy_task,
    source_tasks,
)
from nexus.tasks.spec import make_task_env


def _limits(steps: int = 4096) -> dict:
    return {
        "val_seed": VAL_SEED,
        "independent_eval_seed": INDEPENDENT_SEED,
        "eval_episodes": 8,
        "max_target_steps": steps,
    }


def test_dev_and_final_test_are_disjoint() -> None:
    src = source_policy_task().task_id
    dev = {t.task_id for t in development_targets()}
    final = {t.task_id for t in final_test_targets()}
    assert src not in dev and src not in final
    assert dev.isdisjoint(final)
    assert "cartpole_lowg" in dev
    assert final == {"cartpole_short", "cartpole_highg", "cartpole_longheavy"}
    for t in list(development_targets()) + list(final_test_targets()) + list(source_tasks()):
        assert t.compatible_with(source_policy_task())
        assert t.obs_dim == 4 and t.n_actions == 2


def test_new_physics_params_apply() -> None:
    env = make_task_env(final_test_targets()[1], seed=0)  # highg
    try:
        assert abs(float(env.unwrapped.gravity) - 14.7) < 1e-6
    finally:
        env.close()


def test_selector_uses_val_thresholds_not_test() -> None:
    sel = AdaptationSelector(max_target_steps=4096, limits=_limits())
    reuse = sel.decide(zero_shot_val=REUSE_VAL_THRESHOLD + 1, source_val=400.0, current_limits=_limits())
    assert reuse.strategy == "reuse" and reuse.target_steps == 0
    cons = sel.decide(zero_shot_val=CONSERVATIVE_VAL_THRESHOLD + 1, source_val=200.0, current_limits=_limits())
    assert cons.strategy == "conservative_low_lr"
    enc = sel.decide(zero_shot_val=10.0, source_val=200.0, current_limits=_limits())
    assert enc.strategy == "encoder_new_heads_finetune"
    scratch = sel.decide(zero_shot_val=10.0, source_val=10.0, current_limits=_limits())
    assert scratch.strategy == "scratch"


def test_selector_cannot_change_eval_limits() -> None:
    sel = AdaptationSelector(max_target_steps=4096, limits=_limits())
    bad = {**_limits(), "independent_eval_seed": HOLDOUT_EVAL_SEED}
    with pytest.raises(RuntimeError):
        sel.decide(zero_shot_val=10.0, source_val=200.0, current_limits=bad)


def test_v063_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = run_v063_benchmark(
        n_seeds=1,
        source_budgets=(256,),
        transfer_steps=128,
        eval_episodes=2,
        artifact_path=tmp_path / "v063.json",
        checkpoint_dir=tmp_path / "ckpts",
    )
    assert out["protocol"]["selector_sees_final_test_returns"] is False
    assert out["protocol"]["selection_uses_independent"] is False
    assert out["source"]["selection_uses_independent"] is False
    tgt = out["per_seed"][0]["targets"]
    assert "cartpole_highg" in tgt
    assert tgt["cartpole_highg"]["split"] == "test"
    assert tgt["cartpole_lowg"]["split"] == "dev"
    dec = tgt["cartpole_highg"]["selector"]["decision"]
    assert dec["used_independent_or_holdout_for_decision"] is False
    assert "source_before" in tgt["cartpole_highg"]["fixed"]["full_finetune"]
    assert (tmp_path / "v063.json").exists()
