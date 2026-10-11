from __future__ import annotations

import json

from nexus.cl.linucb_strategy import StrategyLinUCB
from nexus.cl.protocol import CONFIRM_EVAL_SEED_V065, VAL_SEED
from nexus.cl.serialize import dumps_strict
from nexus.cl.v065 import run_v065_benchmark
from nexus.tasks.cartpole_family import confirmation_targets, v065_confirmation_targets, v065_development_targets


def test_v065_confirm_is_disjoint_from_v064_confirm() -> None:
    old = {t.task_id for t in confirmation_targets()}
    new = {t.task_id for t in v065_confirmation_targets()}
    dev = {t.task_id for t in v065_development_targets()}
    assert new.isdisjoint(old)
    assert new.isdisjoint(dev)
    assert old == dev
    assert CONFIRM_EVAL_SEED_V065 != VAL_SEED


def test_linucb_updates_without_confirm_seed() -> None:
    ucb = StrategyLinUCB()
    x = ucb.features(source_val=100.0, zero_shot_val=20.0, zero_shot_std=5.0, rms_shift=0.1, budget_frac=1.0)
    ucb.update("scratch", x, 0.2)
    ucb.update("encoder_new_heads_finetune", x, 0.8)
    arm = ucb.choose(x)
    assert arm in ucb.arms


def test_v065_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = run_v065_benchmark(
        n_seeds=1,
        source_budgets=(256,),
        transfer_steps=128,
        probe_steps=64,
        eval_episodes=2,
        artifact_path=tmp_path / "v065.json",
        checkpoint_dir=tmp_path / "ckpts",
    )
    raw = (tmp_path / "v065.json").read_text()
    json.loads(raw)
    json.dumps(json.loads(raw), allow_nan=False)
    assert out["protocol"]["selector_fit_uses_confirm"] is False
    assert out["protocol"]["confirm_eval_seed"] == CONFIRM_EVAL_SEED_V065
    t0 = out["per_seed"][0]["targets"]["cartpole_v065_0"]
    assert t0["ablations"]["D_pretrained_encoder_source_rms"]["copied_encoder_tensors"] > 0
    assert t0["ablations"]["A_random_encoder_fresh_rms"]["copied_encoder_tensors"] == 0
    assert t0["ablations"]["B_random_encoder_source_rms"]["rms"] == "source"
    assert t0["ablations"]["C_pretrained_encoder_fresh_rms"]["rms"] == "fresh"
    assert t0["learned_selector"]["decision"]["used_confirm"] is False
    dumps_strict(out)
