from __future__ import annotations

import numpy as np

from nexus.tasks.cartpole_family import source_policy_task
from nexus.tasks.pendulum_family import pendulum_default, tensors_compatible
from nexus.tasks.spec import make_task_env
from nexus.world.baselines import heuristic_pendulum_pd, run_episodes
from nexus.world.cross_env import N_CAND, architecture_compatibility, run_cross_environment_benchmark
from nexus.world.data import collect_transitions
from nexus.world.freeze import FROZEN_HIDDEN, FROZEN_KIND, FROZEN_PRIMARY_HORIZON
from nexus.world.planning import RandomShootingMPC
from nexus.world.rewards import pendulum_step_reward
from nexus.world.verify import V085_MAE_RATIO


def test_recipe_frozen() -> None:
    assert FROZEN_KIND == "residual"
    assert FROZEN_HIDDEN == (64, 64)
    assert FROZEN_PRIMARY_HORIZON == 3
    assert N_CAND == 16
    assert V085_MAE_RATIO == 0.97


def test_tensors_incompatible_with_cartpole() -> None:
    a, b = source_policy_task(), pendulum_default()
    assert not tensors_compatible(a, b)
    c = architecture_compatibility(a, b)
    assert c["tensors_compatible"] is False
    assert c["weight_transfer_attempted"] is False


def test_discrete_torque_env() -> None:
    spec = pendulum_default()
    env = make_task_env(spec, seed=0)
    assert spec.obs_dim == 3
    assert spec.n_actions == 3
    assert int(env.action_space.n) == 3
    obs, _ = env.reset(seed=0)
    assert np.asarray(obs).reshape(-1).size == 3
    nxt, rew, term, trunc, _ = env.step(1)
    assert np.isfinite(rew)
    env.close()


def test_pendulum_reward_matches_env_zero_torque() -> None:
    spec = pendulum_default()
    env = make_task_env(spec, seed=1)
    o, _ = env.reset(seed=1)
    nxt, rew, _, _, _ = env.step(1)
    pred = float(pendulum_step_reward(o, 1, nxt)[0])
    assert abs(pred - float(rew)) < 1e-5
    env.close()


def test_mpc_uses_task_reward_not_cartpole_unit() -> None:
    spec = pendulum_default()
    from nexus.world.dynamics import WorldModel

    wm = WorldModel.create(3, 3, kind="residual", seed=0)
    p = RandomShootingMPC(wm, n_actions=3, horizon=3, n_candidates=16, seed=0, objective="predicted_reward", step_reward=pendulum_step_reward)
    a, meta = p.act(np.zeros(3, dtype=np.float32))
    assert a in (0, 1, 2)
    assert "best_score" in meta


def test_collect_not_cartpole_exploratory() -> None:
    spec = pendulum_default()
    ds = collect_transitions(spec, n_transitions=24, env_seeds=(2, 3), base_seed=0, mix=("random", "exploratory"))
    assert ds.obs.shape[1] == 3
    assert set(np.unique(ds.action)).issubset({0, 1, 2})


def test_heuristic_returns_finite() -> None:
    spec = pendulum_default()
    row = run_episodes(spec, act_fn=heuristic_pendulum_pd, episodes=1, seed=0, max_steps=50)
    assert np.isfinite(row["mean_return"])


def test_quick_benchmark() -> None:
    out = run_cross_environment_benchmark(n_model_seeds=1, artifact_path=None, checkpoint_dir="checkpoints/cross_env_test", quick=True)
    assert out["protocol"]["horizon"] == 3
    assert out["protocol"]["n_candidates"] == 16
    assert out["protocol"]["retuned_architecture"] is False
    assert out["protocol"]["claims_weight_transfer"] is False
    assert out["protocol"]["is_agi"] is False
    assert "mpc_minus_random" in out["paired"]
