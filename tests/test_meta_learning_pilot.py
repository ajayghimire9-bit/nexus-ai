from __future__ import annotations

from pathlib import Path

from nexus.tasks.pendulum_family import (
    pendulum_meta_confirm,
    pendulum_meta_train,
    pendulum_meta_val,
    pendulum_physics_key,
)
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_PRIMARY_HORIZON
from nexus.world.meta_learning import (
    ARCHS,
    BUDGETS,
    CROSS_ENV_HASH,
    GENERALITY_HASH,
    TRANSFER_HASH,
    assert_physics_disjoint,
    run_meta_learning_pilot,
    validate_prior_artifacts,
)
from nexus.world.planning import PENDULUM_PLAN_HORIZON, mpc_for_model
from nexus.world.belief import BeliefStepModel
from nexus.world.protocol import V089M_CONFIRM_EVAL_SEED, V089P_CONFIRM_EVAL_SEED
from nexus.world.verify import V085_MAE_RATIO


def test_inner_learner_and_planner_frozen() -> None:
    assert FROZEN_PRIMARY_HORIZON == 3
    assert PENDULUM_PLAN_HORIZON == 16
    assert V085_MAE_RATIO == 0.97
    assert BUDGETS[0] == 0 and BUDGETS[-1] == 1024 and 32 in BUDGETS
    wm = WorldModel.create(3, 3, kind="residual", seed=0, arch="mlp")
    p = mpc_for_model(BeliefStepModel(wm))
    assert p.horizon == 16 and p.n_actions == 3


def test_physics_and_eval_seed_not_leaked() -> None:
    assert_physics_disjoint()
    keys = {pendulum_physics_key(s) for s in (*pendulum_meta_train(), *pendulum_meta_val(), *pendulum_meta_confirm())}
    assert len(keys) == 4 + 2 + 4
    splits = {s.train_split for s in pendulum_meta_train()} | {s.train_split for s in pendulum_meta_val()} | {
        s.train_split for s in pendulum_meta_confirm()
    }
    assert "meta_train" in splits and "meta_val" in splits and "meta_confirm" in splits
    assert V089M_CONFIRM_EVAL_SEED != V089P_CONFIRM_EVAL_SEED


def test_film_has_no_physics_vector() -> None:
    film = WorldModel.create(3, 3, kind="residual", seed=1, arch="film")
    names = set(film.net.state_dict())
    assert not any("gravity" in k or "mass" in k or "length" in k for k in names)
    import numpy as np

    o = np.zeros((4, 3), dtype=np.float32)
    film.net.set_context_from_obs_action(film.normalize(o), np.zeros(4, dtype=int))
    mlp = WorldModel.create(3, 3, kind="residual", seed=1, arch="mlp")
    gru = WorldModel.create(3, 3, kind="residual", seed=1, arch="gru")
    cloned = film.clone()
    assert cloned.net.arch == "film"
    assert gru.net.arch == "gru" and mlp.net.n_parameters() > 0
    assert set(ARCHS) == {"mlp", "film", "gru"}


def test_prior_artifacts_intact() -> None:
    v = validate_prior_artifacts()
    assert v["cross_env_ok"] and v["generality_ok"] and v["transfer_ok"]
    assert Path("artifacts/pendulum_transfer.json").exists()
    assert v["cross_env_ok"]
    assert CROSS_ENV_HASH and GENERALITY_HASH and TRANSFER_HASH


def test_quick_meta_pilot() -> None:
    out = run_meta_learning_pilot(
        n_model_seeds=1, n_arch_seeds=1, artifact_path=None, checkpoint_dir="checkpoints/meta_test", quick=True,
    )
    assert out["audit"]["transfer_ok"]
    assert out["protocol"]["film_uses_privileged_physics"] is False
    assert out["protocol"]["is_agi"] is False
    assert "reptile" in out["confirmation"]["auc"]
    assert out["decision"]["meta_learning_success"] in (True, False)
    assert out["protocol"]["selected_arch"] in ARCHS
