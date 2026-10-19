"""Authored fixture paths/callbacks only. Never instantiate real environments."""
from copy import deepcopy
import importlib.util
import itertools
import json
from pathlib import Path
import pytest
from nexus.evolution1.catalogue import digest
from nexus.evolution2 import reset_blocks as blocks, reset_blocked_study as study

ROOT=Path(__file__).resolve().parents[1]


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def config():
    c=json.loads((ROOT/'configs/e3_12f_reset_blocked_runtime_v2.json').read_text())
    # Authored unit-test IDs only; these are NOT scientific registrations.
    c.update(status='registered',execution_authorized=True,env_seed_base=1000000,planner_seed_base=2000000,
             schedule_seeds={f'{f}:{b}':5000+i for i,(f,b) in enumerate(itertools.product(c['families'],c['model_bundles']))})
    return c


def fixture():
    p,_=load('tests/test_e3_12b_operator_headroom.py','reset_panel_fixture').fixture();c=config()
    p.update(reset_plans={},plan_manifests={},sealed_decisions={},decision_manifests={})
    for f,b in itertools.product(c['families'],c['model_bundles']):
        key=f'{f}:{b}';rows=[r for r in p['rows'] if (r['family'],r['bundle'])==(f,b)]
        plan=blocks.make_plan(f,[dict(reset_id=r['episode'],observation=r['initial_observation'])
                             for r in rows if r['role']=='training'],c['schedule_seeds'][key])
        p['reset_plans'][key]=plan
        for row in rows:
            reset,planner=study.seed_pair(c,f,b,row['episode'])
            row['protocol'].update(reset_seed=reset,planner_seed=planner)
            wanted=study.path_labels(row,p,c)
            row['paths']={k:v for k,v in row['paths'].items() if k in wanted}
            row['strategies']={k:v for k,v in row['strategies'].items() if k in wanted}
            row['before']={};row['after']={}
            for path in row['paths'].values():
                for t,step in enumerate(path['steps']):step['planner_seed']=planner+t
        choices=study.decide(rows,c,f,b,plan);p['sealed_decisions'][key]=choices
        for row in rows:
            if row['role']=='evaluation':row['decision']=deepcopy(choices)
        for kind,value in [('plan',plan),('decision',choices)]:
            p[kind+'_manifests'][key]=dict(path=f'authored/{key}_{kind}.json',sha256='a'*64,content_hash=digest(value))
    p['final_policies']={key:{} for key in p['reset_plans']}
    count=study.planned_real_steps(p,c)
    p['resources']['completed']['real_steps']=count;p['resources']['reserved']['real_steps']=count
    return p,c


def test_complete_dynamic_union_reuses_panel_validator_and_has_no_false_success():
    p,c=fixture();assert study.validate(p,c)
    assert 22400<=p['resources']['completed']['real_steps']<=28800
    assert p['resources']['completed']['real_steps']==sum(len(r['paths'])*200 for r in p['rows'])
    a=study.analyze(p,c)
    assert a['label']=='reset_blocking_not_established'
    for f in c['families']:
        assert a['families'][f]['contrasts']['random_balanced']['ci95']==[0.,0.]
        assert len(a['families'][f]['models'])==2


@pytest.mark.parametrize('fault',['model','reset','union','decision','seal','plan','observations','update','resource','extra_resource','nan','reward','fingerprint','bool_id','bool_model','bool_resource'])
def test_invalid_or_incomplete_grid_never_becomes_a_scientific_negative(fault):
    p,c=fixture();row=p['rows'][0];key='pendulum:0'
    if fault=='model':p['rows']=[r for r in p['rows'] if r['bundle']!=1]
    elif fault=='reset':p['rows'].pop()
    elif fault=='union':del row['paths']['parent']
    elif fault=='decision':next(r for r in p['rows'] if r['role']=='evaluation')['decision']['public_blocked']['choice']='switch'
    elif fault=='seal':p['decision_manifests'][key]['content_hash']='x'
    elif fault=='plan':p['reset_plans'][key]['schedules']['public_blocked']['0']='parent'
    elif fault=='observations':row['initial_observation']=[0.,1.,0.]
    elif fault=='update':row['after']={'learned':{'switch':.9}}
    elif fault=='resource':p['resources']['completed']['real_steps']-=1
    elif fault=='extra_resource':p['resources']['completed']['real_steps']=c['real_cap']+1
    elif fault=='nan':row['paths']['parent']['return']=float('nan')
    elif fault=='reward':row['paths']['parent']['steps'][0]['reward']+=1.
    elif fault=='fingerprint':p['models'][0]['after']='changed'
    elif fault=='bool_id':row['bundle']=False
    elif fault=='bool_model':p['models'][0]['bundle']=False
    else:p['resources']['unknown_upper']['real_steps']=False
    with pytest.raises(ValueError):study.validate(p,c)


