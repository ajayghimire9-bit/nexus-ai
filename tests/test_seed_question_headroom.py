"""Synthetic counterfactual contracts; no scientific scoring or worlds."""
from copy import deepcopy
import inspect
import json
from pathlib import Path
import subprocess
import sys
import pytest
import torch
from nexus.evolution1.catalogue import digest
from nexus.seed import question_selection as qs
from nexus.seed import question_headroom as audit
from test_seed_cumulative_learning import toy
from test_seed_question_selection import question_pack,question_result
from test_seed_sequential_consistency import synthetic_pack

ROOT=Path(__file__).resolve().parents[1]
def config():return json.loads((ROOT/'configs/seed_question_headroom.json').read_text())


def test_helpful_and_irrelevant_questions_have_different_independent_query_effects():
    initial=previous=torch.zeros(33);anchors=torch.zeros(4,33);anchors[:,1]=1.;old=torch.zeros(4)
    pool=torch.zeros(2,33);pool[0,0]=1.;pool[1,2]=2.;labels=torch.ones(2);query=torch.zeros(27,33);query[:,0]=1.
    rows=[audit.counterfactual(initial,previous,anchors,old,pool[:0],labels[:0],pool[i],labels[i],.5) for i in range(2)]
    qs.assess(rows,query,torch.ones(27),anchors.repeat(7,1)[:27],torch.zeros(27),blocks=True)
    assert rows[0]['query_mse']<.4 and rows[1]['query_mse']==1.
    assert rows[0]['retention_mse']==0. and rows[1]['retention_mse']==0.
    assert qs.variance_scores(pool,anchors,[])[1]>qs.variance_scores(pool,anchors,[])[0]


def test_all_harmful_labels_do_not_become_useful_merely_by_picking_the_best():
    t=toy();x=torch.zeros(8,33);x[:,0]=1.;old=torch.zeros(4,33);old[:,1]=1.
    row=audit.counterfactual(torch.zeros(33),torch.zeros(33),old,torch.zeros(4),x[:0],torch.zeros(0),x[0],torch.tensor(2.),.5)
    qs.assess([row],x[:1].repeat(27,1),torch.zeros(27),old[:1].repeat(27,1),torch.zeros(27),blocks=True)
    assert row['query_mse']>0. and row['support_error_after']<row['support_error_before']


def test_counterfactuals_restore_identical_state_and_match_original_single_step():
    t=toy();order=list(range(8));path=qs.fit_path(t.support_x,t.old_x,t.old_y,qs.LabelOracle(t.support_y.tolist(),8),order,.5)
    initial=torch.tensor(path[0]['theta']);before=torch.tensor(path[3]['theta']);saved=before.clone();results={}
    for i in (3,4,5):results[i]=audit.counterfactual(initial,before,t.old_x,t.old_y,t.support_x[:3],t.support_y[:3],t.support_x[i],t.support_y[i],.5)
    for i in (5,3,4):assert results[i]==audit.counterfactual(initial,before,t.old_x,t.old_y,t.support_x[:3],t.support_y[:3],t.support_x[i],t.support_y[i],.5)
    assert torch.equal(before,saved) and results[3]['theta']==path[4]['theta']
    results[5]['theta'][0]+=99;assert results[3]['theta']==path[4]['theta']


def test_assessment_cannot_update_counterfactual_fit_or_read_other_candidate_labels():
    t=toy();initial=torch.zeros(33);args=(initial,initial,t.old_x,t.old_y,t.support_x[:1],t.support_y[:1],t.support_x[1],t.support_y[1],.5)
    a=audit.counterfactual(*args);b=deepcopy(a)
    qs.assess([a],t.query_x,t.query_y,t.retention_x,t.retention_y,blocks=True)
    qs.assess([b],t.query_x,t.query_y+999,t.retention_x,t.retention_y-999,blocks=True)
    assert a['theta']==b['theta'] and a['proposal']==b['proposal'] and a['query_mse']!=b['query_mse']
    assert list(inspect.signature(audit.counterfactual).parameters)==['initial','previous','anchors','old_y','seen_x','seen_y','candidate_x','candidate_y','g']
    assert list(inspect.signature(qs.damped_step).parameters)==['initial','previous','anchors','old_y','seen_x','seen_y','g']


def test_cross_block_candidate_selection_cannot_read_omitted_outcomes():
    errors={'0':[0.,0.,1000.],'1':[1.,1.,0.]}
    assert audit.choose_block(errors,2)=='0'
    changed=deepcopy(errors);changed['0'][2]=99999.;changed['1'][2]=99998.
    assert audit.choose_block(changed,2)=='0'
    assert errors['0'][2]>errors['1'][2]  # overfit selection can fail the omitted state
    with pytest.raises(ValueError):audit.choose_block(errors,True)


