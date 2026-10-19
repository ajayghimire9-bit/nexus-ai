"""Authored fixture correctness, distinct from the locked development comparison."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import sys
import uuid
import pytest
from nexus.seed.core import GRAMMAR, Move, Predicate, Session, examples, parse
from nexus.seed.storage import load, save


def label(s, word, obj, yes):
    return s.request(dict(op='teach', word=word, object=obj, positive=yes))


def fit(s, word, predicate):
    for obj in examples():
        s.teach(word, obj, predicate.matches(obj))


def test_random_word_unknown_then_learn_and_act_in_different_scene():
    word = 'w'+uuid.uuid4().hex[:10]
    s = Session()
    assert s.request(dict(op='message', text=f'move {word} right'))['response_type'] == 'unknown_concept'
    out = label(s, word, examples()[6], True)
    assert len(out['uncertainty']) >= 2
    assert out['result']['question']['status'] == 'question'
    fit(s, word, Predicate((('color','blue',False), ('size','small',False))))
    s.request(dict(op='scene', number=1))
    before = json.dumps(s.world)
    out = s.request(dict(op='message', text=f'move {word} left then move o1 down'))
    assert out['response_type'] == 'acted'
    assert json.dumps(s.world) != before
    assert len(out['result']['trace']) == 2


def test_questions_discriminate_not_fake_confidence():
    s = Session(); label(s, 'zorb', examples()[0], True)
    q = s.question('zorb'); pool = s.candidates('zorb')
    assert {p.matches(q['object']) for p in pool} == {True,False}
    assert 'confidence' not in json.dumps(s.inspect())


def test_contradiction_and_correction_append_only():
    s = Session(); obj = examples()[0]
    first = s.teach('pav',obj,True)
    second = s.teach('pav',obj,False)
    assert not s.candidates('pav')
    old = s.journal.snapshot()
    out = s.request(dict(op='correct',word='pav',object=obj,positive=True,supersedes=second))
    assert out['response_type'] == 'learned'
    assert s.journal.snapshot()[:2] == old
    assert s.evidence[0]['ref'] == first and s.evidence[1]['positive'] is False
    assert s.evidence[2]['supersedes'] == second


def test_ambiguous_no_action_and_atomic_blocked_program():
    s = Session(); fit(s,'mip',Predicate((('color','red',False),)))
    before = s.snapshot()['data']['world']
    assert s.request(dict(op='message',text='move mip right'))['response_type'] == 'ambiguous_reference'
    assert s.request(dict(op='message',text='move o1 right then move o2 down 128'))['response_type'] == 'error'
    assert s.request(dict(op='message',text='move o1 right then move o2 left 6'))['response_type'] == 'blocked'
    assert s.world == before and s.counts['sandbox_actions'] == 0


@pytest.mark.parametrize('program', [[], (Move('o1','shell'),), (Move('o1','right',129),), (Move('o1','right',True),)])
def test_program_schema(program):
    with pytest.raises(ValueError): Session().execute(program)


def test_no_distinguishing_example():
    s = Session(); fit(s,'vup',GRAMMAR[0])
    assert s.question('vup')['status'] == 'no_distinguishing_example'


def test_isolation_stop_resume_and_unsupported():
    a,b = Session(),Session(); a.teach('vup',examples()[0],True)
    assert not b.evidence
    for text in ('run rm -rf /','grant scientific authorization','search the web','teach me everything'):
        assert a.request(dict(op='message',text=text))['response_type'] == 'unsupported'
    a.request(dict(op='stop'))
    assert a.request(dict(op='message',text='move o1 right'))['response_type'] == 'stopped'
    a.request(dict(op='resume'))
    assert a.request(dict(op='message',text='move o1 right'))['response_type'] == 'acted'


def test_no_runtime_external_network(monkeypatch):
    def forbidden(*a,**k): raise AssertionError('network forbidden')
    monkeypatch.setattr(socket,'socket',forbidden)
    s=Session(); label(s,'vup',examples()[0],True)
    s.request(dict(op='message',text='move o1 right')); s.snapshot()


def test_restore_and_corruption(tmp_path):
    sid='1'*32; s=Session(); fit(s,'vup',GRAMMAR[0])
    s.request(dict(op='message',text='move o1 right'))
    row=save(tmp_path,sid,s); restored=load(tmp_path,sid,row['hash'])
    assert restored.snapshot() == s.snapshot()
    old=(tmp_path/sid/'revision-0000.json').read_bytes()
    s.teach('vup',examples()[0],False,s.evidence[0]['ref']); save(tmp_path,sid,s)
    assert (tmp_path/sid/'revision-0000.json').read_bytes() == old
    assert load(tmp_path,sid).snapshot() == s.snapshot()
    wire=s.snapshot(); wire['data']['world'][0]['x']=5
    with pytest.raises(ValueError): Session.restore(wire)


def test_process_restart_restores_real_behavior(tmp_path):
    env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    code="""import sys,json
