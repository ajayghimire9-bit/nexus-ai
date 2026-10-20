"""Source-only toy regression and boundary tests; no scientific collection."""
from copy import deepcopy
import json
from pathlib import Path
import torch
import pytest
from nexus.seed import learning_benchmark as lb
from nexus.seed.nonlinear_learning import controller,fit_source,evaluate,Meter,fresh_world
from nexus.seed.nonlinear_learning_audit import bound,config_check,interval,complete_grid
from nexus.seed.action_readout import ActionReadout
from nexus.seed.experimental import Sandbox,digest

ROOT=Path(__file__).resolve().parents[1]


def config():return json.loads((ROOT/'configs/seed_nonlinear_learning.json').read_text())


def toy(seed=7):
    g=torch.Generator().manual_seed(seed);x=torch.randn(66,33,generator=g);w=torch.randn(33,generator=g)
    x=x/lb.scale_features(x[:12]);y=x@w
    return lb.LessonTask(x[:8],y[:8],x[12:39],y[12:39],x[8:12],y[8:12],x[39:],y[39:])


def test_source_learning_gradients_updates_and_static_context_invariance():
    c=config();c['meta_updates']=4
    tasks=[toy(),toy(8)];m,a=fit_source(tasks,6401,False,c,lambda:None)
    static,b=fit_source(tasks,6401,True,c,lambda:None)
    assert a['parameter_change_l2']>0 and b['parameter_change_l2']>0
    assert all(r['gradient_norm']>0 for r in a['training'])
    assert a['source_schedule_sha256']==b['source_schedule_sha256']
    assert torch.equal(static(torch.zeros(4)),static(torch.ones(4)))
    assert not torch.equal(m(torch.zeros(4)),m(torch.ones(4)))
    assert torch.equal(static.logits.weight,torch.zeros_like(static.logits.weight))
    again,logs=fit_source(tasks,6401,False,c,lambda:None)
    assert all(torch.equal(v,again.state_dict()[k]) for k,v in m.state_dict().items())
    assert a['training']==logs['training']


def test_nested_budgets_inner_query_isolation_and_no_adaptation():
    t=toy();m=controller(6401);first,snaps=lb.curve(t,m,'learned')
    changed=deepcopy(t);object.__setattr__(changed,'query_y',t.query_y+999)
    other,alternative=lb.curve(changed,m,'learned')
    assert [v[0] for v in first]==[1,2,4,8]
    assert all(torch.equal(v,alternative[k]) for k,v in snaps.items())
    assert not torch.equal(first[-1][1],other[-1][1])
    _,none=lb.curve(t,None,'none');assert torch.equal(none[1],none[8])


def test_scaling_uses_source_support_old_not_query_or_retention():
    t=toy();scale=lb.scale_features(torch.cat((t.support_x,t.old_x)))
    changed=deepcopy(t);object.__setattr__(changed,'query_x',t.query_x*999)
    assert torch.equal(scale,lb.scale_features(torch.cat((changed.support_x,changed.old_x))))


def test_frozen_nonlinear_readout_inspection_is_side_effect_free():
    torch.manual_seed(3);head=ActionReadout();x=torch.randn(9,34);before={k:v.clone() for k,v in head.state_dict().items()}
    features=head.adaptation_features(x);features2=head.adaptation_features(x)
    assert features.shape==(9,33) and not features.requires_grad and torch.equal(features,features2)
    assert all(torch.equal(v,head.state_dict()[k]) for k,v in before.items())


def test_exact_registered_resource_bound_and_task_goal_separation():
    c=config();assert config_check(c)==dict(real_steps=7984,imagined_transitions=68208,posterior_rows=6192,outer_updates=384)
    seeds=[s for v in c['tasks'].values() for s in v['seeds']]
    assert len(seeds)==len(set(seeds))==24
    for old in ('seed_learning_validation','seed_spatial_transfer','seed_surprise_readout'):
        prior=(ROOT/'configs'/f'{old}.json').read_text()
        assert not any(str(s) in prior for s in seeds)
    modified=deepcopy(c);modified['max_authored_steps']=7983
    with pytest.raises(ValueError,match='bounds'):config_check(modified)


def test_meter_reserves_before_next_interaction_or_forward():
    c=config();c['max_authored_steps']=1;c['max_imagined_transitions']=9
    m=Meter(c);m.charge('collection');m.model(9)
    with pytest.raises(ValueError,match='real_cap'):m.charge('collection')
    with pytest.raises(ValueError,match='imagined_cap'):m.model(1)
    assert sum(m.costs.values())==1 and m.imagined==9


def test_fresh_state_rejection_is_deterministic_and_outcome_independent():
    used=set();a=fresh_world(7,[2,2],0,used)
    b=fresh_world(7,[2,2],0,set());assert a.obj==b.obj
    other=fresh_world(7,[2,2],0,used);assert other.obj!=a.obj
    assert len(used)==2


def test_task_level_intervals_not_outer_seed_or_episode_replications():
    values=[1,2,3,4,5,6,7,8];v=interval(values)
    assert v['mean']==4.5 and v['ci95'][0]==pytest.approx(4.5-2.364624251*torch.tensor(values,dtype=torch.float64).std().item()/8**.5)
    for wrong in (values[:-1],values+[9],[float('nan')]*8,[True]*8):
        with pytest.raises(ValueError):interval(wrong)


def test_study_host_rejects_changed_protocol_before_dispatch(tmp_path):
    host=Sandbox(ROOT,tmp_path/'host');c=config()
    host.grant('tiny','unit test','source-only boundary test',dict(wall_s=180,cpu_s=180,memory_mb=2048,real_steps=12000,imagined_transitions=100000,updates=384),3600,c['carried_used_s'],memory_policy='sampled_rss')
    s=dict(id='test',mode='exploration',recipe=dict(adapter='seed_nonlinear_learning_v1',config_path='configs/seed_nonlinear_learning.json',config_sha256='0'*64,protocol_path='docs/NEXUS_SEED_NONLINEAR_LEARNING_PROTOCOL.md',protocol_sha256='0'*64),train=None,development=None,model_run=None,assessment=None,protocol=None,gate=None)
    with pytest.raises(ValueError,match='registration_hash'):host.execute(s,'tiny')
    assert not host.records('reserved')


@pytest.mark.parametrize('removed',['seed','task','method','budget','duplicate_seed'])
def test_missing_planned_cells_cannot_shrink_expected_grid(removed):
    c=config();r=dict(tasks={k:[dict(seed=s) for s in p['seeds']] for k,p in c['tasks'].items()},
        controllers=[dict(seed=s) for s in c['outer_seeds']],
        curves={role:{str(s):{str(t):{m:[dict(budget=b) for b in c['budgets']] for m in c['methods']}
            for t in c['tasks'][role]['seeds']} for s in c['outer_seeds']} for role in ('development','audit')})
    assert complete_grid(r,c)
    cells=r['curves']['audit'];first=cells['6401'];methods=first[str(c['tasks']['audit']['seeds'][0])]
    if removed=='seed':del cells['6401']
    elif removed=='task':first.pop(str(c['tasks']['audit']['seeds'][0]))
    elif removed=='method':del methods['replay']
    elif removed=='budget':methods['learned'].pop()
    else:r['controllers'].append(r['controllers'][0])
    with pytest.raises(ValueError):complete_grid(r,c)
