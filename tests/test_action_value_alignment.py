"""Synthetic objective mismatch, coverage, ties and strict aggregation."""
import copy
import itertools
import numpy as np
import pytest
from nexus.world import action_value_alignment as m


def sequences():return np.asarray([[i%3]*16 for i in range(16)],dtype=np.int64).tolist()


def test_known_sequence_optimum_can_have_bad_replanning_first_action():
    q=[100.]+[0.]*15;p=m.state_values(sequences(),q,[0.,10.,5.])
    assert p['selected_sequence']==p['selected_first_action']==0
    assert p['metrics']['total_regret']==p['metrics']['represented_regret']==10.
    assert p['metrics']['coverage_gap']==0 and p['best_first_action']==1


def test_aligned_and_flat_cases():
    q=[0.,100.]+[0.]*14;p=m.state_values(sequences(),q,[0.,10.,5.]);assert p['metrics']['total_regret']==0
    flat=m.state_values(sequences(),[1.]*16,[2.]*3)
    assert flat['selected_sequence']==flat['best_first_action']==0
    assert flat['metrics']['optimal_first_action']==1


def test_missing_actions_are_coverage_not_ranking_error():
    p=m.state_values([[0]*16]*16,list(range(16)),[0.,10.,20.])
    assert p['metrics']['total_regret']==p['metrics']['coverage_gap']==20
    assert p['metrics']['represented_regret']==0 and p['metrics']['all_actions_represented']==0


def test_exact_tie_break_cannot_choose_best_first_action_posthoc():
    q=[1.]*16;p=m.state_values(sequences(),q,[0.,1.,2.])
    assert p['selected_sequence']==0 and p['metrics']['total_regret']==2.


@pytest.mark.parametrize('bad',[True,'1',float('nan'),float('inf')])
def test_invalid_reward_types_rejected(bad):
    q=[0.]*16;q[0]=bad
    with pytest.raises(ValueError):m.state_values(sequences(),q,[0.,1.,2.])


@pytest.fixture
def fake_grid():
    cfg=m.load_config();rows=[]
    for d,t,v in itertools.product(cfg['decoders'],cfg['tasks'],cfg['visitors']):
        geometry=m.state_values(sequences(),[100.]+[0.]*15,[0.,10.,5.])
        refs={s:{k:0. for k in m.REFERENCE_METRICS} for s in cfg['contexts']}
        rows.append(dict(decoder=d,task=t,visitor=v,geometry=geometry,references=refs))
    return cfg,rows


def test_primary_is_not_repeated_over_students_and_equal_visitors(fake_grid):
    cfg,rows=fake_grid
    for row in rows:
        row['geometry']['metrics']['total_regret']=100. if row['visitor']==0 else 0.
        row['geometry']['metrics']['represented_regret']=row['geometry']['metrics']['total_regret']
        for refs in row['references'].values():
            for k in refs:refs[k]=100000.
    p=m.summarize(rows,cfg)
    assert p['groups']['pooled']['state']['total_regret']['interval']['mean']==50.
    assert p['groups']['pooled']['state']['total_regret']['interval']['n']==10
    assert p['label']=='sequence_first_action_misalignment_detected'


def test_coverage_only_cannot_be_called_sequence_ranking_misalignment(fake_grid):
    cfg,rows=fake_grid
    for row in rows:row['geometry']=m.state_values([[0]*16]*16,list(range(16)),[0.,10.,20.])
    assert m.summarize(rows,cfg)['label']=='first_action_gap_with_coverage_or_uncertainty'


@pytest.mark.parametrize('missing',['decoder','task','visitor','context','state_metric','reference_metric','duplicate','boolean','boolean_index'])
def test_completeness_and_type_guards(fake_grid,missing):
    cfg,rows=fake_grid
    if missing=='decoder':rows=[r for r in rows if r['decoder']!=9]
    elif missing=='task':rows=[r for r in rows if r['task']!=2]
    elif missing=='visitor':rows=[r for r in rows if r['visitor']!=1]
    elif missing=='context':del rows[0]['references']['4']
    elif missing=='state_metric':del rows[0]['geometry']['metrics']['coverage_gap']
    elif missing=='reference_metric':del rows[0]['references']['zero']['base_first_regret']
    elif missing=='duplicate':rows.append(copy.deepcopy(rows[0]))
    elif missing=='boolean_index':rows[0]['geometry']['selected_sequence']=False
    else:rows[0]['geometry']['metrics']['total_regret']=False
    with pytest.raises((ValueError,KeyError)):m.summarize(rows,cfg)


def test_source_validation_has_no_environment_or_world_model_loading(monkeypatch):
    import nexus.tasks.spec as tasks
    def forbidden(*args,**kwargs):raise AssertionError('offline only')
    monkeypatch.setattr(tasks,'make_task_env',forbidden);monkeypatch.setattr(m.source.visited.prior,'load_models',forbidden)
    source,stage=m.inputs();assert len(source['cells'])==60 and stage['complete'] is True


def test_missing_allocation_prevents_calculation(monkeypatch,tmp_path):
    monkeypatch.setattr(m,'ALLOCATION',tmp_path/'missing.json')
    with pytest.raises((FileNotFoundError,PermissionError)):m.require_allocation(m.load_config())