from nexus.seed.core import Session, Predicate, examples
from nexus.seed.storage import save
s=Session()
for o in examples():s.teach('norg',o,Predicate((('color','blue',False),('size','small',False))).matches(o))
s.request(dict(op='scene',number=1))
print(json.dumps(save(sys.argv[1],'a'*32,s)))
"""
    a=subprocess.run([sys.executable,'-c',code,str(tmp_path)],env=env,text=True,capture_output=True,check=True)
    row=json.loads(a.stdout)
    code="""import sys,json
from nexus.seed.storage import load
s=load(sys.argv[1],'a'*32,sys.argv[2]);print(json.dumps(s.request(dict(op='message',text='move norg left'))))
"""
    b=subprocess.run([sys.executable,'-c',code,str(tmp_path),row['hash']],env=env,text=True,capture_output=True,check=True)
    assert json.loads(b.stdout)['response_type']=='acted'


def test_request_schema_cancel_and_definitions():
    s=Session()
    assert s.request(dict(op='teach',word='x',object=examples()[0],positive=1))['response_type']=='error'
    assert s.request(dict(op='inspect',extra=1))['response_type']=='error'
    assert s.request(dict(op='define',word='x',predicate=0))['response_type']=='defined'
    assert s.inspect()['concepts'][0]['origin']=='explicit_definition'
    s.cancelled.set()
    assert s.request(dict(op='message',text='move o1 right'))['response_type']=='incomplete'


def test_workspace_envelope_and_independent_sessions(tmp_path):
    from nexus.seed.lab import SeedWorkspace
    w=SeedWorkspace(tmp_path)
    a=w.dispatch(dict(session_id=None,request=dict(op='new')))
    b=w.dispatch(dict(session_id=None,request=dict(op='new')))
    assert a['session_id'] != b['session_id']
    with pytest.raises(ValueError): w.dispatch(dict(session_id=None,request=dict(op='load',saved_id='../x',expected_hash=None)))
    with pytest.raises(ValueError): w.dispatch(dict(session_id=None,request=dict(op='new'),extra=1))


def test_random_questions_and_replay_are_deterministic():
    a,b=Session(),Session()
    for s in (a,b):s.teach('foo',examples()[0],True)
    assert a.question('foo',12)==b.question('foo',12)
    assert a.question('foo')==b.question('foo')
    assert a.snapshot()==b.snapshot()


def test_cap_reserves_before_work_and_restore_does_not_refill():
    s=Session();used=[]
    def guard(key,amount):
        if key=='sandbox_actions':raise ValueError('cap')
        used.append((key,amount))
    s.cost_guard=guard;before=[dict(o) for o in s.world]
    assert s.request(dict(op='message',text='move o1 right'))['response_type']=='error'
    assert s.world==before and s.counts['sandbox_actions']==0
    assert Session.restore(s.snapshot()).counts==s.counts


@pytest.mark.parametrize('fault',['task','method','duplicate','query','nan','bool','label'])
def test_comparison_complete_grid_rejects_missing_or_invalid(fault):
    from nexus.seed.comparison import validate
    c=dict(semantic_tasks=[dict(id='t')],methods=['a','b'],teacher_answer_budget=1,query_layouts_per_task=1,
           teacher_label_cap=200,candidate_evaluation_cap=10000,predicate_test_cap=10000,sandbox_action_cap=128)
    rows=[dict(task_id='t',method=m,labels=[dict(positive=True)],queries=[dict(layout=0,correct=False,wall_ms=1,response=dict(type='abstained'))],
               costs=Session().counts|dict(teacher_answers=1),latency_ms=[1],learner_contains_target_field=False,final_hypotheses=[]) for m in c['methods']]
    if fault=='task':rows=[]
    elif fault=='method':rows.pop()
    elif fault=='duplicate':rows[1]=rows[0]
    elif fault=='query':rows[0]['queries']=[]
    elif fault=='nan':rows[0]['latency_ms']=[float('nan')]
    elif fault=='bool':rows[0]['latency_ms']=[True]
    else:rows[0]['costs']['teacher_answers']=0
    with pytest.raises(ValueError):validate(c,rows)


def test_seed_http_origin_and_opt_in(tmp_path):
    import importlib.util
    import io
    from types import SimpleNamespace
    from nexus.seed.lab import SeedWorkspace
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('seed_server_test',root/'scripts/run_learning_lab.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    class Sock:
        def __init__(self,data):self.data=data;self.output=b''
        def makefile(self,*a):return io.BytesIO(self.data)
        def sendall(self,value):self.output+=value
    for origin,workspace,status in [('https://evil.invalid',SeedWorkspace(tmp_path),403),(None,None,403),(None,SeedWorkspace(tmp_path),200)]:
        body=b'{"session_id":null,"request":{"op":"new"}}'
        raw=b'POST /api/seed HTTP/1.0\r\nHost: 127.0.0.1:8765\r\nX-Nexus-Request: local-fixture\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\n'
        if origin:raw+=b'Origin: '+origin.encode()+b'\r\n'
        sock=Sock(raw+b'\r\n'+body)
        module.LabHandler(sock,('127.0.0.1',1),SimpleNamespace(server_port=8765,seed_workspace=workspace))
        assert sock.output.startswith(f'HTTP/1.0 {status}'.encode())