def test_query_paths_are_inaccessible_to_decision_fitting():
    p,c=fixture()
    class Hidden(dict):
        def __getitem__(self,key):
            if key=='paths':raise AssertionError('query_outcomes_read')
            return super().__getitem__(key)
    rows=[Hidden(r) if r['role']=='evaluation' else r for r in p['rows']]
    assert study.decide(rows,c,'pendulum',0,p['reset_plans']['pendulum:0'])==p['sealed_decisions']['pendulum:0']


def test_registration_guards_precede_all_host_access(monkeypatch):
    runner=load('scripts/run_e3_12_mutation_control.py','blocked_runner_guard');runner.configure_reset_blocked()
    c=json.loads(runner.CONFIG.read_text());assert study.validate_config(c) is False
    def forbidden(*args,**kwargs):raise AssertionError('host_or_allocation_access')
    monkeypatch.setattr(runner,'preflight',forbidden)
    monkeypatch.setattr(runner.subprocess,'Popen',forbidden)
    with pytest.raises(ValueError,match='registration'):runner.run()
    with pytest.raises(ValueError,match='registration'):runner.worker()
    with pytest.raises(ValueError,match='registration'):study.requested_seeds(c)
    assert runner.RESULT.name=='e3_12f_reset_blocked.json'
    runner.configure_retention();assert not runner.RESET_BLOCKED_PROFILE
    assert runner.RESULT.name=='e3_12d_parent_retention.json'


def test_public_registration_callback_is_complete_and_pre_feedback_only():
    runner=load('scripts/run_e3_12_mutation_control.py','blocked_public_callback');c=config();seen=[]
    def public(reset):seen.append(reset);return [1.,0.,0.]
    plan=runner.prepare_reset_plan(c,'pendulum',0,public)
    assert seen==[study.seed_pair(c,'pendulum',0,e)[0] for e in range(8)]
    assert plan['sha256']==blocks.make_plan('pendulum',plan['public_observations'],5000)['sha256']


def test_exclusive_plan_and_decision_files_cannot_be_replaced(tmp_path):
    runner=load('scripts/run_e3_12_mutation_control.py','blocked_seals');runner.configure_reset_blocked()
    runner.ROOT=tmp_path;runner.RESULT=tmp_path/'panel.json'
    p,c=fixture();p['plan_manifests']={};p['decision_manifests']={}
    for f,b in itertools.product(c['families'],c['model_bundles']):
        key=f'{f}:{b}'
        runner.save_profile_seal('plan',f,b,p['reset_plans'][key],p)
        runner.save_profile_seal('decision',f,b,p['sealed_decisions'][key],p)
    runner.verify_profile_seals(p)
    with pytest.raises(FileExistsError):runner.save_profile_seal('plan','pendulum',0,p['reset_plans']['pendulum:0'],p)
    (tmp_path/'panel_pendulum_0_plan.json').write_text('{}')
    with pytest.raises(ValueError):runner.verify_profile_seals(p)


def test_exact_recipe_and_symbolic_template_remain_distinct():
    c=config();seeds=study.requested_seeds(c)
    assert len(seeds)==9652
    for change in [dict(model_bundles=[False,1]),dict(practical_margin=0.),dict(real_cap=22400),
                   dict(schedule_seeds={}),dict(schedule_seeds={k:7 for k in c['schedule_seeds']})]:
        with pytest.raises(ValueError):study.validate_config({**c,**change},registered=True)
    bad=deepcopy(c);bad['schedule_seeds']['pendulum:0']=study.seed_pair(c,'pendulum',0,0)[0]
    with pytest.raises(ValueError):study.requested_seeds(bad)


