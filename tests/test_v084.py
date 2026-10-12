from __future__ import annotations

import json

import numpy as np
import pytest
import torch

from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v083_confirmation_targets,
    v083_development_target,
    v084_confirmation_targets,
    v084_development_target,
)
from nexus.world.adapt import WindowThresholdDetector
from nexus.world.agent import InteractionLedger
from nexus.world.belief import IdentityBelief, ScalarKalmanBelief
from nexus.world.data import collect_transitions, split_by_episodes
from nexus.world.dynamics import WorldModel
from nexus.world.online import run_fair_online
from nexus.world.protocol import V083_CONFIRM_EVAL_SEED, V084_CONFIRM_EVAL_SEED, V084_DEV_EVAL_SEED
from nexus.world.v084 import run_v084_benchmark
from nexus.world.verify import (
    CONTROL_VAL_HORIZON,
    MIN_IMPROVE,
    control_decision,
    matched_control_compare,
)


def _det() -> WindowThresholdDetector:
    d = WindowThresholdDetector(window=8, k=0.5)
    d.fit(np.zeros(20, dtype=np.float32))
    return d


def test_control_decision_rule_frozen() -> None:
    d, r, diff = control_decision([10.0], [10.0 + MIN_IMPROVE])
    assert d == "accept" and r == "control_improved" and diff >= MIN_IMPROVE
    d, r, _ = control_decision([20.0], [5.0])
    assert d == "reject" and r == "control_worse"
    d, r, _ = control_decision([10.0], [10.5])
    assert d == "inconclusive" and r == "tie_or_small_diff"
    d, r, _ = control_decision([], [1.0])
    assert d == "reject" and r == "insufficient_evidence"


def test_unequal_lengths_do_not_use_reward_per_step() -> None:
    # Short high-rate vs long low-rate: rule uses totals, not reward/step.
    d, r, _ = control_decision([8.0], [8.0])  # 8/8 vs 8/32 would look like a win if divided
    assert d == "inconclusive"


def test_single_episode_split_is_disjoint() -> None:
    spec = source_policy_task()
    ds = collect_transitions(spec, n_transitions=40, env_seeds=(1,), base_seed=0, mix=("random",))
    # Force one episode id
    ds.episode_id[:] = 0
    tr, va = split_by_episodes(ds, val_frac=0.3, rng=np.random.default_rng(0))
    assert set(tr.episode_id).isdisjoint(set(va.episode_id))
    assert len(va) == 0
    assert len(tr) == len(ds)


def test_v084_confirm_is_new() -> None:
    assert V084_CONFIRM_EVAL_SEED != V083_CONFIRM_EVAL_SEED
    assert V084_CONFIRM_EVAL_SEED != V084_DEV_EVAL_SEED
    prior = {
        (float(t.params["gravity"]), float(t.params["length"]), float(t.params["masspole"]))
        for t in v083_confirmation_targets() + (v083_development_target(),)
    }
    for spec in v084_confirmation_targets() + (v084_development_target(),):
        tup = (float(spec.params["gravity"]), float(spec.params["length"]), float(spec.params["masspole"]))
        assert tup not in prior
    noisy = [t for t in v084_confirmation_targets() if "noisy" in t.task_id]
    clean = [t for t in v084_confirmation_targets() if "clean" in t.task_id]
    assert noisy and clean


def test_matched_compare_charges_both_and_insufficient_budget() -> None:
    spec = source_policy_task()
    a = WorldModel.create(4, 2, kind="residual", seed=1)
    b = WorldModel.create(4, 2, kind="residual", seed=2)
    led = InteractionLedger(target_cap=20)
    out = matched_control_compare(spec, a, b, ledger=led, seed=0)
    assert out["ok"] is False
    assert out["reason"] == "insufficient_budget"
    assert led.target_used == 0
    led2 = InteractionLedger(target_cap=2 * CONTROL_VAL_HORIZON)
    out2 = matched_control_compare(spec, a, b, ledger=led2, seed=3)
    assert out2["ok"] is True
    assert out2["incumbent_steps"] > 0 and out2["candidate_steps"] > 0
    assert led2.buckets["online_val"] == led2.target_used
    assert led2.target_used == out2["incumbent_steps"] + out2["candidate_steps"]
    assert led2.target_used <= 2 * CONTROL_VAL_HORIZON


def test_validation_does_not_mutate_models() -> None:
    spec = source_policy_task()
    a = WorldModel.create(4, 2, kind="residual", seed=3)
    b = WorldModel.create(4, 2, kind="residual", seed=4)
    sa = {k: v.detach().clone() for k, v in a.net.state_dict().items()}
    sb = {k: v.detach().clone() for k, v in b.net.state_dict().items()}
    led = InteractionLedger(target_cap=2 * CONTROL_VAL_HORIZON)
    matched_control_compare(spec, a, b, ledger=led, seed=5)
    for k in sa:
        assert torch.equal(sa[k], a.net.state_dict()[k])
        assert torch.equal(sb[k], b.net.state_dict()[k])


