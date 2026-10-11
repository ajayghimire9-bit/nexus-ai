from __future__ import annotations

import json

from nexus.cl.linucb_strategy import ARMS, StrategyLinUCB
from nexus.cl.protocol import CONFIRM_EVAL_SEED_V066, VAL_SEED
from nexus.cl.v066 import probe_and_continue, rms_mean_shift, run_v066_benchmark
from nexus.rl.running_stats import RunningMeanStd
from nexus.tasks.cartpole_family import (
    v065_confirmation_targets,
    v066_confirmation_targets,
    v066_development_targets,
)


def test_v066_splits_are_disjoint() -> None:
    dev = {t.task_id for t in v066_development_targets()}
    conf = {t.task_id for t in v066_confirmation_targets()}
    old = {t.task_id for t in v065_confirmation_targets()}
    assert conf.isdisjoint(dev)
    assert dev == old
    assert CONFIRM_EVAL_SEED_V066 != VAL_SEED


def test_freeze_obs_rms_skips_running_update() -> None:
    from nexus.cl.v066 import make_v066_trainer
    from nexus.tasks.cartpole_family import source_policy_task

    spec = source_policy_task()
    tr = make_v066_trainer(seed=0, timesteps=128, spec=spec, freeze_obs_rms=True)
    assert tr.obs_rms is not None
    mean0 = tr.obs_rms.mean.copy()
    count0 = float(tr.obs_rms.count)
    tr.collect()
    assert float(tr.obs_rms.count) == count0
    assert (tr.obs_rms.mean == mean0).all()
    tr.close()


def test_rms_only_is_a_selector_arm() -> None:
    assert "rms_only" in ARMS
    ucb = StrategyLinUCB()
    assert "rms_only" in ucb.arms
    a = RunningMeanStd((4,))
    b = RunningMeanStd((4,))
    b.mean += 2.0
    assert rms_mean_shift(a, b) > 0


def test_probe_resumes_checkpoint(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from nexus.cl.v064 import make_v064_trainer
    from nexus.tasks.cartpole_family import source_policy_task, v066_confirmation_targets

    spec = source_policy_task()
    src = make_v064_trainer(seed=0, timesteps=128, spec=spec)
    hold = v066_confirmation_targets()[0]
    out = probe_and_continue(
        source=src,
        target=hold,
        seed=0,
        probe_steps=64,
        total_steps=128,
        eval_episodes=1,
        ckpt_dir=tmp_path,
    )
    assert out["resumed_from_probe_checkpoint"] is True
    assert out["restarted_from_scratch_after_probe"] is False
    assert out["used_confirm_for_selection"] is False
    assert out["steps_used"] == 64 * 2 + max(128 - 64 * 2, 0)
    src.close()


def test_v066_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = run_v066_benchmark(
        n_seeds=2,
        source_budgets=(256,),
        transfer_steps=128,
        probe_steps=32,
        calib_steps=16,
        eval_episodes=2,
        fit_seed_count=1,
        artifact_path=tmp_path / "v066.json",
        checkpoint_dir=tmp_path / "ckpts",
    )
    raw = (tmp_path / "v066.json").read_text()
    json.loads(raw)
    json.dumps(json.loads(raw), allow_nan=False)
    assert out["protocol"]["probe_continues_from_checkpoint"] is True
    assert out["protocol"]["v07_not_implemented"] is True
    assert out["per_seed"][0]["fit_split"] is True
    assert out["per_seed"][1]["test_split"] is True
    assert out["per_seed"][1]["targets"]["cartpole_v066_0"]["selectors"]["probe_and_continue"]["resumed_from_probe_checkpoint"] is True
    assert "B_frozen_source_rms" in out["per_seed"][0]["targets"]["cartpole_v066_0"]["norm"]
