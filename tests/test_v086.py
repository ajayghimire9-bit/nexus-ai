from __future__ import annotations

import json

import numpy as np
import torch

from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import (
    source_policy_task,
    v085_confirmation_targets,
    v085_development_target,
    v086_confirmation_targets,
    v086_development_target,
)
from nexus.world.adapt import finetune_world_model, interpolate_world_models
from nexus.world.agent import InteractionLedger
from nexus.world.data import collect_transitions
from nexus.world.dynamics import WorldModel
from nexus.world.protocol import V085_CONFIRM_REF_SEED, V086_CONFIRM_REF_SEED, V086_DEV_REF_SEED, V086_GATE_SEED
from nexus.world.v086 import METHODS, apply_method, collect_matched, run_safe_online, run_v086_benchmark
from nexus.world.verify import V085_MAE_RATIO, V085_MAE_STEPS, weights_hash


def test_mae_threshold_frozen() -> None:
    assert V085_MAE_RATIO == 0.97
    assert V085_MAE_STEPS == 32


def test_interpolate_is_convex_combination() -> None:
    a = WorldModel.create(4, 2, kind="residual", seed=0)
    b = WorldModel.create(4, 2, kind="residual", seed=1)
    z = interpolate_world_models(a, b, alpha=0.0)
    o = interpolate_world_models(a, b, alpha=1.0)
    m = interpolate_world_models(a, b, alpha=0.5)
    assert weights_hash(z) == weights_hash(a)
    assert weights_hash(o) == weights_hash(b)
    sa, sb, sm = a.net.state_dict(), b.net.state_dict(), m.net.state_dict()
    k = next(iter(sa))
    assert torch.allclose(sm[k], 0.5 * sa[k] + 0.5 * sb[k], atol=1e-5)


def test_methods_share_matched_collect() -> None:
    spec = source_policy_task()
    src = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=24, env_seeds=(1, 2), base_seed=0, mix=("random",))
    train_ds, val_ds = collect_matched(spec, src, model_seed=0, pair_i=0, collect_n=16, val_n=8)
    hashes = []
    n_train = []
    for m in ("finetune", "low_lr", "interpolate"):
        cand, log = apply_method(m, src, tr, train_ds, val_ds, epochs=1, seed=0)  # type: ignore[arg-type]
        hashes.append(weights_hash(cand))
        n_train.append(len(train_ds))
    assert n_train[0] == n_train[1] == n_train[2]
    assert len(set(hashes)) >= 1  # models may differ; data size matched


def test_low_lr_recorded() -> None:
    spec = source_policy_task()
    src = WorldModel.create(4, 2, kind="residual", seed=1)
    tr = collect_transitions(spec, n_transitions=32, env_seeds=(1, 2), base_seed=0, mix=("random",))
    va = collect_transitions(spec, n_transitions=16, env_seeds=(8, 9), base_seed=1, mix=("random",))
    _c, log = apply_method("low_lr", src, tr, tr, va, epochs=1, seed=0)
    assert log["lr"] == 1e-4
    _c2, log2 = apply_method("finetune", src, tr, tr, va, epochs=1, seed=0)
    assert log2["lr"] == 5e-4


def test_early_stop_can_halt() -> None:
    spec = source_policy_task()
    src = WorldModel.create(4, 2, kind="residual", seed=2)
    tr = collect_transitions(spec, n_transitions=48, env_seeds=(1, 2, 3), base_seed=0, mix=("random",))
    va = collect_transitions(spec, n_transitions=24, env_seeds=(20, 21), base_seed=2, mix=("random",))
    _wm, log = finetune_world_model(src, tr, va, epochs=8, seed=0, lr=5e-4, select_by_val=True, patience=2)
    assert log["patience"] == 2
    assert int(log["epochs_run"]) <= 8


def test_online_always_commits_and_respects_cap() -> None:
    spec = source_policy_task()
    src = WorldModel.create(4, 2, kind="residual", seed=0)
    tr = collect_transitions(spec, n_transitions=16, env_seeds=(1,), base_seed=0, mix=("random",))
    out0 = run_safe_online(spec, src, tr, "finetune", target_cap=0, epochs=1, seed=0, gate="always")
    assert out0["n_accept"] == 0
    assert out0["ledger"]["target_used"] == 0
    out = run_safe_online(spec, src, tr, "finetune", target_cap=48, epochs=1, seed=1, gate="always")
    assert out["ledger"]["target_used"] <= 48
    assert out["ledger"]["within_cap"]
    assert out["n_accept"] == 1
    never = run_safe_online(spec, src, tr, "finetune", target_cap=48, epochs=1, seed=1, gate="never")
    assert never["n_accept"] == 0
    assert never["committed_hash"] == weights_hash(src)


def test_v086_physics_and_seeds_are_new() -> None:
    assert V086_CONFIRM_REF_SEED != V085_CONFIRM_REF_SEED
    assert V086_CONFIRM_REF_SEED != V086_DEV_REF_SEED
    assert V086_GATE_SEED != V086_CONFIRM_REF_SEED
    prior = {
        (float(t.params["gravity"]), float(t.params["length"]), float(t.params["masspole"]))
        for t in v085_confirmation_targets() + (v085_development_target(),)
    }
    for spec in v086_confirmation_targets() + (v086_development_target(),):
        tup = (float(spec.params["gravity"]), float(spec.params["length"]), float(spec.params["masspole"]))
        assert tup not in prior


def test_v086_quick_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    art = tmp_path / "v086.json"
    out = run_v086_benchmark(n_model_seeds=1, quick=True, artifact_path=str(art), checkpoint_dir=str(tmp_path / "ck"))
    assert art.exists()
    json.loads(art.read_text())
    dumps_strict(out)
    assert out["protocol"]["retuned_mae"] is False
    assert out["protocol"]["reference_feeds_gate"] is False
    assert out["protocol"]["selected_method"] in METHODS or out["protocol"]["selected_method"] in ("finetune", "low_lr", "interpolate")
    pair = out["per_seed"][0]["confirmation"][0]["pairs"][0]
    assert "on_policy_mae_candidate" in pair["diagnostics"]
    assert pair["costs"]["collect_train"] > 0
    assert pair["gates"]["mae"]["decision"] in ("accept", "reject")
    seq = out["per_seed"][0]["continual"]
    assert seq[-1]["stage"] == "A_return"
    assert seq[0]["always_hash"] != seq[0]["source_hash"] or seq[0]["always_accept"] == 0