def test_statistics_average_queries_inside_models_not_as_independent_samples(monkeypatch):
    p,c=fixture()
    # Test aggregation alone with authored numbers, not physical reward claims.
    monkeypatch.setattr(study,'validate',lambda *args:True)
    for f,b in itertools.product(c['families'],c['model_bundles']):
        choices=p['sealed_decisions'][f'{f}:{b}']
        choices['random_balanced']['choice']='parent';choices['public_blocked']['choice']='switch'
        for row in p['rows']:
            if (row['family'],row['bundle'],row['role'])==(f,b,'evaluation'):
                row['paths']['parent']['return']=0.
                row['paths']['switch']['return']=float((4 if b==0 else 12) if row['episode']==11 else 0)
    result=study.analyze(p,c)
    for family in result['families'].values():
        contrast=family['contrasts']['random_balanced']
        assert contrast['per_model']==[1.,3.] and contrast['mean']==2.
        assert contrast['ci95']==pytest.approx([2-12.7062047364,2+12.7062047364])
        assert family['screen_passed'] is False


def test_independent_stdlib_export_and_missing_contrast_rejection():
    p,c=fixture();p['analysis']=study.analyze(p,c)
    exporter=load('scripts/summarize_e3_12_mutation_control.py','blocked_exporter')
    summary=exporter.summarize_blocked(p,c)
    assert summary['physical_real_steps']==p['resources']['completed']['real_steps']
    assert summary['phase_accounting']['evaluation']['real_steps']==9600
    assert summary['label']=='reset_blocking_not_established'
    for fault in ('contrast','interval','choice','seed','condition'):
        bad=deepcopy(p)
        if fault=='contrast':del bad['analysis']['families']['pendulum']['contrasts']['parent']
        elif fault=='interval':bad['analysis']['families']['pendulum']['contrasts']['parent']['ci95']=[]
        elif fault=='choice':bad['sealed_decisions']['pendulum:0']['public_blocked']['choice']='switch'
        elif fault=='seed':bad['rows']=[r for r in bad['rows'] if r['bundle']!=1]
        else:del bad['reset_plans']['pendulum:0']['schedules']['public_blocked']
        with pytest.raises(ValueError):exporter.summarize_blocked(bad,c)


def test_receipts_reject_duplicates_unknown_work_and_wrong_seal_references():
    p,c=fixture();runner=load('scripts/run_e3_12_mutation_control.py','blocked_receipts')
    remaining=runner.expected_profile_decisions(p)
    assert len(remaining)==study.planned_real_steps(p,c)
    f,b,e,condition,tick=next(iter(remaining));key=f'{f}:{b}'
    role='training' if e<8 else 'evaluation'
    meta=dict(family=f,bundle=b,episode=e,condition=condition,tick=tick,role=role,
              plan_sha256=p['plan_manifests'][key]['sha256'],
              decision_sha256=p['decision_manifests'][key]['sha256'] if role=='evaluation' else None)
    for change in [dict(condition='unobserved'),dict(plan_sha256='b'*64),dict(role='wrong'),dict(tick=True)]:
        with pytest.raises(ValueError):runner.check_profile_receipt({**meta,**change},p,remaining)
    runner.check_profile_receipt(meta,p,remaining)
    with pytest.raises(ValueError):runner.check_profile_receipt(meta,p,remaining)


