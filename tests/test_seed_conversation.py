"""Authored conversation fixtures only; no scientific study or neural training."""
from copy import deepcopy
import json
import uuid
import pytest
from nexus.seed.lab import SeedWorkspace
from nexus.seed.core import Session
from nexus.seed.conversation import INITIAL,interpret,turns
from nexus.seed.shared_brain import SharedBrain
from nexus.seed import skill_library as lib
from nexus.seed.storage import load


@pytest.fixture
def workspace(tmp_path):
    w=SeedWorkspace(tmp_path);sid=w.dispatch(dict(session_id=None,request={'op':'new'}))['session_id'];return w,sid


def send(pair,text,identifier=None):
    w,sid=pair
    return w.dispatch(dict(session_id=sid,request=dict(op='chat_send',text=text,id=identifier or uuid.uuid4().hex)))['response']


def teach_reverse(w):
    for t in ('Teach you a skill from examples.','reverse','[3, 1, 2, 1] -> [1, 2, 1, 3]','[4, 0, 4, 2] -> [2, 4, 0, 4]'):r=send(w,t)
    assert r['chat']['messages'][-1]['status']=='success'


def test_composed_code_executes_and_replay_is_idempotent(workspace):
    identifier=uuid.uuid4().hex
    result=send(workspace,'Write code to sort and remove duplicates on [3, 1, 3, 2]',identifier)
    card=result['chat']['messages'][-1]['cards'][0]['data']
    assert card['executed'] and card['output']==[1,2,3]
    assert card['instructions']==5 and 'sorted' in card['python']
    duplicate=send(workspace,'Write code to sort and remove duplicates on [3, 1, 3, 2]',identifier)
    assert duplicate['duplicate']
    assert interpret('Write code to import os',deepcopy(INITIAL)).kind=='unsupported'


def test_taught_multiword_phrase_uses_verified_skill(workspace):
    teach_reverse(workspace)
    result=send(workspace,'Teach phrase "turn the numbers around" as reverse')
    assert result['chat']['messages'][-1]['status']=='success'
    run=send(workspace,'Run phrase "turn the numbers around" on [1, 2, 3]')
    assert run['chat']['messages'][-1]['cards'][0]['data']['value']==[3,2,1]
    assert send(workspace,'Teach phrase "turn the numbers around" as reverse')['chat']['messages'][-1]['status']=='error'


def test_generated_lessons_actual_answers_and_fixed_numbering(workspace):
    from nexus.seed.foundation.runtime import state
    w,sid=workspace;out=send(workspace,'Generate lessons')
    assert len(out['chat']['messages'][-1]['cards'])==4
    tasks=list(state(w.sessions[sid])['lessons'].values())
    for i in (1,0,2,3):
        result=send(workspace,f"Answer lesson {i+1}: "+json.dumps(tasks[i]['expected']))
        assert result['chat']['messages'][-1]['cards'][0]['data']['correct']
    assert len(state(w.sessions[sid])['curriculum_feedback'])==4


def test_workbench_inspection_does_not_change_graph_or_learning(workspace):
    w,sid=workspace;before=w.sessions[sid].counts.copy()
    out=send(workspace,'Show phases')
    assert len(out['chat']['messages'][-1]['cards'][0]['data'])==7
    assert w.sessions[sid].counts==before


@pytest.mark.parametrize('text,kind',[('Hello!','hello'),('What can you do?','help'),('I want to teach you a word.','start'),('A dax means a red object.','definition'),('Use the reverse skill on [1, 2, 3].','run'),('Apply this skill to [3, 4]','run'),('What does that word mean?','meaning'),('Show me some examples.','examples'),('What have you learned?','memory'),('Move the red object to the top-right corner.','goal'),('Correct my previous example.','correct'),('Save this conversation.','save'),('Help me find the pattern.','start'),('Buy stocks for me','unsupported')])
def test_wording(text,kind):assert interpret(text,deepcopy(INITIAL)).kind==kind


def test_language_definition_requires_user_check_and_reference_resolution(workspace):
    w,sid=workspace;r=send(workspace,'A dax means a red object.')
    assert r['chat']['context']['pending']['kind']=='check_label'
    assert not lib.state(w.sessions[sid])['active']
    q=r['chat']['context']['pending']['input'];answer=q['color']=='red'
    r=send(workspace,'yes' if answer else 'no');assert r['chat']['messages'][-1]['status']=='success'
    assert lib.state(w.sessions[sid])['active']['dax'][1]['program']['literals']==[['color','red',False]]
    assert 'dax is verified' in send(workspace,'What does that word mean?')['text']
    send(workspace,'I want to teach you a word.')
    assert send(workspace,'What does that word mean?')['chat']['messages'][-1]['status']=='clarification'


def test_coding_separate_checks_cross_lab_use_and_no_self_verification(workspace):
    teach_reverse(workspace)
    r=send(workspace,'Use the reverse skill on [1, 2, 3].');assert '[3, 2, 1]' in r['text']
    assert '[5, 4]' in send(workspace,'Use this skill on [4, 5]')['text']
    assert 'reverse (verified)' in send(workspace,'What have you learned?')['text']


def test_reasoning_pattern_flow(workspace):
    for text in ('Help me find the pattern.','nextwise','[2, 0, 1] -> [3, 1, 2]\n[1, 1, 2] -> [2, 2, 3]','[4, -1, 0] -> [5, 0, 1]'):r=send(workspace,text)
    assert r['chat']['context']['lab']=='reasoning'
    assert '[3, 5]' in send(workspace,'Use this skill on [2, 4]')['text']


