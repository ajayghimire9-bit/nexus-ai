from __future__ import annotations

import copy
import json

import numpy as np
import pytest
import torch

from nexus.world.data import TransitionDataset
from nexus.world.context_model import ContextWorldModel
from nexus.world.direct_latent import (
    assert_latent_audit_allowed,
    assert_latent_splits_disjoint,
    audit_schema_from_config,
    choose_rule,
    classify_latent,
    donor_index,
    fit_from_support,
    fit_latent,
    frozen_network_digest,
    latent_screen,
    load_latent_config,
    lock_network,
    paired_constant_minus_mlp,
    score_with_z,
    support_for,
)
from nexus.world.result_checks import schema_completeness


def _toy_rows(n: int = 32, seed: int = 0, task: str = "toy") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    obs = rng.normal(size=(n, 3)).astype(np.float32)
    action = rng.integers(0, 3, size=n).astype(np.int64)
    episode = np.array([0] * (n // 2) + [1] * (n - n // 2), dtype=np.int64)
    return obs, action, episode


def _dataset(obs: np.ndarray, action: np.ndarray, nxt: np.ndarray, episode: np.ndarray, task: str, seed: int) -> TransitionDataset:
    n = len(obs)
    return TransitionDataset(
        obs=obs,
        action=action,
        next_obs=nxt,
        reward=np.zeros(n, dtype=np.float32),
        terminated=np.zeros(n, dtype=bool),
        truncated=np.zeros(n, dtype=bool),
        task_id=task,
        seed=np.full(n, seed, dtype=np.int64),
        episode_id=episode,
        policy=np.array(["random"] * n, dtype=object),
        physics={},
        env_interactions=n,
    )


def _sensitive(seed: int = 0) -> tuple[ContextWorldModel, np.ndarray, np.ndarray]:
    obs, action, _episode = _toy_rows(32, seed)
    model = ContextWorldModel.create(3, 3, seed=seed + 4)
    model.obs_rms.update(obs)
    lock_network(model)
    with torch.no_grad():
        model.net.film.weight.normal_(mean=0.0, std=0.5)
        model.net.state_head.weight.normal_(mean=0.0, std=0.5)
        model.net.term_head.weight.zero_()
        model.net.term_head.bias.fill_(-4.0)
    return model, obs, action


def _targets(model: ContextWorldModel, obs: np.ndarray, action: np.ndarray, z: torch.Tensor) -> np.ndarray:
    obs_n = torch.as_tensor(model.normalize(obs))
    act = torch.as_tensor(action)
    with torch.no_grad():
        pred, _logit = model.net(obs_n, act, z)
        return model.unnormalize((obs_n + pred).cpu().numpy())


def _cell() -> dict:
    return {
        "mae": 0.1,
        "rmse": 0.2,
        "angvel_mae": 0.3,
        "mae_per_dim": [0.01, 0.02, 0.03],
        "rollout_mae": {"3": 0.1, "8": 0.2, "16": 0.4},
    }


def _audit_records(cfg: dict) -> list[dict]:
    schema = audit_schema_from_config(cfg)
    records = []
    for seed in schema["seed_ids"]:
        for task in schema["task_ids"]:
            for label, conditions in schema["conditions_by_label"].items():
                for condition in conditions:
                    records.append({"seed": seed, "task": task, "label": label, "condition": condition, **copy.deepcopy(_cell())})
    return records


def test_config_and_seed_plan_are_locked() -> None:
    cfg = load_latent_config()
    assert cfg["learning_rates"] == [0.01, 0.1]
    assert cfg["task_updates"] == [0, 16, 64, 256]
    assert cfg["global_updates"] == 300 and cfg["global_lr"] == 0.01
    assert cfg["confirmation_unlocked"] is False
    assert_latent_splits_disjoint(cfg)
    schema = audit_schema_from_config(cfg)
    assert schema["seed_ids"] == [0, 1, 2]
    assert len(schema["task_ids"]) == 8


def test_removed_seed_does_not_shrink_the_audit_grid() -> None:
    cfg = load_latent_config()
    schema = audit_schema_from_config(cfg)
    remaining = [row for row in _audit_records(cfg) if row["seed"] != 2]
    built_after_removal = audit_schema_from_config(cfg)
    assert built_after_removal["seed_ids"] == [0, 1, 2]
    report = schema_completeness(
        remaining,
        seed_ids=schema["seed_ids"],
        task_ids=schema["task_ids"],
        labels=schema["labels"],
        conditions_by_label=schema["conditions_by_label"],
        metrics=tuple(schema["metrics"]),
        horizons=tuple(schema["horizons"]),
        per_dim=3,
    )
    assert report["declared_complete"] is False
    assert any("seed=2" in item for item in report["failures"])


def test_missing_condition_fails_and_full_grid_passes() -> None:
    cfg = load_latent_config()
    schema = audit_schema_from_config(cfg)
    full = _audit_records(cfg)
    kwargs = dict(
        seed_ids=schema["seed_ids"],
        task_ids=schema["task_ids"],
        labels=schema["labels"],
        conditions_by_label=schema["conditions_by_label"],
        metrics=tuple(schema["metrics"]),
        horizons=tuple(schema["horizons"]),
        per_dim=3,
    )
    assert schema_completeness(full, **kwargs)["declared_complete"] is True
    dropped = [row for row in full if not (row["label"] == "wrong" and row["condition"] == "wrong")]
    assert schema_completeness(dropped, **kwargs)["declared_complete"] is False


def test_only_z_changes_and_gradients_are_finite() -> None:
    model, obs, action = _sensitive(1)
    digest = frozen_network_digest(model)
    weight = model.net.film.weight.detach().clone()
    z_true = torch.tensor([0.4, -0.3, 0.2, -0.1, 0.5, 0.0, -0.2, 0.3])
    nxt = _targets(model, obs, action, z_true)
    _episode = np.array([0] * 16 + [1] * 16)
    support = _dataset(obs[:16], action[:16], nxt[:16], np.zeros(16, dtype=np.int64), "a", 11)
    query = _dataset(obs[16:], action[16:], nxt[16:], np.ones(16, dtype=np.int64), "a", 12)
    z = torch.nn.Parameter(torch.zeros(8))
    opt = torch.optim.Adam([z], lr=0.1)
    _state, _term, loss = model.query_terms(support.obs, support.action, support.next_obs, support.terminated, z)
    loss.backward()
    assert z.grad is not None and torch.isfinite(z.grad).all() and float(z.grad.norm()) > 0.0
    opt.zero_grad(set_to_none=True)
    before = frozen_network_digest(model)
    fitted = fit_from_support(model, support, torch.zeros(8), lr=0.1, updates=30, snapshot_at=(30,), query=query)
    assert frozen_network_digest(model) == digest == before
    assert torch.equal(model.net.film.weight.detach(), weight)
    assert float(torch.linalg.vector_norm(fitted["final"])) > 0.0
    query_before = _query_angvel(model, torch.zeros(8), query)
    query_after = _query_angvel(model, fitted["final"], query)
    assert query_after < query_before


def test_query_mutation_does_not_change_fitted_z() -> None:
    model, obs, action = _sensitive(2)
    nxt = _targets(model, obs, action, torch.ones(8))
    support = _dataset(obs[:16], action[:16], nxt[:16], np.zeros(16, dtype=np.int64), "a", 21)
    query = _dataset(obs[16:], action[16:], nxt[16:], np.ones(16, dtype=np.int64), "a", 22)
    first = fit_from_support(model, support, torch.zeros(8), lr=0.05, updates=5, snapshot_at=(5,), query=query)
    query.next_obs = query.next_obs + 4.0
    second = fit_from_support(model, support, torch.zeros(8), lr=0.05, updates=5, snapshot_at=(5,), query=query)
    assert torch.allclose(first["final"], second["final"])


def test_wrong_support_uses_the_cyclic_donor() -> None:
    supports = []
    for i in range(8):
        obs, action, episode = _toy_rows(4, i, f"t{i}")
        supports.append(_dataset(obs, action, obs + 0.1, episode, f"task-{i}", 100 + i))
    assert donor_index(7, 8) == 0
    assert support_for(supports, 7, "wrong").task_id == "task-0"
    assert support_for(supports, 7, "task").task_id == "task-7"
    assert support_for(supports, 0, "wrong").task_id == "task-1"


def test_optimizer_resets_across_tasks_and_continues_within_a_task() -> None:
    model, obs, action = _sensitive(3)
    nxt = _targets(model, obs, action, torch.full((8,), 0.2))
    support_a = _dataset(obs[:16], action[:16], nxt[:16], np.zeros(16, dtype=np.int64), "a", 31)
    support_b = _dataset(obs[16:], action[16:], nxt[16:], np.ones(16, dtype=np.int64), "b", 32)
    init = torch.zeros(8)
    alone = fit_from_support(model, support_b, init, lr=0.05, updates=4, snapshot_at=(4,))
    _other = fit_from_support(model, support_a, init, lr=0.05, updates=4, snapshot_at=(4,))
    again = fit_from_support(model, support_b, init, lr=0.05, updates=4, snapshot_at=(4,))
    assert torch.allclose(alone["final"], again["final"])
    assert alone["started_fresh"] is True and again["started_fresh"] is True
    continuous = fit_latent(
        model, support_a.obs, support_a.action, support_a.next_obs, support_a.terminated, init,
        lr=0.05, updates=4, snapshot_at=(2, 4),
    )
    resumed = fit_latent(
        model, support_a.obs, support_a.action, support_a.next_obs, support_a.terminated, continuous["snapshots"][2],
        lr=0.05, updates=2, snapshot_at=(2,), opt_state=continuous["optimizer_states"][2],
    )
    assert resumed["started_fresh"] is False
    assert torch.allclose(resumed["final"], continuous["snapshots"][4], atol=1e-5)


def test_evaluation_does_not_update_z() -> None:
    model, obs, action = _sensitive(4)
    n = 80
    line = np.arange(n, dtype=np.float32)[:, None].repeat(3, axis=1)
    nxt = np.vstack([line[1:], line[-1:] + 1.0]).astype(np.float32)
    query = _dataset(line, np.zeros(n, dtype=np.int64), nxt, np.zeros(n, dtype=np.int64), "line", 41)
    model.obs_rms.update(line)
    vector = torch.arange(model.context_dim(), dtype=torch.float32)
    digest = frozen_network_digest(model)
    cell = score_with_z(model, vector, query, [3, 8, 16], 2)
    assert np.isfinite(cell["angvel_mae"])
    assert frozen_network_digest(model) == digest
    probe = model.clone_frozen()
    probe.z = vector.clone()
    z0 = probe.z.clone()
    probe.step(line[:4], np.zeros(4, dtype=np.int64))
    assert torch.equal(probe.z, z0)


def test_rule_ties_and_screen() -> None:
    assert choose_rule({"0.01": {"0": 1.0, "16": 1.0}, "0.10": {"0": 1.0}}) == (0.01, 0)
    assert choose_rule({"0.01": {"64": 0.5}, "0.10": {"16": 0.5}}) == (0.1, 16)
    assert choose_rule({"0.01": {"16": 0.5}, "0.10": {"16": 0.5}}) == (0.01, 16)
    good = [_row(0.8) for _ in range(3)]
    assert latent_screen(good)["pass"] is True
    weak = [_row(0.99) for _ in range(3)]
    assert latent_screen(weak)["pass"] is False
    assert classify_latent(0, latent_screen(good), support_improved=True, mean_grad_norm=0.1)["label"] == "checkpoint_0_selected"


def test_audit_manifest_gate_and_paired_prior_contrast(tmp_path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(RuntimeError, match="saved"):
        assert_latent_audit_allowed(missing)
    recorded = tmp_path / "selection.json"
    recorded.write_text(json.dumps({"selection_record": {"selection_recorded": False}, "smoke": False}))
    with pytest.raises(RuntimeError, match="recorded"):
        assert_latent_audit_allowed(recorded)
    paired = paired_constant_minus_mlp()
    assert paired["n"] == 3
    assert paired["contrast"] == "constant_external_minus_mlp"
    assert abs(paired["mean"] - float(np.mean(paired["per_seed"]))) < 1e-12
    assert paired["lo"] < paired["mean"] < paired["hi"] or paired["lo"] == paired["hi"]


def _query_angvel(model: ContextWorldModel, vector: torch.Tensor, query: TransitionDataset) -> float:
    probe = model.clone_frozen()
    probe.z = vector.detach().clone()
    pred, _term = probe.step(query.obs, query.action)
    err = np.abs(pred[:, 2] - query.next_obs[:, 2])
    return float(np.mean(err))


def _row(task: float, *, zero: float = 1.0, global_v: float = 1.0, wrong: float = 1.0) -> dict[str, float]:
    return {
        "angvel_task": task,
        "angvel_zero": zero,
        "angvel_global": global_v,
        "angvel_wrong": wrong,
        "angvel_encoder": 1.0,
        "angvel_mlp": 0.9,
        "angvel_constant_external": 0.9,
        "mae_task": task,
        "mae_global": 1.0,
        "h16_task": task,
        "h16_global": 1.0,
    }
