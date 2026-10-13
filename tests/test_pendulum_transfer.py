from __future__ import annotations

from pathlib import Path

from nexus.tasks.pendulum_family import (
    PENDULUM_PLAN_CANDIDATES,
    PENDULUM_PLAN_HORIZON,
    pendulum_confirmation_targets,
    pendulum_physics_key,
    pendulum_source,
    pendulum_transfer_confirmation,
    pendulum_transfer_development,
    pendulum_transfer_sequence,
)
from nexus.world.belief import BeliefStepModel
from nexus.world.data import collect_transitions
from nexus.world.dynamics import WorldModel
from nexus.world.freeze import FROZEN_HIDDEN, FROZEN_KIND, FROZEN_PRIMARY_HORIZON
from nexus.world.planning import mpc_for_model
from nexus.world.protocol import V089G_CONFIRM_EVAL_SEED, V089P_CONFIRM_EVAL_SEED, V089X_EVAL_SEED
from nexus.world.pendulum_transfer import (
    BUDGETS,
    CROSS_ENV_HASH,
    GENERALITY_HASH,
    METHODS,
    run_pendulum_transfer,
    validate_prior_artifacts,
)
from nexus.world.session import PersistentSession
from nexus.world.verify import V085_MAE_RATIO


def test_planner_and_gate_frozen() -> None:
    assert FROZEN_PRIMARY_HORIZON == 3
    assert PENDULUM_PLAN_HORIZON == 16
    assert PENDULUM_PLAN_CANDIDATES == 16
    assert V085_MAE_RATIO == 0.97
    assert list(BUDGETS) == [0, 64, 128, 256, 512, 1024]
    cp = WorldModel.create(4, 2, kind="residual", seed=0)
    pn = WorldModel.create(3, 3, kind="residual", seed=0)
    pc = mpc_for_model(BeliefStepModel(cp))
    pp = mpc_for_model(BeliefStepModel(pn))
    assert pc.horizon == 3 and pc.n_actions == 2
    assert pp.horizon == 16 and pp.n_actions == 3 and pp.objective == "predicted_reward"


def test_physics_disjoint_from_horizon_diagnostic() -> None:
    prior = {pendulum_physics_key(t) for t in pendulum_confirmation_targets()}
    prior.add(pendulum_physics_key(pendulum_source()))
    suite = (pendulum_transfer_development(),) + pendulum_transfer_confirmation() + pendulum_transfer_sequence()
    seen: set[tuple[float, float, float]] = set()
    for spec in suite:
        key = pendulum_physics_key(spec)
        assert key not in prior, spec.task_id
        assert key not in seen, spec.task_id
        seen.add(key)
    assert V089P_CONFIRM_EVAL_SEED not in (V089X_EVAL_SEED, V089G_CONFIRM_EVAL_SEED)


def test_prior_artifacts_preserved() -> None:
    v = validate_prior_artifacts()
    assert v["cross_env_ok"] and v["generality_ok"]
    assert Path("artifacts/cross_environment.json").exists()
    assert Path("artifacts/planning_generality.json").exists()
    assert v["cross_env_hash"] == CROSS_ENV_HASH
    assert v["generality_hash"] == GENERALITY_HASH


def test_pendulum_session_uses_h16() -> None:
    spec = pendulum_source()
    wm = WorldModel.create(3, 3, kind=FROZEN_KIND, hidden=FROZEN_HIDDEN, seed=1)
    sess = PersistentSession(spec, wm, env_seed=2, plan_seed=3)
    assert sess.planner.horizon == 16
    assert sess.planner.n_actions == 3
    ds = sess.collect(4)
    assert ds.obs.shape[-1] == 3
    sess.close()


def test_train_val_disjoint_source() -> None:
    spec = pendulum_source()
    tr = collect_transitions(spec, n_transitions=16, env_seeds=(1, 2), base_seed=0, mix=("random",))
    va = collect_transitions(spec, n_transitions=16, env_seeds=(8, 9), base_seed=1, mix=("random",))
    from nexus.world.data import assert_disjoint_seeds

    assert_disjoint_seeds(tr, va)


def test_quick_pendulum_transfer() -> None:
    out = run_pendulum_transfer(
        n_model_seeds=1, artifact_path=None, checkpoint_dir="checkpoints/pt_test", quick=True,
    )
    assert out["audit"]["cross_env_ok"]
    assert out["protocol"]["mae_ratio"] == 0.97
    assert out["protocol"]["pendulum_horizon"] == 16
    assert out["protocol"]["is_agi"] is False
    assert out["decision"]["learning_to_learn_success"] in (True, False)
    assert set(METHODS) <= set(out["confirmation"]["mean_return"])
