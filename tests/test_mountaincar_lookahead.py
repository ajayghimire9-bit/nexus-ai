"""MountainCar lookahead protocol locks. The one-run allocation is consumed."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.tasks.mountaincar_family import mountaincar_default, mountaincar_lookahead_development, mountaincar_physics_key
from nexus.tasks.spec import make_task_env
from nexus.world import mountaincar_lookahead as m
from nexus.world.planning_value import sha
from nexus.world.rewards import mountaincar_height


def test_holdout_is_unused_and_not_cartpole_pendulum_or_acrobot():
    cfg=m.load_config()
    hold=m.holdout_from_rule()
    assert hold==[(0.0035,0.0006,0.075),(0.0025,0.0013,0.07),(0.0015,0.0013,0.085)]
    assert mountaincar_physics_key(mountaincar_default())==(0.0025,0.001,0.07)
    assert (0.0025,0.001,0.07) not in hold
    specs=mountaincar_lookahead_development()
    assert [tuple(mountaincar_physics_key(s)) for s in specs]==hold
    assert m.split_hash(specs)==m.HOLD_SPLIT=='2a5cc4979642cc2a'
    assert cfg['candidate_horizon']==16 and cfg['n_actions']==3 and cfg['cartpole_h3'] is False
    assert cfg['pendulum_weights'] is False and cfg['acrobot_copy'] is False
    floor=mountaincar_height(np.asarray([-np.pi/6,0.0],dtype=np.float64))
    assert float(np.asarray(floor).reshape(-1)[0])==pytest.approx(-1.0)


def test_dense_height_replaces_gym_minus_one_and_does_not_goal_terminate():
    env=make_task_env(mountaincar_default(),seed=0)
    obs,_=env.reset(seed=0)
    nxt,r,term,trunc,_info=env.step(2)
    assert term is False
    assert float(r)==pytest.approx(float(np.asarray(mountaincar_height(nxt)).reshape(-1)[0]))
    assert float(r)!=pytest.approx(-1.0)
    env.close()


def test_one_run_allocation_is_consumed_and_output_exists():
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['pendulum_weight_transfer'] is False and record['cartpole_h3'] is False
    assert record['config_sha256']==sha(m.CONFIG)==m.LOCKED_CONFIG
    assert record['protocol_sha256']==sha(m.PROTOCOL)==m.LOCKED_PROTOCOL
    with pytest.raises(PermissionError,match='session allowance exhausted'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is True
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    assert float(usage['remaining_session_allowance_s'])==0.0
    assert int(usage['retries'])==0
    assert usage['raw_sha256']==sha(m.OUTPUT)
    assert usage['label']=='mountaincar_lookahead_established'


def test_primary_labels_and_parents():
    assert m.classify_primary(25.1,0.1,50.0,10)=='mountaincar_lookahead_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='mountaincar_lookahead_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='mountaincar_lookahead_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'
    cfg=m.load_config()
    assert cfg['pendulum_weights'] is False and cfg['cartpole_h3'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert sha(m.CONFIG)==m.LOCKED_CONFIG=='9e4f9cf8b92cbb5e54d9a17b20c1518aae9f925e490930cd4b958ec7885e97f4'
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL=='4f7ebc5f30755e80adecee9c930e9b888a006f1e5edca00d742a8caa3932d4bb'
    assert m.load_allocation()['config_sha256']==m.LOCKED_CONFIG
    assert m.load_allocation()['protocol_sha256']==m.LOCKED_PROTOCOL
    audit=m.audit_results()
    assert audit['audit_passed'] is True
    assert audit['label']=='mountaincar_lookahead_established'
    assert audit['pendulum_weights'] is False and audit['cartpole_h3'] is False
    assert audit['holdout_split_hash']=='2a5cc4979642cc2a'
