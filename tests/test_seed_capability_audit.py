"""Tiny deterministic fixtures only; never executes the registered pilot or a model."""
from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from nexus.seed.capability_evidence import (EventMeter, SharedLedger, PublicInvestigation,
    make_task, catalogue, digest, parameters, train_public)
from nexus.seed.combined_investigation_engine import EqualizedInvestigationEngineV2, EqualizedControllerConfig
from nexus.seed.symbiotic_workbench import PolyglotCodingWorkbench, contained_repository_path
from nexus.seed.agent_loop_worker import validate_repository_names, run_worker_subprocess

ROOT=Path(__file__).resolve().parents[1]


def config():
    value=json.loads((ROOT/'configs/seed_capability_audit.json').read_text())
    value['operators']=['reverse','increment']
    value['source_tasks']=1
    value['assessment_tasks']=1
    return value


def test_public_view_has_no_reference_or_assessment():
    names={f.name for f in fields(PublicInvestigation)}
    assert not names & {'target_ops','assessment_inputs','oracle_fn','patched_repo_candidates'}


def test_candidate_catalogue_does_not_depend_on_target():
    cfg=config()
    a,_,_=make_task(cfg,1,'source',0)
    b,_,_=make_task(cfg,2,'assessment',0)
    assert [(c,o) for c,o,_ in a.candidate_pool]==[(c,o) for c,o,_ in b.candidate_pool]


def test_probe_shuffle_is_content_invariant():
    cfg=config()
    a,_,_=make_task(cfg,1,'assessment',0)
    b,_,_=make_task(cfg,2,'assessment',0)
    assert sorted(map(digest,a.probe_pool_inputs))==sorted(map(digest,b.probe_pool_inputs))
    assert a.probe_pool_inputs!=b.probe_pool_inputs
    learned=({}, {}, {digest(x):i+1 for i,x in enumerate(a.probe_pool_inputs)}, [])
    pa,_=parameters('capsules_reset',learned,a,1)
    pb,_=parameters('capsules_reset',learned,b,1)
    assert {digest(x):y for x,y in zip(a.probe_pool_inputs,pa.learned_probe_scores[a.domain])}=={
        digest(x):y for x,y in zip(b.probe_pool_inputs,pb.learned_probe_scores[b.domain])}


def test_shared_meter_charges_failed_and_probe_calls():
    events=[]
    ledger=SharedLedger(EventMeter(events.append),'fixture')
    assert ledger.invoke_candidate('x',lambda _:1/0,[], 'probe_construction')=='ERR:ZeroDivisionError'
    assert ledger.n_candidate_calls==len(events)==1
    assert events[0]['status']=='error'


def test_training_only_observed_answers_no_legacy_label_trainer():
    cfg=config(); events=[]
    task,ops,_=make_task(cfg,1,'source',0)
    from scripts.verify_seed_capability_audit import reference
    with patch.object(EqualizedInvestigationEngineV2,'select_and_train_v2',side_effect=AssertionError('legacy labels')):
        weights,freq,credit,caps=train_public([task],{task.task_id:lambda x:reference(ops,x)},EventMeter(events.append),1,cfg)
    assert freq and credit
    assert not any(k.startswith('repo_') for w in weights.values() for k in w)
    assert any(e['operation']=='oracle' for e in events)


def test_strict_controller_same_stop_and_shortlist_with_capsules():
    cfg=config(); task,ops,_=make_task(cfg,1,'assessment',0)
    from scripts.verify_seed_capability_audit import reference
    class Answers:
        def request_answer(self,tid,x):return reference(ops,x)
    outputs=[]
    for name in ('tools','fixed_infogain','prior_reset'):
        events=[]; engine=EqualizedInvestigationEngineV2(ledger_factory=lambda:SharedLedger(EventMeter(events.append),'x'),strict_controller_bounds=True)
        params,mode=parameters(name,({}, {}, {}, []),task,1);engine.set_strategy_params(params)
        out=engine.investigate_v2(task,Answers(),EqualizedControllerConfig(**cfg['controller']),mode,allow_compositional_capsules=name=='prior_reset')
        outputs.append((out['selected_ops'],out['candidate_call_log'],out['oracle_question_log']))
    assert outputs[0]==outputs[1]==outputs[2]


