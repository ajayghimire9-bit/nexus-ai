"""Same-server HTTP boundaries with authored fixture sessions only."""
import importlib.util
import json
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import pytest
from nexus.seed.lab import SeedWorkspace
ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def host(tmp_path):
    spec=importlib.util.spec_from_file_location('chat_server',ROOT/'scripts/run_learning_lab.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    with ThreadingHTTPServer(('127.0.0.1',0),m.LabHandler) as server:
        server.seed_workspace=SeedWorkspace(tmp_path);server.fixtures_enabled=False;server.requests_remaining=0
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:yield f'http://127.0.0.1:{server.server_port}',server
        finally:server.shutdown();thread.join(3)


def test_chat_is_main_entry_and_assets_are_local_and_csp_protected(host):
    url,_=host
    for route,content in [('/','Let’s learn something'),('/chat','composer-form'),('/chat.css','prefers-reduced-motion'),('/chat.js','textContent'),('/labs','Shared Learning Labs')]:
        with urlopen(url+route) as r:
            assert content in r.read().decode()
            assert "frame-ancestors 'none'" in r.headers['Content-Security-Policy']
    with pytest.raises(HTTPError):urlopen(url+'/chat.js?path=../../no')


def test_same_envelope_origin_and_body_limits_apply(host):
    url,server=host
    headers={'Content-Type':'application/json','X-Nexus-Request':'local-fixture'}
    def post(payload,**kwargs):return urlopen(Request(url+'/api/seed',data=json.dumps(payload).encode(),headers=kwargs.get('headers',headers)))
    with post(dict(session_id=None,request={'op':'new'})) as r:sid=json.load(r)['session_id']
    with post(dict(session_id=sid,request=dict(op='chat_send',text='Hello',id='1'*32))) as r:assert json.load(r)['response']['chat']['messages'][0]['assistant'].startswith('Hello')
    for payload in [dict(session_id=sid,request=dict(op='chat_send',text='hi',id='bad')),dict(session_id=sid,request=dict(op='chat_send',text='x'*3001,id='2'*32)),dict(session_id='missing',request={'op':'chat_view'}),dict(session_id=sid,request=dict(op='chat_send',text='hi',id='3'*32,grant=True))]:
        with pytest.raises(HTTPError) as exc:post(payload)
        assert exc.value.code==400
    with pytest.raises(HTTPError) as exc:post(dict(session_id=sid,request={'op':'chat_view'}),headers={**headers,'Origin':'https://untrusted.example'})
    assert exc.value.code==403
    with pytest.raises(HTTPError) as exc:post({'large':'x'*70000})
    assert exc.value.code==400
    assert server.seed_workspace.sessions[sid].counts['sandbox_actions']==0


def test_restore_rejects_wrong_receipt_without_losing_an_existing_conversation(tmp_path):
    w=SeedWorkspace(tmp_path);sid=w.dispatch(dict(session_id=None,request={'op':'new'}))['session_id']
    w.dispatch(dict(session_id=sid,request=dict(op='chat_send',text='Hello',id='a'*32)))
    receipt=w.dispatch(dict(session_id=sid,request={'op':'save'}))['response']['saved'];before=w.sessions[sid].snapshot()
    with pytest.raises(ValueError):w.dispatch(dict(session_id=None,request=dict(op='load',saved_id=sid,expected_hash='0'*64)))
    assert w.sessions[sid].snapshot()==before
    assert receipt['hash']!='0'*64


def test_oversize_save_fails_before_writing_an_unrestorable_revision(tmp_path,monkeypatch):
    from nexus.seed import storage
    from nexus.seed.core import Session
    monkeypatch.setattr(storage,'canonical',lambda _: 'x'*2_000_001)
    with pytest.raises(ValueError,match='size_cap'):storage.save(tmp_path,'a'*32,Session())
    assert not list(tmp_path.rglob('revision-*.json'))
