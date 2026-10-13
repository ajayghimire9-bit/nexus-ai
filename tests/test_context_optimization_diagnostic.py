from __future__ import annotations

import copy

import numpy as np
import pytest
import torch

from nexus.world.context_diagnosis import open_loop_mae
from nexus.world.context_model import (
    ContextWorldModel,
    context_optimizer,
    make_context_schedule,
    run_context_updates,
)
from nexus.world.context_optimization import (
    assert_audit_allowed,
    choose_checkpoint,
    load_optimization_config,
    optimization_screen,
)
from nexus.world.data import TransitionDataset, assert_disjoint_seeds
from nexus.world.result_checks import completeness_report


def _toy(n: int = 160, seed: int = 0, task: str = "toy") -> TransitionDataset:
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


def _line(n: int, origin: float, episode: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    obs = (origin + np.arange(n, dtype=np.float32))[:, None]
    return obs, obs + 1.0, np.full(n, episode, dtype=np.int64)


class _PlusOne:
    def __init__(self) -> None:
        self.z = torch.zeros(1)
        self.n_encodes = 0

    def step(self, obs: np.ndarray, action: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        del action
        out = np.asarray(obs, dtype=np.float32) + 1.0
        return out, np.zeros(out.shape[0], dtype=np.float32)


def test_config_locks_the_budget() -> None:
    cfg = load_optimization_config()
    assert cfg["updates"] == [300, 1000, 3000]
    assert cfg["confirmation_unlocked"] is False and cfg["control_sweep"] is False


def test_rollout_endpoint_and_episode_boundary() -> None:
    obs0, nxt0, ep0 = _line(40, 0.0, 0)
    obs1, nxt1, ep1 = _line(200, 1000.0, 1)
    ds = TransitionDataset(
        obs=np.vstack([obs0, obs1]),
        action=np.zeros(240, dtype=np.int64),
        next_obs=np.vstack([nxt0, nxt1]),
        reward=np.zeros(240, dtype=np.float32),
        terminated=np.zeros(240, dtype=bool),
        truncated=np.array([False] * 39 + [True] + [False] * 199 + [True]),
        task_id="line",
        seed=np.zeros(240, dtype=np.int64),
        episode_id=np.concatenate([ep0, ep1]),
        policy=np.array(["random"] * 240, dtype=object),
        physics={},
        env_interactions=240,
    )
    roll = open_loop_mae(_PlusOne(), ds, [16])
    assert roll["16"] < 1e-6
    # Episode of length 40 contributes only the start at 0. The length-200 episode contributes six starts.
    assert roll["windows_16"] == 7
    assert roll["n_episodes"] == 2
    z0 = torch.zeros(1)
    model = _PlusOne()
    model.z = z0.clone()
    open_loop_mae(model, ds, [3, 8])
    assert torch.equal(model.z, z0)
    assert model.n_encodes == 0


def test_schedule_prefix_and_immutable_snapshot() -> None:
    tasks = [_toy(160, 1, "a"), _toy(160, 2, "b")]
    long = make_context_schedule(tasks, updates=12, seed=5, empty_prob=0.0)
    short = make_context_schedule(tasks, updates=4, seed=5, empty_prob=0.0)
    assert [row["task_index"] for row in long[:4]] == [row["task_index"] for row in short]
    assert [row["query_index"].tolist() for row in long[:4]] == [row["query_index"].tolist() for row in short]
    left = ContextWorldModel.create(3, 3, seed=9)
    left.obs_rms.update(np.concatenate([ds.obs for ds in tasks]))
    opt_l = context_optimizer(left)
    run_context_updates(left, opt_l, tasks, long[:4], support_mode="fixed")
    snap = torch.cat([v.detach().flatten().clone() for v in left.encoder.state_dict().values()])
    run_context_updates(left, opt_l, tasks, long[4:], support_mode="fixed")
    live = torch.cat([v.detach().flatten() for v in left.encoder.state_dict().values()])
    assert not torch.equal(snap, live)


def test_resume_matches_continuous_training() -> None:
    tasks = [_toy(160, 3, "a"), _toy(160, 4, "b")]
    schedule = make_context_schedule(tasks, updates=8, seed=7, empty_prob=0.0)
    continuous = ContextWorldModel.create(3, 3, seed=11)
    obs = np.concatenate([ds.obs for ds in tasks])
    continuous.obs_rms.update(obs)
    resumed = continuous.clone_trainable()
    opt_c = context_optimizer(continuous)
    run_context_updates(continuous, opt_c, tasks, schedule[:4], support_mode="fixed")
    mid_enc = {k: v.detach().cpu().clone() for k, v in continuous.encoder.state_dict().items()}
    mid_net = {k: v.detach().cpu().clone() for k, v in continuous.net.state_dict().items()}
    mid_opt = copy.deepcopy(opt_c.state_dict())
    run_context_updates(continuous, opt_c, tasks, schedule[4:], support_mode="fixed")
    assert not torch.equal(mid_enc["net.2.weight"], continuous.encoder.state_dict()["net.2.weight"])
    resumed.encoder.load_state_dict(mid_enc)
    resumed.net.load_state_dict(mid_net)
    resumed.copy_rms(continuous.obs_rms)
    opt_r = context_optimizer(resumed)
    opt_r.load_state_dict(mid_opt)
    run_context_updates(resumed, opt_r, tasks, schedule[4:], support_mode="fixed")
    for a, b in zip(continuous.encoder.parameters(), resumed.encoder.parameters()):
        assert torch.allclose(a, b)
    for a, b in zip(continuous.net.parameters(), resumed.net.parameters()):
        assert torch.allclose(a, b)


def test_eval_clone_does_not_change_later_updates() -> None:
    tasks = [_toy(160, 5), _toy(160, 6, "b")]
    schedule = make_context_schedule(tasks, updates=6, seed=2, empty_prob=0.0)
    live = ContextWorldModel.create(3, 3, seed=4)
    live.obs_rms.update(np.concatenate([ds.obs for ds in tasks]))
    twin = live.clone_trainable()
    opt_l = context_optimizer(live)
    opt_t = context_optimizer(twin)
    run_context_updates(live, opt_l, tasks, schedule[:3], support_mode="fixed")
    run_context_updates(twin, opt_t, tasks, schedule[:3], support_mode="fixed")
    probe = live.clone_frozen()
    _pred, _p = probe.step(tasks[0].obs[:4], tasks[0].action[:4])
    assert torch.equal(probe.z, torch.zeros(probe.context_dim()))
    run_context_updates(live, opt_l, tasks, schedule[3:], support_mode="fixed")
    run_context_updates(twin, opt_t, tasks, schedule[3:], support_mode="fixed")
    for a, b in zip(live.parameters() if False else live.encoder.parameters(), twin.encoder.parameters()):
        assert torch.allclose(a, b)


def test_nonfinite_cells_and_audit_gate() -> None:
    report = completeness_report({"angvel_mae": float("nan"), "ok": 1.0})
    assert report["declared_complete"] is False
    assert any("angvel_mae" in item for item in report["failures"])
    assert completeness_report({"angvel_mae": 0.1})["declared_complete"] is True
    with pytest.raises(RuntimeError):
        assert_audit_allowed(None)
    with pytest.raises(RuntimeError):
        assert_audit_allowed({"selection_recorded": False})
    assert_audit_allowed({"selection_recorded": True, "chosen_updates": 300})


def test_checkpoint_choice_and_screen() -> None:
    assert choose_checkpoint({300: 0.2, 1000: 0.2, 3000: 0.3}) == 300
    assert choose_checkpoint({300: 0.5, 1000: 0.2, 3000: 0.2}) == 1000
    good = [{"angvel_real": 0.8, "angvel_zero": 1.0, "angvel_wrong": 1.0, "mae_real": 1.0, "mae_zero": 1.0, "h16_real": 1.0, "h16_zero": 1.0} for _ in range(3)]
    assert optimization_screen(good)["pass"] is True
    weak = [{"angvel_real": 0.99, "angvel_zero": 1.0, "angvel_wrong": 1.0, "mae_real": 1.0, "mae_zero": 1.0, "h16_real": 1.0, "h16_zero": 1.0} for _ in range(3)]
    assert optimization_screen(weak)["pass"] is False
    a = _toy(20, 1, "a")
    b = _toy(20, 2, "b")
    assert_disjoint_seeds(a, b)
    b.seed[:] = a.seed[0]
    with pytest.raises(ValueError):
        assert_disjoint_seeds(a, b)