def test_shared_worker_control_flow_with_authored_host_only(tmp_path,monkeypatch):
    """Run production orchestration with every world/model call replaced.

    This is a functional test, not simulated/scientific performance evidence.
    """
    from dataclasses import dataclass
    from types import SimpleNamespace
    import os,time
    import numpy as np
    from nexus.evolution1.resources import Work
    from nexus.evolution2 import post_probe,full_policy_source
    from nexus.tasks import spec as task_module
    from nexus.world import dynamics
    runner=load('scripts/run_e3_12_mutation_control.py','blocked_fixture_worker');runner.configure_reset_blocked()
    runner.ROOT=tmp_path;runner.RESULT=tmp_path/'result.json';runner.CONFIG=tmp_path/'config.json'
    runner.USAGE=tmp_path/'usage.json';runner.JOURNAL=tmp_path/'resources.jsonl.gz'
    c=config();runner.CONFIG.write_text(json.dumps(c))
    usage=dict(parent_pid=os.getppid(),start_monotonic=time.perf_counter())
    runner.USAGE.write_text(json.dumps(usage));monkeypatch.setenv('NEXUS_MUTATION_PARENT',str(os.getppid()))
    inventory={'checkpoints':[dict(family=f,bundle=b,path='never_loaded.pt',sha256='a'*64)
                             for f,b in itertools.product(c['families'],c['model_bundles'])]}
    inventory_path=tmp_path/c['checkpoint_inventory'];inventory_path.parent.mkdir(parents=True)
    inventory_path.write_text(json.dumps({'integrity':inventory}))
    p=dict(rows=[],models=[],final_policies={},learning_journals={},reset_plans={},plan_manifests={},
           sealed_decisions={},decision_manifests={},observed=dict(model_calls=0,network_forwards=0,imagined_transitions=0),reward_sha256='b'*64)
    original_read=runner.read
    monkeypatch.setattr(runner,'read',lambda path:p if path==runner.RESULT else original_read(path))
    monkeypatch.setattr(runner,'write',lambda path,data:None)
    observations={'pendulum':[1.,0.,0.],'acrobot':[1.,0.,1.,0.,0.,0.]}
    class AuthoredReset:
        def __init__(self,family):self.family=family
        def reset(self,seed):return np.asarray(observations[self.family]),{}
        def close(self):pass
    monkeypatch.setattr(task_module,'make_task_env',lambda spec,seed:AuthoredReset('pendulum' if spec.obs_dim==3 else 'acrobot'))
    monkeypatch.setattr(post_probe,'simulator_fingerprint',lambda env:'same')
    monkeypatch.setattr(post_probe,'restore_copy',lambda env:(AuthoredReset(env.family),'same'))
    class AuthoredNet:
        hidden=(64,64)
        def eval(self):pass
        def parameters(self):return []
    monkeypatch.setattr(dynamics,'DynamicsMLP',AuthoredNet)
    monkeypatch.setattr(dynamics.WorldModel,'load',lambda path:SimpleNamespace(net=AuthoredNet(),device='cpu',kind='residual'))
    monkeypatch.setattr(full_policy_source,'state_hash',lambda wm:'fixture_frozen')
    class AuthoredJournal:
        def __init__(self,*args):self.paths=[]
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(full_policy_source,'DecisionJournal',AuthoredJournal)
    @dataclass
    class Receipt:
        physical_reserved:Work
        physical_completed_reported:Work
        logical_charged:Work
        events:tuple=()
    visited=[]
    class AuthoredHost:
        def __init__(self,*args):self.total=Work()
        def bind(self,wm):self.instrument=SimpleNamespace(calls=0,network_forwards=0,rows=0)
        def perform(self,ops,body,metadata):
            # Intentionally do NOT execute body: no planning/model/env calls.
            f,b=metadata['family'],metadata['bundle']
            assert (tmp_path/f'result_{f}_{b}_plan.json').exists()
            if metadata['role']=='evaluation':assert (tmp_path/f'result_{f}_{b}_decision.json').exists()
            if metadata['tick']==0:visited.append((f,b,metadata['episode'],metadata['condition']))
            cost=Work(1,1,1,1);self.total=self.total.plus(cost)
            self.instrument.calls+=1;self.instrument.network_forwards+=1;self.instrument.rows+=1
            value=(1,np.asarray(observations[f]),0. if f=='pendulum' else -2.,False,metadata['tick']==199)
            return value,Receipt(cost,cost,cost)
        def resources(self):
            return dict(completed=self.total.payload(),reserved=self.total.payload(),unknown_upper=Work().payload())
    monkeypatch.setattr(post_probe,'Host',AuthoredHost)
    runner.worker()
    assert p['status']=='complete_valid' and p['declared_complete'] is True
    assert all(r['before']==r['after']=={} for r in p['rows'])
    assert len(visited)*200==study.planned_real_steps(p,c)==p['resources']['completed']['real_steps']
    assert len(p['reset_plans'])==len(p['sealed_decisions'])==4
    runner.verify_profile_seals(p)
