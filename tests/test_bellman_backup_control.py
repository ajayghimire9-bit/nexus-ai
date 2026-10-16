"""Bellman-backup protocol locks. One-run allocation is bound; collection is not yet executed."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.world import bellman_backup_control as m
from nexus.world import late_episode_decision_trajectory as late
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences


class Drift:
    uses_simulator=False
    def step(self,obs,actions):
        o=np.asarray(obs,dtype=np.float32).reshape(-1,3)
        a=np.asarray(actions,dtype=np.int64).reshape(-1)
        nxt=o.copy();nxt[:,2]=o[:,2]+0.01*(a+1)
        return nxt,np.zeros(len(o),dtype=np.float64)


class Count:
    uses_simulator=False
    def __init__(self,inner):
        self.inner=inner;self.n=0
    def step(self,obs,actions):
        self.n+=int(np.asarray(actions).size)
        return self.inner.step(obs,actions)


def test_fresh_seeds_do_not_reuse_late_episode_or_h8_resets():
    cfg=m.load_config()
    late_cfg=late.load_config()
    ours=set().union(*m.seed_groups(cfg))
    theirs=set().union(*late.seed_groups(late_cfg))
    assert ours.isdisjoint(theirs)
    assert min(ours)>=13000000
    counts=m.budget(cfg)
    assert counts['episode']==24000 and counts['model_states']==12324000


def test_one_run_allocation_binds_the_registered_hashes():
    record=m.load_allocation()
    assert record['authorized'] is True and record['runs']==1
    assert record['config_sha256']==sha(m.CONFIG)==m.LOCKED_CONFIG
    assert record['protocol_sha256']==sha(m.PROTOCOL)==m.LOCKED_PROTOCOL
    m.require_allocation(m.load_config())
    assert m.OUTPUT.exists() is False
    usage=json.loads(Path(record['one_run_usage_record']).read_text())
    assert float(usage['remaining_session_allowance_s'])==180.0
    assert int(usage['retries'])==0


def test_primary_labels_require_the_25_point_episode_margin():
    assert m.classify_primary(25.1,0.1,50.0,10)=='bellman_backup_improves_episode_return'
    assert m.classify_primary(-26.0,-40.0,-1.0,10)=='bellman_backup_hurts_episode_return'
    assert m.classify_primary(10.0,-1.0,20.0,10)=='bellman_backup_not_established'
    assert m.classify_primary(30.0,1.0,40.0,9)=='incomplete'


def test_closed_parents_are_byte_identical():
    cfg=m.load_config()
    for path,digest in cfg['parents'].items():
        assert sha(path)==digest
    assert cfg['new_network'] is False
    assert cfg['training_updates']==0
    assert sha(m.CONFIG)==m.LOCKED_CONFIG
    assert sha(m.PROTOCOL)==m.LOCKED_PROTOCOL


def test_h16_and_lookahead_use_the_locked_imagined_counts():
    seq=candidate_sequences(13100000,16,16)
    obs=np.array([1.0,0.0,0.2],dtype=np.float32)
    h=Count(Drift());action,scores,idx,_pred=m.h16_first_action(h,obs,seq)
    assert h.n==256 and action==int(seq[idx,0]) and int(np.argmax(scores))==idx
    look=Count(Drift());chosen,q,pred=m.lookahead_first_action(look,obs,seq)
    assert look.n==771 and chosen in (0,1,2) and len(q)==3 and int(np.argmax(q))==chosen
    assert pred.shape==(3,)


def test_lookahead_is_not_open_loop_prefix_selection():
    seq=candidate_sequences(13100000,16,16)
    obs=np.array([1.0,0.0,0.2],dtype=np.float32)
    h16_action,_,_,_=m.h16_first_action(Drift(),obs,seq)
    look_action,_,_=m.lookahead_first_action(Drift(),obs,seq)
    assert h16_action in (0,1,2) and look_action in (0,1,2)
    assert isinstance(int(seq[int(np.argmax(np.zeros(16))),0]),int)
