"""Frozen V0.7.2 residual+H=3 recipe. Do not retune on V0.7.3 confirmation."""

from __future__ import annotations

from nexus.tasks.spec import TaskSpec
from nexus.world.v072 import PLAN_BUDGET, _n_cand

FROZEN_KIND = "residual"
FROZEN_HIDDEN = (64, 64)
FROZEN_N_TRAIN = 1024
FROZEN_N_VAL = 256
FROZEN_EPOCHS = 20
FROZEN_OBJECTIVE = "both"
FROZEN_PLAN_BUDGET = PLAN_BUDGET
FROZEN_HORIZONS = (1, 3, 6)
FROZEN_PRIMARY_HORIZON = 3
FROZEN_CANDIDATES = {h: _n_cand(h, FROZEN_PLAN_BUDGET) for h in FROZEN_HORIZONS}

# Unused in V0.6.x confirmation offsets and V0.7.0 transfer (g=11, L=0.45, m=0.15).
_V073_CONFIRM_OFFSETS = (
    {"gravity": -2.3, "length": -0.08, "masspole": 0.03},
    {"gravity": 0.7, "length": 0.08, "masspole": -0.01},
    {"gravity": 3.2, "length": -0.15, "masspole": 0.08},
)
_BASE = {"gravity": 9.8, "length": 0.5, "masspole": 0.1}


def v073_confirmation_targets() -> tuple[TaskSpec, ...]:
    out = []
    for i, off in enumerate(_V073_CONFIRM_OFFSETS):
        params = {k: float(_BASE[k]) + float(off[k]) for k in _BASE}
        out.append(
            TaskSpec(
                task_id=f"cartpole_v073_{i}",
                family="cartpole",
                gym_id="CartPole-v1",
                obs_dim=4,
                n_actions=2,
                params=params,
                train_split="confirm_v073",
                notes="V0.7 final confirmation physics. Not used to select H=3.",
            )
        )
    return tuple(out)


def confirmation_physics_tuples() -> set[tuple[float, float, float]]:
    return {(float(t.params["gravity"]), float(t.params["length"]), float(t.params["masspole"])) for t in v073_confirmation_targets()}
