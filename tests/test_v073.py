from __future__ import annotations

import json

import numpy as np

from nexus.cl.serialize import dumps_strict
from nexus.world.experiment import v07_transfer_task
from nexus.world.freeze import FROZEN_CANDIDATES, FROZEN_PRIMARY_HORIZON, confirmation_physics_tuples, v073_confirmation_targets
from nexus.world.planning import RandomShootingMPC
from nexus.world.protocol import CONFIRM_EVAL_SEED_V073, CONTROL_EVAL_SEED
from nexus.world.v072 import PLAN_BUDGET, _n_cand


class _M:
    def step(self, obs, action):  # type: ignore[no-untyped-def]
        o = np.asarray(obs, dtype=np.float32)
        o = o.reshape(1, -1) if o.ndim == 1 else o
        return o, np.zeros(o.shape[0])


def test_frozen_recipe_matches_v072() -> None:
    assert FROZEN_PRIMARY_HORIZON == 3
    assert FROZEN_CANDIDATES[3] == _n_cand(3, PLAN_BUDGET)
    assert FROZEN_CANDIDATES[1] == 48
    assert FROZEN_CANDIDATES[6] == 8


def test_confirmation_physics_and_eval_seed_are_new() -> None:
    assert CONFIRM_EVAL_SEED_V073 != CONTROL_EVAL_SEED
    phys = confirmation_physics_tuples()
    tr = v07_transfer_task().params
    assert (tr["gravity"], tr["length"], tr["masspole"]) not in phys
    assert (9.8, 0.5, 0.1) not in phys
    ids = {t.task_id for t in v073_confirmation_targets()}
    assert ids == {"cartpole_v073_0", "cartpole_v073_1", "cartpole_v073_2"}


def test_episode_rng_reproduces_actions() -> None:
    obs = np.zeros(4, dtype=np.float32)
    seqs = []
    for _ in range(2):
        mpc = RandomShootingMPC(_M(), n_actions=2, horizon=3, n_candidates=16, seed=0, objective="both")
        acts = []
        mpc.reset_episode(CONFIRM_EVAL_SEED_V073)
        for _k in range(4):
            a, meta = mpc.act(obs)
            assert meta["used_simulator"] is False
            acts.append(a)
        seqs.append(acts)
    assert seqs[0] == seqs[1]


def test_v073_smoke(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from nexus.world import freeze as fz
    from nexus.world import v073

    old = (fz.FROZEN_N_TRAIN, fz.FROZEN_N_VAL, fz.FROZEN_EPOCHS)
    fz.FROZEN_N_TRAIN, fz.FROZEN_N_VAL, fz.FROZEN_EPOCHS = 64, 32, 1
    v073.FROZEN_N_TRAIN, v073.FROZEN_N_VAL, v073.FROZEN_EPOCHS = 64, 32, 1
    try:
        out = v073.run_v073_benchmark(
            n_model_seeds=1,
            eval_seeds=1,
            eval_episodes=1,
            artifact_path=tmp_path / "v073.json",
            checkpoint_dir=tmp_path / "ck",
        )
    finally:
        fz.FROZEN_N_TRAIN, fz.FROZEN_N_VAL, fz.FROZEN_EPOCHS = old
        v073.FROZEN_N_TRAIN, v073.FROZEN_N_VAL, v073.FROZEN_EPOCHS = old
    dumps_strict(out)
    json.loads((tmp_path / "v073.json").read_text())
    assert out["protocol"]["retuned_on_confirmation"] is False
    assert out["protocol"]["planner_uses_simulator"] is False
    assert out["protocol"]["v08_not_implemented"] is True
    assert "h3" in out["confirmation_mean"]
