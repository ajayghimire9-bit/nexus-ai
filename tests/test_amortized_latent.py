from __future__ import annotations

import copy

import numpy as np
import pytest
import torch
import yaml

from nexus.tasks.pendulum_family import pendulum_context_confirmation
import inspect

from nexus.world.amortized_latent import (
    TEACHER_LR,
    TEACHER_UPDATES,
    _infer,
    assert_amortized_seeds_disjoint,
    assert_checkpoint_hashes,
    assert_dev_allows_confirmation,
    assert_prior_artifacts_unchanged,
    assert_protocol_frozen,
    assert_splits,
    choose_student,
    decoder_digest,
    dev_schema_from_config,
    development_gate,
    encoder_parameter_count,
    load_amortized_config,
    recovery_fraction,
    run_amortized_latent,
    student_objective,
    train_student,
)
from nexus.world.context_model import ContextWorldModel
from nexus.world.context_pilot import _split_hash
from nexus.world.data import TransitionDataset
from nexus.world.direct_latent import fit_from_support, lock_network
from nexus.world.result_checks import schema_completeness


def _support(n: int = 16, seed: int = 0) -> TransitionDataset:
    rng = np.random.default_rng(seed)
    obs = rng.normal(size=(n, 3)).astype(np.float32)
    action = rng.integers(0, 3, size=n).astype(np.int64)
    return TransitionDataset(
        obs=obs, action=action, next_obs=obs + 0.1, reward=np.zeros(n, dtype=np.float32),
        terminated=np.zeros(n, dtype=bool), truncated=np.zeros(n, dtype=bool), task_id="toy",
        seed=np.full(n, seed, dtype=np.int64), episode_id=np.zeros(n, dtype=np.int64),
        policy=np.array(["random"] * n, dtype=object), physics={}, env_interactions=n,
    )


def test_config_locks_teacher_student_and_new_split() -> None:
    cfg = load_amortized_config()
    meta, dev, confirm = assert_splits(cfg)
    assert cfg["teacher_learning_rate"] == TEACHER_LR == 0.1
    assert cfg["teacher_updates"] == TEACHER_UPDATES == 256
    assert cfg["lambdas"][0] == 0
    assert cfg["encoder_hidden"] == 32 and cfg["context_dim"] == 8
    assert _split_hash(pendulum_context_confirmation()) == "87b83c41be34aa1a"
    assert _split_hash(confirm) == "d1fa621351d286cf"
    assert {s.task_id for s in (*meta, *dev, *confirm)}.isdisjoint(set(cfg["forbidden_task_ids"]))
    assert_protocol_frozen("docs/NEXUS_AMORTIZED_LATENT_INFERENCE.md", cfg)
    assert_amortized_seeds_disjoint(cfg)
    assert_prior_artifacts_unchanged(cfg)
    assert_checkpoint_hashes(cfg)


def test_drifted_lambda_grid_is_rejected(tmp_path) -> None:
    cfg = load_amortized_config()
    drifted = copy.deepcopy(cfg)
    drifted["lambdas"] = [10, 100]
    path = tmp_path / "drift.yaml"
    path.write_text(yaml.safe_dump(drifted))
    with pytest.raises(ValueError, match="drifted"):
        load_amortized_config(path)


def test_protocol_must_exist_before_a_run(tmp_path) -> None:
    cfg = load_amortized_config()
    with pytest.raises(RuntimeError, match="protocol document"):
        assert_protocol_frozen(tmp_path / "missing.md", cfg)


def test_teacher_fit_ignores_query_and_leaves_the_decoder_fixed() -> None:
    model = ContextWorldModel.create(3, 3, seed=3)
    support = _support(16, 1)
    model.obs_rms.update(support.obs)
    lock_network(model)
    with torch.no_grad():
        model.net.film.weight.normal_(0.0, 0.3)
        model.net.state_head.weight.normal_(0.0, 0.3)
    before = decoder_digest(model)
    query = _support(16, 2)
    first = fit_from_support(model, support, torch.zeros(8), lr=0.1, updates=4, snapshot_at=(4,), query=query)
    query.next_obs = query.next_obs + 5
    second = fit_from_support(model, support, torch.zeros(8), lr=0.1, updates=4, snapshot_at=(4,), query=query)
    assert decoder_digest(model) == before
    assert torch.allclose(first["final"], second["final"])


