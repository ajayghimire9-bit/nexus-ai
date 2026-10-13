from __future__ import annotations

import copy
import json

import numpy as np
import pytest
import torch

from nexus.tasks.pendulum_family import pendulum_context_train
from nexus.world.context_model import ContextWorldModel, make_context_schedule
from nexus.world.context_pilot import _collect
from nexus.world.frozen_dynamics import (
    assert_frozen_audit_allowed,
    assert_source_splits_disjoint,
    build_selected_checkpoints,
    choose_checkpoint,
    classify_frozen,
    constant_optimizer,
    context_audit_entries,
    freeze_shared_dynamics,
    frozen_parameter_digest,
    frozen_screen,
    history_optimizer,
    load_frozen_config,
    mean_training_support_context,
    mlp_audit_entries,
    planned_env_seeds,
    require_prior_checkpoint,
    run_constant_updates,
    run_history_updates,
)
from nexus.world.result_checks import completeness_report, schema_completeness


def _toy(n: int = 160, seed: int = 0, task: str = "toy") -> "object":
    from nexus.world.data import TransitionDataset

    rng = np.random.default_rng(seed)
    obs = rng.normal(size=(n, 3)).astype(np.float32)
    action = rng.integers(0, 3, size=n)
    nxt = obs + 0.1
    half = n // 2
    return TransitionDataset(
        obs=obs,
        action=action.astype(np.int64),
        next_obs=nxt.astype(np.float32),
        reward=np.zeros(n, dtype=np.float32),
        terminated=np.zeros(n, dtype=bool),
        truncated=np.zeros(n, dtype=bool),
        task_id=task,
        seed=np.full(n, 1000 + seed, dtype=np.int64),
        episode_id=np.array([0] * half + [1] * (n - half), dtype=np.int64),
        policy=np.array(["random"] * n, dtype=object),
        physics={},
        env_interactions=n,
    )


def _prepared(seed: int = 0):
    tasks = [_toy(160, seed, "a"), _toy(160, seed + 1, "b")]
    model = ContextWorldModel.create(3, 3, seed=seed + 3)
    model.obs_rms.update(np.concatenate([ds.obs for ds in tasks]))
    freeze_shared_dynamics(model)
    return model, tasks


def _cell() -> dict:
    return {
        "mae": 0.1,
        "rmse": 0.2,
        "angvel_mae": 0.3,
        "mae_per_dim": [0.01, 0.02, 0.03],
        "rollout_mae": {"3": 0.1, "8": 0.2, "16": 0.3},
    }


def _grid() -> list[dict]:
    records = []
    for seed in (0, 1):
        for task in ("a", "b"):
            for condition in ("real", "zero", "wrong"):
                records.append({"seed": seed, "task": task, "label": "history_u0", "condition": condition, **copy.deepcopy(_cell())})
            records.append({"seed": seed, "task": task, "label": "constant_u0", "condition": "constant", **copy.deepcopy(_cell())})
    return records


_SCHEMA = {
    "seed_ids": [0, 1],
    "task_ids": ["a", "b"],
    "labels": ["history_u0", "constant_u0"],
    "conditions_by_label": {"history_u0": ["real", "zero", "wrong"], "constant_u0": ["constant"]},
}


def test_config_locks_the_frozen_budget() -> None:
    cfg = load_frozen_config()
    assert cfg["additional_updates"] == [0, 300, 1000]
    assert cfg["total_additional_updates"] == 1000
    assert cfg["confirmation_unlocked"] is False and cfg["control_sweep"] is False
    assert cfg["mlp_reference_updates"] == 1000
    assert_source_splits_disjoint(cfg)


def test_old_validator_misses_strings_booleans_and_omitted_cells() -> None:
    assert completeness_report({"angvel_mae": "0.1", "flag": True})["declared_complete"] is True
    assert completeness_report({"angvel_mae": 0.1})["declared_complete"] is True
    report = schema_completeness([{"seed": 0, "task": "a", "label": "history_u0", "condition": "real", "mae": "0.1", "rmse": True, "angvel_mae": 0.2, "mae_per_dim": [0.1], "rollout_mae": {"3": 0.1}}], **_SCHEMA)
    assert report["declared_complete"] is False