@pytest.mark.parametrize('name',['../escape.py','/tmp/escape.py','x/../../escape.py','x\\escape.py','-x.ts','./x.py'])
def test_worker_rejects_escape(name,tmp_path):
    with pytest.raises(ValueError): validate_repository_names({name:'x'})
    if name.startswith('-'):return
    with pytest.raises(ValueError): contained_repository_path(tmp_path,name)


def test_symlink_escape_and_atomic_path_prevalidation(tmp_path):
    outside=tmp_path/'outside';outside.mkdir()
    root=tmp_path/'repo';root.mkdir();(root/'link').symlink_to(outside,target_is_directory=True)
    bench=PolyglotCodingWorkbench(root)
    with pytest.raises(ValueError):bench.load_repository({'ok.py':'x=1','link/escape.py':'x=2'})
    assert not (root/'ok.py').exists()
    assert not (outside/'escape.py').exists()


def test_actual_python_worker_patch_is_not_lambda_selection():
    payload=dict(language='python',files={'a.py':'def solve(x):\n    return x+1\n'},cases=[dict(entry='a.solve',input=4,expected=5)],trace=True)
    result=run_worker_subprocess(payload)
    assert result['all_passed']
    assert result['results'][0]['actual']==5


def tiny_records():
    """Exercise pilot assembly with fixed unit cases, no tools/model/scientific grid."""
    from nexus.seed import capability_evidence as capability_audit
    cfg=config(); cfg['seeds']=[101,102,103];cfg['coding']=[];cfg['chat']=[]
    records=[]
    def fake_checks(cfg,meter,emit):
        for row in cfg['coding']+cfg['chat']: emit(dict(kind='capability',id=row['id']))
        for name in ('json','sqlite','restart','live_model','z3','sympy'):emit(dict(kind='capability',id=name))
    with patch.object(capability_audit,'run_capability_checks',fake_checks):capability_audit.run(cfg,records.append)
    return cfg,records,capability_audit.summarize(records,cfg)


def test_independent_arithmetic_and_semantic_replay():
    from scripts.verify_seed_capability_audit import verify_records
    cfg,records,summary=tiny_records()
    audit=verify_records(records,cfg,summary)
    assert audit['valid'] and not audit['learning_to_learn_established']


@pytest.mark.parametrize('attack',['delete_event','duplicate_event','outcome','counter','summary','delete_task','duplicate_task','delete_seed','private_field','delete_capability'])
def test_tamper_rejection(attack):
    from scripts.verify_seed_capability_audit import verify_records
    cfg,records,summary=tiny_records()
    events=[r for r in records if r['kind']=='execution']
    if attack=='delete_event':records.remove(events[0])
    elif attack=='duplicate_event':records.append(deepcopy(events[0]))
    elif attack=='outcome':events[-1]['output']='forged'
    elif attack=='counter':events[0]['index']=0
    elif attack=='summary':summary['methods']['tools']['candidate_calls']=0
    elif attack=='delete_task':records.remove(next(r for r in records if r['kind']=='episode'))
    elif attack=='duplicate_task':records.append(deepcopy(next(r for r in records if r['kind']=='episode')))
    elif attack=='delete_seed':records=[r for r in records if r.get('seed')!=101]
    elif attack=='private_field':next(r for r in records if r['kind']=='choice')['target_ops']=['reverse']
    elif attack=='delete_capability':records.remove(next(r for r in records if r['kind']=='capability'))
    with pytest.raises(ValueError):verify_records(records,cfg,summary)


def test_hidden_assessment_cannot_change_locked_choice():
    cfg,records,summary=tiny_records()
    # Public learner views physically have no route to those rows. Poisoning final
    # events afterwards cannot alter an earlier choice and is rejected by verifier.
    locks=deepcopy([r for r in records if r['kind']=='choice'])
    next(r for r in records if r.get('operation')=='assessment_reference')['output']=['poison']
    assert locks==[r for r in records if r['kind']=='choice']


def test_old_verifier_grid_from_locked_config():
    from scripts.verify_seed_learned_investigation_policy_v2 import verify_v2_payload
    cfg=json.loads((ROOT/'configs/seed_learned_investigation_policy_v2.json').read_text())
    partial=dict(equalized_controller=cfg['equalized_controller'],objective_weights=cfg['objective_weights'],records=[])
    valid,errors=verify_v2_payload(partial)
    assert not valid and errors==['missing_duplicate_or_unexpected_grid_cell']
