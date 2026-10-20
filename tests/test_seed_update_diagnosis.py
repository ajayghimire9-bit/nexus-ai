"""Toy residual math and source-boundary tests; no experimental outcomes."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
import torch

from nexus.seed import learning_benchmark as lb
from nexus.seed.plasticity import PlasticityController
from nexus.seed.update_diagnosis import config_check, source_pack, trajectory, summarize, validate

ROOT=Path(__file__).resolve().parents[1]


def config():return json.loads((ROOT/'configs/seed_update_diagnosis.json').read_text())


def toy():
    g=torch.Generator().manual_seed(21)
    x=torch.randn(66,33,generator=g)/33**.5;w=torch.randn(33,generator=g);y=x@w
    return lb.LessonTask(x[:8],y[:8],x[12:39],y[12:39],x[8:12],y[8:12],x[39:],y[39:])


@pytest.mark.parametrize('method',['learned','static','fixed','replay','none'])
def test_trace_exactly_matches_existing_inner_rule_and_freezes_weights(method):
    task=toy();m=PlasticityController(33);before=deepcopy(m.state_dict())
    trace=trajectory(task,m,method)
    old,snaps=lb.curve(task,m,'learned' if method=='static' else method)
    for budget,error,forget in old:
        assert torch.equal(torch.tensor(trace[budget]['theta']),snaps[budget])
        assert trace[budget]['query_mse']==float(error.detach())
    assert all(torch.equal(v,m.state_dict()[k]) for k,v in before.items())


def test_query_changes_never_change_corrections_and_later_labels_do_not_change_prefix():
    task=toy();m=PlasticityController(33);first=trajectory(task,m,'learned')
    changed=deepcopy(task);object.__setattr__(changed,'query_y',task.query_y+100)
    second=trajectory(changed,m,'learned')
    assert [r['theta'] for r in first]==[r['theta'] for r in second]
    assert first[1]['query_mse']!=second[1]['query_mse']
    labels=task.support_y.clone();labels[4:]+=10
    object.__setattr__(changed,'support_y',labels)
    third=trajectory(changed,m,'learned')
    assert [r['theta'] for r in first[:5]]==[r['theta'] for r in third[:5]]
    assert first[8]['theta']!=third[8]['theta']


def test_host_extracts_source_arrays_only_and_rejects_bad_hash(tmp_path):
    c=config();pack=source_pack(ROOT,c)
    assert set(pack)=={'scale','tasks','controllers'}
    assert [t['seed'] for t in pack['tasks']]==c['tasks']['train']
    assert set(pack['tasks'][0])=={'seed','arrays','array_sha256'}
    assert not {'audit','development','control','records','repository'} & set(pack)
    bad=deepcopy(c);bad['input_sha256']='0'*64
    with pytest.raises(ValueError,match='source_artifact_hash'):source_pack(ROOT,bad)


def fixture_grid():
    c=config();base=trajectory(toy(),None,'fixed')
    rows={str(s):{str(t):{m:deepcopy(base) for m in c['methods']} for t in c['tasks']['train']} for s in c['outer_seeds']}
    return c,dict(config=c,rows=rows,frozen_controllers=True,source_only=True,analysis=summarize(rows,c))


@pytest.mark.parametrize('fault',['seed','task','method','prefix','nan','bool','string','support'])
def test_complete_grid_and_finite_metric_rejection(fault):
    c,r=fixture_grid();assert validate(r,c)
    task=r['rows']['6401']['95000000'];row=task['learned'][1]
    if fault=='seed':del r['rows']['6401']
    elif fault=='task':del r['rows']['6401']['95000000']
    elif fault=='method':del task['learned']
    elif fault=='prefix':task['learned'].pop()
    elif fault=='nan':row['query_mse']=float('nan')
    elif fault=='bool':row['query_mse']=True
    elif fault=='string':row['query_mse']='0.2'
    else:row['support_error_after']=None
    with pytest.raises(ValueError):validate(r,c)


def test_locked_grid_and_zero_new_collection_bounds():
    c=config();assert config_check(c)==dict(real_steps=0,imagined_transitions=0,outer_updates=0)
    c['tasks']['train'].pop()
    with pytest.raises(ValueError):config_check(c)
