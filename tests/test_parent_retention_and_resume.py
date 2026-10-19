"""Authored fixtures and sealed-file audits only; no scientific execution."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from nexus.evolution2.partial_feedback import parent_inclusive_decision,validate_parent_retention_proposal
from nexus.evolution2.cycle_checkpoint import save_cycle,load_cycle,encode
from nexus.evolution2.learning_cycle import LearningCycle,FixtureHost
from nexus.evolution2.learning_lab import load_operator_replay
from test_e3_12c_partial_feedback import fixture

ROOT=Path(__file__).resolve().parents[1]
PROVENANCE={'kind':'authored_fixture','recipe':'A-B-restart-A-C','source':'test-only'}


@pytest.mark.parametrize('values,choice',[(dict(parent=3,switch=2,rank_blend=1),'parent'),
    (dict(parent=3,switch=3,rank_blend=3),'parent'),(dict(parent=1,switch=4,rank_blend=2),'switch'),
    (dict(parent=1,switch=2,rank_blend=4),'rank_blend')])
def test_three_way_means_and_ties(values,choice):
    p,c=fixture()
    for row in p['rows']:
        if row['role']=='training':
            for k,path in row['paths'].items():path['return']=values[k]
    result=parent_inclusive_decision(p['rows'],c,'pendulum',0)
    assert result['choice']==choice and result['observed_counts']==dict(parent=8,switch=4,rank_blend=4)
    assert result['two_child_choice'] in ('switch','rank_blend')


def test_new_selector_reads_only_registered_training_feedback():
    p,c=fixture()
    class Hidden(dict):
        def __getitem__(self,key):
            if key=='paths':raise AssertionError('query_access')
            return super().__getitem__(key)
    rows=[Hidden(r) if r['role']=='evaluation' else r for r in p['rows']]
    before=parent_inclusive_decision(rows,c,'pendulum',0)
    for r in p['rows']:
        if r['role']=='evaluation':r['paths']=None
    assert parent_inclusive_decision(rows,c,'pendulum',0)==before
    rows=[r for r in rows if not(r['role']=='training' and r['family']=='pendulum' and r['bundle']==0 and r['episode']==0)]
    with pytest.raises(ValueError):parent_inclusive_decision(rows,c,'pendulum',0)


def advance(cycle,host,tasks):
    for task in tasks:
        cycle.begin_task(task)
        for _ in range(2):cycle.step(host,task)


@pytest.mark.parametrize('method',['unified','reset_memory','shuffled_memory','random_generation'])
def test_restart_preserves_exact_trajectory_rng_counts_and_gate(tmp_path,method):
    full=LearningCycle(7,method);advance(full,FixtureHost(7),('A','B','A','C'))
    partial=LearningCycle(7,method);advance(partial,FixtureHost(7),('A','B'))
    path=tmp_path/'state.json';sha=save_cycle(partial,path,provenance=PROVENANCE)
    restored=load_cycle(path,expected_sha256=sha,provenance=PROVENANCE)
    advance(restored,FixtureHost(7),('A','C'))
    assert encode(restored)==encode(full)
    # A real Python process restart, not just deepcopy of the original objects.
    output=tmp_path/'after.json'
    script="""import sys,json
from nexus.evolution2.cycle_checkpoint import load_cycle,save_cycle
from nexus.evolution2.learning_cycle import FixtureHost
path,sha,out,provenance=sys.argv[1:];p=json.loads(provenance)
c=load_cycle(path,expected_sha256=sha,provenance=p);h=FixtureHost(7)
for task in ('A','C'):
 c.begin_task(task)
 for _ in range(2):c.step(h,task)
