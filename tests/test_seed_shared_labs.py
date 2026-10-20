"""Authored engineering fixtures; no scientific task collection or model fit."""
from copy import deepcopy
import itertools
import json
from pathlib import Path
import subprocess
import sys
import pytest
from nexus.seed.core import Session,examples
from nexus.seed.shared_brain import SharedBrain
from nexus.seed import skill_programs as ir
from nexus.seed import skill_library as lib
from nexus.evolution1.catalogue import digest

ROOT=Path(__file__).resolve().parents[1]


def teach(b,name,rows,schema='list',lab='coding',mode='enumerate',supersedes=None):
    return b.request(dict(op='lab_teach',lab=lab,name=name,schema=schema,examples=rows,mode=mode,supersedes=supersedes))['result']


def check(b,name,attempt,rows):return b.request(dict(op='lab_check',name=name,attempt=attempt,checks=rows))['result']
def row(x,y):return dict(input=x,output=y)
def predict(b,name,x,lab='reasoning'):return b.request(dict(op='lab_run',lab=lab,name=name,input=x))['result']


def reverse_skill(b,name='flip'):
    t=teach(b,name,[row([3,1,2,1],[1,2,1,3])]);assert t['candidate_count']==1
    q=check(b,name,t['attempt'],[row([4,0,4,2],[2,4,0,4])]);assert q['status']=='accepted'
    return t,q


def concept_skill(b):
    objects=examples();t=teach(b,'glim',[row(objects[i],i in (0,4)) for i in (0,4,1,6,15)],schema='predicate',lab='language')
    assert t['candidate_count']==1
    q=check(b,'glim',t['attempt'],[row(objects[2],True),row(objects[12],False)])
    assert q['status']=='accepted';return t,q


def test_one_library_reuses_coding_program_in_reasoning_and_fewer_checks():
    s=Session();b=SharedBrain(s);t,_=reverse_skill(b)
    assert predict(b,'flip',[5,2,3])['output']==[3,2,5]
    n=teach(b,'mirror',[row([7,2,0],[0,2,7])],lab='reasoning',mode='reuse_first')
    assert n['candidate_count']==1
    record=lib.state(s)['teaching'][n['attempt']]
    assert record['origin']=='shared_verified_skill' and record['candidate_evaluations']==1
    assert check(b,'mirror',n['attempt'],[row([1,2,2],[2,2,1])])['status']=='accepted'
    assert predict(b,'mirror',[4,2,1],'coding')['output']==[1,2,4]
    assert len(lib.view(s)['entries'])==2 and not lib.view(s)['learning_to_learn_demonstrated']


def test_language_concept_drives_world_command_goal_and_exact_reward():
    s=Session();b=SharedBrain(s);concept_skill(b)
    r=b.request(dict(op='lab_command',text='move glim right'))['result'];assert r['status']=='acted'
    assert (s.world[0]['x'],s.world[0]['y'])==(1,0)
    r=b.request(dict(op='lab_goal',reference='glim',x=1,y=1))['result']
    assert r['status']=='acted' and r['reward']==pytest.approx(1.18)
    assert s.counts['sandbox_actions']==2 and (s.world[0]['x'],s.world[0]['y'])==(1,1)
    restored=Session.restore(s.snapshot());assert restored.snapshot()==s.snapshot()
    assert lib.view(restored)==lib.view(s)
    assert restored.request(dict(op='message',text='move glim right'))['response_type']=='acted'
    with pytest.raises(ValueError,match='shared_word'):restored.teach('glim',examples()[0],False)


def test_motion_skill_runs_as_code_and_executes_in_same_world():
    s=Session();b=SharedBrain(s)
    t=teach(b,'nudge',[row(dict(x=1,y=1),dict(x=2,y=1)),row(dict(x=2,y=2),dict(x=3,y=2))],schema='motion',lab='world')
    assert t['candidate_count']==1
    check(b,'nudge',t['attempt'],[row(dict(x=0,y=3),dict(x=1,y=3))])
    assert predict(b,'nudge',dict(x=3,y=2),'coding')['output']==dict(x=4,y=2)
    assert b.request(dict(op='lab_world_skill',name='nudge',reference='o1'))['result']['status']=='acted'
    assert s.world[0]['x']==1


