from __future__ import annotations

import random

import numpy as np
import pytest

from nexus.config import load_config
from nexus.meta.controller import LinUCBController, make_controller
from nexus.meta.loop import run_research_loop
from nexus.meta.reward import research_reward, task_normalized_score
from nexus.meta.schema import ExperimentAction


def test_schema_rejects_executable_fields() -> None:
    payload = {
        "kind": "mutate_architecture",
        "env_id": "CartPole-v1",
        "architecture": {"hidden_sizes": [32], "activation": "tanh", "code": "print(1)"},
        "learning_rate": 3e-4,
        "train_timesteps": 128,
        "train_seeds": (1,),
        "holdout_eval_seed": 9,
        "assessment_eval_seed": 10,
    }
    with pytest.raises(ValueError, match="executable"):
        ExperimentAction(**payload)  # type: ignore[arg-type]


def test_schema_rejects_unknown_env() -> None:
    with pytest.raises(ValueError, match="unsupported env"):
        ExperimentAction(
            kind="mutate_architecture",
            env_id="NotAnEnv-v0",
            architecture={"hidden_sizes": [8], "activation": "tanh"},
            learning_rate=3e-4,
            train_timesteps=64,
            train_seeds=(0,),
            holdout_eval_seed=1,
            assessment_eval_seed=2,
        )


def test_reward_does_not_rank_raw_cross_env() -> None:
    cart = task_normalized_score("CartPole-v1", 500.0, 22.0)
    acro = task_normalized_score("Acrobot-v1", -80.0, -500.0)
    assert cart > 0.8
    assert acro > 0.7
    raw_would_prefer_cartpole = 500.0 > -80.0
    assert raw_would_prefer_cartpole
    # Normalized scores are both "good relative to random" rather than 500 vs -80.


def test_linucb_updates_from_outcomes() -> None:
    ctrl = LinUCBController(alpha=0.5)
    x = np.ones(8)
    a0 = ctrl.A[0].copy()
    ctrl.update(x, "mutate_architecture", reward=1.0)
    assert not np.allclose(ctrl.A[0], a0)
    assert ctrl.b[0].sum() != 0.0
    assert ctrl.is_meta_rl is False
    loaded = make_controller("linucb")
    loaded.load_state_dict(ctrl.state_dict())
    assert np.allclose(loaded.A[0], ctrl.A[0])


def test_research_loop_respects_budget(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = load_config("configs/smoke.yaml")
    cfg.meta.db_path = str(tmp_path / "m.sqlite")
    cfg.meta.state_path = str(tmp_path / "state.json")
    cfg.meta.champion_dir = str(tmp_path / "champs")
    cfg.meta.max_experiments = 2
    cfg.meta.max_timesteps = 512
    cfg.meta.train_timesteps = 256
    cfg.meta.n_train_seeds = 1
    cfg.meta.eval_episodes = 2
    cfg.meta.controller = "random"
    cfg.meta.seed = 1
    cfg.ppo.num_envs = 2
    cfg.ppo.num_steps = 64
    cfg.ppo.num_minibatches = 2
    result = run_research_loop(cfg, resume=False)
    assert result["n_experiments"] <= 2
    assert result["remaining_timesteps"] >= 0
    assert result["is_meta_rl"] is False
    assert (tmp_path / "state.json").exists()


def test_research_reward_penalizes_failure() -> None:
    ok = research_reward(
        env_id="CartPole-v1",
        mean_return=100.0,
        stderr=5.0,
        random_baseline=22.0,
        best_score_same_env=0.0,
        n_params=1000,
        wall_clock_s=0.2,
        timesteps=256,
        failed=False,
    )
    bad = research_reward(
        env_id="CartPole-v1",
        mean_return=100.0,
        stderr=5.0,
        random_baseline=22.0,
        best_score_same_env=0.0,
        n_params=1000,
        wall_clock_s=0.2,
        timesteps=256,
        failed=True,
    )
    assert bad["reward"] == -1.0
    assert ok["reward"] > bad["reward"]
    rng = random.Random(0)
    assert rng is not None
