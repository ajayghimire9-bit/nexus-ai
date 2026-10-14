from __future__ import annotations

import copy

import numpy as np
import pytest
import torch
import yaml

from nexus.tasks.pendulum_family import pendulum_amortized_confirmation, pendulum_context_confirmation
from nexus.world.context_model import ContextWorldModel
from nexus.world.data import TransitionDataset
from nexus.world.direct_latent import lock_network
from nexus.world.latent_generalization import (
    assert_checkpoint_hashes,
    assert_pair_binding,
    assert_physics,
    assert_protocol_frozen,
    assert_seeds_disjoint,
    choose_epoch,
    decoder_digest,
    development_gate,
    load_generalization_config,
    recommend,
    train_pairs,
)
from nexus.world.result_checks import schema_completeness
from nexus.world.latent_generalization import dev_schema


def _support(n: int = 8, seed: int = 0) -> TransitionDataset:
    rng = np.random.default_rng(seed)
    obs = rng.normal(size=(n, 3)).astype(np.float32)
    action = rng.integers(0, 3, size=n).astype(np.int64)
    return TransitionDataset(
        obs=obs, action=action, next_obs=obs + 0.05, reward=np.zeros(n, dtype=np.float32),
        terminated=np.zeros(n, dtype=bool), truncated=np.zeros(n, dtype=bool), task_id="toy",
        seed=np.full(n, seed, dtype=np.int64), episode_id=np.zeros(n, dtype=np.int64),
        policy=np.array(["random"] * n, dtype=object), physics={}, env_interactions=n,
    )


def test_config_locks_splits_and_the_student_rate() -> None:
    cfg = load_generalization_config()
    train, val, dev = assert_physics(cfg)
    forbidden = {spec.task_id for spec in pendulum_context_confirmation()} | {spec.task_id for spec in pendulum_amortized_confirmation()}
    assert forbidden.isdisjoint({spec.task_id for spec in (*train, *val, *dev)})
    assert cfg["student_learning_rate"] == 0.01
    assert cfg["n_parameters"] == 584
    assert cfg["epochs"] == [40, 100, 200]
    assert_protocol_frozen("docs/NEXUS_LATENT_GENERALIZATION.md", cfg)
    assert_seeds_disjoint(cfg)
    assert_checkpoint_hashes(cfg)


def test_drifted_epoch_grid_is_rejected(tmp_path) -> None:
    cfg = load_generalization_config()
    drifted = copy.deepcopy(cfg)
    drifted["epochs"] = [40, 200]
    path = tmp_path / "drift.yaml"
    path.write_text(yaml.safe_dump(drifted))
    with pytest.raises(ValueError, match="drifted"):
        load_generalization_config(path)


def test_missing_protocol_does_not_collect(monkeypatch, tmp_path) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("collection started before the protocol check")

    monkeypatch.setattr("nexus.world.latent_generalization._collect", boom)
    from nexus.world.latent_generalization import run_latent_generalization

    with pytest.raises(RuntimeError, match="protocol document"):
        run_latent_generalization(protocol_path=tmp_path / "missing.md")


def test_a_teacher_from_another_history_is_refused() -> None:
    with pytest.raises(RuntimeError, match="different support"):
        assert_pair_binding("aaaa", "bbbb")


def test_training_keeps_the_decoder_fixed() -> None:
    model = ContextWorldModel.create(3, 3, seed=2)
    supports = [_support(8, 3), _support(8, 4)]
    for ds in supports:
        model.obs_rms.update(ds.obs)
    lock_network(model)
    before = decoder_digest(model)
    init = {key: value.detach().clone() for key, value in model.encoder.state_dict().items()}
    snapshots, stats, grad = train_pairs(
        model, supports, [torch.zeros(8), torch.ones(8)], epochs=2, checkpoints=[2], lr=0.01,
        seed=11, init_state=init, decoder_before=before, budget=8,
    )
    assert 2 in snapshots
    assert stats[2]["mean"] >= 0
    assert grad > 0
    assert decoder_digest(model) == before
    assert int(sum(param.numel() for param in model.encoder.parameters())) == 584


def test_checkpoint_choice_gate_and_failure_paths() -> None:
    cfg = load_generalization_config()
    assert choose_epoch({100: 0.2, 40: 0.2, 200: 0.3}) == 40
    assert development_gate(0.1, 0.2, 0.15) is True
    assert development_gate(0.2, 0.2, 0.1) is False
    assert recommend(True, True, 0.01, 0.02, 0.1, cfg) == "new_confirmation"
    assert recommend(True, False, 0.01, 0.02, 0.1, cfg) == "hold_confirmation"
    assert recommend(False, False, 0.4, 0.1, 0.8, cfg) == "label_variability"
    assert recommend(False, False, 0.4, 0.1, 0.2, cfg) == "training_budget"
    assert recommend(False, False, 0.1, 0.8, 0.2, cfg) == "attention_pool"
    assert recommend(False, False, 0.1, 0.2, 0.2, cfg) == "more_source_tasks"
    schema = dev_schema(cfg)
    assert schema["seed_ids"] == list(range(15))
    cell = {"mae": 0.1, "rmse": 0.2, "angvel_mae": 0.3, "mae_per_dim": [0.1, 0.1, 0.1], "rollout_mae": {"3": 0.1, "8": 0.2, "16": 0.3}}
    records = []
    for seed in schema["seed_ids"]:
        if seed == 14:
            continue
        for task in schema["task_ids"]:
            for label in schema["labels"]:
                records.append({"seed": seed, "task": task, "label": label, "condition": label, **copy.deepcopy(cell)})
    report = schema_completeness(
        records, seed_ids=schema["seed_ids"], task_ids=schema["task_ids"], labels=schema["labels"],
        conditions_by_label=schema["conditions_by_label"], metrics=tuple(schema["metrics"]), horizons=tuple(schema["horizons"]), per_dim=3,
    )
    assert report["declared_complete"] is False
    assert any("seed=14" in item for item in report["failures"])
