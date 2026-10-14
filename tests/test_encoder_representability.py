from __future__ import annotations

import copy

import numpy as np
import pytest
import torch
import yaml

from nexus.tasks.pendulum_family import pendulum_amortized_confirmation, pendulum_context_confirmation, pendulum_context_train
from nexus.world.context_model import ContextWorldModel
from nexus.world.data import TransitionDataset
from nexus.world.direct_latent import lock_network
from nexus.world.encoder_representability import (
    assert_checkpoint_hashes,
    assert_protocol_frozen,
    assert_saved_targets,
    assert_seeds_disjoint,
    choose_learning_rate,
    constant_code,
    decoder_digest,
    decoder_is_ambiguous,
    decoder_passes,
    distances,
    load_representability_config,
    pair_is_equivalent,
    recommend,
    train_encoder,
    trajectory_complete,
)


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


def test_config_locks_previous_rate_and_saved_targets() -> None:
    cfg = load_representability_config()
    assert 0.001 in cfg["learning_rates"]
    assert cfg["max_steps"] == 2000
    assert cfg["mean_l2_threshold"] == 0.25
    assert cfg["n_parameters"] == 584
    rows = assert_saved_targets(cfg)
    assert len(rows) == 24
    assert {row["task"] for row in rows} == {spec.task_id for spec in pendulum_context_train()}
    forbidden = {spec.task_id for spec in pendulum_context_confirmation()} | {spec.task_id for spec in pendulum_amortized_confirmation()}
    assert forbidden.isdisjoint({row["task"] for row in rows})
    assert_protocol_frozen("docs/NEXUS_ENCODER_REPRESENTABILITY.md", cfg)
    assert_seeds_disjoint(cfg)
    assert_checkpoint_hashes(cfg)


def test_drifted_learning_rate_is_rejected(tmp_path) -> None:
    cfg = load_representability_config()
    drifted = copy.deepcopy(cfg)
    drifted["learning_rates"] = [0.01, 0.1]
    path = tmp_path / "drift.yaml"
    path.write_text(yaml.safe_dump(drifted))
    with pytest.raises(ValueError, match="drifted"):
        load_representability_config(path)


def test_missing_protocol_blocks_before_collection(monkeypatch, tmp_path) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("collection started before the protocol check")

    monkeypatch.setattr("nexus.world.encoder_representability._collect", boom)
    from nexus.world.encoder_representability import run_encoder_representability

    with pytest.raises(RuntimeError, match="protocol document"):
        run_encoder_representability(protocol_path=tmp_path / "missing.md")


def test_training_updates_only_the_encoder() -> None:
    model = ContextWorldModel.create(3, 3, seed=4)
    supports = [_support(8, 1), _support(8, 2)]
    for ds in supports:
        model.obs_rms.update(ds.obs)
    lock_network(model)
    before = decoder_digest(model)
    init = {key: value.detach().clone() for key, value in model.encoder.state_dict().items()}
    teachers = [torch.zeros(8), torch.ones(8)]
    logs = train_encoder(
        model, supports, teachers, ["a", "b"], lr=0.05, steps=2, log_steps=[0, 2],
        init_state=init, decoder_before=before,
    )
    assert [row["step"] for row in logs] == [0, 2]
    assert decoder_digest(model) == before
    assert logs[-1]["grad_norm"] is not None and logs[-1]["grad_norm"] > 0
    assert int(sum(param.numel() for param in model.encoder.parameters())) == 584


def test_threshold_constant_predictor_and_recommendation() -> None:
    cfg = load_representability_config()
    targets = [torch.tensor([1.0, 0.0]), torch.tensor([-1.0, 0.0])]
    const = constant_code(targets)
    dists = distances([const, const], targets)
    assert float(np.mean(dists)) == pytest.approx(1.0)
    assert decoder_passes(0.25, 0.5, 1.0, cfg) is True
    assert decoder_passes(0.2500001, 0.4, 1.0, cfg) is False
    assert decoder_passes(0.2, 0.5000001, 1.0, cfg) is False
    assert decoder_passes(0.2, 0.4, 0.2, cfg) is False
    assert trajectory_complete([0, 1, 2000], [0, 2000, 1]) is True
    assert trajectory_complete([0, 2000], [0, 1, 2000]) is False
    assert choose_learning_rate({0.1: 0.4, 0.001: 0.4, 0.01: 0.5}) == pytest.approx(0.001)
    assert pair_is_equivalent(0.8, 0.05, 0.05, cfg) is True
    assert pair_is_equivalent(0.8, 0.2, 0.05, cfg) is False
    assert pair_is_equivalent(0.4, 0.01, 0.01, cfg) is False
    assert decoder_is_ambiguous(0.8, 4, 2, cfg) is True
    assert decoder_is_ambiguous(0.8, 4, 1, cfg) is False
    assert recommend(True, True, 1.0, cfg) == "null_space"
    assert recommend(True, False, 1.0, cfg) == "generalization"
    assert recommend(False, False, 1e-12, cfg) == "optimizer"
    assert recommend(False, False, 1e-3, cfg) == "attention_pool"
