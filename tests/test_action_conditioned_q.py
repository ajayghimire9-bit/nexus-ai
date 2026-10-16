"""Action-conditioned Q protocol locks. These tests do not collect the registered grid."""
from __future__ import annotations
import itertools
from pathlib import Path
import numpy as np
import pytest
from nexus.world import action_conditioned_q as m
from nexus.world import first_action_value as linear_q
from nexus.world import capacity_matched_q as poly_q
from nexus.world.terminal_value import NAMES


def test_action_observation_features_have_explicit_interactions():
    obs=np.array([0.2,-0.1,0.05]);q=m.features('action_obs',obs,None,[0,1,2])
    assert q.shape==(3,15)
    assert np.allclose(q[:,:3],np.repeat(obs.reshape(1,3),3,axis=0))
    assert np.array_equal(q[:,3:6],np.eye(3))
    assert np.allclose(q[:,6:9],[obs,np.zeros(3),np.zeros(3)])
    assert np.allclose(q[:,9:12],[np.zeros(3),obs,np.zeros(3)])
    additive=m.features('additive',obs,None,[0,1,2])
    assert additive.shape==(3,6)


def test_synthetic_preferred_action_changes_across_states():
    examples=m._synthetic_interaction_data()
    add=m.RidgeQ.fit(*m.stack_examples('additive',examples),ridge=1.0)
    cond=m.RidgeQ.fit(*m.stack_examples('action_obs',examples),ridge=1.0)
    assert m.ranking_is_state_dependent(add,'additive') is False
    assert m.ranking_is_state_dependent(cond,'action_obs') is True
    plus,minus=np.array([0.8,0.0,0.0]),np.array([-0.8,0.0,0.0])
    assert m.preferred_actions(cond,'action_obs',[plus,minus])==[0,1]


def test_additive_baseline_cannot_change_preferred_action():
    rng=np.random.default_rng(0)
    examples=[]
    for i in range(24):
        obs=rng.normal(size=3).tolist()
        for a in range(3):
            examples.append(dict(task=i%8,obs=obs,action=a,y=float(a)))
    model=m.RidgeQ.fit(*m.stack_examples('additive',examples),ridge=1.0)
    chosen=m.preferred_actions(model,'additive',[rng.normal(size=3) for _ in range(8)])
    assert len(set(chosen))==1


def test_repeated_context_rows_are_not_independent_labels():
    cells=[dict(decoder=0,task=t,obs=[0.1*t,0.0,0.0],returns=[float(t),1.0,-1.0]) for t in range(8)]
    examples=m.unique_source_examples(0,cells)
    assert len(examples)==24
    x,y=m.stack_examples('action_obs',examples)
    diag=m.design_diagnostics('action_obs',x,y,ridge=1.0)
    assert diag['n_rows']==24 and diag['n_weights']==16
    assert diag['state_dependent'] is True and diag['uses_context'] is False


def test_source_only_cross_task_selection_ignores_development_cells():
    cells=[dict(decoder=0,task=t,obs=[0.4 if t%2==0 else -0.4,0.0,0.0],
                returns=[10.0, -10.0, 0.0] if t%2==0 else [-10.0, 10.0, 0.0]) for t in range(8)]
    extra=dict(decoder=0,task=8,obs=[9.0,9.0,9.0],returns=[100.0,100.0,100.0])
    examples=m.unique_source_examples(0,cells)
    row=m.leave_one_task_out(examples,'action_obs',1.0)
    assert row['n_held_out_tasks']==8 and row['action_id']>0.5
    with pytest.raises(ValueError):
        m.unique_source_examples(0,cells+[extra])


def test_family_selection_prefers_state_dependent_models():
    table={
        'additive':{'0.1':dict(action_id=0.9,rmse=1.0,n_weights=7),'1.0':dict(action_id=0.9,rmse=1.0,n_weights=7),'10.0':dict(action_id=0.9,rmse=1.0,n_weights=7)},
        'action_obs':{'0.1':dict(action_id=0.6,rmse=2.0,n_weights=16),'1.0':dict(action_id=0.7,rmse=1.4,n_weights=16),'10.0':dict(action_id=0.5,rmse=3.0,n_weights=16)},
        'action_obs_z':{'0.1':dict(action_id=0.7,rmse=1.4,n_weights=24),'1.0':dict(action_id=0.7,rmse=1.4,n_weights=24),'10.0':dict(action_id=0.4,rmse=4.0,n_weights=24)},
        'action_obs_action_z':{'0.1':dict(action_id=0.2,rmse=8.0,n_weights=48),'1.0':dict(action_id=0.2,rmse=8.0,n_weights=48),'10.0':dict(action_id=0.2,rmse=8.0,n_weights=48)},
    }
    chosen=m.select_registered_family(table)
    assert chosen['family']=='action_obs' and chosen['ridge']==1.0
    assert chosen['n_weights']==16 and chosen['rmse']==1.4
    assert 'additive' not in m.ELIGIBLE


