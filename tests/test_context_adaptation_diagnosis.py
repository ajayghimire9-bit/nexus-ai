from __future__ import annotations

import json

import numpy as np
import pytest
import torch

from nexus.world.confirm_guard import (
    PROTOCOL_ID,
    ConfirmationRejected,
    assert_confirmation_allowed,
    pilot_config_fingerprint,
)
from nexus.world.context_diagnosis import interpret_diagnosis, load_diagnosis_config
from nexus.world.context_model import (
    ContextWorldModel,
    make_context_schedule,
    support_take,
    train_context_model,
)
from nexus.world.context_pilot import prefix_hash, run_context_adaptation
from nexus.world.data import TransitionDataset


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
        truncated=np.array([False] * (n - 1) + [True]),
        task_id="toy",
        seed=np.full(n, seed, dtype=np.int64),
        episode_id=np.array([0] * half + [1] * (n - half), dtype=np.int64),
        policy=np.array(["random"] * n, dtype=object),
        physics={},
        env_interactions=n,
    )


def test_config_is_the_locked_source() -> None:
    cfg = load_diagnosis_config()
    assert cfg["n_seeds"] == 3 and cfg["primary_hi"] == 128
    assert cfg["confirmation_unlocked"] is False
    assert cfg["ft_epochs"] == 4


def test_nondefault_checkpoint_roundtrip_and_cleared_context(tmp_path) -> None:  # type: ignore[no-untyped-def]
    model = ContextWorldModel.create(4, 2, seed=3, encoder_hidden=7, context_dim=5, trunk_hidden=(13, 9))
    model.obs_rms.update(np.ones((6, 4), dtype=np.float32))
    model.z = torch.ones(5)
    obs = np.ones((2, 4), dtype=np.float32)
    act = np.zeros(2, dtype=np.int64)
    pred, _p = model.step(obs, act)
    path = tmp_path / "custom.pt"
    model.save(path)
    blob = torch.load(path, weights_only=False)
    assert blob["encoder_hidden"] == 7 and blob["context_dim"] == 5 and tuple(blob["trunk_hidden"]) == (13, 9)
    blob.pop("encoder_hidden")
    torch.save(blob, path)
    loaded = ContextWorldModel.load(path)
    assert loaded.encoder.hidden == 7 and loaded.context_dim() == 5 and loaded.net.hidden == (13, 9)
    assert torch.equal(loaded.z, torch.zeros(5))
    loaded.z = torch.ones(5)
    pred2, _ = loaded.step(obs, act)
    assert np.allclose(pred, pred2)
    cloned = loaded.clone_frozen()
    assert cloned.context_dim() == 5 and cloned.encoder.hidden == 7
    assert torch.equal(cloned.z, torch.zeros(5))
    cloned.z = torch.ones(5)
    pred3, _ = cloned.step(obs, act)
    assert np.allclose(pred, pred3)
    empty = ContextWorldModel.create(3, 3, seed=0, context_dim=5)
    empty.clear_context()
    assert int(empty.z.numel()) == 5
    assert int(empty.encode(np.zeros((0, 3), dtype=np.float32), np.zeros(0, dtype=np.int64), np.zeros((0, 3), dtype=np.float32), differentiable=False).numel()) == 5


