"""First-action Q protocol locks. These tests do not collect the registered grid."""
from __future__ import annotations
import copy
import itertools
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.world import first_action_value as m
from nexus.world import source_scalar_calibration as scalar
from nexus.world import visited_commitment as visited


def test_linear_q_recovers_a_known_action_preference():
    rng=np.random.default_rng(0);x=rng.normal(size=(144,14));x[:,11:]=np.eye(3)[np.tile(np.arange(3),48)]
    y=2.0*x[:,12]-1.0*x[:,11]
    model=m.ActionValueReadout.fit(x,y,ridge=1.0)
    assert model.weights.shape==(15,)
    pred=model.predict(x);assert float(np.corrcoef(pred,y)[0,1])>0.99
    q=model.predict(np.concatenate([np.zeros((3,11)),np.eye(3)],axis=1))
    assert int(np.argmax(q))==1


def test_development_labels_cannot_change_a_frozen_source_fit():
    rng=np.random.default_rng(1)
    source_x=rng.normal(size=(144,14));source_y=rng.normal(size=144)
    eval_x=rng.normal(size=(60,14));eval_y=rng.normal(size=60)+100
    frozen=m.ActionValueReadout.fit(source_x,source_y,ridge=1.0)
    mixed=m.ActionValueReadout.fit(np.vstack([source_x,eval_x]),np.concatenate([source_y,eval_y]),ridge=1.0)
    assert frozen.digest()!=mixed.digest()
    again=m.ActionValueReadout.fit(source_x,source_y,ridge=1.0)
    assert again.digest()==frozen.digest()


def test_common_continuation_seed_has_no_action_argument():
    cfg=m.load_config()
    first=m.source_future_seeds(cfg,2);again=m.source_future_seeds(cfg,2)
    assert first==again and len(first)==64
    assert m.future_seeds(cfg,1,2,0)==m.future_seeds(cfg,1,2,0)
    assert 'action' not in m.source_future_seeds.__code__.co_varnames
    assert 'action' not in m.future_seeds.__code__.co_varnames


def test_candidate_seed_is_shared_across_scoring_rules():
    cfg=m.load_config();seed=m.candidate_seed(cfg,4,1,1)
    seq=m.candidate_sequences(seed)
    assert seq.shape==(16,16) and seed==m.candidate_seed(cfg,4,1,1)


def test_new_seeds_are_disjoint_from_closed_blocks():
    cfg=m.load_config();m.check_seeds(cfg)
    blocked=set().union(*scalar.seed_sets(visited.load_config()),*scalar.seed_sets(scalar.load_config()))
    used={m.source_state_seed(cfg,t) for t in range(8)}
    used|={m.reset_seed(cfg,d,t) for d,t in itertools.product(range(10),range(3))}
    used|={m.candidate_seed(cfg,d,t,v) for d,t,v in itertools.product(range(10),range(3),range(2))}
    assert not (used & blocked)
    assert min(used)>=4000000


def test_equal_visitor_weight_and_decoder_units():
    cfg=m.load_config();rows=[]
    metrics={k:0.0 for k in m.FIELDS}
    for d,t,v in itertools.product(range(10),range(3),range(2)):
        cell={name:dict(metrics) for name in m.NAMES}
        for name in cell:
            cell[name]['gain_vs_h16']=10.0 if v==0 else 0.0
        rows.append(dict(decoder=d,task=t,state=v,metrics=cell))
    summary=m.summarize(rows,cfg)
    assert summary['groups']['pooled']['gain_vs_h16']['interval']['mean']==5.0
    assert summary['groups']['pooled']['gain_vs_h16']['interval']['n']==10
    assert summary['groups']['student_visitor']['gain_vs_h16']['interval']['mean']==10.0
    assert summary['groups']['zero_visitor']['gain_vs_h16']['interval']['mean']==0.0


def test_primary_label_distinguishes_incomplete_from_inconclusive():
    assert m.classify_primary(2.0,-1.0,3.0,10,1.0,True)=='aligned_first_action_gain_not_established'
    assert m.classify_primary(2.0,0.5,3.0,10,1.0,True)=='aligned_first_action_gain'
    assert m.classify_primary(-2.0,-3.0,-0.1,10,1.0,True)=='aligned_first_action_harm'
    assert m.classify_primary(2.0,0.5,3.0,9,1.0,True)=='incomplete'
    assert m.classify_primary(2.0,0.5,3.0,10,1.0,False)=='incomplete'