print(save_cycle(c,out,provenance=p))
"""
    run=subprocess.run([sys.executable,'-c',script,str(path),sha,str(output),json.dumps(PROVENANCE)],cwd=ROOT,env=os.environ,text=True,capture_output=True,timeout=15)
    assert run.returncode==0,run.stderr
    child=load_cycle(output,expected_sha256=run.stdout.strip(),provenance=PROVENANCE)
    assert encode(child)==encode(full)
    with pytest.raises(FileExistsError):save_cycle(partial,path,provenance=PROVENANCE)


def test_checkpoint_hash_provenance_pending_and_schema_rejection(tmp_path):
    c=LearningCycle();c.begin_task('A');path=tmp_path/'state.json';sha=save_cycle(c,path,provenance=PROVENANCE)
    with pytest.raises(ValueError,match='hash'):load_cycle(path,expected_sha256='0'*64,provenance=PROVENANCE)
    with pytest.raises(ValueError,match='provenance'):load_cycle(path,expected_sha256=sha,provenance={'other':1})
    p=json.loads(path.read_text());p['state']['type']='__import__';path.write_text(json.dumps(p))
    with pytest.raises(ValueError,match='unvetted'):load_cycle(path,expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),provenance=PROVENANCE)
    c.stream.choose_experiment()
    with pytest.raises(ValueError,match='settled'):save_cycle(c,tmp_path/'pending.json',provenance=PROVENANCE)


class SimpleHost:
    def __init__(self,hidden=1):self.hidden=hidden;self.calls=0
    def evaluate(self,strategy,task,phase):
        self.calls+=1
        return (1. if strategy.kind=='switch' else 0.)*(self.hidden if phase!='training' else 1.)


def test_only_new_training_incumbent_progress_earns_discovery_credit():
    c=LearningCycle(7,'fixed_generation',objective='training_incumbent_progress_v1');c.begin_task('A');h=SimpleHost()
    rows=[c.step(h,'A') for _ in range(3)]
    assert rows[0]['effective_gain']==1.
    assert rows[2]['gain']==1. and rows[2]['effective_gain']==0.
    assert rows[2]['training_progress']['novel'] is False
    assert c.charged.cpu_units==9 and c.stream.choices==3
    old=LearningCycle(7,'fixed_generation');old.begin_task('A')
    prior=[old.step(SimpleHost(),'A') for _ in range(3)]
    assert prior[2]['effective_gain']==1.  # Historical objective deliberately preserved.


def test_assessment_outcomes_cannot_train_scheduler_or_generator():
    runs=[]
    for hidden in (-1,1):
        c=LearningCycle(7,'fixed_generation',objective='training_incumbent_progress_v1');c.begin_task('A')
        for _ in range(3):c.step(SimpleHost(hidden),'A')
        runs.append(c)
    a,b=runs
    assert a.stream.rates==b.stream.rates and a.rules.state_dict()==b.rules.state_dict()
    assert a.stream.generator.mutation_stats==b.stream.generator.mutation_stats
    assert a.incumbent!=b.incumbent


def test_progress_failure_consumes_cost_and_durable_resume_keeps_it(tmp_path):
    c=LearningCycle(objective='training_incumbent_progress_v1');c.begin_task('A')
    class Failure:
        def evaluate(self,*args):raise RuntimeError('authored_failure')
    with pytest.raises(RuntimeError):c.step(Failure(),'A')
    assert c.charged.cpu_units==3 and c.stream.remaining==15 and c.stream.pending is None
    path=tmp_path/'failed.json';sha=save_cycle(c,path,provenance=PROVENANCE)
    restored=load_cycle(path,expected_sha256=sha,provenance=PROVENANCE)
    assert restored.charged==c.charged
    next_row=restored.step(SimpleHost(),'A')
    assert next_row['event']=='1:A' and restored.charged.cpu_units==6


def test_verified_operator_view_has_actual_choices_parent_failures_and_paths():
    data=load_operator_replay(ROOT)
    assert len(data['cases'])==16 and len(data['training'])==32 and data['live'] is False
    assert any(r['harmful_change'] for r in data['cases'])
    assert data['label']=='headroom_visible_selection_not_established'
    for r in data['cases']:
        assert r['selected_minus_parent']==pytest.approx(r['returns'][r['decision']['training_mean_kind']]-r['returns']['parent'])
        assert all(len(p['steps'])==200 for p in r['paths'].values())


@pytest.mark.parametrize('key,value',[('execution_authorized',True),('allocation',{}),('numerical_environment_seeds',[1]),
    ('model_bundles',[0]),('proposed_real_cap',20000),('revealed_children_per_training_reset',True)])
def test_fresh_proposal_cannot_masquerade_as_a_registered_execution(key,value):
    c=json.loads((ROOT/'configs/e3_12d_parent_retention_proposal.json').read_text())
    assert validate_parent_retention_proposal(c)['execution_allowed'] is False
    c[key]=value
    with pytest.raises(ValueError):validate_parent_retention_proposal(c)


def test_recorded_view_rejects_changed_capture_or_config(tmp_path):
    folder=tmp_path/'artifacts';folder.mkdir();config=tmp_path/'configs';config.mkdir()
    for filename in ('e3_12b_operator_headroom.json','e3_12b_operator_validation.json'):
        (folder/filename).write_bytes((ROOT/'artifacts'/filename).read_bytes())
    cp=config/'e3_12b_operator_headroom.json';cp.write_bytes((ROOT/'configs'/cp.name).read_bytes())
    assert len(load_operator_replay(tmp_path)['cases'])==16
    cp.write_text(cp.read_text()+' ')
    with pytest.raises(ValueError,match='verified_operator'):load_operator_replay(tmp_path)


def test_resume_after_rule_freezing_and_new_objective(tmp_path):
    c=LearningCycle(8,objective='training_incumbent_progress_v1');advance(c,FixtureHost(8),('A','B'));c.freeze_rule()
    path=tmp_path/'frozen.json';sha=save_cycle(c,path,provenance=PROVENANCE)
    loaded=load_cycle(path,expected_sha256=sha,provenance=PROVENANCE)
    assert loaded.selected_rule==c.selected_rule and encode(loaded)==encode(c)
    advance(c,FixtureHost(8),('A','C'));advance(loaded,FixtureHost(8),('A','C'))
    assert encode(loaded)==encode(c)


@pytest.mark.parametrize('fault',['worker','complete','status','history','inputs'])
def test_scientific_runner_cannot_exit_success_on_invalid_parent_validation(fault):
    from test_e3_12c_partial_feedback import load
    runner=load('scripts/run_e3_12_mutation_control.py','parent_exit_audit')
    p=dict(declared_complete=True,status='complete_valid',historical_preserved=True,inputs_preserved=True)
    assert runner.completion_exit_code(0,p)==0
    code=0
    if fault=='worker':code=1
    elif fault=='complete':p['declared_complete']=False
    elif fault=='status':p['status']='incomplete_or_invalid'
    elif fault=='history':p['historical_preserved']=False
    else:p['inputs_preserved']=False
    assert runner.completion_exit_code(code,p)==1