def test_schema_accepts_the_full_grid_and_rejects_each_deleted_axis() -> None:
    assert schema_completeness(_grid(), **_SCHEMA)["declared_complete"] is True
    assert schema_completeness([row for row in _grid() if row["task"] != "b"], **_SCHEMA)["declared_complete"] is False
    assert schema_completeness([row for row in _grid() if row["seed"] != 1], **_SCHEMA)["declared_complete"] is False
    assert schema_completeness([row for row in _grid() if row["condition"] != "wrong"], **_SCHEMA)["declared_complete"] is False
    assert schema_completeness([row for row in _grid() if row["label"] != "history_u0"], **_SCHEMA)["declared_complete"] is False
    missing_horizon = _grid()
    for row in missing_horizon:
        del row["rollout_mae"]["16"]
    assert schema_completeness(missing_horizon, **_SCHEMA)["declared_complete"] is False


def test_schema_rejects_duplicates_nonfinite_and_short_lists() -> None:
    duplicated = _grid()
    duplicated.append(copy.deepcopy(duplicated[0]))
    assert any("duplicate cell" in item for item in schema_completeness(duplicated, **_SCHEMA)["failures"])
    nan_grid = _grid()
    nan_grid[0]["angvel_mae"] = float("nan")
    inf_grid = _grid()
    inf_grid[0]["mae"] = float("inf")
    short = _grid()
    short[0]["mae_per_dim"] = [0.1, 0.2]
    assert schema_completeness(nan_grid, **_SCHEMA)["declared_complete"] is False
    assert schema_completeness(inf_grid, **_SCHEMA)["declared_complete"] is False
    assert schema_completeness(short, **_SCHEMA)["declared_complete"] is False


def test_frozen_weights_and_normalization_stay_fixed_while_encoder_moves() -> None:
    model, tasks = _prepared(1)
    before = frozen_parameter_digest(model)
    count = float(model.obs_rms.count)
    encoder_before = torch.cat([param.detach().flatten().clone() for param in model.encoder.parameters()])
    schedule = make_context_schedule(tasks, updates=4, seed=11, empty_prob=0.0)
    opt = history_optimizer(model, lr=1e-3)
    log = run_history_updates(model, opt, tasks, schedule)
    assert frozen_parameter_digest(model) == before
    assert float(model.obs_rms.count) == count
    assert log["max_encoder_grad_norm"] > 0.0
    assert log["max_film_grad_norm"] > 0.0
    encoder_after = torch.cat([param.detach().flatten() for param in model.encoder.parameters()])
    assert not torch.equal(encoder_before, encoder_after)
    for name, param in model.net.named_parameters():
        if not name.startswith("film."):
            assert param.grad is None or float(param.grad.detach().norm()) == 0.0


def test_clone_frozen_is_not_a_training_setup() -> None:
    model, _tasks = _prepared(2)
    frozen = model.clone_frozen()
    with pytest.raises(RuntimeError, match="not a training setup"):
        history_optimizer(frozen)


def test_constant_vector_is_shared_and_encoder_is_not_trained() -> None:
    model, tasks = _prepared(3)
    encoder_before = torch.cat([param.detach().flatten().clone() for param in model.encoder.parameters()])
    vector = torch.nn.Parameter(mean_training_support_context(model, tasks, seed=50))
    for param in model.encoder.parameters():
        param.requires_grad_(False)
    assert vector.shape == (model.context_dim(),)
    opt = constant_optimizer(model, vector, lr=1e-3)
    schedule = make_context_schedule(tasks, updates=4, seed=12, empty_prob=0.0)
    log = run_constant_updates(model, vector, opt, tasks, schedule)
    assert log["support_encodes"] == 0
    assert log["max_vector_grad_norm"] > 0.0
    assert log["max_film_grad_norm"] > 0.0
    encoder_after = torch.cat([param.detach().flatten() for param in model.encoder.parameters()])
    assert torch.equal(encoder_before, encoder_after)
    assert opt.param_groups[0]["params"][0] is vector


