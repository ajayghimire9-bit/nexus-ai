from __future__ import annotations

import json

import numpy as np
import pytest

from nexus.cl.serialize import dumps_strict
from nexus.tasks.cartpole_family import source_policy_task
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, make_task_env, sync_cartpole_derived
from nexus.world.data import assert_disjoint_seeds, collect_transitions
from nexus.world.dynamics import WorldModel
from nexus.world.imagine import imagine_actions, multi_step_errors
from nexus.world.protocol import COLLECT_TEST_SEED, COLLECT_TRAIN_SEED, COLLECT_VAL_SEED
from nexus.world.train import one_step_errors, train_world_model


def test_corrected_physics_sync() -> None:
    spec = source_policy_task()
    env = make_task_env(spec, seed=0)
    inner = env.unwrapped
    inner.masspole = 0.3
    inner.length = 0.8
    sync_cartpole_derived(inner)
    assert inner.total_mass == pytest.approx(inner.masscart + inner.masspole)
    assert inner.polemass_length == pytest.approx(inner.masspole * inner.length)
    env.close()
    assert CARTPOLE_PHYSICS_VERSION == "cartpole_derived_v1"


def test_collect_and_disjoint_splits() -> None:
    spec = source_policy_task()
    tr = collect_transitions(spec, n_transitions=40, env_seeds=(0, 1), base_seed=COLLECT_TRAIN_SEED, mix=("random", "exploratory"))
    va = collect_transitions(spec, n_transitions=20, env_seeds=(100, 101), base_seed=COLLECT_VAL_SEED, policy="random")
    te = collect_transitions(spec, n_transitions=20, env_seeds=(200, 201), base_seed=COLLECT_TEST_SEED, policy="exploratory")
    assert len(tr) == 40 == tr.env_interactions
    assert_disjoint_seeds(tr, va, te)
    assert tr.obs.shape == (40, 4)
    assert set(np.unique(tr.action)).issubset({0, 1})


def test_deterministic_simulation() -> None:
    spec = source_policy_task()
    a = make_task_env(spec, seed=3)
    b = make_task_env(spec, seed=3)
    o1, _ = a.reset(seed=3)
    o2, _ = b.reset(seed=3)
    assert np.allclose(o1, o2)
    for act in (0, 1, 1, 0, 0):
        n1, r1, t1, u1, _ = a.step(act)
        n2, r2, t2, u2, _ = b.step(act)
        assert np.allclose(n1, n2)
        assert r1 == r2 and t1 == t2 and u1 == u2
    a.close()
    b.close()


def test_dynamics_shapes_and_checkpoint(tmp_path) -> None:  # type: ignore[no-untyped-def]
    spec = source_policy_task()
    tr = collect_transitions(spec, n_transitions=96, env_seeds=(0, 1, 2), base_seed=1, mix=("random", "exploratory"))
    va = collect_transitions(spec, n_transitions=32, env_seeds=(50, 51), base_seed=2, policy="random")
    wm, _ = train_world_model(tr, va, kind="residual", epochs=2, batch_size=32, seed=0)
    pred, p = wm.step(tr.obs[:8], tr.action[:8])
    assert pred.shape == (8, 4)
    assert p.shape == (8,)
    err = one_step_errors(wm, va)
    assert len(err["mae_per_dim"]) == 4
    path = tmp_path / "wm.pt"
    wm.save(path)
    loaded = WorldModel.load(path)
    err2 = one_step_errors(loaded, va)
    assert abs(err["mae"] - err2["mae"]) < 1e-5


def test_multi_step_prediction_length() -> None:
    spec = source_policy_task()
    tr = collect_transitions(spec, n_transitions=128, env_seeds=(0, 1), base_seed=4, policy="random")
    va = collect_transitions(spec, n_transitions=64, env_seeds=(80, 81), base_seed=5, policy="random")
    wm, _ = train_world_model(tr, va, kind="residual", epochs=3, seed=1)
    out = imagine_actions(wm, va.obs[0], va.action[:5])
    assert out["states"].shape == (5, 4)
    ms = multi_step_errors(wm, va, (1, 5))
    assert "1" in ms and "5" in ms


def test_v07_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from nexus.world.experiment import run_v07_benchmark

    out = run_v07_benchmark(
        n_train=128,
        n_val=64,
        n_test=64,
        epochs=2,
        mpc_candidates=8,
        mpc_horizon=3,
        control_seeds=2,
        eval_episodes=2,
        ensemble_members=2,
        ensemble_epochs=1,
        transfer_n=48,
        ppo_seeds=2,
        artifact_path=tmp_path / "v07.json",
        checkpoint_dir=tmp_path / "ck",
    )
    raw = (tmp_path / "v07.json").read_text()
    json.loads(raw)
    dumps_strict(out)
    assert out["protocol"]["planner_uses_simulator"] is False
    assert out["collection"]["disjoint_seeds"] is True
    assert out["collection"]["env_interactions"] == 128 + 64 + 64
    assert out["is_agi"] is False
    win = out["prediction"][out["prediction"]["winner"]]["one_step"]["mae"]
    persist = out["prediction"]["persistence"]["mae"]
    assert win == win and persist == persist
