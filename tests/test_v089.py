from __future__ import annotations

from nexus.tasks.cartpole_family import (
    source_policy_task,
    v088_confirmation_targets,
    v088_development_target,
    v089_confirmation_targets,
    v089_development_target,
    v089_sequence_tasks,
)
from nexus.world.adapt import WindowThresholdDetector, per_transition_mae
from nexus.world.data import collect_transitions
from nexus.world.dynamics import WorldModel
from nexus.world.protocol import V088_CONFIRM_EVAL_SEED, V089_CONFIRM_EVAL_SEED, V089_DEV_EVAL_SEED, V089_GATE_SEED
from nexus.world.session import PersistentSession
from nexus.world.v089 import BUDGETS, STAGE_CAP, TRAIN_N, VAL_N, _auc, fail_tail_mae, run_detection_compare, run_mae_persistent, run_v089_benchmark
from nexus.world.verify import V085_MAE_RATIO, V085_MAE_STEPS, weights_hash


def _src():
    spec = source_policy_task()
    src = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=16, env_seeds=(1,), base_seed=0, mix=("random",))
    det = WindowThresholdDetector(window=8, k=3.0)
    det.fit(per_transition_mae(src, tr.obs, tr.action, tr.next_obs))
    return spec, src, tr, det


def test_mae_not_retuned() -> None:
    assert V085_MAE_RATIO == 0.97
    assert BUDGETS[0] == 0
    assert 1024 in BUDGETS
    assert STAGE_CAP == TRAIN_N + VAL_N + V085_MAE_STEPS


def test_v089_physics_and_seeds_are_new() -> None:
    assert V089_CONFIRM_EVAL_SEED != V088_CONFIRM_EVAL_SEED
    assert V089_CONFIRM_EVAL_SEED != V089_DEV_EVAL_SEED
    assert V089_GATE_SEED != V089_CONFIRM_EVAL_SEED
    prior = {
        (float(t.params["gravity"]), float(t.params["length"]), float(t.params["masspole"]))
        for t in v088_confirmation_targets() + (v088_development_target(),)
    }
    for spec in v089_confirmation_targets() + (v089_development_target(),) + v089_sequence_tasks():
        key = (float(spec.params["gravity"]), float(spec.params["length"]), float(spec.params["masspole"]))
        assert key not in prior, spec.task_id


def test_persistent_chunks_do_not_reset_mid_episode() -> None:
    spec, src, _tr, _det = _src()
    sess = PersistentSession(spec, src, env_seed=3, plan_seed=4)
    ds1 = sess.collect(6)
    ds2 = sess.collect(6)
    if not bool(ds1.terminated[-1]) and not bool(ds1.truncated[-1]):
        assert int(ds2.episode_id[0]) == int(ds1.episode_id[-1])
    assert sess.n_scheduled_switches == 0
    assert sess.n_resets == 1 + sess.n_term_resets
    assert sess.interactions == 12
    sess.close()


def test_scheduled_task_switch_is_explicit() -> None:
    spec, src, _tr, _det = _src()
    other = v089_development_target()
    sess = PersistentSession(spec, src, env_seed=5, plan_seed=6)
    sess.collect(4)
    sess.switch_task(other, env_seed=9)
    assert sess.n_scheduled_switches == 1
    ds = sess.collect(4)
    assert ds.task_id == other.task_id
    sess.close()


def test_set_model_keeps_episode() -> None:
    spec, src, _tr, _det = _src()
    sess = PersistentSession(spec, src, env_seed=1, plan_seed=2)
    sess.collect(3)
    ep = sess.episode_id
    prev = sess.prev_a
    other = src.clone()
    sess.set_model(other)
    assert sess.episode_id == ep
    assert sess.prev_a == prev
    sess.close()


def test_detection_does_not_use_train_data() -> None:
    spec, src, _tr, det = _src()
    tgt = v089_development_target()
    out = run_detection_compare(spec, tgt, src, det, seed=2, n_source=16, n_target=16, recalib_n=8)
    assert out["used_train_for_detection"] is False
    assert "fixed" in out["fpr"] and "recalib" in out["target"] and "trend" in out["target"]
    assert out["n_scheduled_switches"] == 1


def test_mae_persistent_respects_budget() -> None:
    spec, src, tr, det = _src()
    det.threshold = -1.0
    out = run_mae_persistent(
        spec, src, tr, cap=40, epochs=1, seed=1, adapt_seed=2, gate_seed=3, detector=det,
        train_n=16, val_n=8, snapshots_at=(0, 40),
    )
    assert out["ledger"]["target_used"] <= 40
    assert out["ledger"]["within_cap"]
    assert out["ledger"]["no_double_count"]
    assert 0 in out["snapshots"]


def test_fail_tail_and_auc() -> None:
    spec, src, tr, _det = _src()
    m = fail_tail_mae(src, tr, k=4)
    assert m is None or m >= 0.0
    assert _auc([0, 64, 128], [1.0, 2.0, 2.0]) > 0


def test_update_consistency_hash() -> None:
    spec, src, tr, det = _src()
    h0 = weights_hash(src)
    det.threshold = 1e9
    out = run_mae_persistent(
        spec, src, tr, cap=16, epochs=1, seed=0, adapt_seed=0, gate_seed=0, detector=det,
        train_n=32, val_n=8, snapshots_at=(0, 16),
    )
    assert out["n_accept"] == 0
    assert out["committed_hash"] == h0


def test_quick_benchmark() -> None:
    out = run_v089_benchmark(n_model_seeds=1, artifact_path=None, checkpoint_dir="checkpoints/v089_test", quick=True)
    assert out["protocol"]["mae_ratio"] == 0.97
    assert out["protocol"]["retuned_mae"] is False
    assert out["protocol"]["is_agi"] is False
    assert "learning_curve" in out
    assert "transfer" in out
    assert "detection" in out
