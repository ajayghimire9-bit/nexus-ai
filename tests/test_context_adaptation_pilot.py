from __future__ import annotations

import numpy as np
import torch

from nexus.tasks.pendulum_family import pendulum_context_confirmation, pendulum_context_development, pendulum_context_train
from nexus.world.context_model import MAX_CONTEXT, ContextWorldModel, split_support_query, train_context_model
from nexus.world.context_pilot import (
    BUDGETS,
    PRIMARY_HI,
    assert_context_physics_disjoint,
    prefix_hash,
    run_context_adaptation,
)
from nexus.world.data import TransitionDataset
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_PRIMARY_HORIZON
from nexus.world.planning import PENDULUM_PLAN_HORIZON


def _toy(scale: float, n: int = 80, seed: int = 0) -> TransitionDataset:
    rng = np.random.default_rng(seed)
    obs = rng.normal(size=(n, 3)).astype(np.float32)
    action = rng.integers(0, 3, size=n)
    nxt = obs + float(scale) * (action.astype(np.float32)[:, None] - 1.0)
    half = n // 2
    return TransitionDataset(
        obs=obs,
        action=action.astype(np.int64),
        next_obs=nxt.astype(np.float32),
        reward=np.zeros(n, dtype=np.float32),
        terminated=np.zeros(n, dtype=bool),
        truncated=np.zeros(n, dtype=bool),
        task_id="toy",
        seed=np.zeros(n, dtype=np.int64),
        episode_id=np.array([0] * half + [1] * (n - half), dtype=np.int64),
        policy=np.array(["random"] * n, dtype=object),
        physics={},
        env_interactions=n,
    )


def test_physics_splits_are_disjoint() -> None:
    assert_context_physics_disjoint()
    assert len(pendulum_context_train()) == 8
    assert len(pendulum_context_development()) == 3
    assert len(pendulum_context_confirmation()) == 4
    assert FROZEN_PRIMARY_HORIZON == 3 and PENDULUM_PLAN_HORIZON == 16
    assert BUDGETS[0] == 0 and 256 in BUDGETS and PRIMARY_HI == 256


def test_encoder_gradients_and_learning() -> None:
    ds_a, ds_b = _toy(0.2, seed=1), _toy(3.0, seed=2)
    model = ContextWorldModel.create(3, 3, seed=0)
    model.obs_rms.update(np.concatenate([ds_a.obs, ds_b.obs], axis=0))
    support, query = split_support_query(ds_a, np.random.default_rng(0))
    assert set(support.episode_id.tolist()).isdisjoint(set(query.episode_id.tolist()))
    z = model.encode(support.obs[:8], support.action[:8], support.next_obs[:8], differentiable=True)
    loss = model.query_loss(query.obs[:8], query.action[:8], query.next_obs[:8], query.terminated[:8], z)
    loss.backward()
    grads = [p.grad for p in model.encoder.parameters() if p.grad is not None]
    assert grads
    norm = float(sum(g.norm().item() for g in grads))
    assert np.isfinite(norm) and norm > 0
    before = torch.cat([p.detach().flatten().clone() for p in model.encoder.parameters()])
    log = train_context_model(model, [ds_a, ds_b], updates=8, seed=0, empty_prob=0.0)
    after = torch.cat([p.detach().flatten() for p in model.encoder.parameters()])
    assert log["encoder_l2_delta"] > 0
    assert float(torch.linalg.vector_norm(after - before).item()) > 0
    za = model.encode(ds_a.obs[:16], ds_a.action[:16], ds_a.next_obs[:16], differentiable=False)
    zb = model.encode(ds_b.obs[:16], ds_b.action[:16], ds_b.next_obs[:16], differentiable=False)
    assert float(torch.linalg.vector_norm(za - zb).item()) > 0


