from __future__ import annotations

import pytest

from nexus.tasks.cartpole_family import (
    CARTPOLE_FAMILY,
    confirmation_targets,
    heldout_task,
    source_tasks,
    v064_development_targets,
)
from nexus.tasks.spec import CARTPOLE_PHYSICS_VERSION, TaskSpec, apply_params, make_task_env, sync_cartpole_derived


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


def test_derived_mass_and_length_are_synced() -> None:
    spec = CARTPOLE_FAMILY["cartpole_heavy"]
    env = make_task_env(spec, seed=0)
    try:
        inner = env.unwrapped
        assert abs(inner.masspole - 0.3) < 1e-9
        assert abs(inner.total_mass - (inner.masscart + inner.masspole)) < 1e-9
        assert abs(inner.polemass_length - inner.masspole * inner.length) < 1e-9
    finally:
        env.close()


def test_unsynced_env_differs_from_corrected_dynamics() -> None:
    spec = CARTPOLE_FAMILY["cartpole_longheavy"]
    good = make_task_env(spec, seed=1)
    stale = make_task_env(CARTPOLE_FAMILY["cartpole_default"], seed=1)
    try:
        inner = stale.unwrapped
        inner.masspole = 0.3
        inner.length = 0.8
        # Intentionally do not sync: legacy setattr-only bug.
        g = good.unwrapped
        s = stale.unwrapped
        assert abs(g.total_mass - s.total_mass) > 1e-9 or abs(g.polemass_length - s.polemass_length) > 1e-9
        state = (0.01, 0.02, 0.03, 0.04)
        g.state = state
        s.state = state
        ng = g.step(1)[0]
        ns = s.step(1)[0]
        assert not (abs(ng - ns).max() < 1e-9)
    finally:
        good.close()
        stale.close()


def test_corrected_env_matches_hand_synced_equivalent() -> None:
    spec = CARTPOLE_FAMILY["cartpole_highg"]
    a = make_task_env(spec, seed=7)
    b = make_task_env(CARTPOLE_FAMILY["cartpole_default"], seed=7)
    try:
        inner = b.unwrapped
        for k, v in spec.params.items():
            setattr(inner, k, v)
        sync_cartpole_derived(inner)
        a.unwrapped.state = (0.0, 0.0, 0.05, 0.0)
        b.unwrapped.state = (0.0, 0.0, 0.05, 0.0)
        oa = a.unwrapped.step(0)[0]
        ob = b.unwrapped.step(0)[0]
        assert abs(oa - ob).max() < 1e-9
        assert abs(a.unwrapped.total_mass - b.unwrapped.total_mass) < 1e-12
        assert abs(a.unwrapped.polemass_length - b.unwrapped.polemass_length) < 1e-12
    finally:
        a.close()
        b.close()


def test_physics_knobs_change_transitions() -> None:
    base = make_task_env(CARTPOLE_FAMILY["cartpole_default"], seed=0)
    hi = make_task_env(CARTPOLE_FAMILY["cartpole_highg"], seed=0)
    try:
        state = (0.0, 0.0, 0.08, 0.0)
        base.unwrapped.state = state
        hi.unwrapped.state = state
        assert abs(base.unwrapped.step(1)[0] - hi.unwrapped.step(1)[0]).max() > 1e-6
    finally:
        base.close()
        hi.close()


def test_reset_and_step_are_deterministic() -> None:
    spec = CARTPOLE_FAMILY["cartpole_short"]
    e1 = make_task_env(spec, seed=42)
    e2 = make_task_env(spec, seed=42)
    try:
        o1, _ = e1.reset(seed=42)
        o2, _ = e2.reset(seed=42)
        assert abs(o1 - o2).max() < 1e-9
        for a in (0, 1, 0, 1, 1):
            n1, r1, t1, u1, _ = e1.step(a)
            n2, r2, t2, u2, _ = e2.step(a)
            assert abs(n1 - n2).max() < 1e-9
            assert r1 == r2 and t1 == t2 and u1 == u2
    finally:
        e1.close()
        e2.close()


def test_v064_splits_keep_confirmation_unseen() -> None:
    dev = {t.task_id for t in v064_development_targets()}
    conf = {t.task_id for t in confirmation_targets()}
    assert conf.isdisjoint(dev)
    assert "cartpole_short" in dev
    assert CARTPOLE_PHYSICS_VERSION == "cartpole_derived_v1"
    for t in confirmation_targets():
        assert t.compatible_with(source_tasks()[0])
        env = make_task_env(t, seed=0)
        try:
            inner = env.unwrapped
            assert abs(inner.total_mass - inner.masscart - inner.masspole) < 1e-9
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
