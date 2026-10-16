"""MountainCar compute-matched protocol locks. The one-run allocation is consumed."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from nexus.tasks.mountaincar_family import (
    mountaincar_lookahead_confirmation,
    mountaincar_lookahead_development,
    mountaincar_physics_key,
)
from nexus.world import mountaincar_compute_matched as m
from nexus.world import mountaincar_lookahead as base
from nexus.world import mountaincar_lookahead_confirm as confirm
from nexus.world.planning_value import sha


def test_holdout_is_development_and_confirmation_stays_closed():
    cfg=m.load_config()
    hold=base.holdout_from_rule()
    assert hold==[(0.0035,0.0006,0.075),(0.0025,0.0013,0.07),(0.0015,0.0013,0.085)]
    specs=mountaincar_lookahead_development()
    assert [tuple(mountaincar_physics_key(s)) for s in specs]==hold
    closed={mountaincar_physics_key(s) for s in mountaincar_lookahead_confirmation()}
    assert closed.isdisjoint(set(hold))
    assert cfg['holdout_split_hash']==m.HOLD_SPLIT=='2a5cc4979642cc2a'
    assert cfg['closed_confirmation_split_hash']==confirm.HOLD_SPLIT=='bf4b4412f4f683dd'
    assert cfg['reset_base']==27000000 and cfg['step_seed_base']==27100000
    ours=set().union(*m.seed_groups(cfg))
    assert min(ours)>=27000000
    blocked={base.reset_seed(base.load_config(),s,t) for s in range(10) for t in range(3)}
    blocked|={base.reset_seed(confirm.load_config(),s,t) for s in range(10) for t in range(3)}
    assert ours.isdisjoint(blocked)


def test_forty_eight_candidates_are_a_prefix_of_frozen_sixteen():
    seq48,seq16=m.shared_candidates(27100000)
    assert seq48.shape==(48,16) and seq16.shape==(16,16)
    assert (seq48[:16]==seq16).all()
    counts=m.budget(m.load_config())
    assert counts['episode_max']==12000 and counts['model_states_max']==9234000
    assert counts['lookahead_imagined_per_step']==771
    assert counts['matched_h16_imagined_per_step']==768
    assert counts['original_h16_imagined_per_step']==256
    assert counts['training_updates']==0


def test_one_run_allocation_is_consumed_and_output_exists():
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['retune_from_confirmation'] is False
    assert record['config_sha256']==sha(m.CONFIG)==m.LOCKED_CONFIG
    assert record['protocol_sha256']==sha(m.PROTOCOL)==m.LOCKED_PROTOCOL
    with pytest.raises(PermissionError,match='session allowance exhausted'):
        m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is True
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    assert float(usage['remaining_session_allowance_s'])==0.0
    assert int(usage['retries'])==0
    assert usage['raw_sha256']==sha(m.OUTPUT)
    assert usage['label']=='mountaincar_compute_matched_lookahead_established'


def test_primary_labels_require_the_25_point_episode_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='mountaincar_compute_matched_lookahead_established'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='mountaincar_compute_matched_lookahead_harm_established'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='mountaincar_compute_matched_lookahead_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_frozen_checkpoints_and_lookahead_identity():
    m.load_frozen_models(m.load_config())
    cfg=m.load_config()
    assert cfg['compute_matched_control'] is True
    assert cfg['reuse_development_checkpoints'] is True
    assert cfg['training_updates']==0
    assert cfg['n_candidates']==16 and cfg['matched_candidates']==48
    assert cfg['pendulum_weights'] is False and cfg['cartpole_h3'] is False
    assert cfg['retune_from_confirmation'] is False
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert sha(m.CONFIG)==m.LOCKED_CONFIG=='e33b01b6d50aff45f7c7a99990b978fa7e8bc58503da472903c79651d0eda033'
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL=='6f5be2802e132bc944e8c97437b0e60a22ebb304b6fdb2a54445fdc3fe75b076'
    assert m.load_allocation()['config_sha256']==m.LOCKED_CONFIG
    assert m.load_allocation()['protocol_sha256']==m.LOCKED_PROTOCOL
    audit=m.audit_results()
    assert audit['audit_passed'] is True
    assert audit['label']=='mountaincar_compute_matched_lookahead_established'
    assert audit['pendulum_weights'] is False and audit['cartpole_h3'] is False
    assert audit['holdout_split_hash']=='2a5cc4979642cc2a'
    assert audit['retune_from_confirmation'] is False
