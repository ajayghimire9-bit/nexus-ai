"""Seed API binding for the SAME loopback Learning Lab server."""
import threading
import uuid
from .core import Session
from .storage import load, save


class SeedWorkspace:
    def __init__(self, directory, *, language_encoder=None, meta_questions=False, grounded_model=None, grounded_hash=None, action_readout=None,plasticity_controller=None,plasticity_hash=None,surprise_gate=None,shared_model=None,shared_hash=None):
        self.directory = directory
        self.sessions = {}
        self.lock = threading.RLock()
        self.requests = 0
        self.language_encoder = language_encoder
        self.meta_questions = meta_questions
        self.grounded_model = grounded_model
        self.grounded_hash = grounded_hash
        self.action_readout=action_readout
        self.plasticity_controller=plasticity_controller;self.plasticity_hash=plasticity_hash
        self.surprise_gate=surprise_gate
        self.shared_model=shared_model;self.shared_hash=shared_hash

    def attach_grounded(self, session):
        if self.grounded_model is not None:
            from .grounded_agent import GroundedAgent
            from .adaptive_state import AdaptiveState
            adaptive=AdaptiveState(self.plasticity_controller) if self.plasticity_controller is not None else None
            import copy
            session.grounded_agent=GroundedAgent(self.grounded_model,self.grounded_hash,self.action_readout,adaptive,self.plasticity_hash,copy.deepcopy(self.surprise_gate))
            session.grounded_agent.restore_state(session)

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
                sid = uuid.uuid4().hex; self.sessions[sid] = Session(language_encoder=self.language_encoder,meta_questions=self.meta_questions)
                self.attach_grounded(self.sessions[sid])
                response = self.sessions[sid].request(dict(op='inspect'))
            elif op == 'load' and set(request) == {'op','saved_id','expected_hash'}:
                if len(self.sessions) >= 16 and request['saved_id'] not in self.sessions:
                    raise ValueError('server_session_cap')
                sid = request['saved_id']
                self.sessions[sid] = load(self.directory, sid, request['expected_hash'])
                # Runtime capabilities are owner-selected CLI settings, never
                # granted by saved evidence or a client payload.
                self.sessions[sid].language_encoder=self.language_encoder
                self.sessions[sid].meta_questions=self.meta_questions
                self.attach_grounded(self.sessions[sid])
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
            elif type(op) is str and op.startswith('structure_'):
                from .structure.runtime import request as structure_request
                response=structure_request(self.sessions[sid],request)
            elif type(op) is str and op.startswith('lab_'):
                from .shared_brain import SharedBrain
                response=SharedBrain(self.sessions[sid],self.shared_model,self.shared_hash).request(request)
            elif op in ('chat_send','chat_view'):
                from .shared_brain import SharedBrain
                from .conversation import Conversation
                chat=Conversation(SharedBrain(self.sessions[sid],self.shared_model,self.shared_hash))
                if op=='chat_view' and set(request)=={'op'}:
                    response=dict(text='Conversation restored without resubmitting messages.',chat=chat.view())
                elif op=='chat_send' and set(request)=={'op','text','id'}:
                    response=chat.send(request['text'],request['id'])
                    if response.pop('save_requested',False):
                        response['saved']=save(self.directory,sid,self.sessions[sid])
                        response['notification']='Conversation saved locally.'
                else:raise ValueError('typed_chat_request')
            else:
                response = self.sessions[sid].request(request)
            return dict(session_id=sid, kind='live_authored_seed', scientific=False, response=response)
