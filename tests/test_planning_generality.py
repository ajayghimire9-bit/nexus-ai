from __future__ import annotations

from pathlib import Path

import numpy as np

from nexus.tasks.pendulum_family import pendulum_confirmation_targets, pendulum_default, pendulum_development
from nexus.tasks.spec import make_task_env
from nexus.world.cross_env import N_CAND
from nexus.world.data import collect_transitions
from nexus.world.freeze import FROZEN_PRIMARY_HORIZON
from nexus.world.generality import (
    CROSS_ENV_HASH,
    FIXED_CANDIDATES,
    HORIZONS,
    PrivilegedPendulumDynamics,
    n_cand_for,
    run_planning_generality,
    validate_cross_env_preserved,
)
from nexus.world.rewards import pendulum_step_reward
from nexus.world.verify import V085_MAE_RATIO


def test_prior_cross_env_artifact_not_retuned() -> None:
    assert FROZEN_PRIMARY_HORIZON == 3
    assert N_CAND == 16
    assert V085_MAE_RATIO == 0.97
    v = validate_cross_env_preserved()
    assert v["ok"], v
    assert Path("artifacts/cross_environment.json").exists()
    assert v["protocol_hash"] == CROSS_ENV_HASH


def test_horizons_and_budgets() -> None:
    assert HORIZONS == (3, 8, 16, 32)
    assert n_cand_for(3, mode="fixed_candidates") == FIXED_CANDIDATES == 16
    assert n_cand_for(3, mode="fixed_imagine_budget") == 16
    assert n_cand_for(32, mode="fixed_imagine_budget") == 2
    assert n_cand_for(8, mode="fixed_imagine_budget") == 6


def test_confirm_physics_unused_in_h3_default() -> None:
    default_g = 10.0
    for spec in pendulum_confirmation_targets():
        assert float(spec.params["g"]) != default_g
        assert spec.task_id != pendulum_default().task_id
        assert spec.task_id != pendulum_development().task_id


def test_reward_and_disjoint_collect() -> None:
    spec = pendulum_development()
    env = make_task_env(spec, seed=2)
    o, _ = env.reset(seed=2)
    nxt, rew, _, _, _ = env.step(0)
    assert abs(float(pendulum_step_reward(o, 0, nxt)[0]) - float(rew)) < 1e-5
    env.close()
    tr = collect_transitions(spec, n_transitions=16, env_seeds=(1, 2), base_seed=0, mix=("random",))
    va = collect_transitions(spec, n_transitions=16, env_seeds=(8, 9), base_seed=1, mix=("random",))
    from nexus.world.data import assert_disjoint_seeds

    assert_disjoint_seeds(tr, va)


def test_oracle_is_labeled_simulator() -> None:
    spec = pendulum_development()
    dyn = PrivilegedPendulumDynamics(spec)
    assert dyn.uses_simulator is True
    o = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    nxt, p = dyn.step(o, 1)
    assert nxt.shape[-1] == 3
    dyn.close()


def test_quick_generality_benchmark() -> None:
    out = run_planning_generality(
        n_model_seeds=1, n_dev_seeds=1, artifact_path=None, checkpoint_dir="checkpoints/pg_test", quick=True,
    )
    assert out["audit"]["cross_env_preserved"]["ok"]
    assert out["protocol"]["oracle_on_confirmation"] is False
    assert out["protocol"]["is_agi"] is False
    assert "selected" in out["protocol"]
    assert out["decision"]["proceed_to_meta_learning"] in (True, False)
