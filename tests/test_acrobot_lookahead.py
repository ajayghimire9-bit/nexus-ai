"""Acrobot lookahead protocol locks. One-run allocation is live and unconsumed."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.tasks.acrobot_family import acrobot_default, acrobot_lookahead_development, acrobot_physics_key
from nexus.tasks.spec import make_task_env
from nexus.world import acrobot_lookahead as m
from nexus.world.planning_value import sha
from nexus.world.rewards import acrobot_height


def test_holdout_is_unused_and_not_cartpole_or_pendulum():
    cfg=m.load_config()
    hold=m.holdout_from_rule()
    assert hold==[(0.95,1.2,0.8),(1.25,1.35,0.95),(0.75,1.4,1.4)]
    assert acrobot_physics_key(acrobot_default())==(1.0,1.0,1.0)
    assert (1.0,1.0,1.0) not in hold
    specs=acrobot_lookahead_development()
    assert [tuple(acrobot_physics_key(s)) for s in specs]==hold
    assert m.split_hash(specs)==m.HOLD_SPLIT=='911ea726b6ed2111'
    assert cfg['candidate_horizon']==16 and cfg['n_actions']==3 and cfg['cartpole_h3'] is False
    assert cfg['pendulum_weights'] is False
    hanging=acrobot_height(np.asarray([1.0,0.0,1.0,0.0,0.0,0.0],dtype=np.float64))
    assert float(np.asarray(hanging).reshape(-1)[0])==pytest.approx(-2.0)


def test_dense_height_replaces_gym_minus_one_and_does_not_goal_terminate():
    env=make_task_env(acrobot_default(),seed=0)
    obs,_=env.reset(seed=0)
    nxt,r,term,trunc,_info=env.step(1)
    assert term is False
    assert float(r)==pytest.approx(float(np.asarray(acrobot_height(nxt)).reshape(-1)[0]))
    env.close()


def test_one_run_allocation_is_live_and_has_no_output():
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['pendulum_weight_transfer'] is False and record['cartpole_h3'] is False
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    assert float(usage['remaining_session_allowance_s'])==300.0
    m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False


def test_primary_labels_and_parents():
    assert m.classify_primary(25.1,0.1,50.0,10)=='acrobot_lookahead_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='acrobot_lookahead_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='acrobot_lookahead_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'
    cfg=m.load_config()
    assert cfg['pendulum_weights'] is False and cfg['cartpole_h3'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert sha(m.CONFIG)==m.LOCKED_CONFIG=='3978b7e309f41339a56a2e6993bc48344f2bbf211baf88d3e86ce994ffa7122a'
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL=='e2b83a21e89292e0aec5112c5456f56f82eb0d14d2b9548389ef8e79ed432567'
    seq=m.shared_candidates(22100000)
    assert seq.shape==(16,16) and int(seq.max())<=2
