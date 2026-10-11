from __future__ import annotations

import random

import numpy as np
import pytest

from nexus.config import load_config
from nexus.meta.checkpoint import select_representative_checkpoint
from nexus.meta.controller import EpsilonGreedyController, LinUCBController, make_controller
from nexus.meta.loop import compare_controllers, run_research_loop
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


def _tiny_meta_cfg(tmp_path, *, seed: int = 0, n_seeds: int = 1, max_exp: int = 2, train_ts: int = 128):
    cfg = load_config("configs/smoke.yaml")
    cfg.meta.db_path = str(tmp_path / "m.sqlite")
    cfg.meta.state_path = str(tmp_path / "state.json")
    cfg.meta.champion_dir = str(tmp_path / "champs")
    cfg.meta.max_experiments = max_exp
    cfg.meta.max_timesteps = 10_000
    cfg.meta.train_timesteps = train_ts
    cfg.meta.n_train_seeds = n_seeds
    cfg.meta.eval_episodes = 2
    cfg.meta.holdout_eval_seed = 80_000
    cfg.meta.assessment_eval_seed = 81_000
    cfg.meta.independent_eval_seed = 92_000
    cfg.meta.seed = seed
    cfg.meta.controller = "epsilon_greedy"
    cfg.meta.epsilon = 0.0
    cfg.ppo.num_envs = 2
    cfg.ppo.num_steps = 64
    cfg.ppo.num_minibatches = 2
    return cfg


def test_env_steps_sum_all_training_seeds(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = _tiny_meta_cfg(tmp_path, n_seeds=2, max_exp=1, train_ts=128)
    result = run_research_loop(cfg, controller=EpsilonGreedyController(epsilon=0.0), resume=False)
    trained = [h for h in result["history"] if h.get("result") and h["result"].get("env_steps")]
    assert trained, result["history"]
    steps = int(trained[0]["result"]["env_steps"])
    assert steps == 128 * 2
    assert result["env_steps_consumed"] == steps
    assert result["remaining_timesteps"] == cfg.meta.max_timesteps - steps


def test_representative_checkpoint_is_not_last_seed() -> None:
    rows = [
        {"seed": 1, "mean_return": 100.0, "path": "a.pt"},
        {"seed": 2, "mean_return": 110.0, "path": "b.pt"},
        {"seed": 3, "mean_return": 400.0, "path": "last.pt"},
    ]
    chosen = select_representative_checkpoint(rows)
    assert chosen is not None
    assert chosen["path"] != "last.pt"
    assert chosen["seed"] == 2


def test_resume_matches_uninterrupted_history(tmp_path) -> None:  # type: ignore[no-untyped-def]
    full_dir = tmp_path / "full"
    part_dir = tmp_path / "part"
    full_dir.mkdir()
    part_dir.mkdir()
    cfg_full = _tiny_meta_cfg(full_dir, seed=3, max_exp=2, train_ts=128)
    cfg_part = _tiny_meta_cfg(part_dir, seed=3, max_exp=2, train_ts=128)
    ctrl = EpsilonGreedyController(epsilon=0.0)
    full = run_research_loop(cfg_full, controller=EpsilonGreedyController(epsilon=0.0), resume=False)
    run_research_loop(cfg_part, controller=ctrl, resume=False, stop_after=1)
    resumed = run_research_loop(cfg_part, controller=ctrl, resume=True)

    def _fps(payload: dict) -> list[str]:
        out = []
        for h in payload["history"]:
            if "proposal" in h:
                out.append(h["proposal"]["action"]["fingerprint"])
            elif "skipped_duplicate" in h:
                out.append(h["skipped_duplicate"])
        return out

    assert _fps(resumed) == _fps(full)
    assert resumed["env_steps_consumed"] == full["env_steps_consumed"]


def test_compare_controllers_is_paired(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = _tiny_meta_cfg(tmp_path, seed=0, max_exp=1, train_ts=128)
    out = compare_controllers(cfg, names=("random", "epsilon_greedy"), controller_seeds=(0,))
    paired = out["paired"][0]
    seeds = {tuple(paired["runs"][n]["train_seeds"]) for n in paired["runs"]}
    assert len(seeds) == 1
    assert paired["train_seeds"] == [1000]


def test_assessment_seed_not_used_as_controller_feedback(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = _tiny_meta_cfg(tmp_path, seed=4, max_exp=1, train_ts=128)
    result = run_research_loop(cfg, controller=EpsilonGreedyController(epsilon=0.0), resume=False)
    for h in result["history"]:
        rw = h.get("controller_reward")
        if not rw:
            assert h.get("controller_updated") is False
            continue
        assert rw["eval_seed"] == cfg.meta.holdout_eval_seed
        assert rw["eval_seed"] != cfg.meta.assessment_eval_seed
        assert rw["eval_seed"] != cfg.meta.independent_eval_seed
        if h.get("result", {}).get("independent_assessment"):
            assert h["result"]["independent_assessment"]["eval_seed"] == cfg.meta.assessment_eval_seed


def test_inflight_resume_does_not_double_count_or_exceed_budget(tmp_path) -> None:  # type: ignore[no-untyped-def]
    cfg = _tiny_meta_cfg(tmp_path, seed=5, max_exp=1, train_ts=256)
    ctrl = EpsilonGreedyController(epsilon=0.0)
    paused = run_research_loop(
        cfg, controller=ctrl, resume=False, interrupt_train_after_iters=1
    )
    assert paused["interrupted"] is True
    assert paused["n_experiments"] == 0
    assert paused["env_steps_consumed"] == 0
    assert paused["remaining_timesteps"] == cfg.meta.max_timesteps
    finished = run_research_loop(cfg, controller=ctrl, resume=True)
    assert finished["interrupted"] is False
    assert finished["n_experiments"] == 1
    assert finished["env_steps_consumed"] == 256
    assert finished["remaining_timesteps"] == cfg.meta.max_timesteps - 256
    assert finished["remaining_timesteps"] >= 0
    fps = [
        h["proposal"]["action"]["fingerprint"]
        for h in finished["history"]
        if "proposal" in h
    ]
    assert len(fps) == len(set(fps))
    ind = finished["independent_eval"]
    assert ind is not None
    assert ind["eval_seed"] == cfg.meta.independent_eval_seed


def test_frozen_linucb_does_not_update() -> None:
    frozen = make_controller("linucb_frozen")
    x = np.ones(8)
    a0 = frozen.A[0].copy()
    frozen.update(x, "mutate_architecture", 1.0)
    assert np.allclose(frozen.A[0], a0)
    live = make_controller("linucb")
    live.update(x, "mutate_architecture", 1.0)
    assert not np.allclose(live.A[0], a0)