def test_common_candidate_is_selected_after_averaging_damping_fits_and_ties():
    def row(err):return dict(query_mse=err,query_blocks=[err]*3,retention_mse=.1)
    cell=dict(variance_index=0,before={str(s):row(10.) for s in (7201,7202,7203)},candidates={
        '0':{str(s):row(err) for s,err in zip((7201,7202,7203),(0.,10.,10.))},
        '1':{str(s):row(err) for s,err in zip((7201,7202,7203),(3.,4.,4.))}})
    a=audit.cell_analysis(cell,config());assert a['oracle_index']==1 and a['query']['query_oracle']==pytest.approx(11/3)
    assert a['query']['query_oracle']!=pytest.approx(8/3)  # no per-fit oracle winners
    assert audit.choose_block({'3':[0.]*3,'1':[0.]*3},2)=='1'


def test_less_harmful_best_candidate_cannot_pass_the_useful_question_screen():
    c=config();rows={}
    def metrics(error):return dict(query_mse=error,query_blocks=[error]*3,retention_mse=.1)
    for task in c['tasks']['train']:
        rows[str(task)]={}
        for b in c['budgets']:
            rows[str(task)][str(b)]=dict(variance_index=0,before={str(s):metrics(1.) for s in c['constant_seeds']},
                candidates={'0':{str(s):metrics(3.) for s in c['constant_seeds']}})
            if b!=8:rows[str(task)][str(b)]['candidates']['1']={str(s):metrics(2.) for s in c['constant_seeds']}
    a=audit.summarize(rows,c)
    assert a['primary_contrast']['mean']>0. and a['primary_contrast']['ci95'][0]>0.
    assert a['oracle_keep_contrast']['mean']<0. and a['oracle_headroom_pass'] is False
    assert a['label']=='practical_headroom_not_demonstrated'


@pytest.fixture(scope='module')
def headroom_pack(question_pack,question_result):
    r=question_result['study'];c=config();pack=dict(questions=deepcopy(question_pack),question_config=r['config'],
        parent_sha256=c['parent_sha256'],source_data_sha256=c['source_data_sha256'],query_records={},reference={})
    for t in c['tasks']['train']:
        pack['reference'][str(t)]=dict(order=r['orders'][str(t)]['informative']['fixed']['indices'],paths=deepcopy(r['rows'][str(t)]['informative']['fixed']))
        pack['query_records'][str(t)]=dict(record_sha256=digest({'synthetic':t}),episode_seeds=dict(
            support=list(range(t+100,t+108)),old=list(range(t+200,t+204)),query=list(range(t+300,t+303)),retention=list(range(t+400,t+403))))
    assert audit.validate_pack(pack,c);return pack


@pytest.fixture(scope='module')
def headroom_result(headroom_pack,tmp_path_factory):
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from nexus.seed.question_headroom import run;print(json.dumps(run(json.load(sys.stdin)),allow_nan=False))'
    p=subprocess.run([sys.executable,'-c',code,str(ROOT/'src')],input=json.dumps(dict(inputs=dict(study_config=config(),source_pack=headroom_pack))),
        text=True,capture_output=True,check=True,timeout=30,cwd=tmp_path_factory.mktemp('headroom-toy'))
    r=json.loads(p.stdout);assert audit.validate_output(r,config(),dict(cpu_s=30,updates=0),headroom_pack);return r


def test_complete_toy_grid_original_choice_reproduction_and_terminal_singleton(headroom_result,headroom_pack):
    r=headroom_result['study'];assert r['declared_complete'] is True
    assert headroom_result['resources']['counterfactual_updates']==756
    assert r['frozen_before_sha256']==r['frozen_after_sha256'] and r['reference_before_sha256']==r['reference_after_sha256']
    for task,cells in r['rows'].items():
        last=r['analysis']['cells'][task]['8'];assert last['oracle_regret']==0.
        assert last['query']['variance']==last['query']['query_oracle']
        assert last['query']['cross_block']==pytest.approx(last['query']['variance'],abs=2e-6,rel=0)
        assert [len(cells[str(b)]['candidates']) for b in config()['budgets']]==[8,7,5,1]


def test_saved_state_not_mutated_and_conditional_task_interval(headroom_result,headroom_pack):
    r=headroom_result['study'];assert r['reference_after_sha256']==digest(headroom_pack['reference'])
    a=r['analysis'];values=[v['variance']-v['query_oracle'] for v in a['per_task'].values()]
    assert len(a['primary_contrast']['paired_task_values'])==12
    assert sum(values)/12==pytest.approx(a['primary_contrast']['mean'])
    assert all(v>=0 for v in values)


