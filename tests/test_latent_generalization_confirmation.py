from __future__ import annotations

import copy

import pytest
import yaml

from nexus.tasks.pendulum_family import pendulum_latent_confirmation, pendulum_latent_train, pendulum_physics_key
from nexus.world.latent_generalization_confirmation import (
    assert_confirmation_physics,
    assert_confirmation_seeds,
    assert_protocol_frozen,
    assert_reproduction,
    confirmation_gate,
    load_confirmation_config,
    recommend_confirmation,
    recovery_fraction,
)
from nexus.world.result_checks import schema_completeness
from nexus.world.latent_generalization_confirmation import confirm_schema


def test_config_locks_the_new_split_and_the_effect_size() -> None:
    cfg = load_confirmation_config()
    specs = assert_confirmation_physics(cfg)
    assert [spec.task_id for spec in specs] == [f"pendulum_lat_cf{i}" for i in range(4)]
    train_g = {key[0] for key in (pendulum_physics_key(spec) for spec in pendulum_latent_train())}
    for spec in pendulum_latent_confirmation():
        g, m, l = pendulum_physics_key(spec)
        outside = g < 7.3 or g > 13.2 or m < 0.65 or m > 1.05 or l < 0.78 or l > 1.22
        assert outside
        assert g not in train_g or m not in {0.65, 1.05} or l not in {0.78, 1.22}
    assert cfg["minimum_effect"] == 0.01
    assert cfg["confirmation_epoch"] == 200
    assert_protocol_frozen("docs/NEXUS_LATENT_GENERALIZATION_CONFIRMATION.md", cfg)
    assert_confirmation_seeds(cfg)


def test_drifted_effect_size_is_rejected(tmp_path) -> None:
    cfg = load_confirmation_config()
    drifted = copy.deepcopy(cfg)
    drifted["minimum_effect"] = 0.0
    path = tmp_path / "drift.yaml"
    path.write_text(yaml.safe_dump(drifted))
    with pytest.raises(ValueError, match="drifted"):
        load_confirmation_config(path)


def test_missing_protocol_does_not_retrain(monkeypatch, tmp_path) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("retraining started before the protocol check")

    monkeypatch.setattr("nexus.world.latent_generalization_confirmation.run_latent_generalization", boom)
    from nexus.world.latent_generalization_confirmation import run_latent_generalization_confirmation

    with pytest.raises(RuntimeError, match="protocol document"):
        run_latent_generalization_confirmation(protocol_path=tmp_path / "missing.md")


def test_a_development_mismatch_blocks_confirmation(monkeypatch) -> None:
    calls = []

    def fake_run(**kwargs):
        kwargs["sink"]["snapshots"] = {}
        kwargs["sink"]["decoder_digests"] = []
        return {
            "chosen_epoch": 100,
            "means": {"student": 0.2, "zero": 0.2, "encoder": 0.2, "global": 0.2, "teacher": 0.2, "baseline": 0.2},
            "dev_checkpoint_angvel": {"40": 0.2, "100": 0.2, "200": 0.2},
            "train_latent_l2": 1.0,
            "history_latent_l2": 1.0,
            "teacher_pair_median_l2": 1.0,
            "pair_rows": [],
            "resources": {"teacher_optimizer_steps": 30720, "student_optimizer_steps": 96000},
        }

    def watch(*args, **_kwargs):
        calls.append(getattr(args[0], "task_id", ""))
        raise AssertionError("confirmation collection started")

    monkeypatch.setattr("nexus.world.latent_generalization_confirmation.run_latent_generalization", fake_run)
    monkeypatch.setattr("nexus.world.latent_generalization._collect", watch)
    from nexus.world.latent_generalization_confirmation import run_latent_generalization_confirmation

    with pytest.raises(RuntimeError, match="confirmation stays closed"):
        run_latent_generalization_confirmation()
    assert calls == []


