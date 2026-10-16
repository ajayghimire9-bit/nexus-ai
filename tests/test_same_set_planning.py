"""Same-set planning locks. These tests do not collect the registered grid."""
from __future__ import annotations
import itertools
from pathlib import Path
import numpy as np
import pytest
import yaml
from nexus.world import same_set_planning as m
from nexus.world import receding_policy_consistency as recede
from nexus.world import action_conditioned_q as acq
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences


def test_remaining_horizon_draws_are_not_full_h16():
    full=candidate_sequences(0)
    rem=m.remaining_sequences(0,15)
    assert full.shape==(16,16) and rem.shape==(16,15)
    assert m.imagined_recede(m.REMAINING)==1920
    assert m.imagined_recede((16,)*15)==3840
    assert m.imagined_recede(m.REMAINING)*2==m.imagined_recede((16,)*15)


def test_suffix_shift_matches_remaining_horizon_length():
    seq=candidate_sequences(4)
    shifted=recede.shift_suffixes(seq,1)
    assert shifted.shape==(16,15) and np.array_equal(shifted,seq[:,1:])
    for k,h in enumerate(m.REMAINING):
        tail=seq[:,1+k:]
        assert tail.shape==(16,h)


def test_primary_label_requires_complete_ten_decoder_screen():
    assert m.classify_primary(2.0,0.5,3.0,10,1.0,True)=='same_set_replanning_gain'
    assert m.classify_primary(-2.0,-3.0,-1.1,10,1.0,True)=='fresh_equal_horizon_gain'
    assert m.classify_primary(2.0,-0.1,3.0,10,1.0,True)=='same_set_advantage_not_established'
    assert m.classify_primary(2.0,0.5,3.0,9,1.0,True)=='incomplete'


def test_summarize_uses_ten_decoder_units():
    rows=[]
    for d,t,v in itertools.product(range(10),range(3),range(2)):
        metrics={k:0.0 for k in m.FIELDS}
        metrics['same']=4.0;metrics['fresh_equal']=1.0;metrics['gain_same_fresh']=3.0
        rows.append(dict(decoder=d,task=t,state=v,metrics=metrics))
    summary=m.summarize(rows,dict(practical_margin=1.0))
    assert summary['groups']['pooled']['gain_same_fresh']['interval']['mean']==3.0
    assert summary['groups']['pooled']['gain_same_fresh']['interval']['n']==10
    assert summary['label']=='same_set_replanning_gain'


def test_budget_seeds_unauthorized_and_parents_frozen():
    cfg=m.load_config();counts=m.budget(cfg)
    assert counts['same']+counts['fresh_equal']+counts['h16']==2880
    assert counts['model_states']==506880
    assert counts['same']==counts['fresh_equal']==counts['h16']
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    with pytest.raises(PermissionError,match='fresh human approval'):
        m.require_allocation(cfg)
    recede_cfg=yaml.safe_load(recede.CONFIG.read_text())
    blocked=set().union(*acq.seed_groups(yaml.safe_load(acq.CONFIG.read_text())),*recede.seed_groups(recede_cfg))
    used=set().union(*m.seed_groups(cfg))
    assert not (used & blocked) and min(used)>=8000000
    assert sha('artifacts/receding_policy_consistency.json')=='48736a499e0d650dbf8138cc29e03cdbb623f0e3b413dec7b2b6b552adc2e149'
    assert sha('docs/NEXUS_RECEDING_POLICY_CONSISTENCY_PROTOCOL.md')=='69e50a8409167ff64de64afd55ddc136273498740d8c5cfad04d281acbb6f85e'
    text=Path('docs/NEXUS_SAME_SET_PLANNING_PROTOCOL.md').read_text()
    assert 'authorized: false' in text and 'score_correction_closed: true' in text
    assert 'confirmation_physics_authorized: false' in text
    assert not m.OUTPUT.exists()