@pytest.mark.parametrize('fault',['task','budget','candidate','seed','block','metric','nan','infinity','boolean','string','theta','proposal','frozen','reference','seen','decision'])
def test_complete_grid_and_bad_metrics_fail_closed(headroom_result,headroom_pack,fault):
    r=deepcopy(headroom_result['study']);cell=r['rows']['95000000']['1'];row=cell['candidates']['0']['7201']
    if fault=='task':del r['rows']['95000000']
    elif fault=='budget':del r['rows']['95000000']['2']
    elif fault=='candidate':del cell['candidates']['0']
    elif fault=='seed':del cell['candidates']['0']['7201']
    elif fault=='block':row['query_blocks'].pop()
    elif fault=='metric':del row['query_mse']
    elif fault=='nan':row['query_mse']=float('nan')
    elif fault=='infinity':row['retention_blocks'][0]=float('inf')
    elif fault=='boolean':row['retention_mse']=True
    elif fault=='string':row['query_mse']='0'
    elif fault=='theta':row['theta'][0]+=.1
    elif fault=='proposal':row['proposal'][0]+=.1
    elif fault=='frozen':r['frozen_after_sha256']='0'*64
    elif fault=='reference':r['reference_after_sha256']='0'*64
    elif fault=='seen':cell['seen_indices']=[0]
    elif fault=='decision':r['analysis']['cells']['95000000']['1']['oracle_index']=99
    with pytest.raises((ValueError,KeyError)):audit.validate(r,config(),headroom_pack)


def test_source_preflight_verifies_recorded_state_blocks_without_neural_imports():
    code='import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from nexus.seed.question_headroom import source_pack;c=json.load(open(Path(sys.argv[2])/"configs/seed_question_headroom.json"));p=source_pack(Path(sys.argv[2]),c);assert len(p["query_records"])==12;assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(ROOT)],check=True,timeout=30)


def test_missing_parent_or_wrong_hash_fails_without_collection(tmp_path):
    c=config();c['parent_sha256']='0'*64
    with pytest.raises(ValueError,match='headroom_file_hash'):audit.source_pack(ROOT,c)
    with pytest.raises(FileNotFoundError):audit.source_pack(tmp_path,config())


def test_seed_overlap_fails(headroom_pack):
    p=deepcopy(headroom_pack);s=p['query_records']['95000000']['episode_seeds'];s['query'][0]=s['support'][0]
    with pytest.raises(ValueError):audit.validate_pack(p,config())
    p=deepcopy(headroom_pack);p['query_records']['95000000']['episode_seeds']['query'][0]=p['query_records']['95010000']['episode_seeds']['support'][0]
    with pytest.raises(ValueError,match='cross_task_seed_overlap'):audit.validate_pack(p,config())


@pytest.mark.parametrize('key,value',[('budgets',[1,2,4]),('minimum_fraction',.01),('max_wall_s',31),('constant_seeds',[7201]),('query_blocks',[[True]*9]*3)])
def test_locked_grid_and_practical_criteria_cannot_shrink(key,value):
    c=config();c[key]=value
    with pytest.raises(ValueError):audit.config_check(c)


def test_unlocked_protocol_cannot_reserve_execution(tmp_path):
    from nexus.seed.experimental import Sandbox
    h=Sandbox(ROOT,tmp_path/'host');h.grant('toy','owner','synthetic preflight',dict(wall_s=30,cpu_s=30,memory_mb=2048,updates=0,real_steps=0,imagined_transitions=0),3600,0,memory_policy='sampled_rss')
    spec=dict(id='toy',mode='exploration',recipe=dict(adapter='seed_question_headroom_v1',config_path='configs/seed_question_headroom.json',config_sha256='a'*64,
        protocol_path='unlocked.md',protocol_sha256='b'*64),train=None,development=None,model_run=None,assessment=None,protocol=None,gate=None)
    with pytest.raises(ValueError,match='vetted_study_manifest'):h.execute(spec,'toy')
    assert not h.records('reserved')


def test_standalone_verifier_imports_under_isolated_python_without_execution():
    code='import runpy,sys;p=runpy.run_path(sys.argv[1],run_name="audit_import_only");assert callable(p["verify"]);assert not any(k in sys.modules for k in ("torch","numpy","gymnasium"))'
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'scripts/verify_seed_question_headroom.py')],check=True,timeout=10)
