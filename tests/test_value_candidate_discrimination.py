"""Recorded-data analysis fixtures; no new simulator trajectories."""
import copy
import itertools
import json

import numpy as np
import pytest
from nexus.world import value_candidate_discrimination as module
from nexus.world.terminal_value import NAMES,TerminalReadout


def toy():
    indices=[0,4,8,12];x=np.zeros((16,11)).tolist();base=[-1e6]*16;terminal=[-100.]*16
    for i,b,p in zip(indices,[0.,0.,1.,2.],[-100.,-101.,-102.,-103.]):base[i]=b;terminal[i]=p
    prefix=dict(rollouts=[dict(rewards=[0.]*16) for _ in range(4)])
    cal=dict(targets=[-104.,-103.,-102.,-101.],inputs={n:dict(imagined=[x[i] for i in indices]) for n in NAMES},predictions={n:dict(imagined=[terminal[i] for i in indices],constant=[-100.]*4) for n in NAMES})
    scores={n:dict(base=base.copy(),terminal=terminal.copy(),survival=[1.]*16,corrected=(np.array(base)+terminal).tolist(),inputs=copy.deepcopy(x)) for n in NAMES}
    return prefix,cal,scores,indices


def test_good_absolute_prediction_can_still_reverse_action_ranking():
    prefix,cal,scores,indices=toy();m=module.cell_metrics(prefix,cal,scores,indices)['0']
    assert m['tail_mse']==6 and m['tail_bias_sq']==1 and m['tail_centered_mse']==5
    assert m['constant_centered_mse']==1.25 and m['tail_centered_gain']==-3.75
    assert m['base_return']==-101 and m['value_return']==-104 and m['benefit']==-3
    assert m['value_regret']-m['base_regret']==-m['benefit']
    assert m['base_best']==1 and m['value_best']==0


def test_shared_source_constant_and_survival_correction():
    prefix,cal,scores,indices=toy()
    # Negative constant can change ranking when survival differs. It is not
    # silently assumed to be an identical action-independent additive offset.
    for score in scores.values():
        score['survival'][indices[-1]]=0.
        score['corrected']=(np.array(score['base'])+np.array(score['survival'])*score['terminal']).tolist()
    m=module.cell_metrics(prefix,cal,scores,indices)['zero']
    assert m['constant_return']==-101
    assert m['value_return']==-101


def test_full_prefix_plus_tail_endpoint_accounting_and_tie_rule():
    prefix,cal,scores,indices=toy()
    prefix['rollouts'][0]['rewards']=[-1.]*16
    for s in scores.values():
        s['base']=[0.]*16;s['terminal']=[0.]*16;s['corrected']=[0.]*16
    m=module.cell_metrics(prefix,cal,scores,indices)['0']
    assert m['base_return']==-120 and m['value_return']==-120
    assert m['actual16_return']==-103 # actual16 ties indices4,8,12; first is4


def test_labels_cannot_mutate_saved_model_scores():
    prefix,cal,scores,indices=toy();saved=copy.deepcopy(scores)
    module.cell_metrics(prefix,cal,scores,indices)
    cal['targets']=[-900.,-500.,-300.,-50.]
    module.cell_metrics(prefix,cal,scores,indices)
    assert scores==saved


def rows():
    prefix,cal,scores,indices=toy();metrics=module.cell_metrics(prefix,cal,scores,indices)
    return [dict(decoder=d,task=t,metrics=copy.deepcopy(metrics)) for d,t in itertools.product(range(10),range(11))]


def test_aggregation_uses_ten_decoders_not_student_or_task_replicates():
    cfg,_,_,_=module.inputs();result=module.summarize(rows(),cfg)
    ci=result['summaries']['development']['metrics']['benefit']['interval']
    assert ci['n']==10 and ci['df']==9 and ci['mean']==ci['lo']==ci['hi']==-3
    assert result['label']=='exploratory_in_set_harm'


@pytest.mark.parametrize('axis,value',[('decoder',9),('task',10)])
def test_missing_planned_grid_axis_rejected(axis,value):
    cfg,_,_,_=module.inputs()
    with pytest.raises(ValueError):module.summarize([r for r in rows() if r[axis]!=value],cfg)


@pytest.mark.parametrize('bad',[True,'1',float('nan'),float('inf')])
def test_nonfinite_or_wrong_numeric_types_fail(bad):
    cfg,_,_,_=module.inputs();r=rows();r[0]['metrics']['0']['benefit']=bad
    with pytest.raises(ValueError):module.summarize(r,cfg)


def test_missing_condition_and_metric_rejected():
    cfg,_,_,_=module.inputs()
    for condition in ('context','metric'):
        r=rows()
        if condition=='context':del r[0]['metrics']['zero']
        else:del r[0]['metrics']['0']['benefit']
        with pytest.raises(ValueError):module.summarize(r,cfg)


def test_prepare_cannot_collect_or_fit(monkeypatch):
    import nexus.world.terminal_value_calibration as cal
    import nexus.world.terminal_value_execution as previous
    def forbidden(*args,**kwargs):raise AssertionError('no new environment/fitting allowed')
    monkeypatch.setattr(cal,'make_task_env',forbidden);monkeypatch.setattr(previous,'make_task_env',forbidden)
    monkeypatch.setattr(TerminalReadout,'fit',forbidden)
    p=module.prepare();assert p['new_environment_steps']==0 and p['model_cap']==337920


def test_environment_instrumentation_fails_closed():
    cfg,_,_,_=module.inputs();meter=module.InferenceMeter(cfg)
    with pytest.raises(RuntimeError):meter.instrument_env(None)
    meter.deadline=0
    with pytest.raises(TimeoutError):meter.check()


def test_replay_corruption_rejected():
    prefix,cal,scores,indices=toy()
    scores['0']['inputs'][0][0]=1.
    with pytest.raises(ValueError):module.cell_metrics(prefix,cal,scores,indices)


def test_recorded_complete_replay_validates_without_checkpoint_loading(monkeypatch):
    import nexus.world.checkpoint_integrity as integrity
    def forbidden():raise AssertionError('repository-only result test cannot require .pt files')
    monkeypatch.setattr(integrity,'verify_checkpoint_integrity',forbidden)
    cfg,parent,stage,capture=module.inputs();p=json.loads(module.OUTPUT.read_text())
    assert p['complete'] is True and p['source_dirty'] is False
    result=module.validate_result(p,cfg,parent,stage,capture)
    ci=result['summaries']['development']['metrics']['benefit']['interval']
    assert result['label']=='exploratory_in_set_gain' and ci['mean']==pytest.approx(24.030169236506037)
    assert p['model_states']==337920 and p['new_environment_steps']==0