def test_confirmation_teacher_fit_requires_a_locked_decoder() -> None:
    from nexus.world.context_model import ContextWorldModel
    from nexus.world.data import TransitionDataset
    from nexus.world.direct_latent import lock_network
    from nexus.world.latent_generalization import _fit_teacher
    import numpy as np
    import torch

    rng = np.random.default_rng(0)
    n = 8
    obs = rng.normal(size=(n, 3)).astype(np.float32)
    action = rng.integers(0, 3, size=n).astype(np.int64)
    support = TransitionDataset(
        obs=obs, action=action, next_obs=obs + 0.05, reward=np.zeros(n, dtype=np.float32),
        terminated=np.zeros(n, dtype=bool), truncated=np.zeros(n, dtype=bool), task_id="toy",
        seed=np.zeros(n, dtype=np.int64), episode_id=np.zeros(n, dtype=np.int64),
        policy=np.array(["random"] * n, dtype=object), physics={}, env_interactions=n,
    )
    unlocked = ContextWorldModel.create(3, 3, seed=1)
    unlocked.obs_rms.update(obs)
    with pytest.raises(RuntimeError, match="received a gradient"):
        _fit_teacher(unlocked, support, torch.zeros(8))
    locked = ContextWorldModel.create(3, 3, seed=1)
    locked.obs_rms.update(obs)
    lock_network(locked)
    vector = _fit_teacher(locked, support, torch.zeros(8))
    assert torch.isfinite(vector).all()


def test_reproduction_tolerance_and_the_primary_gate() -> None:
    cfg = load_confirmation_config()
    reference = {
        "means": {"student": 0.0913, "zero": 0.1587, "encoder": 0.1773, "global": 0.1478, "teacher": 0.0781, "baseline": 0.1672},
        "dev_checkpoint_angvel": {"40": 0.1513, "100": 0.0988, "200": 0.0913},
        "train_latent_l2": 0.648,
        "history_latent_l2": 1.752,
        "teacher_pair_median_l2": 1.522,
        "pair_rows": [{"role": "train", "decoder": 0, "task": "pendulum_lat_tr0", "support_index": 0, "support_hash": "aa", "vector_sha256": "bb"}],
    }
    matched = copy.deepcopy(reference)
    matched["chosen_epoch"] = 200
    matched["resources"] = {"teacher_optimizer_steps": 30720, "student_optimizer_steps": 96000}
    assert_reproduction(matched, reference, cfg)
    shifted = copy.deepcopy(matched)
    shifted["means"]["student"] = 0.0913 + 0.001
    with pytest.raises(RuntimeError, match="student"):
        assert_reproduction(shifted, reference, cfg)

    passed, report = confirmation_gate({name: [0.02, 0.021, 0.019] for name in ("zero", "encoder", "global")}, 0.01)
    assert passed is True
    assert report["global"]["interval"]["df"] == 2
    trivial, _ = confirmation_gate({name: [0.009, 0.009, 0.009] for name in ("zero", "encoder", "global")}, 0.01)
    assert trivial is False
    mixed, _ = confirmation_gate({"zero": [0.05, 0.05, -0.04], "encoder": [0.05, 0.05, 0.05], "global": [0.05, 0.05, 0.05]}, 0.01)
    assert mixed is False
    assert recommend_confirmation(True, 0.0, [0.02, 0.02, 0.02], 1.7, 1.2) == "mpc_return_pilot"
    assert recommend_confirmation(False, 0.5, [0.02, 0.02, 0.02], 1.7, 1.2) == "teacher_failure"
    assert recommend_confirmation(False, 0.0, [0.02, -0.01, 0.02], 1.7, 1.2) == "decoder_variability"
    assert recommend_confirmation(False, 0.0, [-0.02, -0.02, -0.02], 1.7, 1.2) == "support_history_uncertainty"
    assert recommend_confirmation(False, 0.0, [-0.02, -0.02, -0.02], 0.1, 0.1) == "task_shift"
    assert recovery_fraction(0.15, 0.09, 0.08, 0.05) is not None
    assert recovery_fraction(0.15, 0.09, 0.15, 0.05) is None
    schema = confirm_schema(cfg)
    assert schema["seed_ids"] == list(range(15))
    assert schema["task_ids"] == [f"pendulum_lat_cf{i}" for i in range(4)]
    cell = {"mae": 0.1, "rmse": 0.2, "angvel_mae": 0.3, "mae_per_dim": [0.1, 0.1, 0.1], "rollout_mae": {"3": 0.1, "8": 0.2, "16": 0.3}}
    records = []
    for seed in schema["seed_ids"]:
        if seed == 7:
            continue
        for task in schema["task_ids"]:
            for label in schema["labels"]:
                records.append({"seed": seed, "task": task, "label": label, "condition": label, **copy.deepcopy(cell)})
    report = schema_completeness(
        records, seed_ids=schema["seed_ids"], task_ids=schema["task_ids"], labels=schema["labels"],
        conditions_by_label=schema["conditions_by_label"], metrics=tuple(schema["metrics"]), horizons=tuple(schema["horizons"]), per_dim=3,
    )
    assert report["declared_complete"] is False
    assert any("seed=7" in item for item in report["failures"])
