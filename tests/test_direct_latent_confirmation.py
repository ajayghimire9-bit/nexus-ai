from __future__ import annotations

import copy

import numpy as np
import pytest
import torch
import yaml

from nexus.tasks.pendulum_family import pendulum_context_confirmation
from nexus.world.context_model import ContextWorldModel
from nexus.world.context_pilot import _split_hash
from nexus.world.data import TransitionDataset
from nexus.world.direct_latent import frozen_network_digest, lock_network
from nexus.world.direct_latent_confirmation import (
    CONFIRM_LR,
    CONFIRM_UPDATES,
    assert_checkpoint_hashes,
    assert_confirmation_seeds_disjoint,
    assert_prior_artifacts_unchanged,
    assert_protocol_frozen,
    assert_split_matches,
    confirmation_schema_from_config,
    fit_confirmation_latent,
    load_confirmation_config,
    support_for,
    task_level_report,
)
from nexus.world.direct_latent import support_for as latent_support_for
from nexus.world.result_checks import schema_completeness


def test_split_hash_and_tuples_match_the_reserved_set() -> None:
    cfg = load_confirmation_config()
    specs = assert_split_matches(cfg)
    assert _split_hash(pendulum_context_confirmation()) == "87b83c41be34aa1a"
    assert [spec.task_id for spec in specs] == ["pendulum_ctx_c0", "pendulum_ctx_c1", "pendulum_ctx_c2", "pendulum_ctx_c3"]
    assert cfg["learning_rate"] == CONFIRM_LR == 0.1
    assert cfg["updates"] == CONFIRM_UPDATES == 256
    assert cfg["support_budget"] == 128
    assert cfg["same_decoder_conditions"] == ["task", "zero", "global", "wrong", "encoder"]
    assert cfg["external_conditions"] == ["mlp_reference"]


