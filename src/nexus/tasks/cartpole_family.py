from __future__ import annotations

from nexus.tasks.spec import TaskSpec

# All members wrap CartPole-v1: obs_dim=4, n_actions=2. Physics knobs change
# the *same* state representation. This is not Acrobot and is not cross-family.


def _cartpole(task_id: str, **params: float) -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        family="cartpole",
        gym_id="CartPole-v1",
        obs_dim=4,
        n_actions=2,
        params=params,
        reward_scale=1.0 / 500.0,
        notes="Compatible CartPole variant; independent eval uses a reserved seed.",
    )


CARTPOLE_FAMILY: dict[str, TaskSpec] = {
    "cartpole_default": _cartpole("cartpole_default", gravity=9.8, length=0.5, masspole=0.1),
    "cartpole_long": _cartpole("cartpole_long", gravity=9.8, length=0.8, masspole=0.1),
    "cartpole_heavy": _cartpole("cartpole_heavy", gravity=9.8, length=0.5, masspole=0.3),
    "cartpole_lowg": _cartpole("cartpole_lowg", gravity=4.9, length=0.5, masspole=0.1),
}


def source_tasks() -> tuple[TaskSpec, TaskSpec, TaskSpec]:
    return (
        CARTPOLE_FAMILY["cartpole_default"],
        CARTPOLE_FAMILY["cartpole_long"],
        CARTPOLE_FAMILY["cartpole_heavy"],
    )


def heldout_task() -> TaskSpec:
    return CARTPOLE_FAMILY["cartpole_lowg"]