def test_prefix_hash_includes_outcomes_inside_budget() -> None:
    ds = _toy(1.0, n=40, seed=4)
    base = prefix_hash(ds, 8)
    inside = ds.next_obs.copy()
    inside[3, 0] += 1.0
    changed = TransitionDataset(
        obs=ds.obs, action=ds.action, next_obs=inside, reward=ds.reward, terminated=ds.terminated,
        truncated=ds.truncated, task_id=ds.task_id, seed=ds.seed, episode_id=ds.episode_id,
        policy=ds.policy, physics={}, env_interactions=len(ds),
    )
    assert prefix_hash(changed, 8) != base
    outside = ds.next_obs.copy()
    outside[20, 0] += 4.0
    held = TransitionDataset(
        obs=ds.obs, action=ds.action, next_obs=outside, reward=ds.reward, terminated=ds.terminated,
        truncated=ds.truncated, task_id=ds.task_id, seed=ds.seed, episode_id=ds.episode_id,
        policy=ds.policy, physics={}, env_interactions=len(ds),
    )
    assert prefix_hash(held, 8) == base
    flags = ds.terminated.copy()
    flags[2] = True
    flagged = TransitionDataset(
        obs=ds.obs, action=ds.action, next_obs=ds.next_obs, reward=ds.reward, terminated=flags,
        truncated=ds.truncated, task_id=ds.task_id, seed=ds.seed, episode_id=ds.episode_id,
        policy=ds.policy, physics={}, env_interactions=len(ds),
    )
    assert prefix_hash(flagged, 8) != base


def test_context_cap_short_histories_and_rollout_freeze() -> None:
    ds = _toy(0.5, n=200, seed=8)
    model = ContextWorldModel.create(3, 3, seed=1)
    model.obs_rms.update(ds.obs)
    model.set_context_from_dataset(ds, budget=10_000)
    z_cap = model.z.clone()
    tail = ds.next_obs.copy()
    tail[128:] += 3.0
    mutated_tail = TransitionDataset(
        obs=ds.obs, action=ds.action, next_obs=tail, reward=ds.reward, terminated=ds.terminated,
        truncated=ds.truncated, task_id=ds.task_id, seed=ds.seed, episode_id=ds.episode_id,
        policy=ds.policy, physics={}, env_interactions=len(ds),
    )
    model.set_context_from_dataset(mutated_tail, budget=10_000)
    assert torch.allclose(model.z, z_cap)
    head = ds.next_obs.copy()
    head[4, 1] += 2.0
    mutated_head = TransitionDataset(
        obs=ds.obs, action=ds.action, next_obs=head, reward=ds.reward, terminated=ds.terminated,
        truncated=ds.truncated, task_id=ds.task_id, seed=ds.seed, episode_id=ds.episode_id,
        policy=ds.policy, physics={}, env_interactions=len(ds),
    )
    model.set_context_from_dataset(mutated_head, budget=128)
    assert not torch.allclose(model.z, z_cap)
    model.set_context_from_dataset(ds, budget=0)
    pred0, _ = model.step(ds.obs[:3], ds.action[:3])
    model.set_context_from_dataset(ds, budget=2)
    pred2, _ = model.step(ds.obs[:3], ds.action[:3])
    assert np.isfinite(pred0).all() and np.isfinite(pred2).all()
    z_before = model.z.clone()
    n0 = model.n_encodes
    query = ds.slice(np.arange(0, 40))
    query = TransitionDataset(
        obs=query.obs, action=query.action, next_obs=query.next_obs, reward=query.reward,
        terminated=query.terminated, truncated=query.truncated, task_id=query.task_id, seed=query.seed,
        episode_id=np.zeros(len(query), dtype=np.int64), policy=query.policy, physics={}, env_interactions=len(query),
    )
    # Make the slice contiguous in next_obs so the rollout accepts it.
    query = TransitionDataset(
        obs=np.vstack([query.obs, query.next_obs[-1:]]),
        action=np.concatenate([query.action, query.action[-1:]]),
        next_obs=np.vstack([query.next_obs, query.next_obs[-1:]]),
        reward=np.concatenate([query.reward, query.reward[-1:]]),
        terminated=np.concatenate([query.terminated, [True]]),
        truncated=np.concatenate([query.truncated, [True]]),
        task_id="toy",
        seed=np.zeros(len(query) + 1, dtype=np.int64),
        episode_id=np.zeros(len(query) + 1, dtype=np.int64),
        policy=np.array(["random"] * (len(query) + 1), dtype=object),
        physics={},
        env_interactions=len(query) + 1,
    )
    # The constructed episode may not be contiguous. Drive step() directly instead.
    del query
    state = ds.obs[:1]
    for t in range(16):
        state, _p = model.step(state, ds.action[t : t + 1])
    assert torch.equal(model.z, z_before)
    assert model.n_encodes == n0
    assert np.isfinite(state).all()