def test_ridge_grid_is_source_only_and_rejects_other_values():
    x=m.features('action_obs',np.zeros(3),None,[0,1,2])
    with pytest.raises(ValueError,match='regularization'):
        m.RidgeQ.fit(x,[0.0,1.0,0.0],ridge=2.0)


def test_row_metrics_keep_h16_and_sequence_value_independent_of_q():
    seq=np.zeros((16,16),dtype=np.int64);seq[:,0]=np.arange(16)%3
    z=np.zeros(8);obs=np.zeros(3)
    inputs=np.concatenate([np.zeros((16,3)),np.repeat(z.reshape(1,8),16,axis=0)],axis=1)
    base=np.zeros(16);base[2]=10.0
    corrected=np.zeros(16);corrected[0]=10.0
    scores={name:dict(base=base.tolist(),corrected=corrected.tolist(),inputs=inputs.tolist()) for name in NAMES}
    examples=m._synthetic_interaction_data()
    cond=m.RidgeQ.fit(*m.stack_examples('action_obs',examples),ridge=1.0)
    add=m.RidgeQ.fit(*m.stack_examples('additive',examples),ridge=1.0)
    student=m.row_metrics(scores,seq,[1.0,2.0,3.0],cond,add,obs,'action_obs','additive')['0']
    assert student['h16_first']==3.0 and student['sequence_first']==1.0
    other=m.RidgeQ.fit(*m.stack_examples('additive',examples),ridge=10.0)
    swapped=m.row_metrics(scores,seq,[1.0,2.0,3.0],cond,other,obs,'action_obs','additive')['0']
    assert swapped['h16_first']==3.0 and swapped['sequence_first']==1.0


def test_equal_visitor_weight_and_decoder_units():
    cfg=dict(practical_margin=1.0);rows=[]
    metrics={k:0.0 for k in m.FIELDS}
    for d,t,v in itertools.product(range(10),range(3),range(2)):
        cell={name:dict(metrics) for name in NAMES}
        for name in cell:cell[name]['gain_vs_h16']=10.0 if v==0 else 0.0
        rows.append(dict(decoder=d,task=t,state=v,metrics=cell))
    summary=m.summarize(rows,cfg)
    assert summary['groups']['pooled']['gain_vs_h16']['interval']['mean']==5.0
    assert summary['groups']['pooled']['gain_vs_h16']['interval']['n']==10


def test_primary_label_distinguishes_incomplete_from_inconclusive():
    assert m.classify_primary(2.0,-1.0,3.0,10,1.0,True)=='action_conditioned_gain_not_established'
    assert m.classify_primary(2.0,0.5,3.0,10,1.0,True)=='action_conditioned_gain'
    assert m.classify_primary(-2.0,-3.0,-0.1,10,1.0,True)=='action_conditioned_harm'
    assert m.classify_primary(2.0,0.5,3.0,9,1.0,True)=='incomplete'


def test_budget_seeds_and_unauthorized_allocation():
    cfg=m.load_config();counts=m.budget(cfg)
    assert counts['source_labels']==30720 and counts['collection']+counts['first_common']==14520
    assert counts['model_states']==11612160
    assert cfg['family']=='action_obs' and cfg['source_states']==2 and cfg['n_weights']==16
    blocked=set().union(*poly_q.seed_groups(linear_q.load_config()),*poly_q.seed_groups(poly_q.load_config()))
    used=set().union(*m.seed_groups(cfg))
    assert not (used & blocked) and min(used)>=6000000
    record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    with pytest.raises(PermissionError,match='fresh human approval'):
        m.require_allocation(cfg)
    text=Path('docs/NEXUS_ACTION_CONDITIONED_Q_PROTOCOL.md').read_text()
    assert 'n_weights: 16' in text and 'authorized: false' in text
    assert 'architecture_change_authorized: false' in text
    assert 'NEXUS_CAPACITY_MATCHED_Q_PROTOCOL.md' in text


def test_complete_grid_rejects_a_missing_decoder():
    cfg=dict(practical_margin=1.0);rows=[]
    metrics={k:0.0 for k in m.FIELDS}
    for d,t,v in itertools.product(range(9),range(3),range(2)):
        rows.append(dict(decoder=d,task=t,state=v,metrics={name:dict(metrics) for name in NAMES}))
    with pytest.raises(ValueError,match='incomplete'):
        m.summarize(rows,cfg)


def test_capacity_matched_protocol_was_not_modified():
    from nexus.world.planning_value import sha
    assert sha('docs/NEXUS_CAPACITY_MATCHED_Q_PROTOCOL.md')=='f4965d77d236d2d44085c865b5bff96ce235d6aa62e2415ec30ee77c1868f612'
    assert sha('configs/capacity_matched_q.yaml')=='ff34a3e2c4e5feb2d3f9d8acddb8b2158f28892c1761855993ecff7d032a02f6'
