"""Acrobot confirmation protocol locks. The one-run allocation is consumed."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from nexus.tasks.acrobot_family import (
    acrobot_default,
    acrobot_lookahead_confirmation,
    acrobot_lookahead_development,
    acrobot_physics_key,
)
from nexus.world import acrobot_lookahead_confirm as m
from nexus.world.planning_value import sha


def test_confirmation_holdout_avoids_source_and_development():
    cfg=m.load_config()
    hold=m.holdout_from_rule()
    assert hold==[(0.75,0.6,0.95),(1.3,1.4,1.4),(1.15,0.85,0.6)]
    closed={acrobot_physics_key(acrobot_default())}
    closed|={acrobot_physics_key(s) for s in acrobot_lookahead_development()}
    assert all(k not in closed for k in hold)
    specs=acrobot_lookahead_confirmation()
    assert [tuple(acrobot_physics_key(s)) for s in specs]==hold
    assert m.split_hash(specs)==m.HOLD_SPLIT=='b309bd481fd8abcb'
    assert cfg['candidate_horizon']==16 and cfg['retune_from_development'] is False
    assert cfg['pendulum_weights'] is False and cfg['cartpole_h3'] is False


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
    assert usage['label']=='acrobot_lookahead_transfer_established'


def test_primary_labels_keep_the_25_point_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='acrobot_lookahead_transfer_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='acrobot_lookahead_transfer_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='acrobot_lookahead_transfer_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_h16_was_not_retuned_and_parents_are_closed():
    cfg=m.load_config()
    assert cfg['candidate_horizon']==16 and cfg['n_candidates']==16
    assert cfg['retune_from_development'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert sha(m.CONFIG)==m.LOCKED_CONFIG=='a87959767f30ca75f0acfc753476ce06fc12c86a324315cc0f910f4149586ab1'
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL=='dcf9913397acad3e9229ff60aa4b169250892f38f87bc2f9366a3564bf1a6b67'
    audit=m.audit_results()
    assert audit['audit_passed'] is True
    assert audit['label']=='acrobot_lookahead_transfer_established'
    assert audit['retune_from_development'] is False
    assert audit['holdout_split_hash']=='b309bd481fd8abcb'