def test_context_budget_order_and_clear() -> None:
    ds = _toy(1.0, n=40, seed=3)
    model = ContextWorldModel.create(3, 3, seed=1)
    model.obs_rms.update(ds.obs)
    full = model.encode(ds.obs, ds.action, ds.next_obs, differentiable=False).clone()
    perm = np.random.default_rng(4).permutation(len(ds))
    shuffled = model.encode(ds.obs[perm], ds.action[perm], ds.next_obs[perm], differentiable=False)
    assert torch.allclose(full, shuffled, atol=1e-5)
    model.set_context_from_dataset(ds, budget=8)
    z8 = model.z.clone()
    changed = ds.next_obs.copy()
    changed[20:] += 5.0
    ds2 = TransitionDataset(
        obs=ds.obs, action=ds.action, next_obs=changed, reward=ds.reward, terminated=ds.terminated,
        truncated=ds.truncated, task_id=ds.task_id, seed=ds.seed, episode_id=ds.episode_id,
        policy=ds.policy, physics=dict(ds.physics), env_interactions=len(ds),
    )
    model.set_context_from_dataset(ds2, budget=8)
    assert torch.allclose(model.z, z8)
    assert prefix_hash(ds, 8) == prefix_hash(ds2, 8)
    assert prefix_hash(ds, 8) != prefix_hash(ds, 16)
    model.clear_context()
    assert float(torch.linalg.vector_norm(model.z).item()) == 0.0
    model.set_context_from_dataset(ds, budget=0)
    assert float(torch.linalg.vector_norm(model.z).item()) == 0.0
    n0 = model.n_encodes
    z_before = model.z.clone()
    _nxt, _p = model.step(ds.obs[:4], ds.action[:4])
    assert model.n_encodes == n0
    assert torch.equal(model.z, z_before)
    assert MAX_CONTEXT == 128


def test_save_load_and_legacy_mlp(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ctx = ContextWorldModel.create(3, 3, seed=2)
    ctx.obs_rms.update(np.zeros((4, 3), dtype=np.float32))
    obs = np.zeros((2, 3), dtype=np.float32)
    act = np.zeros(2, dtype=np.int64)
    pred, _p = ctx.step(obs, act)
    path = tmp_path / "ctx.pt"
    ctx.save(path)
    loaded = ContextWorldModel.load(path)
    loaded.copy_rms(ctx.obs_rms)
    pred2, _ = loaded.step(obs, act)
    assert np.allclose(pred, pred2)
    mlp = WorldModel.create(4, 2, kind="residual", seed=0, arch="mlp")
    mlp.obs_rms.update(np.zeros((3, 4), dtype=np.float32))
    mp = tmp_path / "mlp.pt"
    mlp.save(mp)
    blob = torch.load(mp, weights_only=False)
    blob.pop("arch")
    blob.pop("hidden")
    torch.save(blob, mp)
    legacy = WorldModel.load(mp)
    assert legacy.net.arch == "mlp"
    assert legacy.net.hidden == (64, 64)
    a, _ = mlp.step(np.zeros((2, 4), dtype=np.float32), np.zeros(2, dtype=np.int64))
    b, _ = legacy.step(np.zeros((2, 4), dtype=np.float32), np.zeros(2, dtype=np.int64))
    assert np.allclose(a, b)


def test_two_seeds_match_and_smoke() -> None:
    ds = _toy(0.5, seed=5)
    logs = []
    deltas = []
    for _ in range(2):
        m = ContextWorldModel.create(3, 3, seed=7)
        m.obs_rms.update(ds.obs)
        logs.append(train_context_model(m, [ds, _toy(0.5, seed=6)], updates=2, seed=9, empty_prob=0.0))
        deltas.append(torch.cat([p.detach().flatten() for p in m.encoder.parameters()]).clone())
    assert torch.allclose(deltas[0], deltas[1])
    out = run_context_adaptation(phase="smoke", quick=True, artifact_path=None)
    assert out["gate"]["pass"] is False
    assert out["protocol"]["confirm_evaluated"] is False
    assert out["protocol"]["is_agi"] is False
    task = next(iter(out["per_seed"][0]["curves"]["per_task"].values()))
    assert task["prefix_hashes"]["0"] != task["prefix_hashes"]["16"]
    for method in ("mlp_frozen", "mlp_ft", "ctx_real", "ctx_zero", "ctx_wrong"):
        assert len(task["curve"][method]) == 2
        assert np.isfinite(task["curve"][method]).all()
