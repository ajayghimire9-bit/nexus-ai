"""Synthetic evidence only: no new scores computed on research outcomes."""
import copy
import itertools
import numpy as np
import pytest
from nexus.world import visited_value_ranking as m


def scores(predicted,base=None,alive=None):
    p=np.asarray(predicted,dtype=float);b=np.zeros(16) if base is None else np.asarray(base,dtype=float);a=np.ones(16) if alive is None else np.asarray(alive,dtype=float)
    return dict(terminal=p.tolist(),base=b.tolist(),survival=a.tolist(),corrected=(b+a*p).tolist())


def test_perfect_tail_prediction_and_independent_return_identity():
    y=np.arange(16,dtype=float);r=m.metrics(np.zeros(16),y,scores(y),7.5)
    assert r['tail_mse']==r['tail_bias_sq']==r['tail_centered_mse']==0
    assert r['centered_benefit']==np.var(y)
    assert r['tail_pair_accuracy']==1 and r['return_gain']==15
    assert r['base_regret']-r['value_regret']==r['return_gain']


def test_bias_shift_keeps_centered_and_ordering_information():
    y=np.arange(16,dtype=float);a=m.metrics(np.zeros(16),y,scores(y),0.);b=m.metrics(np.zeros(16),y,scores(y+100),0.)
    assert b['tail_mse']==b['tail_bias_sq']==10000
    assert a['tail_centered_mse']==b['tail_centered_mse']==0
    assert a['tail_pair_accuracy']==b['tail_pair_accuracy']==1


def test_reversed_constant_and_flat_target_rankings_remain_finite():
    y=np.arange(16,dtype=float)
    assert m.pair_accuracy(-y,y)==(0.,0.)
    assert m.pair_accuracy(np.zeros(16),y)==(.5,0.)
    assert m.pair_accuracy(y,np.zeros(16))==(.5,1.)


def test_survival_weighted_constant_is_not_assumed_to_preserve_choice():
    base=np.zeros(16);base[0]=1.;alive=np.ones(16);alive[1]=0.
    r=m.metrics(np.zeros(16),np.arange(16,dtype=float),scores(np.zeros(16),base,alive),-100.)
    assert r['constant_changed']==1 and r['constant_return']==1


@pytest.mark.parametrize('bad',[True,'1',float('nan'),float('inf')])
def test_invalid_metric_inputs_rejected(bad):
    y=list(range(16));y[0]=bad
    with pytest.raises((ValueError,TypeError)):m.metrics(np.zeros(16),y,scores(np.zeros(16)),0.)


@pytest.fixture
def synthetic_rows():
    cfg=m.load_config();metric=m.metrics(np.zeros(16),np.arange(16),scores(np.arange(16)),0.)
    rows=[dict(decoder=d,task=t,visitor=v,metrics={s:dict(metric) for s in cfg['contexts']}) for d,t,v in itertools.product(cfg['decoders'],cfg['tasks'],cfg['visitors'])]
    return cfg,rows


def test_complete_grid_statistics_and_equal_visitor_weight(synthetic_rows):
    cfg,rows=synthetic_rows
    for row in rows:
        for r in row['metrics'].values():r['centered_benefit']=100. if row['visitor']==0 else -20.
    p=m.summarize(rows,cfg)
    assert p['groups']['pooled']['centered_benefit']['interval']['mean']==40.
    assert p['groups']['pooled']['centered_benefit']['interval']['n']==10


@pytest.mark.parametrize('missing',['decoder','task','visitor','context','metric','duplicate','boolean'])
def test_strict_completeness(synthetic_rows,missing):
    cfg,rows=synthetic_rows
    if missing=='decoder':rows=[r for r in rows if r['decoder']!=9]
    elif missing=='task':rows=[r for r in rows if r['task']!=2]
    elif missing=='visitor':rows=[r for r in rows if r['visitor']!=1]
    elif missing=='context':del rows[0]['metrics']['4']
    elif missing=='metric':del rows[0]['metrics']['zero']['tail_mse']
    elif missing=='duplicate':rows.append(copy.deepcopy(rows[0]))
    else:rows[0]['metrics']['zero']['tail_mse']=False
    with pytest.raises((ValueError,KeyError)):m.summarize(rows,cfg)


def test_source_constant_cannot_be_fit_to_query_labels():
    stage=dict(source_cells=[dict(decoder=0,task=t,traces=[dict(rewards=[-2.]*48) for _ in range(4)]) for t in range(8)])
    assert m.source_constant(stage,0)==-96.
    stage['source_cells'].pop()
    with pytest.raises(ValueError):m.source_constant(stage,0)


def test_research_actual_prefix_reference_is_separate_from_deployable_scores():
    prefix=np.arange(16)*100.;predicted=np.arange(16)[::-1].astype(float)
    r=m.metrics(prefix,np.zeros(16),scores(predicted),0.)
    assert r['value_return']==0 and r['actual_prefix_predicted_tail_return']==1500


def test_no_metric_can_silently_break_saved_gain16():
    row=dict(decoder=0,task=0,state=0,prefixes=[dict(rewards=[0.]*16) for _ in range(16)],block_tails=[dict(rewards=[0.]*48) for _ in range(16)],scores={'zero':scores(np.zeros(16))},metrics={'zero':dict(gain16=1.)})
    with pytest.raises(ValueError,match='gain16'):m.build_row(row,0.)


def test_source_validation_needs_no_environment_inference_or_binary_loading(monkeypatch):
    from nexus.world import visited_commitment as parent
    import nexus.tasks.spec as tasks
    import gymnasium
    def forbidden(*args,**kwargs):raise AssertionError('offline analysis cannot collect or load models')
    monkeypatch.setattr(tasks,'make_task_env',forbidden);monkeypatch.setattr(gymnasium,'make',forbidden)
    monkeypatch.setattr(parent.prior,'load_models',forbidden);monkeypatch.setattr(parent.prior,'verify_inputs',forbidden)
    capture,stage=m.inputs(m.load_config())
    assert len(capture['cells'])==60 and stage['complete'] is True


def test_missing_allocation_rejected_before_source_analysis(monkeypatch,tmp_path):
    monkeypatch.setattr(m,'ALLOCATION',tmp_path/'missing.json')
    with pytest.raises((FileNotFoundError,PermissionError)):m.require_allocation(m.load_config())
