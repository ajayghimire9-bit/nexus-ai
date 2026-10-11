from __future__ import annotations

import pytest

from nexus.tasks.cartpole_family import CARTPOLE_FAMILY, heldout_task, source_tasks
from nexus.tasks.spec import TaskSpec, make_task_env


def test_cartpole_family_is_compatible_and_not_acrobot() -> None:
    src = source_tasks()
    hold = heldout_task()
    assert all(src[0].compatible_with(t) for t in src)
    assert hold.compatible_with(src[0])
    assert src[0].obs_dim == 4
    assert src[0].n_actions == 2
    acrobot = TaskSpec(
        task_id="acrobot",
        family="acrobot",
        gym_id="Acrobot-v1",
        obs_dim=6,
        n_actions=3,
    )
    assert not src[0].compatible_with(acrobot)


def test_cartpole_params_apply() -> None:
    spec = CARTPOLE_FAMILY["cartpole_long"]
    env = make_task_env(spec, seed=0)
    try:
        assert abs(float(env.unwrapped.length) - 0.8) < 1e-6
        obs, _ = env.reset(seed=0)
        assert obs.shape[-1] == 4
        env.step(env.action_space.sample())
    finally:
        env.close()


def test_unknown_cartpole_param_rejected() -> None:
    bad = TaskSpec(
        task_id="bad",
        family="cartpole",
        gym_id="CartPole-v1",
        obs_dim=4,
        n_actions=2,
        params={"not_a_real_knob": 1.0},
    )
    with pytest.raises(AttributeError):
        make_task_env(bad)
