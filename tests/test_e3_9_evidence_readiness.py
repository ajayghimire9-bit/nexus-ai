"""Source-only contracts: no environments, learned inference, or fitting."""
import copy
import itertools
import importlib.util
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest

from nexus.evolution1.catalogue import digest
from nexus.evolution1.resources import Clock, Work, Operation
from nexus.evolution2.planner_adapter import FakeStepModel, score_open_loop
from nexus.evolution2.planner_evidence import evidence_operations, planner_evidence
from nexus.evolution2.staged_study import StagedStudy
from test_e3_8_learning_interfaces import ledger_for, receipt


def manifest():
    return dict(kind='registered_fresh_study',registered=True,authorized=True,
        protocol_commit='a'*40,planned_tasks=['A','B'],planned_episodes=[0,1],
        conditions=['mean','context'],cases=[dict(task=t,condition=c,episode=e,
            reset_seed=100+e,planner_seed=200+e,probe_steps=8,remaining_steps=192)
            for t,c,e in itertools.product(['A','B'],['mean','context'],[0,1])],
        per_case_real_cap=192,per_case_imagined_cap=0,
        total_real_cap=4*(8+2*192),total_imagined_cap=0)


@pytest.mark.parametrize('axis,key,value',[
    ('task','task','A'),('episode','episode',0),('condition','condition','mean')])
def test_independent_axes_reject_entire_missing_groups(axis,key,value):
    m=manifest();StagedStudy(m)
    m['cases']=[c for c in m['cases'] if c[key]!=value]
    with pytest.raises(ValueError,match='complete_case_grid'):StagedStudy(m)


@pytest.mark.parametrize('field,value',[
    ('registered',1),('authorized','yes'),('protocol_commit','synthetic'),
    ('planned_tasks',[]),('planned_tasks',['A','A']),('planned_episodes',[False,1]),
    ('planned_episodes',[0,0]),('conditions',['mean','mean'])])
def test_registration_types_and_axes_are_fail_closed(field,value):
    m=manifest();m[field]=value
    with pytest.raises(ValueError):StagedStudy(m)


def test_mutating_host_stops_before_another_case_executes():
    m=manifest();m['kind']='synthetic_contract';m['cases']=m['cases'][:2]
    # The two first cases are separate episodes of one condition.
    m['conditions']=['mean'];s=StagedStudy(m)
    s.fit_source([{'phase':'training'}],lambda rows:{'w':1},digest)
    for e in (0,1):
        prefix=[dict(task='A',episode=e,step=i,phase='support',
            observation=[i],action=0,next_observation=[i+1],reward=-1.) for i in range(8)]
        s.adapt_support('A',prefix,lambda p,r:{},receipt(8),episode=e)
    calls=[]
    def host(case,policy,context):
        calls.append(case);policy['w']=2
        return {},None
    with pytest.raises(ValueError,match='evaluation_changed_policy'):s.evaluate(host)
    assert len(calls)==1 and not s.complete


def test_metered_evidence_matches_existing_scoring_and_keeps_inputs():
    plans={'incumbent':np.array([[0,1,2],[2,1,0]]),
           'challenger':np.array([[1,2,1],[0,0,2]])}
    before=copy.deepcopy(plans);obs=np.array([.2,.3],dtype=np.float32)
    model=FakeStepModel(2,3)
    def reward(o,a,n):return -n[:,0]**2
    expected={k:score_open_loop(model,obs,v,reward) for k,v in plans.items()}
    ledger=ledger_for(evidence_operations(plans,3))
    result=planner_evidence(plans,obs,model,reward,n_actions=3,ledger=ledger,
        clock=lambda:Clock(0,0),fingerprint=lambda:'frozen')
    for k in plans:
        np.testing.assert_array_equal(plans[k],before[k])
        np.testing.assert_allclose(result[k]['scores'],expected[k],rtol=0,atol=1e-12)
        assert result[k]['selected_candidate']==int(np.argmax(expected[k]))
    np.testing.assert_array_equal(obs,np.array([.2,.3],dtype=np.float32))
    assert ledger.close(Clock(0,0)).physical_completed_reported.imagined_transitions==12


def test_mutating_model_is_rejected_and_work_is_not_free():
    class Mutating(FakeStepModel):
        def step(self,obs,action):
            obs[0,0]=999
            return super().step(obs,action)
    plans={'a':np.array([[0,0]]),'b':np.array([[1,1]])}
    ledger=ledger_for(evidence_operations(plans,3));obs=np.array([1.])
    with pytest.raises(ValueError):planner_evidence(plans,obs,Mutating(1,3),
        lambda o,a,n:n[:,0],n_actions=3,ledger=ledger,
        clock=lambda:Clock(0,0),fingerprint=lambda:'fixed')
    assert obs[0]==1
    assert ledger.close(Clock(0,0)).physical_unknown_upper_bound.imagined_transitions==1


