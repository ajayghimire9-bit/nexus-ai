"""Capacity-matched Q protocol locks. These tests do not collect the registered grid."""
from __future__ import annotations
import copy
import itertools
import json
from pathlib import Path
import numpy as np
import pytest
from nexus.world import capacity_matched_q as m
from nexus.world import first_action_value as linear_q
from nexus.world import source_scalar_calibration as scalar
from nexus.world import visited_commitment as visited
from nexus.world.terminal_value import polynomial_features


def test_features_match_sequence_value_polynomial_and_count_eighty_one_weights():
    obs=np.array([0.2,-0.1,0.05]);z=np.linspace(-0.3,0.4,8)
    poly=polynomial_features(np.concatenate([obs,z]).reshape(1,11))
    q=m.q_features(obs,z,[0,1,2])
    assert poly.shape==(1,77) and q.shape==(3,80)
    assert np.allclose(q[:,:77],np.repeat(poly,3,axis=0))
    assert np.array_equal(q[:,77:],np.eye(3))
    model=m.PolynomialActionValueReadout.fit(q,[0.0,1.0,-1.0],ridge=1.0)
    assert model.weights.shape==(81,) and model.mean.shape==(80,)


def test_repeated_context_rows_are_not_counted_as_independent_labels():
    rng=np.random.default_rng(0)
    cells=[];context_by_task={}
    for t in range(8):
        cells.append(dict(decoder=0,task=t,obs=rng.normal(size=3).tolist(),returns=[float(t),float(t)+1,float(t)+2]))
        context_by_task[t]={name:rng.normal(size=8).tolist() for name in m.NAMES}
    x,y=m.source_training_arrays(0,cells,context_by_task)
    diag=m.design_diagnostics(x,y,ridge=1.0)
    assert x.shape==(144,80) and y.shape==(144,)
    assert diag['n_unique_labels']==24 and diag['n_unique_observations']==8
    assert diag['repeated_context_rows_not_independent'] is True
    assert diag['state_independent_action_ranking'] is True
    assert diag['action_dummies_sum_to_one'] is True
    assert diag['n_weights']==81 and diag['ridge']==1.0
    assert diag['augmented_rank']<81


def test_action_ranking_cannot_depend_on_state_under_additive_dummies():
    rng=np.random.default_rng(1)
    x=rng.normal(size=(144,80));x[:,77:]=np.eye(3)[np.tile(np.arange(3),48)]
    y=np.tile([0.0,2.0,-1.0],48)
    model=m.PolynomialActionValueReadout.fit(x,y,ridge=1.0)
    chosen=[]
    for _ in range(5):
        obs=rng.normal(size=3);z=rng.normal(size=8)
        chosen.append(int(np.argmax(model.predict(m.q_features(obs,z,[0,1,2])))))
    assert len(set(chosen))==1


def test_development_labels_cannot_change_a_frozen_source_fit():
    rng=np.random.default_rng(2)
    source_x=rng.normal(size=(144,80));source_x[:,77:]=np.eye(3)[np.tile(np.arange(3),48)]
    source_y=rng.normal(size=144)
    eval_x=rng.normal(size=(60,80));eval_x[:,77:]=np.eye(3)[np.tile(np.arange(3),20)]
    eval_y=rng.normal(size=60)+100
    frozen=m.PolynomialActionValueReadout.fit(source_x,source_y,ridge=1.0)
    mixed=m.PolynomialActionValueReadout.fit(np.vstack([source_x,eval_x]),np.concatenate([source_y,eval_y]),ridge=1.0)
    assert frozen.digest()!=mixed.digest()
    assert m.PolynomialActionValueReadout.fit(source_x,source_y,ridge=1.0).digest()==frozen.digest()


def test_ridge_is_prespecified_and_rejects_other_values():
    x=np.concatenate([np.zeros((3,77)),np.eye(3)],axis=1)
    with pytest.raises(ValueError,match='regularization'):
        m.PolynomialActionValueReadout.fit(x,[0.0,1.0,0.0],ridge=0.1)


def test_new_seeds_are_disjoint_from_closed_and_linear_q_blocks():
    cfg=m.load_config();m.check_seeds(cfg)
    blocked=set().union(*scalar.seed_sets(visited.load_config()),*scalar.seed_sets(scalar.load_config()),*m.seed_groups(linear_q.load_config()))
    used=set().union(*m.seed_groups(cfg))
    assert not (used & blocked)
    assert min(used)>=5000000
    assert 'action' not in m.source_future_seeds.__code__.co_varnames
    assert 'action' not in m.future_seeds.__code__.co_varnames


def test_candidate_seed_is_shared_across_scoring_rules():
    cfg=m.load_config();seed=m.candidate_seed(cfg,4,1,1)
    seq=m.candidate_sequences(seed)
    assert seq.shape==(16,16) and seed==m.candidate_seed(cfg,4,1,1)


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
    x=m.q_features(np.zeros(3),np.zeros(8),[0,1,2])
    readout=m.PolynomialActionValueReadout.fit(x,[0.0,0.0,0.0],ridge=1.0)
    seq=np.zeros((16,16),dtype=np.int64);seq[5,0]=1;seq[7,0]=1
    chosen=m.score_aligned(readout,np.zeros(3),np.zeros(8),seq)
    assert chosen['first_action']==0 and chosen['selected']==0
    class PreferActionOne:
        def predict(self,inputs):
            return np.asarray(inputs,dtype=np.float64)[:,78]*10.0
    chosen=m.score_aligned(PreferActionOne(),np.zeros(3),np.zeros(8),seq)
    assert chosen['first_action']==1 and chosen['selected']==5


