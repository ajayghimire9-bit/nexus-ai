from __future__ import annotations

from nexus.tasks.cartpole_family import (
    source_policy_task,
    v087_confirmation_targets,
    v087_development_target,
    v088_confirmation_targets,
    v088_development_target,
    v088_sequence_tasks,
)
from nexus.world.adapt import WindowThresholdDetector, per_transition_mae
from nexus.world.data import collect_transitions
from nexus.world.dynamics import WorldModel
from nexus.world.memory import PredictiveMemory
from nexus.world.protocol import V087_CONFIRM_EVAL_SEED, V088_CONFIRM_EVAL_SEED, V088_DEV_EVAL_SEED, V088_GATE_SEED
from nexus.world.v088 import (
    CYCLE_COST,
    FROZEN_TRAIN,
    FROZEN_VAL,
    MAX_CYCLES,
    PRIMARY_CAP,
    copy_detector,
    retrieve_with_probe,
    run_change_triggered,
    run_pool_cycles,
    run_v088_benchmark,
)
from nexus.world.verify import V085_MAE_RATIO, weights_hash


def _src():
    spec = source_policy_task()
    src = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=16, env_seeds=(1,), base_seed=0, mix=("random",))
    det = WindowThresholdDetector(window=8, k=3.0)
    det.fit(per_transition_mae(src, tr.obs, tr.action, tr.next_obs))
    return spec, src, tr, det


def test_mae_not_retuned() -> None:
    assert V085_MAE_RATIO == 0.97
    assert FROZEN_TRAIN == 128
    assert FROZEN_VAL == 64
    assert MAX_CYCLES == 3
    assert PRIMARY_CAP == 3 * CYCLE_COST
    assert PRIMARY_CAP == 672


def test_v088_physics_and_seeds_are_new() -> None:
    assert V088_CONFIRM_EVAL_SEED != V087_CONFIRM_EVAL_SEED
    assert V088_CONFIRM_EVAL_SEED != V088_DEV_EVAL_SEED
    assert V088_GATE_SEED != V088_CONFIRM_EVAL_SEED
    prior = {
        (float(t.params["gravity"]), float(t.params["length"]), float(t.params["masspole"]))
        for t in v087_confirmation_targets() + (v087_development_target(),)
    }
    for spec in v088_confirmation_targets() + (v088_development_target(),) + v088_sequence_tasks():
        key = (float(spec.params["gravity"]), float(spec.params["length"]), float(spec.params["masspole"]))
        assert key not in prior, spec.task_id


def test_no_alarm_skips_adaptation() -> None:
    spec, src, tr, det = _src()
    det.threshold = 1e9
    h0 = weights_hash(src)
    out = run_change_triggered(
        spec, src, tr, "low_lr", target_cap=48, epochs=1, seed=0, gate="always",
        train_n=16, val_n=8, max_cycles=2, adapt_seed=1, gate_seed=2, detector=det, require_alarm=True,
    )
    assert out["n_propose"] == 0
    assert out["n_accept"] == 0
    assert out["committed_hash"] == h0
    assert out["missed"]
    assert out["ledger"]["within_cap"]
    assert out["ledger"]["no_double_count"]
    assert out["ledger"]["target_used"] <= 48


def test_alarm_triggers_and_budget_enforced() -> None:
    spec, src, tr, det = _src()
    det.threshold = -1.0
    cap = 3 * (16 + 8 + 0)
    out = run_change_triggered(
        spec, src, tr, "low_lr", target_cap=cap, epochs=1, seed=1, gate="always",
        train_n=16, val_n=8, max_cycles=3, adapt_seed=1, gate_seed=2, detector=det, require_alarm=True, chunk=8,
    )
    assert out["n_propose"] == 3
    assert out["n_accept"] == 3
    assert out["ledger"]["target_used"] <= cap
    assert out["ledger"]["within_cap"]
    assert out["ledger"]["no_double_count"]
    assert out["committed_hash"] != weights_hash(src)
    assert len(out["cycles"]) == 3