def test_initialization_does_not_change_the_query_schedule() -> None:
    tasks = [_toy(160, 8, "a"), _toy(160, 9, "b")]
    schedule = make_context_schedule(tasks, updates=6, seed=15, batch=8, empty_prob=0.2)
    before = [(int(row["task_index"]), row["query_index"].tolist(), bool(row["empty"])) for row in schedule]
    model, _ = _prepared(4)
    mean_training_support_context(model, tasks, seed=12345)
    after = [(int(row["task_index"]), row["query_index"].tolist(), bool(row["empty"])) for row in schedule]
    assert before == after
    history = model.clone_trainable()
    constant = model.clone_trainable()
    freeze_shared_dynamics(history)
    freeze_shared_dynamics(constant)
    for param in constant.encoder.parameters():
        param.requires_grad_(False)
    vector = torch.nn.Parameter(torch.zeros(history.context_dim()))
    h_log = run_history_updates(history, history_optimizer(history), tasks, schedule)
    c_log = run_constant_updates(constant, vector, constant_optimizer(constant, vector), tasks, schedule)
    assert h_log["query_indices"] == c_log["query_indices"] == [row["query_index"].tolist() for row in schedule]
    for row in schedule:
        support = set(np.asarray(row["support_index"]).tolist())
        query = set(np.asarray(row["query_index"]).tolist())
        assert support.isdisjoint(query)


def test_optimizer_continuity_and_immutable_snapshot() -> None:
    tasks = [_toy(160, 6, "a"), _toy(160, 7, "b")]
    schedule = make_context_schedule(tasks, updates=8, seed=21, empty_prob=0.0)
    continuous, _ = _prepared(5)
    continuous.obs_rms.update(np.concatenate([ds.obs for ds in tasks]))
    resumed = continuous.clone_trainable()
    freeze_shared_dynamics(resumed)
    opt_c = history_optimizer(continuous)
    opt_r = history_optimizer(resumed)
    run_history_updates(continuous, opt_c, tasks, schedule[:4])
    saved = copy.deepcopy(opt_c.state_dict())
    saved_exp = saved["state"][0]["exp_avg"].clone()
    mid_enc = {k: v.detach().cpu().clone() for k, v in continuous.encoder.state_dict().items()}
    mid_net = {k: v.detach().cpu().clone() for k, v in continuous.net.state_dict().items()}
    digest = frozen_parameter_digest(continuous)
    run_history_updates(continuous, opt_c, tasks, schedule[4:])
    assert torch.equal(saved["state"][0]["exp_avg"], saved_exp)
    assert not torch.equal(opt_c.state_dict()["state"][0]["exp_avg"], saved_exp)
    assert frozen_parameter_digest(continuous) == digest
    resumed.encoder.load_state_dict(mid_enc)
    resumed.net.load_state_dict(mid_net)
    opt_r.load_state_dict(copy.deepcopy(saved))
    run_history_updates(resumed, opt_r, tasks, schedule[4:])
    for left, right in zip(continuous.encoder.parameters(), resumed.encoder.parameters()):
        assert torch.allclose(left, right)
    for left, right in zip(continuous.net.parameters(), resumed.net.parameters()):
        assert torch.allclose(left, right)


def test_evaluation_does_not_change_context_or_frozen_weights() -> None:
    model, tasks = _prepared(9)
    probe = model.clone_frozen()
    probe.z = torch.arange(probe.context_dim(), dtype=torch.float32)
    z0 = probe.z.clone()
    encodes = int(probe.n_encodes)
    weight = probe.encoder.net[0].weight.detach().clone()
    digest = frozen_parameter_digest(probe)
    _pred, _term = probe.step(tasks[0].obs[:8], tasks[0].action[:8])
    assert torch.equal(probe.z, z0)
    assert int(probe.n_encodes) == encodes
    assert torch.equal(probe.encoder.net[0].weight.detach(), weight)
    assert frozen_parameter_digest(probe) == digest


