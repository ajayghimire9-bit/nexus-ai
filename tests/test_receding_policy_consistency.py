"""Receding policy-consistency locks. These tests do not collect the registered grid."""
from __future__ import annotations
import itertools
from pathlib import Path
import numpy as np
import pytest
import yaml
from nexus.world import receding_policy_consistency as m
from nexus.world import action_conditioned_q as acq
from nexus.world.planning_value import sha
from nexus.world.prediction_control_gap import candidate_sequences


def test_suffix_shift_preserves_the_original_plan_tail():
    seq=candidate_sequences(11)
    shifted=m.shift_suffixes(seq,1)
    assert shifted.shape==(16,15) and np.array_equal(shifted,seq[:,1:])
    plan=m.selected_plan(seq,np.arange(16,dtype=np.float64))
    assert int(shifted[plan['index'],0])==int(plan['sequence'][1])


def test_search_noise_is_not_the_same_as_same_set_suffix_identity():
    seq=candidate_sequences(0)
    other=candidate_sequences(1)
    scores=np.arange(16,dtype=np.float64)
    a=m.selected_plan(seq,scores)['first_action']
    b=m.selected_plan(other,scores)['first_action']
    noise=m.first_action_switch(a,b)
    same=m.first_action_switch(int(seq[-1,1]),int(m.shift_suffixes(seq,1)[-1,0]))
    assert same==0.0
    assert noise in (0.0,1.0)


def test_offline_live_mismatch_rebuilds_from_stored_seeds_without_env():
    seq=candidate_sequences(21)
    stay=int(seq[3,1]);flip=0 if stay!=0 else 1
    collection=[
        dict(seed=21,selected_index=3,action=int(seq[3,0]),reward=0.0),
        dict(seed=22,selected_index=0,action=stay,reward=-1.0),
    ]
    stayed=m.live_suffix_mismatches(collection)
    assert stayed[0]['switch']==0.0 and stayed[0]['intended']==stay
    collection[1]['action']=flip
    flipped=m.live_suffix_mismatches(collection)
    assert flipped[0]['switch']==1.0


def test_primary_label_distinguishes_incomplete_from_inconclusive():
    assert m.classify_primary(2.0,-1.0,3.0,10,1.0,True)=='replan_consistency_not_established'
    assert m.classify_primary(2.0,0.5,3.0,10,1.0,True)=='open_loop_commitment_gain'
    assert m.classify_primary(-2.0,-3.0,-1.1,10,1.0,True)=='receding_replanning_gain'
    assert m.classify_primary(2.0,0.5,3.0,9,1.0,True)=='incomplete'


def test_summarize_uses_ten_decoder_units_and_equal_visitors():
    rows=[]
    for d,t,v in itertools.product(range(10),range(8),range(2)):
        metrics={k:0.0 for k in m.FIELDS}
        metrics['commit']=10.0 if v==0 else 0.0
        metrics['recede_fresh']=0.0
        metrics['gain_commit_fresh']=metrics['commit']-metrics['recede_fresh']
        rows.append(dict(decoder=d,task=t,state=v,metrics=metrics))
    summary=m.summarize(rows,dict(practical_margin=1.0))
    assert summary['groups']['pooled']['gain_commit_fresh']['interval']['mean']==5.0
    assert summary['groups']['pooled']['gain_commit_fresh']['interval']['n']==10


def test_budget_seeds_unauthorized_and_score_correction_closed():
    cfg=m.load_config();counts=m.budget(cfg)
    assert counts['commit']+counts['recede_same']+counts['recede_fresh']+counts['common_zero']==8960
    assert counts['model_states']==1515520
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    with pytest.raises(PermissionError,match='fresh human approval'):
        m.require_allocation(cfg)
    blocked=set().union(*acq.seed_groups(yaml.safe_load(acq.CONFIG.read_text())))
    used=set().union(*m.seed_groups(cfg))
    assert not (used & blocked) and min(used)>=7000000
    assert sha('docs/NEXUS_ACTION_CONDITIONED_Q_PROTOCOL.md')=='76c06fd1de355d7176f7165b6e2dc1cfceb0729b67ea5cac244e595207bfa597'
    assert sha('artifacts/action_conditioned_q_completed.json')=='aa78514a5a2bb560089453000d8049284aafe3136c83f03c1a88de9dc01a3793'
    text=Path('docs/NEXUS_RECEDING_POLICY_CONSISTENCY_PROTOCOL.md').read_text()
    assert 'authorized: false' in text and 'score_correction_closed: true' in text
    assert not m.OUTPUT.exists()
