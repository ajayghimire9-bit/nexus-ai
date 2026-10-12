from __future__ import annotations

import dataclasses
import json

import numpy as np
import pytest
import torch

from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v084_confirmation_targets,
    v084_development_target,
    v085_confirmation_targets,
    v085_development_target,
)
from nexus.world.adapt import adapt_method
from nexus.world.agent import InteractionLedger
from nexus.world.data import collect_transitions, split_by_episodes
from nexus.world.dynamics import WorldModel
from nexus.world.protocol import V084_CONFIRM_EVAL_SEED, V085_CONFIRM_REF_SEED, V085_DEV_REF_SEED, V085_GATE_SEED
from nexus.world.v085 import generate_pair, run_v085_benchmark, verify_pair, VERIFIER_SPECS
from nexus.world.verify import (
    CONTROL_VAL_HORIZON,
    GateInput,
    MIN_IMPROVE,
    classify_reference,
    control_decision,
    harm_status,
    matched_control_compare,
    run_gate,
)


def test_adapt_method_single_episode_does_not_use_train_as_val() -> None:
    spec = source_policy_task()
    ds = collect_transitions(spec, n_transitions=40, env_seeds=(1,), base_seed=0, mix=("random",))
    ds.episode_id[:] = 0
    tr, va = split_by_episodes(ds, val_frac=0.3, rng=np.random.default_rng(0))
    assert len(va) == 0
    src = WorldModel.create(4, 2, kind="residual", seed=0)
    _wm, log = adapt_method("finetune", src, ds, ds, epochs=1, seed=0, episode_disjoint=True, allow_overlap_val=False)
    assert log["independent_validation"] is False
    assert log["checkpoint_rule"] == "last_epoch"
    assert log["val_used_for_selection"] is False
    assert log.get("best_val") is None
    assert "train_loss_history" in log
    assert log.get("overlap_val") is not True


def test_adapt_method_independent_val_is_disjoint() -> None:
    spec = source_policy_task()
    tr = collect_transitions(spec, n_transitions=32, env_seeds=(1, 2), base_seed=0, mix=("random",))
    va = collect_transitions(spec, n_transitions=16, env_seeds=(80, 81), base_seed=9, mix=("random",))
    src = WorldModel.create(4, 2, kind="residual", seed=1)
    _wm, log = adapt_method("finetune", src, tr, tr, epochs=1, seed=1, allow_overlap_val=False, independent_val=va)
    assert log["independent_validation"] is True
    assert log["checkpoint_rule"] == "best_independent_val"
    assert log["val_n"] == len(va)
    assert log["best_val"] is not None


def test_gate_input_has_no_reference_fields() -> None:
    names = {f.name for f in dataclasses.fields(GateInput)}
    assert "reference" not in names
    assert "ref_label" not in names
    assert "ref_scores" not in names
    assert "confirmation" not in names


def test_run_gate_does_not_read_reference_attribute() -> None:
    spec = source_policy_task()
    a = WorldModel.create(4, 2, kind="residual", seed=0)
    b = WorldModel.create(4, 2, kind="residual", seed=1)
    led = InteractionLedger(target_cap=0)
    inp = GateInput(spec=spec, incumbent=a, candidate=b, ledger=led, seed=0)

    class Sneaky:
        def __init__(self, inner: GateInput) -> None:
            object.__setattr__(self, "_inner", inner)
            self.reference_label = "benefit"
            self.ref_scores = [500.0]

        def __getattr__(self, item: str):
            return getattr(self._inner, item)

    out = run_gate("never", Sneaky(inp))  # type: ignore[arg-type]
    assert out["decision"] == "reject"
    assert out["reason"] == "never"
    assert "reference_label" not in out


def test_identical_pairs_for_each_verifier() -> None:
    spec = source_policy_task()
    src = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=24, env_seeds=(1, 2), base_seed=0, mix=("random",))
    pair = generate_pair(spec, src, tr, model_seed=0, recipe="c24", collect_n=16, val_n=8, epochs=1, pair_i=0)
    ids = []
    hashes = []
    for vname, vspec in VERIFIER_SPECS:
        d = verify_pair(pair, vname, vspec, gate_seed=1)
        ids.append(d["pair_id"])
        hashes.append((d["inc_hash"], d["cand_hash"]))
    assert len(set(ids)) == 1
    assert len(set(hashes)) == 1