def test_runner_does_not_collect_before_the_protocol_is_frozen(tmp_path, monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("environment was stepped")

    monkeypatch.setattr("nexus.world.direct_latent_confirmation._collect", boom)
    from nexus.world.direct_latent_confirmation import run_direct_latent_confirmation

    with pytest.raises(RuntimeError, match="protocol document"):
        run_direct_latent_confirmation(protocol_path=tmp_path / "missing.md", output_path=tmp_path / "out.json")


def test_protocol_must_be_frozen_before_confirmation(tmp_path) -> None:
    cfg = load_confirmation_config()
    assert_protocol_frozen("docs/NEXUS_DIRECT_LATENT_CONFIRMATION.md", cfg)
    missing = tmp_path / "missing.md"
    with pytest.raises(RuntimeError, match="protocol document"):
        assert_protocol_frozen(missing, cfg)
    blank = tmp_path / "blank.md"
    blank.write_text("no lock\n")
    with pytest.raises(RuntimeError, match="protocol lock"):
        assert_protocol_frozen(blank, cfg)


def test_drifted_optimizer_is_rejected(tmp_path) -> None:
    cfg = load_confirmation_config()
    drifted = copy.deepcopy(cfg)
    drifted["learning_rate"] = 0.01
    path = tmp_path / "drift.yaml"
    path.write_text(yaml.safe_dump(drifted))
    with pytest.raises(ValueError, match="drifted"):
        load_confirmation_config(path)


def test_prior_artifacts_and_checkpoints_stay_immutable() -> None:
    cfg = load_confirmation_config()
    assert_prior_artifacts_unchanged(cfg)
    assert_checkpoint_hashes(cfg)
    changed = copy.deepcopy(cfg)
    changed["prior_artifact_sha256"]["artifacts/direct_latent_audit.json"] = "0" * 64
    with pytest.raises(RuntimeError, match="changed"):
        assert_prior_artifacts_unchanged(changed)


def test_confirmation_seeds_do_not_overlap_support_and_query() -> None:
    cfg = load_confirmation_config()
    assert_confirmation_seeds_disjoint(cfg)


def test_wrong_donor_is_the_next_confirmation_task() -> None:
    supports = []
    for i in range(4):
        obs = np.zeros((4, 3), dtype=np.float32)
        supports.append(
            TransitionDataset(
                obs=obs,
                action=np.zeros(4, dtype=np.int64),
                next_obs=obs + 0.1,
                reward=np.zeros(4, dtype=np.float32),
                terminated=np.zeros(4, dtype=bool),
                truncated=np.zeros(4, dtype=bool),
                task_id=f"pendulum_ctx_c{i}",
                seed=np.full(4, 64000 + 10 * i, dtype=np.int64),
                episode_id=np.zeros(4, dtype=np.int64),
                policy=np.array(["random"] * 4, dtype=object),
                physics={},
                env_interactions=4,
            )
        )
    assert support_for(supports, 3, "wrong").task_id == "pendulum_ctx_c0"
    assert support_for(supports, 0, "wrong").task_id == "pendulum_ctx_c1"
    assert latent_support_for(supports, 3, "wrong").task_id == "pendulum_ctx_c0"


def test_only_z_changes_under_the_locked_rule() -> None:
    rng = np.random.default_rng(0)
    obs = rng.normal(size=(16, 3)).astype(np.float32)
    action = rng.integers(0, 3, size=16).astype(np.int64)
    model = ContextWorldModel.create(3, 3, seed=7)
    model.obs_rms.update(obs)
    lock_network(model)
    with torch.no_grad():
        model.net.film.weight.normal_(0.0, 0.4)
        model.net.state_head.weight.normal_(0.0, 0.4)
    obs_n = torch.as_tensor(model.normalize(obs))
    with torch.no_grad():
        pred, _logit = model.net(obs_n, torch.as_tensor(action), torch.ones(8))
        nxt = model.unnormalize((obs_n + pred).cpu().numpy())
    support = TransitionDataset(
        obs=obs,
        action=action,
        next_obs=nxt,
        reward=np.zeros(16, dtype=np.float32),
        terminated=np.zeros(16, dtype=bool),
        truncated=np.zeros(16, dtype=bool),
        task_id="toy",
        seed=np.full(16, 1, dtype=np.int64),
        episode_id=np.zeros(16, dtype=np.int64),
        policy=np.array(["random"] * 16, dtype=object),
        physics={},
        env_interactions=16,
    )
    query = copy.deepcopy(support)
    query.next_obs = query.next_obs + 3.0
    digest = frozen_network_digest(model)
    first = fit_confirmation_latent(model, support, torch.zeros(8), query=query)
    query.next_obs += 5.0
    second = fit_confirmation_latent(model, support, torch.zeros(8), query=query)
    assert frozen_network_digest(model) == digest
    assert torch.allclose(first["final"], second["final"])
    assert len(first["trace"]) == CONFIRM_UPDATES + 1
    assert float(torch.linalg.vector_norm(first["final"])) > 0.0


def test_missing_task_fails_the_locked_grid() -> None:
    cfg = load_confirmation_config()
    schema = confirmation_schema_from_config(cfg)
    cell = {"mae": 0.1, "rmse": 0.2, "angvel_mae": 0.3, "mae_per_dim": [0.01, 0.02, 0.03], "rollout_mae": {"3": 0.1, "8": 0.2, "16": 0.3}}
    records = []
    for seed in schema["seed_ids"]:
        for task in schema["task_ids"]:
            if task == "pendulum_ctx_c3":
                continue
            for label in schema["labels"]:
                records.append({"seed": seed, "task": task, "label": label, "condition": label, **copy.deepcopy(cell)})
    built = confirmation_schema_from_config(cfg)
    assert built["task_ids"] == ["pendulum_ctx_c0", "pendulum_ctx_c1", "pendulum_ctx_c2", "pendulum_ctx_c3"]
    report = schema_completeness(
        records,
        seed_ids=built["seed_ids"],
        task_ids=built["task_ids"],
        labels=built["labels"],
        conditions_by_label=built["conditions_by_label"],
        metrics=tuple(built["metrics"]),
        horizons=tuple(built["horizons"]),
        per_dim=3,
    )
    assert report["declared_complete"] is False
    assert any("pendulum_ctx_c3" in item for item in report["failures"])


def test_task_level_miss_is_reported_without_shrinking_the_grid() -> None:
    records = []
    for seed in (0, 1, 2):
        for task, task_v in (("pendulum_ctx_c0", 0.05), ("pendulum_ctx_c1", 0.20)):
            for label, value in (("task", task_v), ("zero", 0.10), ("global", 0.10), ("wrong", 0.10), ("encoder", 0.11), ("mlp_reference", 0.12)):
                records.append({"seed": seed, "task": task, "label": label, "angvel_mae": value})
    report = task_level_report(records, ["pendulum_ctx_c0", "pendulum_ctx_c1"])
    assert report[0]["task_point_screen"] is True
    assert report[1]["task_point_screen"] is False
    assert "zero" in report[1]["misses_five_percent"]
