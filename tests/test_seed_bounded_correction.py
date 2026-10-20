"""Toy checks only; no source comparison or environment execution."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
import torch

from nexus.evolution1.catalogue import digest
from nexus.seed import learning_benchmark as lb,update_diagnosis as prior
from nexus.seed.plasticity import PlasticityController
from nexus.seed.bounded_correction import BOUNDED,METHODS,bounded_delta,limiter,config_check,source_pack,summarize,validate

ROOT=Path(__file__).resolve().parents[1]


def config():return json.loads((ROOT/'configs/seed_bounded_correction.json').read_text())


def toy():
    g=torch.Generator().manual_seed(81)
    x=torch.randn(66,33,generator=g)/33**.5;w=torch.randn(33,generator=g);y=x@w
    return lb.LessonTask(x[:8],y[:8],x[12:39],y[12:39],x[8:12],y[8:12],x[39:],y[39:])


def test_bound_is_exact_on_observed_design_and_preserves_direction():
    theta=torch.tensor([1.,2.]);candidate=torch.tensor([4.,6.]);design=torch.eye(2)
    result,info=bounded_delta(theta,candidate,design,.2)
    assert info['alpha']==pytest.approx(.2/(25/2)**.5)
    assert torch.allclose(result-theta,info['alpha']*(candidate-theta))
    assert info['actual_rms']==pytest.approx(.2,abs=1e-6)
    inside,record=bounded_delta(theta,candidate,design,10)
    assert torch.equal(inside,candidate) and record['alpha']==1
    zero,record=bounded_delta(theta,theta,design,.2)
    assert torch.equal(zero,theta) and record['alpha']==1
    for bad in (0,-1,float('nan'),True):
        with pytest.raises(ValueError):bounded_delta(theta,candidate,design,bad)


def test_query_and_future_rows_cannot_change_limiter_or_weights():
    task=toy();m=PlasticityController(33);before=deepcopy(m.state_dict());logs=[]
    a=prior.trajectory(task,m,'learned',update_fn=limiter(.1,logs))
    changed=deepcopy(task)
    object.__setattr__(changed,'query_y',task.query_y+100)
    object.__setattr__(changed,'query_x',task.query_x*100)
    labels=task.support_y.clone();labels[4:]+=10
    object.__setattr__(changed,'support_y',labels)
    b=prior.trajectory(changed,m,'learned',update_fn=limiter(.1,[]))
    assert [v['theta'] for v in a[:5]]==[v['theta'] for v in b[:5]]
    assert a[-1]['theta']!=b[-1]['theta']
    assert [v['design_rows'] for v in logs]==list(range(5,13))
    assert all(v['actual_rms']<=.1+2e-6 for v in logs)
    assert all(torch.equal(v,m.state_dict()[k]) for k,v in before.items())


def test_cached_pack_is_exact_source_only_and_wrong_provenance_fails():
    c=config();p=source_pack(ROOT,c)
    assert set(p)=={'data','cached_rows'}
    assert set(p['data'])=={'scale','tasks','controllers'}
    assert len(p['data']['tasks'])==12
    c['baseline_sha256']='0'*64
    with pytest.raises(ValueError,match='provenance'):source_pack(ROOT,c)


def fixture():
    c=config();task=toy();m=PlasticityController(33)
    arrays={k:getattr(task,k).tolist() for k in task.__dataclass_fields__}
    data=dict(scale=[1.]*33,tasks=[dict(seed=t,arrays=arrays) for t in c['tasks']['train']],controllers=[])
    reference={method:prior.trajectory(task,m if method in ('learned','static') else None,method) for method in prior.METHODS}
    rms=float((task.support_y-task.support_x@lb.initial(task)).square().mean().sqrt());tau=max(1e-6,.25*rms)
    all_rows=deepcopy(reference);logs={}
    for method in BOUNDED:
        base=method.removesuffix('_bounded');log=[]
        all_rows[method]=prior.trajectory(task,m if base!='fixed' else None,base,update_fn=limiter(tau,log));logs[method]=log
    cached={str(s):{str(t):deepcopy(reference) for t in c['tasks']['train']} for s in c['outer_seeds']}
    rows={str(s):{str(t):deepcopy(all_rows) for t in c['tasks']['train']} for s in c['outer_seeds']}
    limits={str(s):{str(t):deepcopy(logs) for t in c['tasks']['train']} for s in c['outer_seeds']}
    pack=dict(data=data,cached_rows=cached)
    r=dict(config=c,rows=rows,limit_trace=limits,tau=tau,source_residual_rms=rms,
           source_only=True,frozen_controllers=True,source_pack_sha256=digest(pack),analysis=summarize(rows,limits,c))
    return c,r,pack


@pytest.mark.parametrize('fault',['seed','task','method','prefix','nan','boolean','cache','bound','summary','initial','scale'])
def test_complete_grid_bounds_and_cache_integrity(fault):
    c,r,p=fixture();assert validate(r,c,p)
    task=r['rows']['6401']['95000000'];row=task['learned_bounded'][1]
    if fault=='seed':del r['rows']['6401']
    elif fault=='task':del r['rows']['6401']['95000000']
    elif fault=='method':del task['learned_bounded']
    elif fault=='prefix':task['learned_bounded'].pop()
    elif fault=='nan':row['query_mse']=float('nan')
    elif fault=='boolean':row['query_mse']=True
    elif fault=='cache':task['replay'][1]['update_l2']+=1
    elif fault=='bound':r['limit_trace']['6401']['95000000']['learned_bounded'][0]['actual_rms']+=1
    elif fault=='summary':r['analysis']['advance_source_screen']=not r['analysis']['advance_source_screen']
    elif fault=='initial':task['fixed_bounded'][0]['theta'][0]+=1
    else:r['source_residual_rms']*=2;r['tau']*=2
    with pytest.raises(ValueError):validate(r,c,p)


def test_locked_rule_and_declared_work_arithmetic():
    c=config();assert config_check(c)==dict(real_steps=0,imagined_transitions=0,outer_updates=0)
    n=len(c['outer_seeds'])*len(c['tasks']['train'])*len(BOUNDED)
    assert n*8==864 and n*9==972 and n*sum(range(5,13))==7344
    assert n*9*27==26244
    assert len(c['outer_seeds'])*len(c['tasks']['train'])*len(METHODS)*9==2592
    c['bound_fraction']=.5
    with pytest.raises(ValueError):config_check(c)