def test_gate_accepts_better_rejects_worse_ties_inconclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    import nexus.world.verify as verify

    scores = {"inc": 10.0, "cand": 20.0}

    def fake(spec, wm, est, *, horizon, seed, ledger, bucket):
        del spec, est, seed
        n = int(horizon)
        if bucket == "eval_only":
            ledger.charge(n, "eval_only")
        else:
            ledger.charge(n, bucket)
        return (scores["cand"] if wm is fake.cand else scores["inc"]), n, False  # type: ignore[attr-defined]

    spec = source_policy_task()
    inc = WorldModel.create(4, 2, kind="residual", seed=0)
    cand = WorldModel.create(4, 2, kind="residual", seed=1)
    fake.cand = cand  # type: ignore[attr-defined]
    monkeypatch.setattr(verify, "_rollout_frozen", fake)
    led = InteractionLedger(target_cap=2 * CONTROL_VAL_HORIZON)
    inp = GateInput(spec=spec, incumbent=inc, candidate=cand, ledger=led, seed=0, horizon=CONTROL_VAL_HORIZON)
    out = run_gate("control", inp)
    assert out["decision"] == "accept"

    scores["cand"] = 5.0
    led2 = InteractionLedger(target_cap=2 * CONTROL_VAL_HORIZON)
    out2 = run_gate("control", GateInput(spec=spec, incumbent=inc, candidate=cand, ledger=led2, seed=0))
    assert out2["decision"] == "reject" and out2["reason"] == "control_worse"

    scores["cand"] = 10.0
    led3 = InteractionLedger(target_cap=2 * CONTROL_VAL_HORIZON)
    out3 = run_gate("control", GateInput(spec=spec, incumbent=inc, candidate=cand, ledger=led3, seed=0))
    assert out3["reason"] == "tie_or_small_diff"
    assert out3["decision"] == "reject"


def test_ceiling_tie_inconclusive() -> None:
    d, r, _ = control_decision([32.0], [32.0], min_improve=MIN_IMPROVE)
    assert d == "inconclusive" and r == "tie_or_small_diff"


def test_both_rollouts_charged_and_budget_cap() -> None:
    spec = source_policy_task()
    a = WorldModel.create(4, 2, kind="residual", seed=2)
    b = WorldModel.create(4, 2, kind="residual", seed=3)
    led = InteractionLedger(target_cap=10)
    out = matched_control_compare(spec, a, b, ledger=led, seed=0, horizon=CONTROL_VAL_HORIZON)
    assert out["ok"] is False
    assert led.target_used == 0
    led2 = InteractionLedger(target_cap=2 * CONTROL_VAL_HORIZON)
    out2 = matched_control_compare(spec, a, b, ledger=led2, seed=1, horizon=CONTROL_VAL_HORIZON)
    assert out2["ok"]
    assert led2.buckets["online_val"] == out2["incumbent_steps"] + out2["candidate_steps"]
    assert led2.target_used <= led2.target_cap


def test_validation_does_not_mutate() -> None:
    spec = source_policy_task()
    a = WorldModel.create(4, 2, kind="residual", seed=3)
    b = WorldModel.create(4, 2, kind="residual", seed=4)
    sa = {k: v.detach().clone() for k, v in a.net.state_dict().items()}
    led = InteractionLedger(target_cap=2 * CONTROL_VAL_HORIZON)
    run_gate("control", GateInput(spec=spec, incumbent=a, candidate=b, ledger=led, seed=2))
    for k in sa:
        assert torch.equal(sa[k], a.net.state_dict()[k])


def test_harm_status_three_way() -> None:
    assert harm_status(n_accept=0, n_harmful_accept=0, n_unresolved_accept=0)["status"] == "no_acceptance"
    assert harm_status(n_accept=4, n_harmful_accept=0, n_unresolved_accept=0)["status"] == "no_detected_harm"
    assert harm_status(n_accept=4, n_harmful_accept=1, n_unresolved_accept=2)["status"] == "inconclusive_audits"


def test_classify_reference_margin() -> None:
    assert classify_reference([100.0], [120.0]) == "benefit"
    assert classify_reference([100.0], [80.0]) == "harm"
    assert classify_reference([100.0], [105.0]) == "inconclusive"


def test_v085_physics_and_seeds_are_new() -> None:
    assert V085_CONFIRM_REF_SEED != V084_CONFIRM_EVAL_SEED
    assert V085_CONFIRM_REF_SEED != V085_DEV_REF_SEED
    assert V085_GATE_SEED != V085_CONFIRM_REF_SEED
    prior = {
        (float(t.params["gravity"]), float(t.params["length"]), float(t.params["masspole"]))
        for t in v084_confirmation_targets() + (v084_development_target(),)
    }
    for spec in v085_confirmation_targets() + (v085_development_target(),):
        tup = (float(spec.params["gravity"]), float(spec.params["length"]), float(spec.params["masspole"]))
        assert tup not in prior


def test_v085_quick_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    art = tmp_path / "v085.json"
    out = run_v085_benchmark(n_model_seeds=1, quick=True, artifact_path=str(art), checkpoint_dir=str(tmp_path / "ck"))
    assert art.exists()
    json.loads(art.read_text())
    dumps_strict(out)
    assert out["protocol"]["reference_feeds_gate"] is False
    assert out["protocol"]["retuned_on_confirmation"] is False
    assert out["protocol"]["selected_verifier"] in dict(VERIFIER_SPECS)
    # same pair ids across verifiers on confirm
    pair = out["per_seed"][0]["confirmation"][0]["pairs"][0]
    hashes = {(pair["gates"][n]["inc_hash"], pair["gates"][n]["cand_hash"]) for n, _ in VERIFIER_SPECS}
    assert len(hashes) == 1