def test_aligned_selection_uses_candidate_first_actions_and_lowest_index_ties():
    readout=m.ActionValueReadout.fit(np.concatenate([np.zeros((3,11)),np.eye(3)],axis=1),[0.0,0.0,0.0],ridge=1.0)
    seq=np.zeros((16,16),dtype=np.int64);seq[5,0]=1;seq[7,0]=1
    chosen=m.score_aligned(readout,np.zeros(3),np.zeros(8),seq)
    assert chosen['first_action']==0 and chosen['selected']==0
    class PreferActionOne:
        def predict(self,inputs):
            return np.asarray(inputs,dtype=np.float64)[:,12]*10.0
    chosen=m.score_aligned(PreferActionOne(),np.zeros(3),np.zeros(8),seq)
    assert chosen['first_action']==1 and chosen['selected']==5


def test_row_metrics_use_measured_first_action_returns():
    seq=np.zeros((16,16),dtype=np.int64);seq[:,0]=np.arange(16)%3
    z=np.zeros(8);obs=np.zeros(3)
    inputs=np.concatenate([np.zeros((16,3)),np.repeat(z.reshape(1,8),16,axis=0)],axis=1)
    base=np.zeros(16);base[2]=10.0
    corrected=np.zeros(16);corrected[0]=10.0
    scores={name:dict(base=base.tolist(),corrected=corrected.tolist(),inputs=inputs.tolist()) for name in m.NAMES}
    q=m.ActionValueReadout.fit(np.concatenate([np.zeros((3,11)),np.eye(3)],axis=1),[0.0,5.0,0.0],ridge=1.0)
    metrics=m.row_metrics(scores,seq,[1.0,2.0,3.0],{name:q for name in m.NAMES},obs)
    student=metrics['0']
    assert student['h16_first']==3.0
    assert student['sequence_first']==1.0
    assert student['aligned_first']==2.0
    assert student['gain_vs_h16']==-1.0
    assert student['gain_vs_sequence']==1.0


def test_budget_and_protocol_lock():
    cfg=m.load_config();counts=m.budget(cfg)
    assert counts['source_labels']+counts['collection']+counts['first_common']==29880
    assert counts['model_states']==7741440
    assert cfg['n_weights']==15 and cfg['horizon']==16 and cfg['n_candidates']==16
    text=Path('docs/NEXUS_FIRST_ACTION_VALUE_PROTOCOL.md').read_text()
    assert '7741440' in text and 'aligned_minus_h16_first_action_64' in text
    assert 'architecture_change_authorized: false' in text


def test_allocation_binds_the_locked_hashes():
    cfg=m.load_config();m.require_allocation(cfg)


def test_missing_allocation_blocks_execution(monkeypatch,tmp_path):
    monkeypatch.setattr(m,'ALLOCATION',tmp_path/'missing.json')
    with pytest.raises((FileNotFoundError,PermissionError)):
        m.require_allocation(m.load_config())


def test_complete_grid_rejects_a_missing_decoder():
    cfg=m.load_config();rows=[]
    metrics={k:0.0 for k in m.FIELDS}
    for d,t,v in itertools.product(range(9),range(3),range(2)):
        rows.append(dict(decoder=d,task=t,state=v,metrics={name:dict(metrics) for name in m.NAMES}))
    with pytest.raises(ValueError,match='incomplete'):
        m.summarize(rows,cfg)


def test_source_arrays_ignore_held_out_development_physics():
    z={name:[0.0]*8 for name in m.NAMES}
    cells=[dict(decoder=0,task=t,obs=[0.1,0.0,0.0],returns=[float(t),0.0,1.0]) for t in range(8)]
    extra=dict(decoder=0,task=8,obs=[9.0,9.0,9.0],returns=[100.0,100.0,100.0])
    features,labels=m.source_training_arrays(0,cells,{t:z for t in range(8)})
    assert features.shape==(144,14) and labels.shape==(144,)
    with pytest.raises(ValueError):
        m.source_training_arrays(0,cells+[extra],{t:z for t in range(8)})


def test_simulator_restore_is_exact_on_an_unregistered_reset():
    from nexus.tasks.pendulum_family import pendulum_context_development
    from nexus.tasks.spec import make_task_env
    from nexus.world.receding_horizon import true_state
    from nexus.world.long_continuation_execution import restore_at_phase
    spec=pendulum_context_development()[0];env=make_task_env(spec)
    obs,_=env.reset(seed=424242);state=true_state(env)
    env.step(1);restored=restore_at_phase(env,state,0)
    assert np.array_equal(restored,obs)
    env.close()
