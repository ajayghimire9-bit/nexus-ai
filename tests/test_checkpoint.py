from __future__ import annotations

from pathlib import Path

from nexus.tasks.cartpole_family import source_policy_task
from nexus.world.adapt import WindowThresholdDetector, per_transition_mae
from nexus.world.data import collect_transitions
from nexus.world.dynamics import WorldModel
from nexus.world.v089 import (
    BUDGETS,
    V085_MAE_RATIO,
    run_mae_persistent,
    run_mae_rejection_audit,
    validate_v089_artifact,
    weight_l2_delta,
)
from nexus.world.verify import V085_MAE_RATIO as GATE_RATIO


def test_frozen_gate_unchanged() -> None:
    assert GATE_RATIO == 0.97
    assert V085_MAE_RATIO == 0.97


def test_v089_artifact_protocol() -> None:
    path = Path("artifacts/v089_learning.json")
    assert path.exists()
    v = validate_v089_artifact(path)
    assert v["ok"], v["issues"]
    assert v["is_agi"] is False
    assert v["protocol_hash"] == "e10d512ec0a20f05"


def test_learning_curve_budgets_and_pairing() -> None:
    import json

    p = json.loads(Path("artifacts/v089_learning.json").read_text())
    assert p["learning_curve"]["budgets"] == list(BUDGETS)
    eval_seed = p["protocol"]["confirm_eval_seed"]
    for s in p["per_seed"]:
        assert set(s["curve"].keys()) == {str(b) for b in BUDGETS}
        assert s["pretrain"] == 1328
        led = s["mae_online"]["ledger"]
        assert led["bucket_sum"] == led["target_used"]
        assert led["buckets"]["detect"] + led["buckets"]["adapt_collect"] + led["buckets"]["online_val"] == led["target_used"]
    assert eval_seed == 156000
    assert p["protocol"]["dev_eval_seed"] != eval_seed


def test_weight_l2_zero_on_clone() -> None:
    a = WorldModel.create(4, 2, kind="residual", seed=0)
    assert weight_l2_delta(a, a.clone()) == 0.0


def test_audit_does_not_accept_by_changing_gate() -> None:
    spec = source_policy_task()
    src = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=16, env_seeds=(1,), base_seed=0, mix=("random",))
    det = WindowThresholdDetector(window=8, k=3.0)
    det.fit(per_transition_mae(src, tr.obs, tr.action, tr.next_obs))
    det.threshold = -1.0
    props: list = []
    out = run_mae_persistent(
        spec, src, tr, cap=80, epochs=1, seed=1, adapt_seed=2, gate_seed=3, detector=det,
        train_n=16, val_n=8, snapshots_at=(0, 80), proposals_out=props,
    )
    assert GATE_RATIO == 0.97
    for pr in props:
        assert pr["gate_ratio_threshold"] == 0.97
        assert pr["eval_feeds_gate"] is False
        assert "control_delta" in pr
    assert out["ledger"]["no_double_count"]


def test_quick_mae_audit() -> None:
    out = run_mae_rejection_audit(n_model_seeds=1, artifact_path=None, quick=True)
    assert out["protocol"]["retuned_mae"] is False
    assert out["protocol"]["mae_ratio"] == 0.97
    assert out["protocol"]["eval_feeds_gate"] is False
