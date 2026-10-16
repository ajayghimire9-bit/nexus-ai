"""H=3 saturation diagnostic protocol locks. One-run allocation is live and unconsumed."""
from __future__ import annotations
import json
from pathlib import Path
from nexus.tasks.cartpole_family import (
    cartpole_h3_saturation,
    cartpole_lookahead_development,
    cartpole_lookahead_hard,
    cartpole_physics_key,
)
from nexus.world import cartpole_h3_saturation as m
from nexus.world.freeze import v073_confirmation_targets
from nexus.world.planning_value import sha


def test_saturation_holdout_is_stricter_and_avoids_closed_splits():
    cfg=m.load_config()
    hold=m.holdout_from_rule()
    assert hold==[(13.2,0.27,0.23),(15.6,0.25,0.28),(15.4,0.27,0.2),(15.5,0.3,0.28),(16.0,0.34,0.2),(13.8,0.31,0.27)]
    occupied,_rows=m.occupied_physics()
    assert all(k not in occupied for k in hold)
    closed={cartpole_physics_key(s) for s in v073_confirmation_targets()}
    closed|={cartpole_physics_key(s) for s in cartpole_lookahead_development()}
    closed|={cartpole_physics_key(s) for s in cartpole_lookahead_hard()}
    assert (13.0,0.35,0.18) in closed
    assert all(k not in closed for k in hold)
    specs=cartpole_h3_saturation()
    assert [tuple(cartpole_physics_key(s)) for s in specs]==hold
    assert m.split_hash(specs)==m.HOLD_SPLIT=='a69833ab38a34ab4'
    assert cfg['candidate_horizon']==3 and cfg['lookahead_authorized'] is False
    assert cfg['eval_tasks']==6


def test_one_run_allocation_is_live_and_has_no_output():
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['lookahead_authorized'] is False
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    assert float(usage['remaining_session_allowance_s'])==300.0
    m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False


def test_primary_labels_keep_the_25_point_gap_from_ceiling():
    assert m.classify_primary(25.1,0.1,50.0,10)=='cartpole_h3_unsaturated'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='cartpole_h3_still_ceilinged'
    assert m.classify_primary(4.6,-7.5,16.7,10)=='cartpole_h3_still_ceilinged'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_h3_was_not_retuned_lookahead_is_withheld_and_parents_are_closed():
    cfg=m.load_config()
    assert cfg['candidate_horizon']==3 and cfg['pendulum_weights'] is False
    assert cfg['lookahead_authorized'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert sha(m.CONFIG)==m.LOCKED_CONFIG=='55be38a5d77e76bb38a56c50d92e9522037855e8b500577de55c665af9291421'
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL=='657cf38d25c9d013b733e8ba6ef373845b487f980d19f6b815e3cf4ad96cd157'