def test_audit_is_blocked_without_a_saved_complete_manifest(tmp_path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(RuntimeError, match="saved"):
        assert_frozen_audit_allowed(missing)
    incomplete = tmp_path / "selection.json"
    incomplete.write_text(json.dumps({"selection_record": {"selection_recorded": False}}))
    with pytest.raises(RuntimeError, match="recorded"):
        assert_frozen_audit_allowed(incomplete)


def test_audit_plan_does_not_include_an_unselected_context_checkpoint() -> None:
    assert [row["updates"] for row in context_audit_entries(300, 0)] == [300, 0, 0]
    assert [row["label"] for row in context_audit_entries(300, 1000)] == ["history_selected", "starting", "constant_selected"]
    assert mlp_audit_entries() == [{"label": "mlp_reference", "updates": 1000, "kind": "mlp"}]
    hashes = {
        "artifacts/frozen_dynamics_checkpoints/seed0_history_u300.pt": "a",
        "artifacts/frozen_dynamics_checkpoints/seed0_history_u0.pt": "b",
        "artifacts/frozen_dynamics_checkpoints/seed0_history_u1000.pt": "ignored",
        "artifacts/frozen_dynamics_checkpoints/seed0_constant_u0.pt": "c",
        "artifacts/context_optimization_checkpoints/seed0_mlp_u1000.pt": "d",
    }
    selected = build_selected_checkpoints(history_updates=300, constant_updates=0, mlp_updates=1000, seeds=[0], checkpoint_sha256=hashes)
    assert set(selected) == {"history_selected", "starting", "constant_selected", "mlp_reference"}
    blob = json.dumps(selected)
    assert "history_u1000" not in blob
    assert selected["history_selected"]["updates"] == 300
    assert selected["mlp_reference"]["updates"] == 1000
    assert selected["mlp_reference"]["paths"]["0"].endswith("mlp_u1000.pt")


def test_checkpoint_tie_prefers_zero_updates_and_screen_rules() -> None:
    assert choose_checkpoint({0: 0.2, 300: 0.2, 1000: 0.3}) == 0
    good = [_screen_row(0.80) for _ in range(3)]
    assert frozen_screen(good)["pass"] is True
    weak = [_screen_row(0.99) for _ in range(3)]
    assert frozen_screen(weak)["pass"] is False
    recalibrated = [_screen_row(0.80, constant=0.81) for _ in range(3)]
    screen = frozen_screen(recalibrated)
    assert screen["generic_recalibration"] is True and screen["pass"] is False
    assert classify_frozen(300, screen)["label"] == "generic_recalibration"
    worse_than_start = [_screen_row(0.80, start=0.70) for _ in range(3)]
    assert frozen_screen(worse_than_start)["start_ok"] is False
    one_seed = [_screen_row(0.80), _screen_row(1.10), _screen_row(1.10)]
    assert frozen_screen(one_seed)["positive_seeds"] == 1
    harmful = [_screen_row(0.80, mae_real=1.06) for _ in range(3)]
    assert frozen_screen(harmful)["harm_ok"] is False
    assert classify_frozen(0, frozen_screen(good))["additional_training_helped"] is False
    assert classify_frozen(0, frozen_screen(good))["label"] == "checkpoint_0_selected"


def _screen_row(real: float, *, zero: float = 1.0, wrong: float = 1.0, constant: float = 1.0, start: float = 1.0, mae_real: float = 1.0) -> dict[str, float]:
    return {
        "angvel_real": real,
        "angvel_zero": zero,
        "angvel_wrong": wrong,
        "angvel_constant": constant,
        "angvel_start": start,
        "angvel_mlp": 0.5,
        "mae_real": mae_real,
        "mae_zero": 1.0,
        "h16_real": 1.0,
        "h16_zero": 1.0,
    }


def test_hash_mismatch_does_not_accept_a_stand_in_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("nexus.world.frozen_dynamics.PRIOR_CHECKPOINT_DIR", tmp_path)
    (tmp_path / "seed0_context_u3000.pt").write_bytes(b"not-the-recorded-checkpoint")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        require_prior_checkpoint(0, "context", 3000, "0" * 64)


def test_planned_seeds_match_a_pendulum_collection() -> None:
    spec = pendulum_context_train()[0]
    ds = _collect(spec, 40, env0=91000, base=250_000)
    assert {int(s) for s in np.unique(ds.seed)} == planned_env_seeds(40, 91000)