def test_row_metrics_keep_h16_and_sequence_value_independent_of_q():
    seq=np.zeros((16,16),dtype=np.int64);seq[:,0]=np.arange(16)%3
    z=np.zeros(8);obs=np.zeros(3)
    inputs=np.concatenate([np.zeros((16,3)),np.repeat(z.reshape(1,8),16,axis=0)],axis=1)
    base=np.zeros(16);base[2]=10.0
    corrected=np.zeros(16);corrected[0]=10.0
    scores={name:dict(base=base.tolist(),corrected=corrected.tolist(),inputs=inputs.tolist()) for name in m.NAMES}
    q=m.PolynomialActionValueReadout.fit(m.q_features(obs,z,[0,1,2]),[0.0,5.0,0.0],ridge=1.0)
    other=m.PolynomialActionValueReadout.fit(m.q_features(obs,z,[0,1,2]),[5.0,0.0,0.0],ridge=1.0)
    student=m.row_metrics(scores,seq,[1.0,2.0,3.0],{name:q for name in m.NAMES},obs)['0']
    swapped=m.row_metrics(scores,seq,[1.0,2.0,3.0],{name:other for name in m.NAMES},obs)['0']
    assert student['h16_first']==swapped['h16_first']==3.0
    assert student['sequence_first']==swapped['sequence_first']==1.0
    assert student['aligned_first']==2.0 and swapped['aligned_first']==1.0
    assert student['gain_vs_h16']==-1.0


def test_budget_and_protocol_lock():
    cfg=m.load_config();counts=m.budget(cfg)
    assert counts['source_labels']+counts['collection']+counts['first_common']==29880
    assert counts['model_states']==7741440
    assert cfg['n_weights']==81 and cfg['n_poly']==77 and cfg['horizon']==16
    text=Path('docs/NEXUS_CAPACITY_MATCHED_Q_PROTOCOL.md').read_text()
    assert 'n_weights: 81' in text and 'authorized: false' in text
    assert 'score_correction_closes_if_gain_not_established: true' in text
    assert 'architecture_change_authorized: false' in text


def test_committed_allocation_is_unauthorized_and_blocks_execute():
    cfg=m.load_config();record=m.load_allocation()
    assert record['authorized'] is False and record['runs']==0
    remaining=json.loads(m.USAGE.read_text())['remaining_session_allowance_s']
    assert remaining<cfg['time_cap_s']
    with pytest.raises(PermissionError,match='fresh human approval'):
        m.require_allocation(cfg)


def test_missing_allocation_blocks_hash_load(monkeypatch,tmp_path):
    monkeypatch.setattr(m,'ALLOCATION',tmp_path/'missing.json')
    with pytest.raises((FileNotFoundError,ValueError,PermissionError)):
        m.load_allocation()


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
    assert features.shape==(144,80) and labels.shape==(144,)
    with pytest.raises(ValueError):
        m.source_training_arrays(0,cells+[extra],{t:z for t in range(8)})


def test_corrupted_fit_record_is_rejected():
    cfg=m.load_config()
    rng=np.random.default_rng(3)
    cells=[];context={}
    for t in range(8):
        cells.append(dict(decoder=0,task=t,obs=rng.normal(size=3).tolist(),returns=[0.0,1.0,-1.0]))
        context[t]={name:rng.normal(size=8).tolist() for name in m.NAMES}
    x,y=m.source_training_arrays(0,cells,context)
    model=m.PolynomialActionValueReadout.fit(x,y,ridge=1.0)
    stage=dict(complete=True,readouts={str(d):dict(state=model.state_dict(),sha256=model.digest(),rows=144,fit_rmse=0.0,diagnostics=m.design_diagnostics(x,y)) for d in range(10)})
    with pytest.raises(ValueError):
        m.validate_fit(stage,cfg,cells,{0:context})
    all_cells=[]
    contexts={}
    for d in range(10):
        contexts[d]={}
        for t in range(8):
            all_cells.append(dict(decoder=d,task=t,obs=cells[t]['obs'],returns=cells[t]['returns']))
            contexts[d][t]=context[t]
    x0,y0=m.source_training_arrays(0,all_cells,contexts[0])
    model=m.PolynomialActionValueReadout.fit(x0,y0,ridge=1.0)
    rmse=float(np.sqrt(np.mean((model.predict(x0)-y0)**2)))
    stage=dict(complete=True,readouts={str(d):dict(state=model.state_dict(),sha256=model.digest(),rows=144,fit_rmse=rmse,diagnostics=m.design_diagnostics(x0,y0)) for d in range(10)})
    assert m.validate_fit(stage,cfg,all_cells,contexts) is True
    bad=copy.deepcopy(stage);bad['readouts']['3']['sha256']='0'*64
    with pytest.raises(ValueError):
        m.validate_fit(bad,cfg,all_cells,contexts)


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
