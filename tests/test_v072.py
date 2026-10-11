from __future__ import annotations

import json

import numpy as np
import pytest

from nexus.cl.serialize import dumps_strict
from nexus.world.planning import RandomShootingMPC
from nexus.world.terminate import TermOverride, geometric_terminate


class _ConstModel:
    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        o = np.asarray(obs, dtype=np.float32)
        o = o.reshape(1, -1) if o.ndim == 1 else o
        nxt = o.copy()
        nxt[:, 2] += 0.01
        return nxt, np.full(o.shape[0], 0.2)


def test_persistent_rng_changes_candidates_within_episode() -> None:
    m = _ConstModel()
    mpc = RandomShootingMPC(m, n_actions=2, horizon=4, n_candidates=8, seed=7)
    obs = np.zeros(4, dtype=np.float32)
    mpc.reset_episode(7)
    mpc.act(obs)
    s1 = mpc.last_seqs.copy()
    mpc.act(obs)
    s2 = mpc.last_seqs.copy()
    assert not np.array_equal(s1, s2)


def test_reset_episode_reproduces_first_candidates() -> None:
    m = _ConstModel()
    mpc = RandomShootingMPC(m, n_actions=2, horizon=4, n_candidates=8, seed=7)
    obs = np.zeros(4, dtype=np.float32)
    mpc.reset_episode(11)
    mpc.act(obs)
    s1 = mpc.last_seqs.copy()
    mpc.act(obs)
    mpc.reset_episode(11)
    mpc.act(obs)
    assert np.array_equal(mpc.last_seqs, s1)


def test_two_planners_same_seed_match_trajectory() -> None:
    m = _ConstModel()
    obs = np.array([0.01, 0.0, 0.02, 0.0], dtype=np.float32)
    acts = []
    for _ in range(2):
        mpc = RandomShootingMPC(m, n_actions=2, horizon=3, n_candidates=6, seed=3)
        seq = []
        mpc.reset_episode(3)
        for _k in range(5):
            a, _ = mpc.act(obs)
            seq.append(a)
        acts.append(seq)
    assert acts[0] == acts[1]


def test_geometric_terminate_on_predicted_state_not_env() -> None:
    ok = np.zeros(4, dtype=np.float32)
    bad = np.array([3.0, 0.0, 0.0, 0.0], dtype=np.float32)
    assert float(geometric_terminate(ok)[0]) == 0.0
    assert float(geometric_terminate(bad)[0]) == 1.0
    wrapped = TermOverride(_ConstModel(), "always_live")
    _, p = wrapped.step(ok, 0)
    assert float(p.reshape(-1)[0]) == 0.0


def test_v072_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from nexus.world.v072 import run_v072_benchmark

    out = run_v072_benchmark(
        n_model_seeds=1,
        n_train=64,
        n_val=32,
        n_test=32,
        epochs=1,
        paired_eval_seeds=1,
        eval_episodes=1,
        ensemble_members=2,
        ensemble_epochs=1,
        quick=True,
        artifact_path=tmp_path / "v072.json",
        checkpoint_dir=tmp_path / "ck",
    )
    dumps_strict(out)
    json.loads((tmp_path / "v072.json").read_text())
    assert out["protocol"]["persistent_rng"] is True
    assert out["protocol"]["planner_uses_simulator"] is False
    assert out["is_agi"] is False
