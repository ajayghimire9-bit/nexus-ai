"""Synthetic active-query contracts only; no scientific collection or fitting."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
import torch
from nexus.evolution1.catalogue import digest
from nexus.seed import question_selection as qs
from nexus.seed import sequential_consistency as seq
from nexus.seed import cumulative_learning as cum
from nexus.seed.update_diagnosis import trajectory
from test_seed_cumulative_learning import toy
from test_seed_sequential_consistency import synthetic_pack

ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/seed_question_selection.json').read_text())


def test_variance_matches_primal_covariance_and_redundancy_matters():
    pool=torch.tensor([[1.,0.],[0.,1.],[1.,1.],[.5,0.]],dtype=torch.float64)
    anchors=torch.tensor([[1.,0.]],dtype=torch.float64)
    scores=qs.variance_scores(pool,anchors,[])
    cov=torch.linalg.inv(.1*torch.eye(2,dtype=torch.float64)+anchors.T@anchors)
    assert scores==pytest.approx(torch.einsum('nd,df,nf->n',pool,cov,pool).tolist(),abs=1e-7)
    assert scores[1]>scores[0] and qs.variance_scores(pool,anchors,[1])[1]<scores[1]


def test_oracle_only_reveals_requested_labels_and_counts_duplicates():
    oracle=qs.LabelOracle([2.,3.,4.],2)
    assert oracle.reveal(2)==4. and oracle.revealed==[2]
    with pytest.raises(ValueError):oracle.reveal(2)
    assert oracle.reveal(0)==2.
    with pytest.raises(ValueError):oracle.reveal(1)
    with pytest.raises(ValueError):qs.LabelOracle([1.],True)
    with pytest.raises(ValueError):qs.LabelOracle([1.],0).reveal(0)


def test_orders_are_input_only_unique_deterministic_and_rng_isolated():
    t=toy();a=qs.orders(t.support_x,t.old_x,95000000,config())
    torch.rand(91);b=qs.orders(t.support_x,t.old_x,95000000,config())
    assert a==b
    assert len({tuple(x['indices']) for x in a['random'].values()})>1
    assert all(sorted(x['indices'])==list(range(8)) for method in a.values() for x in method.values())
    assert qs.variance_scores(torch.eye(3),torch.zeros(1,3),[])==[10.]*3


def test_fixed_learner_is_identical_to_previous_constant_damping():
    t=toy();meta={'constants':{'x':{'weights':{'logits.bias':[.2]}}}};g=float(.5+.25*torch.tensor(.2))
    a=qs.fit_path(t.support_x,t.old_x,t.old_y,qs.LabelOracle(t.support_y.tolist(),8),list(range(8)),g)
    b=trajectory(t,None,'fixed',update_fn=seq.updater('constant_damping',meta,'x',[]))
    assert [x['theta'] for x in a]==[x['theta'] for x in b]
    assert a[0]['theta']!=a[-1]['theta']


def test_future_and_query_outcomes_cannot_change_question_or_fit_prefix():
    t=toy();order=qs.orders(t.support_x,t.old_x,95000000,config())['informative']['fixed']['indices']
    a=qs.fit_path(t.support_x,t.old_x,t.old_y,qs.LabelOracle(t.support_y.tolist(),8),order,.5)
    labels=t.support_y.clone();labels[order[4:]]+=50
    b=qs.fit_path(t.support_x,t.old_x,t.old_y,qs.LabelOracle(labels.tolist(),8),order,.5)
    assert a[:5]==b[:5] and a[-1]['theta']!=b[-1]['theta']
    before=deepcopy(a)
    first=qs.assess(deepcopy(a),t.query_x,t.query_y,t.retention_x,t.retention_y)
    second=qs.assess(deepcopy(a),t.query_x,t.query_y+999,t.retention_x,t.retention_y-999)
    assert a==before and [r['theta'] for r in first]==[r['theta'] for r in second]
    assert first[8]['query_mse']!=second[8]['query_mse']
    import inspect
    assert list(inspect.signature(qs.orders).parameters)==['pool','anchors','task_id','c','check']
    assert 'query' not in inspect.signature(qs.fit_path).parameters


def test_same_all_eight_labels_yield_same_cumulative_proposal_not_same_damping_path():
    t=toy();a=list(range(8));b=list(reversed(a))
    fit=lambda order:qs.fit_path(t.support_x,t.old_x,t.old_y,qs.LabelOracle(t.support_y.tolist(),8),order,.5)
    x,y=fit(a),fit(b)
    assert torch.allclose(torch.tensor(x[-1]['proposal']),torch.tensor(y[-1]['proposal']),atol=2e-6,rtol=0)
    assert x[-1]['theta']!=y[-1]['theta']


def test_zero_budget_and_snapshot_immutability():
    t=toy();a=qs.fit_path(t.support_x,t.old_x,t.old_y,qs.LabelOracle(t.support_y.tolist(),8),list(range(8)),.5)
    b=qs.fit_path(t.support_x,t.old_x,t.old_y,qs.LabelOracle(t.support_y.tolist(),8),list(range(8)),.5)
    assert a==b and all(torch.isfinite(torch.tensor(r['theta'])).all() for r in a)
    old=list(a[0]['theta']);a[-1]['theta'][0]+=99;assert a[0]['theta']==old


@pytest.fixture(scope='module')
def question_pack(synthetic_pack):
    source=deepcopy(synthetic_pack)
    for t in source['tasks']:t['array_sha256']=digest(t['arrays'])
    for meta in source['frozen_folds'].values():
        meta['source_sha256']=digest([t for t in source['tasks'] if t['seed'] in meta['train_ids']])
        for info in meta['constants'].values():
            info['provenance']['source_sha256']=meta['source_sha256']
            raw=json.dumps(dict(schema='seed_plasticity_v1',width=1,provenance=info['provenance'],weights=info['weights']),allow_nan=False).encode()
            info['sha256']=hashlib.sha256(raw).hexdigest()
    p=dict(source=source,parent_config=json.loads((ROOT/'configs/seed_sequential_consistency.json').read_text()),parent_sha256=config()['parent_sha256'])
    assert qs.validate_pack(p,config());return p


@pytest.fixture(scope='module')
def question_result(question_pack,tmp_path_factory):
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from nexus.seed.question_selection import run;print(json.dumps(run(json.load(sys.stdin)),allow_nan=False))'
    proc=subprocess.run([sys.executable,'-c',code,str(ROOT/'src')],input=json.dumps(dict(inputs=dict(study_config=config(),source_pack=question_pack))),
        text=True,capture_output=True,check=True,timeout=60,cwd=tmp_path_factory.mktemp('question-toy'))
    r=json.loads(proc.stdout);assert qs.validate_output(r,config(),dict(cpu_s=60,updates=0),question_pack);return r


def test_toy_complete_and_aggregation_averages_orders_and_fits_within_tasks(question_result):
    r=question_result['study'];c=config();a=r['analysis'];task='95000000'
    expected=sum(path[p]['query_mse'] for replicas in r['rows'][task]['random'].values() for path in replicas.values() for p in c['curve_budgets'])/120
    assert a['per_task'][task]['random']==pytest.approx(expected)
    assert len(a['primary_contrast']['paired_task_values'])==12
    assert question_result['resources']['inner_updates']==3456
    assert r['frozen_before_sha256']==r['frozen_after_sha256'] and a['learned_question_policy'] is False


@pytest.mark.parametrize('fault',['task','method','order','seed','prefix','metric','nan','inf','boolean','string','index','damping','frozen','variance'])
def test_missing_grid_and_bad_arithmetic_rejected(question_result,question_pack,fault):
    r=deepcopy(question_result['study']);cell=r['rows']['95000000'];rows=cell['informative']['fixed']['7201'];row=rows[2]
    if fault=='task':del r['rows']['95000000']
    elif fault=='method':del cell['random']
    elif fault=='order':del cell['random']['8101']
    elif fault=='seed':del cell['informative']['fixed']['7201']
    elif fault=='prefix':rows.pop()
    elif fault=='metric':del row['query_mse']
    elif fault=='nan':row['query_mse']=float('nan')
    elif fault=='inf':row['query_mse']=float('inf')
    elif fault=='boolean':row['retention_mse']=True
    elif fault=='string':row['query_mse']='1.0'
    elif fault=='index':row['index']=rows[1]['index']
    elif fault=='damping':row['theta'][0]+=.1
    elif fault=='frozen':r['frozen_after_sha256']='0'*64
    elif fault=='variance':r['orders']['95000000']['informative']['fixed']['variance_trace'].pop()
    with pytest.raises((ValueError,KeyError)):qs.validate(r,config(),question_pack)


def test_real_source_hashes_and_no_prior_scores_enter_worker():
    p=qs.source_pack(ROOT,config());assert qs.validate_pack(p,config())
    assert set(p)=={'source','parent_config','parent_sha256'} and 'analysis' not in p['source']
    assert all('query_mse' not in t['arrays'] for t in p['source']['tasks'])


def test_source_hash_damage_and_assessment_overlap_fail(question_pack):
    p=deepcopy(question_pack);p['source']['tasks'][0]['arrays']['support_y'][0]+=.1
    with pytest.raises(ValueError):qs.validate_pack(p,config())
    p=deepcopy(question_pack);t=p['source']['tasks'][0];t['arrays']['query_x'][0]=t['arrays']['support_x'][0];t['array_sha256']=digest(t['arrays'])
    with pytest.raises(ValueError):qs.validate_pack(p,config())


def test_host_refuses_unlocked_paths_before_reservation(tmp_path):
    from nexus.seed.experimental import Sandbox
    h=Sandbox(ROOT,tmp_path/'host');h.grant('toy','owner','synthetic preflight',dict(wall_s=60,cpu_s=60,memory_mb=2048,updates=0,real_steps=0,imagined_transitions=0),3600,0,memory_policy='sampled_rss')
    spec=dict(id='toy',mode='exploration',recipe=dict(adapter='seed_question_selection_v1',config_path='configs/seed_question_selection.json',config_sha256='a'*64,
        protocol_path='unlocked.md',protocol_sha256='b'*64),train=None,development=None,model_run=None,assessment=None,protocol=None,gate=None)
    with pytest.raises(ValueError,match='vetted_study_manifest'):h.execute(spec,'toy')
    assert not h.records('reserved')


@pytest.mark.parametrize('key,value',[('max_wall_s',61),('posterior_ridge',.2),('minimum_fraction',.01),('question_seeds',[8101]),('constant_seeds',[7201]),('curve_budgets',[1,2,4])])
def test_recipe_changes_fail(key,value):
    c=config();c[key]=value
    with pytest.raises(ValueError):qs.config_check(c)