def test_paired_schedule_shares_queries_and_shortens_support() -> None:
    tasks = [_toy(0.4, n=160, seed=1), _toy(1.5, n=160, seed=2)]
    first = make_context_schedule(tasks, updates=12, seed=11, empty_prob=0.0)
    second = make_context_schedule(tasks, updates=12, seed=11, empty_prob=0.0)
    assert [row["task_index"] for row in first] == [row["task_index"] for row in second]
    assert [row["query_index"].tolist() for row in first] == [row["query_index"].tolist() for row in second]
    assert any(int(row["variable_length"]) < 128 for row in first)
    for row in first:
        fixed = support_take(row, "fixed")
        variable = support_take(row, "variable")
        assert variable.tolist() == fixed[: variable.size].tolist()
        assert set(np.unique(tasks[row["task_index"]].episode_id[row["support_index"]]).tolist()).isdisjoint(
            set(np.unique(tasks[row["task_index"]].episode_id[row["query_index"]]).tolist())
        )
    obs = np.concatenate([ds.obs for ds in tasks], axis=0)
    left = ContextWorldModel.create(3, 3, seed=4)
    left.obs_rms.update(obs)
    right = left.clone_trainable()
    log_fixed = train_context_model(left, tasks, updates=12, seed=11, schedule=first, support_mode="fixed", empty_prob=0.0)
    log_var = train_context_model(right, tasks, updates=12, seed=11, schedule=first, support_mode="variable", empty_prob=0.0)
    assert log_fixed["query_examples"] == log_var["query_examples"]
    assert log_var["support_examples"] < log_fixed["support_examples"]
    assert log_fixed["mean_encoder_grad_norm"] > 0


def _passing_artifact() -> dict:
    from nexus.world.confirm_guard import _split_hashes

    hashes = _split_hashes()
    return {
        "incomplete": False,
        "gate": {"pass": True},
        "protocol": {
            "code_version": "context_adaptation_pilot",
            "phase": "dev",
            "quick": False,
            "confirm_evaluated": False,
            "protocol_id": PROTOCOL_ID,
            "config_fingerprint": pilot_config_fingerprint(),
            "implementation_sha": "b86baf4e23e29761ec34e29b2a8d67f3a24ae207",
            "source_dirty": False,
            "ft_epochs": 4,
            **hashes,
        },
    }


def test_confirmation_rejects_without_environments(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("confirmation environment was contacted")

    monkeypatch.setattr("nexus.world.context_pilot.collect_transitions", boom)
    with pytest.raises(ConfirmationRejected):
        run_context_adaptation(phase="confirm", dev_artifact={"incomplete": False, "gate": {"pass": False}, "protocol": {}})
    artifact = json.loads(open("artifacts/context_adaptation_dev.json").read())
    with pytest.raises(ConfirmationRejected):
        assert_confirmation_allowed(artifact)
    clean = {"error": None, "source_dirty": False, "source_changed": False}
    assert_confirmation_allowed(_passing_artifact(), source_status=clean)
    with pytest.raises(ConfirmationRejected):
        assert_confirmation_allowed(_passing_artifact(), source_status={"error": None, "source_dirty": False, "source_changed": True, "changed_paths": ["src/nexus/world/context_model.py"]})
    with pytest.raises(ConfirmationRejected):
        assert_confirmation_allowed(None)


def test_interpretation_priority() -> None:
    flags = {
        "real_context_fails_source_prediction": True,
        "source_prediction_helps_but_development_does_not": True,
        "variable_length_short_history_point_estimate_positive": True,
        "prediction_improves_but_control_worsens": False,
        "zero_context_far_below_mlp": True,
    }
    choice = interpret_diagnosis(flags)
    assert choice["next_intervention"] == "representation_or_optimization"
    assert choice["coexisting"]
