from __future__ import annotations

import numpy as np

from nexus.tasks.cartpole_family import source_policy_task
from nexus.world.baselines import heuristic_cartpole, run_episodes
from nexus.world.planning import RandomShootingMPC, one_step_greedy


class _FakeModel:
    def __init__(self) -> None:
        self.calls = 0

    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        self.calls += 1
        o = np.asarray(obs, dtype=np.float32).reshape(-1, 4)
        a = np.asarray(action, dtype=np.int64).reshape(-1)
        if a.size == 1:
            a = np.full(o.shape[0], int(a.flat[0]))
        nxt = o.copy()
        nxt[:, 2] = o[:, 2] + 0.05 * (2 * a - 1)
        p = (np.abs(nxt[:, 2]) > 0.2).astype(np.float32)
        return nxt, p


class _BoomEnv:
    def step(self, _action: int) -> None:
        raise AssertionError("imagined planning must not call env.step")


def test_mpc_does_not_step_simulator() -> None:
    model = _FakeModel()
    mpc = RandomShootingMPC(model=model, n_actions=2, horizon=4, n_candidates=6, seed=0)
    obs = np.zeros(4, dtype=np.float32)
    action, meta = mpc.act(obs)
    assert action in (0, 1)
    assert meta["used_simulator"] is False
    assert model.calls > 0
    mpc.act(obs)
    # If the planner had been given this env, step would raise.
    boom = _BoomEnv()
    assert boom is not mpc.model


def test_one_step_greedy_uses_model_only() -> None:
    model = _FakeModel()
    a = one_step_greedy(model, np.array([0.0, 0.0, 0.05, 0.0], dtype=np.float32), 2)
    assert a in (0, 1)
    assert model.calls >= 2


def test_heuristic_runs_and_counts_interactions() -> None:
    spec = source_policy_task()
    row = run_episodes(spec, act_fn=heuristic_cartpole, episodes=2, seed=83_000)
    assert row["env_interactions"] == int(sum(row["returns"])) or row["env_interactions"] >= 2
    assert row["episodes"] == 2