def test_reasoning_relation_is_inferred_then_reused_in_language():
    b=SharedBrain(Session());o=examples();pair=lambda i,j:dict(first=o[i],second=o[j])
    t=teach(b,'lefter',[row(pair(0,3),True),row(pair(6,2),True)],schema='relation',lab='reasoning')
    assert t['candidate_count']==1
    assert check(b,'lefter',t['attempt'],[row(pair(1,4),True),row(pair(4,1),False)])['status']=='accepted'
    assert predict(b,'lefter',pair(2,5),'language')['output'] is True
    from nexus.seed.semantic_lessons import RELATIONS as original
    from nexus.seed.relations import RELATIONS
    assert original is RELATIONS


def test_failed_proposal_and_check_preserve_previous_verified_knowledge():
    s=Session();b=SharedBrain(s);old,accepted=reverse_skill(b);before=lib.state(s)['active']['flip']
    conflict=teach(b,'flip',[row([3,1,2,1],[3,1,2,1])]);assert conflict['status']=='retain'
    assert lib.state(s)['active']['flip']==before and predict(b,'flip',[3,2,1])['output']==[1,2,3]
    correction=teach(b,'flip',[row([7,2,1],[1,2,7])],supersedes=conflict['attempt'])
    assert correction['candidate_count']==1
    rejected=check(b,'flip',correction['attempt'],[row([6,2,0],[6,2,0])]);assert rejected['status']=='rejected'
    assert lib.state(s)['active']['flip']==before
    with pytest.raises(ValueError,match='consumed'):check(b,'flip',correction['attempt'],[row([9,2,0],[0,2,9])])


def test_disjoint_assessments_cannot_fit_candidates_or_be_reused_as_teaching():
    s=Session();b=SharedBrain(s);t=teach(b,'flip',[row([3,1,2,1],[1,2,1,3])]);models=deepcopy(lib.state(s)['latest'])
    with pytest.raises(ValueError,match='fresh_disjoint'):check(b,'flip',t['attempt'],[row([3,1,2,1],[1,2,1,3])])
    meta=deepcopy(lib.view(s)['learning_rules']);check(b,'flip',t['attempt'],[row([4,0,4,2],[2,4,0,4])])
    assert lib.state(s)['latest']==models and lib.view(s)['learning_rules']==meta
    with pytest.raises(ValueError,match='cannot_become_teaching'):teach(b,'flip',[row([4,0,4,2],[2,4,0,4])])


def test_semantic_input_identity_blocks_id_coordinate_holdout_disguise():
    b=SharedBrain(Session());t=teach(b,'glim',[row(examples()[0],True)],schema='predicate',lab='language')
    # Reconstruct a unique meaning first, then attempt a disguised training row.
    t=teach(b,'glim',[row(examples()[4],True),row(examples()[1],False),row(examples()[6],False),row(examples()[15],False)],schema='predicate',lab='language')
    fake=dict(examples()[0],id='other',x=5,y=5)
    with pytest.raises(ValueError,match='fresh_disjoint'):check(b,'glim',t['attempt'],[row(fake,True)])


def test_future_source_feedback_changes_rule_statistics_assessment_does_not():
    s=Session();b=SharedBrain(s)
    t=teach(b,'flip',[row([3,1,2,1],[1,2,1,3])],mode='adaptive')
    empty=lib.view(s)['learning_rules'];assert not empty['kind_n']
    b.request(dict(op='lab_ask',name='flip'));assert lib.view(s)['learning_rules']==empty
    later=teach(b,'flip',[row([0,2,1,1],[1,1,2,0])],mode='adaptive')
    stats=lib.view(s)['learning_rules'];assert stats['kind_n']=={'list/enumerate':1}
    assert later['feedback'][0]['before_error']==1 and later['feedback'][0]['after_error']==0
    assert later['rule']=='reuse_first' # controlled exploration of unseen rule
    before=deepcopy(stats);check(b,'flip',later['attempt'],[row([4,0,4,2],[2,4,0,4])]);assert lib.view(s)['learning_rules']==before
    restored=Session.restore(s.snapshot());assert lib.view(restored)['learning_rules']==stats


def test_inspection_is_read_only_and_rollback_keeps_evidence():
    s=Session();b=SharedBrain(s);t,first=reverse_skill(b)
    later=teach(b,'flip',[row([7,0,1],[1,0,7])]);second=check(b,'flip',later['attempt'],[row([8,1,2],[2,1,8])])
    snap=s.snapshot();b.request(dict(op='lab_inspect'));b.request(dict(op='lab_inspect'));assert snap==s.snapshot()
    n=len(s.journal.snapshot());b.request(dict(op='lab_rollback',name='flip',target=first['revision']))
    assert len(s.journal.snapshot())==n+1 and lib.state(s)['active']['flip'][0]==first['revision']
    assert Session.restore(s.snapshot()).snapshot()==s.snapshot()


