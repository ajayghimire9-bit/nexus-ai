from __future__ import annotations

import json

from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v086_confirmation_targets,
    v086_development_target,
    v087_confirmation_targets,
    v087_development_target,
)
from nexus.world.data import collect_transitions
from nexus.world.dynamics import WorldModel
from nexus.world.protocol import V086_CONFIRM_REF_SEED, V087_CONFIRM_EVAL_SEED, V087_DEV_EVAL_SEED, V087_GATE_SEED
from nexus.world.v087 import BANK_TRAIN, BANK_VAL, SPLIT_TRAIN, SPLIT_VAL, paired_control_eval, run_online_cycles, run_v087_benchmark
from nexus.world.verify import V085_MAE_RATIO, weights_hash


def test_paired_eval_uses_identical_seed() -> None:
    spec = source_policy_task()
    a = WorldModel.create(4, 2, kind="residual", seed=0)
    b = a.clone()
    ev = paired_control_eval(spec, {"x": a, "y": b}, seed=7, episodes=1)
    assert ev["x"]["mean_return"] == ev["y"]["mean_return"]
    assert ev["x"]["env_interactions"] == ev["y"]["env_interactions"]


def test_split_vs_bank_train_sizes() -> None:
    assert SPLIT_TRAIN < BANK_TRAIN
    assert SPLIT_VAL < BANK_VAL
    spec = source_policy_task()
    src = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=16, env_seeds=(1,), base_seed=0, mix=("random",))
    split = run_online_cycles(spec, src, tr, "low_lr", target_cap=128, epochs=1, seed=0, gate="mae", train_n=SPLIT_TRAIN, val_n=SPLIT_VAL, max_cycles=1, adapt_seed=1, gate_seed=2)
    assert split["train_n"] == SPLIT_TRAIN
    bankish = run_online_cycles(spec, src, tr, "low_lr", target_cap=256, epochs=1, seed=0, gate="mae", train_n=BANK_TRAIN, val_n=BANK_VAL, max_cycles=1, adapt_seed=1, gate_seed=2)
    assert bankish["train_n"] == BANK_TRAIN
    if split["cycles"] and bankish["cycles"]:
        assert split["cycles"][0]["train_n"] <= SPLIT_TRAIN
        assert bankish["cycles"][0]["train_n"] >= split["cycles"][0]["train_n"]


def test_always_commits_never_does_not() -> None:
    spec = source_policy_task()
    src = WorldModel.create(4, 2, kind="residual", seed=1)
    tr = collect_transitions(spec, n_transitions=16, env_seeds=(1,), base_seed=0, mix=("random",))
    h0 = weights_hash(src)
    never = run_online_cycles(spec, src, tr, "low_lr", target_cap=40, epochs=1, seed=3, gate="never", train_n=16, val_n=8, max_cycles=2, adapt_seed=0, gate_seed=0)
    always = run_online_cycles(spec, src, tr, "low_lr", target_cap=40, epochs=1, seed=3, gate="always", train_n=16, val_n=8, max_cycles=1, adapt_seed=0, gate_seed=0)
    assert never["n_accept"] == 0
    assert never["committed_hash"] == h0
    assert always["n_accept"] == 1
    assert always["committed_hash"] != h0
    assert always["ledger"]["target_used"] <= 40
    assert never["ledger"]["within_cap"] and always["ledger"]["within_cap"]


def test_zero_cap_no_env() -> None:
    spec = source_policy_task()
    src = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=8, env_seeds=(1,), base_seed=0, mix=("random",))
    out = run_online_cycles(spec, src, tr, "low_lr", target_cap=0, epochs=1, seed=0, gate="mae", train_n=16, val_n=8, max_cycles=1, adapt_seed=0, gate_seed=0)
    assert out["ledger"]["target_used"] == 0
    assert out["n_propose"] == 0


def test_mae_not_retuned() -> None:
    assert V085_MAE_RATIO == 0.97


def test_v087_physics_and_seeds_are_new() -> None:
    assert V087_CONFIRM_EVAL_SEED != V086_CONFIRM_REF_SEED
    assert V087_CONFIRM_EVAL_SEED != V087_DEV_EVAL_SEED
    assert V087_GATE_SEED != V087_CONFIRM_EVAL_SEED
    prior = {
        (float(t.params["gravity"]), float(t.params["length"]), float(t.params["masspole"]))
        for t in v086_confirmation_targets() + (v086_development_target(),)
    }
    for spec in v087_confirmation_targets() + (v087_development_target(),):
        tup = (float(spec.params["gravity"]), float(spec.params["length"]), float(spec.params["masspole"]))
        assert tup not in prior


def test_v087_quick_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    art = tmp_path / "v087.json"
    out = run_v087_benchmark(n_model_seeds=1, quick=True, artifact_path=str(art), checkpoint_dir=str(tmp_path / "ck"))
    assert art.exists()
    json.loads(art.read_text())
    dumps_strict(out)
    assert out["protocol"]["retuned_mae"] is False
    assert out["protocol"]["paired_eval"] is True
    assert out["protocol"]["reference_feeds_gate"] is False
    assert "bank" in out["ablation"]["accept_rate"]
    pol = out["per_seed"][0]["confirmation"]
    tid = next(iter(pol))
    assert "mae_low_lr" in pol[tid]["policies"]
    assert pol[tid]["policies"]["never"]["planning"]["mean_return"] == pol[tid]["policies"]["snapshot"]["planning"]["mean_return"]
    seq = out["per_seed"][0]["continual"]
    assert seq[-1]["stage"] == "A_return"
    assert "hashes" in pol[tid]["policies"]["mae_low_lr"]