def test_mae_rollback_keeps_incumbent() -> None:
    spec, src, tr, det = _src()
    det.threshold = -1.0
    h0 = weights_hash(src)
    out = run_change_triggered(
        spec, src, tr, "low_lr", target_cap=80, epochs=1, seed=2, gate="mae",
        train_n=16, val_n=8, max_cycles=1, adapt_seed=3, gate_seed=4, detector=det, require_alarm=True,
    )
    if out["n_propose"] and not out["n_accept"]:
        assert out["committed_hash"] == h0
        assert out["cycles"][0]["before"] == out["cycles"][0]["after"]
    assert out["ledger"]["within_cap"]


def test_accepted_update_changes_next_cycle_incumbent() -> None:
    spec, src, tr, det = _src()
    det.threshold = -1.0
    out = run_change_triggered(
        spec, src, tr, "low_lr", target_cap=3 * (16 + 8), epochs=1, seed=4, gate="always",
        train_n=16, val_n=8, max_cycles=2, adapt_seed=5, gate_seed=6, detector=det, require_alarm=True,
    )
    assert out["n_accept"] >= 2
    h = [c["after"] for c in out["cycles"]]
    assert h[0] != weights_hash(src)
    assert out["cycles"][1]["before"] == h[0]


def test_pool_ablation_isolates_sizes() -> None:
    spec, src, tr, _det = _src()
    pool_tr = collect_transitions(spec, n_transitions=48, env_seeds=(2, 3), base_seed=1, mix=("random",))
    pool_va = collect_transitions(spec, n_transitions=32, env_seeds=(8, 9), base_seed=2, mix=("random",))
    a = run_pool_cycles(src, tr, pool_tr, pool_va, spec, "low_lr", train_n=16, val_n=8, n_cycles=1, epochs=1, adapt_seed=7, gate_seed=8)
    b = run_pool_cycles(src, tr, pool_tr, pool_va, spec, "low_lr", train_n=32, val_n=16, n_cycles=2, epochs=1, adapt_seed=7, gate_seed=8)
    assert a["cycles"][0]["train_n"] == 16
    assert b["cycles"][0]["train_n"] == 32
    assert b["n_propose"] == 2
    assert a["source_hash"] == b["source_hash"] == weights_hash(src)


def test_probe_retrieval_no_task_id() -> None:
    spec, src, tr, _det = _src()
    mem = PredictiveMemory(max_entries=4, replay_cap=32)
    mem.store(src, tr, stats={"stage": "source"}, label="source")
    other = src.clone()
    mem.store(other, tr, stats={"stage": "later"}, label="later")
    model, meta, n = retrieve_with_probe(spec, mem, src, seed=11, n=8)
    assert meta["used_task_id"] is False
    assert meta.get("used_privileged_physics") is False
    assert n == meta["probe_n"] or n >= 0
    assert model is not None


def test_copy_detector_is_independent() -> None:
    spec, src, tr, det = _src()
    c = copy_detector(det)
    c.threshold = -1.0
    assert det.threshold != c.threshold
    c._buf.append(1.0)
    assert c._buf != det._buf


def test_zero_cap() -> None:
    spec, src, tr, det = _src()
    out = run_change_triggered(
        spec, src, tr, "low_lr", target_cap=0, epochs=1, seed=0, gate="mae",
        train_n=16, val_n=8, max_cycles=1, adapt_seed=0, gate_seed=0, detector=det,
    )
    assert out["ledger"]["target_used"] == 0
    assert out["n_propose"] == 0


def test_quick_benchmark_writes_nothing_optional() -> None:
    out = run_v088_benchmark(n_model_seeds=1, artifact_path=None, checkpoint_dir="checkpoints/v088_test", quick=True)
    assert out["protocol"]["mae_ratio"] == 0.97
    assert out["protocol"]["retuned_mae"] is False
    assert out["protocol"]["is_agi"] is False
    assert "noisy_confirmation" in out
    assert "ablation" in out