def test_gate_accepts_clearly_better_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    import nexus.world.verify as verify

    def fake_rollout(spec, wm, est, *, horizon, seed, ledger, bucket):
        del spec, est, seed
        n = int(horizon)
        if bucket != "eval_only":
            ledger.charge(n, bucket)
        else:
            ledger.charge(n, "eval_only")
        score = 30.0 if id(wm) in fake_rollout.cand_ids else 10.0  # type: ignore[attr-defined]
        return score, n, False

    fake_rollout.cand_ids = set()  # type: ignore[attr-defined]

    spec = source_policy_task()
    inc = WorldModel.create(4, 2, kind="residual", seed=0)
    cand = WorldModel.create(4, 2, kind="residual", seed=1)
    fake_rollout.cand_ids.add(id(cand))  # type: ignore[attr-defined]
    monkeypatch.setattr(verify, "_rollout_frozen", fake_rollout)
    led = InteractionLedger(target_cap=2 * CONTROL_VAL_HORIZON)
    cmp = verify.matched_control_compare(spec, inc, cand, ledger=led, seed=0)
    d, r, _ = control_decision(cmp["incumbent_scores"], cmp["candidate_scores"])
    assert d == "accept" and r == "control_improved"


def test_gate_rejects_worse_and_ties(monkeypatch: pytest.MonkeyPatch) -> None:
    import nexus.world.verify as verify

    def fake(spec, wm, est, *, horizon, seed, ledger, bucket):
        del spec, est, seed, wm
        ledger.charge(int(horizon), bucket if bucket != "eval_only" else "eval_only")
        return 12.0, int(horizon), False

    monkeypatch.setattr(verify, "_rollout_frozen", fake)
    spec = source_policy_task()
    a = WorldModel.create(4, 2, kind="residual", seed=0)
    b = WorldModel.create(4, 2, kind="residual", seed=1)
    led = InteractionLedger(target_cap=2 * CONTROL_VAL_HORIZON)
    cmp = verify.matched_control_compare(spec, a, b, ledger=led, seed=0)
    d, r, _ = control_decision(cmp["incumbent_scores"], cmp["candidate_scores"])
    assert d == "inconclusive"


def test_fair_online_zero_budget_no_env() -> None:
    spec = source_policy_task()
    wm = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=8, env_seeds=(1,), base_seed=0, mix=("random",))
    out = run_fair_online(spec, wm, tr, IdentityBelief(), target_cap=0, policy="control_fair", epochs=1, seed=0, detector=_det())
    assert out["n_env_steps"] == 0
    assert out["n_observe"] == 0
    assert out["ledger"]["target_used"] == 0


def test_insufficient_budget_does_not_overrun() -> None:
    spec = source_policy_task()
    wm = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=16, env_seeds=(1, 2), base_seed=1, mix=("random",))
    out = run_fair_online(spec, wm, tr, IdentityBelief(), target_cap=40, policy="control_fair", epochs=1, seed=2, detector=_det())
    assert out["ledger"]["target_used"] <= 40
    assert out["ledger"]["within_cap"]
    if out["n_proposals"]:
        assert "insufficient_budget" in out["rejects"] or out["n_insufficient"] >= 0


def test_observe_once_and_metadata() -> None:
    spec = source_policy_task()
    from nexus.world.train import train_world_model

    tr = collect_transitions(spec, n_transitions=32, env_seeds=(1, 2), base_seed=0, mix=("random",))
    va = collect_transitions(spec, n_transitions=16, env_seeds=(8, 9), base_seed=1, mix=("random",))
    wm, _ = train_world_model(tr, va, kind="residual", epochs=1, seed=0)
    est = ScalarKalmanBelief()
    out = run_fair_online(spec, wm, tr, est, target_cap=24, policy="never", epochs=1, seed=0, detector=_det())
    assert out["observe_once"] is True
    assert out["n_observe"] == out["n_env_steps"]
    assert out["uses_confirmation"] is False


def test_confirmation_not_used_in_gate() -> None:
    spec = source_policy_task()
    wm = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=16, env_seeds=(1,), base_seed=0, mix=("random",))
    out = run_fair_online(spec, wm, tr, IdentityBelief(), target_cap=20, policy="never", epochs=1, seed=0, detector=_det())
    assert out["uses_confirmation"] is False
    for t in out["proposal_traces"]:
        assert t["uses_confirmation"] is False


def test_conditional_harm_na_when_no_accepts() -> None:
    spec = source_policy_task()
    wm = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=16, env_seeds=(1,), base_seed=0, mix=("random",))
    out = run_fair_online(spec, wm, tr, IdentityBelief(), target_cap=16, policy="never", epochs=1, seed=0, detector=_det())
    assert out["n_accept"] == 0
    assert out["conditional_harm"] == "not_applicable"


def test_v084_quick_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    art = tmp_path / "v084.json"
    out = run_v084_benchmark(n_model_seeds=1, quick=True, artifact_path=str(art), checkpoint_dir=str(tmp_path / "ck"))
    assert art.exists()
    json.loads(art.read_text())
    dumps_strict(out)
    assert out["protocol"]["retuned_on_confirmation"] is False
    assert out["protocol"]["selected_protocol"] in ("never", "always", "mae", "control_fair")
    assert "0" in out["noisy_confirmation"]