def test_question_contains_only_unlabeled_disagreement_and_does_not_change_policy():
    s=Session();b=SharedBrain(s);teach(b,'thing',[row(examples()[0],True)],schema='predicate',lab='language')
    before=s.snapshot();q=b.request(dict(op='lab_ask',name='thing'))['result']
    assert q['status']=='ask' and 'output' not in q and ir.input_key('predicate',q['input'])!=ir.input_key('predicate',examples()[0])
    assert s.snapshot()==before


@pytest.mark.parametrize('program,x',[({'schema':'list','ops':['__import__']},[1]),({'schema':'list','ops':['reverse']*3},[1]),({'schema':'list','ops':['sort'],'code':'import os'},[1]),({'schema':'motion','ops':['left']},dict(x=0,y=1))])
def test_program_limits_fail_closed(program,x):
    with pytest.raises(ValueError):ir.run(program,x)


@pytest.mark.parametrize('x',[[True],[float('nan')],list(range(17)),[65],'__import__("os")'])
def test_typed_inputs_reject_unsafe_or_unbounded_values(x):
    with pytest.raises(ValueError):ir.value('list',x)


def test_program_canonicalization_is_exact_on_exhaustive_small_fixture_inputs():
    xs=[list(x) for n in range(4) for x in itertools.product((-1,0,1,2),repeat=n)]
    for a,b in itertools.product(ir.LIST_OPS,repeat=2):
        p=dict(schema='list',ops=[a,b]);q=ir.canonical(p)
        assert all(ir.run(p,x)==ir.run(q,x) for x in xs)
    assert len({digest(p) for p in ir.catalogue('list')})==len(ir.catalogue('list'))


def test_rule_kernel_exactly_matches_existing_epsilon_greedy():
    from nexus.meta.controller import EpsilonGreedyController
    from nexus.meta.kind_statistics import observe_kind,kind_value
    c=EpsilonGreedyController();sums={};counts={}
    for kind,reward in [('a',1.),('b',-.1),('a',.3),('a',-.25),('b',.5)]:
        c.update((),kind,reward);observe_kind(sums,counts,kind,reward)
        assert c.predicted_kind_value((),kind)==kind_value(sums,counts,kind)


def test_optional_shared_neural_encoder_is_frozen_and_inspection_does_not_advance_it():
    import torch
    from nexus.world.seed_rssm import SeedRSSM
    with torch.random.fork_rng():torch.manual_seed(701);model=SeedRSSM().eval()
    for p in model.parameters():p.requires_grad_(False)
    before={k:v.clone() for k,v in model.state_dict().items()};s=Session();b=SharedBrain(s,model,'a'*64)
    # Random test weights are fixture plumbing, never claimed to be trained.
    x=b.encode('list',[[2,1]]);y=b.encode('list',[[2,1]]);assert torch.equal(x,y) and x.shape==(1,32)
    assert b.encode('predicate',[examples()[0]]).shape==(1,32)
    assert b.encode('relation',[dict(first=examples()[0],second=examples()[3])]).shape==(1,32)
    assert b.encode('motion',[dict(x=2,y=1)]).shape==(1,32)
    reverse_skill(b);assert len(lib.state(s)['latest']['flip'][1]['prototype'])==32
    assert b.inspect()['architecture']['encoder_parameters']==7552
    assert predict(b,'flip',[5,2,3])['retrieval']==['flip']
    work=dict(model.work);snap=s.snapshot();b.request(dict(op='lab_inspect'));b.request(dict(op='lab_inspect'))
    assert model.work==work and snap==s.snapshot() and all(torch.equal(v,model.state_dict()[k]) for k,v in before.items())
    assert Session.restore(s.snapshot()).snapshot()==s.snapshot()
    model.train()
    with pytest.raises(ValueError,match='frozen'):SharedBrain(s,model,'a'*64)


