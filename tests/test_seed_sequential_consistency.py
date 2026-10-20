"""Synthetic sequential replay and isolation, never scientific worlds or fitting."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import pytest
import torch
from nexus.evolution1.catalogue import digest
from nexus.seed import sequential_consistency as seq
from nexus.seed import cumulative_learning as cum
from nexus.seed import prefix_consistency as evidence
from nexus.seed.update_diagnosis import trajectory
from test_seed_cumulative_learning import toy,toy_pack

ROOT=Path(__file__).resolve().parents[1]


def config():return json.loads((ROOT/'configs/seed_sequential_consistency.json').read_text())


@pytest.fixture(scope='module')
def synthetic_pack(tmp_path_factory):
    # Fit only generated linear toy data to create a test fixture, not new
    # scientific labels or purported historical checkpoints.
    c=config();p=toy_pack();before=Path.cwd();os.chdir(tmp_path_factory.mktemp('seq-parents'))
    try:parent=evidence.run(dict(inputs=dict(study_config=json.loads((ROOT/'configs/seed_prefix_consistency.json').read_text()),source_pack=p)))['study']
    finally:os.chdir(before)
    pack=dict(tasks=p['tasks'],frozen_folds={},parent_hashes={k:c[k+'_sha256'] for k in ('predictor_parent','damping_parent')},
        damping_config_sha256=digest({'synthetic_fixture':True}))
    for f in range(4):
        meta=parent['folds'][str(f)];_,_,with_bound=cum.prepare_fold(p,c,f)
        constants={}
        for j,seed in enumerate(c['constant_seeds']):
            provenance=dict(config_sha256=pack['damping_config_sha256'],fold=f,seed=seed,source_sha256=meta['source_sha256'],source_only=True)
            weights={'logits.weight':[[0.,0.,0.,0.]],'logits.bias':[.2*(j-1)]}
            raw=json.dumps(dict(schema='seed_plasticity_v1',width=1,provenance=provenance,weights=weights),allow_nan=False).encode()
            constants[str(seed)]=dict(provenance=provenance,weights=weights,sha256=hashlib.sha256(raw).hexdigest(),checkpoint=f'toy-{f}-{seed}.json')
        pack['frozen_folds'][str(f)]=dict(train_ids=meta['train_ids'],excluded_ids=meta['excluded_ids'],scale=meta['scale'],
            source_sha256=meta['source_sha256'],tau=with_bound['tau'],predictors={k:meta['models'][k] for k in ('consistency','prefix_mean')},constants=constants)
    assert seq.validate_pack(pack,c);return pack


def test_exact_retain_then_later_update_keeps_all_observed_labels():
    task=toy();trace=[];meta={'predictors':{'prefix_mean':{'means':[-1.,1.]+[-1.]*6}}}
    rows=trajectory(task,None,'fixed',update_fn=seq.updater('prefix_selector',meta,'frozen',trace))
    assert rows[1]['theta']==rows[0]['theta'] and trace[0]['gate']==0
    initial=torch.tensor(rows[0]['theta']);expected=cum.posterior(initial,torch.cat((task.old_x,task.support_x[:2])),
        torch.cat((task.old_y,task.support_y[:2])),torch.ones_like(initial))
    assert torch.equal(torch.tensor(rows[2]['theta']),expected) and trace[1]['gate']==1


def test_features_follow_actual_retained_fit_not_cached_reference():
    task=toy();trace=[];model=dict(columns=list(range(4,10)),center=[0.]*6,scale=[1.]*6,beta=[0.]*6,mean=-1.)
    meta={'predictors':{'consistency':model}}
    rows=trajectory(task,None,'fixed',update_fn=seq.updater('consistency_selector',meta,'frozen',trace))
    assert all(r['theta']==rows[0]['theta'] for r in rows)
    actual=evidence.features(rows[1]['theta'],trace[1]['proposal'],task.support_x[1].tolist(),float(task.support_y[1]),
        task.old_x.tolist(),task.old_y.tolist(),task.support_x[:2].tolist(),task.support_y[:2].tolist())
    assert trace[1]['features']==actual
    reference=evidence.support_trace(task.support_x,task.support_y,task.old_x,task.old_y)
    assert trace[1]['features']!=reference[1]['features']


def test_query_and_retention_poison_cannot_change_decisions(synthetic_pack):
    task=toy();other=deepcopy(task);object.__setattr__(other,'query_y',task.query_y+1000);object.__setattr__(other,'retention_y',task.retention_y-1000)
    meta=synthetic_pack['frozen_folds']['0'];before=digest(meta);a=[];b=[]
    x=trajectory(task,None,'fixed',update_fn=seq.updater('consistency_selector',meta,'frozen',a))
    y=trajectory(other,None,'fixed',update_fn=seq.updater('consistency_selector',meta,'frozen',b))
    assert a==b and all(u['theta']==v['theta'] for u,v in zip(x,y)) and digest(meta)==before
    assert x[0]['query_mse']!=y[0]['query_mse']


def test_future_labels_cannot_change_earlier_decisions(synthetic_pack):
    task=toy();other=deepcopy(task);labels=task.support_y.clone();labels[4:]+=50;object.__setattr__(other,'support_y',labels)
    meta=synthetic_pack['frozen_folds']['0'];a=[];b=[]
    x=trajectory(task,None,'fixed',update_fn=seq.updater('consistency_selector',meta,'frozen',a))
    y=trajectory(other,None,'fixed',update_fn=seq.updater('consistency_selector',meta,'frozen',b))
    assert x[:5]==y[:5] and a[:4]==b[:4]


def test_parent_payload_no_previous_query_table_or_training_logs():
    p=seq.source_pack(ROOT,config());assert seq.validate_pack(p,config())
    for f in p['frozen_folds'].values():
        assert 'cases' not in f and 'models' not in f and set(f['predictors'])=={'consistency','prefix_mean'}
        assert all(set(v)=={'weights','provenance','sha256','checkpoint'} for v in f['constants'].values())


def test_changed_checkpoint_or_fold_provenance_fails(synthetic_pack):
    p=deepcopy(synthetic_pack);p['frozen_folds']['0']['constants']['7201']['weights']['logits.bias'][0]+=.1
    with pytest.raises(ValueError):seq.validate_pack(p,config())
    p=deepcopy(synthetic_pack);p['frozen_folds']['0']['train_ids'][0]=p['frozen_folds']['0']['excluded_ids'][0]
    with pytest.raises(ValueError):seq.validate_pack(p,config())


@pytest.fixture(scope='module')
def synthetic_result(synthetic_pack,tmp_path_factory):
    before=Path.cwd();os.chdir(tmp_path_factory.mktemp('seq-result'))
    try:out=seq.run(dict(inputs=dict(study_config=config(),source_pack=synthetic_pack)))
    finally:os.chdir(before)
    assert seq.validate_output(out,config(),dict(cpu_s=30,updates=0),synthetic_pack)
    return out


def test_complete_synthetic_execution_and_seed_aggregation(synthetic_result):
    out=synthetic_result;r=out['study'];c=config();a=r['analysis']
    assert r['declared_complete'] is True and out['resources']['trajectories']==108
    assert r['frozen_before_sha256']==r['frozen_after_sha256']
    assert set(out['metrics'])=={'mse','baseline_mse'}
    expected=sum(sum(trace[p]['query_mse'] for p in c['curve_budgets'])/4 for trace in r['rows']['95000000']['constant_damping'].values())/3
    assert a['per_task']['95000000']['constant_damping']==pytest.approx(expected)
    assert len(a['contrasts']['constant_damping']['paired_task_values'])==12
    assert all(list(r['rows'][str(t)]['consistency_selector'])==['frozen'] for t in c['tasks']['train'])


@pytest.mark.parametrize('fault',['task','method','replica','prefix','metric','gate','features','proposal','initial','frozen','nan','boolean'])
def test_complete_grid_and_sequential_math_reject_corruption(synthetic_result,synthetic_pack,fault):
    r=deepcopy(synthetic_result['study']);cell=r['rows']['95000000'];row=cell['consistency_selector']['frozen'][2]
    if fault=='task':del r['rows']['95000000']
    elif fault=='method':del cell['prefix_selector']
    elif fault=='replica':del cell['constant_damping']['7201']
    elif fault=='prefix':cell['consistency_selector']['frozen'].pop()
    elif fault=='metric':del row['retention_mse']
    elif fault=='gate':row['gate']=1-row['gate']
    elif fault=='features':row['features'][4]+=.1
    elif fault=='proposal':row['proposal'][0]+=.1
    elif fault=='initial':cell['consistency_selector']['frozen'][0]['theta'][0]+=.1
    elif fault=='frozen':r['frozen_after_sha256']='0'*64
    elif fault=='nan':row['predicted_utility']=float('nan')
    else:row['query_mse']=False
    with pytest.raises((ValueError,KeyError)):seq.validate(r,config(),synthetic_pack)


def test_budget_and_threshold_locked_and_unvetted_host_path_rejected(tmp_path):
    from nexus.seed.experimental import Sandbox
    c=config();assert seq.config_check(c)['outer_updates']==0;c['utility_threshold']=.1
    with pytest.raises(ValueError):seq.config_check(c)
    h=Sandbox(ROOT,tmp_path/'host');h.grant('toy','owner','synthetic preflight',dict(wall_s=30,cpu_s=30,memory_mb=2048,updates=0,real_steps=0,imagined_transitions=0),3600,0,memory_policy='sampled_rss')
    spec=dict(id='toy',mode='exploration',recipe=dict(adapter='seed_sequential_consistency_v1',config_path='configs/seed_sequential_consistency.json',config_sha256='a'*64,
        protocol_path='unlocked.md',protocol_sha256='b'*64),train=None,development=None,model_run=None,assessment=None,protocol=None,gate=None)
    with pytest.raises(ValueError,match='vetted_study_manifest'):h.execute(spec,'toy')
    assert h.records('reserved')==[]