def test_underdeclared_reservation_is_rejected_before_model_dispatch():
    calls=[]
    class Counted(FakeStepModel):
        def step(self,*args):
            calls.append(1)
            return super().step(*args)
    plans={'a':np.array([[0],[1]]),'b':np.array([[1],[2]])}
    ops=evidence_operations(plans,3)
    bad=(Operation(ops[0].key,'model',Work(imagined_transitions=1,model_calls=1,network_forwards=1)),ops[1])
    ledger=ledger_for(bad)
    with pytest.raises(ValueError,match='reservation_shape'):planner_evidence(plans,[0.],Counted(1,3),
        lambda o,a,n:n[:,0],n_actions=3,ledger=ledger,
        clock=lambda:Clock(0,0),fingerprint=lambda:'fixed')
    assert not calls


@pytest.mark.parametrize('name,n_actions',[('A',3),('a'*33,3),('abc',True),('abc',0)])
def test_invalid_operation_names_and_action_schema_rejected(name,n_actions):
    with pytest.raises(ValueError):evidence_operations({name:np.array([[0]]),'other':np.array([[0]])},n_actions)


def audit_module():
    path=Path(__file__).resolve().parents[1]/'scripts/audit_e3_9_planner_evidence_readiness.py'
    spec=importlib.util.spec_from_file_location('readiness_audit',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def audit_fixture(tmp_path):
    m=audit_module();c=json.loads(m.CONFIG.read_text())
    fits=[];arrays=[]
    for f,b in itertools.product(c['families'],c['model_bundles']):
        path=f'{f}{b}.pt';raw=f'{f}{b}'.encode();(tmp_path/path).write_bytes(raw)
        fits.append(dict(family=f,bundle=b,path=path,sha256=hashlib.sha256(raw).hexdigest()))
        for split in c['source_splits']:
            path=f'{f}{b}{split}.npz';(tmp_path/path).write_bytes(raw)
            arrays.append(dict(family=f,bundle=b,split=split,path=path,sha256=hashlib.sha256(raw).hexdigest()))
    for key,path,text in [('fit_manifest','fits.json',json.dumps(dict(fits=fits))),
        ('source_inventory','constants.py','LOCKED_ARRAYS = '+repr(tuple(arrays))),
        ('draft_manifest','draft.json',json.dumps(dict(registered=False,authorized=False,cases=[])))]:
        (tmp_path/path).write_text(text);c[key]=path;c[key+'_sha256']=m.sha(tmp_path/path)
    return m,c


def test_integrity_verifies_bytes_without_loading_checkpoints(tmp_path):
    m,c=audit_fixture(tmp_path);result=m.audit(tmp_path,c)
    assert result['integrity']['all_files_match']
    assert result['verdict']=='BLOCKED_FRESH_STUDY_NOT_READY'
    assert not result['model_inference'] and result['new_real_steps']==0
    (tmp_path/'pendulum0.pt').unlink()
    assert not m.audit(tmp_path,c)['integrity']['all_files_match']
    (tmp_path/'acrobot0.pt').write_bytes(b'wrong')
    assert sum(not r['matches'] for r in m.audit(tmp_path,c)['integrity']['checkpoints'])==2


@pytest.mark.parametrize('omit',['family','bundle','split'])
def test_inventory_axes_do_not_shrink_with_missing_manifest_rows(tmp_path,omit):
    m,c=audit_fixture(tmp_path)
    key='source_inventory' if omit=='split' else 'fit_manifest'
    path=tmp_path/c[key]
    if omit=='split':
        rows=m.ast.literal_eval(m.ast.parse(path.read_text()).body[0].value)
        path.write_text('LOCKED_ARRAYS = '+repr(tuple(r for r in rows if r['split']!='val')))
    else:
        rows=json.loads(path.read_text())['fits']
        rows=[r for r in rows if r['family']!='pendulum'] if omit=='family' else [r for r in rows if r['bundle']!=0]
        path.write_text(json.dumps(dict(fits=rows)))
    # Even if the container's hash were re-pinned, fixed expected axes reject it.
    c[key+'_sha256']=m.sha(path)
    with pytest.raises(ValueError,match='grid'):m.inventory(tmp_path,c)


def test_evidence_compute_is_additional_not_free():
    m=audit_module();c=json.loads(m.CONFIG.read_text());b=m.budget(c['budget_illustration'])
    assert b['total_real_interactions']==27104
    assert b['per_case_controller_imagined']==294912
    assert b['per_case_combined_imagined']==393216
    assert b['combined_imagined_upper']==55050240
    assert b['evidence_imagined_upper']==13762560
    assert b['evidence_model_calls_upper']==860160
    assert not b['allocation']
    for value in (True,1.0,0):
        bad=copy.deepcopy(c['budget_illustration']);bad['conditions']=value
        with pytest.raises(ValueError):m.budget(bad)


def test_readiness_auditor_cannot_import_a_runtime_or_evaluator():
    m=audit_module();tree=m.ast.parse(Path(m.__file__).read_text())
    names=[]
    for node in m.ast.walk(tree):
        if isinstance(node,m.ast.Import):names.extend(a.name.split('.')[0] for a in node.names)
        elif isinstance(node,m.ast.ImportFrom):names.append(node.module.split('.')[0])
    assert set(names)<=set(('argparse','ast','hashlib','itertools','json','pathlib','subprocess'))
