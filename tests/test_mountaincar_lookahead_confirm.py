"""MountainCar confirmation protocol locks. The one-run allocation is consumed."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from nexus.tasks.mountaincar_family import (
    mountaincar_default,
    mountaincar_lookahead_confirmation,
    mountaincar_lookahead_development,
    mountaincar_physics_key,
)
from nexus.world import mountaincar_lookahead as base
from nexus.world import mountaincar_lookahead_confirm as m
from nexus.world.planning_value import sha


def test_confirmation_holdout_avoids_source_and_development():
    cfg=m.load_config()
    hold=m.holdout_from_rule()
    assert hold==[(0.0031,0.0007,0.09),(0.0022,0.0014,0.085),(0.0037,0.0014,0.07)]
    closed={mountaincar_physics_key(mountaincar_default())}
    closed|={mountaincar_physics_key(s) for s in mountaincar_lookahead_development()}
    assert all(k not in closed for k in hold)
    specs=mountaincar_lookahead_confirmation()
    assert [tuple(mountaincar_physics_key(s)) for s in specs]==hold
    assert m.split_hash(specs)==m.HOLD_SPLIT=='bf4b4412f4f683dd'
    assert cfg['candidate_horizon']==16 and cfg['retune_from_development'] is False
    assert cfg['pendulum_weights'] is False and cfg['cartpole_h3'] is False
    assert cfg['reset_base']==26000000
    ours={base.reset_seed(cfg,s,t) for s in range(10) for t in range(3)}
    blocked={base.reset_seed(base.load_config(),s,t) for s in range(10) for t in range(3)}
    assert ours.isdisjoint(blocked)


def test_one_run_allocation_is_consumed_and_output_exists():
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['retune_from_development'] is False
    assert record['config_sha256']==sha(m.CONFIG)==m.LOCKED_CONFIG
    assert record['protocol_sha256']==sha(m.PROTOCOL)==m.LOCKED_PROTOCOL
    with pytest.raises(PermissionError,match='session allowance exhausted'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is True
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    assert float(usage['remaining_session_allowance_s'])==0.0
    assert int(usage['retries'])==0
    assert usage['raw_sha256']==sha(m.OUTPUT)
    assert usage['label']=='mountaincar_lookahead_transfer_established'


def test_primary_labels_keep_the_25_point_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='mountaincar_lookahead_transfer_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='mountaincar_lookahead_transfer_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='mountaincar_lookahead_transfer_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_h16_was_not_retuned_and_parents_are_closed():
    cfg=m.load_config()
    assert cfg['candidate_horizon']==16 and cfg['n_candidates']==16
    assert cfg['retune_from_development'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert sha(m.CONFIG)==m.LOCKED_CONFIG=='80675aadd0b5d31b539ba027263df258a72f94bbad5a4a54ed03f28490a80229'
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL=='8f2b4f698198177785476a2b839e8dc2cb68cc4c134b0461d15196af22acc7dd'
    audit=m.audit_results()
    assert audit['audit_passed'] is True
    assert audit['label']=='mountaincar_lookahead_transfer_established'
    assert audit['retune_from_development'] is False
    assert audit['holdout_split_hash']=='bf4b4412f4f683dd'
