"""MountainCarContinuous lookahead protocol locks. Collection remains unauthorized."""
from __future__ import annotations
from dataclasses import replace
import gymnasium as gym
import numpy as np
import pytest
from nexus.tasks.mountaincar_continuous_family import mcc_default, mcc_lookahead_development, mcc_physics_key
from nexus.tasks.mountaincar_family import mountaincar_default
from nexus.tasks.spec import make_task_env
from nexus.world import mountaincar_continuous_lookahead as m
from nexus.world.planning_value import sha
from nexus.world.rewards import mountaincar_height


def test_holdout_is_unused_and_not_discrete_mountaincar_cartpole_or_pendulum():
    cfg=m.load_config()
    hold=m.holdout_from_rule()
    assert hold==[(0.0038,0.0019,0.085),(0.0024,0.0019,0.09),(0.0033,0.0014,0.05)]
    assert mcc_physics_key(mcc_default())==(0.0025,0.0015,0.07)
    assert (0.0025,0.0015,0.07) not in hold
    specs=mcc_lookahead_development()
    assert [tuple(mcc_physics_key(s)) for s in specs]==hold
    assert m.split_hash(specs)==m.HOLD_SPLIT=='d247d7921d6afff7'
    assert cfg['candidate_horizon']==16 and cfg['n_actions']==3 and cfg['cartpole_h3'] is False
    assert cfg['pendulum_weights'] is False and cfg['mountaincar_copy'] is False
    assert mcc_default().gym_id=='MountainCarContinuous-v0'
    assert mcc_default().family=='mountaincar_continuous'
    assert mcc_default().compatible_with(mountaincar_default()) is False
    floor=mountaincar_height(np.asarray([-np.pi/6,0.0],dtype=np.float64))
    assert float(np.asarray(floor).reshape(-1)[0])==pytest.approx(-1.0)


def test_dense_height_replaces_gym_bonus_and_does_not_goal_terminate():
    env=make_task_env(mcc_default(),seed=0)
    assert env.action_space.n==3
    obs,_=env.reset(seed=0)
    nxt,r,term,trunc,_info=env.step(2)
    assert term is False
    assert float(r)==pytest.approx(float(np.asarray(mountaincar_height(nxt)).reshape(-1)[0]))
    assert float(r)!=pytest.approx(100.0)
    env.close()


def test_injected_gravity_matches_gym_at_default_and_changes_when_raised():
    raw=gym.make('MountainCarContinuous-v0')
    raw.reset(seed=1)
    gym_nxt,_,_,_,_=raw.step(np.asarray([1.0],dtype=np.float32))
    raw.close()
    env=make_task_env(mcc_default(),seed=1)
    env.reset(seed=1)
    ours,_,_,_,_=env.step(2)
    env.close()
    assert np.allclose(np.asarray(ours,dtype=np.float32),np.asarray(gym_nxt,dtype=np.float32),atol=1e-6)
    heavy=replace(mcc_default(), params=dict(mcc_default().params, gravity=0.004))
    env=make_task_env(heavy,seed=1)
    env.reset(seed=1)
    alt,_,_,_,_=env.step(2)
    env.close()
    assert not np.allclose(np.asarray(alt,dtype=np.float32),np.asarray(gym_nxt,dtype=np.float32),atol=1e-6)


def test_collection_stays_unauthorized_and_has_no_output():
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False
    with pytest.raises(PermissionError,match='fresh human approval required'):
        m.execute()


def test_primary_labels_and_parents():
    assert m.classify_primary(25.1,0.1,50.0,10)=='mountaincar_continuous_lookahead_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='mountaincar_continuous_lookahead_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='mountaincar_continuous_lookahead_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'
    cfg=m.load_config()
    assert cfg['mountaincar_copy'] is False and cfg['pendulum_weights'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    report=m.prep()
    assert report['authorized'] is False
    assert report['eligibility']['reused_discrete_mountaincar'] is False
    assert sha(m.CONFIG)==m.LOCKED_CONFIG
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL
    assert m.load_allocation()['config_sha256']==m.LOCKED_CONFIG
    assert m.load_allocation()['protocol_sha256']==m.LOCKED_PROTOCOL