def test_session_save_reload_and_stdlib_only_replay(tmp_path):
    from nexus.seed.storage import save,load
    s=Session();b=SharedBrain(s);reverse_skill(b);concept_skill(b);sid='a'*32
    receipt=save(tmp_path,sid,s);restored=load(tmp_path,sid,receipt['hash']);assert restored.snapshot()==s.snapshot()
    p=tmp_path/'snapshot.json';p.write_text(json.dumps(s.snapshot()))
    code="import sys,json;sys.path.insert(0,sys.argv[1]);from nexus.seed.core import Session;from nexus.seed.shared_brain import SharedBrain;s=Session.restore(json.load(open(sys.argv[2])));assert len(SharedBrain(s).inspect()['shared_library']['entries'])==2;assert not any(m in sys.modules for m in ('torch','numpy','gymnasium'))"
    subprocess.run([sys.executable,'-I','-S','-c',code,str(ROOT/'src'),str(p)],check=True)


def test_snapshot_rejects_forged_derived_candidates_and_feedback():
    s=Session();b=SharedBrain(s);reverse_skill(b);snapshot=s.snapshot()
    # Rehashing a fabricated event chain does not bypass deterministic replay.
    from nexus.evolution1.fixtures import Journal
    events=s.journal.snapshot();j=Journal()
    for e in events:
        p=json.loads(e.payload_json)
        if e.kind=='seed_shared_teaching':p['candidates']=[]
        j.append(e.kind,p)
    from dataclasses import asdict
    d=deepcopy(snapshot['data']);d['events']=[asdict(e) for e in j.snapshot()]
    with pytest.raises(ValueError,match='not_reproduced'):Session.restore(dict(data=d,sha256=digest(d)))


def test_workspace_uses_same_session_and_explicit_capabilities(tmp_path):
    from nexus.seed.lab import SeedWorkspace
    w=SeedWorkspace(tmp_path);sid=w.dispatch(dict(session_id=None,request=dict(op='new')))['session_id']
    t=w.dispatch(dict(session_id=sid,request=dict(op='lab_teach',lab='coding',name='flip',schema='list',examples=[row([3,1,2,1],[1,2,1,3])],mode='enumerate',supersedes=None)))
    assert t['kind']=='live_authored_seed' and t['scientific'] is False
    saved=w.dispatch(dict(session_id=sid,request=dict(op='save')))['response']['saved']
    again=w.dispatch(dict(session_id=None,request=dict(op='load',saved_id=sid,expected_hash=saved['hash'])))
    assert again['session_id']==sid
    with pytest.raises(ValueError):w.dispatch(dict(session_id=sid,request=dict(op='lab_teach',code='arbitrary')))


def test_world_boundary_and_stopped_state_cannot_bypass_existing_guards():
    s=Session();b=SharedBrain(s);before=deepcopy(s.world)
    assert b.request(dict(op='lab_command',text='move o1 left'))['result']['status']=='blocked'
    assert s.world==before and s.counts['sandbox_actions']==0
    s.request(dict(op='stop'))
    with pytest.raises((ValueError,TimeoutError)):b.request(dict(op='lab_goal',reference='o1',x=2,y=2))
    assert b.request(dict(op='lab_inspect'))['response_type']=='inspection'


def test_validation_outcomes_do_not_update_selector_or_change_existing_teaching():
    a=SharedBrain(Session());b=SharedBrain(Session())
    first=teach(a,'flip',[row([3,1,2,1],[1,2,1,3])],mode='adaptive')
    other=teach(b,'flip',[row([3,1,2,1],[1,2,1,3])],mode='adaptive')
    check(a,'flip',first['attempt'],[row([4,0,4,2],[2,4,0,4])])
    check(b,'flip',other['attempt'],[row([4,0,4,2],[4,0,4,2])])
    assert lib.view(a.session)['learning_rules']==lib.view(b.session)['learning_rules']
    assert lib.state(a.session)['latest']==lib.state(b.session)['latest']
    assert len(lib.state(a.session)['active'])==1 and not lib.state(b.session)['active']


def test_wrong_encoder_hash_fails_before_loading_any_weights(tmp_path):
    from nexus.world.seed_rssm import SeedRSSM
    path=tmp_path/'core.json';path.write_text('{}')
    with pytest.raises(ValueError,match='hash'):SeedRSSM.load(path,'0'*64)


def test_shared_controller_does_not_reuse_neural_action_belief():
    b=SharedBrain(Session());b.session.grounded_agent=object()
    with pytest.raises(ValueError,match='without_neural_action_controller'):b.request(dict(op='lab_goal',reference='o1',x=1,y=1))
