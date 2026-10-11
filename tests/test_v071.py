from __future__ import annotations

import json
from typing import Any

import numpy as np
import pytest

from nexus.cl.serialize import dumps_strict
from nexus.world.planning import RandomShootingMPC
from nexus.world.select import select_winner
from nexus.world.train import one_step_errors


class _ConstModel:
    def __init__(self, p_term: float) -> None:
        self.p = p_term

    def step(self, obs: np.ndarray, action: int | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        o = np.asarray(obs, dtype=np.float32)
        o = o.reshape(1, -1) if o.ndim == 1 else o.reshape(-1, o.shape[-1])
        a = np.asarray(action).reshape(-1)
        n = o.shape[0] if a.size != o.shape[0] else o.shape[0]
        nxt = o.copy()
        nxt[:, 2] += 0.01
        return nxt, np.full(o.shape[0], self.p, dtype=np.float64)


def test_select_winner_rejects_test_argument() -> None:
    class _M:
        def step(self, obs: Any, action: Any) -> tuple[Any, Any]:
            raise AssertionError("should not score dummy")

    with pytest.raises(RuntimeError, match="test metrics"):
        select_winner({"a": _M()}, val=None, test=object())  # type: ignore[arg-type]


def test_select_uses_only_val(monkeypatch: pytest.MonkeyPatch) -> None:
    from nexus.world import select as sel
    from nexus.world.data import collect_transitions
    from nexus.tasks.cartpole_family import source_policy_task
    from nexus.world.linear import fit_ridge

    spec = source_policy_task()
    val = collect_transitions(spec, n_transitions=24, env_seeds=(0,), base_seed=1, policy="random")
    ridge = fit_ridge(val, n_actions=2)
    seen: list[int] = []

    def _err(model: Any, ds: Any) -> dict[str, float]:
        seen.append(id(ds))
        return {"mae": 0.1}

    monkeypatch.setattr(sel, "one_step_errors", _err)
    kind, scores = select_winner({"ridge": ridge}, val)
    assert kind == "ridge"
    assert seen == [id(val)]


def test_absorbing_termination_stops_future_reward() -> None:
    dead = _ConstModel(1.0)
    live = _ConstModel(0.0)
    seqs = np.zeros((1, 5), dtype=np.int64)
    obs = np.zeros(4, dtype=np.float32)
    s_dead = RandomShootingMPC(dead, n_actions=2, horizon=5, n_candidates=1, seed=0)._score_batch(obs, seqs)
    s_live = RandomShootingMPC(live, n_actions=2, horizon=5, n_candidates=1, seed=0)._score_batch(obs, seqs)
    assert float(s_dead[0]) == pytest.approx(1.0)
    assert float(s_live[0]) == pytest.approx(5.0)


def test_mpc_seeded_action_is_deterministic() -> None:
    m = _ConstModel(0.1)
    obs = np.array([0.01, 0.0, 0.02, 0.0], dtype=np.float32)
    mpc = RandomShootingMPC(m, n_actions=2, horizon=3, n_candidates=8, seed=4)
    mpc.reset_episode(4)
    a1, _ = mpc.act(obs)
    mpc.reset_episode(4)
    a2, _ = mpc.act(obs)
    assert a1 == a2


def test_time_budget_enforced() -> None:
    m = _ConstModel(0.0)
    mpc = RandomShootingMPC(m, n_actions=2, horizon=4, n_candidates=32, seed=0, max_plan_ms=-1.0, enforce_time_budget=True, chunk_size=4)
    _, meta = mpc.act(np.zeros(4, dtype=np.float32))
    assert meta["n_scored"] == 4
    assert meta["time_budget_enforced"] is True


def test_v071_smoke_no_test_selection(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    from nexus.world import v071
    from nexus.world.train import one_step_errors as real_err

    phase = {"n": 0}

    def _wrap(model: Any, ds: Any) -> Any:
        # After selection, test eval is allowed. During select_winner only val is passed.
        return real_err(model, ds)

    monkeypatch.setattr(v071, "one_step_errors", _wrap)
    out = v071.run_v071_benchmark(
        n_model_seeds=2,
        n_train=64,
        n_val=32,
        n_test=32,
        epochs=1,
        mpc_candidates=4,
        mpc_horizon=2,
        paired_eval_seeds=2,
        eval_episodes=1,
        ensemble_members=2,
        ensemble_epochs=1,
        transfer_n=32,
        ppo_short_seeds=1,
        ppo_strong_seeds=1,
        ppo_strong_steps=256,
        dagger_episodes=1,
        artifact_path=tmp_path / "v071.json",
        checkpoint_dir=tmp_path / "ck",
    )
    dumps_strict(out)
    json.loads((tmp_path / "v071.json").read_text())
    assert out["protocol"]["selection"].startswith("validation")
    assert out["protocol"]["planner_uses_simulator"] is False
    assert out["is_agi"] is False
    assert len(out["per_seed"]) == 2
    assert "mpc_minus_greedy" in out["paired_control"]