def test_world_clarifies_before_acting_and_counts_actual_actions(workspace):
    w,sid=workspace;s=w.sessions[sid];before=deepcopy(s.world)
    r=send(workspace,'Move the red object to the top-right corner.')
    assert r['chat']['context']['pending']['kind']=='object' and s.world==before and s.counts['sandbox_actions']==0
    r=send(workspace,'o1');assert r['chat']['messages'][-1]['status']=='success'
    assert s.world[0]['x']==5 and s.world[0]['y']==0 and r['resources']['sandbox_actions']==5
    assert send(workspace,'Move it down')['resources']['sandbox_actions']==1


def test_correction_preserves_evidence_and_verified_revision(workspace):
    teach_reverse(workspace);w,sid=workspace;s=w.sessions[sid];old=lib.state(s)['active']['reverse'];events=s.journal.snapshot()
    r=send(workspace,'That answer was wrong.');assert r['chat']['context']['pending']['kind']=='correction'
    r=send(workspace,'[3, 1, 2, 1] -> [3, 1, 2, 1]')
    state=lib.state(s);assert state['active']['reverse']==old
    assert s.journal.snapshot()[:len(events)]==events
    latest=state['latest']['reverse'];assert latest[1]['supersedes'] in state['teaching']
    assert r['chat']['context']['pending']['kind']=='checks'
    r=send(workspace,'[4, 0, 4, 2] -> [4, 0, 4, 2]')
    assert r['chat']['messages'][-1]['status']=='error'  # consumed old check stays protected


def test_save_restore_is_data_only_for_chat_and_deduplicates_actions(workspace,monkeypatch):
    w,sid=workspace;send(workspace,'Move o1 to top-right corner.')
    token=uuid.uuid4().hex;send(workspace,'Move it down',token);s=w.sessions[sid];before=s.snapshot()
    duplicate=send(workspace,'Move it down',token);assert duplicate['duplicate'] and s.snapshot()==before
    with pytest.raises(ValueError,match='mismatch'):send(workspace,'Move it up',token)
    r=send(workspace,'Save this conversation.');receipt=r['saved'];snapshot=s.snapshot()
    monkeypatch.setattr(SharedBrain,'request',lambda *a,**k:(_ for _ in ()).throw(AssertionError('no_chat_operation_replay')))
    restored=load(w.directory,sid,receipt['hash']);assert restored.snapshot()==snapshot
    assert restored.world==s.world and restored.counts==s.counts and len(turns(restored))==len(turns(s))


def test_inspection_and_session_isolation(workspace):
    w,sid=workspace;send(workspace,'A dax means a red object.');before=w.sessions[sid].snapshot()
    for _ in range(3):w.dispatch(dict(session_id=sid,request={'op':'chat_view'}))
    assert w.sessions[sid].snapshot()==before
    other=w.dispatch(dict(session_id=None,request={'op':'new'}))['session_id']
    assert not w.dispatch(dict(session_id=other,request={'op':'chat_view'}))['response']['chat']['messages']
    assert not lib.state(w.sessions[other])['latest']


@pytest.mark.parametrize('text',[None,42,'',' ' *3,'a'*3001,'bad\x00text'])
def test_malformed_chat_text(workspace,text):
    w,sid=workspace;before=w.sessions[sid].snapshot()
    with pytest.raises((ValueError,TypeError)):send(workspace,text)
    assert w.sessions[sid].snapshot()==before


def test_checks_cannot_be_reused_as_teaching_and_unsafe_programs_do_not_execute(workspace):
    teach_reverse(workspace);w,sid=workspace
    send(workspace,'Correct my previous example.')
    r=send(workspace,'[4, 0, 4, 2] -> [4, 0, 4, 2]');assert r['chat']['messages'][-1]['status']=='error'
    before=dict(w.sessions[sid].counts)
    r=send(workspace,'__import__("os").system("no")');assert r['chat']['messages'][-1]['status']=='clarification'
    assert w.sessions[sid].counts==before


def test_script_text_stays_plain_data_and_transcript_tampering_rejected(workspace):
    w,sid=workspace;send(workspace,'<img src=x onerror=alert(1)>');wire=w.sessions[sid].snapshot()
    assert '<img' in turns(w.sessions[sid])[-1]['user']
    assert Session.restore(wire).snapshot()==wire
    from nexus.evolution1.catalogue import digest
    event=wire['data']['events'][-1];p=json.loads(event['payload_json']);p['context']['active_name']='../../bad'
    # Schema and journal hashes must both validate; no pickle or code loading.
    event['payload_json']=json.dumps(p);wire['sha256']=digest(wire['data'])
    with pytest.raises(ValueError):Session.restore(wire)


def test_pause_and_resume_keep_existing_limits(workspace):
    w,sid=workspace;send(workspace,'stop');r=send(workspace,'Move o1 right')
    assert r['chat']['messages'][-1]['status']=='error' and w.sessions[sid].counts['sandbox_actions']==0
    send(workspace,'resume');assert send(workspace,'Move o1 right')['resources']['sandbox_actions']==1
    w.requests=500
    with pytest.raises(ValueError,match='request_cap'):send(workspace,'hello')
