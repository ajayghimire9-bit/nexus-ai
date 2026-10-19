"""Seed API binding for the SAME loopback Learning Lab server."""
import threading
import uuid
from .core import Session
from .storage import load, save


class SeedWorkspace:
    def __init__(self, directory):
        self.directory = directory
        self.sessions = {}
        self.lock = threading.RLock()
        self.requests = 0

    def dispatch(self, wire):
        if type(wire) is not dict or set(wire) != {'session_id','request'} or type(wire['request']) is not dict:
            raise ValueError('seed_envelope_schema')
        request = wire['request']; sid = wire['session_id']; op = request.get('op')
        # Out-of-band cancellation must not wait behind a search's lock.
        if op == 'stop' and set(request) == {'op'} and sid in self.sessions:
            self.sessions[sid].cancelled.set()
        with self.lock:
            if self.requests >= 500:
                raise ValueError('server_seed_request_cap')
            self.requests += 1
            if op == 'new' and set(request) == {'op'} and sid is None:
                if len(self.sessions) >= 16:
                    raise ValueError('server_session_cap')
                sid = uuid.uuid4().hex; self.sessions[sid] = Session()
                response = self.sessions[sid].request(dict(op='inspect'))
            elif op == 'load' and set(request) == {'op','saved_id','expected_hash'}:
                if len(self.sessions) >= 16 and request['saved_id'] not in self.sessions:
                    raise ValueError('server_session_cap')
                sid = request['saved_id']
                self.sessions[sid] = load(self.directory, sid, request['expected_hash'])
                response = self.sessions[sid].request(dict(op='inspect'))
            elif sid not in self.sessions:
                raise ValueError('active_session_required')
            elif op == 'save' and set(request) == {'op'}:
                saved = save(self.directory, sid, self.sessions[sid])
                response = self.sessions[sid].request(dict(op='inspect'))
                response['saved'] = saved
            elif op == 'export' and set(request) == {'op'}:
                response = self.sessions[sid].request(dict(op='inspect'))
                response['export'] = self.sessions[sid].snapshot()
            else:
                response = self.sessions[sid].request(request)
            return dict(session_id=sid, kind='live_authored_seed', scientific=False, response=response)