def test_student_gradients_reach_the_encoder_only() -> None:
    model = ContextWorldModel.create(3, 3, seed=5)
    support = _support(16, 4)
    model.obs_rms.update(support.obs)
    lock_network(model)
    with torch.no_grad():
        model.net.film.weight.normal_(0.0, 0.4)
        model.net.state_head.weight.normal_(0.0, 0.4)
    for param in model.encoder.parameters():
        param.requires_grad_(True)
    before = decoder_digest(model)
    count = encoder_parameter_count(model)
    loss, _z = student_objective(model, support, torch.ones(8), 10.0)
    loss.backward()
    assert any(param.grad is not None and float(param.grad.norm()) > 0 for param in model.encoder.parameters())
    assert all(param.grad is None for param in model.net.parameters())
    assert decoder_digest(model) == before
    init = {k: v.detach().cpu().clone() for k, v in model.encoder.state_dict().items()}
    snapshots = train_student(
        model, [support, _support(16, 6)], [torch.zeros(8), torch.ones(8)], lam=0.0, epochs=2, checkpoints=[2],
        budgets=[16], student_lr=0.01, seed=9, init_state=init, decoder_before=before,
    )
    assert 2 in snapshots
    assert decoder_digest(model) == before
    assert encoder_parameter_count(model) == count


def test_missing_student_seed_fails_the_locked_grid() -> None:
    cfg = load_amortized_config()
    schema = dev_schema_from_config(cfg)
    assert schema["seed_ids"] == list(range(30))
    cell = {"mae": 0.1, "rmse": 0.2, "angvel_mae": 0.3, "mae_per_dim": [0.1, 0.1, 0.1], "rollout_mae": {"3": 0.1, "8": 0.2, "16": 0.3}}
    records = []
    for seed in schema["seed_ids"]:
        if seed == 29:
            continue
        for task in schema["task_ids"]:
            for label in schema["labels"]:
                records.append({"seed": seed, "task": task, "label": label, "condition": label, **copy.deepcopy(cell)})
    report = schema_completeness(
        records, seed_ids=schema["seed_ids"], task_ids=schema["task_ids"], labels=schema["labels"],
        conditions_by_label=schema["conditions_by_label"], metrics=tuple(schema["metrics"]), horizons=tuple(schema["horizons"]), per_dim=3,
    )
    assert report["declared_complete"] is False
    assert any("seed=29" in item for item in report["failures"])


def test_inference_uses_the_loaded_encoder_and_ignores_query_arguments() -> None:
    model = ContextWorldModel.create(3, 3, seed=7)
    support = _support(16, 8)
    model.obs_rms.update(support.obs)
    lock_network(model)
    base = {key: value.detach().clone() for key, value in model.encoder.state_dict().items()}
    shifted = {key: value + 0.5 for key, value in base.items()}
    assert not torch.allclose(_infer(model, base, support, 16), _infer(model, shifted, support, 16))
    assert "query" not in inspect.signature(student_objective).parameters
    assert "query" not in inspect.signature(train_student).parameters
    assert development_gate(0.2, 0.3, 0.2) is False


def test_missing_protocol_does_not_collect(monkeypatch, tmp_path) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("collection started before the protocol check")

    monkeypatch.setattr("nexus.world.amortized_latent._collect", boom)
    with pytest.raises(RuntimeError, match="protocol document"):
        run_amortized_latent(protocol_path=tmp_path / "missing.md")


def test_selection_ties_gate_and_recovery() -> None:
    assert choose_student({"student_l10_e40_b128": 0.2, "student_l0_e400_b16": 0.2}) == (0, 400, 16)
    assert development_gate(0.2, 0.3, 0.25) is True
    assert development_gate(0.3, 0.3, 0.2) is False
    assert recovery_fraction(1.0, 0.4, 0.2) == pytest.approx(0.75)
    assert recovery_fraction(1.0, 0.4, 0.99) is None
    with pytest.raises(RuntimeError, match="development gate"):
        assert_dev_allows_confirmation({"selection_recorded": True, "gate_pass": False}, load_amortized_config())
